"""Export local data for energy_dashboard; no network or legacy output writes."""
from argparse import ArgumentParser
from pathlib import Path
from elpris.intelligence_data import build_intelligence_data

if __name__ == '__main__':
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'energy_dashboard/public/data')
    args=parser.parse_args()
    result=build_intelligence_data(args.output)
    print(f"Exported {len(result['parks'])} parks, 4 zones and {len(result['futures'])} contracts to {args.output}")
    print(f"Dataset {result['dataset_version']}; metrics {result['metric_version']}")
