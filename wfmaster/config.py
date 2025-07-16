"""Configuration management for wfmaster"""
import os
from pathlib import Path
import pandas as pd
from typing import Dict, Optional
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Config:
    """Configuration manager for wfmaster"""
    def __init__(self, config_dir: Optional[str] = None):
        """Initialize configuration
        
        Args:
            config_dir: Directory containing configuration files.
                        If None, uses environment variable or default.
        """        
        # Set config directory
        self.config_dir = config_dir or os.getenv('CONFIG_DIR')
        if self.config_dir is None:
            # Get the package root directory (parent of this file's directory)
            package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.config_dir = os.path.join(package_dir, 'config')
        
        # Set paths from environment variables
        self.team_mapping_file = os.getenv('TEAM_MAPPING_FILE')
        self.output_dir = os.getenv('OUTPUT_DIR')
        self.league_mapping_file = os.getenv('LEAGUE_MAP_FILE')
        self.cup_mapping_file = os.getenv('CUP_MAP_FILE')
        
        self._league_mapping = None
        self._competition_mapping = None
    
    @property
    def league_mapping(self) -> pd.DataFrame:
        """Get league mapping DataFrame"""
        if self._league_mapping is None:
            if not self.league_mapping_file:
                self._league_mapping = pd.DataFrame(columns=['League', 'Country', 'League_Name', 'Round', 'League_Type', 'Season', 'Gender'])  # Return empty DataFrame with specified columns if no cup mapping file
            else:
                path = os.path.join(self.config_dir, self.league_mapping_file)
                self._league_mapping = pd.read_csv(path)
        return self._league_mapping
    
    @property
    def competition_mapping(self) -> pd.DataFrame:
        """Get competition mapping DataFrame"""
        if self._competition_mapping is None:
            if not self.cup_mapping_file:
                self._competition_mapping = pd.DataFrame(columns=['Comp_Code', 'Competition', 'Comp_Name', 'Comp_Type', 'Season', 'Gender'])  # Return empty DataFrame with specified columns if no cup mapping file
            else:
                path = os.path.join(self.config_dir, self.cup_mapping_file)
                self._competition_mapping = pd.read_csv(path)
        return self._competition_mapping

# Global configuration instance
_config = None

def get_config(config_dir: Optional[str] = None) -> Config:
    """Get or create the global configuration instance
    
    Args:
        config_dir: Optional configuration directory
        
    Returns:
        Config: Configuration instance
    """
    global _config
    if _config is None:
        _config = Config(config_dir)
    return _config
