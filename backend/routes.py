import csv
import io
import json
import os
import smtplib
import uuid
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from dotenv import load_dotenv
from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    send_file,
)

from backend.app import app
from backend.ml_predict import predict
from services.thingspeak_service import fetch_latest_feeds, fetch_last_feed

# Load environment variables
load_dotenv()

logger = logging.getLogger("routes")
logging.basicConfig(level=logging.INFO)

USERS_FILE = "users.json"
VERIFICATION_FILE = "verification_tokens.json"
ACTIVITY_FILE = "user_activity.json"


def load_activity():
    """Load user activity log from JSON file."""
    if not os.path.exists(ACTIVITY_FILE):
        return []
    try:
        with open(ACTIVITY_FILE, "r") as file:
            return json.load(file)
    except Exception:
        return []


def send_alert_email(subject, body, to_email):
    """Send an alert email."""
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP credentials not configured, skipping email alert")
        return

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = smtp_user
    msg['To'] = to_email

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_email, msg.as_string())
        server.quit()
        logger.info("Alert email sent to %s", to_email)
    except Exception as e:
        logger.error("Failed to send alert email: %s", e)


def save_activity(activity):
    """Save user activity log to JSON file."""
    with open(ACTIVITY_FILE, "w") as file:
        json.dump(activity, file, indent=4)


def log_user_activity(username, email, action, session_type="Web"):
    """Log user activity (login/logout)."""
    activity = load_activity()
    activity.append({
        "username": username,
        "email": email,
        "action": action,
        "timestamp": datetime.utcnow().isoformat(),
        "session_type": session_type
    })
    # Keep only last 200 entries
    if len(activity) > 200:
        activity = activity[-200:]
    save_activity(activity)


def get_active_sessions():
    """Get currently active user sessions."""
    activity = load_activity()
    # Group by email, keep most recent activity for each user
    sessions_by_email = {}
    for entry in activity:
        email = entry.get("email")
        if email not in sessions_by_email or entry.get("timestamp") > sessions_by_email[email].get("timestamp"):
            sessions_by_email[email] = entry
    
    # Determine status based on last activity
    active_sessions = []
    for email, activity_entry in sessions_by_email.items():
        last_activity = activity_entry.get("timestamp")
        action = activity_entry.get("action")
        
        # If last action was logout, user is offline
        if action == "logout":
            status = "offline"
        else:
            # Parse timestamp and check if within last 30 minutes
            try:
                last_time = datetime.fromisoformat(last_activity)
                time_diff = (datetime.utcnow() - last_time).total_seconds() / 60
                if time_diff < 30:
                    status = "online"
                else:
                    status = "idle"
            except Exception:
                status = "online"
        
        active_sessions.append({
            "username": activity_entry.get("username", "Unknown"),
            "email": email,
            "login_time": activity_entry.get("timestamp"),
            "last_activity": activity_entry.get("timestamp"),
            "status": status,
            "session_type": activity_entry.get("session_type", "Web")
        })
    
    return sorted(active_sessions, key=lambda x: x.get("last_activity", ""), reverse=True)


def load_thresholds():
    """Load threshold settings from JSON file."""
    thresholds_file = "thresholds.json"
    default_thresholds = {
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
    
    if not os.path.exists(thresholds_file):
        return default_thresholds
    
    try:
        with open(thresholds_file, "r") as file:
            return json.load(file)
    except Exception:
        return default_thresholds


def save_thresholds(thresholds):
    """Save threshold settings to JSON file."""
    thresholds_file = "thresholds.json"
    with open(thresholds_file, "w") as file:
        json.dump(thresholds, file, indent=4)


REPORTS_FILE = "reports.json"


def load_reports():
    """Load generated reports from JSON storage."""
    if not os.path.exists(REPORTS_FILE):
        return []
    try:
        with open(REPORTS_FILE, "r") as file:
            return json.load(file)
    except Exception:
        return []


def save_reports(reports):
    """Save generated reports to JSON storage."""
    with open(REPORTS_FILE, "w") as file:
        json.dump(reports, file, indent=4, default=str)


def build_report_summary(report_type, latest, history):
    """Build a report summary payload for the requested report type."""
    now = datetime.utcnow().isoformat()
    report = {
        "id": uuid.uuid4().hex,
        "generated_at": now,
        "report_type": report_type,
        "report_name": "Monthly Risk Report",
        "summary": "A snapshot of recent risk activity and sensor behavior.",
        "data_summary": {},
        "report_contents": "",
    }

    safe_count = 0
    medium_count = 0
    high_count = 0
    for entry in history or []:
        risk = float(entry.get("risk_score", 0) or 0)
        if risk >= 0.70:
            high_count += 1
        elif risk >= 0.35:
            medium_count += 1
        else:
            safe_count += 1

    last_status = latest.get("fault_status") if latest else "No data"
    device_id = latest.get("device_id") if latest else "Unknown"
    total_records = len(history or [])

    if report_type == "device_health":
        report["report_name"] = "Device Health Summary"
        report["summary"] = (
            f"Latest device state for {device_id}. Fault status: {last_status}. "
            f"Recent sensor activity includes {total_records} records."
        )
        report["data_summary"] = {
            "device_id": device_id,
            "fault_status": last_status,
            "latest_temperature": latest.get("temperature") if latest else None,
            "latest_humidity": latest.get("humidity") if latest else None,
            "latest_static_charge": latest.get("static_charge") if latest else None,
            "latest_voltage": latest.get("voltage") if latest else None,
            "history_records": total_records,
            "risk_counts": {
                "safe": safe_count,
                "medium": medium_count,
                "high": high_count,
            },
        }
        report["report_contents"] = (
            f"Device Health Summary for {device_id}\n"
            f"Generated at {now}\n\n"
            f"Summary:\n"
            f"  {report['summary']}\n\n"
            f"Latest Reading:\n"
            f"  Timestamp: {latest.get('timestamp', 'N/A')}\n"
            f"  Device ID: {device_id}\n"
            f"  Fault Status: {last_status}\n"
            f"  Temperature: {latest.get('temperature', 'N/A')}\n"
            f"  Humidity: {latest.get('humidity', 'N/A')}\n"
            f"  Static Charge: {latest.get('static_charge', 'N/A')}\n"
            f"  Voltage: {latest.get('voltage', 'N/A')}\n\n"
            f"Risk Counts:\n"
            f"  Safe: {safe_count}\n"
            f"  Medium: {medium_count}\n"
            f"  High: {high_count}\n\n"
            f"Recommendations:\n"
            f"  Review devices showing medium/high risk and normalize environmental controls to reduce ESD exposure."
        )
    else:
        report["report_name"] = "Monthly Risk Report"
        report["summary"] = (
            f"Recent risk breakdown includes {safe_count} safe, {medium_count} medium, "
            f"and {high_count} high-risk entries. Latest status: {last_status}."
        )
        report["data_summary"] = {
            "latest_reading": latest,
            "history_count": total_records,
            "risk_counts": {
                "safe": safe_count,
                "medium": medium_count,
                "high": high_count,
            },
        }
        report["report_contents"] = (
            f"Monthly Risk Report\n"
            f"Generated at {now}\n\n"
            f"Summary:\n"
            f"  {report['summary']}\n\n"
            f"Risk Counts:\n"
            f"  Safe: {safe_count}\n"
            f"  Medium: {medium_count}\n"
            f"  High: {high_count}\n\n"
            f"Latest Reading:\n"
            f"  Timestamp: {latest.get('timestamp', 'N/A')}\n"
            f"  Device ID: {latest.get('device_id', 'N/A')}\n"
            f"  Fault Status: {latest.get('fault_status', 'N/A')}\n"
            f"  Temperature: {latest.get('temperature', 'N/A')}\n"
            f"  Humidity: {latest.get('humidity', 'N/A')}\n"
            f"  Static Charge: {latest.get('static_charge', 'N/A')}\n"
            f"  Voltage: {latest.get('voltage', 'N/A')}\n\n"
            f"Insights:\n"
            f"  The system observed the highest risk when latest values exceeded normal thresholds for static charge and temperature.\n"
            f"  Review the environment and sensor placement to reduce ESD exposure."
        )

    return report


def create_report(report_type="monthly_risk"):
    latest = None
    history = []
    try:
        latest = fetch_last_feed()
    except Exception:
        latest = None
    try:
        history = fetch_latest_feeds()
    except Exception:
        history = []

    if not latest and history:
        latest = history[-1]

    report = build_report_summary(report_type, latest or {}, history)
    reports = load_reports()
    reports.insert(0, report)
    save_reports(reports)
    return report


def load_users():
    """Load existing users from JSON file."""
    if not os.path.exists(USERS_FILE):
        return []

    with open(USERS_FILE, "r") as file:
        return json.load(file)


def save_users(users):
    """Save users into JSON file."""
    with open(USERS_FILE, "w") as file:
        json.dump(users, file, indent=4)


def load_verification_tokens():
    if not os.path.exists(VERIFICATION_FILE):
        return {}
    try:
        with open(VERIFICATION_FILE, "r") as file:
            return json.load(file)
    except Exception:
        return {}


def save_verification_tokens(tokens):
    with open(VERIFICATION_FILE, "w") as file:
        json.dump(tokens, file, indent=4)


def create_verification_token(email):
    tokens = load_verification_tokens()
    token = str(uuid.uuid4())
    tokens[token] = {
        "email": email,
        "created_at": datetime.utcnow().isoformat(),
    }
    save_verification_tokens(tokens)
    return token


def verify_token(token):
    tokens = load_verification_tokens()
    token_data = tokens.get(token)
    if not token_data:
        return None

    try:
        created_at = datetime.fromisoformat(token_data["created_at"])
    except Exception:
        del tokens[token]
        save_verification_tokens(tokens)
        return None

    if datetime.utcnow() - created_at > timedelta(minutes=30):
        del tokens[token]
        save_verification_tokens(tokens)
        return None

    email = token_data.get("email")
    del tokens[token]
    save_verification_tokens(tokens)
    return email


def send_project_link_email(receiver_email, verification_link):
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")

    subject = "Verify Your ESD Dashboard Access"
    body = f"""
Hello,

Thank you for signing in to the ESD Fault Prediction System.

Please verify your access by clicking the link below:
{verification_link}

If you did not request this access, please ignore this email.

Thank you,
ESD Fault Prediction Team
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()

        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        logger.info("Verification email sent successfully to %s", receiver_email)
    except Exception as exc:
        logger.warning("Email sending failed to %s: %s", receiver_email, exc)


def ensure_authenticated():
    if request.path.startswith("/api/"):
        if "email" not in session:
            return jsonify({"error": "unauthorized"}), 403
        if not session.get("verified"):
            return jsonify({"error": "verification_required"}), 403
        return None

    open_paths = {"/", "/login", "/mail-sent", "/verify"}
    if request.path in open_paths:
        return None

    if "email" not in session:
        return redirect(url_for("home"))
    if not session.get("verified"):
        return redirect(url_for("mail_sent_page"))
    return None


@app.route("/")
def home():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username") or "Operator"
    email = request.form.get("email")
    password = request.form.get("password")

    users = load_users()
    existing_user = next((user for user in users if user["email"] == email), None)

    if existing_user:
        username = existing_user.get("username", username)
    else:
        users.append({
            "username": username,
            "email": email,
            "password": password,
        })
        save_users(users)

    token = create_verification_token(email)
    base_url = request.host_url.rstrip("/")
    verification_link = f"{base_url}/verify?token={token}"
    send_project_link_email(email, verification_link)

    # Log the login activity
    log_user_activity(username, email, "login")

    session["username"] = username
    session["email"] = email
    session["verified"] = False

    return redirect(url_for("mail_sent_page"))


@app.route("/mail-sent")
def mail_sent_page():
    if "email" not in session:
        return redirect(url_for("home"))

    return render_template(
        "mail_sent.html",
        page="mail_sent",
        username=session.get("username", "Operator"),
        email=session.get("email"),
    )


@app.route("/verify")
def verify_page():
    token = request.args.get("token")
    if not token:
        return render_template(
            "verify.html",
            page="verify",
            verified=False,
            message="Verification token missing.",
        )

    verified_email = verify_token(token)
    if not verified_email:
        return render_template(
            "verify.html",
            page="verify",
            verified=False,
            message="Verification token is invalid or has expired.",
        )

    session["verified"] = True
    session["email"] = verified_email
    return render_template(
        "verify.html",
        page="verify",
        verified=True,
        message="Your email has been verified successfully.",
        username=session.get("username", "Operator"),
    )


@app.route("/dashboard")
def dashboard():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    return render_template(
        "dashboard.html",
        page="dashboard",
        username=session.get("username", "Operator"),
    )


@app.route("/live-data")
def live_data_page():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    return render_template(
        "live_data.html",
        page="live_data",
        username=session.get("username", "Operator"),
    )


@app.route("/history")
def history_page():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    return render_template(
        "historical.html",
        page="history",
        username=session.get("username", "Operator"),
    )


@app.route("/prediction-results")
def prediction_results_page():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    return render_template(
        "prediction_results.html",
        page="prediction_results",
        username=session.get("username", "Operator"),
    )


@app.route("/alerts")
def alerts_page():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    return render_template(
        "alerts.html",
        page="alerts",
        username=session.get("username", "Operator"),
    )


@app.route("/reports")
def reports_page():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    return render_template(
        "reports.html",
        page="reports",
        username=session.get("username", "Operator"),
    )


@app.route("/settings")
def settings_page():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    # Load thresholds from a JSON file
    thresholds = load_thresholds()
    
    return render_template(
        "settings.html",
        page="settings",
        username=session.get("username", "Operator"),
        thresholds=thresholds,
    )


@app.route("/final")
def final_page():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    return render_template(
        "final.html",
        page="final",
        username=session.get("username", "Operator"),
        email=session.get("email"),
    )


@app.route("/api/live-data")
def api_live_data():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    latest = None
    feeds = []
    try:
        feeds = fetch_latest_feeds()
    except Exception as exc:
        logger.warning("Failed to fetch live history data: %s", exc)
        feeds = []

    try:
        latest = fetch_last_feed()
    except Exception as exc:
        logger.warning("Failed to fetch ThingSpeak latest entry: %s", exc)
        latest = None

    if not latest and feeds:
        latest = feeds[-1] if feeds else None

    return jsonify({
        "latest": latest,
        "history": feeds,
    })


@app.route("/api/history")
def api_history():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    try:
        feeds = fetch_latest_feeds()
    except Exception as exc:
        logger.warning("Failed to fetch history data: %s", exc)
        feeds = []

    return jsonify({
        "history": feeds,
    })


@app.route("/api/predict", methods=["POST"])
def api_predict():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    result = predict(payload)
    result["input"] = {
        "temperature": float(payload.get("temperature", 0)),
        "humidity": float(payload.get("humidity", 0)),
        "static_charge": float(payload.get("static_charge", 0)),
        "voltage": float(payload.get("voltage", 0)),
    }
    return jsonify(result)


@app.route("/user-activity")
def user_activity_page():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    return render_template(
        "user_activity.html",
        page="user_activity",
        username=session.get("username", "Operator"),
        session_data=get_active_sessions(),
    )


@app.route("/api/user-activity")
def api_user_activity():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    return jsonify({
        "activities": get_active_sessions()
    })


@app.route("/api/upload-sensor", methods=["POST"])
def api_upload_sensor():
    """Endpoint for devices to upload sensor data."""
    payload = request.get_json(silent=True) or request.form.to_dict() or {}
    temperature = float(payload.get("temperature", 0))
    humidity = float(payload.get("humidity", 0))
    static_charge = float(payload.get("static_charge", 0))
    voltage = float(payload.get("voltage", 0))
    device_id = payload.get("device_id", "ESP32-01")

    try:
        from services.thingspeak_service import write_sensor_payload
        write_sensor_payload(temperature, humidity, static_charge, voltage)
        return jsonify({"status": "success", "message": "Data uploaded"})
    except Exception as exc:
        logger.warning("Failed to upload sensor data: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/api/reports", methods=["GET", "POST"])
def api_reports():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    if request.method == "GET":
        reports = load_reports()
        return jsonify({"reports": reports})

    payload = request.get_json(silent=True) or {}
    report_type = payload.get("type", "monthly_risk")
    report = create_report(report_type)
    download_url = url_for("download_report", report_id=report["id"])
    return jsonify({"status": "success", "report": report, "download_url": download_url})


@app.route("/api/reports/<report_id>/download")
def download_report(report_id):
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    reports = load_reports()
    report = next((r for r in reports if r.get("id") == report_id), None)
    if not report:
        return jsonify({"error": "Report not found"}), 404

    content_lines = [
        f"Report Name: {report.get('report_name')}",
        f"Generated At: {report.get('generated_at')}",
        f"Summary: {report.get('summary')}",
        "",
        "Data Summary:",
    ]
    for key, value in (report.get("data_summary") or {}).items():
        content_lines.append(f"{key}: {json.dumps(value, default=str)}")

    content = "\n".join(content_lines)
    buffer = io.BytesIO(content.encode("utf-8"))
    buffer.seek(0)
    filename = f"{report.get('report_name', 'report').replace(' ', '_').lower()}.txt"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="text/plain",
    )


@app.route("/api/export/csv")
def api_export_csv():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    history = []
    try:
        history = fetch_latest_feeds()
    except Exception:
        history = []

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Entry ID", "Timestamp", "Temperature", "Humidity", "Static Charge", "Voltage", "Risk Score", "Fault Status", "Device ID"])
    for entry in history:
        writer.writerow([
            entry.get("id"),
            entry.get("timestamp"),
            entry.get("temperature"),
            entry.get("humidity"),
            entry.get("static_charge"),
            entry.get("voltage"),
            entry.get("risk_score"),
            entry.get("fault_status"),
            entry.get("device_id"),
        ])

    csv_bytes = output.getvalue().encode("utf-8")
    buffer = io.BytesIO(csv_bytes)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="sensor_data_export.csv",
        mimetype="text/csv",
    )


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    auth_redirect = ensure_authenticated()
    if auth_redirect:
        return auth_redirect

    if request.method == "GET":
        return jsonify(load_thresholds())
    
    elif request.method == "POST":
        try:
            thresholds = request.get_json()
            save_thresholds(thresholds)
            return jsonify({"status": "success", "message": "Settings saved"}), 200
        except Exception as e:
            logger.error("Error saving settings: %s", str(e))
            return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/logout")
def logout():
    username = session.get("username", "Unknown")
    email = session.get("email", "unknown@example.com")
    
    # Log the logout activity
    log_user_activity(username, email, "logout")
    
    session.clear()
    return redirect(url_for("home"))
