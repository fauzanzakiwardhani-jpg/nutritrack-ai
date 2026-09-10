import sqlite3

DB_NAME = "nutrition_ai.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Tabel Profil Pengguna
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            height_cm REAL,
            weight_kg REAL,
            activity_level TEXT,
            health_goal TEXT,
            daily_calorie_target REAL
        )
    ''')

    # Tabel Sesi Makan
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meal_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            meal_type TEXT,
            image_path TEXT,
            total_calories REAL,
            total_protein_g REAL,
            total_carbs_g REAL,
            total_fat_g REAL,
            ai_feedback TEXT,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabel Detail Item Makanan
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meal_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            item_name TEXT NOT NULL,
            estimated_weight_g REAL,
            calories REAL,
            protein_g REAL,
            carbs_g REAL,
            fat_g REAL,
            FOREIGN KEY (session_id) REFERENCES meal_sessions(session_id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database berhasil diinisialisasi!")