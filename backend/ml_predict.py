import json
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("ml_predict")
logging.basicConfig(level=logging.INFO)

THRESHOLDS_FILE = "thresholds.json"
DEFAULT_THRESHOLDS = {
    "temperature": {
        "safe": [20, 25],
        "warning": [26, 30],
        "danger": [31, 999],
    },
    "humidity": {
        "safe": [40, 60],
        "warning": [30, 40],
        "danger": [0, 29],
    },
    "static_charge": {
        "safe": [0, 50],
        "warning": [50, 100],
        "danger": [101, 999],
    },
}


def load_thresholds():
    if not os.path.exists(THRESHOLDS_FILE):
        return DEFAULT_THRESHOLDS
    try:
        with open(THRESHOLDS_FILE, "r") as file:
            return json.load(file)
    except Exception as ex:
        logger.warning("Unable to load thresholds file, using defaults: %s", ex)
        return DEFAULT_THRESHOLDS


def _normalize(value, minimum, maximum):
    if maximum <= minimum:
        return 0.0
    return min(max((value - minimum) / (maximum - minimum), 0.0), 1.0)


def _score_for_zone(value, safe_range, warning_range, danger_range):
    if safe_range[0] <= value <= safe_range[1]:
        return 0.15 + 0.18 * _normalize(value, safe_range[0], safe_range[1])
    if warning_range[0] <= value <= warning_range[1]:
        return 0.40 + 0.25 * _normalize(value, warning_range[0], warning_range[1])
    if danger_range[0] <= value <= danger_range[1]:
        return 0.70 + 0.30 * _normalize(value, danger_range[0], danger_range[1])

    all_ranges = [safe_range, warning_range, danger_range]
    min_value = min(r[0] for r in all_ranges)
    max_value = max(r[1] for r in all_ranges)
    if value < min_value:
        return 0.0
    if value > max_value:
        return 1.0
    return 0.5


def calculate_risk_probability(temperature, humidity, static_charge, voltage):
    thresholds = load_thresholds()
    temp_score = _score_for_zone(
        temperature,
        thresholds["temperature"]["safe"],
        thresholds["temperature"]["warning"],
        thresholds["temperature"]["danger"],
    )
    hum_score = _score_for_zone(
        humidity,
        thresholds["humidity"]["safe"],
        thresholds["humidity"]["warning"],
        thresholds["humidity"]["danger"],
    )
    static_score = _score_for_zone(
        static_charge,
        thresholds["static_charge"]["safe"],
        thresholds["static_charge"]["warning"],
        thresholds["static_charge"]["danger"],
    )
    return round((temp_score + hum_score + static_score) / 3.0, 4)


def classify_status(risk_probability):
    if risk_probability >= 0.70:
        return "High Risk"
    if risk_probability >= 0.35:
        return "Medium Risk"
    return "Safe"


def build_response(prediction_class, probability, confidence):
    return {
        "predicted_class": prediction_class,
        "risk_probability": round(probability, 4),
        "confidence_score": round(confidence, 4),
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }


def infer_risk(temperature, humidity, static_charge, voltage):
    risk_probability = calculate_risk_probability(temperature, humidity, static_charge, voltage)
    predicted_class = classify_status(risk_probability)
    confidence_score = max(0.65, min(0.99, risk_probability + 0.1))
    return (
        risk_probability,
        predicted_class,
        confidence_score,
    )


def predict(sensor_input):
    temperature = float(sensor_input.get("temperature", 0))
    humidity = float(sensor_input.get("humidity", 0))
    static_charge = float(sensor_input.get("static_charge", 0))
    voltage = float(sensor_input.get("voltage", 0))

    risk_probability = calculate_risk_probability(temperature, humidity, static_charge, voltage)
    predicted_class = classify_status(risk_probability)
    confidence_score = max(0.65, min(0.99, risk_probability + 0.1))
    return build_response(predicted_class, risk_probability, confidence_score)
