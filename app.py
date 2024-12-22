from flask import Flask, request, jsonify, render_template, redirect
from datetime import datetime, timedelta
import sqlite3
import random
import string

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT NOT NULL,
            short_id TEXT NOT NULL UNIQUE,
            expires_on TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

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
    expires_on = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')

    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO urls (original_url, short_id, expires_on)
            VALUES (?, ?, ?)
        ''', (original_url, short_id, expires_on))
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Custom slug already in use. Please choose a different slug.'}), 400
    finally:
        conn.close()

    return jsonify({'shortened_url': short_url})

@app.route('/<short_id>')
def redirect_to_original(short_id):
    conn = sqlite3.connect('urls.db')
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        SELECT original_url, expires_on
        FROM urls
        WHERE short_id = ?
    ''', (short_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        original_url, expires_on = row
        if expires_on > now:
            return redirect(original_url)
        else:
            return 'This URL has expired.', 404
    return 'URL not found.', 404

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
