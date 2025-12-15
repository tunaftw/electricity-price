# Ladda ner historisk elprisdata

Ladda ner historisk elprisdata från elprisetjustnu.se.

## Instruktioner

1. Fråga användaren om de vill ladda ner:
   - Alla zoner (SE1, SE2, SE3, SE4) eller specifika
   - Hela historiken (från nov 2021) eller specifikt datumintervall

2. Kör nedladdningen med lämpliga flaggor:
   ```
   python3 download.py [--zones SE1 SE2...] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
   ```

3. Informera om att nedladdningen tar ~12 min per zon för full historik (0.5s delay mellan API-anrop)

4. Efter nedladdning, kör `python3 process.py` för att skapa quarterly-data
