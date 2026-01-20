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

## Quick Start
```bash
git clone https://github.com/JaimeLoopz/queens-mesh-weather-bot
cd queens-mesh-weather-bot
pip install -r requirements.txt

# Dry run (preview message, no send)
python3 queens_weather_bot.py test

# Broadcast to mesh
python3 queens_weather_bot.py
