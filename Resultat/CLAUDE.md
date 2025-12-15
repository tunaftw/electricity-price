# Resultat - Datastruktur

Detta arkiv innehåller all nedladdad data, beräknade profiler och analysrapporter.

## Mappstruktur

```
Resultat/
├── marknadsdata/                    # Nedladdad extern marknadsdata
│   ├── spotpriser/                  # Spotpriser per elområde (SE1-SE4)
│   │   ├── SE1/                     # 2021.csv, 2022.csv, etc.
│   │   ├── SE2/
│   │   ├── SE3/
│   │   └── SE4/
│   │
│   ├── entsoe-produktion/           # ENTSO-E faktisk produktion
│   │   └── entsoe/
│   │       └── generation/
│   │           ├── SE1/             # solar_2022.csv, wind_onshore_2015.csv
│   │           ├── SE2/
│   │           ├── SE3/             # + nuclear_2021.csv
│   │           └── SE4/             # + nuclear_2021.csv
│   │
│   ├── reglering-mimer/             # Svenska kraftnät reglerpriser
│   │   └── mimer/
│   │       ├── fcr/                 # FCR-N, FCR-D priser
│   │       ├── afrr/                # aFRR upp/ned per zon
│   │       ├── mfrr_cm/             # mFRR kapacitetsmarknad
│   │       └── mfrr/                # mFRR energiaktivering (historik)
│   │
│   ├── obalans-esett/               # eSett Nordic obalanspriser
│   │   └── esett/
│   │       └── imbalance/
│   │           ├── SE1/
│   │           ├── SE2/
│   │           ├── SE3/
│   │           └── SE4/
│   │
│   └── installerad-kapacitet/       # Energimyndigheten statistik
│       └── installed/
│           ├── wind_by_elarea.csv   # Vindkraft per elområde
│           └── solar_installations.csv
│
├── profiler/                        # Beräknade produktionsprofiler
│   ├── beraknade/                   # PVsyst-processade profiler
│   │   ├── ew_boda.csv              # Öst-väst profil (Böda)
│   │   ├── south_lundby.csv         # Sydvänd profil (Lundby)
│   │   └── tracker_sweden.csv       # Tracker-profil (Hova)
│   │
│   └── normaliserade/               # ENTSO-E normaliserade profiler
│       ├── solar_SE1.csv            # Solprofil SE1
│       ├── solar_SE2.csv
│       ├── solar_SE3.csv
│       ├── solar_SE4.csv
│       ├── wind_onshore_SE1.csv     # Vindprofil SE1
│       ├── wind_onshore_SE2.csv
│       ├── wind_onshore_SE3.csv
│       └── wind_onshore_SE4.csv
│
├── sol-kalldata/                    # Råa PVsyst-dokument
│   ├── 250410_E-W_Hourly_Böda.CSV
│   ├── 221208 - Lundby_VD1_HourlyRes_0.CSV
│   ├── 221208 - Lundby.VD1-Report.pdf
│   ├── 230329 - Hova_VD6_HourlyRes_1.CSV
│   └── 15102025_Hova_PVsyst SRC Forecast 5MW.pdf
│
├── rapporter/                       # Analysrapporter och Excel-filer
│   ├── capture_prices_*.xlsx        # Capture price-analyser
│   ├── battery_*.xlsx               # Batterianalyser
│   ├── baseload_*.xlsx              # Baseload PPA-analyser
│   ├── ratio_optimization_*.xlsx    # Optimeringsresultat
│   └── insights/                    # Markdown-insikter
│
├── BESS-PV-Vind-Baseload-PPA/       # Komplett analysproject
│   ├── README.md
│   ├── dokumentation/               # Detaljerad dokumentation
│   ├── kod/                         # Analyskod
│   └── resultat/                    # Projektspecifika resultat
│
├── historik-nordpool/               # Duplicerad historisk data
│   ├── SE1/
│   ├── SE2/
│   ├── SE3/
│   └── SE4/
│
└── presentationer/                  # PowerPoint-generering
    └── pptx/
        ├── create_presentation.js
        └── node_modules/
```

## Datakällor

| Mapp | Källa | API | Frekvens |
|------|-------|-----|----------|
| spotpriser | elprisetjustnu.se | REST | Tim/15-min |
| entsoe-produktion | ENTSO-E Transparency | REST+XML | Tim |
| reglering-mimer | Svenska kraftnät Mimer | REST | Tim |
| obalans-esett | eSett Open Data | REST+JSON | 15-min |
| installerad-kapacitet | Energimyndigheten | PxWeb | Årlig |

## Bakåtkompatibilitet

Symlinks i `data/`-katalogen säkerställer att befintliga scripts fungerar:

| Symlink | Pekar till |
|---------|------------|
| `data/raw/SE1-SE4` | `Resultat/marknadsdata/spotpriser/SE*` |
| `data/raw/entsoe` | `Resultat/marknadsdata/entsoe-produktion/entsoe` |
| `data/raw/mimer` | `Resultat/marknadsdata/reglering-mimer/mimer` |
| `data/raw/esett` | `Resultat/marknadsdata/obalans-esett/esett` |
| `data/raw/installed` | `Resultat/marknadsdata/installerad-kapacitet/installed` |
| `data/profiles` | `Resultat/profiler/normaliserade` |
| `data/solar_profiles` | `Resultat/profiler/beraknade` |
| `data/reports` | `Resultat/rapporter` |

## Kommandon

Se huvuddokumentationen i `/CLAUDE.md` för nedladdnings- och analyskommandon.
