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
TIME_LIMIT = 5
is_recording = False

# Speech Recognition Global Variables
recognition = None
recognized_text_buffer = ""

async def init():
    global session_id, recognition
    url_params = js.URLSearchParams.new(window.location.search)
    session_id = url_params.get('session_id')
    
    # Initialize Speech Recognition
    init_speech_recognition()
    
    await init_webcam()
    await load_next_question()

def init_speech_recognition():
    global recognition
    if hasattr(js.window, 'webkitSpeechRecognition'):
        recognition = js.window.webkitSpeechRecognition.new()
        recognition.continuous = True
        recognition.interimResults = True
        recognition.lang = 'ko-KR' # Set language to Korean

        def on_result(event):
            global recognized_text_buffer
            interim_transcript = ""
            final_transcript = ""

            # Iterate through results
            for i in range(event.resultIndex, event.results.length):
                # Use .item() instead of [] for JsProxy objects
                result = event.results.item(i)
                transcript = result.item(0).transcript
                if result.isFinal:
                    final_transcript += transcript
                else:
                    interim_transcript += transcript
            
            # Combine stored final buffer with current interim
            display_text = recognized_text_buffer + final_transcript + interim_transcript
            
            # Update UI
            document.getElementById('stt-output').innerText = display_text
            
            # Update buffer if we have new final text
            if final_transcript:
                recognized_text_buffer += final_transcript + " "

        def on_error(event):
            js.console.error(f"Speech recognition error: {event.error}")

        recognition.onresult = create_proxy(on_result)
        recognition.onerror = create_proxy(on_error)
        
    else:
        js.console.warn("Web Speech API not supported in this browser.")

async def init_webcam():
    try:
        # Fix: Create a proper JS object for constraints using JSON parsing
        # to_js on a dict creates a Map, which getUserMedia doesn't accept.
        constraints_json = json.dumps({"video": True, "audio": True})
        constraints = js.JSON.parse(constraints_json)
        
        stream = await window.navigator.mediaDevices.getUserMedia(constraints)
        video_element = document.getElementById('webcam')
        video_element.srcObject = stream
        
        js.console.log("Webcam initialized successfully")
    except Exception as e:
        js.console.error(f"Webcam access denied or error: {e}")
        js.alert(f"Webcam error: {e}")

async def load_next_question():
    global current_question_id, audio_chunks, recognized_text_buffer
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
        recognized_text_buffer = "" # Reset text buffer for next question
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
    global media_recorder, audio_chunks, is_recording, recognition
    
    try:
        video_element = document.getElementById('webcam')
        stream = video_element.srcObject
        media_recorder = js.MediaRecorder.new(stream)
        audio_chunks = []
        
        def on_data_available(e):
            audio_chunks.append(e.data)
            
        def on_stop(e):
            global is_recording
            is_recording = False
            window.setTimeout(create_proxy(submit_answer), 0)

        media_recorder.ondataavailable = create_proxy(on_data_available)
        media_recorder.onstop = create_proxy(on_stop)
        
        media_recorder.start()
        is_recording = True
        
        # Start Speech Recognition
        if recognition:
            try:
                recognition.start()
            except Exception as re:
                js.console.log(f"Recognition start error (might be already started): {re}")
        
        document.getElementById('start-btn').disabled = True
        document.getElementById('stop-btn').disabled = False
        document.getElementById('stt-output').innerText = "듣고 있습니다..."
        
    except Exception as e:
        js.console.error(f"Error starting recording: {e}")
        js.alert("녹음 시작 중 오류가 발생했습니다.")

def stop_recording(event=None):
    global media_recorder, recognition
    if media_recorder and media_recorder.state != 'inactive':
        media_recorder.stop()
        
        # Stop Speech Recognition
        if recognition:
            recognition.stop()
            
        document.getElementById('start-btn').disabled = False
        document.getElementById('stop-btn').disabled = True
        if timer_interval:
            window.clearInterval(timer_interval)

async def submit_answer(event=None):
    global audio_chunks, session_id, current_question_id, recognized_text_buffer
    
    try:
        # Create Blob from chunks
        # We need to convert python list of JS objects to JS array
        js_chunks = to_js(audio_chunks)
        audio_blob = js.Blob.new(js_chunks, field_type="video/webm") # Helper might be needed for options
        # Note: js.Blob.new takes (sequence, options_dict)
        # to_js on a list creates a JsProxy for the list.
        
        form_data = js.FormData.new()
        form_data.append('session_id', session_id)
        if current_question_id:
            form_data.append('question_id', current_question_id)
        form_data.append('audio', audio_blob, 'answer.webm')
        
        # Send the real-time recognized text as a fallback or hint if you wanted
        # But user didn't ask to change backend submission logic to use this text specifically instead of STT, 
        # but displaying it in the report might be good.
        # For now, let's keep backend processing as primary but we could send `recognized_text_buffer`.
        
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
