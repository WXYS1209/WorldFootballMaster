"""UEFA Cup competitions scraper implementation"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm
import os
from typing import Dict, List, Optional
from .competition_scrapers import CupScraper
from ..config import get_config

class UEFAScraper(CupScraper):
    """Scraper for UEFA competitions (UCL, UEL, UECL, etc.)"""      
    def __init__(self, output_dir: str = None, config_dir: str = None):
        """Initialize UEFAScraper
        
        Args:
            output_dir: Directory to save output files
            config_dir: Optional directory containing configuration files
        """
        super().__init__(output_dir)
        self.config = get_config(config_dir)
        self.COMPETITION_MAP = self.config.competition_mapping
        self.current_season = self.config.current_season
        self.config = get_config(config_dir)
        self.COMPETITION_MAP = self.config.competition_mapping
        
    def scrape(self, season: str = None) -> pd.DataFrame:
        """Scrape data for all UEFA competitions
        
        Args:
            season: Season to scrape data for
            
        Returns:
            pd.DataFrame: Scraped match data
        """
        self.logger.info("="*10 + "Start scraping UEFA schedules" + "="*10)
        
        for cc in tqdm(range(len(self.COMPETITION_MAP)), desc="Scraping competitions", unit="competition"):
            self.logger.info(f"Scraping Competition: {self.COMPETITION_MAP.Comp_Name[cc]}")
            self._scrape_competition(cc, season)
        
        self._process_dates()
        return self.data
    
    def scrape_stage(self, stage: str, season: str = '2024-2025', competition: str = None) -> pd.DataFrame:
        """Scrape specific stage of a competition
        
        Args:
            stage: Stage name to filter
            season: Season to scrape
            competition: Optional competition code to filter
            
        Returns:
            pd.DataFrame: Filtered match data
        """
        self.scrape(season)
        filtered_data = self.data[self.data['Round'] == stage]
        if competition:
            filtered_data = filtered_data[filtered_data['Comp_Code'] == competition]
        return filtered_data
    
    def _scrape_competition(self, comp_num: int, season: str) -> None:
        """Scrape matches for a specific competition
        
        Args:
            comp_num: Index in COMPETITION_MAP
            season: Season string
        """
        # Handle special season formats for certain competitions
        season = self._adjust_season(comp_num, season)
        
        url = self._build_url(comp_num, season)
        response = requests.get(url)
        
        if response.status_code != 200:
            self.logger.error(f"Failed to retrieve data from {url} with status code {response.status_code}")
            return
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        try:
            match_table = soup.find_all('table', class_='standard_tabelle')[0]
        except IndexError:
            self.logger.error(f"No match table found at URL: {url}")
            return
            
        self._parse_matches(match_table, comp_num, season)
    
    def _adjust_season(self, comp_num: int, season: str) -> str:
        """Adjust season string for special competitions
        
        Args:
            comp_num: Competition index
            season: Original season string
            
        Returns:
            str: Adjusted season string
        """
        comp = self.COMPETITION_MAP.Competition[comp_num]
        if comp == 'em':
            return '2024-in-deutschland'
        elif comp == 'em-qualifikation':
            return '2023-2024'
        elif comp == 'wm-quali-europa':
            return '2025-2026'
        elif comp == 'uefa-super-cup':
            return '2024'
        return season
    
    def _build_url(self, comp_num: int, season: str) -> str:
        """Build URL for scraping
        
        Args:
            comp_num: Competition index
            season: Season string
            
        Returns:
            str: URL for scraping
        """
        return f"https://chn.worldfootball.net/all_matches/{self.COMPETITION_MAP.Competition[comp_num]}-{season}/"
    
    def _parse_matches(self, match_table: BeautifulSoup, comp_num: int, season: str) -> None:
        """Parse match data from BeautifulSoup table
        
        Args:
            match_table: BeautifulSoup table element
            comp_num: Competition index
            season: Season string
        """
        current_round = ""
        temp_data = []
        rows = match_table.find_all('tr')
        
        for row in rows:
            round_cell = row.find('th')
            if round_cell:
                current_round = round_cell.text.strip()
                continue
                
            cells = row.find_all('td')
            if len(cells) >= 5:
                match_data = self._extract_match_data(cells, comp_num, season, current_round)
                temp_data.append(match_data)
                
        if temp_data:
            temp_df = pd.DataFrame(temp_data)
            self.data = pd.concat([self.data, temp_df], ignore_index=True)
    
    def _extract_match_data(self, cells: List, comp_num: int, season: str, current_round: str) -> Dict:
        """Extract match data from table cells
        
        Args:
            cells: List of table cells
            comp_num: Competition index
            season: Season string
            current_round: Current round/stage name
            
        Returns:
            dict: Extracted match data
        """
        home_team_url = self._extract_team_url(cells[2])
        away_team_url = self._extract_team_url(cells[4])
        
        return {
            'Season': season,
            'League': self.COMPETITION_MAP.Comp_Name[comp_num],
            'Round': current_round,
            'Date': cells[0].text.strip(),
            'Time': cells[1].text.strip(),
            'Home_Team': cells[2].text.strip(),
            'Away_Team': cells[4].text.strip(),
            'Score': cells[5].text.strip(),
            'Comp_Code': self.COMPETITION_MAP.Comp_Code[comp_num],
            'Home Url': home_team_url,
            'Away Url': away_team_url
        }
    
    def _extract_team_url(self, cell: BeautifulSoup) -> str:
        """Extract team URL from cell
        
        Args:
            cell: BeautifulSoup cell element
            
        Returns:
            str: Team URL or empty string
        """
        team_link = cell.find('a')
        return f"https://chn.worldfootball.net/{team_link['href']}" if team_link else ""
    
    def _process_dates(self) -> None:
        """Process and format dates in the dataframe"""
        self.data['Date'] = self.data['Date'].replace('', None)
        self.data['Date'] = self.data['Date'].ffill()
        self.data['Date'] = pd.to_datetime(self.data['Date'], format='%d/%m/%Y', errors='coerce')
    
    def save(self, filename: Optional[str] = None) -> None:
        """Save scraped data to Excel file
        
        Args:
            filename: Name of output file. If None, uses default name.
        """
        if not self._validate_data(self.data):
            self.logger.error("No data to save")
            return
            
        output_file = filename or os.path.join(self.output_dir, 'sch_uefa.xlsx')
        self.data.to_excel(output_file, index=False)
        self.logger.info(f"Schedule saved to {output_file}")
        self.logger.info("="*10 + "Done scraping UEFA schedules" + "="*10)
