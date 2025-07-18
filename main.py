import os
import logging
from wfmaster.scraper import LeagueScraper, CupScraper
from wfmaster.cleaner import LeagueCleaner, CupCleaner
import shutil
import pandas as pd

def process(scraper, cleaner, output_file, initial):
    """
    Run the full pipeline: scrape, clean, save, and update the final schedule.

    Args:
        scraper: Scraper instance (e.g., LeagueScraper or CupScraper).
        cleaner: Cleaner instance (e.g., LeagueCleaner or CupCleaner).
        output_file (str): Path to the output Excel file.
        initial (bool): Whether this is the initial run (affects schedule update logic).
    """
    data = scraper.scrape()
    scraper.save()
    # data = pd.read_excel("./output/sch_leaguescraper.xlsx")
    cleaner.clean(input_data = data)
    cleaner.save()
    cleaner.update_final_schedule(output_file, initial)

def copy_files(files, dst_dir):
    """
    Copy specified files to the destination directory.

    Args:
        files (list): List of file paths to copy.
        dst_dir (str): Destination directory path.
    """
    for fname in files:
        dst = os.path.join(dst_dir, fname)

        if not os.path.exists(fname):
            continue

        shutil.copy2(fname, dst_dir)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Setup logging
    log_path = os.path.join(script_dir, 'worldfootball_master.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.FileHandler(log_path, encoding='utf-8')] # logging.StreamHandler()
    )
    logging.info('WorldFootballMaster started.')

    process(
        scraper=LeagueScraper(),
        cleaner=LeagueCleaner(),
        output_file=os.path.join(script_dir, 'output', os.getenv('LEAGUE_OUT_FILE')) if os.getenv('LEAGUE_OUT_FILE') else None,
        initial=os.path.exists(os.path.join(script_dir, 'output', os.getenv('LEAGUE_OUT_FILE')))
    )

    # process(
    #     scraper=CupScraper(),
    #     cleaner=CupCleaner(),
    #     output_file=os.path.join(script_dir, 'output', os.getenv('CUP_OUT_FILE')) if os.getenv('CUP_OUT_FILE') else None,
    #     initial=not os.path.exists(os.path.join(script_dir, 'output', os.getenv('CUP_OUT_FILE')))
    # )

    final_schs = [
        os.path.join(script_dir, 'output', os.getenv('LEAGUE_OUT_FILE'))
        # os.path.join(script_dir, 'output', os.getenv('CUP_OUT_FILE'))
        ]
    dst_dir = os.getenv('DST_DIR')
    files = [os.path.join(script_dir, 'output', ff) for ff in final_schs]
    copy_files(files, dst_dir)

    logging.info('WorldFootballMaster finished.')

if __name__ == "__main__":
    main()
