"""Cup competitions data cleaner"""
import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
from .base_cleaner import BaseCleaner

class CupCleaner(BaseCleaner):
    """Cleaner for cup competition schedules"""
    
    def __init__(self, config_dir: str = None):
        """
        Initialize the CupCleaner for cup competition schedules.

        Args:
            config_dir (str, optional): Path to the directory containing configuration files. If None, uses default config location.
        """
        super().__init__(config_dir)
        self.clean_data = None
    
    def _process_round(self, schedule: pd.DataFrame) -> pd.DataFrame:
        """
        Process round, stage, group, and leg information for cup schedules.
        Assigns round numbers, stage labels, group info, and detects multi-leg knockout ties.

        Args:
            schedule (pd.DataFrame): Schedule DataFrame to process.

        Returns:
            pd.DataFrame: Schedule DataFrame with round, stage, group, and leg information added.
        """

        # make sure Round_num exists
        schedule["Round_num"] = None

        # iterate each Competition/Season/Round chunk
        for _, grp in schedule.groupby(["Competition", "Season", "Round"], sort=False):
            # get that group’s row‐indices in date/Kickoff order
            idx_sorted = grp.sort_values(["Date", "bj_kickoff"]).index.tolist()
            
            # build the round numbers in the sorted order
            round_list = [1]
            for prev_idx, curr_idx in zip(idx_sorted, idx_sorted[1:]):
                days_gap = (schedule.at[curr_idx, "Date"] - schedule.at[prev_idx, "Date"]).days
                round_list.append(round_list[-1] + 1 if days_gap > 2 else round_list[-1])
            
            # write those back into the original DataFrame (at the same indices)
            schedule.loc[idx_sorted, "Round_num"] = round_list

        schedule['match_round'] = schedule.apply(
            lambda row: f"Round {row['Round_num']:02d}"
            if ('Group' in row['Round'] or 'League phase' in row['Round'])
            else row['Round'],
            axis=1
        )

        def stage_mapper(r):
            rd = r['Round']
            # 1) group phase
            if 'Group' in rd or 'League phase' in rd:
                return 'Group Stage'
            # 2) “Round of 16”, “Round of 32”, etc. should stay as-is
            if rd.startswith('Round of'):
                return rd
            # 3) any other “Round X” (i.e. knockout rounds you want blank)
            if rd.startswith('Round '):
                return pd.NA
            # 4) finals, play‑offs, etc.
            return rd

        schedule['match_stage'] = schedule.apply(stage_mapper, axis=1)

        schedule['match_group'] = schedule['Round'].apply(
            lambda x: x if 'Group' in x else ""
        )
        
        # --- NEW: detect and number knockout legs ---
        # 1) Which Rounds are “two‑leg” ties?
        ko_pattern = r"Semi|Quarter|Play-off|Round of|Third"
        mask_ko = schedule['Round'].str.contains(ko_pattern, case=False, regex=True)

        # 2) Build a tie identifier (unordered pair of teams)
        schedule.loc[mask_ko, 'tie_id'] = schedule.loc[mask_ko] \
            .apply(lambda r: tuple(sorted([r['Home_Team'], r['Away_Team']])), axis=1)

        # 3) Slice, sort by date, then cumcount() to get leg numbers
        ko = schedule[mask_ko].sort_values(
            ['Competition', 'Season', 'Round', 'tie_id', 'Date', 'bj_kickoff']
        ).copy()

        # count how many matches in each tie
        ko['tie_size'] = ko.groupby(
            ['Competition', 'Season', 'Round', 'tie_id']
        )['tie_id'].transform('size')

        # only for ties with more than one leg...
        multi_leg = ko['tie_size'] > 1
        # compute leg number
        ko.loc[multi_leg, 'leg_num'] = (
            ko[multi_leg]
            .groupby(['Competition', 'Season', 'Round', 'tie_id'])
            .cumcount() + 1
        )

        # human‑friendly suffix
        def _leg_label(n):
            return f"{int(n)}st Leg" if n == 1 else f"{int(n)}nd Leg" if n == 2 else f"{int(n)}th Leg"
        ko.loc[multi_leg, 'match_leg'] = ko.loc[multi_leg, 'leg_num'].map(_leg_label)

        # update only the multi‑leg rows in the main DataFrame
        schedule.loc[ko.index[multi_leg], 'match_leg'] = ko.loc[multi_leg, 'match_leg']
        schedule.loc[ko.index[multi_leg], 'match_round'] = ko.loc[multi_leg].apply(
            lambda r: f"{r['Round']} - {r['match_leg']}", axis=1
        )

        # clean up helpers
        schedule = schedule.drop(columns=['tie_id'], errors='ignore')
        return schedule
    
    def update_final_schedule(self, final_schedule_path: Optional[str] = None, initial: bool = False) -> None:
        """
        Update the final schedule Excel file with cleaned data, handling both initial and incremental updates for cup competitions.

        Args:
            final_schedule_path (str, optional): Path to the final schedule Excel file. If None, uses default output location.
            initial (bool): Whether this is the initial run. If True, creates the Sequence sheet and initializes the file.
        """
        if not self._validate_data(self.clean_data):
            self.logger.error("No clean data available")
            return
            
        final_path = final_schedule_path # or os.path.join(self.config.output_dir, 'Schedule.xlsx')
        
        if not os.path.exists(final_path):
            initial = True
            # Create an empty Excel file with the required sheets and columns
            with pd.ExcelWriter(final_path) as writer:
                pd.DataFrame(columns=['season', 'competition', 'hometeam_id', 'hometeam', 'awayteam_id', 'awayteam', 'match_round', 'match_stage', 'Match_in_Season', 'match_id']).to_excel(writer, sheet_name="Sequence", index=False)
                pd.DataFrame(columns=self.FINAL_COLUMNS).to_excel(writer, sheet_name="Schedule", index=False)

        try:
            if initial:
                # For initial run, use clean_data as both sequence and schedule
                self.logger.info("Initial run - creating sequence from clean data")
                df_seq = self.clean_data[['season', 'competition', 'hometeam_id', 'hometeam', 'awayteam_id', 'awayteam', 'match_round', 'match_stage']].copy()
                # Create match_id by grouping and using cumcount
                # Add sequential match number within each season/competition group
                df_seq['Match_in_Season'] = df_seq.groupby(['season', 'competition']).cumcount() + 1
                df_seq['match_id'] = df_seq[['competition','season', 'Match_in_Season']].astype(str).agg('_'.join, axis=1)
                df_final_org = pd.DataFrame(columns=self.FINAL_COLUMNS)

                # Save sequence first
                with pd.ExcelWriter(final_path) as writer:
                    df_seq.to_excel(writer, sheet_name="Sequence", index=False)
                # return
            else:
                # 1) Load existing sequence & schedule
                df_seq = pd.read_excel(final_path, sheet_name="Sequence").drop(columns=['hometeam', 'awayteam'], errors='ignore')
                try:
                    df_final_org  = pd.read_excel(final_path, sheet_name="Schedule")
                except:
                    df_final_org = pd.DataFrame(columns=self.FINAL_COLUMNS)

                # 2) Build a “new candidates” DataFrame from clean_data
                cols = ['season','competition','hometeam_id','hometeam',
                        'awayteam_id','awayteam','match_stage']
                new_cands = self.clean_data[cols].drop_duplicates()

                # 3) Find which candidates aren’t already in df_seq
                key_cols = ['season','competition','hometeam_id','awayteam_id','match_stage']
                existing_keys = df_seq[key_cols].drop_duplicates()
                # create a boolean mask via a left‐anti join
                new_cands = (new_cands
                            .merge(existing_keys.assign(_present=1),
                                    on=key_cols, how='left')
                            .loc[lambda d: d['_present'].isna()]
                            .drop(columns='_present'))

                if not new_cands.empty:
                    # 4) For each (season,competition), find the current max Match_in_Season
                    max_nums = (df_seq
                                .groupby(['season','competition'])['Match_in_Season']
                                .max()
                                .reset_index()
                                .rename(columns={'Match_in_Season':'max_seen'}))

                    # 5) Attach that max and assign new Match_in_Season by cumcount
                    new_cands = (new_cands
                                .merge(max_nums, on=['season','competition'], how='left')
                                .fillna({'max_seen': 0}))
                    new_cands['Match_in_Season'] = (
                        new_cands.groupby(['season','competition'])
                                .cumcount()
                        + new_cands['max_seen'].astype(int)
                        + 1
                    )
                    new_cands.drop(columns='max_seen', inplace=True)

                    # 6) Build the match_id string
                    new_cands['match_id'] = (
                        new_cands[['competition','season','Match_in_Season']]
                        .astype(str)
                        .agg('_'.join, axis=1)
                    )

                    # 7) Append to your master sequence
                    df_seq = pd.concat([df_seq, new_cands], ignore_index=True)
                    # 8) Save both sheets back to Excel
                    with pd.ExcelWriter(final_path) as writer:
                        df_seq.to_excel(writer, sheet_name="Sequence", index=False)
                
            # Merge with sequence
            df_final = df_seq.merge(
                self.clean_data.drop(columns=['match_round'], errors='ignore'),
                how="left",
                on=['season', 'competition', 'hometeam_id', 'awayteam_id', 'match_stage']
            )
            # Check for modifications
            df_check = self._check_modifications(df_final, df_final_org)
            
            # Mutate modified time
            if not initial:
                df_final['modified_time'] = df_final_org['modified_time']
                df_final.loc[df_check['modified'] == True, 'modified_time'] = pd.Timestamp(datetime.today().date())
                df_final['note'] = pd.NA
                df_final.loc[df_check['modified'] == True, 'note'] = "Modified"
            
            else:
                df_final['modified_time'] = pd.Timestamp(datetime.today().date())
                df_final['note'] = "Initial scrape"

            # Generate statistics
            df_update_info = df_check.loc[df_check['modified'] == True, ['season', 'competition', 'match_round']].value_counts().sort_index()
            df_stat = df_final.loc[df_final['status'].notna(), ['season', 'competition', 'match_round']].value_counts().sort_index()
            
            self.logger.info(f"Number of schedule updated: {df_update_info.sum()}")
            
            # Save updates
            self._save_final_schedule(final_path, df_final[self.FINAL_COLUMNS], df_update_info, df_stat)
            
        except Exception as e:
            self.logger.error(f"Error updating final schedule: {e}", exc_info=True)
            raise
    
