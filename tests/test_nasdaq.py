from pathlib import Path

from elpris import dashboard_v2_data, nasdaq


EURONEXT_SAMPLE = """
<caption>Nordic System Price Electricity Base Load</caption>
<table><tbody>
<tr><td>Quarter</td><td>NSBQ</td><td>Q4 2026</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td>72.95</td><td>5,102</td></tr>
<tr><td>Year</td><td>NSBY</td><td>2027</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td>48.55</td><td>4,035</td></tr>
</tbody></table>
<caption>Nordic EPAD Electricity Base Load - Sweden STO</caption>
<table><tbody>
<tr><td>Quarter</td><td>STBQ</td><td>Q4 2026</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td>-5.94</td><td>1,849</td></tr>
<tr><td>Year</td><td>STBY</td><td>2027</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td>-1.75</td><td>1,382</td></tr>
</tbody></table>
<span class="fdc-dtu">&nbsp;05/07/2026 13:54 CEST</span>
"""


def test_parse_euronext_power_snapshot_maps_to_existing_csv_symbols():
    rows_by_file = nasdaq.parse_euronext_power_snapshot(EURONEXT_SAMPLE)

    assert rows_by_file["sys_baseload.csv"] == [
        {
            "date": "2026-07-05",
            "contract": "ENOFUTBLQ4-26",
            "daily_fix_eur": "72.95",
            "bid_eur": "",
            "ask_eur": "",
            "high_eur": "",
            "low_eur": "",
            "open_interest": "5102",
        },
        {
            "date": "2026-07-05",
            "contract": "ENOFUTBLYR-27",
            "daily_fix_eur": "48.55",
            "bid_eur": "",
            "ask_eur": "",
            "high_eur": "",
            "low_eur": "",
            "open_interest": "4035",
        },
    ]
    assert rows_by_file["epad_se3_sto.csv"][0]["contract"] == "SYSTOFUTBLQ4-26"
    assert rows_by_file["epad_se3_sto.csv"][0]["daily_fix_eur"] == "-5.94"


def test_forward_curve_excludes_stale_active_contracts(tmp_path, monkeypatch):
    data_dir = tmp_path / "futures"
    data_dir.mkdir()
    (data_dir / "sys_baseload.csv").write_text(
        "\n".join(
            [
                "date,contract,daily_fix_eur,bid_eur,ask_eur,high_eur,low_eur,open_interest",
                "2026-04-29,ENOFUTBLQ3-26,48.50,,,,,",
                "2026-07-05,ENOFUTBLQ4-26,72.95,,,,,5102",
                "2026-07-05,ENOFUTBLYR-27,48.55,,,,,4035",
            ]
        )
        + "\n"
    )
    for filename in [
        "epad_se1_lul.csv",
        "epad_se2_sun.csv",
        "epad_se3_sto.csv",
        "epad_se4_mal.csv",
    ]:
        (data_dir / filename).write_text(
            "date,contract,daily_fix_eur,bid_eur,ask_eur,high_eur,low_eur,open_interest\n"
        )

    monkeypatch.setattr(dashboard_v2_data, "NASDAQ_DATA_DIR", data_dir)

    forward = dashboard_v2_data.load_forward_curve_data({})

    labels = [c["label"] for c in forward["contracts"]]
    assert forward["settlement_date"] == "2026-07-05"
    assert "Q3-26" not in labels
    assert labels[:2] == ["Q4-26", "YR-27"]
