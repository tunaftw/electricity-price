# Synka solparksdata fran Bazefield

Ladda ner produktionsdata (ActivePowerMeter, 15-min) fran Svea Solars solparker via Bazefield API.

## Om Bazefield

Bazefield ar Svea Solars monitoreringsportal. API-nyckel kravs (`BAZEFIELD_API_KEY` i `.env`).

**Parker:** Horby (SE4), Fjallskar (SE3), Agerum (SE4), Hova (SE3), Bjorke (SE3), Skakelbacken (SE3), Stenstorp (SE3), Tangen (SE4)

## Instruktioner

1. Kor `python3 bazefield_download.py` for inkrementell synk av alla parker

### Flaggor

- `--parks horby fjallskar` - Specifika parker
- `--backfill` - Sok upp forsta datum med data och ladda ner all historik
- `--status` - Visa synkstatus per park
- `--start 2025-01-01 --end 2025-12-31` - Specifikt datumintervall

### Initial setup (forsta gangen)

Kor backfill for att hamta all tillganglig historik:
```
python3 bazefield_download.py --backfill
```

### Inkrementell uppdatering

Kor utan flaggor -- scriptet fortsatter fran senaste synkade datum:
```
python3 bazefield_download.py
```

## Dataformat

Kolumner i nedladdad data:
- `timestamp` - ISO 8601 lokal tid (ex: 2025-06-15T10:00:00.0000000+02:00)
- `power_mw` - Genomsnittlig effekt vid matare (MW)

Data sparas till: `Resultat/profiler/parker/<park>_<zon>.csv`

Dashboard v2 upptacker parkprofiler automatiskt och beraknar capture price.
