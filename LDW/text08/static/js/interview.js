const urlParams = new URLSearchParams(window.location.search);
const sessionId = urlParams.get('session_id');

let currentQuestionId = null;
let mediaRecorder;
let audioChunks = [];
let timerInterval;
const TIME_LIMIT = 90;

// Init
window.onload = async () => {
    initWebcam();
    loadNextQuestion();
};

async function initWebcam() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        document.getElementById('webcam').srcObject = stream;
    } catch (e) {
        alert("Webcam access denied.");
    }
}

async function loadNextQuestion() {
    try {
        const res = await fetch(`/api/interview/${sessionId}/current`);
        const data = await res.json();

        if (data.finished) {
            window.location.href = `/feedback.html?session_id=${sessionId}`;
            return;
        }

        currentQuestionId = data.question_id;
        document.getElementById('question-text').innerText = `Q${data.index}. ${data.question}`;
        document.getElementById('progress').innerText = `${data.index}/${data.total}`;

        // Reset buttons for next question
        document.getElementById('start-btn').disabled = false;
        document.getElementById('stop-btn').disabled = true;

        resetTimer();
    } catch (e) {
        console.error("Error loading question:", e);
    }
}

// ... (previous code)

function resetTimer() {
    clearInterval(timerInterval);
    let timeLeft = TIME_LIMIT;
    document.getElementById('timer').innerText = timeLeft;

    timerInterval = setInterval(() => {
        timeLeft--;
        document.getElementById('timer').innerText = timeLeft;
        if (timeLeft <= 0) {
            clearInterval(timerInterval); // Stop timer

            // Check if recording
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                stopRecording(); // Will trigger submitAnswer normally
            } else {
                forceTimeOutSubmit(); // Not recording, force submit as timeout
            }
        }
    }, 1000);
}

// New function for timeout submission without recording
async function forceTimeOutSubmit() {
    document.getElementById('start-btn').disabled = true;
    document.getElementById('stop-btn').disabled = true;
    document.getElementById('stt-output').innerText = "시간 초과! 다음 질문으로 넘어갑니다...";

    // We send a submit request with text indicating timeout
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('question_id', currentQuestionId);
    // answer_text triggers the fallback in backend
    formData.append('answer_text', "시간 초과로 답변을 제출하지 못했습니다.");

    try {
        const res = await fetch('/api/interview/submit', {
            method: 'POST',
            body: formData
        });
        const result = await res.json();

        // Slightly different UI feedback
        document.getElementById('stt-output').innerText = `시간 초과. (점수: ${result.score})`;

        // Wait a bit then next
        setTimeout(loadNextQuestion, 3000);

    } catch (e) {
        console.error("Timeout submittion failed", e);
        // Even if failed, try to go next or alert
        setTimeout(loadNextQuestion, 3000);
    }
}

async function startRecording() {
    // ... (rest of code)

    const stream = document.getElementById('webcam').srcObject;
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = event => {
        audioChunks.push(event.data);
    };

    mediaRecorder.onstop = submitAnswer;

    mediaRecorder.start();
    document.getElementById('start-btn').disabled = true;
    document.getElementById('stop-btn').disabled = false;

    // Simulate STT Stream (Mock)
    document.getElementById('stt-output').innerText = "듣고 있습니다...";
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        document.getElementById('start-btn').disabled = false;
        document.getElementById('stop-btn').disabled = true;
        clearInterval(timerInterval);
    }
}

async function submitAnswer() {
    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('question_id', currentQuestionId);
    formData.append('audio', audioBlob, 'answer.webm');

    // Canvas Image
    const canvas = document.getElementById('archCanvas');
    // Convert canvas to blob if needed or just skip for now

    document.getElementById('stt-output').innerText = "답변 제출 및 평가 중...";

    try {
        const res = await fetch('/api/interview/submit', {
            method: 'POST',
            body: formData
        });
        const result = await res.json();

        document.getElementById('stt-output').innerText = `답변: ${result.stt}\n점수: ${result.score}`;

        // Wait a bit then next
        setTimeout(loadNextQuestion, 3000);

    } catch (e) {
        alert("Submission failed");
    }
}
