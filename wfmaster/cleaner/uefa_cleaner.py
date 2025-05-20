"""UEFA competitions data cleaner"""
import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
from .competition_cleaners import CupCleaner

class UEFACleaner(CupCleaner):
    """Cleaner for UEFA competition schedules"""
    
    def __init__(self, input_dir: str = None, output_dir: str = None, team_mapping_path: str = None):
        """Initialize UEFACleaner
        
        Args:
            input_dir: Directory containing input files
            output_dir: Directory to save output files
            team_mapping_path: Path to team mapping Excel file
        """
        super().__init__(input_dir, output_dir)
        self.team_mapping_path = team_mapping_path or "D:/wangxiaoyang/Regular_Work/support_files/team_mapping_football.xlsx"
        self.data = None
        self.clean_data = None
        
    def clean(self, input_file: Optional[str] = None) -> pd.DataFrame:
        """Clean UEFA schedule data
        
        Args:
            input_file: Path to input file. If None, uses default name.
            
        Returns:
            pd.DataFrame: Cleaned schedule data
        """
        self.logger.info("="*10 + "Start cleaning UEFA schedules" + "="*10)
        
        # Load data
        input_file = input_file or os.path.join(self.input_dir, 'sch_uefa.xlsx')
        self.data = pd.read_excel(input_file)
        
        # Load team mappings
        self._load_team_mappings()
        
        # Process data
        self.clean_data = self._process_data()
        
        self.logger.info("Done cleaning UEFA schedules.")
        return self.clean_data
    
    def clean_stage(self, stage: str, competition: str = None) -> pd.DataFrame:
        """Clean data for a specific stage
        
        Args:
            stage: Stage name to filter
            competition: Optional competition code to filter
            
        Returns:
            pd.DataFrame: Cleaned data for the stage
        """
        if self.clean_data is None:
            self.clean()
            
        filtered_data = self.clean_data[self.clean_data['Round'] == stage]
        if competition:
            filtered_data = filtered_data[filtered_data['Comp_Code'] == competition]
        return filtered_data
    
    def update_group_stats(self, group_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Update group stage statistics
        
        Args:
            group_data: Optional DataFrame containing group stage data
            
        Returns:
            pd.DataFrame: Updated group statistics
        """
        if group_data is None:
            group_data = self.clean_stage('Group Stage')
            
        # Calculate group statistics
        stats = []
        for comp in group_data['Comp_Code'].unique():
            for group in group_data[group_data['Comp_Code'] == comp]['Group'].unique():
                group_matches = group_data[
                    (group_data['Comp_Code'] == comp) & 
                    (group_data['Group'] == group)
                ]
                
                team_stats = self._calculate_team_stats(group_matches)
                for team, team_stat in team_stats.items():
                    stats.append({
                        'Competition': comp,
                        'Group': group,
                        'Team': team,
                        **team_stat
                    })
                    
        return pd.DataFrame(stats)
    
    def save(self, filename: Optional[str] = None) -> None:
        """Save cleaned data to Excel file
        
        Args:
            filename: Name of output file. If None, uses default name.
        """
        if not self._validate_data(self.clean_data):
            self.logger.error("No data to save")
            return
            
        output_file = filename or os.path.join(self.output_dir, 'sch_uefa_clean.xlsx')
        self.clean_data.to_excel(output_file, index=False)
        self.logger.info(f"Cleaned schedule saved to {output_file}")
    
    def _load_team_mappings(self) -> None:
        """Load team mapping data"""
        try:
            self.team_mapping = pd.read_excel(
                self.team_mapping_path,
                sheet_name="n0"
            ).drop_duplicates(['Org', 'Team_Code']).reset_index(drop=True)
            
            self.code_mapping = pd.read_excel(
                self.team_mapping_path,
                sheet_name="m0"
            )
        except Exception as e:
            self.logger.error(f"Error loading team mappings: {e}")
            raise
    
    def _process_data(self) -> pd.DataFrame:
        """Process and clean the schedule data
        
        Returns:
            pd.DataFrame: Cleaned data
        """
        # Merge with team mappings
        df = self.data.merge(
            self.team_mapping[['Org', 'Team_Code']], 
            how='left',
            left_on='Home_Team',
            right_on='Org'
        ).rename(columns={'Team_Code': 'Home_Team_Code'}).merge(
            self.team_mapping[['Org', 'Team_Code']],
            how='left',
            left_on='Away_Team',
            right_on='Org'
        ).rename(columns={'Team_Code': 'Away_Team_Code'})
        
        # Check for unmapped teams
        if df['Home_Team_Code'].isna().any() or df['Away_Team_Code'].isna().any():
            self.logger.warning("New team name detected in the schedule.")
        
        # Merge with code mappings for English names
        df = df.merge(
            self.code_mapping,
            how='left',
            left_on='Home_Team_Code',
            right_on='Team_Code'
        ).rename(columns={'Eng_Name': 'Home_Name'}).merge(
            self.code_mapping,
            how='left',
            left_on='Away_Team_Code',
            right_on='Team_Code'
        ).rename(columns={'Eng_Name': 'Away_Name'})
        
        # Create match details
        df['Detail'] = df['Home_Name'] + " vs. " + df['Away_Name']
        
        # Process dates and times
        df = self._process_datetime(df)
        
        # Process scores and results
        df = self._process_scores(df)
        
        # Select and order columns
        columns = [
            'League', 'Round', 'Date', 'Time_Stamp', 'Start', 'End',
            'Home_Team', 'Away_Team', 'Score', 'Home_Score', 'Away_Score',
            'Home_Result', 'Away_Result', 'Detail', 'Live_Timeslot',
            'Comp_Code', 'Home Url', 'Away Url'
        ]
        
        return df[columns]
    
    def _process_datetime(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process date and time information
        
        Args:
            df: DataFrame to process
            
        Returns:
            pd.DataFrame: Processed DataFrame
        """
        # Create date string
        df['Date_Org'] = df['Date'].apply(lambda x: x.strftime('%Y-%m-%d'))
        
        # Create datetime string
        df['DateTime_str'] = df.apply(
            lambda row: row['Date_Org'] + " " + row['Time'] if pd.notna(row['Time'])
            else row['Date_Org'] + " " + "00:00",
            axis=1
        )
        
        # Convert to timestamp
        df['Time_Stamp'] = pd.to_datetime(df['DateTime_str'])
        
        # Process time format
        df['Start'] = df['Time'].apply(self._format_time_to_26)
        df['End'] = df['Time'].apply(lambda x: 
            self._format_time_to_26((datetime.strptime(x, '%H:%M') + timedelta(hours=2)).strftime('%H:%M'))
            if pd.notna(x) else pd.NA
        )
        
        # Adjust date for late matches
        df['Date'] = df.apply(lambda row: 
            (row['Date'] - timedelta(days=1)) 
            if (pd.isna(row['Start']) or int(row['Start'].split(":")[0]) >= 24)
            else row['Date'], axis=1
        )
        
        # Create timeslot string
        df['Live_Timeslot'] = df['Start'] + '-' + df['End']
        
        return df
    
    def _format_time_to_26(self, time_str: str) -> str:
        """Format time string to 26-hour format
        
        Args:
            time_str: Time string to format
            
        Returns:
            str: Formatted time string
        """
        if pd.isna(time_str):
            return pd.NA
            
        tmp = time_str.split(":")
        hh, mm = map(int, tmp[0:2])
        
        ss = int(tmp[2]) if len(tmp) == 3 else 0
        
        if hh < 2:
            hh += 24
        elif (hh == 2 and (mm + ss) == 0):
            hh += 24
            
        return f'{hh}:{mm:02d}'
    
    def _process_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process match scores and calculate results
        
        Args:
            df: DataFrame to process
            
        Returns:
            pd.DataFrame: Processed DataFrame
        """
        # Split score into components
        df[['Score', 'Score_Half']] = df['Score'].str.split(' ', expand=True).loc[:, 0:1]
        df[['Home_Score', 'Away_Score']] = df['Score'].str.split(':', expand=True)
        
        # Calculate match results
        df['Home_Result'] = df.apply(lambda row: 
            '' if not row['Home_Score'].isdigit() or not row['Away_Score'].isdigit()
            else 'W' if int(row['Home_Score']) > int(row['Away_Score'])
            else 'L' if int(row['Home_Score']) < int(row['Away_Score'])
            else 'T', axis=1
        )
        
        df['Away_Result'] = df.apply(lambda row:
            '' if not row['Home_Score'].isdigit() or not row['Away_Score'].isdigit()
            else 'W' if int(row['Home_Score']) < int(row['Away_Score'])
            else 'L' if int(row['Home_Score']) > int(row['Away_Score'])
            else 'T', axis=1
        )
        
        return df
    
    def _calculate_team_stats(self, matches: pd.DataFrame) -> Dict:
        """Calculate statistics for teams in a group
        
        Args:
            matches: DataFrame containing group matches
            
        Returns:
            dict: Team statistics
        """
        stats = {}
        
        for _, match in matches.iterrows():
            # Process home team
            if match['Home_Team'] not in stats:
                stats[match['Home_Team']] = {
                    'Played': 0, 'Won': 0, 'Drawn': 0, 'Lost': 0,
                    'Goals_For': 0, 'Goals_Against': 0, 'Points': 0
                }
            
            # Process away team
            if match['Away_Team'] not in stats:
                stats[match['Away_Team']] = {
                    'Played': 0, 'Won': 0, 'Drawn': 0, 'Lost': 0,
                    'Goals_For': 0, 'Goals_Against': 0, 'Points': 0
                }
            
            # Update statistics if match is completed
            if match['Home_Score'].isdigit() and match['Away_Score'].isdigit():
                home_score = int(match['Home_Score'])
                away_score = int(match['Away_Score'])
                
                # Update home team stats
                stats[match['Home_Team']]['Played'] += 1
                stats[match['Home_Team']]['Goals_For'] += home_score
                stats[match['Home_Team']]['Goals_Against'] += away_score
                
                # Update away team stats
                stats[match['Away_Team']]['Played'] += 1
                stats[match['Away_Team']]['Goals_For'] += away_score
                stats[match['Away_Team']]['Goals_Against'] += home_score
                
                if home_score > away_score:
                    stats[match['Home_Team']]['Won'] += 1
                    stats[match['Home_Team']]['Points'] += 3
                    stats[match['Away_Team']]['Lost'] += 1
                elif home_score < away_score:
                    stats[match['Away_Team']]['Won'] += 1
                    stats[match['Away_Team']]['Points'] += 3
                    stats[match['Home_Team']]['Lost'] += 1
                else:
                    stats[match['Home_Team']]['Drawn'] += 1
                    stats[match['Home_Team']]['Points'] += 1
                    stats[match['Away_Team']]['Drawn'] += 1
                    stats[match['Away_Team']]['Points'] += 1
        
        return stats
