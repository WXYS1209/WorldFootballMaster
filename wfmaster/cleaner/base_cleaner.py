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
            team_mapping_path: Path to team mapping Excel file
        """
        self.config = get_config(config_dir)

        self._load_team_mappings()
        self._setup_logging()
        self.data = None
        self.clean_data = None
        
    def _setup_logging(self):
        """Configure logging for the cleaner"""
        log_file = os.path.join(self.config.output_dir, f"{self.__class__.__name__.lower()}.log")
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s: %(message)s'
        )
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def clean(self, *args, **kwargs):
        """Main cleaning method to be implemented by subclasses"""
        pass
    
    def save(self, filename: Optional[str] = None) -> None:
        """Save cleaned data to Excel file
        
        Args:
            filename: Name of output file. If None, uses default name.
        """
        if not self._validate_data(self.clean_data):
            self.logger.error("No data to save")
            return
            
        output_file = filename or os.path.join(self.config.output_dir, f'sch_{self.__class__.__name__.lower()}_clean.xlsx')
        self.clean_data.to_excel(output_file, index=False)
        self.logger.info(f"Cleaned schedule saved to {output_file}")
    
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
                self.config.team_mapping_path,
                sheet_name="n0"
            ).drop_duplicates(['Org', 'Team_Code']).reset_index(drop=True)
            
            self.code_mapping = pd.read_excel(
                self.config.team_mapping_path,
                sheet_name="m0"
            )
        except Exception as e:
            self.logger.error(f"Error loading team mappings: {e}")
            raise
    
    def _add_team_codes(self, schedule: pd.DataFrame) -> pd.DataFrame:
        """Add team codes to schedule data
        
        Args:
            schedule: Schedule DataFrame
            team_mapping: Team mapping DataFrame
            
        Returns:
            pd.DataFrame: Schedule with team codes
        """
        schedule_with_codes = schedule.merge(
            self.team_mapping[['Org', 'Team_Code']], 
            how='left', 
            left_on='Home_Team', 
            right_on='Org'
        ).rename(columns={'Team_Code': 'hometeam_id'}).merge(
            self.team_mapping[['Org', 'Team_Code']], 
            how='left', 
            left_on='Away_Team', 
            right_on='Org'
        ).rename(columns={'Team_Code': 'awayteam_id'})
        
        if schedule_with_codes['hometeam_id'].isna().any() or schedule_with_codes['awayteam_id'].isna().any():
            self.logger.warning("New team name detected in the schedule.")
            
        return schedule_with_codes
    
    def _merge_team_names(self, schedule: pd.DataFrame) -> pd.DataFrame:
        """Merge English team names
        
        Args:
            schedule: Schedule DataFrame
            code_mapping: Code mapping DataFrame
            
        Returns:
            pd.DataFrame: Schedule with English team names
        """
        sch = schedule.merge(
            self.code_mapping, 
            how='left', 
            left_on='hometeam_id', 
            right_on='Team_Code'
        ).rename(columns={'Eng_Name': 'hometeam'}).merge(
            self.code_mapping, 
            how='left', 
            left_on='awayteam_id', 
            right_on='Team_Code'
        ).rename(columns={'Eng_Name': 'awayteam'})
        
        sch['match'] = sch['hometeam'] + " vs. " + sch['awayteam']
        
        return sch
    
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
    
    @abstractmethod
    def _process_round(self, *args, **kwargs):
        """Process round information"""
        pass