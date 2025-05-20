from .base_scraper import BaseScraper
from .competition_scrapers import LeagueScraper, CupScraper
from .five_league_scraper import FiveLeagueScraper
from .uefa_scraper import UEFAScraper

__all__ = [
    'BaseScraper',
    'LeagueScraper',
    'CupScraper',
    'FiveLeagueScraper',
    'UEFAScraper'
]
