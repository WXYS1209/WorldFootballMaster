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
    
    def _process_round(self, schedule: pd.DataFrame) -> pd.DataFrame:
        schedule['match_round'] = schedule['Round']
        schedule['match_stage'] = "League"
        return schedule
    
