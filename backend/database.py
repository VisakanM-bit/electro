import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "esd_fault_prediction")


def get_db_connection(use_database=True):
    try:
        connect_args = {
            "host": MYSQL_HOST,
            "port": MYSQL_PORT,
            "user": MYSQL_USER,
            "password": MYSQL_PASSWORD,
            "auth_plugin": "mysql_native_password",
        }
        if use_database:
            connect_args["database"] = MYSQL_DATABASE
        connection = mysql.connector.connect(**connect_args)
        return connection
    except Error as error:
        raise RuntimeError(f"Database connection failed: {error}")


def initialize_database():
    schema_sql = """
    CREATE TABLE IF NOT EXISTS users (
      id INT AUTO_INCREMENT PRIMARY KEY,
      username VARCHAR(64) NOT NULL UNIQUE,
      email VARCHAR(128) NOT NULL UNIQUE,
      password_hash VARCHAR(256) NOT NULL,
      role VARCHAR(32) DEFAULT 'admin',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS sensor_data (
      id INT AUTO_INCREMENT PRIMARY KEY,
      device_id VARCHAR(64) DEFAULT 'ESP32-01',
      temperature DECIMAL(6,2) NULL,
      humidity DECIMAL(6,2) NULL,
      static_charge DECIMAL(8,2) NULL,
      voltage DECIMAL(8,2) NULL,
      risk_score DECIMAL(5,2) NULL,
      fault_status VARCHAR(32) NULL,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS predictions (
      id INT AUTO_INCREMENT PRIMARY KEY,
      sensor_record_id INT NULL,
      predicted_class VARCHAR(32) NOT NULL,
      risk_probability DECIMAL(5,4) NOT NULL,
      confidence_score DECIMAL(5,4) NOT NULL,
      prediction_input JSON NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (sensor_record_id) REFERENCES sensor_data(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS alerts (
      id INT AUTO_INCREMENT PRIMARY KEY,
      alert_name VARCHAR(128) NOT NULL,
      alert_level VARCHAR(32) NOT NULL,
      message TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS reports (
      id INT AUTO_INCREMENT PRIMARY KEY,
      report_name VARCHAR(128) NOT NULL,
      data_summary JSON NULL,
      generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS settings (
      id INT AUTO_INCREMENT PRIMARY KEY,
      config_key VARCHAR(128) NOT NULL UNIQUE,
      config_value JSON NOT NULL,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );
    """

    connection = None
    cursor = None
    try:
        try:
            connection = get_db_connection()
        except RuntimeError:
            connection = get_db_connection(use_database=False)
            cursor = connection.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE}")
            connection.commit()
            cursor.close()
            connection.close()
            connection = get_db_connection()

        cursor = connection.cursor()
        for statement in schema_sql.strip().split(";"):
            statement = statement.strip()
            if not statement:
                continue
            cursor.execute(statement)
        connection.commit()
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def query_database(query, params=None, fetch_one=False, fetch_all=False):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params or ())
        if fetch_one:
            return cursor.fetchone()
        if fetch_all:
            return cursor.fetchall()
        connection.commit()
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
