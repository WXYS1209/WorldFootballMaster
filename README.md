# WorldFootballMaster

A Python package for scraping and processing football schedule data from various leagues.

## Installation

```bash
pip install -e .
```

## Usage

### Command Line Interface

The package provides two main commands:

1. Scrape schedules:
```bash
wf-scrape --season 2024-2025 --output-dir /path/to/output
```

2. Clean schedules:
```bash
wf-clean --input-dir /path/to/input --output-dir /path/to/output --update-final
```

### Python API

```python
from wfmaster.scraper import FiveLeagueScraper
from wfmaster.cleaner import FiveLeagueCleaner

# Scrape data
scraper = FiveLeagueScraper(output_dir='path/to/output')
data = scraper.scrape(season='2024-2025')
scraper.save()

# Clean data
cleaner = FiveLeagueCleaner(
    input_dir='path/to/input',
    output_dir='path/to/output'
)
cleaned_data = cleaner.clean()
cleaner.save()
cleaner.update_final_schedule()
```

## Project Structure

```
wfmaster/
├── scraper/
│   ├── __init__.py
│   ├── base_scraper.py
│   └── five_league_scraper.py
├── cleaner/
│   ├── __init__.py
│   ├── base_cleaner.py
│   └── five_league_cleaner.py
└── inspector/  # Future expansion for data analysis
```

## Features

- Scrape football schedules from major leagues
- Clean and process schedule data
- Update final schedule with modifications
- Extensible base classes for future additions
