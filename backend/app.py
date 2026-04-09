import os
from flask import Flask

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret")

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

file_path = os.path.join(BASE_DIR, "users.json")

@app.route('/api/history-data')
def history_data():
    return jsonify({
        "timestamps": [
            "10:00", "10:05", "10:10", "10:15", "10:20"
        ],
        "temperature": [30, 32, 34, 33, 35],
        "humidity": [45, 46, 48, 47, 49],
        "static_charge": [50, 52, 57, 55, 58],
        "voltage": [220, 221, 219, 222, 223],
        "risk_score": [0.2, 0.4, 0.8, 0.6, 0.9]
    })
@app.route("/")
def home():
    return "Deployment working successfully"
@app.route("/test")
def test():
    return "Backend working"
from backend import routes
