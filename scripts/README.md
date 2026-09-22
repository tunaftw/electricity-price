# scripts/

Automation helpers for running the elpris pipeline on a schedule.

## Daily update on macOS (launchd)

`com.elpris.daily.plist` runs `python3 update_all.py --quiet --auto-reports` every day at 06:00,
logs to `Resultat/logs/daily_update.{log,err}`, and exits non-zero on failure
(so you can wire alerts later).

The `--auto-reports` flag automatically generates the previous month's park performance reports
once per month (if the HTML files don't already exist), enabling monthly report generation without manual intervention.

### Install

```bash
# Copy into LaunchAgents (per-user, doesn't need sudo)
cp scripts/com.elpris.daily.plist ~/Library/LaunchAgents/

# Load it
launchctl load ~/Library/LaunchAgents/com.elpris.daily.plist

# Verify it's registered
launchctl list | grep elpris
```

### Inspect / disable

```bash
# See last exit code
launchctl list | grep elpris      # column 1 = PID, column 2 = last exit code

# Tail logs
tail -f Resultat/logs/daily_update.log
tail -f Resultat/logs/daily_update.err

# Trigger a one-off run now
launchctl start com.elpris.daily

# Disable
launchctl unload ~/Library/LaunchAgents/com.elpris.daily.plist
```

### Edit the schedule

Adjust `StartCalendarInterval` in the plist (Hour/Minute), then `launchctl unload`
+ `launchctl load` again.

## Daily futures settlements (launchd, Mon–Fri 19:15)

`se.elpris.futures-daily.plist` runs `python3 futures_daily.py` every weekday at
19:15 local time. The script fetches the dated Euronext settlements (SYS + EPAD
SE1–SE4, every listed month/quarter/year) and merges them into
`Resultat/marknadsdata/nasdaq/futures/*.csv`, keyed on (trading date, contract)
— re-running is harmless, and each run re-reads every session since the newest
stored day (at least 10), so missed days heal themselves as long as the contract
still trades. **Euronext does not serve expired contracts**: a quarter that
starts delivery while the job is off is lost for good. It logs to `Resultat/logs/futures_daily_YYYYMMDD.log` and
exits 1 on fetch errors or if the newest SYS settlement is more than 3 weekdays
stale (launchd's own stdout/stderr go to `Resultat/logs/futures_daily_launchd.{log,err}`).

Independent of `com.elpris.daily` — install either or both.

### Install

The project lives under `~/Documents`, which macOS privacy protection (TCC)
guards. If the first scheduled run logs `Operation not permitted` in
`Resultat/logs/futures_daily_launchd.err`, give `/usr/bin/python3` Full Disk
Access (System Settings → Privacy & Security) or move the repo out of
`~/Documents`.

```bash
cp scripts/se.elpris.futures-daily.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/se.elpris.futures-daily.plist

# Verify it's registered (shows schedule, last exit code, run count)
launchctl print gui/$(id -u)/se.elpris.futures-daily | head -40
```

### Run now / inspect / disable

```bash
# One-off run right now (same environment as the scheduled run)
launchctl kickstart -p gui/$(id -u)/se.elpris.futures-daily

# Logs
tail -n 30 Resultat/logs/futures_daily_$(date +%Y%m%d).log
cat Resultat/logs/futures_daily_launchd.err

# Disable / uninstall
launchctl bootout gui/$(id -u)/se.elpris.futures-daily
rm ~/Library/LaunchAgents/se.elpris.futures-daily.plist
```

After editing the plist: `bootout` then `bootstrap` again.

Manual variants: `python3 futures_daily.py --sessions 30` (wider catch-up) and
`python3 futures_daily.py --backfill` (all history Euronext still serves, back to
2026-02-02, plus re-dating of old fetch-dated snapshot rows — idempotent).

## Daily update via cron (Linux / macOS alternative)

If you prefer cron, add this to `crontab -e`:

```cron
0 6 * * * cd /Users/pontusskog/Documents/Developer/electricity-price && /usr/bin/python3 update_all.py --quiet --auto-reports >> Resultat/logs/daily_update.log 2>&1
```

Cron has known issues on macOS (Full Disk Access needed for ~/Library, sleep
interrupts schedule). launchd is the recommended approach on macOS.
