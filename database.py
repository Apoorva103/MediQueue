import sqlite3

def init_db():
    # Connect to SQLite database (this creates 'hospital.db' file automatically)
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()

    # Create the patients table if it doesn't already exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_number TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            department TEXT NOT NULL,
            reason TEXT NOT NULL,
            urgency TEXT DEFAULT 'Normal',
            status TEXT DEFAULT 'Waiting',
            registration_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("Database and patients table created successfully!")

if __name__ == "__main__":
    init_db()