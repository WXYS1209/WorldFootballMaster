"""
Command-line interface for scraping football schedules
"""

import argparse
import os
from wfmaster.scraper import FiveLeagueScraper

def main():
    parser = argparse.ArgumentParser(description='Scrape football schedules.')
    parser.add_argument('--type', type=str, choices=['league', 'cup'], required=True,
                      help='Type of competition to scrape')
    parser.add_argument('--competition', type=str, choices=['five', 'uefa'], required=True,
                      help='Which competition to scrape')
    parser.add_argument('--season', type=str, default='2024-2025',
                      help='Season to scrape (format: YYYY-YYYY)')
    parser.add_argument('--output-dir', type=str, default=None,
                      help='Directory to save output files')
    parser.add_argument('--stage', type=str, default=None,
                      help='Specific stage/round to scrape (for cup competitions)')
    
    args = parser.parse_args()
    
    try:
        # Initialize appropriate scraper
        if args.competition == 'five':
            scraper = FiveLeagueScraper(output_dir=args.output_dir)
        elif args.competition == 'uefa':
            scraper = UEFAScraper(output_dir=args.output_dir)
        else:
            print(f"Unknown competition: {args.competition}")
            return 1
        
        # Scrape data
        if args.type == 'cup' and args.stage:
            data = scraper.scrape_stage(args.stage, season=args.season)
        else:
            data = scraper.scrape(season=args.season)
            
        scraper.save()
        print(f"Scraping completed successfully! Found {len(data)} matches.")
    except Exception as e:
        print(f"Error during scraping: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
