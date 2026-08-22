"""Enhetstester för elpris.insikt.puls (Daglig puls — avvikelsedetektion).

Alla detektorer är rena funktioner som tar data som argument, så testerna
bygger syntetiska serier och rör aldrig filsystemet. Per detektor testas:

1. **Triggar** vid ett känt avvikelsefall.
2. **Triggar inte** vid normalfall.
3. **Gränsvärde** (exakt tröskeln — t.ex. exakt 3 dagar, exakt 70 %).
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from elpris.insikt.puls import (
    ALARM_NEW_TYPE_DAYS,
    ALARM_SURGE_FACTOR,
    ALARM_SURGE_MIN,
    DETECTOR_ALARM_SURGE,
    DETECTOR_INVERTER_UNDERPERFORMANCE,
    DETECTOR_MISSING_DATA,
    DETECTOR_PARK_YIELD_ANOMALY,
    DETECTOR_SOURCE_STALENESS,
    DETECTOR_STUCK_SIGNAL_NIGHT,
    MISSING_MAX_AGE_HOURS,
    MISSING_MIN_QUARTERS,
    STUCK_MIN_QUARTERS,
    UNDERPERF_MAX_PLAUSIBLE_YIELD,
    UNDERPERF_MIN_DAYS,
    UNDERPERF_RATIO,
    build_summary,
    detect_alarm_surge,
    detect_inverter_underperformance,
    detect_missing_data,
    detect_park_yield_anomaly,
    detect_source_staleness,
    detect_stuck_signal_night,
    expected_source_date,
    render_puls_html,
    summarize_park_days,
)

UTC = ZoneInfo("UTC")
SE = ZoneInfo("Europe/Stockholm")

DAY = date(2026, 6, 15)


def _days_back(n: int) -> str:
    return (DAY - timedelta(days=n)).isoformat()


# ---------------------------------------------------------------------------
# 1. INVERTER_UNDERPERFORMANCE
# ---------------------------------------------------------------------------

def _inv_rows(day_offsets, laggard_yield_by_offset, n_peers=4, rated=250.0):
    """Bygg inverter-rader: N friska invertrar på 4,0 kWh/kW + en laggard."""
    rows = []
    for off in day_offsets:
        d = (DAY - timedelta(days=off)).isoformat()
        for i in range(n_peers):
            rows.append({
                "date": d,
                "inverter": f"INV0{i + 1}",
                "energy_kwh": 4.0 * rated,
                "rated_kw": rated,
            })
        laggard = laggard_yield_by_offset.get(off)
        if laggard is not None:
            rows.append({
                "date": d,
                "inverter": "INV99",
                "energy_kwh": laggard * rated,
                "rated_kw": rated,
            })
    return rows


def test_underperformance_triggers_after_three_bad_days():
    # INV99 på 2,0 av 4,0 kWh/kW (50 %) tre dagar i rad t.o.m. D.
    rows = _inv_rows([0, 1, 2, 3], {0: 2.0, 1: 2.0, 2: 2.0, 3: 4.0})
    findings = detect_inverter_underperformance("horby", rows, DAY)

    assert len(findings) == 1
    f = findings[0]
    assert f["detector"] == DETECTOR_INVERTER_UNDERPERFORMANCE
    assert f["severity"] == "warn"
    assert f["park"] == "horby"
    assert f["value"]["days"] == UNDERPERF_MIN_DAYS
    assert f["value"]["ratio_pct"] == pytest.approx(50.0)
    # Förlust: 3 dagar × (4,0 − 2,0) kWh/kW × 250 kW = 1 500 kWh
    assert f["value"]["lost_kwh"] == pytest.approx(1500.0)
    assert "INV99" in f["text"]


def test_underperformance_not_triggered_by_two_bad_days():
    rows = _inv_rows([0, 1, 2, 3], {0: 2.0, 1: 2.0, 2: 4.0, 3: 4.0})
    assert detect_inverter_underperformance("horby", rows, DAY) == []


def test_underperformance_boundary_exactly_70_pct_does_not_trigger():
    # Exakt på tröskeln (2,8 / 4,0 = 0,70) → INTE ett fynd.
    at_threshold = 4.0 * UNDERPERF_RATIO
    rows = _inv_rows([0, 1, 2], {0: at_threshold, 1: at_threshold, 2: at_threshold})
    assert detect_inverter_underperformance("horby", rows, DAY) == []

    # Precis under tröskeln → fynd.
    below = at_threshold - 0.01
    rows = _inv_rows([0, 1, 2], {0: below, 1: below, 2: below})
    assert len(detect_inverter_underperformance("horby", rows, DAY)) == 1


def test_underperformance_ignores_dark_days_below_median_floor():
    # Mörka dagar (median < 0,5 kWh/kWp) ska varken bryta eller bygga streak.
    rows = _inv_rows([0, 2, 3], {0: 2.0, 2: 2.0, 3: 2.0})
    # Dag D-1 är mörk för alla — median 0,2 → hoppas över.
    dark = (DAY - timedelta(days=1)).isoformat()
    for i in range(4):
        rows.append({"date": dark, "inverter": f"INV0{i + 1}",
                     "energy_kwh": 0.2 * 250.0, "rated_kw": 250.0})
    rows.append({"date": dark, "inverter": "INV99",
                 "energy_kwh": 0.2 * 250.0, "rated_kw": 250.0})

    findings = detect_inverter_underperformance("horby", rows, DAY)
    assert len(findings) == 1
    assert findings[0]["value"]["days"] == 3


def test_underperformance_requires_data_for_the_reported_day():
    # Ingen data alls för D → detektorn är tyst (MISSING_DATA äger det fallet).
    rows = _inv_rows([1, 2, 3], {1: 2.0, 2: 2.0, 3: 2.0})
    assert detect_inverter_underperformance("horby", rows, DAY) == []


def test_underperformance_drops_physically_impossible_rows():
    # Björke 2026-05-02 i verklig data: TS2 rapporterade 22,5 kWh/kW (CF 94 %)
    # medan TS1 låg på 0. Utan vakten blir medianen orimlig och friska
    # invertrar ser ut att underprestera.
    rows = []
    for off in (0, 1, 2):
        d = (DAY - timedelta(days=off)).isoformat()
        for i in range(4):  # rimliga invertrar
            rows.append({"date": d, "inverter": f"INV0{i + 1}",
                         "energy_kwh": 4.0 * 250.0, "rated_kw": 250.0})
        for i in range(4):  # räknarfel: 22,5 kWh/kW
            rows.append({"date": d, "inverter": f"BAD0{i + 1}",
                         "energy_kwh": 22.5 * 250.0, "rated_kw": 250.0})
        rows.append({"date": d, "inverter": "INV99",
                     "energy_kwh": 3.6 * 250.0, "rated_kw": 250.0})

    # Medianen ska bli 4,0 (INV99 på 90 % → friskt), inte ~13 (→ falsklarm).
    assert detect_inverter_underperformance("bjorke", rows, DAY) == []
    assert UNDERPERF_MAX_PLAUSIBLE_YIELD == 12.0


def test_underperformance_without_rated_kw_uses_raw_energy():
    rows = []
    for off in (0, 1, 2):
        d = (DAY - timedelta(days=off)).isoformat()
        for i in range(4):
            rows.append({"date": d, "inverter": f"INV0{i + 1}",
                         "energy_kwh": 1000.0, "rated_kw": None})
        rows.append({"date": d, "inverter": "INV99",
                     "energy_kwh": 400.0, "rated_kw": None})
    findings = detect_inverter_underperformance("hova", rows, DAY)
    assert len(findings) == 1
    assert findings[0]["value"]["lost_kwh"] == pytest.approx(1800.0)


# ---------------------------------------------------------------------------
# 2. STUCK_SIGNAL_NIGHT
# ---------------------------------------------------------------------------

def _night_quarters(n_stuck: int, power_mw: float = 1.0, poa: float = 0.0):
    """Ett dygn med 96 kvartar där de n första är "nattvakts"-mönstret."""
    base = datetime(2026, 6, 14, 22, 0, tzinfo=UTC)
    out = []
    for i in range(96):
        stuck = i < n_stuck
        out.append({
            "timestamp_utc": base + timedelta(minutes=15 * i),
            "meter_mw": 0.0,
            "inverter_mw": power_mw if stuck else 0.0,
            "poa": poa if stuck else 300.0,
        })
    return out


def test_stuck_signal_triggers_on_two_hours_of_phantom_power():
    findings = detect_stuck_signal_night("bjorke", _night_quarters(12), DAY)
    assert len(findings) == 1
    f = findings[0]
    assert f["detector"] == DETECTOR_STUCK_SIGNAL_NIGHT
    assert f["severity"] == "warn"
    # 12 kvartar × 1,0 MW × 0,25 h = 3,0 MWh fantomenergi
    assert f["value"]["phantom_mwh"] == pytest.approx(3.0)
    assert f["value"]["longest_run"] == 12


def test_stuck_signal_boundary_exactly_eight_quarters_triggers():
    assert len(detect_stuck_signal_night("bjorke",
                                         _night_quarters(STUCK_MIN_QUARTERS),
                                         DAY)) == 1
    assert detect_stuck_signal_night("bjorke",
                                     _night_quarters(STUCK_MIN_QUARTERS - 1),
                                     DAY) == []


def test_stuck_signal_silent_when_meter_present():
    quarters = _night_quarters(12)
    for q in quarters:
        q["meter_mw"] = 0.5  # mätaren rapporterar → vi litar på den
    assert detect_stuck_signal_night("bjorke", quarters, DAY) == []


def test_stuck_signal_silent_in_daylight():
    quarters = _night_quarters(12, poa=200.0)  # ljus finns → äkta produktion
    assert detect_stuck_signal_night("bjorke", quarters, DAY) == []


def test_stuck_signal_silent_below_power_floor():
    quarters = _night_quarters(12, power_mw=0.005)  # under 0,01 MW = brus
    assert detect_stuck_signal_night("bjorke", quarters, DAY) == []


# ---------------------------------------------------------------------------
# 3. MISSING_DATA
# ---------------------------------------------------------------------------

def _last_ts(hours_before_day_end: float) -> datetime:
    day_end = datetime(DAY.year, DAY.month, DAY.day, tzinfo=SE) + timedelta(days=1)
    return day_end - timedelta(hours=hours_before_day_end)


def test_missing_data_triggers_on_stale_timestamp():
    findings = detect_missing_data("tangen", _last_ts(48), 96, DAY)
    assert len(findings) == 1
    assert findings[0]["detector"] == DETECTOR_MISSING_DATA
    assert findings[0]["value"]["age_hours"] == pytest.approx(48.0)


def test_missing_data_triggers_on_thin_coverage():
    findings = detect_missing_data("tangen", _last_ts(0.25), 40, DAY)
    assert len(findings) == 1
    assert findings[0]["value"]["quarters"] == 40


def test_missing_data_silent_on_full_day():
    assert detect_missing_data("tangen", _last_ts(0.25), 96, DAY) == []


def test_missing_data_boundary_exact_thresholds_are_ok():
    # Exakt 36 h gammal och exakt 80 kvartar → inom toleransen.
    assert detect_missing_data("tangen", _last_ts(MISSING_MAX_AGE_HOURS),
                               MISSING_MIN_QUARTERS, DAY) == []
    # En kvart mindre → fynd.
    assert len(detect_missing_data("tangen", _last_ts(MISSING_MAX_AGE_HOURS),
                                   MISSING_MIN_QUARTERS - 1, DAY)) == 1


def test_missing_data_triggers_when_no_data_at_all():
    findings = detect_missing_data("tangen", None, 0, DAY)
    assert len(findings) == 1
    assert findings[0]["value"]["last_timestamp"] is None


# ---------------------------------------------------------------------------
# 4. PARK_YIELD_ANOMALY
# ---------------------------------------------------------------------------

def _daily(yield_d, poa_d, base_yield=5.0, base_poa=5000.0, n=30):
    series = []
    for off in range(n, 0, -1):
        series.append({
            "date": (DAY - timedelta(days=off)).isoformat(),
            "yield_kwh_kwp": base_yield,
            "poa_wh_m2": base_poa,
            "quarters": 96,
        })
    series.append({"date": DAY.isoformat(), "yield_kwh_kwp": yield_d,
                   "poa_wh_m2": poa_d, "quarters": 96})
    return series


def test_yield_anomaly_triggers_on_normal_sun_but_low_yield():
    findings = detect_park_yield_anomaly("hova", _daily(2.0, 5000.0), DAY)
    assert len(findings) == 1
    f = findings[0]
    assert f["detector"] == DETECTOR_PARK_YIELD_ANOMALY
    assert f["severity"] == "warn"
    assert f["value"]["yield_ratio_pct"] == pytest.approx(40.0)


def test_yield_anomaly_silent_when_it_was_simply_cloudy():
    # Halva instrålningen → låg yield är väntad, inte en avvikelse.
    assert detect_park_yield_anomaly("hova", _daily(2.0, 2500.0), DAY) == []


def test_yield_anomaly_silent_on_normal_day():
    assert detect_park_yield_anomaly("hova", _daily(4.9, 5100.0), DAY) == []


def test_yield_anomaly_boundary_exactly_60_pct_does_not_trigger():
    assert detect_park_yield_anomaly("hova", _daily(3.0, 5000.0), DAY) == []
    assert len(detect_park_yield_anomaly("hova", _daily(2.99, 5000.0), DAY)) == 1


def test_yield_anomaly_boundary_poa_exactly_20_pct_off_still_evaluated():
    # POA 20 % under medianen ligger precis inom toleransen → utvärderas.
    assert len(detect_park_yield_anomaly("hova", _daily(2.0, 4000.0), DAY)) == 1
    # 21 % under → väderförklaring, hoppas över.
    assert detect_park_yield_anomaly("hova", _daily(2.0, 3950.0), DAY) == []


def test_yield_anomaly_skipped_without_poa():
    series = _daily(2.0, None)
    assert detect_park_yield_anomaly("hova", series, DAY) == []


def test_yield_anomaly_skipped_with_too_short_baseline():
    assert detect_park_yield_anomaly("hova", _daily(2.0, 5000.0, n=5), DAY) == []


# ---------------------------------------------------------------------------
# 5. ALARM_SURGE
# ---------------------------------------------------------------------------

def _alarms(counts_by_offset, event_name="Grid abnormal", history_days=120):
    """Alarm-serie: {dagar_bakåt: antal}. Historiken börjar history_days bak."""
    rows = []
    # En ankarrad långt bak så historikkravet är uppfyllt.
    rows.append({"date": _days_back(history_days), "event_name": event_name})
    for off, count in counts_by_offset.items():
        for _ in range(count):
            rows.append({"date": _days_back(off), "event_name": event_name})
    return rows


def test_alarm_surge_triggers_on_volume_spike():
    counts = {off: 2 for off in range(1, 31)}   # snitt 2/dygn
    counts[0] = 20                              # > max(10, 3×2) = 10
    findings = detect_alarm_surge("horby", _alarms(counts), DAY)
    surge = [f for f in findings if f["value"].get("kind") == "volym"]
    assert len(surge) == 1
    assert surge[0]["detector"] == DETECTOR_ALARM_SURGE
    assert surge[0]["value"]["count"] == 20


def test_alarm_surge_silent_on_normal_day():
    counts = {off: 2 for off in range(0, 31)}
    assert detect_alarm_surge("horby", _alarms(counts), DAY) == []


def test_alarm_surge_floor_protects_quiet_parks():
    # Snitt 0,1/dygn → 3× snitt är 0,3, men golvet ALARM_SURGE_MIN gäller.
    counts = {5: 3}
    counts[0] = ALARM_SURGE_MIN
    assert detect_alarm_surge("horby", _alarms(counts), DAY) == []
    counts[0] = ALARM_SURGE_MIN + 1
    assert len(detect_alarm_surge("horby", _alarms(counts), DAY)) == 1


def test_alarm_surge_boundary_exactly_three_times_mean_does_not_trigger():
    counts = {off: 10 for off in range(1, 31)}   # snitt 10/dygn
    counts[0] = int(ALARM_SURGE_FACTOR * 10)     # exakt 3× → ingen surge
    assert detect_alarm_surge("horby", _alarms(counts), DAY) == []
    counts[0] = int(ALARM_SURGE_FACTOR * 10) + 1
    assert len(detect_alarm_surge("horby", _alarms(counts), DAY)) == 1


def test_alarm_new_type_triggers():
    rows = _alarms({off: 2 for off in range(0, 31)})
    rows.append({"date": DAY.isoformat(), "event_name": "Isolationsfel"})
    findings = detect_alarm_surge("horby", rows, DAY)
    new_types = [f for f in findings if f["value"].get("kind") == "ny typ"]
    assert len(new_types) == 1
    assert "Isolationsfel" in new_types[0]["text"]


def test_alarm_new_type_not_reported_when_seen_within_90_days():
    rows = _alarms({off: 2 for off in range(0, 31)})
    rows.append({"date": _days_back(ALARM_NEW_TYPE_DAYS - 1),
                 "event_name": "Isolationsfel"})
    rows.append({"date": DAY.isoformat(), "event_name": "Isolationsfel"})
    findings = detect_alarm_surge("horby", rows, DAY)
    assert [f for f in findings if f["value"].get("kind") == "ny typ"] == []


def test_alarm_detector_silent_without_history():
    # Serien börjar samma dag → allt vore "nytt". Ingen slutsats.
    rows = [{"date": DAY.isoformat(), "event_name": "Grid abnormal"}
            for _ in range(50)]
    assert detect_alarm_surge("horby", rows, DAY) == []


# ---------------------------------------------------------------------------
# 6. SOURCE_STALENESS
# ---------------------------------------------------------------------------

def test_expected_source_date_spot_flips_at_13():
    before = datetime(2026, 6, 16, 9, 0, tzinfo=SE)
    after = datetime(2026, 6, 16, 14, 0, tzinfo=SE)
    assert expected_source_date("spot", DAY, before) == DAY
    assert expected_source_date("spot", DAY, after) == DAY + timedelta(days=1)


def test_expected_source_date_uses_lag_for_other_sources():
    now = datetime(2026, 6, 16, 9, 0, tzinfo=SE)
    assert expected_source_date("esett", DAY, now) == DAY - timedelta(days=2)
    assert expected_source_date("entsoe", DAY, now) == DAY - timedelta(days=2)
    # ERA5 släpar ~5 dagar — annars falsklarm varje dag.
    assert expected_source_date("temperatur", DAY, now) == DAY - timedelta(days=5)


def test_source_staleness_triggers_and_is_info_level():
    now = datetime(2026, 6, 16, 9, 0, tzinfo=SE)
    sources = [{"source": "esett", "label": "eSett obalanspriser",
                "scope": "SE1-SE4", "latest_date": DAY - timedelta(days=10)}]
    findings = detect_source_staleness(sources, DAY, now)
    assert len(findings) == 1
    assert findings[0]["detector"] == DETECTOR_SOURCE_STALENESS
    assert findings[0]["severity"] == "info"
    assert findings[0]["park"] is None
    assert findings[0]["value"]["days_behind"] == 8


def test_source_staleness_silent_when_within_expected_lag():
    now = datetime(2026, 6, 16, 9, 0, tzinfo=SE)
    sources = [
        {"source": "esett", "label": "eSett", "scope": "SE3",
         "latest_date": DAY - timedelta(days=2)},
        {"source": "temperatur", "label": "Temperatur", "scope": "8 parker",
         "latest_date": DAY - timedelta(days=5)},
        {"source": "spot", "label": "Spot", "scope": "SE3",
         "latest_date": DAY},
    ]
    assert detect_source_staleness(sources, DAY, now) == []


def test_source_staleness_reports_missing_file():
    now = datetime(2026, 6, 16, 9, 0, tzinfo=SE)
    sources = [{"source": "entsoe", "label": "ENTSO-E sol", "scope": "SE2",
                "latest_date": None}]
    findings = detect_source_staleness(sources, DAY, now)
    assert len(findings) == 1
    assert findings[0]["value"]["latest_date"] is None


# ---------------------------------------------------------------------------
# summarize_park_days — dygnsaggregat ur 15-min-serien
# ---------------------------------------------------------------------------

def test_summarize_park_days_aggregates_local_days():
    # 96 kvartar på 1,0 MW under svensk lokal dag → 24 MWh.
    start = datetime(2026, 6, 15, 0, 0, tzinfo=SE).astimezone(UTC)
    records = [{
        "timestamp_utc": start + timedelta(minutes=15 * i),
        "effective_power_mw": 1.0,
        "irradiance_poa": 400.0,
    } for i in range(96)]

    days = summarize_park_days(records, capacity_kwp=10000)
    assert len(days) == 1
    d = days[0]
    assert d["date"] == "2026-06-15"
    assert d["quarters"] == 96
    # 24 MWh / 10 MWp = 2,4 kWh/kWp
    assert d["yield_kwh_kwp"] == pytest.approx(2.4)
    # 96 × 400 W/m² × 0,25 h = 9 600 Wh/m²
    assert d["poa_wh_m2"] == pytest.approx(9600.0)


def test_summarize_park_days_drops_poa_with_thin_coverage():
    start = datetime(2026, 6, 15, 0, 0, tzinfo=SE).astimezone(UTC)
    records = []
    for i in range(96):
        rec = {"timestamp_utc": start + timedelta(minutes=15 * i),
               "effective_power_mw": 0.0}
        if i < 10:
            rec["irradiance_poa"] = 400.0
        records.append(rec)
    days = summarize_park_days(records, capacity_kwp=10000)
    assert days[0]["poa_wh_m2"] is None


# ---------------------------------------------------------------------------
# Sammanfattning + rendering
# ---------------------------------------------------------------------------

def test_build_summary_clean_day_is_one_calm_line():
    summary = build_summary([], park_count=8)
    assert "Inga avvikelser" in summary
    assert "8 parker" in summary


def test_build_summary_counts_parks_and_sources():
    findings = [
        {"park": "horby", "detector": DETECTOR_MISSING_DATA, "severity": "warn"},
        {"park": "horby", "detector": DETECTOR_ALARM_SURGE, "severity": "warn"},
        {"park": "hova", "detector": DETECTOR_MISSING_DATA, "severity": "warn"},
        {"park": None, "detector": DETECTOR_SOURCE_STALENESS, "severity": "info"},
    ]
    summary = build_summary(findings, park_count=8)
    assert summary.startswith("4 avvikelser")
    assert "2 parker" in summary
    assert "1 datakälla" in summary


def test_build_summary_singular_forms():
    findings = [{"park": "hova", "detector": DETECTOR_MISSING_DATA,
                 "severity": "warn"}]
    summary = build_summary(findings, park_count=8)
    assert summary.startswith("1 avvikelse")
    assert "1 park" in summary


def test_render_puls_html_clean_day():
    result = {
        "date": DAY.isoformat(),
        "findings": [],
        "summary": "Inga avvikelser — alla 8 parker och datakällor ser normala ut",
        "clean": True,
        "generated_at": "2026-06-16 06:00",
    }
    html = render_puls_html(result)
    assert html.startswith("<!DOCTYPE html>")
    assert "Inga avvikelser" in html
    assert "2026-06-15" in html
    # Fristående: ingen Plotly, ingen extern JS.
    assert "plotly" not in html.lower()


def test_render_puls_html_escapes_and_groups():
    result = {
        "date": DAY.isoformat(),
        "findings": [
            {"park": "horby", "severity": "warn", "rubrik": "Inverter <under>",
             "text": "A & B", "detector": DETECTOR_INVERTER_UNDERPERFORMANCE,
             "value": {}},
            {"park": None, "severity": "info", "rubrik": "Källa släpar",
             "text": "eSett", "detector": DETECTOR_SOURCE_STALENESS,
             "value": {}},
        ],
        "summary": "2 avvikelser: 1 park, 1 datakälla",
        "clean": False,
        "generated_at": "2026-06-16 06:00",
    }
    html = render_puls_html(result)
    assert "Inverter &lt;under&gt;" in html
    assert "A &amp; B" in html
    assert "Att åtgärda" in html or "warn" in html
