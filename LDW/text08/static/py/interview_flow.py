import js
from pyscript import document, window
from pyodide.http import pyfetch
from pyodide.ffi import create_proxy, to_js
import json

session_id = None
current_question_id = None
media_recorder = None
audio_chunks = []
timer_interval = None
TIME_LIMIT = 90
is_recording = False

async def init():
    global session_id
    url_params = js.URLSearchParams.new(window.location.search)
    session_id = url_params.get('session_id')
    
    await init_webcam()
    await load_next_question()

async def init_webcam():
    try:
        constraints = to_js({"video": True, "audio": True})
        stream = await window.navigator.mediaDevices.getUserMedia(constraints)
        video_element = document.getElementById('webcam')
        video_element.srcObject = stream
    except Exception as e:
        js.console.error(f"Webcam access denied: {e}")
        js.alert("Webcam access denied.")

async def load_next_question():
    global current_question_id, audio_chunks
    try:
        response = await pyfetch(f'/api/interview/{session_id}/current')
        data = await response.json()
        
        if data.get('finished'):
            window.location.href = f'/feedback.html?session_id={session_id}'
            return

        current_question_id = data.get('question_id') # Might be missing based on API analysis, but flow uses it
        
        q_text = f"Q{data.get('index')}. {data.get('question')}"
        document.getElementById('question-text').innerText = q_text
        document.getElementById('progress').innerText = f"{data.get('index')}/{data.get('total')}"
        
        # Reset state
        audio_chunks = []
        document.getElementById('start-btn').disabled = False
        document.getElementById('stop-btn').disabled = True
        document.getElementById('stt-output').innerText = "답변 준비 중..."
        
        reset_timer()
        
    except Exception as e:
        js.console.error(f"Error loading question: {e}")

def reset_timer():
    global timer_interval, TIME_LIMIT
    if timer_interval:
        window.clearInterval(timer_interval)
    
    time_left = TIME_LIMIT
    document.getElementById('timer').innerText = str(time_left)
    
    def timer_callback():
        nonlocal time_left
        time_left -= 1
        document.getElementById('timer').innerText = str(time_left)
        
        if time_left <= 0:
            window.clearInterval(timer_interval)
            if is_recording:
                stop_recording()
            else:
                window.setTimeout(create_proxy(force_timeout_submit), 0)

    timer_interval = window.setInterval(create_proxy(timer_callback), 1000)

async def force_timeout_submit(event=None):
    document.getElementById('start-btn').disabled = True
    document.getElementById('stop-btn').disabled = True
    document.getElementById('stt-output').innerText = "시간 초과! 다음 질문으로 넘어갑니다..."
    
    form_data = js.FormData.new()
    form_data.append('session_id', session_id)
    if current_question_id:
        form_data.append('question_id', current_question_id)
    form_data.append('answer_text', "대답하지 않음.")
    
    try:
        await pyfetch(
            url='/api/interview/submit',
            method='POST',
            body=form_data
        )
        window.setTimeout(create_proxy(load_next_question), 3000)
    except Exception as e:
        js.console.error(f"Timeout submission failed: {e}")
        window.setTimeout(create_proxy(load_next_question), 3000)

async def start_recording(event=None):
    global media_recorder, audio_chunks, is_recording
    
    try:
        video_element = document.getElementById('webcam')
        stream = video_element.srcObject
        media_recorder = js.MediaRecorder.new(stream)
        audio_chunks = []
        
        def on_data_available(e):
            audio_chunks.append(e.data)
            
        def on_stop(e):
            nonlocal is_recording
            is_recording = False
            window.setTimeout(create_proxy(submit_answer), 0)

        media_recorder.ondataavailable = create_proxy(on_data_available)
        media_recorder.onstop = create_proxy(on_stop)
        
        media_recorder.start()
        is_recording = True
        
        document.getElementById('start-btn').disabled = True
        document.getElementById('stop-btn').disabled = False
        document.getElementById('stt-output').innerText = "듣고 있습니다..."
        
    except Exception as e:
        js.console.error(f"Error starting recording: {e}")
        js.alert("녹음 시작 중 오류가 발생했습니다.")

def stop_recording(event=None):
    global media_recorder
    if media_recorder and media_recorder.state != 'inactive':
        media_recorder.stop()
        document.getElementById('start-btn').disabled = False
        document.getElementById('stop-btn').disabled = True
        if timer_interval:
            window.clearInterval(timer_interval)

async def submit_answer(event=None):
    global audio_chunks, session_id, current_question_id
    
    try:
        # Create Blob from chunks
        # We need to convert python list of JS objects to JS array
        js_chunks = to_js(audio_chunks)
        audio_blob = js.Blob.new(js_chunks, field_type="audio/webm") # Helper might be needed for options
        # Note: js.Blob.new takes (sequence, options_dict)
        # to_js on a list creates a JsProxy for the list.
        
        form_data = js.FormData.new()
        form_data.append('session_id', session_id)
        if current_question_id:
            form_data.append('question_id', current_question_id)
        form_data.append('audio', audio_blob, 'answer.webm')
        
        # Canvas Image
        canvas = document.getElementById('archCanvas')
        # canvas.toBlob requires a callback in JS.
        # Simplification: We will skip canvas upload for now or use sync if possible (toDataURL then blob)
        # Or just skip it as per interview.js "Convert canvas to blob if needed or just skip for now"
        
        document.getElementById('stt-output').innerText = "답변 제출 및 평가 중..."
        
        response = await pyfetch(
            url='/api/interview/submit',
            method='POST',
            body=form_data
        )
        result = await response.json()
        
        score = 0
        stt_text = ""
        if result:
            stt_text = result.get('stt', '')
            score = result.get('score', 0)
            
        document.getElementById('stt-output').innerText = f"답변: {stt_text}\n점수: {score}"
        
        window.setTimeout(create_proxy(load_next_question), 3000)
        
    except Exception as e:
        js.console.error(f"Submission failed: {e}")
        js.alert("제출 실패")

# Initialize
# We need to wait for DOM to be ready or just run init
# PyScript runs this when loaded.
window.setTimeout(create_proxy(init), 100)

# Expose functions for buttons
start_record_proxy = create_proxy(start_recording)
stop_record_proxy = create_proxy(stop_recording)

js.window.startRecording = start_record_proxy
js.window.stopRecording = stop_record_proxy
