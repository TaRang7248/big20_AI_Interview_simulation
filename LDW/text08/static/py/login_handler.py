import js
from pyscript import document
from pyodide.http import pyfetch
import json

async def function_start_interview(event=None):
    username = document.getElementById('username').value
    job_role = document.getElementById('job_role').value

    if not username or not job_role:
        js.alert("모든 정보를 입력해주세요.")
        return

    # 1. Login/Register
    login_data = js.FormData.new()
    login_data.append('username', username)
    login_data.append('job_role', job_role)

    try:
        response = await pyfetch(
            url='/api/auth/login',
            method='POST',
            body=login_data
        )
        user = await response.json()

        # 2. Start Interview
        start_data = js.FormData.new()
        start_data.append('user_id', user['user_id'])
        start_data.append('job_role', job_role)
        start_data.append('candidate_name', username)

        start_res = await pyfetch(
            url='/api/interview/start',
            method='POST',
            body=start_data
        )
        session = await start_res.json()

        if 'session_id' in session:
            js.window.location.href = f"/interview.html?session_id={session['session_id']}"
            
    except Exception as e:
        js.alert(f"Error starting interview: {str(e)}")

# Expose function to global scope
from pyodide.ffi import create_proxy
start_proxy = create_proxy(function_start_interview)
js.window.startInterview = start_proxy
