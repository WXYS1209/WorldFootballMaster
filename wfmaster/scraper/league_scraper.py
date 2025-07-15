import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm
import os
from typing import Dict, List, Optional
from .base_scraper import BaseScraper

class LeagueScraper(BaseScraper):
    """Scraper for five major European football leagues"""
    def __init__(self, config_dir: str = None):
        """Initialize FiveLeagueScraper
        
        Args:
            config_dir: Optional directory containing configuration files
        """
        super().__init__(config_dir)
        self.LEAGUE_MAP = self.config.league_mapping # [self.config.league_mapping['League_Type'] == "Five_League"].reset_index(drop=True)

    def scrape(self) -> pd.DataFrame:
        """Scrape schedule data for all five leagues
            
        Returns:
            pd.DataFrame: Scraped schedule data
        """
        self.logger.info("="*10 + "Start scraping schedules" + "="*10)
        
        for cc in tqdm(range(len(self.LEAGUE_MAP)), desc="Scraping schedule", unit="league"):
            self.logger.info(f"Scraping League: {self.LEAGUE_MAP.League_Name[cc]}")            
            for round_num in tqdm(
                range(1, self.LEAGUE_MAP['Round'][cc]+1), 
                desc=f"Scraping schedule for {self.LEAGUE_MAP.League_Name[cc]}", 
                unit="round"
            ):
                self.scrape_round(round_num=round_num, season=self.LEAGUE_MAP.Season[cc], country_idx=cc)
        self.logger.info("="*10 + "Done scraping schedules" + "="*10)
        
        return self.data
    
    def scrape_round(self, round_num: int, season: str, country_idx: int = None) -> pd.DataFrame:
        """Scrape data for a specific round, season and country
        
        Args:
            round_num: Round number to scrape
            season: Season string
            country_idx: Index of country in LEAGUE_MAP (optional)
            
        Returns:
            pd.DataFrame: Scraped data for the round, season and country
        """
        if country_idx is not None:
            self._scrape_round_internal(country_idx, season, round_num)
            return self.data[self.data['Round'] == f'Round {round_num:02d}']
        
        for cc in tqdm(range(len(self.LEAGUE_MAP)), desc="Scraping schedule", unit="league"):
            if round_num <= self.LEAGUE_MAP.Round[cc]:
                self._scrape_round_internal(cc, season, round_num)
        return self.data[self.data['Round'] == f'Round {round_num:02d}']
    
    def _scrape_round_internal(self, country_idx: int, season: str, round_num: int) -> None:
        """Internal method to scrape data for a specific round
        
        Args:
            country_idx: Index of country in LEAGUE_MAP
            season: Season string
            round_num: Round number to scrape
        """
        url = self._build_url(country_idx, season, round_num)
        response = requests.get(url)
        
        if response.status_code != 200:
            error_msg = f"Failed to retrieve data from {url} with status code {response.status_code}"
            self.logger.error(error_msg)
            raise requests.RequestException(error_msg)
            
        soup = BeautifulSoup(response.content, 'html.parser')
        try:
            match_table = soup.find_all('table', class_='standard_tabelle')[0]
        except IndexError:
            self.logger.error(f"No match table found at URL: {url}")
            raise ValueError(f"No match table found at URL: {url}")
            
        self._parse_matches(match_table, season, country_idx, round_num)
    
    def _build_url(self, country_idx: int, season: str, round_num: int) -> str:
        """Build URL for scraping
        
        Args:
            country_idx: Index of country in LEAGUE_MAP
            season: Season string
            round_num: Round number
            
        Returns:
            str: URL for scraping
        """
        return f'https://chn.worldfootball.net/schedule/{self.LEAGUE_MAP.League[country_idx]}-{season}-spieltag/{round_num}/'
    
    def _parse_matches(self, match_table: BeautifulSoup, season, country_idx: int, round_num: int) -> None:
        """Parse match data from BeautifulSoup table
        
        Args:
            match_table: BeautifulSoup table element
            country_idx: Index of country in LEAGUE_MAP
            round_num: Round number
        """
        temp_data = []
        rows = match_table.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 5:
                match_data = self._extract_match_data(cells, season, self.LEAGUE_MAP.League_Name[country_idx], f'Round {round_num:02d}')
                temp_data.append(match_data)
                
        if temp_data:
            temp_df = pd.DataFrame(temp_data)
            self.data = pd.concat([self.data, temp_df], ignore_index=True)
            self.data['gender'] = self.LEAGUE_MAP.Gender[country_idx]
            self.data['sport'] = "Football"
            self.data['discipline'] = "Football"
        
        self._process_dates()
    
        