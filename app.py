from flask import Flask, request, jsonify, render_template, redirect
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import random
import string
import os

app = Flask(__name__)

# Database connection function
def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv('SUPABASE_DB_NAME'),
        user=os.getenv('SUPABASE_USER'),
        password=os.getenv('SUPABASE_PASSWORD'),
        host=os.getenv('SUPABASE_HOST'),
        port=os.getenv('SUPABASE_PORT', 5432)
    )

# Initialize the database (run once to set up the table)
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id SERIAL PRIMARY KEY,
            original_url TEXT NOT NULL,
            short_id TEXT NOT NULL UNIQUE,
            expires_on TIMESTAMP NOT NULL
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

# Function to generate a random short ID
def generate_short_id(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shorten', methods=['POST'])
def shorten_url():
    data = request.json
    original_url = data.get('original_url')
    custom_slug = data.get('custom_slug')

    if custom_slug:
        short_id = custom_slug
    else:
        short_id = generate_short_id()

    short_url = request.host_url + short_id
    expires_on = datetime.now() + timedelta(days=3)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO urls (original_url, short_id, expires_on)
            VALUES (%s, %s, %s)
        ''', (original_url, short_id, expires_on))
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({'error': 'Custom slug already in use. Please choose a different slug.'}), 400
    finally:
        cursor.close()
        conn.close()

    return jsonify({'shortened_url': short_url})

@app.route('/<short_id>')
def redirect_to_original(short_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    now = datetime.now()

    cursor.execute('''
        SELECT original_url, expires_on
        FROM urls
        WHERE short_id = %s
    ''', (short_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row:
        original_url = row['original_url']
        expires_on = row['expires_on']

        if expires_on > now:
            return redirect(original_url)
        else:
            return 'This URL has expired.', 404
    return 'URL not found.', 404

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
