#!/usr/bin/env python3
"""CLI for finding optimal solar/wind ratio for baseload PPA with battery constraints."""

import argparse
import sys
from pathlib import Path

from elpris.baseload_analysis import (
    optimize_solar_wind_ratio,
    print_ratio_optimization_table,
    export_ratio_optimization_excel,
    export_detailed_validation_excel,
    generate_heatmap_data,
)


def create_heatmap(result, output_path: Path) -> None:
    """Create and save heatmap visualization."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib krävs för heatmap. Installera med: pip install matplotlib")
        return

    data = generate_heatmap_data(result)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Plot 1: Baseload % vs Sol-ratio
    ax1 = axes[0]
    sol_ratios = [r * 100 for r in data["sol_ratios"]]
    baseload_pcts = [p * 100 for p in data["baseload_pcts"]]
    meets = data["meets_constraints"]

    colors = ['green' if m else 'lightgray' for m in meets]
    ax1.bar(sol_ratios, baseload_pcts, color=colors, edgecolor='darkgray', width=4)

    # Mark optimal
    if result.optimal:
        opt_idx = data["sol_ratios"].index(result.optimal.sol_ratio)
        ax1.bar(sol_ratios[opt_idx], baseload_pcts[opt_idx], color='darkgreen', edgecolor='black', width=4)

    ax1.set_xlabel('Sol-andel (%)')
    ax1.set_ylabel('Max Baseload (%)')
    ax1.set_title(f'Max Baseload per Sol/Vind-ratio\n(Batteri: {result.battery_duration_min}-{result.battery_duration_max}h, Eff: {result.efficiency:.0%})')
    ax1.set_xlim(-5, 105)
    ax1.grid(axis='y', alpha=0.3)

    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='green', edgecolor='darkgray', label='Uppfyller constraint'),
        Patch(facecolor='lightgray', edgecolor='darkgray', label='Uppfyller EJ'),
        Patch(facecolor='darkgreen', edgecolor='black', label='Optimal'),
    ]
    ax1.legend(handles=legend_elements, loc='upper right')

    # Plot 2: Battery duration vs Sol-ratio
    ax2 = axes[1]
    durations = [d if d and d < 100 else None for d in data["battery_durations"]]

    # Filter out None values for plotting
    valid_sol = [s * 100 for s, d in zip(data["sol_ratios"], durations) if d is not None]
    valid_dur = [d for d in durations if d is not None]

    ax2.plot(valid_sol, valid_dur, 'o-', color='#1B4F72', linewidth=2, markersize=6)

    # Add constraint band
    ax2.axhspan(result.battery_duration_min, result.battery_duration_max, alpha=0.2, color='green', label='Målintervall')
    ax2.axhline(y=result.battery_duration_min, color='green', linestyle='--', alpha=0.5)
    ax2.axhline(y=result.battery_duration_max, color='green', linestyle='--', alpha=0.5)

    ax2.set_xlabel('Sol-andel (%)')
    ax2.set_ylabel('Batteri-duration (h)')
    ax2.set_title('Batteri-duration per Sol/Vind-ratio')
    ax2.set_xlim(-5, 105)
    ax2.set_ylim(0, max(10, max(valid_dur) * 1.1) if valid_dur else 10)
    ax2.grid(alpha=0.3)
    ax2.legend()

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Heatmap sparad: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Hitta optimal sol/vind-ratio för baseload PPA med batteri-constraint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exempel:
  python baseload_ratio_cli.py
  python baseload_ratio_cli.py --total-capacity 5.0 --battery-min 2 --battery-max 4
  python baseload_ratio_cli.py --zone SE4 --excel --heatmap
        """
    )

    parser.add_argument(
        "--total-capacity", "-c",
        type=float,
        default=2.0,
        help="Total installerad kapacitet i MW (default: 2.0)"
    )
    parser.add_argument(
        "--zone", "-z",
        default="SE3",
        choices=["SE1", "SE2", "SE3", "SE4"],
        help="Elområde (default: SE3)"
    )
    parser.add_argument(
        "--profile", "-p",
        default="south_lundby",
        help="Solprofil (default: south_lundby)"
    )
    parser.add_argument(
        "--year", "-y",
        type=int,
        default=2024,
        help="Analysår (default: 2024)"
    )
    parser.add_argument(
        "--battery-min",
        type=float,
        default=1.0,
        help="Min batteri-duration i timmar (default: 1.0)"
    )
    parser.add_argument(
        "--battery-max",
        type=float,
        default=3.0,
        help="Max batteri-duration i timmar (default: 3.0)"
    )
    parser.add_argument(
        "--steps", "-s",
        type=int,
        default=21,
        help="Antal steg i grid-sökning (default: 21 = 5%% intervall)"
    )
    parser.add_argument(
        "--efficiency", "-eff",
        type=float,
        default=0.90,
        help="Round-trip batterieffektivitet (default: 0.90 = 90%%)"
    )
    parser.add_argument(
        "--excel", "-e",
        action="store_true",
        help="Exportera resultat till Excel"
    )
    parser.add_argument(
        "--heatmap",
        action="store_true",
        help="Skapa heatmap-visualisering (kräver matplotlib)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output-sökväg för Excel/heatmap (default: data/reports/)"
    )
    parser.add_argument(
        "--detailed-validation", "-dv",
        action="store_true",
        help="Exportera detaljerad validerings-Excel med formler och inputdata"
    )
    parser.add_argument(
        "--baseload",
        type=float,
        default=None,
        help="Baseload i MW för validerings-Excel (default: optimal baseload)"
    )

    args = parser.parse_args()

    print(f"\nKör optimering av sol/vind-ratio...")
    print(f"  Total kapacitet: {args.total_capacity} MW")
    print(f"  Zon: {args.zone}")
    print(f"  Batteri-duration: {args.battery_min}-{args.battery_max}h")
    print(f"  Batterieffektivitet: {args.efficiency:.0%}")
    print(f"  Steg: {args.steps}")
    print()

    # Run optimization
    result = optimize_solar_wind_ratio(
        total_capacity_mw=args.total_capacity,
        zone=args.zone,
        sol_profile_name=args.profile,
        year=args.year,
        n_steps=args.steps,
        battery_duration_min=args.battery_min,
        battery_duration_max=args.battery_max,
        efficiency=args.efficiency,
    )

    # Print results
    print_ratio_optimization_table(result)

    # Export to Excel if requested
    if args.excel:
        if args.output:
            excel_path = Path(args.output)
            if excel_path.suffix != '.xlsx':
                excel_path = excel_path.with_suffix('.xlsx')
        else:
            excel_path = None

        saved_path = export_ratio_optimization_excel(result, excel_path)
        print(f"\nExcel-fil sparad: {saved_path}")

    # Create heatmap if requested
    if args.heatmap:
        if args.output:
            heatmap_path = Path(args.output).with_suffix('.png')
        else:
            heatmap_path = Path(f"data/reports/ratio_optimization_{args.zone}_{args.year}.png")

        create_heatmap(result, heatmap_path)

    # Create detailed validation Excel if requested
    if args.detailed_validation:
        if result.optimal:
            opt = result.optimal
            baseload = args.baseload if args.baseload else opt.baseload_mw

            validation_filepath = None
            if args.output:
                validation_filepath = args.output.replace('.xlsx', '_validation.xlsx')

            validation_path = export_detailed_validation_excel(
                zone=args.zone,
                year=args.year,
                sol_profile_name=args.profile,
                sol_mw=opt.sol_mw,
                vind_mw=opt.vind_mw,
                baseload_mw=baseload,
                efficiency=args.efficiency,
                filepath=validation_filepath,
            )
            print(f"\nDetaljerad validerings-Excel sparad: {validation_path}")
        else:
            print("\nKan inte skapa validerings-Excel: Ingen optimal lösning hittades")

    # Return optimal summary
    if result.optimal:
        opt = result.optimal
        print(f"\n{'='*60}")
        print("SAMMANFATTNING")
        print(f"{'='*60}")
        print(f"Optimal ratio: {opt.sol_ratio:.0%} Sol / {1-opt.sol_ratio:.0%} Vind")
        print(f"  Sol: {opt.sol_mw:.2f} MW | Vind: {opt.vind_mw:.2f} MW")
        print(f"  Max Baseload: {opt.baseload_mw:.3f} MW ({opt.baseload_pct:.1%})")
        print(f"  Batteri: {opt.battery_mwh:.2f} MWh / {opt.battery_mw:.3f} MW")
        print(f"  Duration: {opt.battery_duration_h:.1f}h")
        print(f"  Effektivitet: {result.efficiency:.0%}")
        print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
