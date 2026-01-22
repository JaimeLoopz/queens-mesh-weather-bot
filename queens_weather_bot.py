#!/usr/bin/env python3
"""
Queens Mesh Weather Bot - Open-Meteo Version (Updated Jan 2026)
With tiered alerts, conditional facts, sunrise/sunset messages 30 min before, soft-test flags, etc.
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
parser.add_argument("--sunrise", action="store_true", help="Send sunrise message")
parser.add_argument("--sunset", action="store_true", help="Send sunset message")
parser.add_argument("--channel", type=int, default=1, help="Meshtastic channel index (default: 1)")
args = parser.parse_args()

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

# Open-Meteo config (includes daily sunrise/sunset/forecast)
LAT, LON = 40.6815, -73.8365
METEO_URL = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    f"&current=temperature_2m,apparent_temperature,wind_speed_10m,wind_direction_10m,"
    f"relative_humidity_2m,pressure_msl,weather_code"
    f"&daily=sunrise,sunset,temperature_2m_max,temperature_2m_min,weather_code"
    f"&temperature_unit=fahrenheit&wind_speed_unit=mph&pressure_unit=hPa"
    f"&timezone=America%2FNew_York"
)

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
            lines = [line.strip() for line in f if line.strip()]
        cold_facts = []
        hot_facts = []
        rain_facts = []
        wind_facts = []
        snow_facts = []
        humidity_facts = []
        general_facts = []
        for line in lines:
            cleaned = line.rstrip(",.;").strip()
            if line.startswith("[cold]"):
                cold_facts.append(cleaned.replace("[cold]", "").strip())
            elif line.startswith("[hot]"):
                hot_facts.append(cleaned.replace("[hot]", "").strip())
            elif line.startswith("[rain]"):
                rain_facts.append(cleaned.replace("[rain]", "").strip())
            elif line.startswith("[wind]"):
                wind_facts.append(cleaned.replace("[wind]", "").strip())
            elif line.startswith("[snow]"):
                snow_facts.append(cleaned.replace("[snow]", "").strip())
            elif line.startswith("[humidity]"):
                humidity_facts.append(cleaned.replace("[humidity]", "").strip())
            else:
                general_facts.append(cleaned)
        return cold_facts, hot_facts, rain_facts, wind_facts, snow_facts, humidity_facts, general_facts
    except FileNotFoundError:
        log("Facts file missing — using fallback")
        return [], [], [], [], [], [], ["Queens owns the mesh 👑"]
    except Exception as e:
        log(f"Error loading facts: {e}")
        return [], [], [], [], [], [], ["Mesh loves you back ❤️"]

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
    log("Fetching weather + daily forecast from Open-Meteo")
    try:
        r = requests.get(METEO_URL, timeout=30)
        r.raise_for_status()
        data = r.json()
        current = data["current"]
        daily = data["daily"]

        code = current["weather_code"]
        icon = WEATHER_ICONS.get(code, "☁️")

        temp = round(current["temperature_2m"])
        feels = round(current["apparent_temperature"])
        wind_speed = round(current["wind_speed_10m"])
        wind_dir_deg = current.get("wind_direction_10m", 0)
        hum = round(current["relative_humidity_2m"])
        press_hpa = current["pressure_msl"]
        press_inhg = round(press_hpa * 0.02953, 2)

        idx = round(wind_dir_deg / 22.5) % 16
        wind_arrow = WIND_ARROWS[idx]

        moon = get_moon_phase()

        today_idx = 0
        tomorrow_idx = 1
        sunrise_today_str = daily["sunrise"][today_idx]
        sunset_today_str = daily["sunset"][today_idx]
        sunrise_today = datetime.fromisoformat(sunrise_today_str)
        sunset_today = datetime.fromisoformat(sunset_today_str)

        pre_sunrise = sunrise_today - timedelta(minutes=30)
        pre_sunset = sunset_today - timedelta(minutes=30)

        temp_max_today = round(daily["temperature_2m_max"][today_idx])
        temp_min_today = round(daily["temperature_2m_min"][today_idx])
        forecast_code_today = daily["weather_code"][today_idx]
        forecast_icon_today = WEATHER_ICONS.get(forecast_code_today, "☁️")

        temp_max_tomorrow = round(daily["temperature_2m_max"][tomorrow_idx])
        temp_min_tomorrow = round(daily["temperature_2m_min"][tomorrow_idx])
        forecast_code_tomorrow = daily["weather_code"][tomorrow_idx]
        forecast_icon_tomorrow = WEATHER_ICONS.get(forecast_code_tomorrow, "☁️")

        raw = f"{icon}|{temp}°F|{feels}°F|{wind_speed}mph {wind_arrow}|{hum}%|{press_inhg:.2f} inHg|{moon}"
        log("Success: Got weather data")
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(raw)
        return raw, pre_sunrise, pre_sunset, sunrise_today, sunset_today, temp_max_today, temp_min_today, forecast_icon_today, temp_max_tomorrow, temp_min_tomorrow, forecast_icon_tomorrow
    except Exception as e:
        log(f"Open-Meteo failed: {e}")
        if os.path.exists(CACHE_FILE):
            age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
            if age < timedelta(hours=4):
                try:
                    with open(CACHE_FILE, "r", encoding="utf-8") as f:
                        return f.read().strip(), None, None, None, None, None, None, None, None, None, None
                except Exception as e:
                    log(f"Cache read failed: {e}")
        log("No usable weather data")
        return None, None, None, None, None, None, None, None, None, None, None

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
    if wind_speed > 25:
        return f"WINDY 🌬️ {wind} — hold onto your hat!"

    if feels_num < -20:
        return f"DANGEROUS COLD 🥶 Feels like {feels_num}°F — frostbite in <10 min! Stay indoors!"
    elif feels_num < 0:
        return f"EXTREME COLD 🥶 Feels like {feels_num}°F — frostbite in 10-30 min. Limit exposure!"
    elif feels_num < 20:
        return f"VERY COLD 🥶 Feels like {feels_num}°F — frostbite risk in 30-60 min. Cover up!"
    elif feels_num < 32:
        return f"CHILLY 🥶 Feels like {feels_num}°F — layer up and stay warm!"

    if feels_num > 130:
        return f"EXTREME HEAT DANGER 🔥 Feels like {feels_num}°F — heatstroke in minutes! Seek AC now!"
    elif feels_num > 105:
        return f"HEAT DANGER 🔥 Feels like {feels_num}°F — heat exhaustion likely. Rest, hydrate!"
    elif feels_num > 90:
        return f"EXTREME CAUTION 🔥 Feels like {feels_num}°F — cramps/stroke possible. Limit activity!"
    elif feels_num > 80:
        return f"HEAT CAUTION 🔥 Feels like {feels_num}°F — fatigue risk. Drink water, take breaks!"

    if hum_num > 80:
        return f"HUMID & STICKY 💧 {hum} — muggy out there"

    rain_icons = {"🌧", "🌦", "⛈️", "☔", "🌧🌧"}
    if icon in rain_icons:
        return "RAIN COMING ☔ Stay dry, Queens!"

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

def build_sunrise_message(sunrise_time, temp_max_today, temp_min_today, forecast_icon_today, fact):
    msg = (
        f"Queens Sunrise 🌅\n"
        f"Sunrise at {sunrise_time.strftime('%-l:%M %p')}\n"
        f"Today's forecast: {forecast_icon_today} High {temp_max_today}°F Low {temp_min_today}°F\n"
        f"{fact}"
    )
    if len(msg) > 220:
        msg = msg[:210] + "… [trunc]"
        log(f"Sunrise message truncated to {len(msg)} chars")
    return msg

def build_sunset_message(sunset_time, temp_max_tomorrow, temp_min_tomorrow, forecast_icon_tomorrow, fact):
    msg = (
        f"Queens Sunset 🌇\n"
        f"Sunset at {sunset_time.strftime('%-l:%M %p')}\n"
        f"Tomorrow's forecast: {forecast_icon_tomorrow} High {temp_max_tomorrow}°F Low {temp_min_tomorrow}°F\n"
        f"{fact}"
    )
    if len(msg) > 220:
        msg = msg[:210] + "… [trunc]"
        log(f"Sunset message truncated to {len(msg)} chars")
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
        raw, pre_sunrise, pre_sunset, sunrise_today, sunset_today, temp_max_today, temp_min_today, forecast_icon_today, temp_max_tomorrow, temp_min_tomorrow, forecast_icon_tomorrow = get_weather_data()
        if not raw:
            return
        parsed = parse_weather(raw)
        if not parsed:
            log("Weather parsing failed")
            return
        icon, temp, feels, wind, hum, press, moon, wind_speed, feels_num, hum_num, wind_arrow = parsed
        status = get_status(feels_num, hum_num, icon, wind, hum, wind_speed)

        # Conditional fact selection
        cold_facts, hot_facts, rain_facts, wind_facts, snow_facts, humidity_facts, general_facts = load_facts()
        if feels_num < 32:
            fact = random.choice(cold_facts or general_facts)
        elif feels_num > 85:
            fact = random.choice(hot_facts or general_facts)
        elif wind_speed > 15:
            fact = random.choice(wind_facts or general_facts)
        elif icon in {"🌧", "🌦", "⛈️", "☔", "🌧🌧"}:
            fact = random.choice(rain_facts or general_facts)
        elif any(x in icon for x in ["❄️", "🌨"]) and feels_num <= 32:
            fact = random.choice(snow_facts or general_facts)
        elif hum_num > 80:
            fact = random.choice(humidity_facts or general_facts)
        else:
            fact = random.choice(general_facts)

        now = datetime.now()

        if args.test:
            dry_run_test()
        elif args.sunrise:
            message = build_sunrise_message(sunrise_today, temp_max_today, temp_min_today, forecast_icon_today, fact)
            send_to_mesh(message)
        elif args.sunset:
            message = build_sunset_message(sunset_today, temp_max_tomorrow, temp_min_tomorrow, forecast_icon_tomorrow, fact)
            send_to_mesh(message)
        else:
            message = build_message(icon, temp, wind, hum, press, moon, status, fact)
            send_to_mesh(message)
    except Exception as e:
        log(f"Unexpected error in main: {e}")

def dry_run_test():
    print("\n=== DRY RUN TEST (no real send) ===\n")
    raw, pre_sunrise, pre_sunset, sunrise_today, sunset_today, temp_max_today, temp_min_today, forecast_icon_today, temp_max_tomorrow, temp_min_tomorrow, forecast_icon_tomorrow = get_weather_data()
    if not raw:
        print("No weather data available")
        return
    parsed = parse_weather(raw)
    if not parsed:
        print("Parse failed")
        return
    icon, temp, feels, wind, hum, press, moon, wind_speed, feels_num, hum_num, wind_arrow = parsed
    status = get_status(feels_num, hum_num, icon, wind, hum, wind_speed)

    cold_facts, hot_facts, rain_facts, wind_facts, snow_facts, humidity_facts, general_facts = load_facts()
    if feels_num < 32:
        fact = random.choice(cold_facts or general_facts)
    elif feels_num > 85:
        fact = random.choice(hot_facts or general_facts)
    elif wind_speed > 15:
        fact = random.choice(wind_facts or general_facts)
    elif icon in {"🌧", "🌦", "⛈️", "☔", "🌧🌧"}:
        fact = random.choice(rain_facts or general_facts)
    elif any(x in icon for x in ["❄️", "🌨"]) and feels_num <= 32:
        fact = random.choice(snow_facts or general_facts)
    elif hum_num > 80:
        fact = random.choice(humidity_facts or general_facts)
    else:
        fact = random.choice(general_facts)

    message = build_message(icon, temp, wind, hum, press, moon, status, fact)
    print(message)
    if sunrise_today:
        print(f"\nSunrise preview (30 min before {sunrise_today.strftime('%-l:%M %p')}):\n{build_sunrise_message(sunrise_today, temp_max_today, temp_min_today, forecast_icon_today, fact)}")
    if sunset_today:
        print(f"\nSunset preview (30 min before {sunset_today.strftime('%-l:%M %p')}):\n{build_sunset_message(sunset_today, temp_max_tomorrow, temp_min_tomorrow, forecast_icon_tomorrow, fact)}")
    print(f"\nLength: {len(message)} chars")
    print(f"Channel would be: {CHANNEL}")
    print("\n=== END DRY RUN ===\n")

if __name__ == "__main__":
    if args.test:
        dry_run_test()
    else:
        main()
