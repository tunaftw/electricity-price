# Beräkna capture-pris för sol

Beräkna capture-pris (volymviktat medelpris) för solel.

## Instruktioner

$ARGUMENTS

### Kommandon:

```bash
# Capture per månad (default) för SE3
python3 capture.py SE3

# Capture per år
python3 capture.py SE3 --period year

# Capture per dag
python3 capture.py SE3 --period day

# Total capture för en period
python3 capture.py SE3 --period total

# Specifikt datumintervall
python3 capture.py SE3 --start 2024-01-01 --end 2024-12-31 --period month
```

### Beräkningsformel:
```
Capture-pris = Σ(elpris_t × solproduktion_t) / Σ(solproduktion_t)
```

### Aggregeringsnivåer:
- `day` - Beräkna för varje dag
- `week` - Aggregera per vecka
- `month` - Aggregera per månad (default)
- `year` - Aggregera per år
- `total` - Total capture för hela perioden

### Output:
Tabellen visar:
- Period
- Capture-pris (SEK/kWh)
- Genomsnittligt spotpris (SEK/kWh)
- Capture ratio (capture/spot)

### Förutsättningar:
Kräver att quarterly-data finns. Om den saknas, kör först:
```bash
python3 process.py
```
