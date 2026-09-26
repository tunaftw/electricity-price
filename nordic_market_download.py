"""Refresh six-zone Nordic market inputs and validated dashboard payload."""
import argparse
from elpris.nordic_market_data import CACHE, _save, build_nordic_market_data, refresh_inputs

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cached', action='store_true', help='Rebuild using cached inputs only')
    args = parser.parse_args()
    if not args.cached:
        refresh_inputs()
    data = build_nordic_market_data()
    _save(CACHE / 'dashboard.json', data)
    print(f"Nordic market: {len(data['futures'])} maturities, settlement {data['settlement_date']}, history through {data['through']}")
