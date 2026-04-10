"""
park_product_data.py
====================

Park-level teknisk konfiguration för Svea Solar Utility-portföljens
8 solparker i drift. Genererad från SharePoint Asset Management Library
(djupgrävning 2026-04-10) primärt baserad på senaste PVsyst SRC Forecast-
simuleringarna (Oct 2025-batchen) och Project Zeus Information Memorandum
(Jul 2025) för COD-datum och PPA-counterparties.

Avsedd för:
    - Steg 2: Park-metadata fill (modul/växelriktare/geografi)
    - Steg 5: Inverter fabrikat-extrahering och API-åtkomst

Fält som inte kunde verifieras i källsystemen är satta till None. Se
`park_product_data_gap_summary.md` för fält-för-fält lucka-analys och
rekommenderade uppföljande källor.

Alla numeriska värden är härledda från PVsyst SRC Forecast-simuleringarna
från Oct 2025 (Stenstorp: "Corrected" bifacial version från May 2025) som
har etablerats som aktuell "source of truth" för portföljen av
Business Development / Asset Management.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Konstanter
# ---------------------------------------------------------------------------

SHAREPOINT_BASE = (
    "https://sveasolarcom.sharepoint.com/sites/Utilityhub/"
    "Asset Management Library/Projects in operation"
)

# ---------------------------------------------------------------------------
# Park-data
# ---------------------------------------------------------------------------

PARK_PRODUCT_DATA: dict[str, dict] = {
    # =====================================================================
    # 01. HÖRBY (02 - Hörby, Mjällby, Blekinge, SE4)
    # =====================================================================
    "horby": {
        "park_name": "Hörby",
        "sharepoint_folder": "02 - Hörby",

        # --- Modules ---
        "module_type": "Trina TSM-650DEG21C.20 (Vertex N, bifacial)",
        "module_wp": 650,
        "num_modules": 27870,
        "dc_capacity_mwp": 18.12,

        # --- Inverters ---
        "inverter_model": "Sineng SP-275K-H1",
        "inverter_manufacturer": "Sineng",
        "num_inverters": 51,
        "string_inverter_or_central": "string",  # Sineng SP-275K = string inverter
        "ac_capacity_mwac": 12.75,
        "grid_limit_mwac": 12.00,

        # --- Geometry ---
        "tilt_angle": 19.1,
        "azimuth": 1.3,
        "tracking_type": "fixed",

        # --- BoS / MV ---
        "transformer_capacity_kva": 2400,
        "transformer_count": 5,
        "mv_voltage_kv": 20.0,

        # --- Key dates ---
        "commissioning_date": "2023-04",       # COD Apr-23 per Zeus IM
        "ppa_start_date": "2023-04",           # COD-aligned PPA start (Bixia PaP)

        # --- Performance (PVsyst SRC Forecast Oct 2025) ---
        "expected_annual_yield_kwh_kwp": 1036,
        "expected_pr_pct": 85.02,

        # --- Location ---
        "latitude": 56.05,
        "longitude": 14.67,
        "altitude_m": 16,
        "exact_location_name": "Mjällby",
        "price_zone": "SE4",

        # --- Commercial / Monitoring ---
        "ppa_offtaker": "Bixia AB (Vida)",
        "ppa_signed_date": "2022-07-06",
        "ppm_provider": None,                  # Not verified in SharePoint search
        "scada_system": None,                  # Not verified
        "inverter_api_access": None,           # Sineng iSolarCloud typically Modbus TCP - requires verification

        # --- Source documents ---
        "source_documents": [
            f"{SHAREPOINT_BASE}/02 - Hörby/03 - Technical Documentation/01 - Yield Assessment/01 - PVsyst/14102025_Hörby PVsyst_SRC Forecast 12 MW [SLC_weighted].pdf",
            "Development-Sweden/Documentation/13 PPAs/Signed PPAs/Horby/PPA Horby 20220705, FINAL.pdf",
            "Project Zeus Final Report Ramboll 20250915.pdf (Operational Portfolio)",
        ],
    },

    # =====================================================================
    # 02. FJÄLLSKÄR 1 (01 - Fjällskär, Enstaberga, SE3)
    # =====================================================================
    "fjallskar": {
        "park_name": "Fjällskär 1",
        "sharepoint_folder": "01 - Fjällskär",

        "module_type": "Trina TSM-640/650/655DEG21C (mixed Vertex N bifacial)",
        "module_wp": 650,                       # Viktat medel ~653 Wp
        "num_modules": 31780,
        "dc_capacity_mwp": 20.75,

        "inverter_model": "Sineng SP-275K-H1",
        "inverter_manufacturer": "Sineng",
        "num_inverters": 56,
        "string_inverter_or_central": "string",
        "ac_capacity_mwac": 14.00,
        "grid_limit_mwac": 14.00,

        "tilt_angle": 33.0,
        "azimuth": -0.6,
        "tracking_type": "fixed",

        "transformer_capacity_kva": 2333,
        "transformer_count": 6,
        "mv_voltage_kv": 10.9,

        "commissioning_date": "2023-04",
        "ppa_start_date": "2023-04",

        "expected_annual_yield_kwh_kwp": 997,
        "expected_pr_pct": 81.19,

        "latitude": 58.78,
        "longitude": 16.84,
        "altitude_m": 33,
        "exact_location_name": "Enstaberga",
        "price_zone": "SE3",

        "ppa_offtaker": "Bixia AB (Parks & Resorts)",
        "ppa_signed_date": None,
        "ppm_provider": None,
        "scada_system": None,
        "inverter_api_access": None,

        "source_documents": [
            f"{SHAREPOINT_BASE}/01 - Fjällskär/03 - Technical Documentation/01 - Yield Assessment/01 - PVsyst/15102025_PVsyst Fjällskär SRC Forecast [SLC].pdf",
            "Project Zeus Final Report Ramboll 20250915.pdf",
        ],
    },

    # =====================================================================
    # 03. BJÖRKE (03 - Björke, Trödje/Gävle, SE3)
    # =====================================================================
    "bjorke": {
        "park_name": "Björke",
        "sharepoint_folder": "03 - Björke",

        "module_type": "Risen RSM132-8-660BMDG (9380 st) + Trina TSM-655DEG21C (1148 st), bifacial",
        "module_wp": 660,                       # Dominant teknologi
        "num_modules": 10528,
        "dc_capacity_mwp": 6.943,

        "inverter_model": "Sineng SP-275K-H1",
        "inverter_manufacturer": "Sineng",
        "num_inverters": 17,
        "string_inverter_or_central": "string",
        "ac_capacity_mwac": 4.25,
        "grid_limit_mwac": 4.00,                # Curtailed

        "tilt_angle": 29.0,
        "azimuth": -1.3,
        "tracking_type": "fixed",

        "transformer_capacity_kva": 3420,
        "transformer_count": 2,
        "mv_voltage_kv": 12.0,

        "commissioning_date": "2023-10",        # COD Oct-23 per Zeus IM
        "ppa_start_date": "2023-10",

        "expected_annual_yield_kwh_kwp": 877,
        "expected_pr_pct": 76.81,

        "latitude": 60.79,
        "longitude": 17.20,
        "altitude_m": 10,
        "exact_location_name": "Trödje",
        "price_zone": "SE3",

        "ppa_offtaker": "Bixia AB (Emballator)",
        "ppa_signed_date": None,
        "ppm_provider": None,
        "scada_system": None,
        "inverter_api_access": None,

        "source_documents": [
            f"{SHAREPOINT_BASE}/03 - Björke/03 - Technical Documentation/01 - Yield Assessment/01 - PVsyst/15102025_PVsyst Björke Bifacial SRC Forecast 4MW [SLC].pdf",
            "Project Zeus Final Report Ramboll 20250915.pdf",
        ],
    },

    # =====================================================================
    # 04. AGERUM (04 - Agerum, Örelycke, Blekinge, SE4)
    # =====================================================================
    "agerum": {
        "park_name": "Agerum",
        "sharepoint_folder": "04 - Agerum",

        "module_type": "Trina TSM-655DEG21C + TSM-660DEG21C (Vertex N, bifacial)",
        "module_wp": 660,
        "num_modules": 13412,
        "dc_capacity_mwp": 8.846,

        "inverter_model": "Sineng SP-275K-H1",
        "inverter_manufacturer": "Sineng",
        "num_inverters": 24,
        "string_inverter_or_central": "string",
        "ac_capacity_mwac": 6.00,
        "grid_limit_mwac": 6.00,

        "tilt_angle": 27.0,
        "azimuth": 0.3,
        "tracking_type": "fixed",

        "transformer_capacity_kva": 1600,
        "transformer_count": 4,
        "mv_voltage_kv": 10.6,

        "commissioning_date": "2023-12",        # COD Dec-23 per Zeus IM
        "ppa_start_date": "2023-12",

        "expected_annual_yield_kwh_kwp": 1033,
        "expected_pr_pct": 84.23,

        "latitude": 56.16,
        "longitude": 14.63,
        "altitude_m": 12,
        "exact_location_name": "Örelycke",
        "price_zone": "SE4",

        "ppa_offtaker": "Bixia AB (AGEs)",
        "ppa_signed_date": None,
        "ppm_provider": None,
        "scada_system": None,
        "inverter_api_access": None,

        "source_documents": [
            f"{SHAREPOINT_BASE}/04 - Agerum/03 - Technical Documentation/01 - Yield Assessment/01 - PVsyst/15102025_PVsyst Agerum SRC Forecast [SLC].pdf",
            "Project Zeus Final Report Ramboll 20250915.pdf",
        ],
    },

    # =====================================================================
    # 05. HOVA (06 - Hova, Källtorp, Västra Götaland, SE3)  ★ TRACKER
    # =====================================================================
    "hova": {
        "park_name": "Hova",
        "sharepoint_folder": "06 - Hova",

        "module_type": "Trina TSM-680/685NEG21C (Vertex N, bifacial)",
        "module_wp": 685,                       # Dominant (TSM-685)
        "num_modules": 8680,
        "dc_capacity_mwp": 5.917,

        "inverter_model": "Huawei SUN2000-330KTL-H1",
        "inverter_manufacturer": "Huawei",
        "num_inverters": 17,
        "string_inverter_or_central": "string",
        "ac_capacity_mwac": 5.312,
        "grid_limit_mwac": 5.00,

        "tilt_angle": None,                     # Tracker - variable axis tilt
        "azimuth": None,                        # Tracker - rotation axis N-S
        "tracking_type": "single_axis_tracker", # Schletter tracker, 96 trackers, backtracking, wind stow 15.6 m/s

        "transformer_capacity_kva": 2500,
        "transformer_count": 2,
        "mv_voltage_kv": 12.0,

        "commissioning_date": "2024-10",        # COD Oct-24 per Zeus IM; Schletter tracker commissioning 2024-08-08
        "ppa_start_date": "2024-10",

        "expected_annual_yield_kwh_kwp": 1202,  # Highest in portfolio
        "expected_pr_pct": 89.27,

        "latitude": 58.85,
        "longitude": 14.20,
        "altitude_m": 109,
        "exact_location_name": "Källtorp",
        "price_zone": "SE3",

        "ppa_offtaker": "Energi Danmark (Ljusgårda)",
        "ppa_signed_date": None,
        "ppm_provider": "Meteocontrol",         # Confirmed via Meteocontrol commissioning report
        "scada_system": "Meteocontrol VCOM",
        "inverter_api_access": None,            # Huawei FusionSolar API available (Modbus TCP + REST) - requires verification

        "source_documents": [
            f"{SHAREPOINT_BASE}/06 - Hova/03 - Technical Documentation/01 - Yield Assessment/01 - PVsyst/15102025_Hova_PVsyst SRC Forecast 5MW [SLC].pdf",
            f"{SHAREPOINT_BASE}/06 - Hova/03 - Technical Documentation/06 - Commissioning/01 - LV/01 - Reports/Commissioning_report_Hova.pdf",
            f"{SHAREPOINT_BASE}/06 - Hova/02 - EPC/05 - Offers & Order confirmations (material and sub-suppliers)/Datalogger Meteo control/Commissioning Meteocontrol/QO-005779_Svea_Solar_Hova_Commissioning_Report_EN_V5_0.pdf",
            "Project Zeus Final Report Ramboll 20250915.pdf",
        ],
    },

    # =====================================================================
    # 06. SKÄKELBACKEN (09 - Skakelbacken, Ludvika-området, SE3)
    # =====================================================================
    "skakelbacken": {
        "park_name": "Skäkelbacken",
        "sharepoint_folder": "09 - Skakelbacken",

        "module_type": "Tongwei TWMNF-66HD695 (bifacial)",
        "module_wp": 695,
        "num_modules": 9352,
        "dc_capacity_mwp": 6.500,

        "inverter_model": "Sungrow SG350HX-15A",
        "inverter_manufacturer": "Sungrow",
        "num_inverters": 16,
        "string_inverter_or_central": "string",
        "ac_capacity_mwac": 5.120,
        "grid_limit_mwac": 5.00,

        "tilt_angle": 30.2,
        "azimuth": -3.7,
        "tracking_type": "fixed",

        "transformer_capacity_kva": 2500,
        "transformer_count": 2,
        "mv_voltage_kv": 10.5,

        "commissioning_date": "2025-06",        # COD Jun-25 per Zeus IM
        "ppa_start_date": "2025-06",

        "expected_annual_yield_kwh_kwp": 933,
        "expected_pr_pct": 83.18,

        "latitude": 60.09,
        "longitude": 15.05,
        "altitude_m": 285,
        "exact_location_name": "Skäkelbacken (Skackelbacken_SC)",
        "price_zone": "SE3",

        "ppa_offtaker": "Arla Foods",
        "ppa_signed_date": None,                # Part of 2023 Arla master PPA
        "ppm_provider": "Meteocontrol",         # Confirmed via Meteocontrol quotation
        "scada_system": "Meteocontrol VCOM",
        "inverter_api_access": None,            # Sungrow iSolarCloud API - requires verification

        "source_documents": [
            f"{SHAREPOINT_BASE}/09 - Skakelbacken/03 - Technical Documentation/01 - Yield Assessment/01 - PVsyst/15102025_PVsyst Skakelbacken SRC Forecast [SLC].pdf",
            f"{SHAREPOINT_BASE}/09 - Skakelbacken/03 - Technical Documentation/04 - Equipment/04 - DAS and SCADA/Meteocontrol/pA-136169-V2_Svea_[SE] Skackelbacken_6.5MW_jsc.pdf",
            "Project Zeus Final Report Ramboll 20250915.pdf",
        ],
    },

    # =====================================================================
    # 07. STENSTORP (08 - Stenstorp, Västra Götaland, SE3)
    # =====================================================================
    "stenstorp": {
        "park_name": "Stenstorp",
        "sharepoint_folder": "08 - Stenstorp",

        "module_type": "Trina TSM-650 (1288 st) + TSM-660DEG21C (448 st), bifacial",
        "module_wp": 650,
        "num_modules": 1736,
        "dc_capacity_mwp": 1.133,

        "inverter_model": "Huawei SUN2000-330KTL-H1",
        "inverter_manufacturer": "Huawei",
        "num_inverters": 3,
        "string_inverter_or_central": "string",
        "ac_capacity_mwac": 0.900,
        "grid_limit_mwac": 0.900,

        "tilt_angle": 23.2,
        "azimuth": -2.0,
        "tracking_type": "fixed",

        "transformer_capacity_kva": 1000,
        "transformer_count": 1,
        "mv_voltage_kv": 10.0,

        "commissioning_date": "2025-03",        # COD Mar-25 per Zeus IM; grid connection signed 2024-03-19
        "ppa_start_date": None,                 # Merchant per Zeus IM

        "expected_annual_yield_kwh_kwp": 1008,
        "expected_pr_pct": 81.74,

        "latitude": 58.27,
        "longitude": 13.71,
        "altitude_m": 183,
        "exact_location_name": "Stenstorp",
        "price_zone": "SE3",

        "ppa_offtaker": "Merchant (no PPA)",    # Per Zeus IM Operational Portfolio
        "ppa_signed_date": None,
        "ppm_provider": "Meteocontrol",         # Confirmed via Meteocontrol invoice + SCADA folder
        "scada_system": "Meteocontrol VCOM",
        "inverter_api_access": None,

        "source_documents": [
            f"{SHAREPOINT_BASE}/08 - Stenstorp/03 - Technical Documentation/01 - Yield Assessment/01 - PVsyst/05052025_Stenstorp_Bifacial PVsyst RH SRC [MTNM]_Corrected.pdf",
            f"{SHAREPOINT_BASE}/08 - Stenstorp/03 - Technical Documentation/04 - Equipment/04 - DAS and SCADA/MeteoControl/MC_1st_invoice_pA-134610_Svea-Solar_Stenstorp_dle.pdf",
            f"{SHAREPOINT_BASE}/08 - Stenstorp/03 - Technical Documentation/09 - RfG/Grid connection Stenstorp - EN.pdf",
            "Project Zeus Final Report Ramboll 20250915.pdf",
        ],
    },

    # =====================================================================
    # 08. TÅNGEN 1 (10 - Tången, Gungvala, Blekinge, SE4)
    # =====================================================================
    "tangen": {
        "park_name": "Tången 1",
        "sharepoint_folder": "10 - Tången",

        "module_type": "Risen RSM132-8-660BMDG (bifacial)",
        "module_wp": 660,
        "num_modules": 10192,
        "dc_capacity_mwp": 6.727,

        "inverter_model": "Huawei SUN2000-330KTL-H1",
        "inverter_manufacturer": "Huawei",
        "num_inverters": 16,
        "string_inverter_or_central": "string",
        "ac_capacity_mwac": 5.280,
        "grid_limit_mwac": 4.500,               # Curtailed

        "tilt_angle": 21.1,
        "azimuth": 3.4,
        "tracking_type": "fixed",

        "transformer_capacity_kva": 2500,       # 2× olika: 2500 + 2000 kVA
        "transformer_count": 2,
        "mv_voltage_kv": 11.0,

        "commissioning_date": "2025-09",        # COD Sep-25 per Zeus IM
        "ppa_start_date": "2025-09",

        "expected_annual_yield_kwh_kwp": 1013,
        "expected_pr_pct": 84.69,

        "latitude": 56.23,
        "longitude": 14.76,
        "altitude_m": 46,
        "exact_location_name": "Gungvala",
        "price_zone": "SE4",

        "ppa_offtaker": "Energi Danmark (Strandmøllen) + Arla",
        "ppa_signed_date": "2025-04-02",        # ED PPA signed 2 April 2025
        "ppm_provider": None,                   # SCADA commissioning checklist finns men PPM-provider ej explicit
        "scada_system": None,
        "inverter_api_access": None,            # Huawei FusionSolar

        "source_documents": [
            f"{SHAREPOINT_BASE}/10 - Tången/03 - Technical Documentation/01 - Yield Assessment/01 - PVsyst/15102025_PVsyst Tången SRC Forecast [SLC].pdf",
            f"{SHAREPOINT_BASE}/10 - Tången/04 - Contracts/06 - PPA & BRP/PPA Energi Danmark and SVEA Tangen-signed.pdf",
            f"{SHAREPOINT_BASE}/10 - Tången/03 - Technical Documentation/06 - Commissioning/04 - SCADA/SCADA_Commissioning_Checklist_Tången.docx",
            "Project Zeus Final Report Ramboll 20250915.pdf",
        ],
    },
}

# ---------------------------------------------------------------------------
# SCADA-integration grupper (för Steg 5: inverter-nivå data)
# ---------------------------------------------------------------------------

# Mappar invertertillverkare → lista med park-nycklar.
# Används för att planera SCADA-integration: en API-klient per fabrikat.
SCADA_INTEGRATION_GROUPS: dict[str, list[str]] = {
    "sineng": ["horby", "fjallskar", "bjorke", "agerum"],   # Sineng — 148 enheter, 4 parker
    "huawei": ["hova", "stenstorp", "tangen"],              # Huawei FusionSolar — 36 enheter, 3 parker
    "sungrow": ["skakelbacken"],                            # Sungrow iSolarCloud — 16 enheter, 1 park
}


# ---------------------------------------------------------------------------
# Portfolio-level sammanfattning
# ---------------------------------------------------------------------------

PORTFOLIO_SUMMARY = {
    "total_parks": len(PARK_PRODUCT_DATA),
    "total_dc_mwp": round(
        sum(p["dc_capacity_mwp"] for p in PARK_PRODUCT_DATA.values()), 2
    ),
    "total_ac_mwac": round(
        sum(p["ac_capacity_mwac"] for p in PARK_PRODUCT_DATA.values()), 2
    ),
    "total_grid_mwac": round(
        sum(p["grid_limit_mwac"] for p in PARK_PRODUCT_DATA.values()), 2
    ),
    "inverter_manufacturers": sorted(
        {p["inverter_manufacturer"] for p in PARK_PRODUCT_DATA.values()}
    ),
    "tracker_parks": [
        k for k, p in PARK_PRODUCT_DATA.items()
        if p["tracking_type"] != "fixed"
    ],
    "price_zones": sorted({p["price_zone"] for p in PARK_PRODUCT_DATA.values()}),
}


def get_park(park_key: str) -> dict:
    """Hämta park-data via nyckel (t.ex. 'horby', 'fjallskar')."""
    return PARK_PRODUCT_DATA[park_key]


def parks_by_manufacturer(manufacturer: str) -> list[str]:
    """Returnera lista med park-nycklar som använder angiven inverter-tillverkare."""
    return [
        k for k, p in PARK_PRODUCT_DATA.items()
        if p["inverter_manufacturer"].lower() == manufacturer.lower()
    ]


if __name__ == "__main__":
    import json
    print("=== PORTFOLIO SUMMARY ===")
    print(json.dumps(PORTFOLIO_SUMMARY, indent=2, ensure_ascii=False))
    print("\n=== INVERTER GROUPS (relevant för Steg 5) ===")
    for mfr in PORTFOLIO_SUMMARY["inverter_manufacturers"]:
        parks = parks_by_manufacturer(mfr)
        print(f"  {mfr}: {parks}")
