let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let currentSession = null;
let currentQuestion = "";
let candidateName = "";
let jobTitle = "";

async function startInterview() {
    candidateName = document.getElementById('name').value;
    jobTitle = document.getElementById('job_title').value;

    if (!candidateName || !jobTitle) {
        alert("이름과 지원 직무를 입력해 주세요.");
        return;
    }

    document.getElementById('btn-start').disabled = true;
    document.getElementById('btn-start').innerText = "면접관 연결 중...";

    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: candidateName, job_title: jobTitle })
        });

        const data = await response.json();
        currentSession = data.session_id;
        currentQuestion = data.question;

        document.getElementById('start-area').style.display = 'none';
        document.getElementById('interview-area').style.display = 'block';
        document.getElementById('question-text').innerText = currentQuestion;
    } catch (error) {
        console.error("Start Error:", error);
        alert("면접을 시작할 수 없습니다. 서버 상태를 확인하세요.");
        document.getElementById('btn-start').disabled = false;
        document.getElementById('btn-start').innerText = "면접 시작하기";
    }
}

async function toggleRecording() {
    if (!isRecording) {
        startRecording();
    } else {
        stopRecording();
    }
}

async function startRecording() {
    audioChunks = [];
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            await processAudio(audioBlob);
        };

        mediaRecorder.start();
        isRecording = true;
        document.getElementById('btn-record').innerText = "답변 완료 (클릭)";
        document.getElementById('btn-record').style.background = "#ef4444";
        document.getElementById('recording-status').style.display = 'flex';
        document.getElementById('stt-result').innerText = "듣고 있습니다... 말씀해 주세요.";
        document.getElementById('status-msg').innerText = "";
    } catch (err) {
        alert("마이크 사용 권한이 필요합니다.");
    }
}

function stopRecording() {
    mediaRecorder.stop();
    isRecording = false;
    document.getElementById('btn-record').innerText = "답변 시작";
    document.getElementById('btn-record').style.background = "#4f46e5";
    document.getElementById('recording-status').style.display = 'none';
    document.getElementById('btn-record').disabled = true;
    document.getElementById('status-msg').innerText = "답변 분석 중...";
}

async function processAudio(blob) {
    const formData = new FormData();
    formData.append('audio', blob, 'recording.wav');

    try {
        // 1. Transcribe (STT)
        const sttResponse = await fetch('/api/transcribe', {
            method: 'POST',
            body: formData
        });
        const sttData = await sttResponse.json();
        const answerText = sttData.text;
        
        document.getElementById('stt-result').innerText = `"${answerText}"`;

        if (!answerText || answerText.trim() === "") {
            document.getElementById('status-msg').innerText = "인식된 내용이 없습니다. 다시 말씀해 주세요.";
            document.getElementById('btn-record').disabled = false;
            return;
        }

        // 2. Process Answer & Get Next Question
        const evalResponse = await fetch('/api/answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                candidate_name: candidateName,
                job_title: jobTitle,
                question: currentQuestion,
                answer: answerText
            })
        });

        const evalData = await evalResponse.json();
        
        // Update UI with next question
        currentQuestion = evalData.next_step_question;
        document.getElementById('question-text').innerText = currentQuestion;
        document.getElementById('status-msg').innerText = evalData.is_follow_up ? "추가 질문이 생성되었습니다." : "다음 질문입니다.";
        
        document.getElementById('btn-record').disabled = false;

    } catch (error) {
        console.error("Process Error:", error);
        document.getElementById('status-msg').innerText = "오류가 발생했습니다. 다시 시도해 주세요.";
        document.getElementById('btn-record').disabled = false;
    }
}
