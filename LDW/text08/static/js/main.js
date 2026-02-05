let isRecording = false;
let currentSession = null;
let currentQuestion = "";
let currentStep = 1;
let mediaRecorder;
let audioChunks = [];
let timerInterval;
let timeLeft = 90;
let interviewHistory = [];

async function startInterview() {
    const candidateName = document.getElementById('name').value;
    const jobTitle = document.getElementById('job_title').value;

    if (!candidateName || !jobTitle) {
        alert("이름과 지원 직무를 입력해 주세요.");
        return;
    }

    const startBtn = document.getElementById('btn-start');
    startBtn.disabled = true;
    startBtn.innerText = "면접관 연결 중...";

    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: candidateName, job_title: jobTitle })
        });

        const data = await response.json();
        currentSession = data.session_id;
        currentQuestion = data.question;
        currentStep = data.step;

        document.getElementById('start-area').style.opacity = '0';
        setTimeout(() => {
            document.getElementById('start-area').style.display = 'none';
            const interviewArea = document.getElementById('interview-area');
            interviewArea.style.display = 'block';
            setTimeout(() => interviewArea.style.opacity = '1', 50);
            updateUIForQuestion();
            startCamera(); // Start camera for vision AI
        }, 300);

    } catch (error) {
        console.error("Start Error:", error);
        alert("면접을 시작할 수 없습니다. 서버 상태를 확인하세요.");
        startBtn.disabled = false;
        startBtn.innerText = "면접 시작하기";
    }
}

function updateUIForQuestion() {
    document.getElementById('question-text').innerText = currentQuestion;
    document.getElementById('step-counter').innerText = `질문 ${currentStep} / 10`;
    document.getElementById('progress-bar').style.width = `${(currentStep / 10) * 100}%`;
    resetTimer();
}

function resetTimer() {
    clearInterval(timerInterval);
    timeLeft = 90;
    updateTimerUI();
}

function startTimer() {
    timerInterval = setInterval(() => {
        timeLeft--;
        updateTimerUI();
        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            if (isRecording) {
                toggleRecording(); // Auto-stop at 90s
            }
        }
    }, 1000);
}

function updateTimerUI() {
    const timerText = document.getElementById('timer-text');
    const timerProgress = document.querySelector('.timer-progress');

    timerText.innerText = timeLeft;

    // Circular progress - 283 is approx 2 * PI * 45
    const offset = 283 - (timeLeft / 90) * 283;
    timerProgress.style.strokeDashoffset = offset;

    if (timeLeft <= 10) {
        timerProgress.style.stroke = '#fb7185';
    } else {
        timerProgress.style.stroke = 'var(--primary)';
    }
}

async function toggleRecording() {
    if (!isRecording) {
        await startRecording();
    } else {
        await stopRecording();
    }
}

let sttSocket = null;
let silenceTimer = null;

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        // Setup WebSocket for real-time STT
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        sttSocket = new WebSocket(`${protocol}//${window.location.host}/api/ws/stt`);

        sttSocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.text) {
                const resultDiv = document.getElementById('stt-result');
                resultDiv.innerText = data.text;
                // Scroll to bottom
                resultDiv.scrollTop = resultDiv.scrollHeight;
            }
        };

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
                // Send cumulative blob for reliable decoding
                if (sttSocket && sttSocket.readyState === WebSocket.OPEN) {
                    const cumulativeBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
                    sttSocket.send(cumulativeBlob);
                }
            }
        };

        mediaRecorder.onstop = async () => {
            if (sttSocket) sttSocket.close();
            const finalAnswer = document.getElementById('stt-result').innerText;
            await processFinalAnswer(finalAnswer);
        };

        // Collect data every 3 seconds for "real-time" feel
        mediaRecorder.start(3000);
        isRecording = true;

        const btnRecord = document.getElementById('btn-record');
        btnRecord.innerText = "답변 완료 (클릭)";
        btnRecord.classList.add('recording');
        document.getElementById('recording-status').style.display = 'flex';
        document.getElementById('stt-result').innerText = "듣고 있습니다... 90초 이내로 말씀해 주세요.";
        document.getElementById('status-msg').innerText = "";

        startTimer();
    } catch (err) {
        console.error("Microphone Access Error:", err);
        alert("마이크 접근 권한이 필요합니다.");
    }
}

async function stopRecording() {
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        clearInterval(timerInterval);

        const btnRecord = document.getElementById('btn-record');
        btnRecord.innerText = "분석 중...";
        btnRecord.disabled = true;
        btnRecord.classList.remove('recording');
        document.getElementById('recording-status').style.display = 'none';
        document.getElementById('status-msg').innerText = "답변을 평가 중입니다...";
    }
}

async function processFinalAnswer(answerText) {
    if (!answerText || answerText.trim() === "" || answerText.includes("듣고 있습니다")) {
        document.getElementById('status-msg').innerText = "인식된 내용이 없습니다. 다시 말씀해 주세요.";
        enableRecordButton();
        return;
    }

    try {
        // 2. Process Answer
        const response = await fetch('/api/answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSession,
                question: currentQuestion,
                answer: answerText
            })
        });

        const result = await response.json();

        // Save to history
        interviewHistory.push({
            question: currentQuestion,
            answer: answerText,
            evaluation: result.evaluation
        });

        if (result.is_completed) {
            showResults(result.evaluation.pass_fail);
        } else {
            currentQuestion = result.next_question;
            currentStep = result.step;

            const qText = document.getElementById('question-text');
            qText.style.opacity = '0';

            setTimeout(() => {
                updateUIForQuestion();
                qText.style.opacity = '1';
                document.getElementById('status-msg').innerText = result.evaluation.is_follow_up ? "추가 질문이 생성되었습니다." : "다음 질문입니다.";
                enableRecordButton();
            }, 500);
        }

    } catch (error) {
        console.error("Process Error:", error);
        document.getElementById('status-msg').innerText = "처리 중 오류가 발생했습니다.";
        enableRecordButton();
    }
}

function enableRecordButton() {
    const btnRecord = document.getElementById('btn-record');
    btnRecord.disabled = false;
    btnRecord.innerText = "답변 시작";
}

function showResults(passFail) {
    document.getElementById('interview-area').style.display = 'none';
    const resultArea = document.getElementById('result-area');
    resultArea.style.display = 'block';

    document.getElementById('pass-fail-value').innerText = passFail || "평가 완료";
    if (passFail === "불합격") {
        document.getElementById('pass-fail-value').style.color = '#fb7185';
    }

    const feedbackList = document.getElementById('feedback-list');
    feedbackList.innerHTML = "";

    interviewHistory.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = 'feedback-item';
        div.innerHTML = `
            <div class="feedback-q">Q${index + 1}: ${item.question}</div>
            <div class="feedback-f">${item.evaluation.feedback}</div>
            <div class="feedback-s">점수: ${item.evaluation.score}점</div>
        `;
        feedbackList.appendChild(div);
    });
}
// --- Vision AI Logic ---
let visionInterval = null;

async function startCamera() {
    try {
        const video = document.getElementById('camera-preview');
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        video.srcObject = stream;
        
        // Start analyzing every 3 seconds
        visionInterval = setInterval(analyzeFrame, 3000);
    } catch (err) {
        console.error("Camera Error:", err);
        document.getElementById('emotion-badge').innerText = "No Camera";
    }
}

async function analyzeFrame() {
    const video = document.getElementById('camera-preview');
    if (!video || !video.srcObject) return;

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(async (blob) => {
        if (!blob) return;
        const formData = new FormData();
        formData.append('file', blob, 'frame.jpg');

        try {
            const response = await fetch('/api/analyze_face', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (data.dominant_emotion) {
                const badge = document.getElementById('emotion-badge');
                // Translate emotion to Korean if desired, or keep English
                const emotionMap = {
                    "angry": "분노",
                    "disgust": "혐오",
                    "fear": "공포",
                    "happy": "행복",
                    "sad": "슬픔",
                    "surprise": "놀람",
                    "neutral": "평온"
                };
                badge.innerText = emotionMap[data.dominant_emotion] || data.dominant_emotion;
            }
        } catch (err) {
            console.error("Frame Analysis Error:", err);
        }
    }, 'image/jpeg');
}
