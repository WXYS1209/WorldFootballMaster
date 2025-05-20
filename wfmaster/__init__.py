"""
WorldFootballMaster (wfmaster) - A package for scraping and processing football data
"""

from .scraper import BaseScraper, LeagueScraper
from .cleaner import BaseCleaner, LeagueCleaner

__version__ = '0.1.0'
__all__ = ['BaseScraper', 'LeagueScraper', 'BaseCleaner', 'LeagueCleaner']
