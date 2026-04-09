import os
import time
import logging
import requests
from dotenv import load_dotenv
from backend.ml_predict import predict

load_dotenv()

logger = logging.getLogger("thingspeak_service")
logging.basicConfig(level=logging.INFO)

THINGSPEAK_READ_API_KEY = os.getenv("THINGSPEAK_READ_API_KEY", "")
THINGSPEAK_WRITE_API_KEY = os.getenv("THINGSPEAK_WRITE_API_KEY", "")
THINGSPEAK_CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID", "")
THINGSPEAK_BASE_URL = "https://api.thingspeak.com"
RETRY_COUNT = 3
RETRY_DELAY_SECONDS = 2


def _parse_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _calculate_risk(temperature, humidity, static_charge, voltage):
    # Rule-based risk calculation based on thresholds
    risk_score = 0.0
    
    # Temperature risk
    if temperature > 35:
        risk_score += 0.5
    elif temperature > 30:
        risk_score += 0.3
    elif temperature < 15:
        risk_score += 0.2
    
    # Humidity risk
    if humidity < 30:
        risk_score += 0.4
    elif humidity > 70:
        risk_score += 0.2
    elif humidity < 40:
        risk_score += 0.2
    
    # Static charge risk
    if static_charge > 100:
        risk_score += 0.5
    elif static_charge > 75:
        risk_score += 0.3
    elif static_charge > 50:
        risk_score += 0.2
    
    # Voltage risk (assuming normal is around 3.3V)
    if voltage > 4.0 or voltage < 2.5:
        risk_score += 0.3
    
    # Determine class
    if risk_score >= 1.0:
        fault_status = "Critical"
    elif risk_score >= 0.6:
        fault_status = "High"
    elif risk_score >= 0.3:
        fault_status = "Medium"
    else:
        fault_status = "Safe"
    
    return risk_score, fault_status


def _get_risk_value(temperature, humidity, static_charge, voltage):
    return _calculate_risk(temperature, humidity, static_charge, voltage)


def fetch_latest_feeds():
    if not THINGSPEAK_CHANNEL_ID or not THINGSPEAK_READ_API_KEY or THINGSPEAK_CHANNEL_ID == "YOUR_CHANNEL_ID" or THINGSPEAK_READ_API_KEY == "YOUR_READ_API_KEY":
        logger.warning("ThingSpeak credentials not configured or using placeholder values. Using mock data for demonstration.")
        return _get_mock_feeds()

    url = f"{THINGSPEAK_BASE_URL}/channels/{THINGSPEAK_CHANNEL_ID}/feeds.json"
    params = {
        "api_key": THINGSPEAK_READ_API_KEY,
        "results": 20,
    }

    last_exception = None
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            logger.info("Fetching ThingSpeak data attempt %d", attempt)
            response = requests.get(url, params=params, timeout=8)
            response.raise_for_status()
            data = response.json()
            feeds = data.get("feeds", [])

            parsed = []
            for feed in feeds:
                temperature = _parse_float(feed.get("field1"))
                humidity = _parse_float(feed.get("field2"))
                static_charge = _parse_float(feed.get("field3"))
                voltage = _parse_float(feed.get("field4"))
                risk_score, fault_status = _get_risk_value(
                    temperature,
                    humidity,
                    static_charge,
                    voltage,
                )

                parsed.append({
                    "id": int(feed.get("entry_id", 0)),
                    "temperature": temperature,
                    "humidity": humidity,
                    "static_charge": static_charge,
                    "voltage": voltage,
                    "risk_score": risk_score,
                    "device_id": feed.get("field6") or "ESP32-01",
                    "timestamp": feed.get("created_at", ""),
                    "fault_status": fault_status,
                })
            return parsed[::-1] if parsed else []
        except Exception as error:
            last_exception = error
            logger.warning("ThingSpeak request failed on attempt %d: %s", attempt, error)
            time.sleep(RETRY_DELAY_SECONDS)

    logger.error("ThingSpeak fetch failed after %d attempts: %s", RETRY_COUNT, last_exception)
    raise RuntimeError(f"ThingSpeak fetch failed: {last_exception}")


def fetch_last_feed():
    if not THINGSPEAK_CHANNEL_ID or not THINGSPEAK_READ_API_KEY or THINGSPEAK_CHANNEL_ID == "YOUR_CHANNEL_ID" or THINGSPEAK_READ_API_KEY == "YOUR_READ_API_KEY":
        logger.warning("ThingSpeak credentials not configured or using placeholder values. Using mock data for demonstration.")
        feeds = _get_mock_feeds()
        return feeds[-1] if feeds else None

    url = f"{THINGSPEAK_BASE_URL}/channels/{THINGSPEAK_CHANNEL_ID}/feeds/last.json"
    params = {
        "api_key": THINGSPEAK_READ_API_KEY,
    }

    last_exception = None
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            logger.info("Fetching ThingSpeak latest entry attempt %d", attempt)
            response = requests.get(url, params=params, timeout=8)
            response.raise_for_status()
            feed = response.json()
            temperature = _parse_float(feed.get("field1"))
            humidity = _parse_float(feed.get("field2"))
            static_charge = _parse_float(feed.get("field3"))
            voltage = _parse_float(feed.get("field4"))
            risk_score, fault_status = _get_risk_value(
                temperature,
                humidity,
                static_charge,
                voltage,
            )

            return {
                "id": int(feed.get("entry_id", 0)),
                "temperature": temperature,
                "humidity": humidity,
                "static_charge": static_charge,
                "voltage": voltage,
                "risk_score": risk_score,
                "device_id": feed.get("field6") or "ESP32-01",
                "timestamp": feed.get("created_at", ""),
                "fault_status": fault_status,
            }
        except Exception as error:
            last_exception = error
            logger.warning("ThingSpeak latest entry request failed on attempt %d: %s", attempt, error)
            time.sleep(RETRY_DELAY_SECONDS)

    logger.error("ThingSpeak latest entry fetch failed after %d attempts: %s", RETRY_COUNT, last_exception)
    return None


def _get_mock_feeds():
    """Return mock sensor data for demonstration when ThingSpeak is not configured."""
    import random
    from datetime import datetime, timedelta

    feeds = []
    base_time = datetime.utcnow()

    for i in range(20):
        timestamp = (base_time - timedelta(minutes=i*5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        # Generate realistic sensor readings with some variation
        temp = round(25 + random.uniform(-5, 10), 1)
        humidity = round(50 + random.uniform(-20, 30), 1)
        static_charge = round(50 + random.uniform(-30, 70), 1)
        voltage = round(3.3 + random.uniform(-0.2, 0.3), 2)

        # Calculate risk score based on sensor values
        risk_score = _calculate_mock_risk(temp, humidity, static_charge, voltage)

        feeds.append({
            "id": 1000 + i,
            "temperature": temp,
            "humidity": humidity,
            "static_charge": static_charge,
            "voltage": voltage,
            "risk_score": risk_score,
            "device_id": "ESP32-DEMO",
            "timestamp": timestamp,
            "fault_status": _map_fault_status(risk_score),
        })

    return feeds[::-1]  # Return in chronological order (oldest first)


def write_sensor_payload(temperature, humidity, static_charge, voltage, risk_score=None):
    if not THINGSPEAK_WRITE_API_KEY or THINGSPEAK_WRITE_API_KEY == "YOUR_WRITE_API_KEY":
        raise RuntimeError("ThingSpeak write API key is not configured.")

    url = f"{THINGSPEAK_BASE_URL}/update.json"
    payload = {
        "api_key": THINGSPEAK_WRITE_API_KEY,
        "field1": temperature,
        "field2": humidity,
        "field3": static_charge,
        "field4": voltage,
    }
    if risk_score is not None:
        payload["field5"] = risk_score

    response = requests.post(url, params=payload, timeout=8)
    response.raise_for_status()
    return response.json()


def _calculate_mock_risk(temperature, humidity, static_charge, voltage):
    """Calculate risk score based on sensor values."""
    risk = 0.0
    risk += max(0.0, (temperature - 25)) * 0.03
    risk += max(0.0, (60 - humidity)) * 0.02
    risk += max(0.0, (static_charge - 50)) * 0.015
    risk += max(0.0, (voltage - 3.3)) * 0.1
    return min(max(risk, 0.0), 1.0)


def _map_fault_status(risk_score):
    if risk_score >= 0.70:
        return "High Risk"
    if risk_score >= 0.35:
        return "Medium Risk"
    return "Safe"
