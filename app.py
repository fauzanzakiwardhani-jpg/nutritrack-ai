import base64
import hashlib
import io
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai
from PIL import Image
from pydantic import BaseModel, Field

# Model Gemini yang dipakai lewat Interactions API (client.interactions.create).
# Ganti di sini jika Google merilis model lebih baru / model ini dideprecate lagi.
GEMINI_MODEL = "gemini-3.6-flash"

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

try:
    from streamlit_float import float_init
    FLOAT_AVAILABLE = True
except ImportError:
    FLOAT_AVAILABLE = False

# ----------------------------------------------------
# 1. PAGE CONFIGURATION & SETUP
# ----------------------------------------------------
st.set_page_config(
    page_title="AI NutriTrack - Smart Calorie & Health Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    client = genai.Client(api_key=api_key)
else:
    st.error("GEMINI_API_KEY tidak ditemukan di file .env!")

DB_NAME = "gizi_app.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

WATER_QUICK_OPTIONS = [200, 300, 500]

ACTIVITY_OPTIONS = [
    'Sedentari (Jarang olahraga)',
    'Ringan (1-3 hari/minggu)',
    'Sedang (3-5 hari/minggu)',
    'Berat (6-7 hari/minggu)'
]
GOAL_OPTIONS = ['Turunkan Berat Badan', 'Jaga Berat Badan', 'Naikkan Berat Badan']


# ----------------------------------------------------
# 2. CUSTOM CSS INJECTION
# ----------------------------------------------------
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: #f4f7f6;
        color: #0f172a;
    }

    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }

    header[data-testid="stHeader"] {
        background-color: transparent !important;
        z-index: 99999 !important;
    }

    button[data-testid="stSidebarCollapseButton"],
    button[data-testid="baseButton-header"] {
        color: #0f172a !important;
    }

    /* ---------- HAMBURGER TOGGLE ---------- */
    button[data-testid="stSidebarCollapseButton"] svg,
    button[data-testid="stSidebarCollapsedControl"] svg,
    [data-testid="collapsedControl"] svg {
        display: none !important;
    }
    button[data-testid="stSidebarCollapseButton"],
    button[data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        position: relative;
        border-radius: 10px !important;
        transition: background 0.15s ease;
    }
    button[data-testid="stSidebarCollapseButton"]::before,
    button[data-testid="stSidebarCollapsedControl"]::before,
    [data-testid="collapsedControl"]::before {
        content: "☰";
        font-size: 1.35rem;
        line-height: 1;
        color: #0f172a;
        font-weight: 700;
    }
    button[data-testid="stSidebarCollapseButton"]:hover,
    button[data-testid="stSidebarCollapsedControl"]:hover,
    [data-testid="collapsedControl"]:hover {
        background: #ecfdf5 !important;
    }

    /* ---------- SIDEBAR NAV MENU ---------- */
    .nav-heading {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 1rem;
    }
    .nav-heading .text {
        font-weight: 800;
        font-size: 1.05rem;
        color: #0f172a;
        letter-spacing: -0.01em;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] > div[role="radiogroup"] {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label {
        background: #f8fafc;
        border: 1px solid #eef2f1;
        border-radius: 12px;
        padding: 11px 14px;
        margin: 0 !important;
        cursor: pointer;
        font-weight: 600;
        font-size: 0.95rem;
        color: #334155;
        transition: all 0.15s ease;
        width: 100%;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {
        background: #ecfdf5;
        border-color: #a7f3d0;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label > div:first-child {
        display: none;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label div[data-testid="stMarkdownContainer"] p {
        font-size: 0.95rem;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        border-color: #059669;
        box-shadow: 0 4px 10px -2px rgba(16, 185, 129, 0.4);
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) p,
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) div {
        color: #ffffff !important;
    }

    /* ---------- HERO HEADER ---------- */
    .app-header {
        position: relative;
        overflow: hidden;
        background: radial-gradient(120% 160% at 0% 0%, #0d9488 0%, #059669 45%, #10b981 100%);
        padding: 2.4rem 2.6rem;
        border-radius: 22px;
        color: white;
        margin-bottom: 2.2rem;
        box-shadow: 0 20px 40px -12px rgba(5, 150, 105, 0.35);
    }
    .app-header::after {
        content: "";
        position: absolute;
        top: -60px;
        right: -60px;
        width: 220px;
        height: 220px;
        background: rgba(255,255,255,0.10);
        border-radius: 50%;
    }
    .app-header::before {
        content: "";
        position: absolute;
        bottom: -80px;
        right: 120px;
        width: 160px;
        height: 160px;
        background: rgba(255,255,255,0.07);
        border-radius: 50%;
    }
    .app-header h1 {
        color: white !important;
        font-weight: 800;
        font-size: 2.3rem;
        margin: 0;
        letter-spacing: -0.02em;
        position: relative;
        z-index: 2;
    }
    .app-header p {
        color: rgba(255,255,255,0.9);
        font-size: 1rem;
        margin-top: 0.5rem;
        margin-bottom: 0;
        position: relative;
        z-index: 2;
        max-width: 520px;
    }

    /* ---------- SECTION LABELS ---------- */
    .section-label {
        font-size: 0.8rem;
        font-weight: 700;
        color: #059669;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.3rem;
    }

    /* ---------- METRIC CARDS ---------- */
    .metric-card {
        position: relative;
        background: white;
        padding: 1.4rem 1.5rem;
        border-radius: 18px;
        border: 1px solid #eef2f1;
        box-shadow: 0 2px 10px -4px rgba(15, 23, 42, 0.06);
        transition: transform 0.18s ease, box-shadow 0.18s ease;
        overflow: hidden;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 14px 24px -10px rgba(15, 23, 42, 0.12);
    }
    .metric-icon {
        width: 38px;
        height: 38px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.15rem;
        margin-bottom: 0.7rem;
    }
    .metric-label {
        font-size: 0.8rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 1.9rem;
        font-weight: 800;
        color: #0f172a;
        margin-top: 0.2rem;
        letter-spacing: -0.02em;
    }
    .metric-sub {
        font-size: 0.95rem;
        color: #94a3b8;
        font-weight: 600;
    }

    .icon-cal    { background: #d1fae5; color: #059669; }
    .icon-left   { background: #dbeafe; color: #2563eb; }
    .icon-target { background: #fef3c7; color: #d97706; }
    .icon-protein{ background: #dbeafe; color: #2563eb; }
    .icon-carbs  { background: #fef3c7; color: #d97706; }
    .icon-fat    { background: #fee2e2; color: #dc2626; }
    .icon-water  { background: #cffafe; color: #0891b2; }
    .icon-export { background: #ede9fe; color: #7c3aed; }
    .icon-recipe { background: #fce7f3; color: #db2777; }

    .metric-hero {
        background: linear-gradient(160deg, #ecfdf5 0%, #ffffff 55%);
        border: 1px solid #d1fae5;
    }
    .metric-hero-water {
        background: linear-gradient(160deg, #ecfeff 0%, #ffffff 55%);
        border: 1px solid #a5f3fc;
    }

    /* ---------- CUSTOM PROGRESS BAR ---------- */
    .progress-wrap {
        background: #e6ece9;
        border-radius: 999px;
        height: 14px;
        width: 100%;
        overflow: hidden;
        margin: 0.6rem 0 1.6rem 0;
        box-shadow: inset 0 1px 2px rgba(0,0,0,0.04);
    }
    .progress-fill {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #10b981, #34d399);
        transition: width 0.4s ease;
    }
    .progress-fill.over { background: linear-gradient(90deg, #ef4444, #f87171); }
    .progress-fill.water { background: linear-gradient(90deg, #06b6d4, #67e8f9); }
    .progress-fill.protein { background: linear-gradient(90deg, #2563eb, #60a5fa); }
    .progress-fill.carbs { background: linear-gradient(90deg, #d97706, #fbbf24); }
    .progress-fill.fat { background: linear-gradient(90deg, #dc2626, #f87171); }

    .progress-wrap.small { height: 9px; margin: 0.5rem 0 0.2rem 0; }

    div[data-testid="stProgress"] { display: none; }

    /* ---------- AI ADVICE BANNER ---------- */
    .advice-banner {
        border-radius: 16px;
        padding: 1rem 1.3rem;
        font-weight: 500;
        font-size: 0.95rem;
        display: flex;
        align-items: flex-start;
        gap: 10px;
        border: 1px solid transparent;
    }
    .advice-warning { background: #fef2f2; color: #991b1b; border-color: #fecaca; }
    .advice-success { background: #ecfdf5; color: #065f46; border-color: #a7f3d0; }
    .advice-info    { background: #eff6ff; color: #1e3a8a; border-color: #bfdbfe; }

    /* ---------- EMPTY STATE ---------- */
    .empty-state {
        text-align: center;
        padding: 2.6rem 1.5rem;
        background: white;
        border: 1.5px dashed #cbd5e1;
        border-radius: 18px;
        color: #64748b;
    }
    .empty-state .emoji { font-size: 2.2rem; margin-bottom: 0.6rem; }
    .empty-state b { color: #059669; }

    /* ---------- RECIPE CARD ---------- */
    .recipe-card {
        background: white;
        border: 1px solid #eef2f1;
        border-radius: 16px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 8px -4px rgba(15,23,42,0.06);
    }
    .recipe-title {
        font-weight: 800;
        font-size: 1.05rem;
        color: #0f172a;
        margin-bottom: 0.2rem;
    }
    .recipe-macros {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        font-size: 0.82rem;
        font-weight: 700;
        margin: 0.4rem 0 0.5rem 0;
    }
    .recipe-macros span { padding: 3px 10px; border-radius: 999px; }
    .macro-cal { background: #d1fae5; color: #059669; }
    .macro-p { background: #dbeafe; color: #2563eb; }
    .macro-c { background: #fef3c7; color: #d97706; }
    .macro-f { background: #fee2e2; color: #dc2626; }
    .recipe-reason { font-size: 0.9rem; color: #475569; }

    /* ---------- BUTTONS ---------- */
    .stButton>button {
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        border: none;
        box-shadow: 0 6px 14px -4px rgba(16, 185, 129, 0.45);
    }
    .stButton>button[kind="primary"]:hover {
        box-shadow: 0 8px 18px -4px rgba(16, 185, 129, 0.55);
        transform: translateY(-1px);
    }

    /* ---------- SIDEBAR ---------- */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #eef2f1;
    }
    [data-testid="stSidebar"] h3 {
        font-weight: 700;
    }

    /* ---------- EXPANDER LOG ITEM ---------- */
    div[data-testid="stExpander"] {
        border-radius: 14px !important;
        border: 1px solid #eef2f1 !important;
        overflow: hidden;
    }

    /* ---------- AUTH (LOGIN/REGISTER) ---------- */
    .auth-card {
        background: white;
        border-radius: 22px;
        border: 1px solid #eef2f1;
        box-shadow: 0 20px 40px -14px rgba(15, 23, 42, 0.15);
        padding: 2.2rem 2.4rem;
        margin-top: 0.5rem;
    }
    .auth-title {
        font-weight: 800;
        font-size: 1.3rem;
        color: #0f172a;
        margin-bottom: 0.2rem;
    }
    .auth-subtitle {
        font-size: 0.9rem;
        color: #64748b;
        margin-bottom: 1.2rem;
    }

    /* ---------- SIDEBAR USER BADGE ---------- */
    .user-badge {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
        background: #f8fafc;
        border-radius: 14px;
        border: 1px solid #eef2f1;
        margin-bottom: 10px;
    }
    .user-avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: linear-gradient(135deg, #10b981, #059669);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 1.05rem;
        flex-shrink: 0;
    }
    .user-name { font-weight: 700; font-size: 0.92rem; color: #0f172a; line-height: 1.2; }
    .user-username { font-size: 0.78rem; color: #64748b; }

    /* ---------- VIRTUAL ASSISTANT (FLOATING CHAT) ---------- */
    .st-key-va_toggle_btn button {
        width: 58px !important;
        height: 58px !important;
        border-radius: 50% !important;
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        border: none !important;
        box-shadow: 0 10px 24px -6px rgba(5, 150, 105, 0.5) !important;
        font-size: 1.5rem !important;
        color: white !important;
        padding: 0 !important;
        transition: transform 0.15s ease !important;
    }
    .st-key-va_toggle_btn button:hover {
        transform: scale(1.06);
    }
    .st-key-va_panel {
        background: white;
        border-radius: 20px;
        border: 1px solid #eef2f1;
        box-shadow: 0 24px 48px -12px rgba(15, 23, 42, 0.25);
        padding: 0;
        overflow: hidden;
    }
    .va-header {
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        color: white;
        font-weight: 800;
        font-size: 0.95rem;
        padding: 14px 18px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .va-body-wrap { padding: 10px 14px 4px 14px; }
    .va-hint {
        font-size: 0.78rem;
        color: #94a3b8;
        padding: 0 14px 10px 14px;
    }
    .st-key-va_input_box input {
        border-radius: 999px !important;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ----------------------------------------------------
# 3. SCHEMA STRUCTURED OUTPUT (PYDANTIC)
# ----------------------------------------------------
class NutritionAnalysis(BaseModel):
    food_name: str = Field(description="Nama makanan dalam Bahasa Indonesia")
    estimated_weight_g: float = Field(description="Estimasi berat porsi dalam gram")
    calories: float = Field(description="Total kalori dalam kcal")
    protein_g: float = Field(description="Kandungan protein dalam gram")
    carbs_g: float = Field(description="Kandungan karbohidrat dalam gram")
    fat_g: float = Field(description="Kandungan lemak dalam gram")
    ai_feedback: str = Field(description="Ulasan gizi dan saran singkat dalam Bahasa Indonesia")


class RecipeIdea(BaseModel):
    name: str = Field(description="Nama resep/menu dalam Bahasa Indonesia")
    estimated_calories: float = Field(description="Estimasi kalori dalam kcal")
    protein_g: float = Field(description="Estimasi protein dalam gram")
    carbs_g: float = Field(description="Estimasi karbohidrat dalam gram")
    fat_g: float = Field(description="Estimasi lemak dalam gram")
    reason: str = Field(description="Alasan singkat kenapa menu ini cocok untuk sisa kuota pengguna")


class RecipeSuggestions(BaseModel):
    recipes: list[RecipeIdea] = Field(description="Daftar 3 ide resep/menu makanan sehat")


# ----------------------------------------------------
# 4. PASSWORD HASHING (stdlib only — hashlib.pbkdf2_hmac + salt acak)
# ----------------------------------------------------
PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f"{salt}:{pwd_hash.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hash_hex = stored_hash.split(":")
    except (ValueError, AttributeError, TypeError):
        return False
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return secrets.compare_digest(pwd_hash.hex(), hash_hex)


# ----------------------------------------------------
# 5. DATABASE INITIALIZATION
# ----------------------------------------------------
def ensure_column(cursor, table, column, col_type_with_default):
    cursor.execute(f"PRAGMA table_info({table})")
    existing_cols = [row[1] for row in cursor.fetchall()]
    if column not in existing_cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type_with_default}")


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                email TEXT,
                password_hash TEXT,
                name TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                height_cm REAL,
                weight_kg REAL,
                activity_level TEXT,
                goal TEXT,
                target_calories REAL,
                target_protein_g REAL,
                target_carbs_g REAL,
                target_fat_g REAL,
                custom_macro_mode INTEGER DEFAULT 0,
                target_water_ml REAL DEFAULT 2000,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                food_name TEXT,
                weight_g REAL,
                calories REAL,
                protein_g REAL,
                carbs_g REAL,
                fat_g REAL,
                ai_feedback TEXT,
                image_path TEXT,
                input_method TEXT,
                logged_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS water_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount_ml REAL,
                logged_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Migrasi kolom baru untuk instalasi lama (aman dijalankan berkali-kali)
        ensure_column(cursor, "users", "username", "TEXT")
        ensure_column(cursor, "users", "email", "TEXT")
        ensure_column(cursor, "users", "password_hash", "TEXT")
        ensure_column(cursor, "users", "target_protein_g", "REAL")
        ensure_column(cursor, "users", "target_carbs_g", "REAL")
        ensure_column(cursor, "users", "target_fat_g", "REAL")
        ensure_column(cursor, "users", "custom_macro_mode", "INTEGER DEFAULT 0")
        ensure_column(cursor, "users", "target_water_ml", "REAL DEFAULT 2000")
        # Catatan: SQLite tidak izinkan ekspresi/fungsi sebagai default saat ALTER TABLE ADD COLUMN
        # (hanya boleh konstanta), jadi kolom lama cukup NULL — nilai baru tetap terisi otomatis
        # untuk akun yang didaftarkan setelah ini (lihat CREATE TABLE di atas).
        ensure_column(cursor, "users", "created_at", "TIMESTAMP")

        # Index unik untuk username & email (NULL boleh berulang di SQLite, jadi aman untuk data lama)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")

        conn.commit()

init_db()


# ----------------------------------------------------
# 6. CALCULATOR & AUTH HELPERS
# ----------------------------------------------------
def calculate_target(weight_kg, height_cm, age, gender, activity_level, goal):
    if gender == 'Laki-laki':
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

    multipliers = {
        'Sedentari (Jarang olahraga)': 1.2,
        'Ringan (1-3 hari/minggu)': 1.375,
        'Sedang (3-5 hari/minggu)': 1.55,
        'Berat (6-7 hari/minggu)': 1.725
    }
    tdee = bmr * multipliers.get(activity_level, 1.2)
    adjustments = {
        'Turunkan Berat Badan': -400,
        'Jaga Berat Badan': 0,
        'Naikkan Berat Badan': 400
    }
    return round(tdee + adjustments.get(goal, 0))


def default_macro_split(target_calories):
    """Split default 30% protein / 40% karbo / 30% lemak dari total target kalori."""
    protein_g = round((target_calories * 0.30) / 4)
    carbs_g = round((target_calories * 0.40) / 4)
    fat_g = round((target_calories * 0.30) / 9)
    return protein_g, carbs_g, fat_g


def get_user_by_id(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
    return dict(row) if row else None


def get_user_by_identifier(identifier):
    """Cari user berdasarkan username ATAU email (untuk login)."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?", (identifier, identifier))
        row = cursor.fetchone()
    return dict(row) if row else None


def create_user(username, email, password, name, age, gender, height_cm, weight_kg, activity_level, goal):
    """Buat akun baru. Melempar sqlite3.IntegrityError jika username/email sudah dipakai."""
    target_cal = calculate_target(weight_kg, height_cm, age, gender, activity_level, goal)
    auto_p, auto_c, auto_f = default_macro_split(target_cal)
    pwd_hash = hash_password(password)

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, name, age, gender, height_cm, weight_kg,
                                activity_level, goal, target_calories, target_protein_g, target_carbs_g,
                                target_fat_g, custom_macro_mode, target_water_ml)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 2000)
        ''', (username, email, pwd_hash, name, age, gender, height_cm, weight_kg, activity_level, goal,
              target_cal, auto_p, auto_c, auto_f))
        conn.commit()
        return cursor.lastrowid


# ----------------------------------------------------
# 7. HEADER BANNER (selalu tampil, termasuk di halaman login)
# ----------------------------------------------------
st.markdown("""
<div class="app-header">
    <h1>NutriTrack AI</h1>
    <p>Asisten AI Pengenal Gizi, Pengukur Kalori & Analisis Nutrisi Harian — cukup foto makananmu, sisanya biar AI yang hitung.</p>
</div>
""", unsafe_allow_html=True)


# ----------------------------------------------------
# 8. AUTH GATE — LOGIN & REGISTRASI
# ----------------------------------------------------
if "logged_in_user_id" not in st.session_state:
    st.session_state.logged_in_user_id = None

if st.session_state.logged_in_user_id is None:
    col_a, col_b, col_c = st.columns([1, 1.4, 1])
    with col_b:
        st.markdown('<div class="auth-card">', unsafe_allow_html=True)
        tab_login, tab_register = st.tabs(["Login", "Daftar Akun"])

        with tab_login:
            st.markdown('<div class="auth-title">Selamat Datang Kembali</div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-subtitle">Masuk untuk melanjutkan pelacakan gizi kamu.</div>', unsafe_allow_html=True)
            with st.form("login_form"):
                login_id = st.text_input("Username atau Email")
                login_pw = st.text_input("Password", type="password")
                login_submit = st.form_submit_button("Masuk", type="primary", use_container_width=True)

                if login_submit:
                    if not login_id.strip() or not login_pw:
                        st.error("Username/email dan password wajib diisi.")
                    else:
                        user = get_user_by_identifier(login_id.strip())
                        if user and verify_password(login_pw, user.get("password_hash")):
                            st.session_state.logged_in_user_id = user["id"]
                            st.rerun()
                        else:
                            st.error("Username/email atau password salah.")

        with tab_register:
            st.markdown('<div class="auth-title">Buat Akun Baru</div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-subtitle">Isi data diri untuk menghitung target kalori otomatis.</div>', unsafe_allow_html=True)
            with st.form("register_form"):
                r_name = st.text_input("Nama Lengkap")
                rc1, rc2 = st.columns(2)
                with rc1:
                    r_username = st.text_input("Username")
                with rc2:
                    r_email = st.text_input("Email")

                rc3, rc4 = st.columns(2)
                with rc3:
                    r_password = st.text_input("Password", type="password")
                with rc4:
                    r_password_confirm = st.text_input("Konfirmasi Password", type="password")

                rc5, rc6 = st.columns(2)
                with rc5:
                    r_age = st.number_input("Usia (tahun)", 10, 100, 22)
                    r_height = st.number_input("Tinggi Badan (cm)", 100.0, 250.0, 165.0)
                    r_activity = st.selectbox("Tingkat Aktivitas", ACTIVITY_OPTIONS)
                with rc6:
                    r_gender = st.selectbox("Jenis Kelamin", ["Laki-laki", "Perempuan"])
                    r_weight = st.number_input("Berat Badan (kg)", 30.0, 200.0, 60.0)
                    r_goal = st.selectbox("Target Kesehatan", GOAL_OPTIONS)

                register_submit = st.form_submit_button("Daftar", type="primary", use_container_width=True)

                if register_submit:
                    errors = []
                    if not r_name.strip():
                        errors.append("Nama tidak boleh kosong.")
                    if not r_username.strip():
                        errors.append("Username tidak boleh kosong.")
                    if not r_email.strip() or "@" not in r_email:
                        errors.append("Email tidak valid.")
                    if len(r_password) < 6:
                        errors.append("Password minimal 6 karakter.")
                    if r_password != r_password_confirm:
                        errors.append("Konfirmasi password tidak cocok.")

                    if errors:
                        for e in errors:
                            st.error(e)
                    else:
                        try:
                            new_id = create_user(
                                r_username.strip(), r_email.strip(), r_password, r_name.strip(),
                                r_age, r_gender, r_height, r_weight, r_activity, r_goal
                            )
                            st.session_state.logged_in_user_id = new_id
                            st.success("Akun berhasil dibuat! Selamat datang di NutriTrack AI 🎉")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Username atau email sudah terdaftar. Coba yang lain.")

        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()  # Hentikan render lebih lanjut — sidebar & fitur utama hanya untuk yang sudah login


# ----------------------------------------------------
# 9. AMBIL DATA USER YANG SEDANG LOGIN
# ----------------------------------------------------
active_user = get_user_by_id(st.session_state.logged_in_user_id)

if active_user is None:
    # Akun tidak ditemukan (edge case) — paksa logout
    st.session_state.logged_in_user_id = None
    st.rerun()

active_user_id = active_user["id"]
default_goal = active_user["goal"] or "Jaga Berat Badan"


# ----------------------------------------------------
# 10. SIDEBAR NAVIGATION & PROFILE MANAGEMENT
# ----------------------------------------------------
with st.sidebar:
    initial_letter = (active_user["name"] or "?").strip()[:1].upper()
    st.markdown(f"""
    <div class="user-badge">
        <div class="user-avatar">{initial_letter}</div>
        <div>
            <div class="user-name">{active_user['name']}</div>
            <div class="user-username">@{active_user['username'] or '-'}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.divider()
    st.markdown("""
    <div class="nav-heading">
        <span class="text">Menu</span>
    </div>
    """, unsafe_allow_html=True)

    menu_options = ["Log & Rekomendasi", "Input Makanan", "Hidrasi", "Analytics & Trend", "Export Data"]
    menu_raw = st.radio(
        "Pilih Halaman:",
        menu_options,
        index=0,
        label_visibility="collapsed"
    )
    menu_selection = menu_raw

    st.divider()
    st.markdown("### 👤 Profil")

    name = st.text_input("Nama Pengguna", active_user["name"])
    age = st.number_input("Usia (tahun)", 10, 100, int(active_user["age"] or 22))
    gender = st.selectbox("Jenis Kelamin", ["Laki-laki", "Perempuan"], index=0 if active_user["gender"] == "Laki-laki" else 1)
    height = st.number_input("Tinggi Badan (cm)", 100.0, 250.0, float(active_user["height_cm"] or 170.0))
    weight = st.number_input("Berat Badan (kg)", 30.0, 200.0, float(active_user["weight_kg"] or 65.0))

    activity = st.selectbox(
        "Aktivitas Harian", ACTIVITY_OPTIONS,
        index=ACTIVITY_OPTIONS.index(active_user["activity_level"]) if active_user["activity_level"] in ACTIVITY_OPTIONS else 0
    )
    goal = st.selectbox(
        "Target Kesehatan", GOAL_OPTIONS,
        index=GOAL_OPTIONS.index(active_user["goal"]) if active_user["goal"] in GOAL_OPTIONS else 0
    )

    st.divider()
    st.markdown("### 🎯 Target Makronutrisi")
    custom_macro_mode = st.checkbox(
        "Gunakan target makro kustom (Keto / Bulking / Low Carb, dll)",
        value=bool(active_user["custom_macro_mode"])
    )

    current_target_calories = active_user["target_calories"] or 1800
    auto_p, auto_c, auto_f = default_macro_split(current_target_calories)

    if custom_macro_mode:
        target_protein_g = st.number_input("Target Protein (g)", 0.0, 400.0, float(active_user["target_protein_g"] or auto_p))
        target_carbs_g = st.number_input("Target Karbohidrat (g)", 0.0, 600.0, float(active_user["target_carbs_g"] or auto_c))
        target_fat_g = st.number_input("Target Lemak (g)", 0.0, 300.0, float(active_user["target_fat_g"] or auto_f))
    else:
        target_protein_g, target_carbs_g, target_fat_g = auto_p, auto_c, auto_f
        st.caption(f"Otomatis dari target kalori: Protein {auto_p}g · Karbo {auto_c}g · Lemak {auto_f}g")

    st.divider()
    st.markdown("### 💧 Target Hidrasi")
    target_water_ml = st.number_input("Target Air Harian (ml)", 500, 5000, int(active_user["target_water_ml"] or 2000), step=100)

    if st.button("Simpan & Hitung Ulang", use_container_width=True, type="primary"):
        target_cal = calculate_target(weight, height, age, gender, activity, goal)
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET
                    name = ?, age = ?, gender = ?, height_cm = ?, weight_kg = ?,
                    activity_level = ?, goal = ?, target_calories = ?,
                    target_protein_g = ?, target_carbs_g = ?, target_fat_g = ?,
                    custom_macro_mode = ?, target_water_ml = ?
                WHERE id = ?
            ''', (name, age, gender, height, weight, activity, goal, target_cal,
                  target_protein_g, target_carbs_g, target_fat_g,
                  1 if custom_macro_mode else 0, target_water_ml, active_user_id))
            conn.commit()
        st.success(f"Profil diperbarui! Target baru: {target_cal} kcal/hari")
        st.rerun()

    st.divider()
    st.markdown("Pengaturan Data")
    if st.button("Reset Riwayat Saya", type="secondary", use_container_width=True):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT image_path FROM daily_logs WHERE user_id = ? AND image_path IS NOT NULL", (active_user_id,))
            image_paths = [r[0] for r in cursor.fetchall()]
            cursor.execute("DELETE FROM daily_logs WHERE user_id = ?", (active_user_id,))
            cursor.execute("DELETE FROM water_logs WHERE user_id = ?", (active_user_id,))
            conn.commit()

        for p in image_paths:
            if p and os.path.exists(p):
                os.remove(p)

        st.toast("Riwayat log & hidrasi kamu berhasil dibersihkan!", icon="🧹")
        st.rerun()
    st.caption("Hanya menghapus riwayat makanan & air kamu. Akun & profil tetap tersimpan.")


# ----------------------------------------------------
# 11. MAIN CONTENT ROUTING
# ----------------------------------------------------

# ====================================================
# PAGE 1: HALAMAN UTAMA (LOG HARIAN & REKOMENDASI)
# ====================================================
if "Log & Rekomendasi" in menu_selection:
    today_str = datetime.now().strftime('%Y-%m-%d')
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT SUM(calories), SUM(protein_g), SUM(carbs_g), SUM(fat_g) FROM daily_logs WHERE user_id = ? AND DATE(logged_at) = ?",
            (active_user_id, today_str)
        )
        totals = cursor.fetchone()

        cursor.execute("""
            SELECT target_calories, target_protein_g, target_carbs_g, target_fat_g, custom_macro_mode
            FROM users WHERE id = ?
        """, (active_user_id,))
        user_target_row = cursor.fetchone()

        cursor.execute(
            "SELECT id, food_name, weight_g, calories, protein_g, carbs_g, fat_g, ai_feedback, input_method, logged_at, image_path "
            "FROM daily_logs WHERE user_id = ? AND DATE(logged_at) = ? ORDER BY id DESC",
            (active_user_id, today_str)
        )
        logs = cursor.fetchall()

    total_cals = totals[0] if totals and totals[0] else 0.0
    total_protein = totals[1] if totals and totals[1] else 0.0
    total_carbs = totals[2] if totals and totals[2] else 0.0
    total_fat = totals[3] if totals and totals[3] else 0.0

    target = user_target_row[0] if user_target_row and user_target_row[0] else 2000.0
    macro_target_protein = user_target_row[1] if user_target_row and user_target_row[1] else target_protein_g
    macro_target_carbs = user_target_row[2] if user_target_row and user_target_row[2] else target_carbs_g
    macro_target_fat = user_target_row[3] if user_target_row and user_target_row[3] else target_fat_g
    is_custom_macro = bool(user_target_row[4]) if user_target_row and user_target_row[4] is not None else False

    sisa = target - total_cals

    st.markdown('<div class="section-label">Ringkasan</div>', unsafe_allow_html=True)
    st.markdown("### Kalori Hari Ini")

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f"""
        <div class="metric-card metric-hero">
            <div class="metric-icon icon-cal">🔥</div>
            <div class="metric-label">Asupan Kalori</div>
            <div class="metric-value">{total_cals:.0f} <span class="metric-sub">/ {target:.0f} kcal</span></div>
        </div>
        """, unsafe_allow_html=True)

    with k2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon icon-left">⚡</div>
            <div class="metric-label">Sisa Kuota Kalori</div>
            <div class="metric-value" style="color: {'#059669' if sisa >= 0 else '#dc2626'};">{sisa:.0f} <span class="metric-sub">kcal</span></div>
        </div>
        """, unsafe_allow_html=True)

    with k3:
        pct = min((total_cals / target) * 100, 100) if target > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon icon-target">🎯</div>
            <div class="metric-label">Pencapaian Target</div>
            <div class="metric-value">{pct:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    pct_width = min((total_cals / target) * 100, 100) if target > 0 else 0
    bar_class = "over" if sisa < 0 else ""
    st.markdown(f"""
    <div class="progress-wrap">
        <div class="progress-fill {bar_class}" style="width: {pct_width}%;"></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-label">Detail</div>', unsafe_allow_html=True)
    label_makro = "#### Rincian Makronutrisi" + (" (vs Target Kustom)" if is_custom_macro else "")
    st.markdown(label_makro)

    m1, m2, m3 = st.columns(3)
    with m1:
        p_pct = min((total_protein / macro_target_protein) * 100, 100) if macro_target_protein > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon icon-protein">🍗</div>
            <div class="metric-label">Protein</div>
            <div class="metric-value">{total_protein:.1f} <span class="metric-sub">/ {macro_target_protein:.0f} g</span></div>
            <div class="progress-wrap small"><div class="progress-fill protein" style="width:{p_pct}%;"></div></div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        c_pct = min((total_carbs / macro_target_carbs) * 100, 100) if macro_target_carbs > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon icon-carbs">🍞</div>
            <div class="metric-label">Karbohidrat</div>
            <div class="metric-value">{total_carbs:.1f} <span class="metric-sub">/ {macro_target_carbs:.0f} g</span></div>
            <div class="progress-wrap small"><div class="progress-fill carbs" style="width:{c_pct}%;"></div></div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        f_pct = min((total_fat / macro_target_fat) * 100, 100) if macro_target_fat > 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon icon-fat">🥑</div>
            <div class="metric-label">Lemak</div>
            <div class="metric-value">{total_fat:.1f} <span class="metric-sub">/ {macro_target_fat:.0f} g</span></div>
            <div class="progress-wrap small"><div class="progress-fill fat" style="width:{f_pct}%;"></div></div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()

    # SECTION REKOMENDASI AI
    st.markdown('<div class="section-label">Insight</div>', unsafe_allow_html=True)
    st.markdown("### Rekomendasi & Evaluasi AI")
    if total_cals == 0:
        st.markdown("""
        <div class="empty-state">
            <div class="emoji">🍽️</div>
            Belum ada makanan yang dicatat hari ini.<br>
            Buka menu <b>Input Makanan</b> di sidebar untuk memulai!
        </div>
        """, unsafe_allow_html=True)
    else:
        if sisa < 0:
            st.markdown(f"""
            <div class="advice-banner advice-warning">
                ⚠️ <div><b>Perhatian:</b> Anda melebihi target harian sebesar {abs(sisa):.0f} kcal.
                Pertimbangkan untuk memilih makanan rendah kalori untuk sisa hari ini.</div>
            </div>
            """, unsafe_allow_html=True)
        elif sisa < 300:
            st.markdown("""
            <div class="advice-banner advice-success">
                ✅ <div><b>Bagus!</b> Asupan kalori Anda sudah mendekati target harian secara ideal.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="advice-banner advice-info">
                💡 <div><b>Info:</b> Anda masih memiliki sisa kuota kalori sebesar {sisa:.0f} kcal.</div>
            </div>
            """, unsafe_allow_html=True)

    # ---------- AI RECIPE SUGGESTIONS ----------
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 🍲 Rekomendasi Resep AI")
    if sisa <= 0:
        st.caption("Sisa kuota kalori sudah habis/negatif — rekomendasi resep tersedia setelah ada sisa kuota.")
    else:
        sisa_protein = max(macro_target_protein - total_protein, 0)
        sisa_carbs = max(macro_target_carbs - total_carbs, 0)
        sisa_fat = max(macro_target_fat - total_fat, 0)

        if st.button("✨ Cari Ide Menu Sehat", type="primary"):
            if not api_key:
                st.error("API Key belum terkonfigurasi!")
            else:
                with st.spinner("Menyusun ide menu berdasarkan sisa kuota kalori & makro Anda..."):
                    try:
                        recipe_prompt = f"""
                        Berikan 3 ide resep/menu makanan sehat khas Indonesia dalam Bahasa Indonesia,
                        yang cocok dengan sisa kuota gizi pengguna hari ini:
                        - Sisa kalori: {sisa:.0f} kcal
                        - Sisa protein: {sisa_protein:.0f} g
                        - Sisa karbohidrat: {sisa_carbs:.0f} g
                        - Sisa lemak: {sisa_fat:.0f} g
                        - Target kesehatan pengguna: {default_goal}

                        Setiap resep harus muat dalam sisa kuota kalori tersebut (tidak melebihi).
                        Sertakan alasan singkat kenapa menu tersebut cocok.
                        """
                        interaction = client.interactions.create(
                            model=GEMINI_MODEL,
                            input=recipe_prompt,
                            response_format={
                                "type": "text",
                                "mime_type": "application/json",
                                "schema": RecipeSuggestions.model_json_schema(),
                            },
                        )
                        parsed_recipes = RecipeSuggestions.model_validate_json(interaction.output_text)
                        st.session_state["recipe_suggestions"] = parsed_recipes.recipes
                    except Exception as e:
                        st.error(f"Terjadi kesalahan saat mengambil rekomendasi: {e}")

        if "recipe_suggestions" in st.session_state:
            for recipe in st.session_state["recipe_suggestions"]:
                st.markdown(f"""
                <div class="recipe-card">
                    <div class="recipe-title">🍽️ {recipe.name}</div>
                    <div class="recipe-macros">
                        <span class="macro-cal">{recipe.estimated_calories:.0f} kcal</span>
                        <span class="macro-p">P {recipe.protein_g:.0f}g</span>
                        <span class="macro-c">K {recipe.carbs_g:.0f}g</span>
                        <span class="macro-f">L {recipe.fat_g:.0f}g</span>
                    </div>
                    <div class="recipe-reason">{recipe.reason}</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">Riwayat</div>', unsafe_allow_html=True)
    st.markdown("### Log Makanan Hari Ini")

    if logs:
        for log in logs:
            log_id, food_name, weight_g, calories, protein_g, carbs_g, fat_g, ai_eval, method, logged_at, img_path = log

            with st.expander(f"🍽️ {food_name} — {calories:.0f} kcal ({logged_at[-8:-3]})"):
                col_a, col_b = st.columns([3, 1])

                with col_a:
                    method_labels = {
                        "ai_photo": "📸 AI Photo",
                        "ai_text": "⌨️ AI Text",
                        "manual": "✍️ Manual"
                    }
                    method_label = method_labels.get(method, method)
                    st.write(f"**Porsi:** {weight_g} gram &nbsp;·&nbsp; **Input:** {method_label}")
                    st.write(f"**Nutrisi:** Protein {protein_g}g · Karbo {carbs_g}g · Lemak {fat_g}g")
                    st.info(f"**AI Feedback:** {ai_eval if ai_eval else 'Tidak ada catatan.'}")
                    if img_path and os.path.exists(img_path):
                        st.image(img_path, width=160)

                with col_b:
                    if st.button("🗑️ Hapus Log", key=f"del_{log_id}", type="secondary"):
                        with sqlite3.connect(DB_NAME) as conn:
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM daily_logs WHERE id = ? AND user_id = ?", (log_id, active_user_id))
                            conn.commit()

                        if img_path and os.path.exists(img_path):
                            os.remove(img_path)

                        st.toast(f"'{food_name}' telah dihapus.")
                        st.rerun()
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="emoji">📋</div>
            Belum ada riwayat konsumsi yang dicatat hari ini.
        </div>
        """, unsafe_allow_html=True)


# ====================================================
# PAGE 2: INPUT MAKANAN
# ====================================================
elif "Input Makanan" in menu_selection:
    st.markdown('<div class="section-label">Logging</div>', unsafe_allow_html=True)
    st.markdown("### Catat Makanan Kamu")
    input_type = st.radio(
        "Pilih Metode Logging:",
        ["Scan Foto Makanan (AI Vision)", "Ketik Teks (AI Text)", "Input Manual"],
        horizontal=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    if input_type == "Scan Foto Makanan (AI Vision)":
        uploaded_file = st.file_uploader("Unggah foto hidangan kamu di sini", type=["jpg", "jpeg", "png"])

        if uploaded_file:
            col_img, col_info = st.columns([1, 2])
            image = Image.open(uploaded_file)

            with col_img:
                st.image(image, caption="Foto yang Diunggah", use_container_width=True)

            with col_info:
                st.info("Pindai gambar dengan Gemini AI Vision untuk menghitung estimasi kalori dan makronutrisi secara otomatis.")
                if st.button("✨ Analisis Nutrisi dengan AI", type="primary", use_container_width=True):
                    if not api_key:
                        st.error("API Key belum terkonfigurasi!")
                    else:
                        with st.spinner("Menganalisis jenis makanan & kandungan nutrisi..."):
                            try:
                                prompt = f"Identifikasi makanan ini secara presisi dan berikan analisis nutrisi serta feedback singkat dalam Bahasa Indonesia untuk pengguna dengan target kesehatan: '{default_goal}'."

                                image_bytes = uploaded_file.getvalue()
                                image_mime = uploaded_file.type or "image/jpeg"

                                interaction = client.interactions.create(
                                    model=GEMINI_MODEL,
                                    input=[
                                        {"type": "text", "text": prompt},
                                        {"type": "image", "data": base64.b64encode(image_bytes).decode('utf-8'), "mime_type": image_mime},
                                    ],
                                    response_format={
                                        "type": "text",
                                        "mime_type": "application/json",
                                        "schema": NutritionAnalysis.model_json_schema(),
                                    },
                                )

                                parsed_data = NutritionAnalysis.model_validate_json(interaction.output_text)

                                now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                                file_path = os.path.join(UPLOAD_DIR, f"{now_str}_{uploaded_file.name}")
                                image.save(file_path)

                                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                                with sqlite3.connect(DB_NAME) as conn:
                                    cursor = conn.cursor()
                                    cursor.execute('''
                                        INSERT INTO daily_logs (user_id, food_name, weight_g, calories, protein_g, carbs_g, fat_g, ai_feedback, image_path, input_method, logged_at)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ai_photo', ?)
                                    ''', (
                                        active_user_id,
                                        parsed_data.food_name,
                                        parsed_data.estimated_weight_g,
                                        parsed_data.calories,
                                        parsed_data.protein_g,
                                        parsed_data.carbs_g,
                                        parsed_data.fat_g,
                                        parsed_data.ai_feedback,
                                        file_path,
                                        current_time
                                    ))
                                    conn.commit()

                                st.balloons()
                                st.success(f"Berhasil mencatat: **{parsed_data.food_name}** ({parsed_data.calories} kcal)")
                            except Exception as e:
                                st.error(f"Terjadi kesalahan analisis: {e}")

    elif input_type == "Ketik Teks (AI Text)":
        st.info("Ketik apa yang kamu makan secara bebas, contoh: *\"Makan soto ayam 1 porsi sama nasi putih setengah\"*. AI akan mengestimasi kalori dan makronutrisinya.")
        text_input = st.text_area("Deskripsikan makanan kamu:", placeholder="Contoh: Nasi goreng seporsi + telur ceplok + es teh manis", height=100)

        if st.button("✨ Analisis Teks dengan AI", type="primary", use_container_width=True):
            if not api_key:
                st.error("API Key belum terkonfigurasi!")
            elif not text_input.strip():
                st.warning("Tolong isi deskripsi makanan terlebih dahulu.")
            else:
                with st.spinner("Menganalisis deskripsi makanan..."):
                    try:
                        prompt = f"""
                        Berdasarkan deskripsi makanan berikut dari pengguna: "{text_input}"
                        Identifikasi makanan tersebut secara presisi dan berikan analisis nutrisi
                        serta feedback singkat dalam Bahasa Indonesia untuk pengguna dengan
                        target kesehatan: '{default_goal}'. Jika ada beberapa item makanan,
                        jumlahkan menjadi satu estimasi total.
                        """
                        interaction = client.interactions.create(
                            model=GEMINI_MODEL,
                            input=prompt,
                            response_format={
                                "type": "text",
                                "mime_type": "application/json",
                                "schema": NutritionAnalysis.model_json_schema(),
                            },
                        )
                        parsed_data = NutritionAnalysis.model_validate_json(interaction.output_text)
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        with sqlite3.connect(DB_NAME) as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO daily_logs (user_id, food_name, weight_g, calories, protein_g, carbs_g, fat_g, ai_feedback, image_path, input_method, logged_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'ai_text', ?)
                            ''', (
                                active_user_id,
                                parsed_data.food_name,
                                parsed_data.estimated_weight_g,
                                parsed_data.calories,
                                parsed_data.protein_g,
                                parsed_data.carbs_g,
                                parsed_data.fat_g,
                                parsed_data.ai_feedback,
                                current_time
                            ))
                            conn.commit()

                        st.balloons()
                        st.success(f"Berhasil mencatat: **{parsed_data.food_name}** ({parsed_data.calories} kcal)")
                    except Exception as e:
                        st.error(f"Terjadi kesalahan analisis: {e}")

    else:
        with st.form("manual_form", clear_on_submit=True):
            st.markdown("##### Form Input Detail Makanan")
            c1, c2 = st.columns(2)
            with c1:
                food_name = st.text_input("Nama Makanan", placeholder="Contoh: Ayam Bakar Dada")
                weight_g = st.number_input("Estimasi Berat (gram)", 10, 1000, 150)
                cals = st.number_input("Kalori Total (kcal)", 0, 3000, 250)
            with c2:
                protein = st.number_input("Protein (gram)", 0.0, 300.0, 25.0)
                carbs = st.number_input("Karbohidrat (gram)", 0.0, 500.0, 10.0)
                fat = st.number_input("Lemak (gram)", 0.0, 300.0, 8.0)

            feedback = st.text_input("Catatan Pribadi", "Input manual pengguna.")

            submit = st.form_submit_button("Tambahkan ke Log", type="primary", use_container_width=True)
            if submit:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with sqlite3.connect(DB_NAME) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO daily_logs (user_id, food_name, weight_g, calories, protein_g, carbs_g, fat_g, ai_feedback, input_method, logged_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?)
                    ''', (active_user_id, food_name, weight_g, cals, protein, carbs, fat, feedback, current_time))
                    conn.commit()
                st.toast("Makanan berhasil ditambahkan!", icon="✅")


# ====================================================
# PAGE 3: HIDRASI (WATER TRACKER)
# ====================================================
elif "Hidrasi" in menu_selection:
    today_str = datetime.now().strftime('%Y-%m-%d')

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT SUM(amount_ml) FROM water_logs WHERE user_id = ? AND DATE(logged_at) = ?",
            (active_user_id, today_str)
        )
        water_total_row = cursor.fetchone()
        cursor.execute(
            "SELECT id, amount_ml, logged_at FROM water_logs WHERE user_id = ? AND DATE(logged_at) = ? ORDER BY id DESC",
            (active_user_id, today_str)
        )
        water_logs = cursor.fetchall()

    total_water = water_total_row[0] if water_total_row and water_total_row[0] else 0.0
    sisa_water = max(target_water_ml - total_water, 0)
    water_pct = min((total_water / target_water_ml) * 100, 100) if target_water_ml > 0 else 0

    st.markdown('<div class="section-label">Hidrasi</div>', unsafe_allow_html=True)
    st.markdown("### 💧 Pencatat Asupan Air Harian")

    w1, w2, w3 = st.columns(3)
    with w1:
        st.markdown(f"""
        <div class="metric-card metric-hero-water">
            <div class="metric-icon icon-water">💧</div>
            <div class="metric-label">Total Minum Hari Ini</div>
            <div class="metric-value">{total_water:.0f} <span class="metric-sub">/ {target_water_ml:.0f} ml</span></div>
        </div>
        """, unsafe_allow_html=True)
    with w2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon icon-water">🥤</div>
            <div class="metric-label">Sisa Target</div>
            <div class="metric-value">{sisa_water:.0f} <span class="metric-sub">ml</span></div>
        </div>
        """, unsafe_allow_html=True)
    with w3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-icon icon-target">🎯</div>
            <div class="metric-label">Pencapaian</div>
            <div class="metric-value">{water_pct:.0f}%</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="progress-wrap">
        <div class="progress-fill water" style="width: {water_pct}%;"></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### Tambah Cepat")
    quick_cols = st.columns(len(WATER_QUICK_OPTIONS) + 1)
    for i, amount in enumerate(WATER_QUICK_OPTIONS):
        with quick_cols[i]:
            if st.button(f"+{amount} ml", key=f"water_quick_{amount}", use_container_width=True):
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with sqlite3.connect(DB_NAME) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO water_logs (user_id, amount_ml, logged_at) VALUES (?, ?, ?)",
                        (active_user_id, amount, current_time)
                    )
                    conn.commit()
                st.toast(f"+{amount} ml air ditambahkan!", icon="💧")
                st.rerun()

    with quick_cols[-1]:
        with st.popover("Jumlah Lain", use_container_width=True):
            custom_amount = st.number_input("Jumlah (ml)", 10, 2000, 150, step=10, key="custom_water_amount")
            if st.button("Tambahkan", key="add_custom_water", type="primary", use_container_width=True):
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with sqlite3.connect(DB_NAME) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO water_logs (user_id, amount_ml, logged_at) VALUES (?, ?, ?)",
                        (active_user_id, custom_amount, current_time)
                    )
                    conn.commit()
                st.toast(f"+{custom_amount:.0f} ml air ditambahkan!", icon="💧")
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Riwayat Minum Hari Ini")
    if water_logs:
        for w_id, amount_ml, logged_at in water_logs:
            wc1, wc2 = st.columns([4, 1])
            with wc1:
                st.markdown(f"💧 **{amount_ml:.0f} ml** &nbsp;·&nbsp; {logged_at[-8:-3]}")
            with wc2:
                if st.button("Hapus", key=f"del_water_{w_id}"):
                    with sqlite3.connect(DB_NAME) as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM water_logs WHERE id = ? AND user_id = ?", (w_id, active_user_id))
                        conn.commit()
                    st.rerun()
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="emoji">💧</div>
            Belum ada catatan minum air hari ini. Yuk mulai minum!
        </div>
        """, unsafe_allow_html=True)


# ====================================================
# PAGE 4: ANALYTICS & TREND
# ====================================================
elif "Analytics & Trend" in menu_selection:
    st.markdown('<div class="section-label">Analitik</div>', unsafe_allow_html=True)
    st.markdown("### Trend Asupan Kalori (7 Hari Terakhir)")

    with sqlite3.connect(DB_NAME) as conn:
        query = """
            SELECT DATE(logged_at) as log_date, SUM(calories) as total_calories
            FROM daily_logs
            WHERE user_id = ? AND DATE(logged_at) >= DATE('now', '-7 days', 'localtime')
            GROUP BY DATE(logged_at)
            ORDER BY log_date ASC
        """
        df = pd.read_sql_query(query, conn, params=(active_user_id,))

        cursor = conn.cursor()
        cursor.execute("SELECT target_calories FROM users WHERE id = ?", (active_user_id,))
        user_target = cursor.fetchone()

    target_val = user_target[0] if user_target else 2000.0

    if not df.empty:
        df['log_date'] = pd.to_datetime(df['log_date'])

        hari_map = {0: 'Sen', 1: 'Sel', 2: 'Rab', 3: 'Kam', 4: 'Jum', 5: 'Sab', 6: 'Min'}
        df['hari'] = df['log_date'].dt.dayofweek.map(hari_map)
        df['day_label'] = df['hari'] + ' ' + df['log_date'].dt.strftime('%d %b')
        df['status'] = df['total_calories'].apply(lambda c: 'Sesuai Target' if c <= target_val else 'Melebihi Target')
        df['rolling_avg'] = df['total_calories'].rolling(window=3, min_periods=1).mean()

        bar_width = 42

        bars = alt.Chart(df).mark_bar(
            cornerRadiusTopLeft=10,
            cornerRadiusTopRight=10,
            size=bar_width
        ).encode(
            x=alt.X('day_label:N', title=None, sort=list(df['day_label']),
                    axis=alt.Axis(labelAngle=0, labelColor='#64748b', labelFontWeight=600)),
            y=alt.Y('total_calories:Q', title='Kalori (kcal)',
                    axis=alt.Axis(gridColor='#eef2f1', labelColor='#94a3b8')),
            color=alt.Color('status:N',
                             scale=alt.Scale(domain=['Sesuai Target', 'Melebihi Target'],
                                              range=['#34d399', '#f87171']),
                             legend=None),
            tooltip=[
                alt.Tooltip('day_label:N', title='Tanggal'),
                alt.Tooltip('total_calories:Q', title='Kalori', format='.0f'),
                alt.Tooltip('status:N', title='Status')
            ]
        )

        value_labels = alt.Chart(df).mark_text(
            dy=-10, fontWeight=700, fontSize=12, color='#0f172a'
        ).encode(
            x=alt.X('day_label:N', sort=list(df['day_label'])),
            y=alt.Y('total_calories:Q'),
            text=alt.Text('total_calories:Q', format='.0f')
        )

        trend_line = alt.Chart(df).mark_line(
            color='#059669', strokeWidth=2.5, point=alt.OverlayMarkDef(color='#059669', size=45, filled=True)
        ).encode(
            x=alt.X('day_label:N', sort=list(df['day_label'])),
            y=alt.Y('rolling_avg:Q'),
            tooltip=[alt.Tooltip('rolling_avg:Q', title='Rata-rata 3 Hari', format='.0f')]
        )

        target_df = pd.DataFrame({'Target': [target_val]})
        rule = alt.Chart(target_df).mark_rule(
            color='#ef4444', strokeDash=[6, 4], strokeWidth=2
        ).encode(y='Target:Q')

        target_label = alt.Chart(target_df).mark_text(
            align='left', dx=6, dy=-8, color='#ef4444', fontWeight=700, fontSize=11
        ).encode(
            y='Target:Q',
            x=alt.value(0),
            text=alt.value(f'Target {target_val:.0f} kcal')
        )

        chart = (bars + value_labels + trend_line + rule + target_label).properties(
            height=380
        ).configure_view(
            strokeWidth=0
        ).configure_axis(
            domain=False
        )

        st.markdown('<div class="metric-card" style="padding: 1.5rem;">', unsafe_allow_html=True)
        st.altair_chart(chart, use_container_width=True)
        st.markdown("""
        <div style="display:flex; gap:1.5rem; margin-top:0.6rem; font-size:0.85rem; color:#64748b; flex-wrap:wrap;">
            <span>🟢 <b style="color:#0f172a;">Hijau</b> — sesuai target</span>
            <span>🔴 <b style="color:#0f172a;">Merah</b> — melebihi target</span>
            <span>📈 <b style="color:#0f172a;">Garis Hijau Tua</b> — rata-rata bergerak 3 hari</span>
            <span>┄ <b style="color:#0f172a;">Garis Putus-putus Merah</b> — target harian</span>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-icon icon-left">📊</div>
                <div class="metric-label">Rata-rata Harian</div>
                <div class="metric-value">{df['total_calories'].mean():.0f} <span class="metric-sub">kcal</span></div>
            </div>
            """, unsafe_allow_html=True)
        with col_s2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-icon icon-target">📈</div>
                <div class="metric-label">Konsumsi Puncak</div>
                <div class="metric-value">{df['total_calories'].max():.0f} <span class="metric-sub">kcal</span></div>
            </div>
            """, unsafe_allow_html=True)
        with col_s3:
            hari_sesuai = int((df['total_calories'] <= target_val).sum())
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-icon icon-cal">✅</div>
                <div class="metric-label">Hari Sesuai Target</div>
                <div class="metric-value">{hari_sesuai} <span class="metric-sub">/ {len(df)} hari</span></div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="emoji">📉</div>
            Data belum cukup untuk menampilkan grafik tren 7 hari terakhir.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Trend Hidrasi (7 Hari Terakhir)")
    with sqlite3.connect(DB_NAME) as conn:
        water_query = """
            SELECT DATE(logged_at) as log_date, SUM(amount_ml) as total_ml
            FROM water_logs
            WHERE user_id = ? AND DATE(logged_at) >= DATE('now', '-7 days', 'localtime')
            GROUP BY DATE(logged_at)
            ORDER BY log_date ASC
        """
        df_water = pd.read_sql_query(water_query, conn, params=(active_user_id,))

    if not df_water.empty:
        df_water['log_date'] = pd.to_datetime(df_water['log_date'])
        df_water['hari'] = df_water['log_date'].dt.dayofweek.map(hari_map)
        df_water['day_label'] = df_water['hari'] + ' ' + df_water['log_date'].dt.strftime('%d %b')

        water_bars = alt.Chart(df_water).mark_bar(
            cornerRadiusTopLeft=10, cornerRadiusTopRight=10, size=42, color='#22d3ee'
        ).encode(
            x=alt.X('day_label:N', title=None, sort=list(df_water['day_label']),
                    axis=alt.Axis(labelAngle=0, labelColor='#64748b', labelFontWeight=600)),
            y=alt.Y('total_ml:Q', title='Air (ml)', axis=alt.Axis(gridColor='#eef2f1', labelColor='#94a3b8')),
            tooltip=[alt.Tooltip('day_label:N', title='Tanggal'), alt.Tooltip('total_ml:Q', title='Total ml', format='.0f')]
        )
        water_target_df = pd.DataFrame({'Target': [target_water_ml]})
        water_rule = alt.Chart(water_target_df).mark_rule(color='#0891b2', strokeDash=[6, 4], strokeWidth=2).encode(y='Target:Q')

        water_chart = (water_bars + water_rule).properties(height=280).configure_view(strokeWidth=0).configure_axis(domain=False)

        st.markdown('<div class="metric-card" style="padding: 1.5rem;">', unsafe_allow_html=True)
        st.altair_chart(water_chart, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="emoji">💧</div>
            Belum ada data hidrasi untuk 7 hari terakhir.
        </div>
        """, unsafe_allow_html=True)


# ====================================================
# PAGE 5: EXPORT DATA
# ====================================================
elif "Export Data" in menu_selection:
    st.markdown('<div class="section-label">Export</div>', unsafe_allow_html=True)
    st.markdown("### 📤 Export Riwayat Konsumsi Makanan")
    st.caption("Unduh catatan makanan untuk dibagikan ke ahli gizi, personal trainer, atau dokter.")

    period_option = st.selectbox("Pilih Periode", ["7 Hari Terakhir", "30 Hari Terakhir", "Semua Data"])

    if period_option == "7 Hari Terakhir":
        date_clause = "AND DATE(logged_at) >= DATE('now', '-7 days', 'localtime')"
    elif period_option == "30 Hari Terakhir":
        date_clause = "AND DATE(logged_at) >= DATE('now', '-30 days', 'localtime')"
    else:
        date_clause = ""

    with sqlite3.connect(DB_NAME) as conn:
        export_query = f"""
            SELECT
                DATE(logged_at) as Tanggal,
                TIME(logged_at) as Waktu,
                food_name as "Nama Makanan",
                weight_g as "Berat (g)",
                calories as "Kalori (kcal)",
                protein_g as "Protein (g)",
                carbs_g as "Karbohidrat (g)",
                fat_g as "Lemak (g)",
                input_method as "Metode Input",
                ai_feedback as "Catatan AI"
            FROM daily_logs
            WHERE user_id = ? {date_clause}
            ORDER BY logged_at DESC
        """
        export_df = pd.read_sql_query(export_query, conn, params=(active_user_id,))

    if export_df.empty:
        st.markdown("""
        <div class="empty-state">
            <div class="emoji">📭</div>
            Tidak ada data pada periode yang dipilih.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"**{len(export_df)} baris data** ditemukan untuk periode **{period_option}**.")
        st.dataframe(export_df, use_container_width=True, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Unduh Sebagai")
        dl1, dl2, dl3 = st.columns(3)

        with dl1:
            csv_data = export_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "⬇️ Download CSV",
                data=csv_data,
                file_name=f"nutritrack_log_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        with dl2:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False, sheet_name='Log Makanan')
            st.download_button(
                "⬇️ Download Excel",
                data=excel_buffer.getvalue(),
                file_name=f"nutritrack_log_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        with dl3:
            if FPDF_AVAILABLE:
                pdf = FPDF(orientation='L', unit='mm', format='A4')
                pdf.add_page()
                pdf.set_font("Helvetica", "B", 14)
                pdf.cell(0, 10, "NutriTrack AI - Riwayat Konsumsi Makanan", ln=True)
                pdf.set_font("Helvetica", "", 9)
                pdf.cell(0, 6, f"Pengguna: {active_user['name']} | Periode: {period_option} | Dibuat: {datetime.now().strftime('%d %B %Y %H:%M')}", ln=True)
                pdf.ln(3)

                col_widths = [22, 18, 45, 18, 20, 18, 22, 18, 22, 60]
                headers = list(export_df.columns)
                pdf.set_font("Helvetica", "B", 8)
                for h, w in zip(headers, col_widths):
                    pdf.cell(w, 7, str(h)[:20], border=1)
                pdf.ln()

                pdf.set_font("Helvetica", "", 7.5)
                for _, row in export_df.iterrows():
                    for val, w in zip(row.tolist(), col_widths):
                        text = "" if pd.isna(val) else str(val)
                        pdf.cell(w, 6, text[:35], border=1)
                    pdf.ln()

                pdf_bytes = bytes(pdf.output(dest='S'))
                st.download_button(
                    "⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=f"nutritrack_log_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.warning("Library `fpdf2` belum terpasang. Jalankan `pip install fpdf2` untuk mengaktifkan export PDF.")


# ====================================================
# 12. VIRTUAL ASSISTANT (FLOATING CHAT — MUNCUL DI SEMUA HALAMAN)
# ====================================================
def get_va_context():
    """Ambil ringkasan data gizi & hidrasi hari ini (khusus user yang login) untuk konteks jawaban asisten AI."""
    today_str = datetime.now().strftime('%Y-%m-%d')
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT SUM(calories), SUM(protein_g), SUM(carbs_g), SUM(fat_g) FROM daily_logs WHERE user_id = ? AND DATE(logged_at) = ?",
            (active_user_id, today_str)
        )
        totals = cursor.fetchone()
        cursor.execute(
            "SELECT target_calories, target_protein_g, target_carbs_g, target_fat_g FROM users WHERE id = ?",
            (active_user_id,)
        )
        targets_row = cursor.fetchone()
        cursor.execute(
            "SELECT SUM(amount_ml) FROM water_logs WHERE user_id = ? AND DATE(logged_at) = ?",
            (active_user_id, today_str)
        )
        water_row = cursor.fetchone()
        cursor.execute(
            "SELECT food_name, calories FROM daily_logs WHERE user_id = ? AND DATE(logged_at) = ? ORDER BY id DESC LIMIT 5",
            (active_user_id, today_str)
        )
        recent_foods = cursor.fetchall()

    cal_total = totals[0] if totals and totals[0] else 0.0
    p_total = totals[1] if totals and totals[1] else 0.0
    c_total = totals[2] if totals and totals[2] else 0.0
    f_total = totals[3] if totals and totals[3] else 0.0
    cal_target = targets_row[0] if targets_row and targets_row[0] else 2000.0
    p_target = targets_row[1] if targets_row and targets_row[1] else target_protein_g
    c_target = targets_row[2] if targets_row and targets_row[2] else target_carbs_g
    f_target = targets_row[3] if targets_row and targets_row[3] else target_fat_g
    water_total = water_row[0] if water_row and water_row[0] else 0.0

    food_list = ", ".join([f"{f[0]} ({f[1]:.0f} kcal)" for f in recent_foods]) if recent_foods else "belum ada makanan dicatat hari ini"

    return f"""
    Nama pengguna: {active_user['name']}
    Data gizi & hidrasi pengguna HARI INI (gunakan ini untuk menjawab pertanyaan personal, jangan tampilkan mentah-mentah kecuali diminta):
    - Kalori: {cal_total:.0f} dari target {cal_target:.0f} kcal (sisa {cal_target - cal_total:.0f} kcal)
    - Protein: {p_total:.1f}g dari target {p_target:.0f}g
    - Karbohidrat: {c_total:.1f}g dari target {c_target:.0f}g
    - Lemak: {f_total:.1f}g dari target {f_target:.0f}g
    - Air minum: {water_total:.0f}ml dari target {target_water_ml:.0f}ml
    - Makanan terakhir dicatat: {food_list}
    - Target kesehatan pengguna: {default_goal}
    """.strip()


def handle_va_send():
    user_msg = st.session_state.get("va_input_box", "").strip()
    if not user_msg:
        return

    st.session_state.va_messages.append({"role": "user", "content": user_msg})

    if not api_key:
        st.session_state.va_messages.append({"role": "assistant", "content": "API Key belum terkonfigurasi, jadi saya belum bisa menjawab. Cek file .env kamu ya."})
        st.session_state.va_input_box = ""
        return

    context = get_va_context()
    full_prompt = f"""
    Kamu adalah "Nutri", asisten AI ramah di aplikasi NutriTrack AI. Tugasmu menjawab pertanyaan
    seputar gizi/makanan secara umum, DAN memberi saran personal berdasarkan data pengguna berikut
    jika relevan dengan pertanyaannya. Jawab singkat, jelas, dan hangat dalam Bahasa Indonesia.

    {context}

    Pertanyaan pengguna: {user_msg}
    """

    try:
        interaction = client.interactions.create(
            model=GEMINI_MODEL,
            input=full_prompt,
            previous_interaction_id=st.session_state.get("va_last_interaction_id"),
        )
        st.session_state.va_last_interaction_id = interaction.id
        answer = interaction.output_text
    except Exception as e:
        answer = f"Maaf, terjadi kesalahan saat memproses: {e}"

    st.session_state.va_messages.append({"role": "assistant", "content": answer})
    st.session_state.va_input_box = ""


if "va_open" not in st.session_state:
    st.session_state.va_open = False
if "va_messages" not in st.session_state:
    st.session_state.va_messages = [
        {"role": "assistant", "content": f"Halo {active_user['name']}! 👋 Saya Nutri, asisten gizi kamu. Tanya apa saja soal makanan, atau soal sisa kuota kalori & makro kamu hari ini."}
    ]
if "va_last_interaction_id" not in st.session_state:
    st.session_state.va_last_interaction_id = None

if FLOAT_AVAILABLE:
    float_init()

    # Tombol bulat mengambang untuk toggle buka/tutup chat
    toggle_col = st.container(key="va_toggle_btn")
    with toggle_col:
        toggle_icon = "✖️" if st.session_state.va_open else "🤖"
        if st.button(toggle_icon, key="va_toggle_button"):
            st.session_state.va_open = not st.session_state.va_open
    toggle_col.float("position: fixed; bottom: 24px; right: 24px; z-index: 999995; width: 58px;")

    # Panel chat mengambang (hanya dirender saat dibuka)
    if st.session_state.va_open:
        panel_col = st.container(key="va_panel")
        with panel_col:
            st.markdown('<div class="va-header">🤖 Nutri — Asisten Gizi AI</div>', unsafe_allow_html=True)
            st.markdown('<div class="va-body-wrap">', unsafe_allow_html=True)
            with st.container(height=300):
                for msg in st.session_state.va_messages:
                    with st.chat_message(msg["role"]):
                        st.write(msg["content"])
            st.text_input(
                "Tanya sesuatu",
                key="va_input_box",
                placeholder="Tanya soal gizi atau data kamu...",
                label_visibility="collapsed",
                on_change=handle_va_send,
            )
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('<div class="va-hint">Tekan Enter untuk mengirim</div>', unsafe_allow_html=True)
        panel_col.float(
            "position: fixed; bottom: 92px; right: 24px; z-index: 999994; "
            "width: 340px; max-width: 90vw;"
        )
else:
    st.sidebar.warning("💬 Fitur Asisten AI mengambang butuh library `streamlit-float`. Jalankan `pip install streamlit-float` lalu restart aplikasi.")
