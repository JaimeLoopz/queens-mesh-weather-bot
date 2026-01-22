#!/usr/bin/env python3
"""
Queens Mesh Weather Bot - Open-Meteo Version (Updated Jan 2026)
With tiered cold/hot alerts, soft-test on alt channel, wind dir, moon phase, etc.
"""
import os
import sys
import random
import requests
import subprocess
import math
import argparse
from datetime import datetime, timedelta

# ────────────────────────────────────────────────
# ARGUMENT PARSER
# ────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Queens Mesh Weather Bot")
parser.add_argument("--test", action="store_true", help="Dry-run mode (print only)")
parser.add_argument("--test-send", action="store_true", help="Test mode with real send")
parser.add_argument("--channel", type=int, default=1, help="Meshtastic channel index (default: 1)")
args = parser.parse_args()

# Override global channel if specified
CHANNEL = args.channel

# ────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────
CACHE_FILE = "/home/jaimeloopz/.last_good_weather"
LOG_FILE = "/home/jaimeloopz/logs/weather.log"
FACTS_FILE = "/home/jaimeloopz/weather_facts.txt"
SERIAL_PORT = "/dev/ttyUSB0"
MESHTASTIC_CMD = [
    "/usr/local/bin/meshtastic",
    "--port", SERIAL_PORT,
    "--ch-index", str(CHANNEL),
    "--ack",
    "--sendtext"
]

# Open-Meteo config
LAT, LON = 40.6815, -73.8365  # Queens, NY
METEO_URL = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    f"&current=temperature_2m,apparent_temperature,wind_speed_10m,wind_direction_10m,"
    f"relative_humidity_2m,pressure_msl,weather_code"
    f"&temperature_unit=fahrenheit&wind_speed_unit=mph&pressure_unit=hPa"
)

# Weather code to emoji map
WEATHER_ICONS = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
    45: "🌫", 48: "🌫",
    51: "🌦", 53: "🌦", 55: "🌧",
    61: "🌧", 63: "🌧", 65: "🌧🌧",
    80: "🌦", 81: "🌧", 82: "⛈️",
    71: "❄️", 73: "❄️", 75: "🌨️",
    95: "⛈️", 96: "⛈️", 99: "⛈️⚡",
    56: "🌨️", 57: "🌨️", 66: "🌧❄️", 67: "🌧❄️",
}

# Wind direction emojis
WIND_ARROWS = [
    "↓", "↙", "←", "↖", "↑", "↗", "→", "↘",
    "↓", "↙", "←", "↖", "↑", "↗", "→", "↘"
]

# ────────────────────────────────────────────────
# HELPER FUNCTIONS
# ────────────────────────────────────────────────
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def load_facts():
    try:
        with open(FACTS_FILE, "r", encoding="utf-8") as f:
            facts = [line.strip() for line in f if line.strip()]
        return facts if facts else ["Queens owns the mesh 👑"]
    except FileNotFoundError:
        log("Facts file missing — using fallback")
        return ["Queens weather = best weather ❤️"]
    except Exception as e:
        log(f"Error loading facts: {e}")
        return ["Mesh loves you back ❤️"]

def get_moon_phase(dt=None):
    if dt is None:
        dt = datetime.now()
    jd = dt.timestamp() / 86400 + 2440587.5
    epoch_new_moon_jd = 2451550.1
    synodic_month = 29.530588853
    age = (jd - epoch_new_moon_jd) % synodic_month
    phase = age / synodic_month

    phases = [
        (0.03, "🌑"), (0.22, "🌒"), (0.28, "🌓"),
        (0.47, "🌔"), (0.53, "🌕"), (0.72, "🌖"),
        (0.78, "🌗"), (0.97, "🌘"), (1.0, "🌑")
    ]
    for thresh, emoji in phases:
        if phase <= thresh:
            return emoji
    return "🌑"

def get_weather_data():
    log("Fetching weather from Open-Meteo")
    try:
        r = requests.get(METEO_URL, timeout=30)
        r.raise_for_status()
        data = r.json()["current"]
        code = data["weather_code"]
        icon = WEATHER_ICONS.get(code, "☁️")

        temp = round(data["temperature_2m"])
        feels = round(data["apparent_temperature"])
        wind_speed = round(data["wind_speed_10m"])
        wind_dir_deg = data.get("wind_direction_10m", 0)
        hum = round(data["relative_humidity_2m"])
        press_hpa = data["pressure_msl"]
        press_inhg = round(press_hpa * 0.02953, 2)

        idx = round(wind_dir_deg / 22.5) % 16
        wind_arrow = WIND_ARROWS[idx]

        moon = get_moon_phase()

        raw = f"{icon}|{temp}°F|{feels}°F|{wind_speed}mph {wind_arrow}|{hum}%|{press_inhg:.2f} inHg|{moon}"
        log("Success: Got weather from Open-Meteo")
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(raw)
        return raw
    except Exception as e:
        log(f"Open-Meteo failed: {e}")

    if os.path.exists(CACHE_FILE):
        age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
        if age < timedelta(hours=4):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception as e:
                log(f"Cache read failed: {e}")
    log("No usable weather data")
    return None

def parse_weather(raw):
    parts = raw.split("|")
    if len(parts) != 7:
        return None
    icon, temp, feels, wind, hum, press, moon = (p.strip() for p in parts)

    try:
        temp_num = int(temp.replace("°F", ""))
        feels_num = int(feels.replace("°F", ""))
        wind_parts = wind.split()
        wind_speed_str = wind_parts[0].rstrip("mph").strip() if wind_parts else ""
        wind_speed = int(wind_speed_str) if wind_speed_str.isdigit() else 0
        wind_arrow = wind_parts[1] if len(wind_parts) > 1 else ""
        hum_num = int(hum.replace("%", ""))
    except ValueError:
        return None

    return icon, temp, feels, wind, hum, press, moon, wind_speed, feels_num, hum_num, wind_arrow

def get_status(feels_num, hum_num, icon, wind, hum, wind_speed):
    # Priority: Wind > Cold > Hot > Humidity > Precip > Snow
    if wind_speed > 25:
        return f"WINDY 🌬️ {wind} — hold onto your hat!"

    # Tiered COLD alerts
    if feels_num < -20:
        return f"DANGEROUS COLD 🥶 Feels like {feels_num}°F — frostbite in <10 min! Stay indoors!"
    elif feels_num < 0:
        return f"EXTREME COLD 🥶 Feels like {feels_num}°F — frostbite in 10-30 min. Limit exposure!"
    elif feels_num < 20:
        return f"VERY COLD 🥶 Feels like {feels_num}°F — frostbite risk in 30-60 min. Cover up!"
    elif feels_num < 32:
        return f"CHILLY 🥶 Feels like {feels_num}°F — layer up and stay warm!"

    # Tiered HOT alerts
    if feels_num > 130:
        return f"EXTREME HEAT DANGER 🔥 Feels like {feels_num}°F — heatstroke in minutes! Seek AC now!"
    elif feels_num > 105:
        return f"HEAT DANGER 🔥 Feels like {feels_num}°F — heat exhaustion likely. Rest, hydrate!"
    elif feels_num > 90:
        return f"EXTREME CAUTION 🔥 Feels like {feels_num}°F — cramps/stroke possible. Limit activity!"
    elif feels_num > 80:
        return f"HEAT CAUTION 🔥 Feels like {feels_num}°F — fatigue risk. Drink water, take breaks!"

    # Humidity (only if not already triggered by heat)
    if hum_num > 80:
        return f"HUMID & STICKY 💧 {hum} — muggy out there"

    # Rain (exact match)
    rain_icons = {"🌧", "🌦", "⛈️", "☔", "🌧🌧"}
    if icon in rain_icons:
        return "RAIN COMING ☔ Stay dry, Queens!"

    # Snow (only if cold enough)
    if any(x in icon for x in ["❄️", "🌨"]) and feels_num <= 32:
        return "SNOW ALERT ❄️ Bundle up!"

    return "Mild vibes — enjoy Queens!"

def build_message(icon, temp, wind, hum, press, moon, status, fact):
    now = datetime.now().strftime("%-l:%M %p")
    msg = (
        f"Queens Weather\n"
        f"{now} {icon} {temp}\n"
        f"{wind} 💧{hum} {press} {moon}\n"
        f"{status}\n"
        f"{fact}"
    )
    if len(msg) > 220:
        msg = msg[:210] + "… [trunc]"
        log(f"Message truncated to {len(msg)} chars")
    return msg

def send_to_mesh(message):
    log(f"Sending on channel {CHANNEL} ({len(message)} chars) {'[TEST-SEND]' if args.test_send else ''}")
    try:
        result = subprocess.run(
            MESHTASTIC_CMD + [message],
            check=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        log("✅ Message sent successfully")
        return True
    except Exception as e:
        log(f"❌ Send failed: {e}")
        return False

# ────────────────────────────────────────────────
# MAIN & TEST MODE
# ────────────────────────────────────────────────
def main():
    try:
        raw = get_weather_data()
        if not raw:
            return
        parsed = parse_weather(raw)
        if not parsed:
            log("Weather parsing failed")
            return
        icon, temp, feels, wind, hum, press, moon, wind_speed, feels_num, hum_num, wind_arrow = parsed
        status = get_status(feels_num, hum_num, icon, wind, hum, wind_speed)
        fact = random.choice(load_facts())
        message = build_message(icon, temp, wind, hum, press, moon, status, fact)
        send_to_mesh(message)
    except Exception as e:
        log(f"Unexpected error in main: {e}")

def dry_run_test():
    print("\n=== DRY RUN TEST (no real send) ===\n")
    raw = get_weather_data()
    if not raw:
        print("No weather data available")
        return
    parsed = parse_weather(raw)
    if not parsed:
        print("Parse failed")
        return
    icon, temp, feels, wind, hum, press, moon, wind_speed, feels_num, hum_num, wind_arrow = parsed
    status = get_status(feels_num, hum_num, icon, wind, hum, wind_speed)
    fact = random.choice(load_facts())
    message = build_message(icon, temp, wind, hum, press, moon, status, fact)
    print(message)
    print(f"\nLength: {len(message)} chars")
    print(f"Channel would be: {CHANNEL}")
    print("\n=== END DRY RUN ===\n")

if __name__ == "__main__":
    if args.test:
        dry_run_test()
    else:
        main()
