from abc import ABC, abstractmethod
from .base_cleaner import BaseCleaner

class LeagueCleaner(BaseCleaner, ABC):
    """Base class for league-type competition cleaners"""
    
    @abstractmethod
    def clean_round(self, round_num: int, *args, **kwargs):
        """Clean data for a specific round
        
        Args:
            round_num: The round number to clean
        """
        pass
    

class CupCleaner(BaseCleaner, ABC):
    """Base class for cup-type competition cleaners"""
    
    @abstractmethod
    def clean_stage(self, stage: str, *args, **kwargs):
        """Clean data for a specific cup stage
        
        Args:
            stage: The stage to clean (e.g., 'Group Stage', 'Round of 16')
        """
        pass
    
    @abstractmethod
    def update_group_stats(self, *args, **kwargs):
        """Update group stage statistics"""
        pass
