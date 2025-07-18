from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm
from .base_scraper import BaseScraper
import random
import time

class LeagueScraper(BaseScraper):
    """Scraper for five major European football leagues"""
    def __init__(self, config_dir: str = None):
        """
        Initialize the LeagueScraper for scraping major European football leagues.

        Args:
            config_dir (str, optional): Path to the directory containing configuration files. If None, uses default config location.
        """
        super().__init__(config_dir)
        self.LEAGUE_MAP = self.config.league_mapping # [self.config.league_mapping['League_Type'] == "Five_League"].reset_index(drop=True)

    def scrape(self) -> pd.DataFrame:
        """
        Scrape schedule data for all leagues in the LEAGUE_MAP.

        Returns:
            pd.DataFrame: DataFrame containing all scraped schedule data for the leagues.
        """
        self.logger.info("="*10 + "Start scraping LEAGUE schedules" + "="*10)

        for cc in tqdm(range(len(self.LEAGUE_MAP)), desc="Scraping LEAGUE schedules", unit="league"):
            self.logger.info(f"Scraping League: {self.LEAGUE_MAP.League_Name[cc]}")
            self._scrape_internal(season=self.LEAGUE_MAP.Season[cc], country_idx=cc)
            delay = random.uniform(1.0, 3.0)
            time.sleep(delay)

        self.logger.info("="*10 + "Done scraping schedules" + "="*10)
        
        return self.data
        
    def _scrape_internal(self, country_idx: int, season: str) -> None:
        """
        Scrape schedule data for a specific league and season.

        Args:
            country_idx (int): Index of the league in LEAGUE_MAP.
            season (str): Season string (e.g., "2025-2026").
        """
        url = self._build_url(country_idx, season)
        response = self._fetch_with(url)
    
        soup = BeautifulSoup(response.content, 'html.parser')
        try:
            match_table = soup.find_all('table', class_='standard_tabelle')[0]
        except IndexError:
            self.logger.error(f"No match table found at URL: {url}")
            raise ValueError(f"No match table found at URL: {url}")
            
        self._parse_matches(match_table, season, country_idx)
    
    def _build_url(self, country_idx: int, season: str) -> str:
        """
        Build the URL for scraping all matches of a given league and season.

        Args:
            country_idx (int): Index of the league in LEAGUE_MAP.
            season (str): Season string.

        Returns:
            str: The constructed URL for scraping match data.
        """
        return f'https://chn.worldfootball.net/all_matches/{self.LEAGUE_MAP.League[country_idx]}-{season}/'
    
    def _parse_matches(self, match_table: BeautifulSoup, season, country_idx: int) -> None:
        """
        Parse match data from a BeautifulSoup table element and append it to the data DataFrame.

        Args:
            match_table (BeautifulSoup): The table element containing match rows.
            season (str): The season string.
            country_idx (int): Index of the league in LEAGUE_MAP.
        """
        temp_data = []
        current_round = None

        for tr in match_table.find_all('tr'):
            # 1) Round‑header row?
            th = tr.find('th', colspan='7')
            if th:
                # e.g. <a>1. Round</a>
                a = th.find('a')
                current_round_text = a.text.strip() if a else th.text.strip()
                current_round_num = int(current_round_text.split(".")[0])
                current_round = f'Round {current_round_num:02d}'
                continue

            # 2) Data row?
            cells = tr.find_all('td')
            if len(cells) == 7:
                match_data = self._extract_match_data(
                    cells,
                    season,
                    self.LEAGUE_MAP.League_Name[country_idx],
                    round_info = current_round
                )
                temp_data.append(match_data)

        if temp_data:
            temp_df = pd.DataFrame(temp_data)
            self.data = pd.concat([self.data, temp_df], ignore_index=True)
            self.data['gender'] = self.LEAGUE_MAP.Gender[country_idx]
            self.data['sport'] = "Football"
            self.data['discipline'] = "Football"
        
        self._process_dates()
    
        