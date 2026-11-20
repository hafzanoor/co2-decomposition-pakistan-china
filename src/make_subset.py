"""Make the small data subset used by analysis.py from the full OWID CO2 file.

Usage: python src/make_subset.py path/to/owid-co2-data.csv
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COLS = ["country", "iso_code", "year", "population", "gdp", "primary_energy_consumption", "co2",
        "coal_co2", "oil_co2", "gas_co2", "cement_co2", "flaring_co2", "other_industry_co2", "co2_per_capita"]
COUNTRIES = ["Pakistan", "China", "India", "Bangladesh", "World"]

if __name__ == "__main__":
    d = pd.read_csv(sys.argv[1])
    s = d[d.country.isin(COUNTRIES) & (d.year >= 1990)][COLS]
    s.to_csv(ROOT / "data/raw/owid_co2_subset.csv", index=False)
    print(f"Saved {len(s)} rows")
