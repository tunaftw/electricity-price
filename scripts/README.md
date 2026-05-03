# scripts/

Automation helpers for running the elpris pipeline on a schedule.

## Daily update on macOS (launchd)

`com.elpris.daily.plist` runs `python3 update_all.py --quiet` every day at 06:00,
logs to `Resultat/logs/daily_update.{log,err}`, and exits non-zero on failure
(so you can wire alerts later).

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

## Daily update via cron (Linux / macOS alternative)

If you prefer cron, add this to `crontab -e`:

```cron
0 6 * * * cd /Users/pontusskog/Documents/Developer/electricity-price && /usr/bin/python3 update_all.py --quiet >> Resultat/logs/daily_update.log 2>&1
```

Cron has known issues on macOS (Full Disk Access needed for ~/Library, sleep
interrupts schedule). launchd is the recommended approach on macOS.
