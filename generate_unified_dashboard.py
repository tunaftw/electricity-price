#!/usr/bin/env python3
"""Generate the Unified Dashboard (Track C — Nordic Editorial)."""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from elpris.unified_dashboard_data import build_unified_data
from elpris.unified_dashboard_v3_html import render_track_c

OUT_DIR = PROJECT_ROOT / "Resultat" / "rapporter"
# Claude Code preview-servern serverar /private/tmp/dashboard.html eftersom
# Claude.app:s macOS-sandbox blockerar python-processer från projektkatalogen.
# Se .claude/commands/elpris-preview.md.
PREVIEW_PATH = Path("/private/tmp/dashboard.html")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generera Unified Dashboard (Track C — Nordic Editorial)."
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help=(
            "Kopiera även resultatet till /private/tmp/dashboard.html så "
            "Claude Code preview-servern (rapporter-server) kan servera det "
            "direkt. Krävs på macOS pga sandbox."
        ),
    )
    args = parser.parse_args()

    print("Building unified data...", file=sys.stderr)
    data = build_unified_data()
    today = datetime.now().strftime("%Y%m%d")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    html = render_track_c(data)
    out = OUT_DIR / f"dashboard_unified_v3_{today}.html"
    out.write_text(html, encoding="utf-8")
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"  Track C: {out} ({size_mb:.1f} MB)")

    if args.preview:
        shutil.copy2(out, PREVIEW_PATH)
        print(f"  Preview: {PREVIEW_PATH} (uppdaterad)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
