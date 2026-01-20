import pytest
from unittest.mock import patch, mock_open
import random
import queens_weather_bot as bot

# Fake raw matching current format
FAKE_RAW = "☁️|42°F|38°F|6mph ↑|78%|29.88 inHg|🌗"

@patch.object(bot, 'get_weather_data')
@patch.object(bot, 'send_to_mesh')
@patch.object(bot, 'load_facts')
def test_full_successful_flow(mock_load_facts, mock_send, mock_get_data):
    mock_get_data.return_value = FAKE_RAW
    mock_load_facts.return_value = ["Test fact 123"]

    raw = bot.get_weather_data()
    parsed = bot.parse_weather(raw)
    assert parsed is not None, "Parse should succeed with valid raw"

    icon, temp, feels, wind, hum, press, moon, wind_speed, feels_num, hum_num, wind_arrow = parsed

    status = bot.get_status(feels_num, hum_num, icon, wind, hum, wind_speed)
    fact = random.choice(mock_load_facts.return_value)
    message = bot.build_message(icon, temp, wind, hum, press, moon, status, fact)

    bot.send_to_mesh(message)

    assert "Queens Weather" in message
    assert "Mild vibes" in message           # Now passes with exact-match rain check
    assert "Test fact 123" in message
    assert "↑" in wind
    assert "inHg" in press
    mock_send.assert_called_once()

@patch.object(bot, 'get_weather_data')
def test_no_data_graceful(mock_get_data):
    mock_get_data.return_value = None
    assert bot.get_weather_data() is None

@patch.object(bot, 'get_weather_data')
def test_parse_failure(mock_get_data):
    mock_get_data.return_value = "bad|data"
    assert bot.parse_weather("bad|data") is None

def test_status_logic():
    assert "BUNDLE UP" in bot.get_status(20, 70, "☁️", "10mph →", "70%", 10)
    assert "WINDY" in bot.get_status(40, 50, "☁️", "30mph ←", "50%", 30)
    assert "HUMID & STICKY" in bot.get_status(70, 85, "☁️", "5mph", "85%", 5)
    # Rain only triggers on exact rain icons
    assert "RAIN COMING" in bot.get_status(60, 70, "🌧", "8mph", "70%", 8)
    assert "Mild vibes" in bot.get_status(60, 70, "☁️", "8mph", "70%", 8)   # no rain icon

@patch("builtins.open", new_callable=mock_open, read_data="Queens rules\nMesh forever\n")
@patch("os.path.exists", return_value=True)
def test_load_facts(mock_exists, mock_file):
    facts = bot.load_facts()
    assert len(facts) == 2
    assert "Queens rules" in facts

def test_build_message_and_truncation():
    short_msg = bot.build_message("☀️", "55°F", "5mph →", "60%", "30.10 inHg", "🌕", "Nice day", "Short fact")
    assert len(short_msg) < 220

    long_fact = "x" * 300
    long_msg = bot.build_message("☀️", "55°F", "5mph →", "60%", "30.10 inHg", "🌕", "Nice day", long_fact)
    assert "… [trunc]" in long_msg

def test_parse_includes_new_fields():
    parsed = bot.parse_weather(FAKE_RAW)
    assert parsed is not None
    _, _, _, wind, _, press, _, _, _, _, arrow = parsed
    assert arrow == "↑"
    assert "inHg" in press
