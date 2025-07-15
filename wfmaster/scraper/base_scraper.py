from abc import ABC, abstractmethod
import pandas as pd
import logging
import os
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from ..config import get_config

class BaseScraper(ABC):
    """Base class for all scrapers"""
    
    # Common columns for all competition types
    COMMON_COLUMNS = [
        'Season', 'Competition', 'Round', 'Date', 'Time', 
        'Home_Team', 'Away_Team', 'Score', 'Group', 'Stage',
        'Comp_Code', 'gender', 'sport', 'discipline', 
        'match_url', 'home_url', 'away_url', 
    ]
    
    def __init__(self, config_dir: str = None):
        """Initialize the scraper with basic configuration
        
        Args:
            config_dir: Optional directory containing configuration files
        """
        self.config = get_config(config_dir)
        self._setup_logging()
        self.data = pd.DataFrame(columns=self.COMMON_COLUMNS)
        
    def _setup_logging(self):
        """Configure logging for the scraper"""
        log_file = os.path.join(self.config.output_dir, "worldfootball_master.log")
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s: %(message)s'
        )
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def scrape(self, *args, **kwargs):
        """Main scraping method to be implemented by subclasses"""
        pass
    
    def save(self, filename: Optional[str] = None) -> None:
        """Save scraped data to Excel file
        
        Args:
            filename: Name of output file. If None, uses default name.
        """
        if not self._validate_data(self.data):
            self.logger.error("No data to save")
            return
            
        output_file = filename or os.path.join(self.config.output_dir, f'sch_{self.__class__.__name__.lower()}.xlsx')
        self.data.to_excel(output_file, index=False)
        self.logger.info(f"Schedule saved to {output_file}")
        
    def _validate_data(self, df: pd.DataFrame) -> bool:
        """Validate scraped data
        
        Args:
            df: DataFrame containing scraped data
            
        Returns:
            bool: True if data is valid, False otherwise
        """
        return not df.empty if isinstance(df, pd.DataFrame) else False
    
    def _extract_team_url(self, cell: BeautifulSoup) -> str:
        """Extract team URL from cell. Common method for all scrapers.
        
        Args:
            cell: BeautifulSoup cell element
            
        Returns:
            str: Team URL or empty string
        """
        team_link = cell.find('a')
        return f"https://chn.worldfootball.net/{team_link['href']}" if team_link else ""
    
    def _extract_match_url(self, cell: BeautifulSoup) -> str:
        """Extract match URL from cell. Common method for all scrapers.
        
        Args:
            cell: BeautifulSoup cell element
            
        Returns:
            str: match URL or empty string
        """
        match_link = cell.find('a')
        return f"https://chn.worldfootball.net/{match_link['href']}" if match_link else ""
    
    def _process_dates(self) -> None:
        """Process and format dates in the dataframe. Common method for all scrapers."""
        self.data['Date'] = self.data['Date'].replace('', None)
        self.data['Date'] = self.data['Date'].ffill()
        self.data['Date'] = pd.to_datetime(self.data['Date'], format='%d/%m/%Y', errors='coerce')
    
    def _extract_match_data(self, cells: List, season: str, competition: str, round_info: str) -> Dict:
        """Extract basic match data from table cells. Common method for all scrapers.
        
        Args:
            cells: List of table cells
            competition: Competition name
            round_info: Round or stage information
            
        Returns:
            dict: Extracted match data
        """
        return {
            'Season': season,
            'Competition': competition,
            'Round': round_info,
            'Date': cells[0].text.strip(),
            'Time': cells[1].text.strip(),
            'Home_Team': cells[2].text.strip(),
            'Away_Team': cells[4].text.strip(),
            'Score': cells[5].text.strip(),
            'match_url': self._extract_match_url(cells[5]),
            'home_url': self._extract_team_url(cells[2]),
            'away_url': self._extract_team_url(cells[4])
        }
