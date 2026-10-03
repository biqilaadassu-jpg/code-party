from flask import (
    Flask, request, redirect, url_for, session,
    render_template_string, flash, send_from_directory
)
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from markupsafe import escape
from datetime import date, datetime
import os
import uuid
import json
# ============================================================
# APPLICATION
# ============================================================
app = Flask(__name__)
app.secret_key = "smart_membership_secret_key_2026"
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "webp", "svg", "bmp",
    "tiff", "tif", "ico", "avif", "heic", "heif", "jfif", "pjpeg", "pjp"
}
# ============================================================
# SYSTEM TITLES
# ============================================================
SYSTEM_TITLE = "ADDIS ABABA CITY CODE ENFORCEMENT AUTHORITY"
TITLE_EN = "Addis Ababa City Administration Code Enforcement Authority"
TITLE_OM = "Abbaa Taayitaa Kabachisaa Dambii Bulchiinsa Magaalaa Finfinnee"
TITLE_SO = "Hay'adda Fulinta Sharciga Maamulka Magaalada Addis Ababa"
TITLE_TI = "ሓላፍነት ምትግባር ሕጊ ምምሕዳር ከተማ ኣዲስ ኣበባ"
# ============================================================
# DEFAULT ADMIN CREDENTIALS
# ============================================================
DEFAULT_ADMIN_USERNAME = "codeparty"
DEFAULT_ADMIN_PASSWORD = "@codeparty2019"

# ============================================================
# PARTY LOGO
# ============================================================

PARTY_LOGO = (
    "https://thumb.wikimedia.org/wikipedia/en/thumb/f/f7/"
    "Prosperity_Party_logo.svg/960px-Prosperity_Party_logo.svg.png"
    "?utm_source=en.wikipedia.org"
    "&utm_campaign=imageinfo"
    "&utm_content=thumbnail"
)

# ============================================================
# GALLERY / SEED IMAGES
# ============================================================

GALLERY_IMAGES = [
    "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSRjospbCEGwjYsqqdTgG82pg6vr97HfM1zpxiOnJ0IvMrzxdzdyHzhRVgu&s=10",
    "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ6djk9HF0HHjFbNav2PhwSJxWCgYz62cTenUX5xRF8-g&s=10",
    "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcREDYIt9u28Jo3yPa2EWIg8YgmCZDoizlXc2Fw3Edlx4A&s=10",
    "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQsY7BHOPU3krBczrYFgoTmoSSPxwxoF5OEdbxykUyweA&s=10",
]

FALLBACK_IMAGE = (
    "https://images.unsplash.com/photo-1521737604893-d14cc237f11d"
    "?w=600&auto=format&fit=crop"
)

# ============================================================
# MYSQL SETTINGS
# ============================================================

MYSQL_HOST = "127.0.0.1"
MYSQL_USER = "root"
MYSQL_PASSWORD = ""
MYSQL_DATABASE = "organization_membership"

ETHIOPIAN_MONTHS = [
    "መስከረም", "ጥቅምት", "ኅዳር", "ታኅሣሥ", "ጥር", "የካቲት",
    "መጋቢት", "ሚያዝያ", "ግንቦት", "ሰኔ", "ሐምሌ", "ነሐሴ", "ጳጉሜን"
]
DEFAULT_PRIMARY_COLOR = "#087f5b"
DEFAULT_SECONDARY_COLOR = "#0b7285"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection(database=None):
    try:
        config = {
            "host": MYSQL_HOST,
            "user": MYSQL_USER,
            "password": MYSQL_PASSWORD
        }
        if database:
            config["database"] = database
        return mysql.connector.connect(**config)
    except Error as e:
        print("MySQL Connection Error:", e)
        return None


# ============================================================
# SYSTEM SETTINGS HELPERS
# ============================================================

def get_system_settings():
    settings = {
        "primary_color": DEFAULT_PRIMARY_COLOR,
        "secondary_color": DEFAULT_SECONDARY_COLOR,
        "gallery_image": "",
        "signature_image": ""
    }
    connection = get_connection(MYSQL_DATABASE)
    if not connection:
        return settings
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT setting_key, setting_value FROM system_settings")
        for row in cursor.fetchall():
            settings[row["setting_key"]] = row["setting_value"]
        cursor.close()
        connection.close()
    except Error:
        try: connection.close()
        except: pass
    return settings


def get_gallery_images():
    settings = get_system_settings()
    gallery_json = settings.get("gallery_image", "[]")
    try:
        if not gallery_json:
            return []
        return json.loads(gallery_json)
    except:
        return []


@app.context_processor
def inject_system_settings():
    settings = get_system_settings()
    gallery_images = get_gallery_images()
    signature = settings.get("signature_image", "") or ""
    return {
        "system_primary_color": settings.get("primary_color", DEFAULT_PRIMARY_COLOR),
        "system_secondary_color": settings.get("secondary_color", DEFAULT_SECONDARY_COLOR),
        "system_gallery_images": gallery_images,
        "system_gallery_image": gallery_images[0] if gallery_images else "",
        "system_signature_image": signature
    }


# ============================================================
# ENSURE COLUMN HELPER
# ============================================================

def ensure_column(cursor, table, column, definition):
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema=%s AND table_name=%s AND column_name=%s",
            (MYSQL_DATABASE, table, column)
        )
        exists = cursor.fetchone()[0]
        if not exists:
            cursor.execute(
                "ALTER TABLE " + table + " ADD COLUMN "
                + column + " " + definition
            )
            print("Added missing column: " + table + "." + column)
    except Error as e:
        print("ensure_column error for " + table + "." + column + ": " + str(e))


# ============================================================
# MEMBER ID CARD GENERATION HELPERS
# ============================================================

def generate_member_code(member_id):
    year = datetime.now().year
    return f"AACCEA-{year}-{str(member_id).zfill(5)}"


def generate_qr_data(member):
    return (
        f"MEMBER:{member.get('member_code', '')}|"
        f"NAME:{member.get('fullname', '')}|"
        f"PHONE:{member.get('phone', '')}|"
        f"SUB:{member.get('residential_subcity', '')}|"
        f"WOREDA:{member.get('woreda', '')}"
    )


# ============================================================
# DATABASE SETUP
# ============================================================

def setup_database():

    connection = get_connection()
    if connection is None:
        print("Cannot connect to MySQL.")
        return False

    try:
        cursor = connection.cursor()
        cursor.execute(
            "CREATE DATABASE IF NOT EXISTS " + MYSQL_DATABASE
            + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.close()
        connection.close()
    except Error as e:
        print("Database creation error:", e)
        return False

    connection = get_connection(MYSQL_DATABASE)
    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                code VARCHAR(100) UNIQUE NOT NULL,
                phone VARCHAR(50),
                address VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                organization_id INT NULL,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                fullname VARCHAR(255),
                role VARCHAR(50) DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                setting_key VARCHAR(100) UNIQUE NOT NULL,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS approvers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                approver_name VARCHAR(255) NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                position VARCHAR(255),
                signature_image VARCHAR(500),
                is_active TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        for key, value in [
            ("primary_color", DEFAULT_PRIMARY_COLOR),
            ("secondary_color", DEFAULT_SECONDARY_COLOR),
            ("gallery_image", "[]"),
            ("signature_image", "")
        ]:
            cursor.execute("SELECT id FROM system_settings WHERE setting_key=%s", (key,))
            if cursor.fetchone() is None:
                cursor.execute("INSERT INTO system_settings (setting_key, setting_value) VALUES (%s,%s)", (key, value))

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id INT AUTO_INCREMENT PRIMARY KEY,
                organization_id INT NULL,
                fullname VARCHAR(255) NOT NULL,
                phone VARCHAR(50),
                age INT,
                national_id VARCHAR(100),
                birth_date DATE,
                residential_subcity VARCHAR(150),
                woreda VARCHAR(100),
                kebele VARCHAR(100),
                union_name VARCHAR(255),
                family_name VARCHAR(255),
                ethnicity VARCHAR(100),
                health_status VARCHAR(255),
                experience_years INT DEFAULT 0,
                salary DECIMAL(12,2) DEFAULT 0,
                identification_language VARCHAR(100),
                party_responsibility VARCHAR(255),
                institution VARCHAR(255),
                membership_period VARCHAR(100),
                professional_experience VARCHAR(500),
                professional_year INT,
                professional_position VARCHAR(255),
                education_level VARCHAR(255),
                field_of_study VARCHAR(255),
                employment_type VARCHAR(255),
                employment_place VARCHAR(255),
                previous_political_organization VARCHAR(255),
                previous_political_position VARCHAR(255),
                readiness VARCHAR(255),
                address VARCHAR(500),
                photo VARCHAR(255),
                status VARCHAR(50) DEFAULT 'Pending',
                member_code VARCHAR(50) UNIQUE,
                id_issued_date DATE,
                id_expiry_date DATE,
                blood_group VARCHAR(10),
                emergency_contact VARCHAR(50),
                qr_code VARCHAR(255),
                card_generated TINYINT(1) DEFAULT 0,
                approved_at TIMESTAMP NULL,
                approved_by_id INT NULL,
                approved_by_name VARCHAR(255),
                approved_by_signature VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                member_id INT NOT NULL,
                organization_id INT NULL,
                salary DECIMAL(12,2) DEFAULT 0,
                percentage DECIMAL(5,2) DEFAULT 0,
                payment_month VARCHAR(50),
                amount DECIMAL(12,2) DEFAULT 0,
                payment_method VARCHAR(50),
                reference_number VARCHAR(100),
                payment_date DATE,
                status VARCHAR(50) DEFAULT 'Paid',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                category VARCHAR(100) DEFAULT 'News',
                content TEXT,
                photo VARCHAR(500),
                visibility VARCHAR(50) DEFAULT 'public',
                author VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.commit()

        member_columns = [
            ("organization_id", "INT NULL"),
            ("fullname", "VARCHAR(255) NOT NULL"),
            ("phone", "VARCHAR(50)"),
            ("age", "INT"),
            ("national_id", "VARCHAR(100)"),
            ("birth_date", "DATE"),
            ("residential_subcity", "VARCHAR(150)"),
            ("woreda", "VARCHAR(100)"),
            ("kebele", "VARCHAR(100)"),
            ("union_name", "VARCHAR(255)"),
            ("family_name", "VARCHAR(255)"),
            ("ethnicity", "VARCHAR(100)"),
            ("health_status", "VARCHAR(255)"),
            ("experience_years", "INT DEFAULT 0"),
            ("salary", "DECIMAL(12,2) DEFAULT 0"),
            ("identification_language", "VARCHAR(100)"),
            ("party_responsibility", "VARCHAR(255)"),
            ("institution", "VARCHAR(255)"),
            ("membership_period", "VARCHAR(100)"),
            ("professional_experience", "VARCHAR(500)"),
            ("professional_year", "INT"),
            ("professional_position", "VARCHAR(255)"),
            ("education_level", "VARCHAR(255)"),
            ("field_of_study", "VARCHAR(255)"),
            ("employment_type", "VARCHAR(255)"),
            ("employment_place", "VARCHAR(255)"),
            ("previous_political_organization", "VARCHAR(255)"),
            ("previous_political_position", "VARCHAR(255)"),
            ("readiness", "VARCHAR(255)"),
            ("address", "VARCHAR(500)"),
            ("photo", "VARCHAR(255)"),
            ("status", "VARCHAR(50) DEFAULT 'Pending'"),
            ("member_code", "VARCHAR(50) UNIQUE"),
            ("id_issued_date", "DATE"),
            ("id_expiry_date", "DATE"),
            ("blood_group", "VARCHAR(10)"),
            ("emergency_contact", "VARCHAR(50)"),
            ("qr_code", "VARCHAR(255)"),
            ("card_generated", "TINYINT(1) DEFAULT 0"),
            ("approved_at", "TIMESTAMP NULL"),
            ("approved_by_id", "INT NULL"),
            ("approved_by_name", "VARCHAR(255)"),
            ("approved_by_signature", "VARCHAR(500)"),
        ]
        for col, definition in member_columns:
            ensure_column(cursor, "members", col, definition)
        ensure_column(cursor, "members", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ensure_column(cursor, "members", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

        approver_columns = [
            ("approver_name", "VARCHAR(255) NOT NULL"),
            ("full_name", "VARCHAR(255) NOT NULL"),
            ("position", "VARCHAR(255)"),
            ("signature_image", "VARCHAR(500)"),
            ("is_active", "TINYINT(1) DEFAULT 1"),
        ]
        for col, definition in approver_columns:
            ensure_column(cursor, "approvers", col, definition)
        ensure_column(cursor, "approvers", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        payment_columns = [
            ("member_id", "INT NOT NULL"),
            ("organization_id", "INT NULL"),
            ("salary", "DECIMAL(12,2) DEFAULT 0"),
            ("percentage", "DECIMAL(5,2) DEFAULT 0"),
            ("payment_month", "VARCHAR(50)"),
            ("amount", "DECIMAL(12,2) DEFAULT 0"),
            ("payment_method", "VARCHAR(50)"),
            ("reference_number", "VARCHAR(100)"),
            ("payment_date", "DATE"),
            ("status", "VARCHAR(50) DEFAULT 'Paid'"),
        ]
        for col, definition in payment_columns:
            ensure_column(cursor, "payments", col, definition)
        ensure_column(cursor, "payments", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        post_columns = [
            ("title", "VARCHAR(255) NOT NULL"),
            ("category", "VARCHAR(100) DEFAULT 'News'"),
            ("content", "TEXT"),
            ("photo", "VARCHAR(500)"),
            ("visibility", "VARCHAR(50) DEFAULT 'public'"),
            ("author", "VARCHAR(255)"),
        ]
        for col, definition in post_columns:
            ensure_column(cursor, "posts", col, definition)
        ensure_column(cursor, "posts", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        user_columns = [
            ("organization_id", "INT NULL"),
            ("username", "VARCHAR(100) UNIQUE NOT NULL"),
            ("password", "VARCHAR(255) NOT NULL"),
            ("fullname", "VARCHAR(255)"),
            ("role", "VARCHAR(50) DEFAULT 'admin'"),
        ]
        for col, definition in user_columns:
            if col in ("username", "password"):
                continue
            ensure_column(cursor, "users", col, definition)
        ensure_column(cursor, "users", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        org_columns = [
            ("name", "VARCHAR(255) NOT NULL"),
            ("code", "VARCHAR(100) UNIQUE NOT NULL"),
            ("phone", "VARCHAR(50)"),
            ("address", "VARCHAR(255)"),
        ]
        for col, definition in org_columns:
            if col == "code":
                continue
            ensure_column(cursor, "organizations", col, definition)
        ensure_column(cursor, "organizations", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        cursor.execute("SELECT id FROM system_settings WHERE setting_key=%s", ("signature_image",))
        if cursor.fetchone() is None:
            cursor.execute("INSERT INTO system_settings (setting_key, setting_value) VALUES (%s,%s)", ("signature_image", ""))

        connection.commit()

        try:
            cursor.execute("DELETE FROM users WHERE username='' OR username IS NULL")
            cursor.execute("DELETE FROM organizations WHERE code='' OR code IS NULL")
            connection.commit()
        except:
            pass

        cursor.execute("SELECT id FROM organizations WHERE code=%s", ("LIDETA",))
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO organizations (name, code, phone, address) VALUES (%s,%s,%s,%s)",
                ("ADDIS ABABA CITY CODE ENFORCEMENT AUTHORITY", "LIDETA", "", "Lideta Sub-City")
            )
            connection.commit()

        cursor.execute("SELECT id FROM users WHERE username=%s", (DEFAULT_ADMIN_USERNAME,))
        if cursor.fetchone() is None:
            hashed_password = generate_password_hash(DEFAULT_ADMIN_PASSWORD)
            cursor.execute(
                "INSERT INTO users (organization_id, username, password, fullname, role) VALUES (%s,%s,%s,%s,%s)",
                (None, DEFAULT_ADMIN_USERNAME, hashed_password, "General Administrator", "general_admin")
            )
            connection.commit()

        cursor.execute("SELECT COUNT(*) FROM posts")
        if cursor.fetchone()[0] == 0:
            seed = [
                ("የዲጂታል ስርዓታችን በይፋ ተጀመረ", "News",
                 "አዲሱ የዲጂታል አባልነት አስተዳደር ስርዓታችን በይፋ ተጀምሯል። ይህ መድረክ የአባል ምዝገባ፣ ክፍያዎችንና የመረጃ ልውውጥን ያቀላጥፋል።",
                 GALLERY_IMAGES[0], "public"),
                ("የማህበረሰብ ልማት ተነሳሽነት ተጀመረ", "News",
                 "አካባቢያዊ ንግዶችን ለመደገፍና የመሠረተ ልማት ለማሻሻል አዲስ የማህበረሰብ ልማት ተነሳሽነት ተጀምሯል።",
                 GALLERY_IMAGES[1], "public"),
                ("የውስጥ ስብሰባ ማስታወሻ", "Internal",
                 "ሁሉም የኮሚቴ አባላት በሚቀጥለው ሳምንት የሚካሄደውን ሩብ ዓመታዊ ስትራቴጂካዊ ስብሰባ እንዲገኙ ተጋብዘዋል።",
                 GALLERY_IMAGES[2], "internal"),
                ("የፓርቲ ራዕይና ተልዕኮ", "Announcement",
                 "ራዕያችን ሰላማዊ፣ ብልጽግና ያለው፣ አንድ የሆነና ዴሞክራሲያዊ ኢትዮጵያ መገንባት ነው። ተልዕኮአችን ደግሞ ብሔራዊ ብልጽግናን፣ አንድነትንና ሁሉን አቀፍ ተሳትፎን ማስተዋወቅ ነው።",
                 GALLERY_IMAGES[3], "public"),
                ("የአባላት ምዝገባ ዘመቻ ተጀመረ", "Event",
                 "በሁሉም ወረዳዎች የአባላት ምዝገባ ዘመቻ ተጀምሯል። ሁሉም ፍላጎት ያላቸው ዜጎች እንዲመዘገቡ በአክብሮት ተጋብዘዋል።",
                 GALLERY_IMAGES[0], "public"),
                ("የልማት ስራዎች ተመረቀ", "Achievement",
                 "በአካባቢያችን የተከናወኑ የልማት ስራዎች በይፋ ተመርቀዋል። ለሁሉም ተሳታፊዎች ልዩ ምስጋና እናቀርባለን።",
                 GALLERY_IMAGES[1], "public"),
            ]
            for title, cat, content, photo, vis in seed:
                cursor.execute(
                    "INSERT INTO posts (title, category, content, photo, visibility, author) VALUES (%s,%s,%s,%s,%s,%s)",
                    (title, cat, content, photo, vis, "System")
                )
            connection.commit()

        cursor.close()
        connection.close()

        print("Database setup completed.")
        print("General Admin: " + DEFAULT_ADMIN_USERNAME)
        print("Password: " + DEFAULT_ADMIN_PASSWORD)

        return True

    except Error as e:
        print("Table setup error:", e)
        try:
            connection.close()
        except:
            pass
        return False


# ============================================================
# DECORATORS
# ============================================================

def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") not in ["general_admin", "admin"]:
            flash("Access denied.", "danger")
            return redirect(url_for("dashboard"))
        return function(*args, **kwargs)
    return wrapper


# ============================================================
# BASE HTML
# ============================================================

BASE_HTML = """
<!DOCTYPE html>
<html lang="am">

<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }}</title>

<style>
:root { --primary-color: {{ system_primary_color }}; --secondary-color: {{ system_secondary_color }}; }

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Segoe UI', 'Noto Sans Ethiopic', Arial, Helvetica, sans-serif;
    background: #f4f7fb;
    color: #172033;
    overflow-x: hidden;
}

body::before {
    content: "";
    position: fixed;
    inset: 0;
    z-index: 0;
    pointer-events: none;
    background-image: url('""" + PARTY_LOGO + """');
    background-repeat: repeat;
    background-size: 130px 130px;
    opacity: 0.06;
    transform: rotate(-18deg) scale(1.25);
    mix-blend-mode: multiply;
}

.topbar, .sidebar, .main-content, .container, .card,
.footer, .sidebar-backdrop { position: relative; z-index: 1; }

.topbar {
    position: fixed;
    top: 0; left: 0; right: 0;
    min-height: 66px;
    background: linear-gradient(135deg, var(--primary-color), var(--secondary-color), #0b7285);
    color: white;
    display: flex; align-items: center; justify-content: space-between;
    padding: 6px 18px;
    z-index: 1200;
    box-shadow: 0 4px 15px rgba(0,0,0,.2);
}

.topbar-left { display: flex; align-items: center; gap: 14px; }

.hamburger {
    background: rgba(255,255,255,.15);
    border: none; color: white; font-size: 20px;
    width: 42px; height: 42px; border-radius: 10px;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}

.hamburger:hover { background: rgba(255,255,255,.28); }

.topbar-brand { display: flex; align-items: center; gap: 12px; }

.topbar-brand img {
    width: 46px; height: 46px; object-fit: contain;
    background: white; border-radius: 50%; padding: 4px;
    flex-shrink: 0;
}

.topbar-brand-title {
    font-weight: 800; font-size: 14px;
    line-height: 1.35; max-width: 780px;
}

.topbar-brand-small {
    font-size: 11.5px; opacity: .9; margin-top: 2px; font-weight: 600;
}

.topbar-right { display: flex; align-items: center; gap: 12px; }

.topbar-user { display: flex; align-items: center; gap: 10px; font-size: 13px; font-weight: 600; }

.topbar-user-avatar {
    width: 38px; height: 38px; border-radius: 50%;
    background: linear-gradient(135deg, #12b886, #4dabf7);
    color: white;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 15px;
    box-shadow: 0 4px 12px rgba(0,0,0,.25);
    flex-shrink: 0;
}

.sidebar {
    position: fixed;
    top: 66px; left: 0; bottom: 0;
    width: 260px;
    background: linear-gradient(180deg, var(--primary-color), #0a6659, #084c41);
    color: white;
    padding: 18px 12px;
    overflow-y: auto; overflow-x: hidden;
    transition: width .3s ease, transform .3s ease;
    z-index: 1100;
    box-shadow: 4px 0 15px rgba(0,0,0,.15);
}

.sidebar.collapsed { width: 76px; }

.sidebar::-webkit-scrollbar { width: 6px; }
.sidebar::-webkit-scrollbar-thumb { background: rgba(255,255,255,.2); border-radius: 3px; }

.sidebar-section {
    font-size: 10.5px; text-transform: uppercase;
    letter-spacing: 1.2px; opacity: .6;
    padding: 12px 14px 6px;
    white-space: nowrap;
    transition: opacity .2s ease;
}

.sidebar.collapsed .sidebar-section {
    opacity: 0; height: 8px; padding: 0; overflow: hidden;
}

.sidebar-item {
    display: flex; align-items: center; gap: 12px;
    padding: 11px 14px; margin-bottom: 4px;
    border-radius: 10px;
    color: white; text-decoration: none;
    font-size: 14px; font-weight: 600;
    transition: background .2s ease, transform .15s ease;
    white-space: nowrap; overflow: hidden;
    cursor: pointer;
}

.sidebar-item:hover { background: rgba(255,255,255,.15); transform: translateX(3px); }

.sidebar-item.active {
    background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
    box-shadow: 0 6px 18px rgba(18,184,134,.35);
}

.sidebar-icon { font-size: 18px; width: 24px; text-align: center; flex-shrink: 0; }

.sidebar-label { flex: 1; transition: opacity .2s ease; }

.sidebar.collapsed .sidebar-label { opacity: 0; width: 0; pointer-events: none; }

.sidebar.collapsed .sidebar-arrow { opacity: 0; }

.sidebar-dropdown { margin-bottom: 4px; }

.sidebar-dropdown-toggle {
    display: flex; align-items: center; gap: 12px;
    padding: 11px 14px;
    border-radius: 10px;
    color: white; font-size: 14px; font-weight: 600;
    cursor: pointer;
    white-space: nowrap; overflow: hidden;
    user-select: none;
    transition: background .2s ease;
}

.sidebar-dropdown-toggle:hover { background: rgba(255,255,255,.15); }

.sidebar-arrow { font-size: 11px; transition: transform .25s ease; flex-shrink: 0; }

.sidebar-dropdown.open .sidebar-arrow { transform: rotate(90deg); }

.sidebar-submenu {
    max-height: 0; overflow: hidden;
    transition: max-height .35s ease, opacity .25s ease;
    opacity: 0; padding-left: 12px;
}

.sidebar-dropdown.open .sidebar-submenu { max-height: 500px; opacity: 1; }

.sidebar-submenu a {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 14px; margin: 2px 0;
    color: rgba(255,255,255,.85); text-decoration: none;
    font-size: 13px; font-weight: 500;
    border-radius: 8px;
    border-left: 3px solid transparent;
    transition: all .2s ease;
    white-space: nowrap;
}

.sidebar-submenu a:hover {
    background: rgba(255,255,255,.1);
    border-left-color: var(--secondary-color);
    color: white;
    padding-left: 18px;
}

.sidebar-submenu a.active {
    background: rgba(18,184,134,.25);
    border-left-color: var(--secondary-color);
    color: white;
}

.sidebar.collapsed .sidebar-submenu { max-height: 0 !important; opacity: 0 !important; }

.sidebar-divider {
    height: 1px; background: rgba(255,255,255,.15);
    margin: 14px 10px;
}

.main-content {
    margin-left: 260px;
    margin-top: 66px;
    padding: 26px;
    min-height: calc(100vh - 66px);
    transition: margin-left .3s ease;
}

.sidebar.collapsed ~ .main-content,
body.sidebar-collapsed .main-content { margin-left: 76px; }

.sidebar-backdrop {
    display: none; position: fixed; inset: 0;
    background: rgba(0,0,0,.5);
    z-index: 1050;
    backdrop-filter: blur(3px);
}

.sidebar-backdrop.show { display: block; }

.card {
    background: white;
    border-radius: 15px;
    padding: 22px;
    margin-bottom: 20px;
    box-shadow: 0 5px 20px rgba(0,0,0,.08);
}

.card h2, .card h3 { margin-top: 0; }

.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 18px;
}

.stat-card {
    color: white;
    border-radius: 16px;
    padding: 22px;
    min-height: 125px;
    box-shadow: 0 6px 18px rgba(0,0,0,.12);
    transition: transform .25s ease;
}

.stat-card:hover { transform: translateY(-4px); }

.stat-number { font-size: 32px; font-weight: bold; margin-top: 10px; }

.green { background: linear-gradient(135deg,#087f5b,#12b886); }
.blue { background: linear-gradient(135deg,#1864ab,#339af0); }
.orange { background: linear-gradient(135deg,#e67700,#ff922b); }
.red { background: linear-gradient(135deg,#c92a2a,#fa5252); }
.purple { background: linear-gradient(135deg,#6741d9,#9775fa); }

.form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 15px;
}

.form-group { display: flex; flex-direction: column; gap: 6px; }

.form-group label { font-weight: bold; font-size: 14px; }

input, select, textarea {
    width: 100%; padding: 11px;
    border: 1px solid #ccd3dc;
    border-radius: 8px;
    font-size: 14px;
    font-family: inherit;
}

textarea { min-height: 120px; resize: vertical; }

.btn {
    display: inline-block;
    padding: 10px 15px;
    border: none; border-radius: 8px;
    cursor: pointer; text-decoration: none;
    color: white; font-weight: bold; font-size: 13.5px;
}

.btn-primary { background: var(--primary-color); }
.btn-blue { background: #1971c2; }
.btn-orange { background: #e67700; }
.btn-red { background: #c92a2a; }
.btn-gray { background: #495057; }
.btn-green { background: #2f9e44; }

.btn:hover { opacity: .88; }

.table-container { overflow-x: auto; }

table { width: 100%; border-collapse: collapse; min-width: 900px; }

th { background: var(--primary-color); color: white; }
th, td { padding: 10px; border-bottom: 1px solid #ddd; text-align: left; }

tr:hover { background: #f8f9fa; }

.badge { padding: 5px 9px; border-radius: 20px; font-size: 12px; font-weight: bold; }

.badge-pending { background: #fff3bf; color: #8d6b00; }
.badge-approved { background: #d3f9d8; color: var(--primary-color); }
.badge-rejected { background: #ffe3e3; color: #c92a2a; }
.badge-public { background: #d0ebff; color: #1864ab; }
.badge-internal { background: #ffe8cc; color: #d9480f; }

.flash {
    padding: 12px 15px; border-radius: 8px;
    margin-bottom: 15px;
    background: #d3f9d8; color: var(--primary-color);
    font-weight: 600;
}

.center { text-align: center; }

.member-photo {
    width: 70px; height: 70px; object-fit: cover;
    border-radius: 50%; border: 3px solid var(--primary-color);
}

.profile-photo {
    width: 160px; height: 160px; object-fit: cover;
    border-radius: 15px; border: 4px solid var(--primary-color);
}

.search-box { display: flex; gap: 10px; margin-bottom: 15px; }
.search-box input { flex: 1; }

.post-admin-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 18px;
}

.post-admin-card {
    background: white;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 5px 18px rgba(0,0,0,.1);
    transition: transform .3s ease, box-shadow .3s ease;
    display: flex;
    flex-direction: column;
}

.post-admin-card:hover {
    transform: translateY(-6px);
    box-shadow: 0 12px 28px rgba(0,0,0,.16);
}

.post-admin-card img {
    width: 100%; height: 180px; object-fit: cover;
    display: block;
}

.post-admin-body { padding: 16px; flex: 1; display: flex; flex-direction: column; }

@media (max-width: 900px) {
    .sidebar { transform: translateX(-100%); width: 260px; }
    .sidebar.mobile-open { transform: translateX(0); }
    .sidebar.collapsed { width: 260px; }
    .sidebar.collapsed .sidebar-label,
    .sidebar.collapsed .sidebar-arrow { opacity: 1; width: auto; pointer-events: auto; }
    .sidebar.collapsed .sidebar-section { opacity: .6; height: auto; padding: 12px 14px 6px; overflow: visible; }
    .main-content { margin-left: 0 !important; }
    .topbar-brand-small { display: none; }
}

@media (max-width: 700px) {
    .topbar-user-name { display: none; }
    .topbar-brand-title { font-size: 11.5px; max-width: 200px; }
    .topbar-brand img { width: 38px; height: 38px; }
    .topbar { min-height: 60px; padding: 4px 12px; }
    .sidebar { top: 60px; }
    .main-content { margin-top: 60px; }
}

</style>

<script>

function changeLanguage(value) {
    localStorage.setItem("selectedLanguage", value);
    document.documentElement.lang = value;
    document.querySelectorAll("[data-lang]").forEach(function(item) {
        var text = item.getAttribute("data-" + value);
        if (text) item.innerHTML = text;
    });
    document.querySelectorAll("[data-ph-lang]").forEach(function(item) {
        var text = item.getAttribute("data-ph-" + value);
        if (text) item.setAttribute("placeholder", text);
    });
}

function toggleSidebar() {
    var sidebar = document.getElementById("sidebar");
    var isMobile = window.innerWidth <= 900;
    if (isMobile) {
        sidebar.classList.toggle("mobile-open");
        document.getElementById("sidebarBackdrop").classList.toggle("show");
    } else {
        sidebar.classList.toggle("collapsed");
        document.body.classList.toggle("sidebar-collapsed");
        localStorage.setItem("sidebarCollapsed",
            sidebar.classList.contains("collapsed") ? "1" : "0");
    }
}

function toggleDropdown(id) {
    var dd = document.getElementById(id);
    if (!dd) return;
    var sidebar = document.getElementById("sidebar");
    if (sidebar.classList.contains("collapsed") && window.innerWidth > 900) {
        sidebar.classList.remove("collapsed");
        document.body.classList.remove("sidebar-collapsed");
        localStorage.setItem("sidebarCollapsed", "0");
    }
    dd.classList.toggle("open");
    localStorage.setItem(id, dd.classList.contains("open") ? "1" : "0");
}

document.addEventListener("DOMContentLoaded", function() {
    var language = localStorage.getItem("selectedLanguage") || "am";
    var selector = document.getElementById("languageSelector");
    if (selector) selector.value = language;
    changeLanguage(language);

    if (window.innerWidth > 900) {
        var collapsed = localStorage.getItem("sidebarCollapsed");
        if (collapsed === "1") {
            document.getElementById("sidebar").classList.add("collapsed");
            document.body.classList.add("sidebar-collapsed");
        }
    }

    ["ddMembers", "ddPayments", "ddPosts", "ddAccounts", "ddLanguage", "ddSettings", "ddApprovals"].forEach(function(id) {
        var el = document.getElementById(id);
        if (el && localStorage.getItem(id) === "1") el.classList.add("open");
    });

    document.querySelectorAll(".sidebar a").forEach(function(link) {
        link.addEventListener("click", function() {
            if (window.innerWidth <= 900) {
                document.getElementById("sidebar").classList.remove("mobile-open");
                document.getElementById("sidebarBackdrop").classList.remove("show");
            }
        });
    });
});

function confirmDelete() {
    return confirm("Are you sure you want to delete this record?");
}

</script>

</head>

<body>

{% if session.get("user_id") %}

<div class="topbar">
    <div class="topbar-left">
        <button class="hamburger" onclick="toggleSidebar()">&#9776;</button>
        <div class="topbar-brand">
            <img src="{{ logo }}" alt="Logo">
            <div>
                <div class="topbar-brand-title"
                     data-lang
                     data-am="የአዲስ አበባ ከተማ አስተዳደር ደንብ ማስከበር ባለስልጣን"
                     data-en="Addis Ababa City Administration Code Enforcement Authority"
                     data-om="Abbaa Taayitaa Kabajaa Seeraa Bulchiinsa Magaalaa Finfinnee"
                     data-so="Hay'adda Fulinta Sharciga Maamulka Magaalada Addis Ababa"
                     data-ti="ሓላፍነት ምትግባር ሕጊ ምምሕዳር ከተማ ኣዲስ ኣበባ">
                    የአዲስ አበባ ከተማ አስተዳደር ደንብ ማስከበር ባለስልጣን
                </div>
                <div class="topbar-brand-small"
                     data-lang data-am="የአባልነት አስተዳደር" data-en="Membership Management"
                     data-om="Bulchiinsa Miseensummaa" data-so="Maamulka Xubinnimada" data-ti="ምምሕዳር ኣባልነት">
                    የአባልነት አስተዳደር
                </div>
            </div>
        </div>
    </div>
    <div class="topbar-right">
        <a href="{{ url_for('home') }}" class="btn btn-blue" style="font-size:12px;">&#127760; የህዝብ ገጽ</a>
        <div class="topbar-user">
            <div class="topbar-user-avatar">{{ session.get("fullname", "U")[0]|upper }}</div>
            <span class="topbar-user-name">{{ session.get("fullname") }}</span>
        </div>
    </div>
</div>


<div class="sidebar" id="sidebar">

    <div class="sidebar-section" data-lang data-am="ዋና" data-en="Main" data-om="Muummee" data-so="Guud" data-ti="ቀንዲ">ዋና</div>

    <a href="{{ url_for('dashboard') }}"
       class="sidebar-item {% if request.endpoint == 'dashboard' %}active{% endif %}">
        <span class="sidebar-icon">&#127968;</span>
        <span class="sidebar-label" data-lang data-am="ዳሽቦርድ" data-en="Dashboard" data-om="Daashboordii" data-so="Shaxda" data-ti="ዳሽቦርድ">ዳሽቦርድ</span>
    </a>

    <a href="{{ url_for('home') }}"
       class="sidebar-item {% if request.endpoint == 'home' %}active{% endif %}">
        <span class="sidebar-icon">&#127757;</span>
        <span class="sidebar-label" data-lang data-am="የህዝብ ገጽ" data-en="Public Site" data-om="Fuula Ummataa" data-so="Bogga Dadweynaha" data-ti="ገጽ ህዝቢ">የህዝብ ገጽ</span>
    </a>

    <div class="sidebar-dropdown" id="ddPosts">
        <div class="sidebar-dropdown-toggle" onclick="toggleDropdown('ddPosts')">
            <span class="sidebar-icon">&#128240;</span>
            <span class="sidebar-label" data-lang data-am="ልጥፎች" data-en="Posts" data-om="Maxxansa" data-so="Qoraallada" data-ti="ልጥፎታት">ልጥፎች</span>
            <span class="sidebar-arrow">&#9654;</span>
        </div>
        <div class="sidebar-submenu">
            <a href="{{ url_for('manage_posts') }}" class="{% if request.endpoint == 'manage_posts' %}active{% endif %}">
                <span>&#128203;</span>
                <span data-lang data-am="ሁሉም ልጥፎች" data-en="All Posts" data-om="Maxxansa Hunda" data-so="Dhammaan Qoraallada" data-ti="ኩሎም ልጥፎታት">ሁሉም ልጥፎች</span>
            </a>
            <a href="{{ url_for('new_post') }}" class="{% if request.endpoint == 'new_post' %}active{% endif %}">
                <span>&#10133;</span>
                <span data-lang data-am="ልጥፍ ፍጠር" data-en="Create Post" data-om="Maxxansa Uumi" data-so="Samee Qoraal" data-ti="ልጥፍ ፍጠር">ልጥፍ ፍጠር</span>
            </a>
        </div>
    </div>

    <div class="sidebar-dropdown" id="ddMembers">
        <div class="sidebar-dropdown-toggle" onclick="toggleDropdown('ddMembers')">
            <span class="sidebar-icon">&#128101;</span>
            <span class="sidebar-label" data-lang data-am="አባላት" data-en="Members" data-om="Miseensota" data-so="Xubnaha" data-ti="ኣባላት">አባላት</span>
            <span class="sidebar-arrow">&#9654;</span>
        </div>
        <div class="sidebar-submenu">
            <a href="{{ url_for('members') }}" class="{% if request.endpoint == 'members' %}active{% endif %}">
                <span>&#128203;</span>
                <span data-lang data-am="ሁሉም አባላት" data-en="All Members" data-om="Miseensota Hunda" data-so="Dhammaan Xubnaha" data-ti="ኩሎም ኣባላት">ሁሉም አባላት</span>
            </a>
            <a href="{{ url_for('new_member') }}" class="{% if request.endpoint == 'new_member' %}active{% endif %}">
                <span>&#10133;</span>
                <span data-lang data-am="አዲስ ይመዝግቡ" data-en="Register New" data-om="Haaraa Galmeessi" data-so="Diiwaangeli Cusub" data-ti="ሓድሽ መዝግብ">አዲስ ይመዝገቡ</span>
            </a>
        </div>
    </div>

    <div class="sidebar-dropdown" id="ddApprovals">
        <div class="sidebar-dropdown-toggle" onclick="toggleDropdown('ddApprovals')">
            <span class="sidebar-icon">✅</span>
            <span class="sidebar-label" data-lang data-am="ማጽደቂያ" data-en="Approvals" data-om="Mirkaneessaa" data-so="Ansixinta" data-ti="ምጽዳቕ">ማጽደቂያ</span>
            <span class="sidebar-arrow">&#9654;</span>
        </div>
        <div class="sidebar-submenu">
            <a href="{{ url_for('approvers') }}" class="{% if request.endpoint == 'approvers' %}active{% endif %}">
                <span>&#128203;</span>
                <span data-lang data-am="ሁሉም አጽዳቂዎች" data-en="All Approvers" data-om="Mirkaneessitoota Hunda" data-so="Dhammaan Ansixiyayaasha" data-ti="ኩሎም ኣጽዳቒታት">ሁሉም አጽዳቂዎች</span>
            </a>
            <a href="{{ url_for('new_approver') }}" class="{% if request.endpoint == 'new_approver' %}active{% endif %}">
                <span>&#10133;</span>
                <span data-lang data-am="አዲስ አጽዳቂ" data-en="New Approver" data-om="Mirkaneessaa Haaraa" data-so="Ansixiye Cusub" data-ti="ሓድሽ ኣጽዳቒ">አዲስ አጽዳቂ</span>
            </a>
        </div>
    </div>

    <div class="sidebar-dropdown" id="ddPayments">
        <div class="sidebar-dropdown-toggle" onclick="toggleDropdown('ddPayments')">
            <span class="sidebar-icon">&#128176;</span>
            <span class="sidebar-label" data-lang data-am="ክፍያዎች" data-en="Payments" data-om="Kaffaltii" data-so="Lacag-bixinta" data-ti="ክፍሊት">ክፍያዎች</span>
            <span class="sidebar-arrow">&#9654;</span>
        </div>
        <div class="sidebar-submenu">
            <a href="{{ url_for('payments') }}" class="{% if request.endpoint == 'payments' %}active{% endif %}">
                <span>&#128202;</span>
                <span data-lang data-am="ሁሉም ክፍያዎች" data-en="All Payments" data-om="Kaffaltii Hunda" data-so="Dhammaan Lacag-bixinta" data-ti="ኩሎም ክፍሊታት">ሁሉም ክፍያዎች</span>
            </a>
            <a href="{{ url_for('new_payment') }}" class="{% if request.endpoint == 'new_payment' %}active{% endif %}">
                <span>&#10133;</span>
                <span data-lang data-am="ክፍያ ጨምር" data-en="Add Payment" data-om="Kaffaltii Ida'i" data-so="Ku dar Lacag-bixin" data-ti="ክፍሊት ወስኽ">ክፍያ ጨምር</span>
            </a>
        </div>
    </div>

    {% if session.get("role") == "general_admin" %}

    <div class="sidebar-section" data-lang data-am="አስተዳደር" data-en="Administration" data-om="Bulchiinsa" data-so="Maamulka" data-ti="ኣስተዳደር">አስተዳደር</div>

    <div class="sidebar-dropdown" id="ddAccounts">
        <div class="sidebar-dropdown-toggle" onclick="toggleDropdown('ddAccounts')">
            <span class="sidebar-icon">&#127970;</span>
            <span class="sidebar-label" data-lang data-am="መዝገቦች" data-en="Accounts" data-om="Herrega" data-so="Xisaabaadka" data-ti="ሕሳባት">መዝገቦች</span>
            <span class="sidebar-arrow">&#9654;</span>
        </div>
        <div class="sidebar-submenu">
            <a href="{{ url_for('organizations') }}" class="{% if request.endpoint == 'organizations' %}active{% endif %}">
                <span>&#128203;</span>
                <span data-lang data-am="ሁሉም መዝገቦች" data-en="All Accounts" data-om="Herrega Hunda" data-so="Dhammaan Xisaabaadka" data-ti="ኩሎም ሕሳባት">ሁሉም መዝገቦች</span>
            </a>
            <a href="{{ url_for('new_organization') }}" class="{% if request.endpoint == 'new_organization' %}active{% endif %}">
                <span>&#10133;</span>
                <span data-lang data-am="መዝገብ ፍጠር" data-en="Create Account" data-om="Herrega Uumi" data-so="Samee Xisaab" data-ti="ሕሳብ ፍጠር">መዝገብ ፍጠር</span>
            </a>
        </div>
    </div>

    {% endif %}

    <div class="sidebar-dropdown" id="ddSettings">
        <div class="sidebar-dropdown-toggle" onclick="toggleDropdown('ddSettings')">
            <span class="sidebar-icon">⚙️</span>
            <span class="sidebar-label" data-lang data-am="የሲስተም ቅንብር" data-en="Site Setting" data-om="Qindaa'ina Sirnaa" data-so="Dejinta Nidaamka" data-ti="ቅንብር ሲስተም">የሲስተም ቅንብር</span>
            <span class="sidebar-arrow">&#9654;</span>
        </div>
        <div class="sidebar-submenu">
            <a href="{{ url_for('site_settings') }}" class="{% if request.endpoint == 'site_settings' %}active{% endif %}">
                <span>🎨</span><span data-lang data-am="የሲስተም ቀለም" data-en="System Color" data-om="Halluu Sirnaa" data-so="Midabka Nidaamka" data-ti="ሕብሪ ሲስተም">የሲስተም ቀለም</span>
            </a>
            <a href="{{ url_for('site_settings') }}#signature">
                <span>✍️</span><span data-lang data-am="Signature Upload" data-en="Signature Upload" data-om="Mallattoo Olkaa'i" data-so="Saxeex Gelin" data-ti="ፊርማ ጸዓን">Signature Upload</span>
            </a>
            <a href="{{ url_for('site_settings') }}#gallery">
                <span>🖼️</span><span data-lang data-am="Gallery Upload" data-en="Gallery Upload" data-om="Galarii Olkaa'i" data-so="Sawir Gelin" data-ti="ስእሊ ጸዓን">Gallery Upload</span>
            </a>
            <a href="{{ url_for('site_settings') }}#account">
                <span>🔐</span><span data-lang data-am="የተጠቃሚ ስም / የይለፍ ቃል" data-en="Username / Password" data-om="Maqaa fayyadamaa / Jecha darbii" data-so="Magac / Furaha sirta" data-ti="ስም ተጠቃሚ / ናይ መእተዊ ቃል">የተጠቃሚ ስም / የይለፍ ቃል</span>
            </a>
        </div>
    </div>

    <div class="sidebar-divider"></div>

    <div class="sidebar-dropdown" id="ddLanguage">
        <div class="sidebar-dropdown-toggle" onclick="toggleDropdown('ddLanguage')">
            <span class="sidebar-icon">&#127760;</span>
            <span class="sidebar-label" data-lang data-am="ቋንቋ" data-en="Language" data-om="Afaan" data-so="Luqadda" data-ti="ቋንቋ">ቋንቋ</span>
            <span class="sidebar-arrow">&#9654;</span>
        </div>
        <div class="sidebar-submenu">
            <a href="javascript:void(0)" onclick="changeLanguage('am')"><span>&#127462;&#127474;</span><span>አማርኛ</span></a>
            <a href="javascript:void(0)" onclick="changeLanguage('om')"><span>&#127466;&#127469;</span><span>Afaan Oromo</span></a>
            <a href="javascript:void(0)" onclick="changeLanguage('en')"><span>&#127468;&#127463;</span><span>English</span></a>
            <a href="javascript:void(0)" onclick="changeLanguage('so')"><span>&#127480;&#127476;</span><span>Soomaali</span></a>
            <a href="javascript:void(0)" onclick="changeLanguage('ti')"><span>&#127466;&#127479;</span><span>ትግርኛ</span></a>
        </div>
    </div>

    <div class="sidebar-divider"></div>

    <a href="{{ url_for('logout') }}" class="sidebar-item">
        <span class="sidebar-icon">&#128682;</span>
        <span class="sidebar-label" data-lang data-am="ውጣ" data-en="Logout" data-om="Ba'i" data-so="Ka bax" data-ti="ውጻእ">ውጣ</span>
    </a>

</div>

<div class="sidebar-backdrop" id="sidebarBackdrop" onclick="toggleSidebar()"></div>

{% endif %}


<div class="{% if session.get('user_id') %}main-content{% else %}container{% endif %}">

{% if session.get("user_id") %}
{% with messages = get_flashed_messages() %}
{% if messages %}
{% for message in messages %}
<div class="flash">{{ message }}</div>
{% endfor %}
{% endif %}
{% endwith %}
{% endif %}

{{ content|safe }}

</div>

</body>
</html>
"""


def page(title, content):
    return render_template_string(
        BASE_HTML,
        title=title,
        content=content,
        logo=PARTY_LOGO
    )


# ============================================================
# HOME
# ============================================================

HOME_HTML = """
<!DOCTYPE html>
<html lang="am">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>""" + SYSTEM_TITLE + """</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', 'Noto Sans Ethiopic', Arial, sans-serif; background: #eef3f8; color: #172033; overflow-x: hidden; }
.home-hero { position: relative; min-height: 460px; background: linear-gradient(135deg, #064e3b, #087f5b, #0c8599, #075e54); background-size: 400% 400%; animation: gradientShift 18s ease infinite; color: white; overflow: hidden; padding: 80px 20px 100px; text-align: center; }
.hero-slideshow { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; overflow: hidden; }
.hero-slideshow img { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; opacity: 0; transition: opacity 1.5s ease-in-out; }
.hero-slideshow img.active { opacity: 1; }
.hero-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(6, 78, 59, 0.65); z-index: 1; }
@keyframes gradientShift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
.home-hero::before, .home-hero::after { content: ""; position: absolute; border-radius: 50%; filter: blur(70px); opacity: .35; pointer-events: none; }
.home-hero::before { width: 480px; height: 480px; background: var(--secondary-color); top: -160px; left: -160px; animation: orb 14s ease-in-out infinite; }
.home-hero::after { width: 560px; height: 560px; background: #4dabf7; bottom: -200px; right: -180px; animation: orb 18s ease-in-out infinite reverse; }
@keyframes orb { 0%, 100% { transform: translate(0,0) scale(1); } 50% { transform: translate(70px,-50px) scale(1.15); } }
.home-hero-inner { position: relative; z-index: 2; max-width: 1000px; margin: 0 auto; animation: heroUp .9s cubic-bezier(.2,.9,.3,1.2) both; }
@keyframes heroUp { from { opacity: 0; transform: translateY(50px); } to { opacity: 1; transform: translateY(0); } }
.home-hero-logo { width: 110px; height: 110px; object-fit: contain; background: white; border-radius: 50%; padding: 12px; box-shadow: 0 15px 45px rgba(0,0,0,.35); animation: pulse 3s ease-in-out infinite; margin-bottom: 20px; }
@keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.06); } }
.home-hero h1 { font-size: 26px; font-weight: 900; line-height: 1.4; margin-bottom: 14px; text-shadow: 0 4px 20px rgba(0,0,0,.4); }
.home-hero h2.subtitle { font-size: 17px; font-weight: 600; opacity: .95; margin-bottom: 20px; letter-spacing: .3px; }
.home-hero p.tagline { font-size: 15px; opacity: .92; max-width: 760px; margin: 0 auto 24px; line-height: 1.65; }
.home-hero-buttons { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
.hero-btn { display: inline-block; padding: 12px 22px; border-radius: 12px; font-weight: 800; font-size: 13.5px; text-decoration: none; transition: transform .2s ease, box-shadow .2s ease; border: 2px solid transparent; }
.hero-btn.primary { background: white; color: var(--primary-color); box-shadow: 0 10px 25px rgba(0,0,0,.25); }
.hero-btn.secondary { background: transparent; color: white; border-color: rgba(255,255,255,.6); }
.hero-btn:hover { transform: translateY(-3px); box-shadow: 0 15px 32px rgba(0,0,0,.35); }
.hero-particles { position: absolute; inset: 0; overflow: hidden; pointer-events: none; z-index: 2; }
.hero-particles span { position: absolute; width: 6px; height: 6px; background: rgba(255,255,255,.6); border-radius: 50%; animation: rise 14s linear infinite; }
@keyframes rise { 0% { transform: translateY(100vh) scale(.4); opacity: 0; } 10% { opacity: .9; } 90% { opacity: .9; } 100% { transform: translateY(-20vh) scale(1.2); opacity: 0; } }
.news-ticker { background: var(--primary-color); color: white; padding: 10px 0; display: flex; align-items: center; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,.15); }
.news-ticker-label { background: var(--secondary-color); padding: 4px 14px; font-weight: 800; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; white-space: nowrap; z-index: 2; margin-right: 15px; }
.ticker-track { display: flex; gap: 60px; animation: scrollTicker 40s linear infinite; white-space: nowrap; }
.ticker-track span { font-size: 13px; font-weight: 600; }
@keyframes scrollTicker { from { transform: translateX(0); } to { transform: translateX(-50%); } }
.home-container { max-width: 1300px; margin: 0 auto; padding: 40px 20px; }
.home-section-title { text-align: center; font-size: 26px; font-weight: 900; color: var(--primary-color); margin-bottom: 6px; }
.home-section-title::after { content: ""; display: block; width: 70px; height: 4px; background: linear-gradient(90deg, #12b886, #0c8599); border-radius: 3px; margin: 12px auto 0; }
.home-section-sub { text-align: center; font-size: 13px; color: #64748b; margin-bottom: 32px; margin-top: 12px; }
.post-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 26px; }
.post-card { background: white; border-radius: 18px; overflow: hidden; box-shadow: 0 6px 20px rgba(0,0,0,.08); transition: transform .35s ease, box-shadow .35s ease; display: flex; flex-direction: column; opacity: 0; transform: translateY(30px); animation: cardIn .7s ease forwards; }
@keyframes cardIn { to { opacity: 1; transform: translateY(0); } }
.post-card:hover { transform: translateY(-8px) scale(1.01); box-shadow: 0 18px 40px rgba(0,0,0,.18); }
.post-card-image { position: relative; width: 100%; height: 220px; overflow: hidden; background: linear-gradient(135deg,#075e54,#0c8599); }
.post-card-image img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform .8s ease; }
.post-card:hover .post-card-image img { transform: scale(1.08); }
.post-card-category { position: absolute; top: 12px; left: 12px; background: rgba(18,184,134,.95); color: white; padding: 5px 12px; border-radius: 20px; font-size: 11px; font-weight: 800; letter-spacing: .5px; text-transform: uppercase; box-shadow: 0 4px 12px rgba(0,0,0,.25); z-index: 2; }
.post-card-body { padding: 20px 22px 22px; flex: 1; display: flex; flex-direction: column; background: white; }
.post-card-title { font-size: 17px; font-weight: 800; color: var(--primary-color); margin-bottom: 10px; line-height: 1.4; }
.post-card-content { font-size: 13.5px; line-height: 1.7; color: #475569; flex: 1; margin-bottom: 16px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; }
.post-card-meta { display: flex; align-items: center; justify-content: space-between; font-size: 11.5px; color: #94a3b8; padding-top: 14px; border-top: 1px solid #f1f5f9; }
.post-card-author { display: flex; align-items: center; gap: 8px; font-weight: 600; color: #64748b; }
.post-card-author-icon { width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(135deg,#12b886,#4dabf7); color: white; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800; flex-shrink: 0; }
.post-card-date { display: flex; align-items: center; gap: 5px; font-size: 11.5px; color: #94a3b8; }
.empty-feed { grid-column: 1 / -1; text-align: center; padding: 60px 20px; color: #64748b; font-size: 15px; background: white; border-radius: 18px; box-shadow: 0 6px 20px rgba(0,0,0,.08); }
.empty-feed-icon { font-size: 60px; opacity: .3; margin-bottom: 14px; }
.home-footer { background: var(--primary-color); color: rgba(255,255,255,.85); padding: 30px 20px 20px; text-align: center; margin-top: 40px; }
.home-footer a { color: #12b886; text-decoration: none; font-weight: 700; }
.home-footer-title { font-size: 15px; font-weight: 800; margin-bottom: 8px; color: white; }
.home-footer-sub { font-size: 12px; opacity: .7; }
@media (max-width: 700px) {
    .home-hero h1 { font-size: 19px; }
    .home-hero h2.subtitle { font-size: 14px; }
    .home-hero { padding: 60px 16px 70px; }
    .home-hero-logo { width: 84px; height: 84px; }
    .home-container { padding: 30px 14px; }
    .home-section-title { font-size: 21px; }
    .post-grid { grid-template-columns: 1fr; }
    .post-card-image { height: 200px; }
}
</style>
</head>
<body>

<div class="home-hero">
    {% if system_gallery_images %}
    <div class="hero-slideshow">
        {% for img in system_gallery_images %}
            <img src="{{ img if img.startswith('http') else url_for('uploaded_file', filename=img) }}" class="slide-img" alt="Gallery Image">
        {% endfor %}
    </div>
    <div class="hero-overlay"></div>
    {% endif %}

    <div class="hero-particles">
        <span style="left:5%;  animation-delay:0s;   animation-duration:13s;"></span>
        <span style="left:18%; animation-delay:2s;   animation-duration:16s;"></span>
        <span style="left:32%; animation-delay:4s;   animation-duration:12s;"></span>
        <span style="left:48%; animation-delay:1s;   animation-duration:15s;"></span>
        <span style="left:62%; animation-delay:3s;   animation-duration:14s;"></span>
        <span style="left:76%; animation-delay:5s;   animation-duration:17s;"></span>
        <span style="left:90%; animation-delay:2.5s; animation-duration:13s;"></span>
    </div>

    <div class="home-hero-inner">
        <img src="{{ logo }}" class="home-hero-logo" alt="Logo">

        <h1>የአዲስ አበባ ከተማ አስተዳደር ደንብ ማስከበር ባለስልጣን</h1>

        <h2 class="subtitle">የብልጽግና ፓርቲ ዲጂታል ስርዓት — የአባልነት አስተዳደር</h2>

        <p class="tagline">አዳዲስ ዜናዎችን፣ ማስታወቂያዎችንና የማህበረሰብ ዝመናዎችን ይከታተሉ።</p>

        <div class="home-hero-buttons">
            <a href="#feed" class="hero-btn primary">&#128240; አዳዲስ ዜናዎች</a>
            <a href="{{ url_for('login') }}" class="hero-btn secondary">&#128274; የአስተዳዳሪ መግቢያ</a>
        </div>
    </div>
</div>

<div class="news-ticker">
    <div class="news-ticker-label">&#9889; አዲስ</div>
    <div class="ticker-track">
        {% for post in ticker_posts %}<span>&#128204; {{ post.title }}</span>{% endfor %}
        {% for post in ticker_posts %}<span>&#128204; {{ post.title }}</span>{% endfor %}
    </div>
</div>

<div class="home-container" id="feed">
    <h2 class="home-section-title">አዳዲስ ልጥፎችና ማስታወቂያዎች</h2>
    <p class="home-section-sub">ከባለስልጣን ጽ/ቤት ለህዝብ የተሰጡ ዝመናዎች</p>

    <div class="post-grid">
        {% for post in posts %}
        <div class="post-card">
            <div class="post-card-image">
                {% if post.photo and post.photo.startswith('http') %}
                    <img src="{{ post.photo }}" alt="{{ post.title }}" loading="lazy">
                {% elif post.photo %}
                    <img src="{{ url_for('uploaded_file', filename=post.photo) }}" alt="{{ post.title }}" loading="lazy">
                {% else %}
                    <img src=\"""" + FALLBACK_IMAGE + """\" alt="{{ post.title }}" loading="lazy">
                {% endif %}
                <div class="post-card-category">{{ post.category or 'News' }}</div>
            </div>
            <div class="post-card-body">
                <div class="post-card-title">{{ post.title }}</div>
                <div class="post-card-content">{{ post.content or '' }}</div>
                <div class="post-card-meta">
                    <div class="post-card-author">
                        <div class="post-card-author-icon">{{ (post.author or 'S')[0]|upper }}</div>
                        <span>{{ post.author or 'System' }}</span>
                    </div>
                    <div class="post-card-date">&#128197; {{ post.created_at }}</div>
                </div>
            </div>
        </div>
        {% else %}
        <div class="empty-feed">
            <div class="empty-feed-icon">&#128240;</div>
            <h3>እስካሁን ልጥፍ የለም</h3>
            <p>ከባለስልጣን ጽ/ቤት ዝመናዎችን በቅርቡ ይመልከቱ።</p>
        </div>
        {% endfor %}
    </div>
</div>

<div class="home-footer">
    <div class="home-footer-title">""" + SYSTEM_TITLE + """</div>
    <div class="home-footer-sub">
        የተሰራው በቢኪላ ደሱ · <a href="{{ url_for('login') }}">የአስተዳዳሪ መግቢያ</a>
    </div>
</div>

<script>
document.addEventListener("DOMContentLoaded", function() {
    var slides = document.querySelectorAll('.hero-slideshow img');
    if (slides.length > 0) {
        var currentSlide = 0;
        slides[0].classList.add('active');
        setInterval(function() {
            slides[currentSlide].classList.remove('active');
            currentSlide = (currentSlide + 1) % slides.length;
            slides[currentSlide].classList.add('active');
        }, 4000);
    }
});
</script>

</body>
</html>
"""


# ============================================================
# LOGIN PAGE — 3D LOCK DOOR + OPEN BOOK
# ============================================================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="am">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>""" + SYSTEM_TITLE + """ — መግቢያ</title>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Segoe UI', 'Noto Sans Ethiopic', Arial, Helvetica, sans-serif;
    overflow-x: hidden;
}

.login-page {
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px;
    position: relative;
    overflow: hidden;
    background: linear-gradient(-45deg, #064e3b, #087f5b, #0c8599, #075e54);
    background-size: 400% 400%;
    animation: gradientShift 15s ease infinite;
    perspective: 2200px;
}

@keyframes gradientShift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

.login-page::before,
.login-page::after {
    content: "";
    position: absolute;
    border-radius: 50%;
    filter: blur(60px);
    opacity: .35;
    pointer-events: none;
}

.login-page::before {
    width: 420px;
    height: 420px;
    background: var(--secondary-color);
    top: -120px;
    left: -120px;
    animation: floatOrb 12s ease-in-out infinite;
}

.login-page::after {
    width: 520px;
    height: 520px;
    background: #4dabf7;
    bottom: -160px;
    right: -160px;
    animation: floatOrb 15s ease-in-out infinite reverse;
}

@keyframes floatOrb {
    0%, 100% { transform: translate(0,0) scale(1); }
    50% { transform: translate(60px,-40px) scale(1.15); }
}

.login-particles {
    position: absolute;
    inset: 0;
    overflow: hidden;
    pointer-events: none;
}

.login-particles span {
    position: absolute;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: rgba(255,255,255,.55);
    animation: riseParticle 12s linear infinite;
}

@keyframes riseParticle {
    0% { transform: translateY(100vh) scale(.4); opacity: 0; }
    10% { opacity: .8; }
    90% { opacity: .8; }
    100% { transform: translateY(-20vh) scale(1); opacity: 0; }
}

/* ============================================================
   LOCKED DOOR
   ============================================================ */
.login-door {
    position: relative;
    z-index: 5;
    width: min(390px, 92vw);
    min-height: 540px;
    border-radius: 22px;
    padding: 34px 25px 28px;
    background:
        linear-gradient(135deg, rgba(255,255,255,.18), rgba(255,255,255,.04)),
        linear-gradient(160deg, #075e54, #064e3b 55%, #032f2a);
    border: 8px solid rgba(255,255,255,.16);
    box-shadow:
        0 30px 70px rgba(0,0,0,.45),
        inset 0 0 0 2px rgba(255,255,255,.08),
        inset 0 0 35px rgba(0,0,0,.35);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    animation: doorEnter .8s cubic-bezier(.2,.9,.3,1.15) both;
    overflow: hidden;
}

.login-door::before {
    content: "";
    position: absolute;
    inset: 18px;
    border: 2px solid rgba(255,255,255,.12);
    border-radius: 14px;
    pointer-events: none;
}

.login-door::after {
    content: "";
    position: absolute;
    top: 0;
    bottom: 0;
    left: 50%;
    width: 2px;
    background: rgba(0,0,0,.25);
    box-shadow: 1px 0 rgba(255,255,255,.08);
}

@keyframes doorEnter {
    from { opacity: 0; transform: scale(.82) translateY(35px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
}

.door-top {
    position: relative;
    z-index: 2;
    text-align: center;
    color: white;
    margin-bottom: 22px;
}

.door-title {
    font-size: 21px;
    font-weight: 900;
    letter-spacing: .5px;
    text-shadow: 0 3px 10px rgba(0,0,0,.35);
}

.door-subtitle {
    margin-top: 6px;
    font-size: 12px;
    opacity: .82;
}

.door-logo {
    position: relative;
    z-index: 3;
    width: 128px;
    height: 128px;
    object-fit: contain;
    border-radius: 50%;
    padding: 10px;
    background: white;
    box-shadow:
        0 0 0 7px rgba(255,255,255,.10),
        0 15px 35px rgba(0,0,0,.4);
    margin-bottom: 28px;
}

.lock-button {
    position: relative;
    z-index: 5;
    width: 116px;
    height: 116px;
    border: 0;
    border-radius: 50%;
    cursor: pointer;
    background: linear-gradient(145deg, #12b886, #087f5b);
    color: white;
    box-shadow:
        0 12px 30px rgba(0,0,0,.4),
        inset 0 3px 5px rgba(255,255,255,.28),
        inset 0 -5px 10px rgba(0,0,0,.22);
    transition: transform .2s ease, box-shadow .2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.lock-button:hover {
    transform: scale(1.08);
    box-shadow:
        0 18px 38px rgba(0,0,0,.48),
        0 0 0 10px rgba(18,184,134,.15),
        inset 0 3px 5px rgba(255,255,255,.28);
}

.lock-button:active { transform: scale(.96); }

.lock-icon {
    font-size: 54px;
    line-height: 1;
    filter: drop-shadow(0 3px 4px rgba(0,0,0,.35));
}

.door-hint {
    position: relative;
    z-index: 3;
    color: white;
    text-align: center;
    margin-top: 22px;
    font-size: 13px;
    font-weight: 700;
}

.door-hint-small {
    position: relative;
    z-index: 3;
    color: rgba(255,255,255,.65);
    text-align: center;
    margin-top: 7px;
    font-size: 11px;
}

.login-door.unlocking {
    animation: doorUnlock .55s ease both;
}

@keyframes doorUnlock {
    0% { transform: scale(1); }
    45% { transform: scale(1.035); }
    100% { transform: scale(.98); opacity: .25; }
}

/* ============================================================
   3D OPEN BOOK
   ============================================================ */
.book-scene {
    position: relative;
    z-index: 6;
    display: none;
    width: 100%;
    max-width: 1100px;
    margin: 0 auto;
    perspective: 2500px;
    perspective-origin: 50% 40%;
}

.book-scene.visible {
    display: block;
    animation: sceneIn 1s cubic-bezier(.2,.9,.3,1.15) both;
}

@keyframes sceneIn {
    0% { opacity: 0; transform: scale(.82) translateY(30px); }
    65% { opacity: 1; transform: scale(1.02) translateY(-4px); }
    100% { opacity: 1; transform: scale(1) translateY(0); }
}

.book {
    position: relative;
    width: 100%;
    display: flex;
    transform-style: preserve-3d;
    transform: rotateX(10deg) rotateY(0deg);
    animation: bookOpen 1.6s cubic-bezier(.22,.9,.28,1.05) .15s both;
    border-radius: 8px;
}

@keyframes bookOpen {
    0% {
        transform: rotateX(35deg) rotateY(-55deg) scale(.75);
        opacity: 0;
    }
    55% {
        transform: rotateX(18deg) rotateY(-8deg) scale(.98);
        opacity: 1;
    }
    100% {
        transform: rotateX(10deg) rotateY(0deg) scale(1);
        opacity: 1;
    }
}

.book-spine {
    position: absolute;
    left: 50%;
    top: 0;
    bottom: 0;
    width: 14px;
    margin-left: -7px;
    background:
        linear-gradient(to right,
            rgba(0,0,0,.35) 0%,
            rgba(0,0,0,.05) 30%,
            rgba(0,0,0,.75) 50%,
            rgba(0,0,0,.05) 70%,
            rgba(0,0,0,.35) 100%);
    z-index: 10;
    pointer-events: none;
    box-shadow:
        -6px 0 14px rgba(0,0,0,.28),
         6px 0 14px rgba(0,0,0,.28);
    border-radius: 3px;
}

.book-page {
    position: relative;
    width: 50%;
    min-height: 620px;
    background: #fffdf5;
    padding: 34px 34px 30px;
    overflow: hidden;
    transform-style: preserve-3d;
    backface-visibility: hidden;
    transition: box-shadow .4s ease;
}

.book-page.right {
    background:
        linear-gradient(to bottom,
            #fffdf5 0px, #fffdf5 31px,
            #cfe3f5 31px, #cfe3f5 32px,
            #fffdf5 32px);
    background-size: 100% 32px;
    border-top-right-radius: 12px;
    border-bottom-right-radius: 12px;
    border-left: 1px solid #e3ddc8;
    box-shadow:
        inset -12px 0 25px -12px rgba(0,0,0,.18),
        6px 12px 30px rgba(0,0,0,.25);
    transform-origin: left center;
    transform: rotateY(-6deg);
    z-index: 3;
}

.book-page.left {
    background: linear-gradient(135deg, #fffef8 0%, #fdf9ec 100%);
    border-top-left-radius: 12px;
    border-bottom-left-radius: 12px;
    border-right: 1px solid #e3ddc8;
    box-shadow:
        inset 12px 0 25px -12px rgba(0,0,0,.18),
        -6px 12px 30px rgba(0,0,0,.25);
    transform-origin: right center;
    transform: rotateY(6deg);
    z-index: 3;
    display: flex;
    flex-direction: column;
    justify-content: center;
}

.book-page.right::before {
    content: "";
    position: absolute;
    top: 0;
    bottom: 0;
    left: 38px;
    width: 2px;
    background: #e8a0a0;
    opacity: .65;
    pointer-events: none;
}

.book-page::after {
    content: "";
    position: absolute;
    bottom: 14px;
    font-size: 11px;
    color: #94a3b8;
    font-family: 'Georgia', serif;
    font-style: italic;
    letter-spacing: 1px;
}

.book-page.left::after {
    left: 24px;
    content: "❦ 1";
}

.book-page.right::after {
    right: 24px;
    content: "2 ❦";
}

.login-logo-wrap {
    position: relative;
    width: 110px;
    height: 110px;
    margin: 0 auto 12px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.login-logo-ring {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 2px dashed rgba(8,127,91,.55);
    animation: spinRing 14s linear infinite;
}

@keyframes spinRing {
    to { transform: rotate(360deg); }
}

.login-logo-ring::before {
    content: "";
    position: absolute;
    inset: -6px;
    border-radius: 50%;
    border: 2px solid transparent;
    border-top-color: #12b886;
    border-right-color: #4dabf7;
    animation: spinRing 3s linear infinite reverse;
}

.login-logo {
    width: 84px;
    height: 84px;
    object-fit: contain;
    display: block;
    position: relative;
    z-index: 2;
    background: white;
    border-radius: 50%;
    padding: 8px;
    box-shadow: 0 8px 25px rgba(8,127,91,.3);
    animation: logoPulse 3s ease-in-out infinite;
}

@keyframes logoPulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.06); }
}

.login-card h2 {
    margin: 8px 0 4px;
    font-size: 13px;
    line-height: 1.5;
    color: var(--primary-color);
    text-align: center;
    font-weight: 800;
}

.login-card h3 {
    margin: 6px 0 18px;
    font-size: 11.5px;
    color: var(--primary-color);
    text-align: center;
    font-weight: 700;
}

.float-group {
    position: relative;
    margin-bottom: 16px;
}

.float-group input {
    width: 100%;
    padding: 15px 44px;
    border: 2px solid #e2e8f0;
    border-radius: 12px;
    font-size: 14px;
    background: #f8fafc;
    transition: all .25s ease;
    outline: none;
    color: #172033;
}

.float-group input:focus {
    border-color: var(--secondary-color);
    background: white;
    box-shadow: 0 0 0 4px rgba(18,184,134,.15);
}

.float-group label {
    position: absolute;
    left: 44px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 13.5px;
    color: #94a3b8;
    pointer-events: none;
    transition: all .22s ease;
    background: transparent;
    padding: 0 6px;
}

.float-group input:focus + label,
.float-group input:not(:placeholder-shown) + label {
    top: 0;
    left: 38px;
    font-size: 11px;
    font-weight: 700;
    color: var(--primary-color);
    background: white;
    border-radius: 6px;
}

.input-icon {
    position: absolute;
    left: 15px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 16px;
    color: var(--primary-color);
    pointer-events: none;
    z-index: 2;
}

.pw-toggle {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 16px;
    color: #64748b;
    padding: 6px;
    border-radius: 6px;
    z-index: 2;
}

.pw-toggle:hover {
    background: #e6fffa;
    color: var(--primary-color);
}

.login-btn {
    width: 100%;
    padding: 14px;
    border: none;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 800;
    letter-spacing: 1px;
    color: white;
    cursor: pointer;
    position: relative;
    overflow: hidden;
    background: linear-gradient(135deg, #087f5b, #12b886, #0c8599);
    background-size: 200% 200%;
    box-shadow: 0 10px 25px rgba(8,127,91,.35);
    animation: btnGradient 4s ease infinite;
    transition: transform .2s ease, box-shadow .2s ease;
}

.login-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 14px 32px rgba(8,127,91,.5);
}

@keyframes btnGradient {
    0%, 100% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
}

.login-btn.loading {
    pointer-events: none;
    opacity: .9;
}

.login-btn.loading::after {
    content: "";
    position: absolute;
    right: 18px;
    top: 50%;
    width: 16px;
    height: 16px;
    margin-top: -8px;
    border: 3px solid rgba(255,255,255,.4);
    border-top-color: white;
    border-radius: 50%;
    animation: spin .7s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.login-lang { margin-top: 14px; }

.login-lang select {
    width: 100%;
    padding: 11px 14px;
    border-radius: 12px;
    border: 2px solid #e2e8f0;
    background: #f8fafc;
    font-size: 13.5px;
    color: #172033;
    cursor: pointer;
    outline: none;
}

.login-lang select:hover,
.login-lang select:focus {
    border-color: var(--secondary-color);
    background: white;
    box-shadow: 0 0 0 4px rgba(18,184,134,.12);
}

.flash-login {
    padding: 11px 14px;
    border-radius: 10px;
    margin-bottom: 14px;
    background: #ffe3e3;
    color: #c92a2a;
    font-size: 13px;
    font-weight: 600;
    text-align: center;
    border: 1px solid #ffc9c9;
}

.back-home {
    display: block;
    text-align: center;
    margin-top: 12px;
    font-size: 12.5px;
    color: var(--primary-color);
    font-weight: 700;
    text-decoration: none;
}

.back-home:hover { text-decoration: underline; }

.login-card.shake {
    animation: shakeCard .55s cubic-bezier(.36,.07,.19,.97) both;
}

@keyframes shakeCard {
    10%, 90% { transform: translateX(-3px); }
    20%, 80% { transform: translateX(5px); }
    30%, 50%, 70% { transform: translateX(-8px); }
    40%, 60% { transform: translateX(8px); }
}

/* NOTEBOOK */
.notebook {
    position: relative;
    padding: 4px 8px 4px 34px;
    height: 100%;
}

.notebook-title {
    font-size: 19px;
    font-weight: 900;
    color: #075e54;
    text-align: center;
    margin-bottom: 6px;
    padding-bottom: 10px;
    border-bottom: 2px dashed #cfe3f5;
    letter-spacing: .5px;
    font-family: 'Georgia', 'Noto Sans Ethiopic', serif;
}

.notebook-subtitle {
    font-size: 11px;
    color: #94a3b8;
    text-align: center;
    margin-bottom: 20px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.notebook-section { margin-bottom: 18px; }

.notebook-section h4 {
    font-size: 14.5px;
    font-weight: 900;
    color: #0c8599;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'Georgia', 'Noto Sans Ethiopic', serif;
}

.notebook-section h4 .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #12b886;
    flex-shrink: 0;
    box-shadow: 0 0 0 3px rgba(18,184,134,.2);
}

.notebook-section ul {
    list-style: none;
    padding: 0;
    margin: 0;
}

.notebook-section li {
    position: relative;
    padding-left: 20px;
    margin-bottom: 7px;
    font-size: 12.5px;
    line-height: 1.6;
    color: #334155;
}

.notebook-section li::before {
    content: "✎";
    position: absolute;
    left: 0;
    color: #12b886;
    font-size: 11px;
    top: 2px;
}

.notebook-section li::after {
    content: "";
    position: absolute;
    left: 14px;
    right: 0;
    bottom: -3px;
    height: 0;
    border-bottom: 1px dotted #d4d4d4;
}

.notebook-lang {
    display: flex;
    gap: 6px;
    justify-content: center;
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px dashed #cfe3f5;
}

.notebook-lang button {
    background: #e6fffa;
    border: 1px solid #b2f2e5;
    color: #087f5b;
    padding: 4px 10px;
    border-radius: 8px;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
    transition: all .2s ease;
}

.notebook-lang button:hover,
.notebook-lang button.active {
    background: #087f5b;
    color: white;
    border-color: #087f5b;
}

/* RESPONSIVE */
@media (max-width: 1000px) {
    .book {
        flex-direction: column;
        transform: rotateX(6deg);
    }
    @keyframes bookOpen {
        0% { transform: rotateX(25deg) scale(.8); opacity: 0; }
        100% { transform: rotateX(6deg) scale(1); opacity: 1; }
    }
    .book-spine { display: none; }
    .book-page {
        width: 100%;
        min-height: auto;
        transform: none !important;
        border-radius: 14px;
        margin-bottom: 16px;
    }
    .book-page.left { order: 1; }
    .book-page.right { order: 2; border-left: none; }
    .book-page.left::after, .book-page.right::after { display: none; }
}

@media (max-width: 600px) {
    .login-door {
        min-height: 500px;
        padding: 28px 18px;
    }

    .door-logo { width: 105px; height: 105px; }

    .lock-button { width: 100px; height: 100px; }
    .lock-icon { font-size: 46px; }

    .book-page { padding: 26px 22px 24px; }
    .book-page.right::before { display: none; }
    .notebook { padding: 4px 4px 4px 10px; }
    .notebook-section li { font-size: 11.5px; }
    .notebook-title { font-size: 16px; }
}
</style>
</head>

<body>

<div class="login-page">

    <div class="login-particles">
        <span style="left:5%;animation-delay:0s;animation-duration:11s;"></span>
        <span style="left:15%;animation-delay:2s;animation-duration:14s;"></span>
        <span style="left:25%;animation-delay:4s;animation-duration:10s;"></span>
        <span style="left:38%;animation-delay:1s;animation-duration:13s;"></span>
        <span style="left:52%;animation-delay:3s;animation-duration:12s;"></span>
        <span style="left:65%;animation-delay:5s;animation-duration:15s;"></span>
        <span style="left:78%;animation-delay:2.5s;animation-duration:11s;"></span>
        <span style="left:88%;animation-delay:4.5s;animation-duration:14s;"></span>
        <span style="left:95%;animation-delay:1.5s;animation-duration:12s;"></span>
    </div>

    <div class="login-door" id="loginDoor">

        <div class="door-top">
            <div class="door-title"
                 data-lang
                 data-am="የመግቢያ በር"
                 data-en="SECURE LOGIN DOOR"
                 data-om="BALBALA SEENAA"
                 data-so="ALBAABKA GELINTA"
                 data-ti="ማዕጾ መእተዊ">
                የመግቢያ በር
            </div>
            <div class="door-subtitle"
                 data-lang
                 data-am="ለመግባት በሩን ይክፈቱ"
                 data-en="Unlock the door to continue"
                 data-om="Itti fufuuf balbala bani"
                 data-so="Fur albaabka si aad u sii waddo"
                 data-ti="ንምቕጻል ማዕጾ ክፈቱ">
                ለመግባት በሩን ይክፈቱ
            </div>
        </div>

        <img src="{{ logo }}" class="door-logo" alt="Logo">

        <button type="button" class="lock-button" id="unlockButton"
                aria-label="Unlock login">
            <span class="lock-icon" id="lockIcon">🔒</span>
        </button>

        <div class="door-hint"
             data-lang
             data-am="🔒 ቁልፉን ይጫኑ"
             data-en="🔒 Press the lock to login"
             data-om="🔒 Qulfii cuqaasiitii seeni"
             data-so="🔒 Riix qufulka si aad u gasho"
             data-ti="🔒 ንምእታው መፍትሕ ጸቕጡ">
            🔒 ቁልፉን ይጫኑ
        </div>

        <div class="door-hint-small"
             data-lang
             data-am="የተጠቃሚ ስም እና የይለፍ ቃል ከዚያ ይታያሉ"
             data-en="Username and password will appear after unlocking"
             data-om="Maqaan fayyadamaa fi jechi darbii erga bananii booda ni mul'ata"
             data-so="Magaca isticmaalaha iyo erayga sirta ah ayaa soo muuqanaya marka la furo"
             data-ti="ስም ተጠቃሚን ቃል መእተዊን ድሕሪ ምኽፋት ክርአ እዩ">
            የተጠቃሚ ስም እና የይለፍ ቃል ከዚያ ይታያሉ
        </div>

    </div>

    <div class="book-scene" id="bookScene">

        <div class="book">
            <div class="book-spine"></div>

            <div class="book-page left">
                <div class="login-card" id="loginCard">

                    <div class="login-logo-wrap">
                        <div class="login-logo-ring"></div>
                        <img src="{{ logo }}" class="login-logo" alt="Logo">
                    </div>

                    <h2 data-lang
                        data-am="የአዲስ አበባ ከተማ አስተዳደር ደንብ ማስከበር ባለስልጣን"
                        data-en="Addis Ababa City Administration Code Enforcement Authority"
                        data-om="Abbaa Taayitaa Kabajaa Seeraa Bulchiinsa Magaalaa Finfinnee"
                        data-so="Hay'adda Fulinta Sharciga Maamulka Magaalada Addis Ababa"
                        data-ti="ሓላፍነት ምትግባር ሕጊ ምምሕዳር ከተማ ኣዲስ ኣበባ">
                        የአዲስ አበባ ከተማ አስተዳደር ደንብ ማስከበር ባለስልጣን
                    </h2>

                    <h3 data-lang
                        data-am="የብልጽግና ፓርቲ ዲጂታል ስርዓት — የአባልነት አስተዳደር"
                        data-en="Prosperity Party Digital System — Membership Management"
                        data-om="Sirna Dijitaalaa Paartii Badhaadhaa — Bulchiinsa Miseensummaa"
                        data-so="Nidaamka Dhijitaalka Xisbiga Barwaaqada — Maamulka Xubinnimada"
                        data-ti="ዲጂታል ስርዓት ብልጽግና ፓርቲ — ምምሕዳር ኣባልነት">
                        የብልጽግና ፓርቲ ዲጂታል ስርዓት — የአባልነት አስተዳደር
                    </h3>

                    {% with messages = get_flashed_messages() %}
                        {% if messages %}
                            {% for message in messages %}
                                <div class="flash-login">{{ message }}</div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}

                    <form method="POST" id="loginForm" autocomplete="off">

                        <div class="float-group">
                            <span class="input-icon">&#128100;</span>
                            <input type="text" name="username" id="loginUsername"
                                   placeholder=" " required>
                            <label for="loginUsername"
                                   data-lang
                                   data-am="የተጠቃሚ ስም"
                                   data-en="Username"
                                   data-om="Maqaa Fayyadamaa"
                                   data-so="Magaca isticmaalaha"
                                   data-ti="ስም ተጠቃሚ">
                                የተጠቃሚ ስም
                            </label>
                        </div>

                        <div class="float-group">
                            <span class="input-icon">&#128274;</span>
                            <input type="password" name="password" id="loginPassword"
                                   placeholder=" " required>
                            <label for="loginPassword"
                                   data-lang
                                   data-am="የይለፍ ቃል"
                                   data-en="Password"
                                   data-om="Jecha Darbii"
                                   data-so="Furaha sirta"
                                   data-ti="ናይ መእተዊ ቃል">
                                የይለፍ ቃል
                            </label>
                            <button type="button" class="pw-toggle" id="pwToggle">&#128065;</button>
                        </div>

                        <button type="submit" class="login-btn" id="loginBtn"
                                data-lang
                                data-am="ግባ"
                                data-en="LOGIN"
                                data-om="SEENI"
                                data-so="GAL"
                                data-ti="እቶ">
                            ግባ
                        </button>

                    </form>

                    <div class="login-lang">
                        <select id="languageSelector" onchange="changeLanguage(this.value)">
                            <option value="am" selected>አማርኛ</option>
                            <option value="om">Afaan Oromo</option>
                            <option value="en">English</option>
                            <option value="so">Soomaali</option>
                            <option value="ti">ትግርኛ</option>
                        </select>
                    </div>

                    <a href="{{ url_for('home') }}" class="back-home"
                       data-lang
                       data-am="&#8592; ወደ የህዝብ ገጽ ተመለስ"
                       data-en="&#8592; Back to Public Site"
                       data-om="&#8592; Fuula Ummataatti Deebi'i"
                       data-so="&#8592; Ku noqo Bogga Dadweynaha"
                       data-ti="&#8592; ናብ ገጽ ህዝቢ ተመለስ">
                        &#8592; ወደ የህዝብ ገጽ ተመለስ
                    </a>

                </div>
            </div>

            <div class="book-page right">
                <div class="notebook">

                    <div class="notebook-title"
                         data-lang
                         data-am="የብልጽግና ፓርቲ ራዕይ"
                         data-en="Prosperity Party Vision"
                         data-om="Mul'ata Paartii Badhaadhaa"
                         data-so="Aragtida Xisbiga Barwaaqada"
                         data-ti="ራእይ ብልጽግና ፓርቲ">
                        የብልጽግና ፓርቲ ራዕይ
                    </div>

                    <div class="notebook-subtitle"
                         data-lang
                         data-am="ራዕይ · ተልዕኮ · መርሆዎች"
                         data-en="Vision · Mission · Values"
                         data-om="Mul'ata · Ergama · Duudhaa"
                         data-so="Aragti · Hadaf · Qiyam"
                         data-ti="ራእይ · ተልእኾ · መርህ">
                        ራዕይ · ተልዕኮ · መርሆዎች
                    </div>

                    <div class="notebook-section">
                        <h4><span class="dot"></span>
                            <span data-lang data-am="ራዕይ" data-en="Vision" data-om="Mul'ata" data-so="Aragti" data-ti="ራእይ">ራዕይ</span>
                        </h4>
                        <ul>
                            <li data-lang
                                data-am="ብሔራዊ አንድነት፣ የኢኮኖሚ ብልጽግና፣ ዴሞክራሲ፣ የአካባቢ ጥበቃ እና አካታች አገልግሎት በማረጋገጥ ኢትዮጵያን ወደ ብልጽግና መምራት።"
                                data-en="Lead Ethiopia to prosperity via national unity, economic empowerment, democracy, environmental stewardship, and inclusive services."
                                data-om="Tokkummaa biyyaalessaa, cimina diinagdee, dimokiraasii, kunuunsa naannoo fi tajaajila hunda dabalataa karaan Itoophiyaa gara badhaadhummaatti geessuu."
                                data-so="Ku hoggaami Ethiopia barwaaqo iyada oo la marayo midnimada qaranka, awoodsiinta dhaqaalaha, dimoqraadiyadda, ilaalinta deegaanka, iyo adeegyada loo dhan yahay."
                                data-ti="ብሄራዊ ሓድነት፣ ቁጠባዊ ብልጽግና፣ ዴሞክራሲ፣ ምክትታል ከባቢን አካታች ኣገልግሎትን ብምርግጋጽ ኢትዮጵያ ናብ ብልጽግና ምምራሕ።">
                                ብሔራዊ አንድነት፣ የኢኮኖሚ ብልጽግና፣ ዴሞክራሲ፣ የአካባቢ ጥበቃ እና አካታች አገልግሎት በማረጋገጥ ኢትዮጵያን ወደ ብልጽግና መምራት።
                            </li>
                            <li data-lang
                                data-am="ብዝሃነት የሚከበርበት፣ ተስፋ፣ መረጋጋት እና የኢኮኖሚ ሽግግር ያለበት ብሔር መገንባት።"
                                data-en="Build a nation of hope, stability, and economic transformation where diversity is respected under a shared national identity."
                                data-om="Biyeen abdii, tasgabbii fi jijjiirama diinagdee qabu ijaaruu, bakka adda addummaan eenyummaa biyyaalessaa jalatti kabajamu."
                                data-so="Dhis qaran rajo, xasillooni, iyo isbeddel dhaqaale leh halkaas oo kala duwanaanshaha lagu ixtiraamo aqoonsi qaran oo la wadaago."
                                data-ti="ተስፋ፣ ምርግጋጽን ቁጠባዊ ምልውዋጥን ዘለዎ ህዝቢ ምህናጽ፣ ኣብ ትሕቲ ሓባራዊ ብሄራዊ ነነዌ ዝተፈላለየ ክኽበር።">
                                ብዝሃነት የሚከበርበት፣ ተስፋ፣ መረጋጋት እና የኢኮኖሚ ሽግግር ያለበት ብሔር መገንባት።
                            </li>
                        </ul>
                    </div>

                    <div class="notebook-section">
                        <h4><span class="dot"></span>
                            <span data-lang data-am="ተልዕኮ" data-en="Mission" data-om="Ergama" data-so="Hadaf" data-ti="ተልእኾ">ተልዕኮ</span>
                        </h4>
                        <ul>
                            <li data-lang
                                data-am="የህዝብን ሰላም፣ መረጋጋት እና ዴሞክራሲያዊ ስርዓት በማረጋገጥ የዜጎችን ህይወት ማሻሻል።"
                                data-en="Advance progress, economic growth, social justice, and cultural advancement to make Ethiopia a symbol of African prosperity."
                                data-om="Guddina, guddina diinagdee, haqa hawaasummaa fi guddina aadaa dabalatee Itoophiyaa mallattoo badhaadhummaa Afrikaatti taasisuuf."
                                data-so="Horumarka, koritaanka dhaqaalaha, cadaaladda bulshada, iyo horumarka dhaqanka si Ethiopia calaamad uga noqoto barwaaqada Afrika."
                                data-ti="ምዕባለ፣ ቁጠባዊ ዕብየት፣ ማሕበራዊ ፍትሕን ባህላዊ ዕብየትን ብምምራሕ ኢትዮጵያ ምልክት ብልጽግና ኣፍሪቃ ክትከውን።">
                                የህዝብን ሰላም፣ መረጋጋት እና ዴሞክራሲያዊ ስርዓት በማረጋገጥ የዜጎችን ህይወት ማሻሻል።
                            </li>
                            <li data-lang
                                data-am="ሁሉም ዜጋ ተመሳሳይ መብት፣ እድል እና የሀገር ልማት ጥቅም የሚያገኝበት አካታች ስርዓት መፍጠር።"
                                data-en="Create an inclusive system where every citizen enjoys equal rights, opportunities, and benefits from national development regardless of background."
                                data-om="Sirna hunda dabalataa uumuu, bakka bu'aan hundi mirga walqixaa, carraa fi faayidaa guddina biyyaalessaa irraa argatu."
                                data-so="Abuur nidaam loo dhan yahay oo qof kasta oo muwaadin ah uu ku raaxaysto xuquuq siman, fursado, iyo faa'iidooyinka horumarka qaranka."
                                data-ti="ኩሉ ዜጋ ተመሳሳሊ መሰል፣ ዕድልን ካብ ልማት ሃገር ጥቕሚን ዘረክብ አካታች ስርዓት ምፍጣር።">
                                ሁሉም ዜጋ ተመሳሳይ መብት፣ እድል እና የሀገር ልማት ጥቅም የሚያገኝበት አካታች ስርዓት መፍጠር።
                            </li>
                        </ul>
                    </div>

                    <div class="notebook-section">
                        <h4><span class="dot"></span>
                            <span data-lang data-am="መርሆዎች" data-en="Core Values" data-om="Duudhaa" data-so="Qiyamka" data-ti="መርህታት">መርሆዎች</span>
                        </h4>
                        <ul>
                            <li data-lang
                                data-am="በተለያዩ ብሔር ብሔረሰቦች መካከል አንድነት፣ ትብብር፣ የጋራ መከባበር እና ንቁ የዜጎች ተሳትፎን ማጠናከር።"
                                data-en="Strengthen unity, cooperation, mutual respect, and active citizen participation among diverse ethnic groups."
                                data-om="Tokkummaa, walta'iinsa, kabaja walii fi hirmaannaa lammiilee sochii gidduu gareewwan sabaa adda addaa cimsuu."
                                data-so="Xoojinta midnimada, iskaashiga, ixtiraamka labada dhinac, iyo ka-qaybgalka firfircoon ee muwaadiniinta ee kooxaha qawmiyadaha kala duwan."
                                data-ti="ኣብ መንጎ ዝተፈላለዩ ብሄራት ሓድነት፣ ምትሕብባር፣ ሓባራዊ ኣኽብሮትን ንጡፍ ተሳትፎ ዜጋታትን ምምሕያሽ።">
                                በተለያዩ ብሔር ብሔረሰቦች መካከል አንድነት፣ ትብብር፣ የጋራ መከባበር እና ንቁ የዜጎች ተሳትፎን ማጠናከር።
                            </li>
                            <li data-lang
                                data-am="ግልጽነት፣ ተጠያቂነት እና የህግ የበላይነትን ጨምሮ የመልካም አስተዳደር መርሆዎችን ማክበር።"
                                data-en="Uphold good governance principles including transparency, accountability, and the rule of law."
                                data-om="Duudhaa bulchiinsa gaarii kan akka iftoomina, itti gaafatamummaa fi ol'aantummaa seeraa kabajuu."
                                data-so="Ilaali mabaadi'da maamul wanaagga oo ay ka mid yihiin hufnaanta, xisaabtanka, iyo xukunka sharciga."
                                data-ti="ግልጽነት፣ ተጠያቂነትን ልዕልና ሕግን ዝሓቖፈ መርሆታት ጽቡቕ ኣስተዳደር ምኽባር።">
                                ግልጽነት፣ ተጠያቂነት እና የህግ የበላይነትን ጨምሮ የመልካም አስተዳደር መርሆዎችን ማክበር።
                            </li>
                        </ul>
                    </div>

                    <div class="notebook-lang">
                        <button type="button" onclick="changeLanguage('am');highlightLang(this)" class="active">አማ</button>
                        <button type="button" onclick="changeLanguage('om');highlightLang(this)">OM</button>
                        <button type="button" onclick="changeLanguage('en');highlightLang(this)">EN</button>
                        <button type="button" onclick="changeLanguage('so');highlightLang(this)">SO</button>
                        <button type="button" onclick="changeLanguage('ti');highlightLang(this)">ትግ</button>
                    </div>

                </div>
            </div>

        </div>

    </div>

</div>

<script>
function changeLanguage(value) {
    localStorage.setItem("selectedLanguage", value);
    document.documentElement.lang = value;
    document.querySelectorAll("[data-lang]").forEach(function(item) {
        var text = item.getAttribute("data-" + value);
        if (text) item.innerHTML = text;
    });
    var selector = document.getElementById("languageSelector");
    if (selector) selector.value = value;
}

function highlightLang(btn) {
    document.querySelectorAll(".notebook-lang button").forEach(function(b) {
        b.classList.remove("active");
    });
    if (btn) btn.classList.add("active");
}

document.addEventListener("DOMContentLoaded", function() {

    var language = localStorage.getItem("selectedLanguage") || "am";
    var selector = document.getElementById("languageSelector");
    if (selector) selector.value = language;
    changeLanguage(language);

    var langMap = { am: 0, om: 1, en: 2, so: 3, ti: 4 };
    var btns = document.querySelectorAll(".notebook-lang button");
    if (btns[langMap[language]]) highlightLang(btns[langMap[language]]);

    var unlockButton = document.getElementById("unlockButton");
    var loginDoor = document.getElementById("loginDoor");
    var bookScene = document.getElementById("bookScene");
    var lockIcon = document.getElementById("lockIcon");
    var loginUsername = document.getElementById("loginUsername");

    if (unlockButton && loginDoor && bookScene) {
        unlockButton.addEventListener("click", function() {
            unlockButton.disabled = true;
            lockIcon.textContent = "🔓";
            loginDoor.classList.add("unlocking");

            setTimeout(function() {
                loginDoor.style.display = "none";
                bookScene.classList.add("visible");

                setTimeout(function() {
                    if (loginUsername) loginUsername.focus();
                }, 900);
            }, 420);
        });
    }

    var pwToggle = document.getElementById("pwToggle");
    var pwInput = document.getElementById("loginPassword");

    if (pwToggle && pwInput) {
        pwToggle.addEventListener("click", function() {
            var isHidden = pwInput.type === "password";
            pwInput.type = isHidden ? "text" : "password";
            pwToggle.innerHTML = isHidden ? "&#128064;" : "&#128065;";
        });
    }

    var loginForm = document.getElementById("loginForm");
    var loginBtn = document.getElementById("loginBtn");

    if (loginForm && loginBtn) {
        loginForm.addEventListener("submit", function() {
            loginBtn.classList.add("loading");
            loginBtn.disabled = true;

            var lang = localStorage.getItem("selectedLanguage") || "am";
            var loadingText = {
                am: "እባክዎ ይጠብቁ...",
                en: "PLEASE WAIT...",
                om: "MAALOO EEGAA...",
                so: "FADLAN SUG...",
                ti: "በጃኹም ተጸበዩ..."
            };

            loginBtn.innerHTML = loadingText[lang] || loadingText.am;
        });
    }

    var flash = document.querySelector(".flash-login");
    if (flash) {
        if (loginDoor) loginDoor.style.display = "none";
        if (bookScene) bookScene.classList.add("visible");

        var card = document.getElementById("loginCard");
        if (card) {
            card.classList.add("shake");
            setTimeout(function() { card.classList.remove("shake"); }, 700);
        }
    }
});
</script>

</body>
</html>
"""


# ============================================================
# ID CARD HTML
# ============================================================

ID_CARD_HTML = """
<!DOCTYPE html>
<html lang="am">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ID Card — {{ member.fullname }}</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', 'Noto Sans Ethiopic', Arial, sans-serif; background: #e9eef3; padding: 30px 15px; display: flex; flex-direction: column; align-items: center; gap: 22px; }
.toolbar { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }
.toolbar .btn { padding: 10px 20px; border: 0; border-radius: 10px; font-weight: 700; font-size: 13px; cursor: pointer; text-decoration: none; color: white; transition: transform .2s, box-shadow .2s; }
.toolbar .btn:hover { transform: translateY(-2px); box-shadow: 0 8px 18px rgba(0,0,0,.18); }
.btn-green { background: linear-gradient(135deg, #087f5b, #12b886); }
.btn-blue { background: linear-gradient(135deg, #1864ab, #339af0); }
.btn-gray { background: #495057; }
.not-approved-banner { background: linear-gradient(135deg, #fff3bf, #ffe8a3); color: #8d6b00; padding: 16px 24px; border-radius: 12px; font-weight: 700; font-size: 14px; border: 2px dashed #e6b800; text-align: center; max-width: 700px; }
.not-approved-banner .big { display: block; font-size: 17px; margin-bottom: 6px; color: #7a5b00; }
.id-card-set { display: flex; gap: 24px; flex-wrap: wrap; justify-content: center; align-items: flex-start; }
.id-card { position: relative; width: 420px; height: 265px; border-radius: 18px; overflow: hidden; color: white; box-shadow: 0 18px 45px rgba(0,0,0,.28); isolation: isolate; }
.id-card.front { background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 55%, #064e3b 100%); }
.id-card.back { background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); color: #172033; }
.watermark { position: absolute; inset: -40%; z-index: 0; pointer-events: none; background-image: url('{{ logo }}'); background-repeat: repeat; background-size: 70px 70px; opacity: 0.10; transform: rotate(-28deg) scale(1.3); mix-blend-mode: screen; }
.id-card.back .watermark { opacity: 0.08; mix-blend-mode: multiply; background-size: 55px 55px; transform: rotate(-22deg) scale(1.35); }
.watermark-center { position: absolute; top: 50%; left: 50%; width: 220px; height: 220px; transform: translate(-50%, -50%); opacity: 0.07; z-index: 0; pointer-events: none; }
.id-card .layer { position: relative; z-index: 2; height: 100%; padding: 14px 16px; display: flex; flex-direction: column; }
.id-header { display: flex; align-items: center; gap: 10px; border-bottom: 1.5px solid rgba(255,255,255,.35); padding-bottom: 8px; margin-bottom: 8px; }
.id-card.back .id-header { border-bottom-color: rgba(0,0,0,.15); }
.id-header-logo { width: 34px; height: 34px; object-fit: contain; background: white; border-radius: 50%; padding: 3px; flex-shrink: 0; }
.id-header-text { flex: 1; line-height: 1.2; }
.id-header-title { font-size: 9.5px; font-weight: 800; letter-spacing: .3px; text-transform: uppercase; }
.id-header-sub { font-size: 7.5px; opacity: .85; font-weight: 600; margin-top: 1px; }
.id-body { display: flex; gap: 12px; flex: 1; }
.id-photo-box { position: relative; width: 88px; height: 110px; flex-shrink: 0; border-radius: 10px; overflow: visible; background: #fff; border: 2.5px solid rgba(255,255,255,.85); box-shadow: 0 5px 14px rgba(0,0,0,.3); }
.id-photo-box img.member-photo-img { width: 100%; height: 100%; object-fit: cover; display: block; border-radius: 8px; }
.id-photo-stamp { position: absolute; bottom: -10px; right: -10px; width: 34px; height: 34px; background: white; border-radius: 50%; padding: 3px; box-shadow: 0 3px 8px rgba(0,0,0,.35); border: 2px solid var(--primary); z-index: 3; }
.id-info { flex: 1; display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.id-name { font-size: 15px; font-weight: 900; line-height: 1.15; margin-bottom: 4px; text-shadow: 0 2px 4px rgba(0,0,0,.25); }
.id-field { display: flex; gap: 5px; font-size: 9.5px; line-height: 1.35; }
.id-field .lbl { font-weight: 800; opacity: .85; min-width: 52px; flex-shrink: 0; }
.id-field .val { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.id-footer-front { display: flex; align-items: flex-end; justify-content: space-between; margin-top: 6px; padding-top: 6px; border-top: 1.5px solid rgba(255,255,255,.35); gap: 8px; }
.id-code { background: rgba(255,255,255,.2); padding: 4px 9px; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 10.5px; font-weight: 800; letter-spacing: .8px; border: 1px solid rgba(255,255,255,.35); white-space: nowrap; }
.id-signature { text-align: center; font-size: 8px; opacity: .95; display: flex; flex-direction: column; align-items: center; }
.signature-box { height: 34px; min-width: 90px; max-width: 120px; display: flex; align-items: center; justify-content: center; padding: 2px 6px; background: rgba(255,255,255,.9); border-radius: 6px; margin-bottom: 2px; }
.signature-box img { max-height: 100%; max-width: 100%; object-fit: contain; display: block; }
.signature-line { width: 100px; border-bottom: 1px solid rgba(255,255,255,.85); margin-bottom: 2px; }
.back-body { display: flex; gap: 14px; flex: 1; }
.back-terms { flex: 1; font-size: 8.5px; line-height: 1.55; color: #334155; }
.back-terms h4 { font-size: 9.5px; font-weight: 900; color: var(--primary); margin-bottom: 4px; text-transform: uppercase; }
.back-terms ul { list-style: none; padding-left: 0; }
.back-terms li { padding-left: 10px; position: relative; margin-bottom: 3px; }
.back-terms li::before { content: "▪"; position: absolute; left: 0; color: var(--secondary); font-weight: 900; }
.back-qr { width: 96px; flex-shrink: 0; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.back-qr img { width: 92px; height: 92px; border-radius: 6px; background: white; padding: 3px; border: 1.5px solid var(--primary); }
.back-qr .qr-label { font-size: 7.5px; font-weight: 800; color: #475569; text-align: center; }
.back-footer { display: flex; justify-content: space-between; font-size: 7.5px; color: #64748b; padding-top: 5px; border-top: 1.5px dashed #cbd5e1; margin-top: 5px; font-weight: 600; }
.holo-strip { position: absolute; top: 0; right: 30px; width: 42px; height: 100%; background: linear-gradient(120deg, rgba(255,255,255,0) 0%, rgba(255,255,255,.28) 40%, rgba(255,255,255,.55) 50%, rgba(255,255,255,.28) 60%, rgba(255,255,255,0) 100%); z-index: 3; pointer-events: none; animation: holoShift 4s ease-in-out infinite; }
@keyframes holoShift { 0%, 100% { opacity: .35; transform: translateX(0); } 50% { opacity: .75; transform: translateX(-6px); } }
@media (max-width: 900px) {
    .id-card { width: 92vw; max-width: 420px; height: auto; min-height: 265px; }
    .id-card-set { flex-direction: column; align-items: center; }
}
@media print {
    body { background: white; padding: 0; }
    .toolbar, .not-approved-banner { display: none; }
    .id-card { box-shadow: none; page-break-inside: avoid; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
</style>
</head>
<body>

<div class="toolbar">
    {% if member.status == 'Approved' %}
        <button class="btn btn-green" onclick="window.print()">🖨️ ፕሪንት / Print</button>
        <a class="btn btn-blue" href="{{ url_for('member_profile', member_id=member.id) }}">👤 መገለጫ / Profile</a>
    {% else %}
        <a class="btn btn-blue" href="{{ url_for('member_profile', member_id=member.id) }}">👤 መገለጫ / Profile</a>
        <a class="btn btn-green" href="{{ url_for('approve_member', member_id=member.id) }}">✅ Approve & Generate Card</a>
    {% endif %}
    <a class="btn btn-gray" href="{{ url_for('members') }}">← ዝርዝር / Back</a>
</div>

{% if member.status != 'Approved' %}
<div class="not-approved-banner">
    <span class="big">⚠️ የመታወቂያ ካርድ ገና አልተፈቀደም</span>
    This member is <strong>{{ member.status }}</strong>. The ID card will only be fully active after approval.
</div>
{% endif %}

<div class="id-card-set">
    <div class="id-card front">
        <div class="watermark"></div>
        <img class="watermark-center" src="{{ logo }}" alt="">
        <div class="holo-strip"></div>
        <div class="layer">
            <div class="id-header">
                <img class="id-header-logo" src="{{ logo }}" alt="Logo">
                <div class="id-header-text">
                    <div class="id-header-title">{{ system_title }}</div>
                    <div class="id-header-sub">Membership Identity Card · የአባልነት መታወቂያ</div>
                </div>
            </div>

            <div class="id-body">
                <div class="id-photo-box">
                    <img class="member-photo-img" src="{{ photo_url }}" alt="{{ member.fullname }}">
                    <img class="id-photo-stamp" src="{{ logo }}" alt="stamp">
                </div>

                <div class="id-info">
                    <div class="id-name">{{ member.fullname }}</div>
                    <div class="id-field"><span class="lbl">ID No:</span><span class="val">{{ member.member_code or '—' }}</span></div>
                    <div class="id-field"><span class="lbl">Phone:</span><span class="val">{{ member.phone or '—' }}</span></div>
                    <div class="id-field"><span class="lbl">Sub-City:</span><span class="val">{{ member.residential_subcity or '—' }}</span></div>
                    <div class="id-field"><span class="lbl">Woreda:</span><span class="val">{{ member.woreda or '—' }}</span></div>
                    <div class="id-field"><span class="lbl">Ethnicity:</span><span class="val">{{ member.ethnicity or '—' }}</span></div>
                    <div class="id-field"><span class="lbl">Blood:</span><span class="val">{{ member.blood_group or '—' }}</span></div>
                </div>
            </div>

            <div class="id-footer-front">
                <div class="id-code">{{ member.member_code or 'AACCEA-XXXXX' }}</div>
                <div class="id-signature">
                    <div class="signature-box">
                        {% if approver_signature_url %}
                            <img src="{{ approver_signature_url }}" alt="Approver Signature">
                        {% elif signature_url %}
                            <img src="{{ signature_url }}" alt="Signature">
                        {% else %}
                            <span style="font-size:8px;color:#94a3b8;">No signature</span>
                        {% endif %}
                    </div>
                    <div class="signature-line"></div>
                    {% if member.approved_by_name %}<div style="font-weight:800;">{{ member.approved_by_name }}</div>{% endif %}
                    Authorized Signature
                </div>
            </div>
        </div>
    </div>

    <div class="id-card back">
        <div class="watermark"></div>
        <img class="watermark-center" src="{{ logo }}" alt="">

        <div class="layer">
            <div class="id-header">
                <img class="id-header-logo" src="{{ logo }}" alt="Logo">
                <div class="id-header-text">
                    <div class="id-header-title" style="color:#075e54;">Terms &amp; Conditions</div>
                    <div class="id-header-sub">የአጠቃቀም መመሪያዎች · {{ member.member_code or '' }}</div>
                </div>
            </div>

            <div class="back-body">
                <div class="back-terms">
                    <h4>Rules of Use</h4>
                    <ul>
                        <li>This card is the property of the Authority.</li>
                        <li>Non-transferable. Present upon request.</li>
                        <li>Report loss immediately to the office.</li>
                        <li>Return upon termination of membership.</li>
                        <li>Valid only with official stamp &amp; signature.</li>
                        <li>Issued: <strong>{{ issued_str }}</strong></li>
                        <li>Expires: <strong>{{ expiry_str }}</strong></li>
                    </ul>
                </div>

                <div class="back-qr">
                    <img src="{{ qr_url }}" alt="QR Code">
                    <div class="qr-label">SCAN TO VERIFY</div>
                </div>
            </div>

            <div class="back-footer">
                <span>📞 Call On: 0115621721 or 9995</span>
                <span>✉️ info@aaccea.gov.et</span>
                <span>🌐 www.aaccea.gov.et</span>
            </div>
        </div>
    </div>
</div>

<script>
document.documentElement.style.setProperty('--primary', '{{ primary_color }}');
document.documentElement.style.setProperty('--secondary', '{{ secondary_color }}');
</script>

</body>
</html>
"""


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def home():
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM posts WHERE visibility = 'public' ORDER BY id DESC LIMIT 30")
    posts = cursor.fetchall()
    for p in posts:
        if p.get("created_at"):
            try:
                p["created_at"] = p["created_at"].strftime("%b %d, %Y")
            except:
                pass
    ticker_posts = posts[:10]
    cursor.close()
    connection.close()
    return render_template_string(HOME_HTML, logo=PARTY_LOGO, posts=posts, ticker_posts=ticker_posts)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("login"))
        connection = get_connection(MYSQL_DATABASE)
        if connection is None:
            return "MySQL connection failed."
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        cursor.close()
        connection.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["fullname"] = user["fullname"]
            session["role"] = user["role"]
            session["organization_id"] = user["organization_id"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.")
    return render_template_string(LOGIN_HTML, logo=PARTY_LOGO)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor()
    if session.get("role") == "general_admin":
        cursor.execute("SELECT COUNT(*) FROM members")
        total_members = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM members WHERE status='Approved'")
        approved = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM members WHERE status='Pending'")
        pending = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM members WHERE status='Rejected'")
        rejected = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM organizations")
        accounts = cursor.fetchone()[0]
    else:
        oid = session.get("organization_id")
        cursor.execute("SELECT COUNT(*) FROM members WHERE organization_id=%s", (oid,))
        total_members = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM members WHERE organization_id=%s AND status='Approved'", (oid,))
        approved = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM members WHERE organization_id=%s AND status='Pending'", (oid,))
        pending = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM members WHERE organization_id=%s AND status='Rejected'", (oid,))
        rejected = cursor.fetchone()[0]
        accounts = 1
    cursor.execute("SELECT COUNT(*) FROM posts")
    total_posts = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM approvers")
    total_approvers = cursor.fetchone()[0]
    cursor.close()
    connection.close()

    content = """
    <div class="card">
        <h2>ዳሽቦርድ</h2>
        <p>እንኳን ደህና መጡ, <strong>{{ session.get("fullname") }}</strong></p>
    </div>

    <div class="dashboard-grid">
        <div class="stat-card blue"><div>ጠቅላላ አባላት</div><div class="stat-number">{{ total_members }}</div></div>
        <div class="stat-card green"><div>የጸደቀ</div><div class="stat-number">{{ approved }}</div></div>
        <div class="stat-card orange"><div>በመጠባበቅ ላይ</div><div class="stat-number">{{ pending }}</div></div>
        <div class="stat-card red"><div>ውድቅ የተደረገ</div><div class="stat-number">{{ rejected }}</div></div>
        <div class="stat-card purple"><div>ልጥፎች</div><div class="stat-number">{{ total_posts }}</div></div>
        <div class="stat-card green"><div>አጽዳቂዎች</div><div class="stat-number">{{ total_approvers }}</div></div>
    </div>

    <br>

    <div class="card">
        <h3>ፈጣን እርምጃዎች</h3>
        <a href="{{ url_for('new_post') }}" class="btn btn-primary">&#128240; ልጥፍ ፍጠር</a>
        <a href="{{ url_for('manage_posts') }}" class="btn btn-blue">&#128203; ልጥፎችን አስተዳድር</a>
        <a href="{{ url_for('new_member') }}" class="btn btn-orange">አባል ይመዝግቡ</a>
        <a href="{{ url_for('new_approver') }}" class="btn btn-green">+ አጽዳቂ ጨምር</a>
        <a href="{{ url_for('home') }}" class="btn btn-gray">&#127757; የህዝብ ገጽ ተመልከት</a>
    </div>
    """
    return page("Dashboard", render_template_string(
        content,
        total_members=total_members, approved=approved, pending=pending,
        rejected=rejected, accounts=accounts, total_posts=total_posts,
        total_approvers=total_approvers
    ))


# ============================================================
# APPROVERS
# ============================================================

@app.route("/approvers")
@login_required
def approvers():
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM approvers ORDER BY id DESC")
    rows = cursor.fetchall()
    cursor.close()
    connection.close()

    content = """
    <div class="card">
        <h2>አጽዳቂዎች (Approvers)</h2>
        <a href="{{ url_for('new_approver') }}" class="btn btn-primary">+ አዲስ አጽዳቂ</a>
        <br><br>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>መለያ</th><th>Signature</th><th>Approver Name</th>
                        <th>Full Name</th><th>Position</th><th>Status</th><th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                {% for a in rows %}
                    <tr>
                        <td>{{ a.id }}</td>
                        <td>
                            {% if a.signature_image %}
                                <img src="{{ url_for('uploaded_file', filename=a.signature_image) }}" style="max-width:120px;max-height:50px;object-fit:contain;border:2px solid #e2e8f0;border-radius:6px;background:white;padding:3px;">
                            {% else %}
                                <span style="color:#c92a2a;font-size:12px;">No signature</span>
                            {% endif %}
                        </td>
                        <td><strong>{{ a.approver_name }}</strong></td>
                        <td>{{ a.full_name }}</td>
                        <td>{{ a.position or '—' }}</td>
                        <td>
                            {% if a.is_active %}<span class="badge badge-approved">✓ Active</span>
                            {% else %}<span class="badge badge-rejected">✗ Inactive</span>{% endif %}
                        </td>
                        <td>
                            <a href="{{ url_for('edit_approver', approver_id=a.id) }}" class="btn btn-orange" style="font-size:11.5px;">✏ Edit</a>
                            <a href="{{ url_for('delete_approver', approver_id=a.id) }}" class="btn btn-red" style="font-size:11.5px;" onclick="return confirmDelete()">🗑 Delete</a>
                        </td>
                    </tr>
                {% else %}
                    <tr><td colspan="7" style="text-align:center;padding:30px;">
                        <div style="font-size:50px;opacity:.3;">✅</div>
                        <p style="margin-top:10px;color:#64748b;">No approvers yet. Click <strong>+ አዲስ አጽዳቂ</strong> to add one.</p>
                    </td></tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    """
    return page("Approvers", render_template_string(content, rows=rows))


@app.route("/approver/new", methods=["GET", "POST"])
@login_required
def new_approver():
    if request.method == "POST":
        approver_name = request.form.get("approver_name", "").strip()
        full_name = request.form.get("full_name", "").strip()
        position = request.form.get("position", "").strip()
        is_active = 1 if request.form.get("is_active") == "1" else 0

        if not approver_name or not full_name:
            flash("Approver name and full name are required.")
            return redirect(url_for("new_approver"))

        signature_file = request.files.get("signature_image")
        signature_name = None
        if signature_file and signature_file.filename:
            extension = signature_file.filename.rsplit(".", 1)[-1].lower()
            if extension in ALLOWED_EXTENSIONS:
                signature_name = "approver_sig_" + str(uuid.uuid4()) + "." + extension
                signature_file.save(os.path.join(UPLOAD_FOLDER, signature_name))

        connection = get_connection(MYSQL_DATABASE)
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO approvers (approver_name, full_name, position, signature_image, is_active) VALUES (%s,%s,%s,%s,%s)",
            (approver_name, full_name, position, signature_name, is_active)
        )
        connection.commit()
        cursor.close()
        connection.close()
        flash("✅ Approver created successfully.")
        return redirect(url_for("approvers"))

    content = """
    <div class="card">
        <h2>አዲስ አጽዳቂ</h2>
        <form method="POST" enctype="multipart/form-data">
            <div class="form-grid">
                <div class="form-group"><label>Approver Name (short) *</label><input name="approver_name" required maxlength="255"></div>
                <div class="form-group"><label>Full Name *</label><input name="full_name" required maxlength="255"></div>
                <div class="form-group"><label>Position</label><input name="position" maxlength="255"></div>
                <div class="form-group"><label>Active</label>
                    <select name="is_active">
                        <option value="1" selected>Yes — Active</option>
                        <option value="0">No — Inactive</option>
                    </select>
                </div>
                <div class="form-group" style="grid-column: span 2;">
                    <label>📸 Authorized Signature Image</label>
                    <input type="file" name="signature_image" accept="image/*" id="sigPhoto">
                    <div id="sigPreviewWrap" style="display:none;margin-top:14px;">
                        <div style="background:white;border:2px dashed #087f5b;border-radius:10px;padding:12px;display:inline-block;">
                            <img id="sigPreview" style="max-height:80px;max-width:250px;object-fit:contain;display:block;">
                        </div>
                    </div>
                </div>
            </div>
            <br>
            <button type="submit" class="btn btn-primary">💾 አጽዳቂ ፍጠር</button>
            <a href="{{ url_for('approvers') }}" class="btn btn-gray">ሰርዝ</a>
        </form>
    </div>
    <script>
    document.getElementById("sigPhoto").addEventListener("change", function(e) {
        var file = e.target.files[0];
        if (!file) return;
        var reader = new FileReader();
        reader.onload = function(ev) {
            document.getElementById("sigPreview").src = ev.target.result;
            document.getElementById("sigPreviewWrap").style.display = "block";
        };
        reader.readAsDataURL(file);
    });
    </script>
    """
    return page("New Approver", render_template_string(content))


@app.route("/approver/<int:approver_id>/edit", methods=["GET", "POST"])
@login_required
def edit_approver(approver_id):
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM approvers WHERE id=%s", (approver_id,))
    approver = cursor.fetchone()
    cursor.close()
    connection.close()

    if not approver:
        flash("Approver not found.")
        return redirect(url_for("approvers"))

    if request.method == "POST":
        approver_name = request.form.get("approver_name", "").strip()
        full_name = request.form.get("full_name", "").strip()
        position = request.form.get("position", "").strip()
        is_active = 1 if request.form.get("is_active") == "1" else 0

        signature_file = request.files.get("signature_image")
        signature_name = approver.get("signature_image")

        if signature_file and signature_file.filename:
            extension = signature_file.filename.rsplit(".", 1)[-1].lower()
            if extension in ALLOWED_EXTENSIONS:
                signature_name = "approver_sig_" + str(uuid.uuid4()) + "." + extension
                signature_file.save(os.path.join(UPLOAD_FOLDER, signature_name))

        connection = get_connection(MYSQL_DATABASE)
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE approvers SET approver_name=%s, full_name=%s, position=%s, signature_image=%s, is_active=%s WHERE id=%s",
            (approver_name, full_name, position, signature_name, is_active, approver_id)
        )
        connection.commit()
        cursor.close()
        connection.close()
        flash("✅ Approver updated.")
        return redirect(url_for("approvers"))

    content = """
    <div class="card">
        <h2>✏ Edit Approver</h2>
        <form method="POST" enctype="multipart/form-data">
            <div class="form-grid">
                <div class="form-group"><label>Approver Name *</label><input name="approver_name" value="{{ approver.approver_name or '' }}" required></div>
                <div class="form-group"><label>Full Name *</label><input name="full_name" value="{{ approver.full_name or '' }}" required></div>
                <div class="form-group"><label>Position</label><input name="position" value="{{ approver.position or '' }}"></div>
                <div class="form-group"><label>Active</label>
                    <select name="is_active">
                        <option value="1" {% if approver.is_active %}selected{% endif %}>Yes — Active</option>
                        <option value="0" {% if not approver.is_active %}selected{% endif %}>No — Inactive</option>
                    </select>
                </div>
                <div class="form-group" style="grid-column: span 2;">
                    <label>📸 Replace Signature (optional)</label>
                    <input type="file" name="signature_image" accept="image/*">
                    {% if approver.signature_image %}
                    <div style="margin-top:10px;">
                        <p style="font-size:12px;color:#64748b;">Current signature:</p>
                        <img src="{{ url_for('uploaded_file', filename=approver.signature_image) }}" style="max-height:70px;max-width:230px;border:2px solid #087f5b;border-radius:8px;background:white;padding:4px;margin-top:6px;">
                    </div>
                    {% endif %}
                </div>
            </div>
            <br>
            <button type="submit" class="btn btn-primary">💾 Update</button>
            <a href="{{ url_for('approvers') }}" class="btn btn-gray">Cancel</a>
        </form>
    </div>
    """
    return page("Edit Approver", render_template_string(content, approver=approver))


@app.route("/approver/<int:approver_id>/delete")
@login_required
def delete_approver(approver_id):
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor()
    cursor.execute("SELECT signature_image FROM approvers WHERE id=%s", (approver_id,))
    row = cursor.fetchone()
    if row and row[0]:
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, row[0]))
        except:
            pass
    cursor.execute("DELETE FROM approvers WHERE id=%s", (approver_id,))
    connection.commit()
    cursor.close()
    connection.close()
    flash("Approver deleted.")
    return redirect(url_for("approvers"))


# ============================================================
# MANAGE POSTS
# ============================================================

@app.route("/posts")
@admin_required
def manage_posts():
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM posts ORDER BY id DESC")
    rows = cursor.fetchall()
    for p in rows:
        if p.get("created_at"):
            try:
                p["created_at"] = p["created_at"].strftime("%b %d, %Y %H:%M")
            except:
                pass
    cursor.close()
    connection.close()

    content = """
    <div class="card">
        <h2>ልጥፎችን አስተዳድር</h2>
        <a href="{{ url_for('new_post') }}" class="btn btn-primary">+ ልጥፍ ፍጠር</a>
        <a href="{{ url_for('home') }}" class="btn btn-blue">&#127757; የህዝብ ገጽ ተመልከት</a>
        <br><br>

        <div class="post-admin-grid">
            {% for post in rows %}
            <div class="post-admin-card">
                {% if post.photo and post.photo.startswith('http') %}
                    <img src="{{ post.photo }}" alt="{{ post.title }}">
                {% elif post.photo %}
                    <img src="{{ url_for('uploaded_file', filename=post.photo) }}" alt="{{ post.title }}">
                {% else %}
                    <img src=\"""" + FALLBACK_IMAGE + """\" alt="{{ post.title }}">
                {% endif %}
                <div class="post-admin-body">
                    <div style="font-size:15px;font-weight:800;color:#075e54;margin-bottom:6px;">{{ post.title }}</div>
                    <div style="font-size:12.5px;color:#64748b;margin-bottom:12px;">{{ post.content or '' }}</div>
                    <a href="{{ url_for('delete_post', post_id=post.id) }}" class="btn btn-red" onclick="return confirmDelete()">አጥፋ</a>
                </div>
            </div>
            {% else %}
            <div style="grid-column:1/-1;text-align:center;padding:40px;">እስካሁን ልጥፍ የለም</div>
            {% endfor %}
        </div>
    </div>
    """
    return page("Manage Posts", render_template_string(content, rows=rows))


@app.route("/post/new", methods=["GET", "POST"])
@admin_required
def new_post():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "News").strip()
        content_text = request.form.get("content", "").strip()
        visibility = request.form.get("visibility", "public").strip()

        if not title:
            flash("Title is required.")
            return redirect(url_for("new_post"))

        photo = request.files.get("photo")
        photo_name = None
        if photo and photo.filename:
            extension = photo.filename.rsplit(".", 1)[-1].lower()
            if extension in ALLOWED_EXTENSIONS:
                photo_name = str(uuid.uuid4()) + "." + extension
                photo.save(os.path.join(UPLOAD_FOLDER, photo_name))

        author = session.get("fullname") or "Admin"
        connection = get_connection(MYSQL_DATABASE)
        cursor = connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO posts (title, category, content, photo, visibility, author) VALUES (%s,%s,%s,%s,%s,%s)",
                (title, category, content_text, photo_name, visibility, author)
            )
            connection.commit()
            flash("Post published successfully.")
            return redirect(url_for("manage_posts"))
        except Error as e:
            connection.rollback()
            flash("Database error: " + str(e))
        finally:
            cursor.close()
            connection.close()

    content = """
    <div class="card">
        <h2>አዲስ ልጥፍ ፍጠር</h2>
        <form method="POST" enctype="multipart/form-data">
            <div class="form-grid">
                <div class="form-group" style="grid-column: span 2;">
                    <label>አርዕስት *</label>
                    <input name="title" required maxlength="255">
                </div>
                <div class="form-group">
                    <label>ምድብ</label>
                    <select name="category">
                        <option value="News">News</option>
                        <option value="Announcement">Announcement</option>
                        <option value="Event">Event</option>
                        <option value="Internal">Internal</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>ታይነት</label>
                    <select name="visibility">
                        <option value="public">ለህዝብ</option>
                        <option value="internal">የውስጥ</option>
                    </select>
                </div>
                <div class="form-group" style="grid-column: span 2;">
                    <label>ይዘት</label>
                    <textarea name="content" rows="6"></textarea>
                </div>
                <div class="form-group" style="grid-column: span 2;">
                    <label>ፎቶ (አማራጭ)</label>
                    <input type="file" name="photo" accept="image/*">
                </div>
            </div>
            <br>
            <button type="submit" class="btn btn-primary">📤 ልጥፍ አትም</button>
            <a href="{{ url_for('manage_posts') }}" class="btn btn-gray">ሰርዝ</a>
        </form>
    </div>
    """
    return page("New Post", render_template_string(content))


@app.route("/post/<int:post_id>/delete")
@admin_required
def delete_post(post_id):
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor()
    cursor.execute("SELECT photo FROM posts WHERE id=%s", (post_id,))
    row = cursor.fetchone()
    if row and row[0] and not row[0].startswith("http"):
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, row[0]))
        except:
            pass
    cursor.execute("DELETE FROM posts WHERE id=%s", (post_id,))
    connection.commit()
    cursor.close()
    connection.close()
    flash("Post deleted successfully.")
    return redirect(url_for("manage_posts"))


# ============================================================
# MEMBER CREATE
# ============================================================

@app.route("/member/new", methods=["GET", "POST"])
@login_required
def new_member():

    if request.method == "POST":

        fullname = request.form.get("fullname", "").strip()
        if not fullname:
            flash("Full name is required.")
            return redirect(url_for("new_member"))

        age = request.form.get("age") or None
        professional_year = request.form.get("professional_year") or None
        experience_years = request.form.get("experience_years") or 0
        salary = request.form.get("salary") or 0

        photo = request.files.get("photo")
        photo_name = None
        if photo and photo.filename:
            extension = photo.filename.rsplit(".", 1)[-1].lower()
            if extension in ALLOWED_EXTENSIONS:
                photo_name = str(uuid.uuid4()) + "." + extension
                photo.save(os.path.join(UPLOAD_FOLDER, photo_name))
            else:
                flash("Invalid photo format.")
                return redirect(url_for("new_member"))

        organization_id = session.get("organization_id")

        connection = get_connection(MYSQL_DATABASE)
        cursor = connection.cursor()

        sql = """
            INSERT INTO members (
                organization_id, fullname, phone, age, national_id, birth_date,
                residential_subcity, woreda, kebele, union_name, family_name,
                ethnicity, health_status, experience_years, salary, identification_language,
                party_responsibility, institution, membership_period,
                professional_experience, professional_year, professional_position,
                education_level, field_of_study, employment_type, employment_place,
                previous_political_organization, previous_political_position,
                readiness, address, photo, blood_group, emergency_contact
            )
            VALUES (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
        """

        values = (
            organization_id, fullname,
            request.form.get("phone"), age,
            request.form.get("national_id"),
            request.form.get("birth_date") or None,
            request.form.get("residential_subcity"),
            request.form.get("woreda"),
            request.form.get("kebele"),
            request.form.get("union_name"),
            request.form.get("family_name"),
            request.form.get("ethnicity"),
            request.form.get("health_status"),
            experience_years, salary,
            request.form.get("identification_language"),
            request.form.get("party_responsibility"),
            request.form.get("institution"),
            request.form.get("membership_period"),
            request.form.get("professional_experience"),
            professional_year,
            request.form.get("professional_position"),
            request.form.get("education_level"),
            request.form.get("field_of_study"),
            request.form.get("employment_type"),
            request.form.get("employment_place"),
            request.form.get("previous_political_organization"),
            request.form.get("previous_political_position"),
            request.form.get("readiness"),
            request.form.get("address"),
            photo_name,
            request.form.get("blood_group") or "",
            request.form.get("emergency_contact") or ""
        )

        try:
            cursor.execute(sql, values)
            connection.commit()

            new_member_id = cursor.lastrowid
            member_code = generate_member_code(new_member_id)

            cursor.execute(
                "UPDATE members SET member_code=%s, card_generated=0 WHERE id=%s",
                (member_code, new_member_id)
            )
            connection.commit()

            flash(f"Member registered! ID: {member_code}.")
            return redirect(url_for("member_profile", member_id=new_member_id))

        except Error as e:
            connection.rollback()
            flash("Database error: " + str(e))
        finally:
            cursor.close()
            connection.close()

    content = """
    <div class="card">
        <h2>አዲስ አባል ምዝገባ</h2>
        <div style="background:#e7f5ff;border-left:4px solid #1971c2;padding:12px 16px;border-radius:8px;margin-bottom:18px;font-size:13px;color:#1864ab;">
            ℹ️ <strong>Note:</strong> After registration, the member's ID card will be generated but <strong>activated only after approval</strong>.
        </div>

        <form method="POST" enctype="multipart/form-data">

            <h3>የግል መረጃ</h3>
            <div class="form-grid">
                <div class="form-group"><label>ሙሉ ስም *</label><input name="fullname" required></div>
                <div class="form-group"><label>ስልክ</label><input name="phone"></div>
                <div class="form-group"><label>ዕድሜ</label><input type="number" name="age"></div>
                <div class="form-group"><label>ብሔራዊ መታወቂያ</label><input name="national_id"></div>
                <div class="form-group"><label>የትውልድ ቀን</label><input type="date" name="birth_date"></div>
                <div class="form-group">
                    <label>የመታወቂያ ቋንቋ</label>
                    <select name="identification_language">
                        <option value="">Select</option>
                        <option>Amharic</option><option>Afaan Oromo</option><option>English</option>
                        <option>Somali</option><option>Tigrinya</option>
                    </select>
                </div>
                <div class="form-group"><label>የቤተሰብ ስም</label><input name="family_name"></div>
                <div class="form-group"><label>የማህበር / የቤተሰብ ስም</label><input name="union_name"></div>
                <div class="form-group"><label>ብሔር</label><input name="ethnicity"></div>
                <div class="form-group"><label>የጤና ሁኔታ</label><input name="health_status"></div>
                <div class="form-group">
                    <label>የደም አይነት</label>
                    <select name="blood_group">
                        <option value="">Select</option>
                        <option>A+</option><option>A-</option><option>B+</option><option>B-</option>
                        <option>AB+</option><option>AB-</option><option>O+</option><option>O-</option>
                    </select>
                </div>
                <div class="form-group"><label>የአደጋ ጊዜ ተጠሪ</label><input name="emergency_contact"></div>
            </div>

            <h3>የአባል ፎቶ</h3>
            <div class="form-grid">
                <div class="form-group" style="grid-column: span 2;">
                    <label>📸 ፎቶ ይጫኑ</label>
                    <input type="file" name="photo" accept="image/*" id="memberPhoto">
                    <div id="photoPreviewWrap" style="display:none;margin-top:14px;">
                        <img id="photoPreview" style="max-width:160px;border-radius:12px;border:4px solid #087f5b;">
                    </div>
                </div>
            </div>

            <h3>አድራሻ</h3>
            <div class="form-grid">
                <div class="form-group"><label>የመኖሪያ ክፍለ ከተማ</label><input name="residential_subcity"></div>
                <div class="form-group"><label>ወረዳ</label><input name="woreda"></div>
                <div class="form-group"><label>ቀበሌ</label><input name="kebele"></div>
                <div class="form-group"><label>አድራሻ</label><textarea name="address"></textarea></div>
            </div>

            <h3>የአባልነት መረጃ</h3>
            <div class="form-grid">
                <div class="form-group"><label>የፓርቲ ኃላፊነት</label><input name="party_responsibility"></div>
                <div class="form-group"><label>ተቋም</label><input name="institution"></div>
                <div class="form-group"><label>የአባልነት ጊዜ</label><input name="membership_period"></div>
                <div class="form-group"><label>የቀድሞ የፖለቲካ ድርጅት</label><input name="previous_political_organization"></div>
                <div class="form-group"><label>የቀድሞ የፖለቲካ ቦታ</label><input name="previous_political_position"></div>
                <div class="form-group"><label>ዝግጁነት</label><input name="readiness"></div>
            </div>

            <h3>ትምህርት እና ስራ</h3>
            <div class="form-grid">
                <div class="form-group"><label>የትምህርት ደረጃ</label><input name="education_level"></div>
                <div class="form-group"><label>የትምህርት መስክ</label><input name="field_of_study"></div>
                <div class="form-group"><label>የስራ ዓይነት</label><input name="employment_type"></div>
                <div class="form-group"><label>የስራ ቦታ</label><input name="employment_place"></div>
                <div class="form-group"><label>ደመወዝ</label><input type="number" step="0.01" name="salary"></div>
                <div class="form-group"><label>የስራ ልምድ ዓመታት</label><input type="number" name="experience_years"></div>
                <div class="form-group"><label>የሙያ ልምድ</label><textarea name="professional_experience"></textarea></div>
                <div class="form-group"><label>የሙያ ዓመት</label><input type="number" name="professional_year"></div>
                <div class="form-group"><label>የሙያ ቦታ</label><input name="professional_position"></div>
            </div>

            <br>
            <button type="submit" class="btn btn-primary">📝 አባል መዝግብ</button>
            <a href="{{ url_for('members') }}" class="btn btn-gray">ሰርዝ</a>
        </form>
    </div>

    <script>
    document.getElementById("memberPhoto").addEventListener("change", function(e) {
        var file = e.target.files[0];
        if (!file) return;
        var reader = new FileReader();
        reader.onload = function(ev) {
            document.getElementById("photoPreview").src = ev.target.result;
            document.getElementById("photoPreviewWrap").style.display = "block";
        };
        reader.readAsDataURL(file);
    });
    </script>
    """
    return page("New Member", render_template_string(content))


# ============================================================
# MEMBERS LIST
# ============================================================

@app.route("/members")
@login_required
def members():
    search = request.args.get("search", "").strip()
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor(dictionary=True)

    if session.get("role") == "general_admin":
        if search:
            cursor.execute(
                "SELECT * FROM members WHERE fullname LIKE %s OR phone LIKE %s OR member_code LIKE %s ORDER BY id DESC",
                ("%" + search + "%", "%" + search + "%", "%" + search + "%")
            )
        else:
            cursor.execute("SELECT * FROM members ORDER BY id DESC")
    else:
        oid = session.get("organization_id")
        if search:
            cursor.execute(
                "SELECT * FROM members WHERE organization_id=%s AND (fullname LIKE %s OR phone LIKE %s OR member_code LIKE %s) ORDER BY id DESC",
                (oid, "%" + search + "%", "%" + search + "%", "%" + search + "%")
            )
        else:
            cursor.execute("SELECT * FROM members WHERE organization_id=%s ORDER BY id DESC", (oid,))

    rows = cursor.fetchall()
    cursor.close()
    connection.close()

    content = """
    <div class="card">
        <h2>አባላት</h2>
        <div class="search-box">
            <form method="GET" style="display:flex;width:100%;gap:10px">
                <input name="search" placeholder="ስም፣ ስልክ ወይም Member ID ይፈልጉ..." value="{{ search }}">
                <button class="btn btn-blue" type="submit">ፈልግ</button>
                <a class="btn btn-primary" href="{{ url_for('new_member') }}">+ አዲስ አባል</a>
            </form>
        </div>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>መለያ</th><th>Member ID</th><th>ፎቶ</th><th>ሙሉ ስም</th><th>ስልክ</th>
                        <th>ብሔር</th><th>ክፍለ ከተማ</th><th>ሁኔታ</th><th>ID Card</th><th>እርምጃዎች</th>
                    </tr>
                </thead>
                <tbody>
                {% for member in rows %}
                    <tr>
                        <td>{{ member.id }}</td>
                        <td><span style="font-family:'Courier New',monospace;font-size:11px;font-weight:800;color:#087f5b;background:#e6fffa;padding:3px 7px;border-radius:5px;">{{ member.member_code or '—' }}</span></td>
                        <td>
                            {% if member.photo %}
                                <img src="{{ url_for('uploaded_file', filename=member.photo) }}" class="member-photo">
                            {% else %}
                                <div style="width:70px;height:70px;border-radius:50%;background:#e2e8f0;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:11px;">No Photo</div>
                            {% endif %}
                        </td>
                        <td>{{ member.fullname }}</td>
                        <td>{{ member.phone or "" }}</td>
                        <td>{{ member.ethnicity or "" }}</td>
                        <td>{{ member.residential_subcity or "" }}</td>
                        <td>
                            {% if member.status == "Approved" %}<span class="badge badge-approved">✓ የጸደቀ</span>
                            {% elif member.status == "Rejected" %}<span class="badge badge-rejected">✗ ውድቅ</span>
                            {% else %}<span class="badge badge-pending">⏳ በመጠባበቅ</span>{% endif %}
                        </td>
                        <td>
                            {% if member.status == "Approved" %}
                                <a href="{{ url_for('member_id_card', member_id=member.id) }}" class="btn btn-primary" target="_blank" style="font-size:11.5px;">🆔 View Card</a>
                            {% else %}
                                <a href="{{ url_for('approve_member', member_id=member.id) }}" class="btn btn-green" style="font-size:11.5px;">✅ Approve</a>
                            {% endif %}
                        </td>
                        <td>
                            <a href="{{ url_for('member_profile', member_id=member.id) }}" class="btn btn-blue" style="font-size:11.5px;">👁 View</a>
                            <a href="{{ url_for('edit_member', member_id=member.id) }}" class="btn btn-orange" style="font-size:11.5px;">✏ Edit</a>
                            <a href="{{ url_for('delete_member', member_id=member.id) }}" class="btn btn-red" onclick="return confirmDelete()" style="font-size:11.5px;">🗑</a>
                        </td>
                    </tr>
                {% else %}
                    <tr><td colspan="10">ምንም አባል አልተገኘም።</td></tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    """
    return page("Members", render_template_string(content, rows=rows, search=search))


# ============================================================
# MEMBER PROFILE
# ============================================================

@app.route("/member/<int:member_id>")
@login_required
def member_profile(member_id):
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM members WHERE id=%s", (member_id,))
    member = cursor.fetchone()
    cursor.close()
    connection.close()

    if not member:
        return "Member not found.", 404

    content = """
    <div class="card">
        <a href="{{ url_for('members') }}" class="btn btn-gray">← ተመለስ</a>
        <a href="{{ url_for('edit_member', member_id=member.id) }}" class="btn btn-orange">✏ አርትዕ</a>
        {% if member.status == 'Approved' %}
            <a href="{{ url_for('member_id_card', member_id=member.id) }}" class="btn btn-primary" target="_blank">🆔 የመታወቂያ ካርድ</a>
        {% else %}
            <a href="{{ url_for('approve_member', member_id=member.id) }}" class="btn btn-green">✅ አጽድቅ እና ID ፍጠር</a>
        {% endif %}

        <h2>የአባል መገለጫ</h2>

        <div class="center">
            {% if member.photo %}<img src="{{ url_for('uploaded_file', filename=member.photo) }}" class="profile-photo">{% endif %}
            <h2>{{ member.fullname }}</h2>
            {% if member.member_code %}
                <p style="font-family:'Courier New',monospace;font-weight:800;color:#087f5b;background:#e6fffa;display:inline-block;padding:6px 14px;border-radius:8px;margin-top:8px;">{{ member.member_code }}</p>
            {% endif %}
            <p style="margin-top:10px;">
                {% if member.status == "Approved" %}<span class="badge badge-approved" style="font-size:13px;padding:7px 14px;">✓ Approved</span>
                {% elif member.status == "Rejected" %}<span class="badge badge-rejected" style="font-size:13px;padding:7px 14px;">✗ Rejected</span>
                {% else %}<span class="badge badge-pending" style="font-size:13px;padding:7px 14px;">⏳ Pending</span>{% endif %}
            </p>
            {% if member.approved_by_name %}<p style="margin-top:8px;font-size:12.5px;color:#475569;">Approved by: <strong>{{ member.approved_by_name }}</strong></p>{% endif %}
        </div>

        <div class="form-grid" style="margin-top:20px;">
            <div><strong>ስልክ:</strong> {{ member.phone or "" }}</div>
            <div><strong>ዕድሜ:</strong> {{ member.age or "" }}</div>
            <div><strong>ብሔራዊ መታወቂያ:</strong> {{ member.national_id or "" }}</div>
            <div><strong>የትውልድ ቀን:</strong> {{ member.birth_date or "" }}</div>
            <div><strong>ብሔር:</strong> {{ member.ethnicity or "" }}</div>
            <div><strong>ክፍለ ከተማ:</strong> {{ member.residential_subcity or "" }}</div>
            <div><strong>ወረዳ:</strong> {{ member.woreda or "" }}</div>
            <div><strong>ቀበሌ:</strong> {{ member.kebele or "" }}</div>
            <div><strong>ደም አይነት:</strong> {{ member.blood_group or "" }}</div>
            <div><strong>ደመወዝ:</strong> {{ member.salary or 0 }}</div>
        </div>
    </div>
    """
    return page("Member Profile", render_template_string(content, member=member))


# ============================================================
# APPROVE MEMBER
# ============================================================

@app.route("/member/<int:member_id>/approve", methods=["GET", "POST"])
@login_required
def approve_member(member_id):
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM members WHERE id=%s", (member_id,))
    member = cursor.fetchone()

    if not member:
        cursor.close()
        connection.close()
        flash("Member not found.")
        return redirect(url_for("members"))

    if request.method == "POST":
        approver_id = request.form.get("approver_id")
        if not approver_id:
            flash("Please select an approver.")
            cursor.close()
            connection.close()
            return redirect(url_for("approve_member", member_id=member_id))

        cursor.execute("SELECT * FROM approvers WHERE id=%s", (approver_id,))
        approver = cursor.fetchone()
        if not approver:
            flash("Selected approver not found.")
            cursor.close()
            connection.close()
            return redirect(url_for("approve_member", member_id=member_id))

        today = date.today()
        expiry = date(today.year + 5, today.month, today.day)
        code = member.get("member_code") or generate_member_code(member_id)

        cursor.execute(
            """UPDATE members SET status='Approved', member_code=%s, id_issued_date=%s,
               id_expiry_date=%s, card_generated=1, approved_at=NOW(),
               approved_by_id=%s, approved_by_name=%s, approved_by_signature=%s
               WHERE id=%s""",
            (code, today.isoformat(), expiry.isoformat(), approver["id"],
             approver["full_name"], approver.get("signature_image") or "", member_id)
        )
        connection.commit()
        cursor.close()
        connection.close()
        flash(f"✅ Member approved by {approver['full_name']}!")
        return redirect(url_for("member_id_card", member_id=member_id))

    cursor.execute("SELECT * FROM approvers WHERE is_active=1 ORDER BY full_name")
    approvers_list = cursor.fetchall()
    if not approvers_list:
        cursor.execute("SELECT * FROM approvers ORDER BY full_name")
        approvers_list = cursor.fetchall()
    cursor.close()
    connection.close()

    content = """
    <div class="card">
        <h2>✅ Approve Member</h2>
        <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;background:#f8fafc;padding:16px;border-radius:12px;border:1px solid #e2e8f0;margin-bottom:20px;">
            {% if member.photo %}<img src="{{ url_for('uploaded_file', filename=member.photo) }}" style="width:80px;height:80px;object-fit:cover;border-radius:12px;border:3px solid #087f5b;">{% endif %}
            <div>
                <div style="font-size:18px;font-weight:900;color:#075e54;">{{ member.fullname }}</div>
                <div style="font-size:13px;color:#64748b;">{{ member.member_code or '—' }} · {{ member.phone or '—' }}</div>
            </div>
        </div>

        {% if not approvers_list %}
            <div style="background:#fff3bf;border-left:4px solid #e6b800;padding:16px;border-radius:8px;color:#8d6b00;">
                <strong>⚠️ No approvers found.</strong> Please add at least one approver first.<br><br>
                <a href="{{ url_for('new_approver') }}" class="btn btn-primary">+ Add Approver Now</a>
            </div>
        {% else %}
            <form method="POST">
                <h3 style="margin-bottom:12px;">Select the approver for this member:</h3>
                <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin-bottom:20px;">
                    {% for a in approvers_list %}
                    <label class="approver-card" style="cursor:pointer;">
                        <input type="radio" name="approver_id" value="{{ a.id }}" required style="display:none;">
                        <div class="approver-inner" style="border:2px solid #e2e8f0;border-radius:12px;padding:14px;background:white;transition:all .2s;">
                            <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:8px;">
                                <div>
                                    <div style="font-weight:900;color:#075e54;font-size:15px;">{{ a.full_name }}</div>
                                    <div style="font-size:12px;color:#64748b;">{{ a.position or 'Approver' }}</div>
                                </div>
                                {% if a.is_active %}<span class="badge badge-approved" style="font-size:10px;">Active</span>
                                {% else %}<span class="badge badge-rejected" style="font-size:10px;">Inactive</span>{% endif %}
                            </div>
                            {% if a.signature_image %}
                            <div style="background:#f8fafc;border-radius:8px;padding:8px;text-align:center;">
                                <img src="{{ url_for('uploaded_file', filename=a.signature_image) }}" style="max-height:55px;max-width:100%;object-fit:contain;">
                            </div>
                            {% else %}
                            <div style="font-size:11px;color:#c92a2a;">No signature uploaded</div>
                            {% endif %}
                        </div>
                    </label>
                    {% endfor %}
                </div>
                <button type="submit" class="btn btn-green" style="font-size:15px;padding:14px 28px;">✅ Confirm Approval</button>
                <a href="{{ url_for('member_profile', member_id=member.id) }}" class="btn btn-gray">Cancel</a>
            </form>
        {% endif %}
    </div>

    <style>
    .approver-card input:checked + .approver-inner {
        border-color: #087f5b;
        background: #e6fffa;
        box-shadow: 0 0 0 4px rgba(8,127,91,.15);
    }
    .approver-card:hover .approver-inner { border-color: #12b886; }
    </style>
    """
    return page("Approve Member", render_template_string(content, member=member, approvers_list=approvers_list))


# ============================================================
# MEMBER ID CARD
# ============================================================

@app.route("/member/<int:member_id>/id-card")
@login_required
def member_id_card(member_id):
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM members WHERE id=%s", (member_id,))
    member = cursor.fetchone()
    cursor.close()
    connection.close()

    if not member:
        return "Member not found.", 404

    if not member.get("member_code"):
        code = generate_member_code(member["id"])
        connection = get_connection(MYSQL_DATABASE)
        cursor = connection.cursor()
        cursor.execute("UPDATE members SET member_code=%s WHERE id=%s", (code, member["id"]))
        connection.commit()
        cursor.close()
        connection.close()
        member["member_code"] = code

    issued = member.get("id_issued_date")
    expiry = member.get("id_expiry_date")
    issued_str = issued.strftime("%d/%m/%Y") if issued else date.today().strftime("%d/%m/%Y")
    expiry_str = expiry.strftime("%d/%m/%Y") if expiry else "—"

    photo_url = (
        url_for("uploaded_file", filename=member["photo"])
        if member.get("photo") else FALLBACK_IMAGE
    )

    settings = get_system_settings()
    signature_setting = settings.get("signature_image", "") or ""
    if signature_setting:
        signature_url = signature_setting if signature_setting.startswith("http") else url_for("uploaded_file", filename=signature_setting)
    else:
        signature_url = ""

    approver_signature_url = ""
    if member.get("approved_by_signature"):
        approver_signature_url = url_for("uploaded_file", filename=member["approved_by_signature"])

    qr_data = generate_qr_data(member)
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={qr_data}"

    return render_template_string(
        ID_CARD_HTML,
        member=member, photo_url=photo_url, signature_url=signature_url,
        approver_signature_url=approver_signature_url, qr_url=qr_url,
        issued_str=issued_str, expiry_str=expiry_str,
        logo=PARTY_LOGO, system_title=SYSTEM_TITLE,
        primary_color=settings.get("primary_color", DEFAULT_PRIMARY_COLOR),
        secondary_color=settings.get("secondary_color", DEFAULT_SECONDARY_COLOR),
    )


# ============================================================
# MEMBER EDIT
# ============================================================

@app.route("/member/<int:member_id>/edit", methods=["GET", "POST"])
@login_required
def edit_member(member_id):
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM members WHERE id=%s", (member_id,))
    member = cursor.fetchone()
    cursor.close()
    connection.close()

    if not member:
        return "Member not found.", 404

    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        age = request.form.get("age") or None
        professional_year = request.form.get("professional_year") or None

        new_photo = request.files.get("photo")
        photo_name = member.get("photo")
        if new_photo and new_photo.filename:
            extension = new_photo.filename.rsplit(".", 1)[-1].lower()
            if extension in ALLOWED_EXTENSIONS:
                photo_name = str(uuid.uuid4()) + "." + extension
                new_photo.save(os.path.join(UPLOAD_FOLDER, photo_name))

        status = request.form.get("status") or member.get("status") or "Pending"

        connection = get_connection(MYSQL_DATABASE)
        cursor = connection.cursor()

        sql = """
            UPDATE members SET
                fullname=%s, phone=%s, age=%s, national_id=%s, birth_date=%s,
                residential_subcity=%s, woreda=%s, kebele=%s, union_name=%s,
                family_name=%s, ethnicity=%s, health_status=%s, experience_years=%s,
                salary=%s, identification_language=%s, party_responsibility=%s,
                institution=%s, membership_period=%s, professional_experience=%s,
                professional_year=%s, professional_position=%s, education_level=%s,
                field_of_study=%s, employment_type=%s, employment_place=%s,
                previous_political_organization=%s, previous_political_position=%s,
                readiness=%s, address=%s, blood_group=%s, emergency_contact=%s,
                status=%s, photo=%s
            WHERE id=%s
        """
        values = (
            fullname, request.form.get("phone"), age,
            request.form.get("national_id"),
            request.form.get("birth_date") or None,
            request.form.get("residential_subcity"),
            request.form.get("woreda"),
            request.form.get("kebele"),
            request.form.get("union_name"),
            request.form.get("family_name"),
            request.form.get("ethnicity"),
            request.form.get("health_status"),
            request.form.get("experience_years") or 0,
            request.form.get("salary") or 0,
            request.form.get("identification_language"),
            request.form.get("party_responsibility"),
            request.form.get("institution"),
            request.form.get("membership_period"),
            request.form.get("professional_experience"),
            professional_year,
            request.form.get("professional_position"),
            request.form.get("education_level"),
            request.form.get("field_of_study"),
            request.form.get("employment_type"),
            request.form.get("employment_place"),
            request.form.get("previous_political_organization"),
            request.form.get("previous_political_position"),
            request.form.get("readiness"),
            request.form.get("address"),
            request.form.get("blood_group") or "",
            request.form.get("emergency_contact") or "",
            status, photo_name, member_id
        )

        cursor.execute(sql, values)

        if status == "Approved" and member.get("status") != "Approved":
            today = date.today()
            expiry = date(today.year + 5, today.month, today.day)
            cursor.execute(
                "UPDATE members SET id_issued_date=%s, id_expiry_date=%s, card_generated=1, approved_at=NOW() WHERE id=%s",
                (today.isoformat(), expiry.isoformat(), member_id)
            )

        connection.commit()
        cursor.close()
        connection.close()
        flash("Member updated successfully.")
        return redirect(url_for("member_profile", member_id=member_id))

    content = """
    <div class="card">
        <h2>✏ አባል አርትዕ</h2>
        <form method="POST" enctype="multipart/form-data">
            <div class="form-grid">
                <div class="form-group"><label>ሙሉ ስም</label><input name="fullname" value="{{ member.fullname or '' }}" required></div>
                <div class="form-group"><label>ስልክ</label><input name="phone" value="{{ member.phone or '' }}"></div>
                <div class="form-group"><label>ዕድሜ</label><input type="number" name="age" value="{{ member.age or '' }}"></div>
                <div class="form-group"><label>ብሔራዊ መታወቂያ</label><input name="national_id" value="{{ member.national_id or '' }}"></div>
                <div class="form-group"><label>የትውልድ ቀን</label><input type="date" name="birth_date" value="{{ member.birth_date or '' }}"></div>
                <div class="form-group"><label>የመኖሪያ ክፍለ ከተማ</label><input name="residential_subcity" value="{{ member.residential_subcity or '' }}"></div>
                <div class="form-group"><label>ወረዳ</label><input name="woreda" value="{{ member.woreda or '' }}"></div>
                <div class="form-group"><label>ቀበሌ</label><input name="kebele" value="{{ member.kebele or '' }}"></div>
                <div class="form-group"><label>ብሔር</label><input name="ethnicity" value="{{ member.ethnicity or '' }}"></div>
                <div class="form-group"><label>የደም አይነት</label>
                    <select name="blood_group">
                        <option value="">Select</option>
                        {% for bg in ['A+','A-','B+','B-','AB+','AB-','O+','O-'] %}
                        <option value="{{ bg }}" {% if member.blood_group == bg %}selected{% endif %}>{{ bg }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-group"><label>የአደጋ ጊዜ ተጠሪ</label><input name="emergency_contact" value="{{ member.emergency_contact or '' }}"></div>
                <div class="form-group"><label>ደመወዝ</label><input type="number" step="0.01" name="salary" value="{{ member.salary or 0 }}"></div>
                <div class="form-group"><label>ሁኔታ</label>
                    <select name="status">
                        {% for s in ['Pending','Approved','Rejected'] %}
                        <option value="{{ s }}" {% if member.status == s %}selected{% endif %}>{{ s }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-group" style="grid-column: span 2;">
                    <label>አዲስ ፎቶ (optional)</label>
                    <input type="file" name="photo" accept="image/*">
                </div>
            </div>
            <br>
            <button type="submit" class="btn btn-primary">💾 አባል አዘምን</button>
            <a href="{{ url_for('member_profile', member_id=member.id) }}" class="btn btn-gray">ሰርዝ</a>
        </form>
    </div>
    """
    return page("Edit Member", render_template_string(content, member=member))


# ============================================================
# MEMBER DELETE
# ============================================================

@app.route("/member/<int:member_id>/delete")
@login_required
def delete_member(member_id):
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor()
    cursor.execute("SELECT photo FROM members WHERE id=%s", (member_id,))
    row = cursor.fetchone()
    if row and row[0]:
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, row[0]))
        except:
            pass
    cursor.execute("DELETE FROM payments WHERE member_id=%s", (member_id,))
    cursor.execute("DELETE FROM members WHERE id=%s", (member_id,))
    connection.commit()
    cursor.close()
    connection.close()
    flash("Member deleted successfully.")
    return redirect(url_for("members"))


# ============================================================
# PAYMENTS
# ============================================================

@app.route("/payments")
@login_required
def payments():
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor(dictionary=True)
    if session.get("role") == "general_admin":
        cursor.execute("SELECT payments.*, members.fullname FROM payments JOIN members ON payments.member_id = members.id ORDER BY payments.id DESC")
    else:
        cursor.execute("SELECT payments.*, members.fullname FROM payments JOIN members ON payments.member_id = members.id WHERE payments.organization_id=%s ORDER BY payments.id DESC", (session.get("organization_id"),))
    rows = cursor.fetchall()
    cursor.close()
    connection.close()

    content = """
    <div class="card">
        <h2>ወርሃዊ ክፍያዎች</h2>
        <a href="{{ url_for('new_payment') }}" class="btn btn-primary">+ ክፍያ ጨምር</a>
        <br><br>
        <div class="table-container">
            <table>
                <thead>
                    <tr><th>መለያ</th><th>አባል</th><th>ወር</th><th>መጠን</th><th>ዘዴ</th><th>ቀን</th><th>ደረሰኝ</th></tr>
                </thead>
                <tbody>
                {% for payment in rows %}
                    <tr>
                        <td>{{ payment.id }}</td>
                        <td>{{ payment.fullname }}</td>
                        <td>{{ payment.payment_month or "-" }}</td>
                        <td>{{ payment.amount }}</td>
                        <td>{{ payment.payment_method }}</td>
                        <td>{{ payment.payment_date }}</td>
                        <td><a class="btn btn-blue" href="{{ url_for('payment_receipt', payment_id=payment.id) }}" target="_blank">🧾 ደረሰኝ</a></td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    """
    return page("Payments", render_template_string(content, rows=rows))


@app.route("/payment/new", methods=["GET", "POST"])
@login_required
def new_payment():
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor(dictionary=True)
    if session.get("role") == "general_admin":
        cursor.execute("SELECT id, fullname, salary FROM members WHERE status='Approved' ORDER BY fullname")
    else:
        cursor.execute("SELECT id, fullname, salary FROM members WHERE organization_id=%s AND status='Approved' ORDER BY fullname", (session.get("organization_id"),))
    members_list = cursor.fetchall()
    cursor.close()
    connection.close()

    if request.method == "POST":
        member_id = request.form.get("member_id")
        salary = request.form.get("salary") or 0
        percentage = 0
        payment_month = request.form.get("payment_month") or ""
        amount = request.form.get("amount") or 0
        organization_id = session.get("organization_id")

        connection = get_connection(MYSQL_DATABASE)
        cursor = connection.cursor()
        cursor.execute(
            """INSERT INTO payments (member_id, organization_id, salary, percentage, payment_month, amount, payment_method, reference_number, payment_date)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (member_id, organization_id, salary, percentage, payment_month, amount,
             request.form.get("payment_method"), request.form.get("reference_number"),
             request.form.get("payment_date") or date.today().isoformat())
        )
        connection.commit()
        cursor.close()
        connection.close()
        flash("Payment saved.")
        return redirect(url_for("payments"))

    content = """
    <div class="card">
        <h2>ወርሃዊ ክፍያ ጨምር</h2>
        <form method="POST">
            <div class="form-grid">
                <div class="form-group">
                    <label>አባል</label>
                    <select name="member_id" required>
                        <option value="">አባል ይምረጡ</option>
                        {% for member in members_list %}
                        <option value="{{ member.id }}">{{ member.fullname }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-group"><label>ደመወዝ</label><input type="number" step="0.01" name="salary" required></div>
                <div class="form-group">
                    <label>ወር</label>
                    <select name="payment_month" required>
                        <option value="">ወር ይምረጡ</option>
                        {% for month in ethiopian_months %}<option value="{{ month }}">{{ month }}</option>{% endfor %}
                    </select>
                </div>
                <div class="form-group"><label>መጠን</label><input type="number" step="0.01" name="amount" required></div>
                <div class="form-group">
                    <label>ዘዴ</label>
                    <select name="payment_method"><option>Cash</option><option>Bank</option><option>Telebirr</option></select>
                </div>
                <div class="form-group"><label>ማጣቀሻ</label><input name="reference_number"></div>
                <div class="form-group"><label>ቀን</label><input type="date" name="payment_date" value="{{ today }}"></div>
            </div>
            <br>
            <button class="btn btn-primary" type="submit">ክፍያ ያስቀምጡ</button>
        </form>
    </div>
    """
    return page("New Payment", render_template_string(content, members_list=members_list, ethiopian_months=ETHIOPIAN_MONTHS, today=date.today().isoformat()))


# ============================================================
# ORGANIZATIONS
# ============================================================

@app.route("/organizations")
@admin_required
def organizations():
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM organizations ORDER BY id DESC")
    rows = cursor.fetchall()
    cursor.close()
    connection.close()

    content = """
    <div class="card">
        <h2>የድርጅት መዝገቦች</h2>
        <a href="{{ url_for('new_organization') }}" class="btn btn-primary">+ መዝገብ ፍጠር</a>
        <br><br>
        <div class="table-container">
            <table>
                <thead><tr><th>መለያ</th><th>ስም</th><th>ኮድ</th><th>ስልክ</th><th>አድራሻ</th></tr></thead>
                <tbody>
                {% for organization in rows %}
                    <tr>
                        <td>{{ organization.id }}</td>
                        <td>{{ organization.name }}</td>
                        <td>{{ organization.code }}</td>
                        <td>{{ organization.phone or "" }}</td>
                        <td>{{ organization.address or "" }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    """
    return page("Accounts", render_template_string(content, rows=rows))


@app.route("/organization/new", methods=["GET", "POST"])
@admin_required
def new_organization():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        fullname = request.form.get("fullname", "").strip()

        if not name or not code or not username or not password:
            flash("All required fields must be filled.")
            return redirect(url_for("new_organization"))

        connection = get_connection(MYSQL_DATABASE)
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
            if cursor.fetchone():
                flash("Username is already taken.")
                return redirect(url_for("new_organization"))
            cursor.execute("SELECT id FROM organizations WHERE code=%s", (code,))
            if cursor.fetchone():
                flash("Organization code already exists.")
                return redirect(url_for("new_organization"))

            cursor.execute("INSERT INTO organizations (name, code, phone, address) VALUES (%s,%s,%s,%s)",
                           (name, code, request.form.get("phone"), request.form.get("address")))
            organization_id = cursor.lastrowid
            hashed_password = generate_password_hash(password)
            cursor.execute("INSERT INTO users (organization_id, username, password, fullname, role) VALUES (%s,%s,%s,%s,%s)",
                           (organization_id, username, hashed_password, fullname, "admin"))
            connection.commit()
            flash("Organization account created successfully.")
            return redirect(url_for("organizations"))
        except Error as e:
            connection.rollback()
            flash("Error: " + str(e))
        finally:
            cursor.close()
            connection.close()

    content = """
    <div class="card">
        <h2>የድርጅት መዝገብ ፍጠር</h2>
        <form method="POST">
            <div class="form-grid">
                <div class="form-group"><label>የድርጅት ስም *</label><input name="name" required></div>
                <div class="form-group"><label>የድርጅት ኮድ *</label><input name="code" required></div>
                <div class="form-group"><label>ስልክ</label><input name="phone"></div>
                <div class="form-group"><label>አድራሻ</label><input name="address"></div>
                <div class="form-group"><label>የመዝገብ ሙሉ ስም</label><input name="fullname"></div>
                <div class="form-group"><label>የተጠቃሚ ስም *</label><input name="username" required></div>
                <div class="form-group"><label>የይለፍ ቃል *</label><input type="password" name="password" required minlength="6"></div>
            </div>
            <br>
            <button type="submit" class="btn btn-primary">መዝገብ ፍጠር</button>
            <a href="{{ url_for('organizations') }}" class="btn btn-gray">ሰርዝ</a>
        </form>
    </div>
    """
    return page("Create Account", render_template_string(content))


# ============================================================
# SITE SETTINGS
# ============================================================

@app.route("/settings", methods=["GET", "POST"])
@admin_required
def site_settings():
    connection = get_connection(MYSQL_DATABASE)
    if connection is None:
        return "MySQL connection failed.", 500

    cursor = connection.cursor(dictionary=True)

    if request.method == "POST":
        primary = request.form.get("primary_color", DEFAULT_PRIMARY_COLOR).strip()
        secondary = request.form.get("secondary_color", DEFAULT_SECONDARY_COLOR).strip()
        username = request.form.get("username", "").strip()
        new_password = request.form.get("new_password", "")
        current_password = request.form.get("current_password", "")

        import re
        color_re = re.compile(r"^#[0-9A-Fa-f]{6}$")
        if not color_re.match(primary) or not color_re.match(secondary):
            flash("Please enter valid 6-digit colors.")
        else:
            for key, value in [("primary_color", primary), ("secondary_color", secondary)]:
                cursor.execute("UPDATE system_settings SET setting_value=%s WHERE setting_key=%s", (value, key))

            signature_file = request.files.get("signature_image")
            signature_link = request.form.get("signature_link", "").strip()

            if signature_file and signature_file.filename:
                extension = signature_file.filename.rsplit(".", 1)[-1].lower()
                if extension in ALLOWED_EXTENSIONS:
                    signature_name = "signature_" + str(uuid.uuid4()) + "." + extension
                    signature_file.save(os.path.join(UPLOAD_FOLDER, signature_name))
                    cursor.execute("UPDATE system_settings SET setting_value=%s WHERE setting_key='signature_image'", (signature_name,))
                    flash("✅ Signature uploaded.")
            elif signature_link and signature_link.startswith("http"):
                cursor.execute("UPDATE system_settings SET setting_value=%s WHERE setting_key='signature_image'", (signature_link,))
                flash("✅ Signature link saved.")

            gallery = request.files.get("gallery_image")
            gallery_link = request.form.get("gallery_link", "").strip()

            cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key='gallery_image'")
            row = cursor.fetchone()
            existing_gallery = []
            if row and row["setting_value"]:
                try:
                    existing_gallery = json.loads(row["setting_value"])
                except:
                    existing_gallery = []

            new_images = list(existing_gallery)

            if gallery and gallery.filename:
                extension = gallery.filename.rsplit(".", 1)[-1].lower()
                if extension in ALLOWED_EXTENSIONS:
                    gallery_name = str(uuid.uuid4()) + "." + extension
                    gallery.save(os.path.join(UPLOAD_FOLDER, gallery_name))
                    new_images.append(gallery_name)

            if gallery_link and gallery_link.startswith("http"):
                new_images.append(gallery_link)

            if new_images != existing_gallery:
                cursor.execute("UPDATE system_settings SET setting_value=%s WHERE setting_key='gallery_image'", (json.dumps(new_images),))

            user_id = session.get("user_id")
            cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
            user = cursor.fetchone()
            if user and username and username != user["username"]:
                cursor.execute("SELECT id FROM users WHERE username=%s AND id<>%s", (username, user_id))
                if cursor.fetchone():
                    flash("Username already exists.")
                else:
                    cursor.execute("UPDATE users SET username=%s WHERE id=%s", (username, user_id))
                    session["username"] = username
            if user and new_password:
                if not current_password or not check_password_hash(user["password"], current_password):
                    flash("Current password is incorrect.")
                elif len(new_password) < 6:
                    flash("New password must be at least 6 characters.")
                else:
                    cursor.execute("UPDATE users SET password=%s WHERE id=%s", (generate_password_hash(new_password), user_id))

            connection.commit()
            flash("Site settings saved.")

        cursor.close()
        connection.close()
        return redirect(url_for("site_settings"))

    settings = get_system_settings()
    gallery_images = get_gallery_images()
    signature_setting = settings.get("signature_image", "") or ""

    if signature_setting and signature_setting.startswith("http"):
        signature_preview_url = signature_setting
    elif signature_setting:
        signature_preview_url = url_for("uploaded_file", filename=signature_setting)
    else:
        signature_preview_url = ""

    cursor.close()
    connection.close()

    content = """
    <div class="card">
        <h2>⚙️ የሲስተም ቅንብር</h2>
        <form method="POST" enctype="multipart/form-data">

            <h3>🎨 የሲስተም ቀለም</h3><br>
            <div class="form-grid">
                <div class="form-group"><label>Primary Color</label><input type="color" name="primary_color" value="{{ settings.primary_color }}" style="height:48px;padding:4px"></div>
                <div class="form-group"><label>Secondary Color</label><input type="color" name="secondary_color" value="{{ settings.secondary_color }}" style="height:48px;padding:4px"></div>
            </div>

            <hr style="margin:25px 0;border:0;border-top:1px solid #ddd">

            <h3>✍️ Global Default Signature (fallback)</h3><br>
            <div class="form-grid">
                <div class="form-group" style="grid-column: span 2;">
                    <label>📤 Upload Signature Image</label>
                    <input type="file" name="signature_image" accept="image/*">
                </div>
                <div class="form-group" style="grid-column: span 2;">
                    <label>🔗 Or Paste URL</label>
                    <input type="text" name="signature_link" placeholder="https://example.com/signature.png">
                </div>
                {% if signature_preview_url %}
                <div class="form-group" style="grid-column: span 2;">
                    <p style="font-weight:700;color:#087f5b;">Current:</p>
                    <img src="{{ signature_preview_url }}" style="max-height:100px;border:2px dashed #087f5b;border-radius:10px;padding:8px;background:white;">
                </div>
                {% endif %}
            </div>

            <hr style="margin:25px 0;border:0;border-top:1px solid #ddd">
            <h3>🖼️ Gallery Upload</h3><br>
            <div class="form-grid">
                <div class="form-group" style="grid-column: span 2;">
                    <label>Upload Gallery Image</label>
                    <input type="file" name="gallery_image" accept="image/*">
                </div>
                <div class="form-group" style="grid-column: span 2;">
                    <label>Or Paste URL</label>
                    <input type="text" name="gallery_link" placeholder="https://example.com/image.jpg">
                </div>
                {% if gallery_images %}
                <div class="form-group" style="grid-column: span 2;">
                    <p>Gallery ({{ gallery_images|length }}):</p>
                    <div style="display:flex;flex-wrap:wrap;gap:15px;margin-top:12px;">
                        {% for img in gallery_images %}
                        <div style="position:relative;">
                            <img src="{{ img if img.startswith('http') else url_for('uploaded_file', filename=img) }}" style="max-width:150px;max-height:100px;border-radius:8px;border:2px solid #087f5b;object-fit:cover;">
                            <a href="{{ url_for('delete_gallery_image', image_name=img) }}" class="btn btn-red" style="position:absolute;top:-8px;right:-8px;padding:4px 8px;font-size:11px;border-radius:50%;" onclick="return confirm('Delete?');">✕</a>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endif %}
            </div>

            <hr style="margin:25px 0;border:0;border-top:1px solid #ddd">
            <h3>🔐 Credentials</h3><br>
            <div class="form-grid">
                <div class="form-group"><label>Username</label><input name="username" value="{{ session.get('username','') }}" required></div>
                <div class="form-group"><label>Current Password</label><input type="password" name="current_password"></div>
                <div class="form-group"><label>New Password</label><input type="password" name="new_password" minlength="6"></div>
            </div><br>
            <button class="btn btn-primary" type="submit">💾 ቅንብሩን አስቀምጥ</button>
        </form>
    </div>
    """
    return page("Site Setting", render_template_string(
        content, settings=settings,
        gallery_images=gallery_images,
        signature_preview_url=signature_preview_url
    ))


@app.route("/settings/delete-gallery/<path:image_name>")
@admin_required
def delete_gallery_image(image_name):
    connection = get_connection(MYSQL_DATABASE)
    if connection is None:
        return "MySQL connection failed.", 500

    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key='gallery_image'")
    row = cursor.fetchone()

    if row and row["setting_value"]:
        try:
            gallery_images = json.loads(row["setting_value"])
        except:
            gallery_images = []

        if image_name in gallery_images:
            gallery_images.remove(image_name)
            if not image_name.startswith("http"):
                filepath = os.path.join(UPLOAD_FOLDER, image_name)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except:
                        pass
            cursor.execute("UPDATE system_settings SET setting_value=%s WHERE setting_key='gallery_image'", (json.dumps(gallery_images),))
            connection.commit()
            flash("Gallery image deleted.")

    cursor.close()
    connection.close()
    return redirect(url_for("site_settings"))


# ============================================================
# PAYMENT RECEIPT — with ellipse PAID stamp + watermark
# ============================================================

@app.route("/payment/<int:payment_id>/receipt")
@login_required
def payment_receipt(payment_id):
    connection = get_connection(MYSQL_DATABASE)
    cursor = connection.cursor(dictionary=True)
    sql = """
        SELECT payments.*, members.fullname, members.phone,
               organizations.name AS organization_name
        FROM payments
        JOIN members ON payments.member_id = members.id
        LEFT JOIN organizations ON payments.organization_id = organizations.id
        WHERE payments.id=%s
    """
    params = (payment_id,)
    if session.get("role") != "general_admin":
        sql += " AND payments.organization_id=%s"
        params = (payment_id, session.get("organization_id"))
    cursor.execute(sql, params)
    payment = cursor.fetchone()
    cursor.close()
    connection.close()

    if not payment:
        return "Payment not found.", 404

    return render_template_string("""
    <!doctype html>
    <html lang="am">
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Payment Receipt #{{ payment.id }}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', 'Noto Sans Ethiopic', Arial, sans-serif;
            background: #f4f7fb;
            margin: 0;
            padding: 30px;
        }
        .receipt {
            max-width: 720px;
            margin: auto;
            background: #fff;
            padding: 40px 45px 35px;
            border-radius: 15px;
            box-shadow: 0 8px 30px rgba(0,0,0,.08);
            position: relative;
            overflow: hidden;
            isolation: isolate;
        }
        .receipt::before {
            content: "";
            position: absolute;
            inset: -30%;
            z-index: 0;
            pointer-events: none;
            background-image: url('{{ logo }}');
            background-repeat: repeat;
            background-size: 90px 90px;
            opacity: 0.06;
            transform: rotate(-25deg) scale(1.35);
            mix-blend-mode: multiply;
        }
        .receipt::after {
            content: "";
            position: absolute;
            top: 50%;
            left: 50%;
            width: 380px;
            height: 380px;
            transform: translate(-50%, -50%);
            background-image: url('{{ logo }}');
            background-repeat: no-repeat;
            background-size: contain;
            background-position: center;
            opacity: 0.05;
            z-index: 0;
            pointer-events: none;
        }
        .receipt > * { position: relative; z-index: 2; }

        .head {
            text-align: center;
            border-bottom: 3px solid {{ system_primary_color }};
            padding-bottom: 18px;
            margin-bottom: 8px;
        }
        .logo { width: 90px; height: 90px; object-fit: contain; margin-bottom: 6px; }
        .party-title { font-weight: 800; font-size: 15px; color: {{ system_primary_color }}; letter-spacing: .3px; line-height: 1.4; }
        .party-title-om { font-size: 12px; color: #475569; font-weight: 600; margin-top: 1px; }
        .sys-title { font-weight: 900; font-size: 16px; color: #075e54; margin-top: 10px; letter-spacing: .4px; }
        .doc-title { font-size: 12.5px; color: #64748b; font-weight: 700; letter-spacing: 3px; margin-top: 4px; text-transform: uppercase; }

        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px 20px;
            margin: 28px 0 20px;
        }
        .row {
            padding: 12px 14px;
            border-bottom: 1px solid #eef2f7;
            font-size: 14px;
            color: #172033;
            display: flex;
            justify-content: space-between;
            gap: 10px;
        }
        .row .label { font-weight: 700; color: #475569; white-space: nowrap; }
        .row .value { font-weight: 600; color: #075e54; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 65%; }

        .amount { font-size: 30px; font-weight: 900; color: {{ system_primary_color }}; text-align: center; margin: 22px 0 6px; letter-spacing: .5px; }
        .amount .cur { font-size: 18px; color: #475569; }
        .thanks { text-align: center; font-size: 13px; color: #64748b; font-weight: 600; margin-bottom: 10px; }

        .paid-stamp {
            position: absolute;
            right: 25px;
            top: 235px;
            z-index: 5;
            width: 180px;
            height: 110px;
            border: 5px double #e83e8c;
            border-radius: 50%;
            background: rgba(255,255,255,.88);
            color: #e83e8c;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            transform: rotate(-14deg);
            box-shadow: 0 4px 12px rgba(232,62,140,.25);
            line-height: 1.1;
        }
        .paid-stamp .paid-en { font-size: 20px; font-weight: 900; letter-spacing: 2px; text-transform: uppercase; }
        .paid-stamp .paid-am { font-size: 14px; font-weight: 900; letter-spacing: .5px; margin-top: -2px; }
        .paid-stamp .stamp-month {
            margin-top: 3px;
            font-size: 10.5px;
            font-weight: 800;
            letter-spacing: .3px;
            padding: 2px 8px;
            border-radius: 10px;
            background: #e83e8c;
            color: #fff;
            text-transform: uppercase;
        }

        .foot {
            margin-top: 22px;
            padding-top: 14px;
            border-top: 1.5px dashed #cbd5e1;
            font-size: 11px;
            color: #64748b;
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 8px;
            font-weight: 600;
        }
        .btn {
            border: 0;
            border-radius: 10px;
            padding: 12px 24px;
            background: {{ system_primary_color }};
            color: #fff;
            font-weight: 800;
            cursor: pointer;
            font-size: 14px;
            margin-top: 20px;
        }

        @media print {
            body { background: #fff; padding: 0; }
            .receipt { box-shadow: none; border-radius: 0; }
            .no-print { display: none; }
            .receipt::before, .receipt::after, .paid-stamp {
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
        }
    </style>
    </head>
    <body>

    <div class="receipt">

        <div class="head">
            <img class="logo" src="{{ logo }}" alt="Logo">
            <div class="party-title">ብልጽግና ፓርቲ</div>
            <div class="party-title-om">Prosperity Party</div>
            <div class="sys-title">{{ system_title }}</div>
            <div class="doc-title">Payment Receipt · የክፍያ ደረሰኝ</div>
        </div>

        <div class="grid">
            <div class="row">
                <span class="label">Receipt # / ደረሰኝ ቁጥር:</span>
                <span class="value">{{ payment.id }}</span>
            </div>
            <div class="row">
                <span class="label">Date / ቀን:</span>
                <span class="value">{{ payment.payment_date }}</span>
            </div>

            <div class="row">
                <span class="label">Member / አባል:</span>
                <span class="value">{{ payment.fullname }}</span>
            </div>
            <div class="row">
                <span class="label">Phone / ስልክ:</span>
                <span class="value">{{ payment.phone or '-' }}</span>
            </div>

            <div class="row">
                <span class="label">Month / ወር:</span>
                <span class="value">{{ payment.payment_month or '-' }}</span>
            </div>
            <div class="row">
                <span class="label">Method / ዘዴ:</span>
                <span class="value">{{ payment.payment_method or '-' }}</span>
            </div>

            <div class="row">
                <span class="label">Ref / ማጣቀሻ:</span>
                <span class="value">{{ payment.reference_number or '-' }}</span>
            </div>
            <div class="row">
                <span class="label">Status / ሁኔታ:</span>
                <span class="value">{{ payment.status }}</span>
            </div>
        </div>

        <div class="paid-stamp">
            <div class="paid-en">PAID</div>
            <div class="paid-am">ተከፍሏል</div>
            <div class="stamp-month">{{ payment.payment_month or '—' }}</div>
        </div>

        <div class="amount">
            Paid / የተከፈለው: {{ payment.amount }} <span class="cur">ETB</span>
        </div>

        <div class="thanks">Thank you · እናመሰግናለን</div>

        <div class="foot">
            <span>📞 Call On: 0115621721 or 9995</span>
            <span>✉️ info@aaccea.gov.et</span>
            <span>🌐 www.aaccea.gov.et</span>
        </div>

        <div class="no-print" style="text-align:center;">
            <button class="btn" onclick="window.print()">🖨️ Print Receipt</button>
        </div>

    </div>

    </body>
    </html>
    """,
    payment=payment,
    logo=PARTY_LOGO,
    system_title=SYSTEM_TITLE,
    system_primary_color=get_system_settings().get("primary_color", DEFAULT_PRIMARY_COLOR))


# ============================================================
# UPLOADS / HEALTH / 404
# ============================================================

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/health")
def health():
    connection = get_connection(MYSQL_DATABASE)
    if connection:
        connection.close()
        return "<h2>System is running.</h2><p>MySQL: OK</p>"
    return "<h2>System is running.</h2><p>MySQL: FAILED</p>", 500


@app.errorhandler(404)
def not_found(error):
    return page("404", """
        <div class="card center">
            <h1>404</h1>
            <h2>ገጹ አልተገኘም</h2>
            <a href="/" class="btn btn-primary">መነሻ</a>
            <a href="/dashboard" class="btn btn-blue">ዳሽቦርድ</a>
        </div>
    """), 404


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    print("")
    print("==================================================")
    print(" " + SYSTEM_TITLE)
    print("==================================================")

    if setup_database():
        print("")
        print("Login:    " + DEFAULT_ADMIN_USERNAME)
        print("Password: " + DEFAULT_ADMIN_PASSWORD)
        print("")
        print("Public:   http://127.0.0.1:5000/")
        print("Login:    http://127.0.0.1:5000/login")
        print("")
        app.run(host="127.0.0.1", port=5000, debug=True)
    else:
        print("")
        print("Database setup failed. Check XAMPP MySQL.")