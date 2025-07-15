import os
from wfmaster.scraper import LeagueScraper, CupScraper
from wfmaster.cleaner import LeagueCleaner, CupCleaner

def process(scraper, cleaner, output_file):
    data = scraper.scrape()
    scraper.save()
    
    cleaner.clean(input_data = data)
    cleaner.save()
    cleaner.update_final_schedule(output_file)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    process(
        scraper=LeagueScraper(),
        cleaner=LeagueCleaner(),
        output_file=os.path.join(script_dir, 'output', 'league_schedule.xlsx')
    )

    process(
        scraper=CupScraper(),
        cleaner=CupCleaner(),
        output_file=os.path.join(script_dir, 'output', 'cup_schedule.xlsx')
    )

if __name__ == "__main__":
    main()