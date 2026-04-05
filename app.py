"""
TaskFlow — Flask Task Manager
Uses Python's built-in sqlite3 (no Flask-SQLAlchemy required).
"""
 
from flask import Flask, render_template, request, jsonify, send_from_directory, g
import sqlite3
import os
import uuid
from datetime import datetime, date
from werkzeug.utils import secure_filename
 
app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-me-in-production'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), 'taskmanager.db')
 
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg', 'xlsx', 'pptx', 'zip'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
 
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db
 
@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
 
def query_db(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv
 
def execute_db(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid
 
def init_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        color TEXT NOT NULL DEFAULT '#6366f1',
        icon TEXT NOT NULL DEFAULT 'folder',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        priority TEXT NOT NULL DEFAULT 'medium',
        status TEXT NOT NULL DEFAULT 'pending',
        deadline TEXT,
        category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
        file_name TEXT,
        file_path TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        completed_at TEXT
    );
    """)
    cur = db.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        db.executemany("INSERT INTO categories (name, color, icon) VALUES (?, ?, ?)", [
            ('Personal Tasks', '#f59e0b', 'user'),
            ('Work', '#6366f1', 'briefcase'),
            ('Study', '#10b981', 'book'),
        ])
    db.commit()
    db.close()
 
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
 
def category_to_dict(row):
    d = dict(row)
    tasks = query_db("SELECT status FROM tasks WHERE category_id=?", (d['id'],))
    d['task_count'] = len(tasks)
    d['completed_count'] = sum(1 for t in tasks if t['status'] == 'completed')
    return d
 
def task_to_dict(row):
    d = dict(row)
    if d.get('deadline'):
        try:
            dl = date.fromisoformat(d['deadline'])
            d['days_left'] = (dl - date.today()).days
        except:
            d['days_left'] = None
    else:
        d['days_left'] = None
    if d.get('category_id'):
        cat = query_db("SELECT name, color FROM categories WHERE id=?", (d['category_id'],), one=True)
        d['category_name'] = cat['name'] if cat else None
        d['category_color'] = cat['color'] if cat else '#94a3b8'
    else:
        d['category_name'] = None
        d['category_color'] = '#94a3b8'
    return d
 
@app.route('/')
def index():
    return render_template('dashboard.html')
 
@app.route('/tasks')
def tasks_page():
    return render_template('tasks.html')
 
@app.route('/categories')
def categories_page():
    return render_template('categories.html')
 
@app.route('/profile')
def profile_page():
    return render_template('profile.html')
 
@app.route('/api/categories', methods=['GET'])
def get_categories():
    rows = query_db("SELECT * FROM categories ORDER BY created_at ASC")
    return jsonify([category_to_dict(r) for r in rows])
 
@app.route('/api/categories', methods=['POST'])
def create_category():
    data = request.get_json()
    cid = execute_db("INSERT INTO categories (name, color, icon) VALUES (?, ?, ?)",
        (data['name'].strip(), data.get('color', '#6366f1'), data.get('icon', 'folder')))
    row = query_db("SELECT * FROM categories WHERE id=?", (cid,), one=True)
    return jsonify(category_to_dict(row)), 201
 
@app.route('/api/categories/<int:cat_id>', methods=['PUT'])
def update_category(cat_id):
    data = request.get_json()
    row = query_db("SELECT * FROM categories WHERE id=?", (cat_id,), one=True)
    if not row:
        return jsonify({'error': 'Not found'}), 404
    execute_db("UPDATE categories SET name=?, color=?, icon=? WHERE id=?",
        (data.get('name', row['name']).strip(), data.get('color', row['color']), data.get('icon', row['icon']), cat_id))
    row = query_db("SELECT * FROM categories WHERE id=?", (cat_id,), one=True)
    return jsonify(category_to_dict(row))
 
@app.route('/api/categories/<int:cat_id>', methods=['DELETE'])
def delete_category(cat_id):
    execute_db("DELETE FROM categories WHERE id=?", (cat_id,))
    return jsonify({'message': 'Deleted'})
 
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    clauses, args = [], []
    if request.args.get('status'):
        clauses.append("t.status=?"); args.append(request.args['status'])
    if request.args.get('category_id'):
        clauses.append("t.category_id=?"); args.append(int(request.args['category_id']))
    if request.args.get('priority'):
        clauses.append("t.priority=?"); args.append(request.args['priority'])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT t.* FROM tasks t {where} ORDER BY CASE WHEN t.deadline IS NULL THEN 1 ELSE 0 END, t.deadline ASC, t.created_at DESC"
    rows = query_db(sql, args)
    return jsonify([task_to_dict(r) for r in rows])
 
@app.route('/api/tasks', methods=['POST'])
def create_task():
    title = request.form.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Title required'}), 400
    deadline = request.form.get('deadline') or None
    cat_id_raw = request.form.get('category_id')
    cat_id = int(cat_id_raw) if cat_id_raw and cat_id_raw not in ('null', '') else None
    file_name = file_path_val = None
    f = request.files.get('file')
    if f and f.filename and allowed_file(f.filename):
        fname = secure_filename(f"{uuid.uuid4().hex}_{f.filename}")
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
        file_name = f.filename
        file_path_val = fname
    tid = execute_db(
        "INSERT INTO tasks (title, description, priority, deadline, category_id, file_name, file_path) VALUES (?,?,?,?,?,?,?)",
        (title, request.form.get('description',''), request.form.get('priority','medium'),
         deadline, cat_id, file_name, file_path_val))
    row = query_db("SELECT * FROM tasks WHERE id=?", (tid,), one=True)
    return jsonify(task_to_dict(row)), 201
 
@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    row = query_db("SELECT * FROM tasks WHERE id=?", (task_id,), one=True)
    if not row:
        return jsonify({'error': 'Not found'}), 404
    if request.content_type and 'multipart' in request.content_type:
        src = request.form
        f = request.files.get('file')
        if f and f.filename and allowed_file(f.filename):
            if row['file_path']:
                old = os.path.join(app.config['UPLOAD_FOLDER'], row['file_path'])
                if os.path.exists(old): os.remove(old)
            fname = secure_filename(f"{uuid.uuid4().hex}_{f.filename}")
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            execute_db("UPDATE tasks SET file_name=?, file_path=? WHERE id=?", (f.filename, fname, task_id))
    else:
        src = request.get_json() or {}
    title = src.get('title', row['title']).strip()
    description = src.get('description', row['description'])
    priority = src.get('priority', row['priority'])
    deadline = src.get('deadline', row['deadline']) or None
    cat_id_raw = src.get('category_id', row['category_id'])
    cat_id = int(cat_id_raw) if cat_id_raw and str(cat_id_raw) not in ('null', '') else None
    status = src.get('status', row['status'])
    completed_at = row['completed_at']
    if status == 'completed' and not completed_at:
        completed_at = datetime.utcnow().isoformat()
    elif status == 'pending':
        completed_at = None
    execute_db(
        "UPDATE tasks SET title=?, description=?, priority=?, deadline=?, category_id=?, status=?, completed_at=? WHERE id=?",
        (title, description, priority, deadline, cat_id, status, completed_at, task_id))
    row = query_db("SELECT * FROM tasks WHERE id=?", (task_id,), one=True)
    return jsonify(task_to_dict(row))
 
@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    row = query_db("SELECT * FROM tasks WHERE id=?", (task_id,), one=True)
    if row and row['file_path']:
        fp = os.path.join(app.config['UPLOAD_FOLDER'], row['file_path'])
        if os.path.exists(fp): os.remove(fp)
    execute_db("DELETE FROM tasks WHERE id=?", (task_id,))
    return jsonify({'message': 'Deleted'})
 
@app.route('/api/tasks/<int:task_id>/toggle', methods=['POST'])
def toggle_task(task_id):
    row = query_db("SELECT * FROM tasks WHERE id=?", (task_id,), one=True)
    if not row:
        return jsonify({'error': 'Not found'}), 404
    if row['status'] == 'pending':
        execute_db("UPDATE tasks SET status='completed', completed_at=? WHERE id=?",
                   (datetime.utcnow().isoformat(), task_id))
    else:
        execute_db("UPDATE tasks SET status='pending', completed_at=NULL WHERE id=?", (task_id,))
    row = query_db("SELECT * FROM tasks WHERE id=?", (task_id,), one=True)
    return jsonify(task_to_dict(row))
 
@app.route('/api/stats')
def get_stats():
    today = date.today().isoformat()
    total     = query_db("SELECT COUNT(*) as n FROM tasks", one=True)['n']
    pending   = query_db("SELECT COUNT(*) as n FROM tasks WHERE status='pending'", one=True)['n']
    completed = query_db("SELECT COUNT(*) as n FROM tasks WHERE status='completed'", one=True)['n']
    overdue   = query_db("SELECT COUNT(*) as n FROM tasks WHERE status='pending' AND deadline < ?", (today,), one=True)['n']
    due_today = query_db("SELECT COUNT(*) as n FROM tasks WHERE status='pending' AND deadline=?", (today,), one=True)['n']
    due_soon  = query_db(
        "SELECT COUNT(*) as n FROM tasks WHERE status='pending' AND deadline > ? AND deadline <= date(?, '+2 days')",
        (today, today), one=True)['n']
    return jsonify({
        'total': total, 'pending': pending, 'completed': completed,
        'overdue': overdue, 'due_today': due_today, 'due_soon': due_soon,
        'completion_rate': round(completed / total * 100) if total else 0
    })
 
@app.route('/api/reminders')
def get_reminders():
    today = date.today()
    rows = query_db("SELECT * FROM tasks WHERE status='pending' AND deadline IS NOT NULL")
    reminders = []
    for r in rows:
        try:
            diff = (date.fromisoformat(r['deadline']) - today).days
        except:
            continue
        if diff <= 2:
            d = task_to_dict(r)
            d['reminder_type'] = diff
            reminders.append(d)
    return jsonify(reminders)
 
@app.route('/api/activity')
def get_activity():
    rows = query_db("SELECT completed_at FROM tasks WHERE completed_at IS NOT NULL")
    activity = {}
    for r in rows:
        try:
            day = r['completed_at'][:10]
            activity[day] = activity.get(day, 0) + 1
        except:
            pass
    return jsonify(activity)
 
@app.route('/uploads/<path:filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
 
init_db()
 
if __name__ == '__main__':
    app.run(debug=True, port=5000)
 