"""UEFA competitions data cleaner"""
import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
from .base_cleaner import BaseCleaner

class CupCleaner(BaseCleaner):
    """Cleaner for UEFA competition schedules"""
    
    def __init__(self, config_dir: str = None):
        """Initialize UEFACleaner
        
        Args:
            input_dir: Directory containing input files
            output_dir: Directory to save output files
            team_mapping_path: Path to team mapping Excel file
        """
        super().__init__(config_dir)
        self.clean_data = None
    
    def _process_round(self, schedule: pd.DataFrame) -> pd.DataFrame:

        def update_round(group):
            group = group.sort_values(by=["Date", 'bj_kickoff']).reset_index(drop=True)
            group["Round_num"] = 1  # 初始化 Round_num
            for i in range(1, len(group)):
                if (group.loc[i, "Date"] - group.loc[i - 1, "Date"]).days > 2:
                    group.loc[i, "Round_num"] = group.loc[i - 1, "Round_num"] + 1
                else:
                    group.loc[i, "Round_num"] = group.loc[i - 1, "Round_num"]
            return group

        # 按 Comp_Code 和 Round 分组并应用函数
        schedule = schedule.groupby(["Competition", "Season", "Round"], group_keys=False).apply(update_round)
        # sch = sch.drop_duplicates().reset_index(drop=True)

        schedule['match_round'] = schedule.apply(
            lambda row: f"Round {row['Round_num']:02d}"
            if ('Group' in row['Round'] or 'League phase' in row['Round'])
            else row['Round'],
            axis=1
        )

        schedule['match_stage'] = schedule.apply(
            lambda row: "Group Stage"
            if ('Group' in row['Round'] or 'League phase' in row['Round'])
            else pd.NA if "Round" in row['Round']
            else row['Round'],
            axis=1
        )

        schedule['match_group'] = schedule['Round'].apply(
            lambda x: x if 'Group' in x else ""
        )
        
        # schedule['match_round'] = schedule['Round']
        # schedule['match_stage'] = "League"
        return schedule
    
