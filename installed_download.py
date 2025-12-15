#!/usr/bin/env python3
"""Download installed solar and wind capacity from Energimyndigheten."""

from __future__ import annotations

import argparse
import warnings

# Suppress SSL warnings (Energimyndigheten has cert issues)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

from elpris.energimyndigheten import download_installed_capacity


def main():
    parser = argparse.ArgumentParser(
        description="Download installed solar and wind capacity from Energimyndigheten"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output",
    )

    args = parser.parse_args()

    print("Energimyndigheten - Installed Capacity Downloader")
    print("=" * 50)
    print("Data source: Official Swedish Energy Statistics (PxWeb)")
    print("=" * 50)
    print()

    results = download_installed_capacity(verbose=not args.quiet)

    print()
    print("=" * 50)
    print("Download complete!")
    print(f"  Wind power records: {results['wind']}")
    print(f"  Solar installation records: {results['solar']}")


if __name__ == "__main__":
    main()
