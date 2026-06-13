import sqlite3

def check_errors():
    conn = sqlite3.connect("storage/docintel.db")
    cursor = conn.cursor()
    cursor.execute("SELECT original_filename, status, error_message FROM documents ORDER BY created_at DESC LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(f"File: {row[0]}, Status: {row[1]}, Error: {row[2]}")
    conn.close()

if __name__ == "__main__":
    check_errors()
