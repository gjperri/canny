import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        database ="canny",
        user="gabrielperri",
        password=""
    )
    print("Connected to the DB.")

    # Test part
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users;")
    count = cursor.fetchone()[0]
    print(f"Found {count} users in database")
    conn.close()
except Exception as e:
    print("Error connecting")