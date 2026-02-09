import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, send_from_directory
import os
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

app = Flask(__name__, static_url_path='', static_folder='.')

# DB Connection settings
DB_HOST = "127.0.0.1"
DB_NAME = "interview_db"
DB_USER = "postgres"
DB_PASS = os.getenv("POSTGRES_PASSWORD", "013579") # Default fallback or from env
DB_PORT = "5432"

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Create users table if not exists
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
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
    conn.commit()
    conn.close()
    print(f"Database initialized/connected to {DB_NAME} at {DB_HOST}")

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
        c.execute('SELECT id FROM users WHERE id = %s', (data['id'],))
        if c.fetchone():
            return jsonify({'success': False, 'message': '이미 존재하는 아이디입니다.'}), 400
            
        c.execute('''
            INSERT INTO users (id, pw, name, dob, gender, email, address, phone, type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            data['id'], 
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
        c.execute('SELECT * FROM users WHERE id = %s AND pw = %s', (data['id'], data['pw']))
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
        c.execute('SELECT pw FROM users WHERE id = %s', (data['id'],))
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

@app.route('/api/user/<id>', methods=['GET'])
def get_user_info(id):
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute('SELECT id, name, dob, gender, email, address, phone, type FROM users WHERE id = %s', (id,))
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

@app.route('/api/user/<id>', methods=['PUT'])
def update_user_info(id):
    data = request.json
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # 1. Verify Password
        c.execute('SELECT pw FROM users WHERE id = %s', (id,))
        row = c.fetchone()
        if not row:
             return jsonify({'success': False, 'message': '사용자를 찾을 수 없습니다.'}), 404
        
        if row[0] != data['pw']:
            return jsonify({'success': False, 'message': '비밀번호가 일치하지 않습니다.'}), 401

        # 2. Update Info
        c.execute('''
            UPDATE users 
            SET email = %s, phone = %s, address = %s
            WHERE id = %s
        ''', (data['email'], data['phone'], data['address'], id))
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
        c.execute('UPDATE users SET pw = %s WHERE id = %s', (data['new_pw'], data['id']))
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
