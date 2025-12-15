# Uppdatera elprisdata

Kör inkrementell uppdatering av elprisdata från elprisetjustnu.se.

## Instruktioner

1. Kör `python3 update.py` för att ladda ner ny prisdata för alla zoner (SE1-SE4)
2. Kör `python3 process.py` för att konvertera raw-data till quarterly (15-min)
3. Visa status med `python3 status.py`

Om användaren anger specifika zoner (t.ex. "bara SE3"), använd `--zones SE3` flaggan.
