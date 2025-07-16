import os
import logging
from wfmaster.scraper import LeagueScraper, CupScraper
from wfmaster.cleaner import LeagueCleaner, CupCleaner
import shutil
import dotenv

def process(scraper, cleaner, output_file, initial):
    data = scraper.scrape()
    scraper.save()
    
    cleaner.clean(input_data = data)
    cleaner.save()
    cleaner.update_final_schedule(output_file, initial)

def copy_files(files, dst_dir):
    for fname in files:
        # src = os.path.join(script_dir, fname)
        dst = os.path.join(dst_dir, fname)

        if not os.path.exists(fname):
            continue

        shutil.copy2(fname, dst_dir)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Setup logging
    log_path = os.path.join(script_dir, 'output', 'worldfootball_master.log')
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

    process(
        scraper=CupScraper(),
        cleaner=CupCleaner(),
        output_file=os.path.join(script_dir, 'output', os.getenv('CUP_OUT_FILE')) if os.getenv('CUP_OUT_FILE') else None,
        initial=os.path.exists(os.path.join(script_dir, 'output', os.getenv('CUP_OUT_FILE')))
    )

    dst_dir = r'\\tnsfs\tnsfs\部门公共文档\WXY_TEMP\Five_League'
    files = [os.path.join(script_dir, 'output', ff) for ff in [os.path.join(script_dir, 'output', os.getenv('LEAGUE_OUT_FILE')), os.path.join(script_dir, 'output', os.getenv('CUP_OUT_FILE'))]]
    copy_files(files, dst_dir)

    logging.info('WorldFootballMaster finished.')

if __name__ == "__main__":
    main()
