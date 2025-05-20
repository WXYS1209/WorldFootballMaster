import pandas as pd
from datetime import datetime, timedelta
import os
from typing import Optional, Tuple
from .base_cleaner import BaseCleaner

class LeagueCleaner(BaseCleaner):
    """Cleaner for five major European football leagues schedule data"""
    
    def __init__(self, config_dir: str = None):
        """Initialize FiveLeagueCleaner
        
        Args:
            input_dir: Directory containing input files
            output_dir: Directory to save output files
            team_mapping_path: Path to team mapping Excel file
        """
        super().__init__(config_dir)
        self.clean_data = None
        self.final_data = None
    
    def clean(self, input_data: pd.DataFrame) -> pd.DataFrame:
        """Clean the schedule data
        
        Args:
            input_data: Original data
            
        Returns:
            pd.DataFrame: Cleaned schedule data
        """
        self.logger.info("="*10 + "Start cleaning schedules" + "="*10)
        
        try:
            self.clean_data = self._process_schedule(input_data)
            # return self.clean_data
            
        except Exception as e:
            self.logger.error(f"An error occurred during cleaning: {e}", exc_info=True)
            raise
    
    def _process_schedule(self, schedule: pd.DataFrame) -> pd.DataFrame:
        """Process and clean schedule data
        
        Args:
            schedule: Raw schedule DataFrame
            
        Returns:
            pd.DataFrame: Processed schedule data
        """
        
        # Add team codes
        schedule_with_codes = self._add_team_codes(schedule)
        
        sch = self._merge_team_names(schedule_with_codes)
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
    
    def _process_round(self, schedule: pd.DataFrame) -> pd.DataFrame:
        schedule['match_round'] = schedule['Round']
        schedule['match_stage'] = "League"
        return schedule
    
    def update_final_schedule(self, final_schedule_path: Optional[str] = None, initial: bool = False) -> None:
        """Update the final schedule file
        
        Args:
            final_schedule_path: Path to final schedule Excel file
            initial: Whether this is the initial run. If True, will create Sequence sheet
        """
        if not self._validate_data(self.clean_data):
            self.logger.error("No cleaned data available")
            return
            
        final_path = final_schedule_path or os.path.join(self.config.output_dir, '五大联赛赛程.xlsx')
        
        try:
            if initial:
                # For initial run, use clean_data as both sequence and schedule
                self.logger.info("Initial run - creating sequence from clean data")
                df_seq = self.clean_data[['season', 'competition', 'hometeam_id', 'hometeam', 'awayteam_id', 'awayteam', 'match_round']].copy()
                # Create match_id by grouping and using cumcount
                # Add sequential match number within each season/competition group
                df_seq['Match_in_Season'] = df_seq.groupby(['season', 'competition']).cumcount() + 1
                df_seq['match_id'] = df_seq[['competition','season', 'Match_in_Season']].astype(str).agg('_'.join, axis=1)
                # df_final_org = self.clean_data.copy()
                # df_final_org['modified_time'] = pd.Timestamp(datetime.today().date())
                # df_final_org['Match_in_Season'] = df_seq['Match_in_Season']
                # df_final_org['match_id'] = df_seq['match_id']
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
            # print(df_final.columns)
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
    
    def _save_final_schedule(self, path: str, df_final: pd.DataFrame, 
                           df_update_info: pd.DataFrame, df_stat: pd.DataFrame) -> None:
        """Save final schedule to Excel
        
        Args:
            path: Path to save Excel file
            df_final: Final schedule DataFrame
            df_update_info: Update information DataFrame
            df_stat: Statistics DataFrame
        """
        with pd.ExcelWriter(path, mode='a', if_sheet_exists='replace') as writer:
            df_final.to_excel(writer, sheet_name="Schedule", index=False)
            df_update_info.to_excel(writer, sheet_name="Update_Info")
            df_stat.to_excel(writer, sheet_name="Summary")
            
        self.logger.info(f"Final schedule updated and saved to {path}")
    
    def save(self, filename: Optional[str] = None) -> None:
        """Save cleaned data to Excel file
        
        Args:
            filename: Name of output file
        """
        if not self._validate_data(self.clean_data):
            self.logger.error("No clean data to save")
            return
            
        output_file = filename or os.path.join(self.config.output_dir, 'sch_five_league_clean.xlsx')
        self.clean_data.to_excel(output_file, index=False)
        self.logger.info(f"Cleaned schedule saved to {output_file}")
        self.logger.info("="*10 + "Done cleaning schedules" + "="*10)
    
    def clean_round(self, round_num: int):
        pass
    