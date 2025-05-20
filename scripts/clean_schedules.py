"""
Command-line interface for cleaning football schedules
"""

import argparse
import os
from wfmaster.cleaner import FiveLeagueCleaner

def main():
    parser = argparse.ArgumentParser(description='Clean football schedules.')
    parser.add_argument('--input-dir', type=str, default=None,
                      help='Directory containing input files')
    parser.add_argument('--output-dir', type=str, default=None,
                      help='Directory to save output files')
    parser.add_argument('--team-mapping', type=str,
                      default="D:/wangxiaoyang/Regular_Work/support_files/team_mapping_football.xlsx",
                      help='Path to team mapping Excel file')
    parser.add_argument('--update-final', action='store_true',
                      help='Update the final schedule file')
    
    args = parser.parse_args()
    
    # Initialize cleaner
    cleaner = FiveLeagueCleaner(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        team_mapping_path=args.team_mapping
    )
    
    # Clean and save data
    try:
        data = cleaner.clean()
        cleaner.save()
        
        if args.update_final:
            cleaner.update_final_schedule()
            
        print("Cleaning completed successfully!")
    except Exception as e:
        print(f"Error during cleaning: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
