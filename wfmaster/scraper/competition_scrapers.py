from abc import ABC, abstractmethod
from .base_scraper import BaseScraper

class LeagueScraper(BaseScraper, ABC):
    """Base class for league-type competition scrapers"""
    
    @abstractmethod
    def scrape_round(self, round_num: int, *args, **kwargs):
        """Scrape a specific round of the league
        
        Args:
            round_num: The round number to scrape
        """
        pass

class CupScraper(BaseScraper, ABC):
    """Base class for cup-type competition scrapers"""
    
    @abstractmethod
    def scrape_stage(self, stage: str, *args, **kwargs):
        """Scrape a specific stage of the cup competition
        
        Args:
            stage: The stage/round to scrape (e.g., 'Group Stage', 'Round of 16')
        """
        pass
