from flask import Flask, render_template, request, redirect, session, url_for
import string
import random
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key' 

DB_NAME = 'urls.db'

# Initialize database with new password column
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short TEXT UNIQUE,
            long TEXT,
            expires_at TEXT,
            password TEXT
        )
    ''')
    # Add missing columns if not exist
    c.execute("PRAGMA table_info(urls)")
    columns = [col[1] for col in c.fetchall()]
    if 'expires_at' not in columns:
        c.execute("ALTER TABLE urls ADD COLUMN expires_at TEXT")
    if 'password' not in columns:
        c.execute("ALTER TABLE urls ADD COLUMN password TEXT")
    conn.commit()
    conn.close()

def generate_short_id(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

@app.route('/', methods=['GET', 'POST'])
def index():
    message = ""
    short_url = None
    if request.method == 'POST':
        long_url = request.form['long_url']
        custom_slug = request.form.get('custom_slug', '').strip()
        expires_at = request.form.get('expires_at', '').strip()
        password = request.form.get('password', '').strip()

        short_id = custom_slug if custom_slug else generate_short_id()

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM urls WHERE short=?", (short_id,))
        existing = c.fetchone()

        if existing:
            message = "❌ Slug already taken. Try another one."
        else:
            try:
                c.execute("INSERT INTO urls (short, long, expires_at, password) VALUES (?, ?, ?, ?)",
                          (short_id, long_url, expires_at if expires_at else None, password if password else None))
                conn.commit()
                short_url = request.host_url + short_id
            except sqlite3.IntegrityError:
                message = "❌ Database error occurred. Try again."
        conn.close()
    return render_template('index.html', short_url=short_url, message=message)

@app.route('/<short_id>', methods=['GET', 'POST'])
def redirect_to_url(short_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT long, expires_at, password FROM urls WHERE short=?", (short_id,))
    result = c.fetchone()
    conn.close()

    if result:
        long_url, expires_at, password = result

        # Check expiration
        if expires_at:
            today = datetime.today().date()
            expiry_date = datetime.strptime(expires_at, '%Y-%m-%d').date()
            if today > expiry_date:
                return "<h2>🔒 This link has expired.</h2><a href='/'>Go back</a>"

        # Check password
        if password:
            # If already authenticated in session
            if session.get(f'access_{short_id}') == True:
                return redirect(long_url)

            # If form submitted
            if request.method == 'POST':
                entered = request.form.get('password', '').strip()
                if entered == password:
                    session[f'access_{short_id}'] = True
                    return redirect(long_url)
                else:
                    return render_template('password_prompt.html', short_id=short_id, error="❌ Incorrect password.")
            # Show password form
            return render_template('password_prompt.html', short_id=short_id)

        # No password, redirect
        return redirect(long_url)
    else:
        return render_template('not_found.html'), 404

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
