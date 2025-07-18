from abc import ABC, abstractmethod
import pandas as pd
import logging
import os
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from ..config import get_config
import requests
import cloudscraper
import httpx

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
        """
        Initialize the scraper with configuration and default settings.

        Args:
            config_dir (str, optional): Path to the directory containing configuration files. If None, uses default config location.
        """
        self.config = get_config(config_dir)
        self._setup_logging()
        self.data = pd.DataFrame(columns=self.COMMON_COLUMNS)
        self.headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,/;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
        }
    def _setup_logging(self):
        """
        Set up logging for the scraper instance. Logs are written to 'worldfootball_master.log' with INFO level and a standard format.
        """
        log_file = "worldfootball_master.log" # os.path.join(self.config.output_dir, "worldfootball_master.log")
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s: %(message)s'
        )
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def scrape(self, *args, **kwargs):
        """
        Abstract method for scraping data. Must be implemented by subclasses to perform the main scraping logic.
        """
        pass
    
    def save(self, filename: Optional[str] = None) -> None:
        """
        Save the scraped data to an Excel file.

        Args:
            filename (str, optional): Name or path of the output file. If None, a default name is generated based on the class name and output directory.
        """
        if not self._validate_data(self.data):
            self.logger.error("No data to save")
            return
            
        output_file = filename or os.path.join(self.config.output_dir, f'sch_{self.__class__.__name__.lower()}.xlsx')
        self.data.to_excel(output_file, index=False)
        self.logger.info(f"Schedule saved to {output_file}")
    
    def _check_connection(self, response):
        """
        Check if the HTTP response is successful (status code 200).
        Logs and raises an exception if the response is not successful.

        Args:
            response: The HTTP response object to check.
        """
        if response.status_code != 200:
            error_msg = f"Failed to retrieve data with status code {response.status_code}"
            self.logger.error(error_msg)
            raise requests.RequestException(error_msg)
    
    def _fetch_with(self, url: str):
        """
        Attempt to fetch the given URL using multiple HTTP clients (requests, httpx, cloudscraper).
        Returns the first successful response after checking the connection.
        Raises a RequestException if all strategies fail.

        Args:
            url (str): The URL to fetch.

        Returns:
            Response object from the first successful HTTP client.

        Raises:
            requests.RequestException: If all fetch strategies fail.
        """
        strategies = [
            ("requests",      lambda: requests.get(url, headers=self.headers, timeout=10)),
            ("httpx",         lambda: httpx.get   (url, headers=self.headers, timeout=10, verify=False)),
            ("cloudscraper",  lambda: cloudscraper.create_scraper().get(url, headers=self.headers, timeout=10)),
        ]

        last_exc = None
        for name, fetch in strategies:
            try:
                response = fetch()
                self._check_connection(response)
                self.logger.debug(f"Fetched {url!r} using {name}")
                return response
            except Exception as e:
                self.logger.warning(f"{name!r} strategy failed for {url!r}: {e}")
                last_exc = e

        raise requests.RequestException(
            f"All fetch strategies failed for {url!r}"
        ) from last_exc
    
    def _validate_data(self, df: pd.DataFrame) -> bool:
        """
        Validate the scraped data DataFrame.

        Args:
            df (pd.DataFrame): DataFrame containing scraped data.

        Returns:
            bool: True if the DataFrame is valid and not empty, False otherwise.
        """
        return not df.empty if isinstance(df, pd.DataFrame) else False
    
    def _extract_team_url(self, cell: BeautifulSoup) -> str:
        """
        Extract the team URL from a BeautifulSoup cell element.

        Args:
            cell (BeautifulSoup): The cell element containing the team link.

        Returns:
            str: The full team URL if present, otherwise an empty string.
        """
        team_link = cell.find('a')
        return f"https://chn.worldfootball.net/{team_link['href']}" if team_link else ""
    
    def _extract_match_url(self, cell: BeautifulSoup) -> str:
        """
        Extract the match URL from a BeautifulSoup cell element.

        Args:
            cell (BeautifulSoup): The cell element containing the match link.

        Returns:
            str: The full match URL if present, otherwise an empty string.
        """
        match_link = cell.find('a')
        return f"https://chn.worldfootball.net/{match_link['href']}" if match_link else ""
    
    def _process_dates(self) -> None:
        """
        Process and format the 'Date' column in the data DataFrame.
        Fills missing values, forward-fills, and converts to datetime format.
        """
        self.data['Date'] = self.data['Date'].replace('', None)
        self.data['Date'] = self.data['Date'].ffill()
        self.data['Date'] = pd.to_datetime(self.data['Date'], format='%d/%m/%Y', errors='coerce')

    def _extract_match_data(self, cells: List, season: str, competition: str, round_info: str) -> Dict:
        """
        Extract match information from a table row's <td> cells.

        Args:
            cells (List): List of 7 <td> BeautifulSoup elements representing a match row.
            season (str): The season string, e.g., "2025/2026".
            competition (str): The competition name, e.g., "Premier League".
            round_info (str): The round information, e.g., "1. Round".

        Returns:
            dict: Dictionary containing all extracted match fields, including date, time, teams, URLs, score, and extra info.
        """

        # --- Date cell (col 0) ---
        date_cell = cells[0]
        date_link = date_cell.find('a')
        if date_link and date_link.text.strip():
            date_text  = date_link.text.strip()
            date_url   = date_link.get('href')
            date_title = date_link.get('title', '').strip()
        else:
            date_text  = date_cell.text.strip()
            date_url   = None
            date_title = None

        # --- Time (col 1) ---
        time_text = cells[1].text.strip()

        # --- Home team (col 2) ---
        home_cell = cells[2]
        home_link = home_cell.find('a')
        home_team = home_link.text.strip() if home_link else home_cell.text.strip()
        home_url  = home_link.get('href') if home_link else None

        # --- Away team (col 4) ---
        away_cell = cells[4]
        away_link = away_cell.find('a')
        away_team = away_link.text.strip() if away_link else away_cell.text.strip()
        away_url  = away_link.get('href') if away_link else None

        # --- Score & match URL (col 5) ---
        score_cell = cells[5]
        score_link = score_cell.find('a')
        score      = score_link.text.strip() if score_link else score_cell.text.strip()
        match_url  = score_link.get('href') if score_link else None

        # --- Extra info (col 6), often empty but captured if present ---
        extra_info = cells[6].text.strip()

        return {
            'Season':        season,
            'Competition':   competition,
            'Round':         round_info,
            'Date':          date_text,
            'Date_URL':      date_url,
            'Date_Title':    date_title,
            'Time':          time_text,
            'Home_Team':     home_team,
            'home_url':      home_url,
            'Away_Team':     away_team,
            'away_url':      away_url,
            'Score':         score,
            'match_url':     match_url,
            'Extra_Info':    extra_info
        }
