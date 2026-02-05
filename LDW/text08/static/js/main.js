let isRecording = false;
let currentSession = null;
let currentQuestion = "";
let currentStep = 1;
let mediaRecorder;
let audioChunks = [];
let timerInterval;
let timeLeft = 90;
let interviewHistory = [];

// Initialize on load for Interview Page
document.addEventListener('DOMContentLoaded', async () => {
    // Check if we are on the interview page by looking for the question text element
    if (document.getElementById('question-text')) {
        await initInterviewPage();
    }
});

async function initInterviewPage() {
    const intervieweeName = sessionStorage.getItem('interviewee_name');
    const intervieweeJob = sessionStorage.getItem('interviewee_job');

    if (!intervieweeName || !intervieweeJob) {
        // Only redirect if we are NOT on feedback page or login page
        // Wait, main.js is loaded on index/interview pages
        alert("로그인 정보가 없습니다.");
        window.location.href = '/';
        return;
    }

    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: intervieweeName, job_title: intervieweeJob })
        });
        const data = await response.json();

        currentSession = data.session_id;
        currentQuestion = data.question;
        currentStep = data.step;
        sessionStorage.setItem('current_session_id', currentSession);

        document.getElementById('interview-area').style.display = 'block';
        setTimeout(() => document.getElementById('interview-area').style.opacity = '1', 100);

        updateUIForQuestion();
        startCamera();

    } catch (e) {
        console.error("Session Start Error", e);
        alert("면접 세션을 시작할 수 없습니다.");
    }
}

// Global scope startInterview not needed as Login page handles it via form/redirect
function startInterview() {
    // Legacy support or removed
    console.warn("Using legacy startInterview function");
}

function updateUIForQuestion() {
    document.getElementById('question-text').innerText = currentQuestion;
    document.getElementById('step-counter').innerText = `질문 ${currentStep} / 10`;
    document.getElementById('progress-bar').style.width = `${(currentStep / 10) * 100}%`;
    resetTimer();

    // Architect Question Handling (Mock logic: if question contains "아키텍처" or "설계", show canvas tools)
    // For now, always visible or user toggles.
    // Let's autoshow submit button if keyword detected for UX
    if (currentQuestion.includes("아키텍처") || currentQuestion.includes("구조") || currentQuestion.includes("설계") || currentQuestion.includes("그려")) {
        document.getElementById('btn-submit-architecture').style.display = 'inline-block';
        // Highlight canvas panel?
    } else {
        document.getElementById('btn-submit-architecture').style.display = 'none';
    }
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

    if (timerText) timerText.innerText = timeLeft;

    if (timerProgress) {
        // Circular progress - 283 is approx 2 * PI * 45
        const offset = 283 - (timeLeft / 90) * 283;
        timerProgress.style.strokeDashoffset = offset;

        if (timeLeft <= 10) {
            timerProgress.style.stroke = '#fb7185';
        } else {
            timerProgress.style.stroke = 'var(--primary)';
        }
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

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        sttSocket = new WebSocket(`${protocol}//${window.location.host}/api/ws/stt`);

        sttSocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.text) {
                const resultDiv = document.getElementById('stt-result');
                resultDiv.innerText = data.text;
                resultDiv.scrollTop = resultDiv.scrollHeight;
            }
        };

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
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

        interviewHistory.push({
            question: currentQuestion,
            answer: answerText,
            evaluation: result.evaluation
        });

        // Update session storage for feedback page
        sessionStorage.setItem('interview_history', JSON.stringify(interviewHistory));

        if (result.is_completed) {
            finishInterview(result.evaluation);
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

function finishInterview(finalEvaluation) {
    // Prepare data for feedback page
    let finalData = {
        passFail: finalEvaluation ? finalEvaluation.result_status : "평가 완료",
        confidence: finalEvaluation ? finalEvaluation.confidence_score : 0,
        details: interviewHistory
    };

    sessionStorage.setItem('interview_results', JSON.stringify(finalData));

    // Redirect
    window.location.href = '/feedback';
}

// --- Architecture Canvas Logic ---
async function submitArchitecture() {
    if (!confirm("현재 캔버스에 그려진 아키텍처를 제출하고 평가받으시겠습니까?")) return;

    try {
        const imgData = getCanvasImage(); // from canvas.js
        document.getElementById('status-msg').innerText = "아키텍처 분석 중...";

        const response = await fetch('/api/evaluate_architecture', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSession,
                image: imgData
            })
        });

        const result = await response.json();
        alert(`평가 결과: ${result.score}점\n피드백: ${result.feedback}`);

        // Save this feedback to show in final report if needed
        let archFeedback = JSON.parse(sessionStorage.getItem('arch_feedback') || '[]');
        archFeedback.push(result);
        sessionStorage.setItem('arch_feedback', JSON.stringify(archFeedback));

        document.getElementById('status-msg').innerText = "아키텍처 평가가 완료되었습니다.";

    } catch (e) {
        console.error("Arch Submit Error", e);
        alert("아키텍처 제출 실패");
    }
}


// --- Vision AI Logic ---
let visionInterval = null;

async function startCamera() {
    try {
        const video = document.getElementById('camera-preview');
        // Only if element exists
        if (!video) return;

        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        video.srcObject = stream;

        visionInterval = setInterval(analyzeFrame, 3000);
    } catch (err) {
        console.error("Camera Error:", err);
        const badge = document.getElementById('emotion-badge');
        if (badge) badge.innerText = "No Camera";
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
        if (currentSession) {
            formData.append('session_id', currentSession);
        }

        try {
            const response = await fetch('/api/analyze_face', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (data.dominant_emotion) {
                const badge = document.getElementById('emotion-badge');
                if (badge) {
                    const emotionMap = {
                        "angry": "분노",
                        "disgust": "혐오",
                        "fear": "공포",
                        "happy": "행복", // happy -> 행복 (미소)
                        "sad": "슬픔",
                        "surprise": "놀람",
                        "neutral": "평온"
                    };
                    badge.innerText = emotionMap[data.dominant_emotion] || data.dominant_emotion;
                }
            }
        } catch (err) {
            console.error("Frame Analysis Error:", err);
        }
    }, 'image/jpeg');
}
