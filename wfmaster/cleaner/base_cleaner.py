from abc import ABC, abstractmethod
import pandas as pd
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from ..config import get_config

class BaseCleaner(ABC):
    """Base class for all cleaners"""
      # Common columns for cleaned data
    CLEANED_COLUMNS = [
        'match', 'competition_id', 'property', 'edition', 'season', 'competition', 
        'hometeam_id', 'hometeam', 'awayteam_id', 'awayteam', 
        'kickoff_time', 'finish_time', 'bj_kickoff', 'bj_finish', 'match_dur_s',
        'hometeam_score', 'awayteam_score', 'hometeam_result', 'awayteam_result', 'status',
        'venue', 'venue_country', 'attendance', 
        'match_group', 'match_round', 'match_stage', 
        'gender', 'sport', 'discipline', 'event', 
        'live_timeslot', 'date', 'match_url', 'home_url', 'away_url', 'modified_time'
        # 'Score', 'Score_Half', 'temp', 'Home Url', 'Away Url', 'Modified_Time'
    ]
    FINAL_COLUMNS = ['match_id'] + CLEANED_COLUMNS + ['Match_in_Season', 'note']

    def __init__(self, config_dir: str = None):
        """Initialize the cleaner
        
        Args:
            input_dir: Directory containing input files
            output_dir: Directory to save output files
            team_mapping_file: Path to team mapping Excel file
        """
        self.config = get_config(config_dir)

        self._load_team_mappings()
        self._setup_logging()
        self.data = None
        self.clean_data = None
        
    def _setup_logging(self):
        """Configure logging for the cleaner"""
        log_file = os.path.join(self.config.output_dir, "worldfootball_master.log")
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s: %(message)s'
        )
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def clean(self, input_data: pd.DataFrame) -> pd.DataFrame:
        """Clean the schedule data
        
        Args:
            input_data: Original data
            
        Returns:
            pd.DataFrame: Cleaned schedule data
        """
        self.logger.info("="*10 + "Start cleaning schedules" + "="*10)
        if input_data.empty:
            return
        try:
            self.clean_data = self._process_schedule(input_data)
            
        except Exception as e:
            self.logger.error(f"An error occurred during cleaning: {e}", exc_info=True)
            raise
    
    def save(self, filename: Optional[str] = None) -> None:
        """Save cleaned data to Excel file
        
        Args:
            filename: Name of output file. If None, uses default name.
        """
        if not self._validate_data(self.clean_data):
            self.logger.error("No data to save")
            return
            
        output_file = filename or os.path.join(self.config.output_dir, f'sch_{self.__class__.__name__.lower()}.xlsx')
        self.clean_data.to_excel(output_file, index=False)
        self.logger.info(f"Cleaned schedule saved to {output_file}")
        self.logger.info("="*10 + "Done cleaning schedules" + "="*10)
    
    def update_final_schedule(self, final_schedule_path: Optional[str] = None, initial: bool = False) -> None:
        """Update the final schedule file
        
        Args:
            final_schedule_path: Path to final schedule Excel file
            initial: Whether this is the initial run. If True, will create Sequence sheet
        """
        if not self._validate_data(self.clean_data):
            self.logger.error("No clean data available")
            return
            
        final_path = final_schedule_path # or os.path.join(self.config.output_dir, 'Schedule.xlsx')
        
        if not os.path.exists(final_path):
            initial = True
            # Create an empty Excel file with the required sheets and columns
            with pd.ExcelWriter(final_path) as writer:
                pd.DataFrame(columns=['season', 'competition', 'hometeam_id', 'hometeam', 'awayteam_id', 'awayteam', 'match_round', 'Match_in_Season', 'match_id']).to_excel(writer, sheet_name="Sequence", index=False)
                pd.DataFrame(columns=self.FINAL_COLUMNS).to_excel(writer, sheet_name="Schedule", index=False)

        try:
            if initial:
                # For initial run, use clean_data as both sequence and schedule
                self.logger.info("Initial run - creating sequence from clean data")
                df_seq = self.clean_data[['season', 'competition', 'hometeam_id', 'hometeam', 'awayteam_id', 'awayteam', 'match_round']].copy()
                # Create match_id by grouping and using cumcount
                # Add sequential match number within each season/competition group
                df_seq['Match_in_Season'] = df_seq.groupby(['season', 'competition']).cumcount() + 1
                df_seq['match_id'] = df_seq[['competition','season', 'Match_in_Season']].astype(str).agg('_'.join, axis=1)
                df_final_org = pd.DataFrame(columns=self.FINAL_COLUMNS)

                # Save sequence first
                with pd.ExcelWriter(final_path) as writer:
                    df_seq.to_excel(writer, sheet_name="Sequence", index=False)
                # return
            else:
                # Normal operation - load existing files
                df_seq = pd.read_excel(final_path, sheet_name="Sequence")
                df_final_org = pd.read_excel(final_path, sheet_name="Schedule")
            
            # Merge with sequence
            df_final = df_seq.merge(self.clean_data, how="left", on=['season', 'competition', 'hometeam_id', 'hometeam', 'awayteam_id', 'awayteam', 'match_round'])

            # Check for modifications
            df_check = self._check_modifications(df_final, df_final_org)
            
            # Mutate modified time
            if not initial:
                df_final['modified_time'] = df_final_org['modified_time']
                df_final.loc[df_check['modified'] == True, 'modified_time'] = pd.Timestamp(datetime.today().date())
                df_final['note'] = pd.NA
                df_final.loc[df_check['modified'] == True, 'note'] = "Modified"
            
            else:
                df_final['modified_time'] = pd.Timestamp(datetime.today().date())
                df_final['note'] = "Initial scrape"

            # Generate statistics
            df_update_info = df_check.loc[df_check['modified'] == True, ['season', 'competition', 'match_round']].value_counts().sort_index()
            df_stat = df_final.loc[df_final['status'].notna(), ['season', 'competition', 'match_round']].value_counts().sort_index()
            
            self.logger.info(f"Number of schedule updated: {df_update_info.sum()}")
            
            # Save updates
            self._save_final_schedule(final_path, df_final[self.FINAL_COLUMNS], df_update_info, df_stat)
            
        except Exception as e:
            self.logger.error(f"Error updating final schedule: {e}", exc_info=True)
            raise
    
    def _check_modifications(self, df_final: pd.DataFrame, df_final_org: pd.DataFrame) -> pd.DataFrame:
        """Check for modifications between new and original schedule
        
        Args:
            df_final: New final schedule
            df_final_org: Original final schedule
            
        Returns:
            pd.DataFrame: DataFrame with modification flags
        """
        df_check = df_final.merge(
            df_final_org,
            how="left",
            on=['season', 'competition', 'match_round', 'hometeam', 'awayteam', 'match_id'],
            suffixes=["_new", "_old"]
        )
        
        df_check['modified'] = pd.NA
        mask = ~(df_check['status_new'].isna() & df_check['status_old'].isna())
        df_check.loc[mask, 'modified'] = (df_check['status_new'] != df_check['status_old'])[mask]
        
        return df_check
    
    def _save_final_schedule(self, path: str, df_final: pd.DataFrame, df_update_info: pd.DataFrame, df_stat: pd.DataFrame) -> None:
        """Save final schedule to Excel
        
        Args:
            path: Path to save Excel file
            df_final: Final schedule DataFrame
            df_update_info: Update information DataFrame
            df_stat: Statistics DataFrame
        """
        with pd.ExcelWriter(path, mode='a', if_sheet_exists='replace', engine='openpyxl') as writer:
            df_final.to_excel(writer, sheet_name="Schedule", index=False)
            df_update_info.to_excel(writer, sheet_name="Update_Info")
            df_stat.to_excel(writer, sheet_name="Summary")
            
        self.logger.info(f"Final schedule updated and saved to {path}")
    

    def _validate_data(self, df: pd.DataFrame) -> bool:
        """Validate cleaned data
        
        Args:
            df: DataFrame containing cleaned data
            
        Returns:
            bool: True if data is valid, False otherwise
        """
        return not df.empty if isinstance(df, pd.DataFrame) else False
    
    def _load_team_mappings(self) -> None:
        """Load team mapping data"""
        try:
            self.team_mapping = pd.read_excel(
                self.config.team_mapping_file,
                sheet_name="alias"
            )
            
        except Exception as e:
            self.logger.error(f"Error loading team mappings: {e}")
            raise
    
    def _clean_team(self, schedule: pd.DataFrame) -> pd.DataFrame:
        """Add team codes to schedule data
        
        Args:
            schedule: Schedule DataFrame
            team_mapping: Team mapping DataFrame
            
        Returns:
            pd.DataFrame: Schedule with team codes
        """
        # Normalize case for merging
        schedule['Home_Team'] = schedule['Home_Team'].str.lower()
        schedule['Away_Team'] = schedule['Away_Team'].str.lower()
        self.team_mapping['alias'] = self.team_mapping['alias'].str.lower()

        schedule_clean = schedule.merge(
            self.team_mapping, 
            how='left', 
            left_on='Home_Team', 
            right_on='alias'
        ).rename(columns={'team_id': 'hometeam_id', 'csm_name': 'hometeam'}).merge(
            self.team_mapping, 
            how='left', 
            left_on='Away_Team', 
            right_on='alias'
        ).rename(columns={'team_id': 'awayteam_id', 'csm_name': 'awayteam'})
        
        if schedule_clean['hometeam_id'].isna().any() or schedule_clean['awayteam_id'].isna().any():
            self.logger.warning("New team name detected in the schedule.")
        
        schedule_clean['match'] = schedule_clean['hometeam'] + " vs. " + schedule_clean['awayteam']
        return schedule_clean
    
    def _format_time_to_26(self, time_str: str) -> str:
        """Format time string to 26-hour format
        
        Args:
            time_str: Time string to format
            
        Returns:
            str: Formatted time string
        """
        if pd.isna(time_str):
            return pd.NA
            
        tmp = time_str.split(":")
        hh, mm = map(int, tmp[0:2])
        
        ss = int(tmp[2]) if len(tmp) == 3 else 0
        
        if hh < 2:
            hh += 24
        elif (hh == 2 and (mm + ss) == 0):
            hh += 24
            
        return f'{hh}:{mm:02d}'
    
    def _format_season(self, season: str) -> str:
        """Format season string from YYYY-YYYY to YYYY/YY format
        
        Args:
            season: Season string (e.g. '2024-2025')
            
        Returns:
            str: Formatted season string (e.g. '2024/25')
        """
        if isinstance(season, str) and '-' in season:
            try:
                start_year, end_year = season.split('-')
                if len(start_year) == 4 and len(end_year) == 4:
                    return f"{start_year}/{end_year[2:]}"
            except ValueError:
                pass
        return season
        
    def _process_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process match scores and calculate results
        
        Args:
            df: DataFrame to process
            
        Returns:
            pd.DataFrame: Processed DataFrame
        """
        # Split score into components
        df[['Score', 'Score_Half']] = df['Score'].str.split(' ', expand=True).loc[:, 0:1]
        scores = df['Score'].str.split(':', expand=True)
        scores = scores.apply(lambda col: pd.to_numeric(col.str.strip(), errors='coerce'))
        df[['hometeam_score', 'awayteam_score']] = scores.astype('Int64')
        
        # Calculate match results
        df['hometeam_result'] = df.apply(lambda row: 
            pd.NA if pd.isna(row['hometeam_score']) or pd.isna(row['awayteam_score'])
            else 'W' if row['hometeam_score'] > row['awayteam_score']
            else 'L' if row['hometeam_score'] < row['awayteam_score']
            else 'T', axis=1
        )
        
        df['awayteam_result'] = df.apply(lambda row:
            pd.NA if pd.isna(row['hometeam_score']) or pd.isna(row['awayteam_score'])
            else 'W' if row['hometeam_score'] < row['awayteam_score']
            else 'L' if row['hometeam_score'] > row['awayteam_score']
            else 'T', axis=1
        )
        
        return df
    
    def _process_status(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process match status and duration
        
        Args:
            df: DataFrame to process
            
        Returns:
            pd.DataFrame: Processed DataFrame
        """
        
        # Set default status
        df['status'] = df['Score_Half'].apply(
            lambda x: pd.NA if pd.isna(x)
            else 'dnp' if "dnp" in x
            else 'penalty shootout' if 'pso' in x
            else 'extra time' if 'aet' in x
            else 'decision' if 'dec.' in x
            else 'annulled' if 'annulled' in x
            else 'full time'
        )
        
        return df
    
    def _process_datetime(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process date and time information
        
        Args:
            df: DataFrame to process
            
        Returns:
            pd.DataFrame: Processed DataFrame
        """
        # Calculate match duration
        # Duration mapping in seconds
        duration_map = {
            "full time": 7200,        # 2 hours
            "extra time": 9000,       # 2.5 hours 
            "penalty shootout": 10800, # 3 hours
            "decision": 1,
            "dnp": 0
        }
        
        df['match_dur_s'] = df['status'].map(lambda x: duration_map.get(x, 7200) if pd.notna(x) else pd.NA)

        # Create date string
        df['Date_Org'] = df['Date'].apply(lambda x: x.strftime('%Y-%m-%d'))
        
        # Create datetime string
        df['DateTime_str'] = df.apply(
            lambda row: row['Date_Org'] + " " + row['Time'] if pd.notna(row['Time'])
            else row['Date_Org'] + " " + "00:00",
            axis=1
        )
        
        # Convert to timestamp
        df['Time_Stamp'] = pd.to_datetime(df['DateTime_str'])
        
        # Process time format
        df['kickoff_time'] = df['Time'].apply(self._format_time_to_26)
        df['finish_time'] = df.apply(
            lambda row: 
                self._format_time_to_26((datetime.strptime(row['Time'], '%H:%M') + timedelta(seconds=row['match_dur_s'])).strftime('%H:%M'))
                if (pd.notna(row['Time']) & pd.notna(row['match_dur_s'])) else pd.NA,
            axis = 1
        )
        # 1) kickoff_time as <NA> if status is missing
        df['kickoff_time'] = df.apply(
            lambda row: pd.NA
                        if pd.isna(row['status'])
                        else self._format_time_to_26(row['Time']),
            axis=1
        )

        # 2) date adjusted (or <NA>) if status is missing
        df['date'] = df.apply(
            lambda row: pd.NA if pd.isna(row['status'])
            else (
                (row['Date'] - timedelta(days=1))
                if (pd.isna(row['kickoff_time']) or int(row['kickoff_time'].split(':')[0]) >= 24)
                else row['Date']
            ),
            axis=1
        )

        # 3) bj_kickoff as NaT (<NA> for datetime) if status is missing
        df['bj_kickoff'] = df.apply(
            lambda row: pd.NaT
                        if pd.isna(row['status'])
                        else row['Time_Stamp'],
            axis=1
        )

        df['finish_time'] = df.apply(
            lambda row: (
                self._format_time_to_26(
                    (datetime.strptime(row['Time'], '%H:%M')
                    + timedelta(seconds=row['match_dur_s']))
                    .strftime('%H:%M')
                )
            ) if (pd.notna(row['Time']) and pd.notna(row['match_dur_s'])) else pd.NA,
            axis=1
        )

        df['live_timeslot'] = df.apply(
            lambda row: pd.NA
                        if pd.isna(row['status'])
                        else f"{row['kickoff_time']}-{row['finish_time']}",
            axis=1
        )
        
        df['bj_finish'] = df.apply(
            lambda row: (
                row['bj_kickoff'] + timedelta(seconds=row['match_dur_s'])
            ) if pd.notna(row['match_dur_s']) else pd.NaT,
            axis=1
        )

        return df
    
    def _process_schedule(self, schedule: pd.DataFrame) -> pd.DataFrame:
        """Process and clean schedule data
        
        Args:
            schedule: Raw schedule DataFrame
            
        Returns:
            pd.DataFrame: Processed schedule data
        """
        
        # Add team codes
        sch = self._clean_team(schedule)
        
        # sch = self._merge_team_names(schedule_with_codes)
        sch = self._process_scores(sch)
        sch = self._process_status(sch)
        sch = self._process_datetime(sch)
        sch = self._process_round(sch)

        sch['season'] = sch['Season'].apply(self._format_season)
        sch['competition'] = sch['Competition']

        # Keep only specified columns and add missing ones with NA
        missing_cols = set(self.CLEANED_COLUMNS) - set(sch.columns)
        for col in missing_cols:
            sch[col] = pd.NA
        sch = sch[self.CLEANED_COLUMNS]
        return sch
    
    @abstractmethod
    def _process_round(self, *args, **kwargs):
        """Process round information"""
        pass