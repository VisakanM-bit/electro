import os
from flask import Flask, jsonify, render_template
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base project directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Flask app initialization
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

# Secret key
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret")

# Session settings
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

# File paths
USERS_FILE = os.path.join(BASE_DIR, "users.json")
REPORTS_FILE = os.path.join(BASE_DIR, "reports.json")
THRESHOLDS_FILE = os.path.join(BASE_DIR, "thresholds.json")

# -----------------------------
# Home Route
# -----------------------------
@app.route("/")
def index():
    return render_template("login.html")

# -----------------------------
# Test Route
# -----------------------------
@app.route("/test")
def test():
    return "Backend working successfully"

# -----------------------------
# Historical API Route
# -----------------------------
@app.route("/api/history-data")
def history_data():
    return jsonify({
        "timestamps": [
            "10:00", "10:05", "10:10", "10:15", "10:20",
            "10:25", "10:30", "10:35", "10:40", "10:45"
        ],
        "temperature": [30, 32, 34, 33, 35, 34, 36, 35, 37, 36],
        "humidity": [45, 46, 48, 47, 49, 50, 48, 47, 46, 45],
        "static_charge": [50, 52, 57, 55, 58, 60, 62, 61, 63, 64],
        "voltage": [220, 221, 219, 222, 223, 224, 221, 220, 222, 223],
        "risk_score": [0.2, 0.4, 0.8, 0.6, 0.9, 0.7, 0.85, 0.65, 0.95, 0.88]
    })

# -----------------------------
# Import routes after app init
# -----------------------------
from backend import routes