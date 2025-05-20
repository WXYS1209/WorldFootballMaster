from setuptools import setup, find_packages

setup(
    name="wfmaster",
    version="0.1.0",
    packages=find_packages(),    install_requires=[
        'requests',
        'beautifulsoup4',
        'pandas',
        'tqdm',
        'openpyxl',
        'python-dotenv>=0.19.0',
    ],
    entry_points={
        'console_scripts': [
            'wf-scrape=scripts.scrape_schedules:main',
            'wf-clean=scripts.clean_schedules:main',
        ],
    },
    author="Wang Xiaoyang",
    description="A package for scraping and processing football data",
    python_requires=">=3.7",
)
