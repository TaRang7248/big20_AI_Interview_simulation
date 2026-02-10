import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, send_from_directory
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

app = Flask(__name__, static_url_path='', static_folder='.')

# Upload Configuration
UPLOAD_FOLDER = 'uploads/resumes'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# DB Connection settings
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "interview_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579") # Default fallback or from env
DB_PORT = os.getenv("DB_PORT", "5432")

def get_db_connection():
    hosts = [DB_HOST, "127.0.0.1", "localhost"]
    last_error = None
    
    for host in hosts:
        try:
            print(f"Attempting to connect to DB at {host}...")
            conn = psycopg2.connect(
                host=host,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                port=DB_PORT,
                connect_timeout=3
            )
            print(f"Successfully connected to DB at {host}")
            return conn
        except psycopg2.OperationalError as e:
            last_error = e
            print(f"Failed to connect to {host}: {e}")
            
    print(f"All connection attempts failed. Last error: {last_error}")
    print(f"Connection Details: Host={DB_HOST}, DB={DB_NAME}, User={DB_USER}, Port={DB_PORT}")
    raise last_error



def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Create users table if not exists
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id_name TEXT PRIMARY KEY,
            pw TEXT NOT NULL,
            name TEXT NOT NULL,
            dob TEXT,
            gender TEXT,
            email TEXT,
            address TEXT,
            phone TEXT,
            type TEXT DEFAULT 'applicant'
        )
    ''')

    print(f"Database initialized/connected to {DB_NAME} at {DB_HOST}")
    
    # Create interview_announcement table if not exists
    c.execute('''
        CREATE TABLE IF NOT EXISTS interview_announcement (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            job TEXT,
            deadline TEXT,
            content TEXT,
            id_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_name) REFERENCES users(id_name)
        )
    ''')
    
    
    # Create interview_information table if not exists
    c.execute('''
        CREATE TABLE IF NOT EXISTS interview_information (
            id SERIAL PRIMARY KEY,
            id_name TEXT,
            job TEXT,
            resume TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_name) REFERENCES users(id_name)
        )
    ''')

    # Create interview_answer table if not exists
    c.execute('''
        CREATE TABLE IF NOT EXISTS interview_answer (
            id SERIAL PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL
        )
    ''')

    
    # Migration: Rename columns if they exist with old names
    try:
        # Check if 'id' exists in users and rename to 'id_name'
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='id'")
        if c.fetchone():
            c.execute("ALTER TABLE users RENAME COLUMN id TO id_name")
            print("Migrated users table: id -> id_name")

        # Check if 'writer_id' exists in interview_announcement and rename to 'id_name'
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='interview_announcement' AND column_name='writer_id'")
        if c.fetchone():
            c.execute("ALTER TABLE interview_announcement RENAME COLUMN writer_id TO id_name")
            print("Migrated interview_announcement table: writer_id -> id_name")

        # Check if 'job' exists in interview_announcement
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='interview_announcement' AND column_name='job'")
        if not c.fetchone():
            c.execute("ALTER TABLE interview_announcement ADD COLUMN job TEXT")
            print("Migrated interview_announcement table: Added job column")
            
        conn.commit()
    except Exception as e:
        print(f"Migration Warning: {e}")
        conn.rollback()

    conn.commit()
    conn.close()


@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Check if ID exists
        c.execute('SELECT id_name FROM users WHERE id_name = %s', (data['id_name'],))

        if c.fetchone():
            return jsonify({'success': False, 'message': '이미 존재하는 아이디입니다.'}), 400
            
        c.execute('''
            INSERT INTO users (id_name, pw, name, dob, gender, email, address, phone, type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            data['id_name'], 
            data['pw'], 
            data['name'], 
            data.get('dob'), 
            data.get('gender'), 
            data.get('email'), 
            data.get('address'), 
            data.get('phone'), 
            data.get('type', 'applicant')
        ))
        conn.commit()
        return jsonify({'success': True, 'message': '회원가입 완료'})
    except Exception as e:
        print(f"Register Error: {e}")
        return jsonify({'success': False, 'message': '서버 오류가 발생했습니다.'}), 500
    finally:
        if conn: conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        
        # User lookup logic
        # Note: In production, password should be hashed. Plain text for this demo.
        c.execute('SELECT * FROM users WHERE id_name = %s AND pw = %s', (data['id_name'], data['pw']))

        row = c.fetchone()
        
        if row:
            # pyscopg2 RealDictCursor returns a dict-like object
            user = dict(row)
            return jsonify({'success': True, 'user': user})
        else:
            return jsonify({'success': False, 'message': '아이디 또는 비밀번호가 일치하지 않습니다.'}), 401
            
    except Exception as e:
        print(f"Login Error: {e}")
        return jsonify({'success': False, 'message': '서버 오류가 발생했습니다.'}), 500
    finally:
        if conn: conn.close()

@app.route('/api/verify-password', methods=['POST'])
def verify_password():
    data = request.json
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Verify Password
        c.execute('SELECT pw FROM users WHERE id_name = %s', (data['id_name'],))

        row = c.fetchone()
        
        if row and row[0] == data['pw']:
             return jsonify({'success': True})
        else:
             return jsonify({'success': False, 'message': '비밀번호가 일치하지 않습니다.'}), 401

    except Exception as e:
        print(f"Verify Password Error: {e}")
        return jsonify({'success': False, 'message': '서버 오류가 발생했습니다.'}), 500
    finally:
        if conn: conn.close()

@app.route('/api/user/<id_name>', methods=['GET'])
def get_user_info(id_name):

    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute('SELECT id_name, name, dob, gender, email, address, phone, type FROM users WHERE id_name = %s', (id_name,))

        row = c.fetchone()
        
        if row:
            user = dict(row)
            return jsonify({'success': True, 'user': user})
        else:
            return jsonify({'success': False, 'message': '사용자를 찾을 수 없습니다.'}), 404
    except Exception as e:
        print(f"Get User Info Error: {e}")
        return jsonify({'success': False, 'message': '서버 오류가 발생했습니다.'}), 500
    finally:
        if conn: conn.close()

@app.route('/api/user/<id_name>', methods=['PUT'])
def update_user_info(id_name):

    data = request.json
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # 1. Verify Password
        c.execute('SELECT pw FROM users WHERE id_name = %s', (id_name,))

        row = c.fetchone()
        if not row:
             return jsonify({'success': False, 'message': '사용자를 찾을 수 없습니다.'}), 404
        
        if row[0] != data['pw']:
            return jsonify({'success': False, 'message': '비밀번호가 일치하지 않습니다.'}), 401

        # 2. Update Info
        c.execute('''
            UPDATE users 
            SET email = %s, phone = %s, address = %s
            WHERE id_name = %s
        ''', (data['email'], data['phone'], data['address'], id_name))

        conn.commit()
        
        return jsonify({'success': True, 'message': '정보가 수정되었습니다.'})

    except Exception as e:
        print(f"Update User Info Error: {e}")
        return jsonify({'success': False, 'message': '서버 오류가 발생했습니다.'}), 500
    finally:
        if conn: conn.close()

@app.route('/api/change-password', methods=['POST'])
def change_password():
    data = request.json
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Update Password
        c.execute('UPDATE users SET pw = %s WHERE id_name = %s', (data['new_pw'], data['id_name']))

        conn.commit()
        
        if c.rowcount > 0:
            return jsonify({'success': True, 'message': '비밀번호가 변경되었습니다.'})
        else:
            return jsonify({'success': False, 'message': '사용자를 찾을 수 없습니다.'}), 404

    except Exception as e:
        print(f"Change Password Error: {e}")
        return jsonify({'success': False, 'message': '서버 오류가 발생했습니다.'}), 500
    finally:
        if conn: conn.close()

@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT id, title, job, deadline, content, id_name, to_char(created_at, 'YYYY-MM-DD') as created_at FROM interview_announcement ORDER BY created_at DESC")

        rows = c.fetchall()
        
        jobs = [dict(row) for row in rows]
        return jsonify({'success': True, 'jobs': jobs})
    except Exception as e:
        print(f"Get Jobs Error: {e}")
        return jsonify({'success': False, 'message': '서버 오류가 발생했습니다.'}), 500
    finally:
        if conn: conn.close()

@app.route('/api/jobs/<id>', methods=['GET'])
def get_job_detail(id):
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT id, title, job, deadline, content, id_name, to_char(created_at, 'YYYY-MM-DD') as created_at FROM interview_announcement WHERE id = %s", (id,))
        
        row = c.fetchone()
        
        if row:
            job = dict(row)
            return jsonify({'success': True, 'job': job})
        else:
            return jsonify({'success': False, 'message': '공고를 찾을 수 없습니다.'}), 404
    except Exception as e:
        print(f"Get Job Detail Error: {e}")
        return jsonify({'success': False, 'message': '서버 오류가 발생했습니다.'}), 500
    finally:
        if conn: conn.close()

@app.route('/api/jobs', methods=['POST'])
def create_job():
    data = request.json
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO interview_announcement (title, job, deadline, content, id_name)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        ''', (data['title'], data.get('job', ''), data['deadline'], data.get('content', ''), data.get('id_name')))

        
        new_id = c.fetchone()[0]
        conn.commit()
        
        return jsonify({'success': True, 'message': '공고가 등록되었습니다.', 'id': new_id})
    except Exception as e:
        print(f"Create Job Error: {e}")
        return jsonify({'success': False, 'message': '서버 오류가 발생했습니다.'}), 500
    finally:
        if conn: conn.close()

@app.route('/api/jobs/<id>', methods=['PUT'])
def update_job(id):
    data = request.json
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''
            UPDATE interview_announcement
            SET title = %s, job = %s, deadline = %s, content = %s
            WHERE id = %s
        ''', (data['title'], data.get('job', ''), data['deadline'], data.get('content', ''), id))
        conn.commit()
        
        if c.rowcount > 0:
            return jsonify({'success': True, 'message': '공고가 수정되었습니다.'})
        else:
            return jsonify({'success': False, 'message': '공고를 찾을 수 없습니다.'}), 404
            
    except Exception as e:
        print(f"Update Job Error: {e}")
        return jsonify({'success': False, 'message': '서버 오류가 발생했습니다.'}), 500
    finally:
        if conn: conn.close()

@app.route('/api/jobs/<id>', methods=['DELETE'])
def delete_job(id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('DELETE FROM interview_announcement WHERE id = %s', (id,))
        conn.commit()
        
        if c.rowcount > 0:
            return jsonify({'success': True, 'message': '공고가 삭제되었습니다.'})
        else:
            return jsonify({'success': False, 'message': '공고를 찾을 수 없습니다.'}), 404
            
    except Exception as e:
        print(f"Delete Job Error: {e}")
        return jsonify({'success': False, 'message': '서버 오류가 발생했습니다.'}), 500
    finally:
        if conn: conn.close()

@app.route('/api/upload/resume', methods=['POST'])
def upload_resume():
    if 'resume' not in request.files:
        return jsonify({'success': False, 'message': '파일이 없습니다.'}), 400
    
    file = request.files['resume']
    id_name = request.form.get('id_name')
    job_title = request.form.get('job_title') # Job title or code from the announcement

    if file.filename == '':
        return jsonify({'success': False, 'message': '선택된 파일이 없습니다.'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{id_name}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # DB Save
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # Save to interview_information
            c.execute('''
                INSERT INTO interview_information (id_name, job, resume)
                VALUES (%s, %s, %s)
            ''', (id_name, job_title, filepath))
            
            conn.commit()
            return jsonify({'success': True, 'message': '이력서가 업로드되었습니다.', 'filepath': filepath})
        except Exception as e:
            print(f"Resume Upload DB Error: {e}")
            return jsonify({'success': False, 'message': '데이터베이스 저장 중 오류가 발생했습니다.'}), 500
        finally:
            if conn: conn.close()

    else:
        return jsonify({'success': False, 'message': '허용되지 않는 파일 형식입니다. (PDF만 가능)'}), 400

import webbrowser
from threading import Timer

if __name__ == '__main__':
    init_db()
    
    def open_browser():
        if not os.environ.get("WERKZEUG_RUN_MAIN"):
            webbrowser.open_new("http://localhost:5000/")

    Timer(1, open_browser).start()
    print("Serving on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
