import os, sqlite3
from flask import Flask, jsonify, render_template, request, g
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config['DATABASE'] = os.path.join(app.instance_path, 'chatbot.db')
os.makedirs(app.instance_path, exist_ok=True)

def db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE']); g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close(_=None):
    connection = g.pop('db', None)
    if connection: connection.close()

def init_db():
    db().execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    db().commit()


# Initialize SQLite when Gunicorn imports the application on Render.
with app.app_context():
    init_db()


@app.get('/')
def index(): return render_template('index.html')

@app.get('/api/history')
def history():
    rows = db().execute('SELECT id,role,content,created_at FROM messages ORDER BY id').fetchall()
    return jsonify([dict(r) for r in rows])

@app.post('/api/chat')
def chat():
    message = (request.json or {}).get('message','').strip()
    if not message: return jsonify(error='Please enter a message.'), 400
    key = os.getenv('GEMINI_API_KEY')
    if not key: return jsonify(error='GEMINI_API_KEY is not configured. Add it to your .env file.'), 503
    try:
        from google import genai
        client = genai.Client(api_key=key)
        context = db().execute('SELECT role,content FROM messages ORDER BY id DESC LIMIT 8').fetchall()[::-1]
        transcript = '\n'.join(f"{r['role']}: {r['content']}" for r in context)
        prompt = f"You are Nova, a friendly and concise AI assistant. Continue this conversation.\n{transcript}\nuser: {message}"
        result = client.models.generate_content(
            model=os.getenv('GEMINI_MODEL', 'gemini-3.6-flash'),
            contents=prompt,
        )
        answer = result.text.strip()
        db().executemany('INSERT INTO messages(role,content) VALUES(?,?)', [('user',message),('assistant',answer)]); db().commit()
        return jsonify(response=answer)
    except Exception as exc:
        app.logger.exception('Gemini request failed')
        return jsonify(error=f'AI service error: {exc}'), 502

@app.delete('/api/history')
def clear_history():
    db().execute('DELETE FROM messages'); db().commit(); return jsonify(success=True)

@app.cli.command('init-db')
def init_command(): init_db(); print('Database initialized.')

if __name__ == '__main__':
    with app.app_context(): init_db()
    app.run(debug=True)
