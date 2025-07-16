"""UEFA Cup competitions scraper implementation"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm
import os
from typing import Dict, List, Optional
from .base_scraper import BaseScraper
from ..config import get_config

class CupScraper(BaseScraper):
    """Scraper for UEFA competitions (UCL, UEL, UECL, etc.)"""      
    def __init__(self, config_dir: str = None):
        """Initialize UEFAScraper
        
        Args:
            output_dir: Directory to save output files
            config_dir: Optional directory containing configuration files
        """
        super().__init__(config_dir)
        self.config = get_config(config_dir)
        self.COMPETITION_MAP = self.config.competition_mapping
        # self.current_season = self.config.current_season
        # self.config = get_config(config_dir)
        # self.COMPETITION_MAP = self.config.competition_mapping
        
    def scrape(self) -> pd.DataFrame:
        """Scrape data for cup competitions
        
        Args:
            season: Season to scrape data for
            
        Returns:
            pd.DataFrame: Scraped match data
        """
        self.logger.info("="*10 + "Start scraping CUP schedules" + "="*10)
        
        for cc in tqdm(range(len(self.COMPETITION_MAP)), desc="Scraping competitions", unit="competition"):
            self.logger.info(f"Scraping Competition: {self.COMPETITION_MAP.Comp_Name[cc]}")
            self._scrape_competition(comp_idx=cc, season=self.COMPETITION_MAP.Season[cc])
        
        return self.data
    
    # def scrape_stage(self, stage: str, season: str = '2024-2025', competition: str = None) -> pd.DataFrame:
    #     """Scrape specific stage of a competition
        
    #     Args:
    #         stage: Stage name to filter
    #         season: Season to scrape
    #         competition: Optional competition code to filter
            
    #     Returns:
    #         pd.DataFrame: Filtered match data
    #     """
    #     self.scrape(season)
    #     filtered_data = self.data[self.data['Round'] == stage]
    #     if competition:
    #         filtered_data = filtered_data[filtered_data['Comp_Code'] == competition]
    #     return filtered_data
    
    def _scrape_competition(self, comp_idx: int, season: str) -> None:
        """Scrape matches for a specific competition
        
        Args:
            comp_idx: Index in COMPETITION_MAP
            season: Season string
        """
        # Handle special season formats for certain competitions
        # season = self._adjust_season(comp_idx, season)

        url = self._build_url(comp_idx, season)
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
            
        self._parse_matches(match_table, comp_idx, season)
    
    def _build_url(self, comp_idx: int, season: str) -> str:
        """Build URL for scraping
        
        Args:
            comp_idx: Competition index
            season: Season string
            
        Returns:
            str: URL for scraping
        """
        return f"https://chn.worldfootball.net/all_matches/{self.COMPETITION_MAP.Competition[comp_idx]}-{season}/"
    
    def _parse_matches(self, match_table: BeautifulSoup, comp_idx: int, season: str) -> None:
        """Parse match data from BeautifulSoup table
        
        Args:
            match_table: BeautifulSoup table element
            comp_idx: Competition index
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
                match_data = self._extract_match_data(cells, season, self.COMPETITION_MAP.Comp_Name[comp_idx], current_round)
                temp_data.append(match_data)

        if temp_data:
            temp_df = pd.DataFrame(temp_data)
            self.data = pd.concat([self.data, temp_df], ignore_index=True)
            self.data['gender'] = self.COMPETITION_MAP.Gender[comp_idx]
            self.data['sport'] = "Football"
            self.data['discipline'] = "Football"
        
        self._process_dates()