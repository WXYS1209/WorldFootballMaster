import pandas as pd
from datetime import datetime, timedelta
import os
from typing import Optional, Tuple
from .base_cleaner import BaseCleaner

class LeagueCleaner(BaseCleaner):
    """Cleaner for football leagues schedule data"""
    
    def __init__(self, config_dir: str = None):
        """
        Initialize the LeagueCleaner for football leagues.

        Args:
            config_dir (str, optional): Path to the directory containing configuration files. If None, uses default config location.
        """
        super().__init__(config_dir)
        self.clean_data = None
    
    def _process_round(self, schedule: pd.DataFrame) -> pd.DataFrame:
        """
        Process round information for league schedules by assigning match_round and match_stage columns.

        Args:
            schedule (pd.DataFrame): Schedule DataFrame to process.

        Returns:
            pd.DataFrame: Schedule DataFrame with round and stage information added.
        """
        schedule['match_round'] = schedule['Round']
        schedule['match_stage'] = "League"
        return schedule
    
    def update_final_schedule(self, final_schedule_path: Optional[str] = None, initial: bool = False) -> None:
        """
        Update the final schedule Excel file with cleaned data, handling both initial and incremental updates.

        Args:
            final_schedule_path (str, optional): Path to the final schedule Excel file. If None, uses default output location.
            initial (bool): Whether this is the initial run. If True, creates the Sequence sheet and initializes the file.
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
    