# Queens Mesh Weather Bot ⚡️👑

Broadcasts live Queens, NY weather to Meshtastic channel 1 using Open-Meteo.  
Reliable, offline moon phase, wind arrows, alerts — no wttr.in dependency.

## Features
- °F, mph, inHg units
- Feels-like + actionable alerts (cold/frostbite, heat, wind >25 mph, humid, rain/snow)
- 16-point wind direction arrows
- Pure-Python moon phase calculation
- 4-hour cache fallback
- Auto-truncates >220 char messages for Meshtastic
- Random facts from `weather_facts.txt`

## Setup Notes

These notes reflect my current Debian setup — adjust paths/permissions for your environment.

- **Serial port**  
  Change `SERIAL_PORT = "/dev/ttyUSB0"` at the top of the script to match your Meshtastic node.  
  Check connected devices with:  
  ```bash
  ls /dev/ttyUSB*
  dmesg | grep tty

Channel
Set CHANNEL = 1 (main broadcasts) or 2 (testing) — used in --ch-index
Coordinates

Already set for Queens, NY (40.6815, -73.8365) — edit LAT, LON if needed

Logs
Automatically created at ~/logs/weather.log

Facts file
Create/edit weather_facts.txt in the repo folder (one line per fact).
If missing → falls back to defaults like "Queens owns the mesh 👑"

Cron job (automatic broadcasts every 60 minutes)
Open crontab:
crontab -e

Add this line (adjust path if your repo is elsewhere)
*/60 * * * * cd /home/jaimeloopz/queens-mesh-weather-bot && python3 queens_weather_bot.py >> /home/jaimeloopz/logs/cron_weather.log 2>&1


Serial permissions (if you get access errors)
Add your user to the dialout group:sudo usermod -aG dialout $USER

## Quick Start
```bash
git clone https://github.com/JaimeLoopz/queens-mesh-weather-bot
cd queens-mesh-weather-bot
pip install -r requirements.txt

# Dry run (preview message, no send)
python3 queens_weather_bot.py test

# Broadcast to mesh
python3 queens_weather_bot.py

