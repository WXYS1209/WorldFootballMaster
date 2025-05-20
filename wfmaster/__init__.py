"""
WorldFootballMaster (wfmaster) - A package for scraping and processing football data
"""

from .scraper import BaseScraper, FiveLeagueScraper
from .cleaner import BaseCleaner, FiveLeagueCleaner

__version__ = '0.1.0'
__all__ = ['BaseScraper', 'FiveLeagueScraper', 'BaseCleaner', 'FiveLeagueCleaner']
