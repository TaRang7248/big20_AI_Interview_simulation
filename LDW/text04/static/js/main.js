let isRecording = false;
let currentSession = null;
let currentQuestion = "";
let candidateName = "";
let jobTitle = "";
let ws;

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/stt`);
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.status === "recording") {
            const sttResult = document.getElementById('stt-result');
            sttResult.innerText = data.text;
            sttResult.classList.add('pulse-text');
        }
    };
    
    ws.onclose = () => {
        console.log("WebSocket closed. Reconnecting...");
        setTimeout(initWebSocket, 2000);
    };
}

initWebSocket();

async function startInterview() {
    candidateName = document.getElementById('name').value;
    jobTitle = document.getElementById('job_title').value;

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

        document.getElementById('start-area').style.opacity = '0';
        setTimeout(() => {
            document.getElementById('start-area').style.display = 'none';
            const interviewArea = document.getElementById('interview-area');
            interviewArea.style.display = 'block';
            setTimeout(() => interviewArea.style.opacity = '1', 50);
            document.getElementById('question-text').innerText = currentQuestion;
        }, 300);
        
    } catch (error) {
        console.error("Start Error:", error);
        alert("면접을 시작할 수 없습니다. 서버 상태를 확인하세요.");
        startBtn.disabled = false;
        startBtn.innerText = "면접 시작하기";
    }
}

async function toggleRecording() {
    if (!isRecording) {
        await startServerRecording();
    } else {
        await stopServerRecording();
    }
}

async function startServerRecording() {
    try {
        const response = await fetch('/api/start-recording', { method: 'POST' });
        if (response.ok) {
            isRecording = true;
            const btnRecord = document.getElementById('btn-record');
            btnRecord.innerText = "답변 완료 (클릭)";
            btnRecord.classList.add('recording');
            document.getElementById('recording-status').style.display = 'flex';
            document.getElementById('stt-result').innerText = "듣고 있습니다... 말씀해 주세요.";
            document.getElementById('status-msg').innerText = "";
        }
    } catch (err) {
        console.error("Recording Start Error:", err);
        alert("마이크 구동에 실패했습니다.");
    }
}

async function stopServerRecording() {
    isRecording = false;
    const btnRecord = document.getElementById('btn-record');
    btnRecord.innerText = "답변 분석 중...";
    btnRecord.disabled = true;
    btnRecord.classList.remove('recording');
    document.getElementById('recording-status').style.display = 'none';
    document.getElementById('status-msg').innerText = "답변을 텍스트로 변환하고 있습니다...";

    try {
        const response = await fetch('/api/stop-recording', { method: 'POST' });
        const data = await response.json();
        const answerText = data.text;
        
        document.getElementById('stt-result').innerText = `"${answerText}"`;

        if (!answerText || answerText.trim() === "") {
            document.getElementById('status-msg').innerText = "인식된 내용이 없습니다. 다시 말씀해 주세요.";
            btnRecord.disabled = false;
            btnRecord.innerText = "답변 시작";
            return;
        }

        await processAnswer(answerText);
    } catch (error) {
        console.error("Stop Error:", error);
        document.getElementById('status-msg').innerText = "오류가 발생했습니다. 다시 시도해 주세요.";
        btnRecord.disabled = false;
        btnRecord.innerText = "답변 시작";
    }
}

async function processAnswer(answerText) {
    try {
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
        const qText = document.getElementById('question-text');
        qText.style.opacity = '0';
        
        setTimeout(() => {
            qText.innerText = currentQuestion;
            qText.style.opacity = '1';
            document.getElementById('status-msg').innerText = evalData.is_follow_up ? "추가 질문이 생성되었습니다." : "다음 질문입니다.";
            
            const btnRecord = document.getElementById('btn-record');
            btnRecord.disabled = false;
            btnRecord.innerText = "답변 시작";
        }, 500);

    } catch (error) {
        console.error("Process Error:", error);
        document.getElementById('status-msg').innerText = "평가 중 오류가 발생했습니다.";
        const btnRecord = document.getElementById('btn-record');
        btnRecord.disabled = false;
        btnRecord.innerText = "답변 시작";
    }
}
