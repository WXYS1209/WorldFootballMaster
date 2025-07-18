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
        """
        Initialize the CupScraper for Cup competitions.

        Args:
            config_dir (str, optional): Path to the directory containing configuration files. If None, uses default config location.
        """
        super().__init__(config_dir)
        self.config = get_config(config_dir)
        self.COMPETITION_MAP = self.config.competition_mapping
        
    def scrape(self) -> pd.DataFrame:
        """
        Scrape schedule data for all cup competitions in the COMPETITION_MAP.

        Returns:
            pd.DataFrame: DataFrame containing all scraped match data for the competitions.
        """
        self.logger.info("="*10 + "Start scraping CUP schedules" + "="*10)
        
        for cc in tqdm(range(len(self.COMPETITION_MAP)), desc="Scraping competitions", unit="competition"):
            self.logger.info(f"Scraping CUP schedules: {self.COMPETITION_MAP.Comp_Name[cc]}")
            self._scrape_competition(comp_idx=cc, season=self.COMPETITION_MAP.Season[cc])
        
        return self.data
    
    def _scrape_competition(self, comp_idx: int, season: str) -> None:
        """
        Scrape all matches for a specific competition and season.

        Args:
            comp_idx (int): Index of the competition in COMPETITION_MAP.
            season (str): Season string (e.g., "2025-2026").
        """
        # Handle special season formats for certain competitions
        # season = self._adjust_season(comp_idx, season)

        url = self._build_url(comp_idx, season)
        response = self._fetch_with(url)
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        try:
            match_table = soup.find_all('table', class_='standard_tabelle')[0]
        except IndexError:
            self.logger.error(f"No match table found at URL: {url}")
            return
            
        self._parse_matches(match_table, comp_idx, season)
    
    def _build_url(self, comp_idx: int, season: str) -> str:
        """
        Build the URL for scraping all matches of a given competition and season.

        Args:
            comp_idx (int): Index of the competition in COMPETITION_MAP.
            season (str): Season string.

        Returns:
            str: The constructed URL for scraping match data.
        """
        return f"https://chn.worldfootball.net/all_matches/{self.COMPETITION_MAP.Competition[comp_idx]}-{season}/"
    
    def _parse_matches(self, match_table: BeautifulSoup, comp_idx: int, season: str) -> None:
        """
        Parse match data from a BeautifulSoup table element and append it to the data DataFrame.

        Args:
            match_table (BeautifulSoup): The table element containing match rows.
            comp_idx (int): Index of the competition in COMPETITION_MAP.
            season (str): The season string.
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