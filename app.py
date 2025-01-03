from flask import Flask, request, jsonify, render_template, redirect, session
from flask_wtf.csrf import CSRFProtect
from datetime import datetime, timedelta
import sqlite3
import random
import string
import logging
from urllib.parse import urlparse
import re
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# Secret key for CSRF protection and sessions
app.config['SECRET_KEY'] = 'acYS%KQwFM.5!yJjL@f2~R:9u"-=g;ZU'

# Enable CSRF protection
csrf = CSRFProtect(app)

# Configure logging
logging.basicConfig(level=logging.INFO)

DB_NAME = 'urls.db'


def init_db():
    """Initialize the database and create the required table."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT NOT NULL,
            short_id TEXT NOT NULL UNIQUE,
            expires_on TEXT NOT NULL
        )
    ''')

    # Add indexes to speed up searches by short_id and expires_on
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_short_id ON urls (short_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_expires_on ON urls (expires_on)')
    
    conn.commit()
    conn.close()
    logging.info("Database initialized with indexes on short_id and expires_on.")


# Error handler for 404 - Page Not Found
@app.errorhandler(404)
def page_not_found(e):
    """Custom 404 error page."""
    return render_template('404.html'), 404


# Error handler for 500 - Internal Server Error
@app.errorhandler(500)
def internal_server_error(e):
    """Custom 500 error page."""
    return render_template('500.html'), 500


def cleanup_expired_urls():
    """Remove expired URLs from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        DELETE FROM urls WHERE expires_on <= ?
    ''', (now,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    logging.info(f"Expired URLs cleanup complete. {deleted_count} entries removed.")


def start_scheduler():
    """Start the background scheduler for cleanup."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=cleanup_expired_urls, trigger="interval", hours=1)
    scheduler.start()
    logging.info("Scheduler started for periodic cleanup of expired URLs.")


def generate_short_id(length=6):
    """Generate a random short ID."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))


def is_valid_url(url):
    """Validate the URL format."""
    parsed = urlparse(url)
    return bool(parsed.netloc) and bool(parsed.scheme)


def sanitize_slug(slug):
    """Ensure the custom slug contains only allowed characters."""
    return re.fullmatch(r'[a-zA-Z0-9-_]+', slug) is not None


def insert_url(original_url, short_id, expires_on):
    """Insert a new URL into the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO urls (original_url, short_id, expires_on)
            VALUES (?, ?, ?)
        ''', (original_url, short_id, expires_on))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return False
    conn.close()
    return True


def get_url_by_short_id(short_id):
    """Retrieve URL and expiration details using the short ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT original_url, expires_on
        FROM urls
        WHERE short_id = ?
    ''', (short_id,))
    row = cursor.fetchone()
    conn.close()
    return row


@app.route('/')
def index():
    """Render the homepage."""
    return render_template('index.html')


@app.route('/shorten', methods=['POST'])
def shorten_url():
    """Shorten a given URL with a custom expiration."""
    data = request.json
    original_url = data.get('original_url', '').strip()
    custom_slug = data.get('custom_slug', '').strip()
    duration_type = data.get('duration_type', '').strip()
    duration_value = int(data.get('duration_value', 1))

    if not original_url or not is_valid_url(original_url):
        return jsonify({'error': 'Invalid URL. Please enter a valid URL.'}), 400

    if custom_slug and not sanitize_slug(custom_slug):
        return jsonify({'error': 'Custom slug contains invalid characters. Only letters, numbers, "-" and "_" are allowed.'}), 400

    short_id = custom_slug if custom_slug else generate_short_id()

    # Determine expiration based on selected duration type and value
    now = datetime.now()
    if duration_type == "days":
        expires_on = now + timedelta(days=duration_value)
    elif duration_type == "weeks":
        expires_on = now + timedelta(weeks=duration_value)
    elif duration_type == "months":
        expires_on = now + timedelta(weeks=4 * duration_value)
    elif duration_type == "years":
        expires_on = now + timedelta(weeks=52 * duration_value)
    else:
        return jsonify({'error': 'Invalid duration type selected.'}), 400

    expires_on_str = expires_on.strftime('%Y-%m-%d %H:%M:%S')

    if not insert_url(original_url, short_id, expires_on_str):
        return jsonify({'error': 'Custom slug already in use. Please choose a different slug.'}), 400

    short_url = request.host_url.rstrip('/') + '/' + short_id
    return jsonify({'shortened_url': short_url})


@app.route('/<short_id>')
def redirect_to_original(short_id):
    """Redirect to the original URL."""
    row = get_url_by_short_id(short_id)
    if not row:
        return 'URL not found.', 404

    original_url, expires_on = row
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if expires_on <= now:
        return 'This URL has expired.', 410

    return redirect(original_url)


if __name__ == '__main__':
    init_db()
    start_scheduler()
    try:
        app.run(debug=True)
    except (KeyboardInterrupt, SystemExit):
        pass
