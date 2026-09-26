"""Update the site's market view, preserving the other tabs' saved data."""
import argparse
import json
from pathlib import Path

from elpris.nordic_market_data import build_nordic_market_data
from elpris.unified_dashboard_v3_html import render_track_c

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=Path('sites/portfolio-intelligence/public/dashboard.html'))
    args = parser.parse_args()
    source = args.site.read_text(encoding='utf-8')
    offset = source.index('const DATA = ') + len('const DATA = ')
    payload, _ = json.JSONDecoder().raw_decode(source[offset:])
    generated = payload.pop('generated', '')
    assets, meta = payload.pop('assets', {}), payload.pop('meta', {})
    payload['nordic_market'] = build_nordic_market_data()
    rendered = render_track_c({'market': payload, 'assets': assets, 'meta': meta, 'generated': generated})
    args.site.write_text(rendered, encoding='utf-8')
    print(f'Updated {args.site}: {len(rendered):,} characters. Other data generated: {generated}')
