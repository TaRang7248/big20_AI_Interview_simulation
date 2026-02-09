/**
 * AI Interview Program - Main Application Logic
 * Stack: Vanilla JS (ES6+)
 * Features: SPA Routing, Mock Data Management, Interview Simulation
 */

// --- 0. Mock Data (데이터 모델) ---
const MOCK_DB = {
    users: [], // Compatibility: Actual users are now in SQLite/Server
    // users data removed - moved to SQLite DB via server.py
    jobs: [
        { id: 1, title: '2026년 상반기 신입 개발자 공채', deadline: '2026-06-30', content: '백엔드/프론트엔드 개발자 모집' },
        { id: 2, title: 'AI 데이터 분석가 경력직 채용', deadline: '2026-05-15', content: 'Python, SQL 능통자' }
    ],
    applications: [
        // { userId: 'test', jobId: 1, status: 'completed', score: { ... } }
    ],
    interviewQuestions: {
        'phase1': ['자기소개를 간단히 부탁드립니다.', '지원 동기가 무엇인가요?'],
        'phase2': ['가장 열정적으로 임했던 프로젝트 경험을 말씀해주세요.', '갈등 상황을 해결한 경험이 있나요?', '본인의 장단점은 무엇인가요?'],
        'coding': ['문자열 뒤집기 알고리즘을 설명해주세요. (화이트보드 활성화)']
    }
};

// --- 1. Global State (상태 관리) ---
const AppState = {
    currentUser: null, // Logged in user object
    currentJobId: null, // Selected Job ID for interview
    interview: {
        inProgress: false,
        phase: 0, // 0: setup, 1: intro, 2: competency, 3: coding
        questionIndex: 0,
        timer: null,
        timeLeft: 0,
        log: []
    }
};

// --- 2. Code Implementation (로직) ---

// DOM Elements shortcut
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    initRouter();
    initAuth();
    initDashboard();
    initAdmin();
    initInterview();
});

// --- Router Utility ---
function initRouter() {
    // Basic navigation handling logic
    window.navigateTo = (pageId) => {
        // Hide all pages
        $$('.page').forEach(el => el.classList.add('hidden'));
        $$('.page').forEach(el => el.classList.remove('active'));

        // Show target page
        const target = $(`#${pageId}`);
        if (target) {
            target.classList.remove('hidden');
            target.classList.add('active');
            console.log(`Navigated to: ${pageId}`);

            // Run specific page init logic if needed
            if (pageId === 'applicant-dashboard-page') renderJobList();
            if (pageId === 'admin-dashboard-page') renderAdminJobList();
        }
    };

    // Navigation Buttons
    $('#link-signup').addEventListener('click', (e) => { e.preventDefault(); navigateTo('signup-page'); });
    $('#btn-back-login').addEventListener('click', () => navigateTo('login-page'));
    $('#btn-go-home').addEventListener('click', () => {
        if (AppState.currentUser?.type === 'admin') navigateTo('admin-dashboard-page');
        else navigateTo('applicant-dashboard-page');
    });
}

// --- Authentication --
function initAuth() {
    // Login
    $('#login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = $('#login-id').value;
        const pw = $('#login-pw').value;

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id, pw })
            });
            const result = await response.json();

            if (result.success) {
                loginUser(result.user);
            } else {
                showToast(result.message, 'error');
            }
        } catch (error) {
            console.error('Login Error:', error);
            showToast('서버 연결에 실패했습니다.', 'error');
        }
    });

    // SignUp
    $('#signup-form').addEventListener('submit', async (e) => {
        e.preventDefault();

        const newUser = {
            id: $('#reg-id').value,
            pw: $('#reg-pw').value,
            name: $('#reg-name').value,
            dob: $('#reg-dob').value,
            gender: $('#reg-gender').value,
            email: $('#reg-email').value,
            address: $('#reg-addr').value,
            phone: $('#reg-phone').value,
            type: $('input[name="reg-type"]:checked').value
        };

        try {
            const response = await fetch('/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newUser)
            });
            const result = await response.json();

            if (result.success) {
                showToast('회원가입 완료! 로그인해주세요.', 'success');
                navigateTo('login-page');
            } else {
                showToast(result.message, 'error');
            }
        } catch (error) {
            console.error('Register Error:', error);
            showToast('서버 연결에 실패했습니다.', 'error');
        }
    });

    // Logout
    $('#btn-logout').addEventListener('click', () => {
        AppState.currentUser = null;
        $('#navbar').classList.add('hidden');
        navigateTo('login-page');
        showToast('로그아웃 되었습니다.');
    });

    // My Info Link
    $('#link-my-info').addEventListener('click', async () => {
        if (AppState.currentUser) {
            try {
                const response = await fetch(`/api/user/${AppState.currentUser.id}`);
                const result = await response.json();
                if (result.success) {
                    AppState.currentUser = result.user; // Update local state
                    $('#edit-email').value = result.user.email || '';
                    $('#edit-phone').value = result.user.phone || '';
                    navigateTo('myinfo-page');
                } else {
                    showToast('회원 정보를 불러오는데 실패했습니다.', 'error');
                }
            } catch (error) {
                console.error('Fetch User Info Error:', error);
                showToast('서버 연결에 실패했습니다.', 'error');
            }
        }
    });

    // My Info Update
    $('#myinfo-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const confirmPw = $('#confirm-pw').value;
        const newEmail = $('#edit-email').value;
        const newPhone = $('#edit-phone').value;

        try {
            const response = await fetch(`/api/user/${AppState.currentUser.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pw: confirmPw,
                    email: newEmail,
                    phone: newPhone
                })
            });
            const result = await response.json();

            if (result.success) {
                // Update local state partially or refetch
                AppState.currentUser.email = newEmail;
                AppState.currentUser.phone = newPhone;
                showToast('정보가 수정되었습니다.', 'success');
                $('#confirm-pw').value = ''; // clear password input
            } else {
                showToast(result.message || '정보 수정 실패', 'error');
            }
        } catch (error) {
            console.error('Update User Info Error:', error);
            showToast('서버 연결에 실패했습니다.', 'error');
        }
    });

    // My Info Cancel
    $('#btn-cancel-myinfo').addEventListener('click', () => {
        if (AppState.currentUser && AppState.currentUser.type === 'admin') {
            navigateTo('admin-dashboard-page');
        } else {
            navigateTo('applicant-dashboard-page');
        }
    });
}

function loginUser(user) {
    AppState.currentUser = user;
    $('#user-display').textContent = `${user.name}님 (${user.type === 'admin' ? '관리자' : '지원자'})`;
    $('#navbar').classList.remove('hidden');

    // Clear inputs
    $('#login-id').value = '';
    $('#login-pw').value = '';

    if (user.type === 'admin') {
        navigateTo('admin-dashboard-page');
    } else {
        navigateTo('applicant-dashboard-page');
    }
    showToast(`${user.name}님 환영합니다!`, 'success');
}

// --- Applicant Dashboard ---
function initDashboard() {
    $('#link-my-records').addEventListener('click', () => {
        showToast('아직 구현된 기록이 없습니다. (Mock Demo)', 'info');
    });
}

function renderJobList() {
    const list = $('#job-list');
    list.innerHTML = '';
    MOCK_DB.jobs.forEach(job => {
        const li = document.createElement('li');
        li.className = 'job-card';
        li.innerHTML = `
            <div class="job-info">
                <h4>${job.title}</h4>
                <p>마감일: ${job.deadline}</p>
            </div>
            <button class="btn-small" onclick="startInterviewSetup(${job.id})">지원하기</button>
        `;
        list.appendChild(li);
    });
}

// --- Interview Flow ---
// Step 1: Setup
window.startInterviewSetup = (jobId) => {
    AppState.currentJobId = jobId;
    const job = MOCK_DB.jobs.find(j => j.id === jobId);
    $('#setup-job-title').textContent = job.title;

    // Reset Checks
    $('#resume-upload').value = '';
    $('#cam-status').className = 'status pending';
    $('#cam-status').textContent = '확인 필요';
    $('#mic-status').className = 'status pending';
    $('#mic-status').textContent = '확인 필요';
    $('#btn-start-interview').disabled = true;

    navigateTo('interview-setup-page');
};

$('#btn-test-devices').addEventListener('click', async () => {
    // 1. Camera & Mic Permission
    showToast('카메라/마이크 권한을 요청합니다...', 'info');
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });

        // Connect to Video Element
        const video = document.getElementById('user-video');
        if (video) {
            video.srcObject = stream;
            document.getElementById('feed-label').textContent = '내 모습 (Camera On)';
        }

        $('#cam-status').className = 'status ok';
        $('#cam-status').textContent = '정상 (연결됨)';
        $('#mic-status').className = 'status ok';
        $('#mic-status').textContent = '정상 (연결됨)';
        $('#btn-start-interview').disabled = false;

        showToast('장치가 정상적으로 연결되었습니다.', 'success');

    } catch (err) {
        console.error("Device Access Error:", err);
        $('#cam-status').className = 'status error';
        $('#cam-status').textContent = '오류 (권한 거부됨)';
        $('#mic-status').className = 'status error';
        $('#mic-status').textContent = '오류 (권한 거부됨)';
        showToast('카메라/마이크 접근 권한이 필요합니다.', 'error');
    }
});

$('#btn-cancel-interview').addEventListener('click', () => {
    navigateTo('applicant-dashboard-page');
});

// Step 2: Main Interview Logic
$('#btn-start-interview').addEventListener('click', () => {
    // Init Interview State
    AppState.interview = {
        inProgress: true,
        phase: 1, // Start with Intro
        questionIndex: 0,
        logs: [],
        timeLeft: 60 // 60s per question
    };

    // Clear UI
    $('#chat-log').innerHTML = '';
    $('#user-answer').value = '';
    $('#coding-board').classList.add('hidden');

    navigateTo('interview-page');
    runInterviewPhase();
});

function runInterviewPhase() {
    if (!AppState.interview.inProgress) return;

    // Check Phase
    let questions = [];
    let phaseName = '';

    if (AppState.interview.phase === 1) {
        questions = MOCK_DB.interviewQuestions['phase1'];
        phaseName = 'Phase 1: 자기소개';
    } else if (AppState.interview.phase === 2) {
        questions = MOCK_DB.interviewQuestions['phase2'];
        phaseName = 'Phase 2: 역량 검증';
    } else if (AppState.interview.phase === 3) {
        questions = MOCK_DB.interviewQuestions['coding'];
        phaseName = 'Phase 3: 기술 문제';
        $('#coding-board').classList.remove('hidden');
    } else {
        // Finish
        finishInterview();
        return;
    }

    // Check Question Index
    if (AppState.interview.questionIndex >= questions.length) {
        // Next Phase
        AppState.interview.phase++;
        AppState.interview.questionIndex = 0;
        // Recursive call for next phase
        runInterviewPhase();
        return;
    }

    // Update UI
    $('#phase-label').textContent = phaseName;
    const currentQ = questions[AppState.interview.questionIndex];

    // AI Speaking (TTS)
    $('#ai-message').textContent = '...';
    stopListening(); // Stop STT while AI speaks

    // Delay slightly then speak
    setTimeout(() => {
        $('#ai-message').textContent = currentQ;
        addChatLog('AI', currentQ);

        // TTS Call
        speakText(currentQ, () => {
            // After speaking finishes:
            startTimer(60); // Start Timer
            startListening(); // Start STT
        });
    }, 500);
}

function startTimer(seconds) {
    if (AppState.interview.timer) clearInterval(AppState.interview.timer);

    AppState.interview.timeLeft = seconds;
    updateTimerDisplay();

    AppState.interview.timer = setInterval(() => {
        AppState.interview.timeLeft--;
        updateTimerDisplay();

        if (AppState.interview.timeLeft <= 0) {
            clearInterval(AppState.interview.timer);
            submitAnswer(true); // Force submit
        }
    }, 1000);
}

function updateTimerDisplay() {
    const min = Math.floor(AppState.interview.timeLeft / 60);
    const sec = AppState.interview.timeLeft % 60;
    $('#timer-display').textContent = `${min.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;

    // Progress Bar simulation (just visual)
    const totalTime = 60;
    const pct = ((totalTime - AppState.interview.timeLeft) / totalTime) * 100;
    $('#progress-bar').style.width = `${pct}%`;
}

function addChatLog(sender, text) {
    const div = document.createElement('div');
    div.className = `chat-msg ${sender.toLowerCase()}`;
    div.innerHTML = `<strong>${sender}:</strong> ${text}`;
    $('#chat-log').appendChild(div);
    $('#chat-log').scrollTop = $('#chat-log').scrollHeight;
}

$('#btn-submit-answer').addEventListener('click', () => submitAnswer(false));

function submitAnswer(forced) {
    if (AppState.interview.timer) clearInterval(AppState.interview.timer);
    stopListening(); // Stop STT on submit

    const answer = $('#user-answer').value.trim() || (forced ? '(시간 초과)' : '(답변 없음)');
    addChatLog('User', answer);

    // Save Log
    AppState.interview.logs.push({
        phase: AppState.interview.phase,
        qIndex: AppState.interview.questionIndex,
        answer: answer
    });

    $('#user-answer').value = '';

    // Move next
    AppState.interview.questionIndex++;
    runInterviewPhase();
}

function finishInterview() {
    AppState.interview.inProgress = false;
    // Save to Mock DB
    const result = {
        userId: AppState.currentUser.id,
        jobId: AppState.currentJobId,
        date: new Date().toLocaleDateString(),
        scores: {
            tech: Math.floor(Math.random() * 30) + 70, // Mock Score
            prob: Math.floor(Math.random() * 30) + 70,
            comm: Math.floor(Math.random() * 30) + 70,
            atti: Math.floor(Math.random() * 30) + 70
        }
    };
    MOCK_DB.applications.push(result);

    // Show Result Page
    // Animate bars
    navigateTo('result-page');
    setTimeout(() => {
        $('#score-tech').style.width = `${result.scores.tech}%`;
        $('#score-prob').style.width = `${result.scores.prob}%`;
        $('#score-comm').style.width = `${result.scores.comm}%`;
        $('#score-atti').style.width = `${result.scores.atti}%`;

        const avg = (result.scores.tech + result.scores.prob + result.scores.comm + result.scores.atti) / 4;
        $('#pass-fail-badge').textContent = avg >= 80 ? '합격 예측' : '불합격 예측';
        $('#pass-fail-badge').style.color = avg >= 80 ? 'green' : 'red';
    }, 500);
}

// --- Admin Section ---
function initAdmin() {
    $('#admin-menu-jobs').addEventListener('click', () => {
        $('#admin-view-jobs').classList.remove('hidden');
        $('#admin-view-applicants').classList.add('hidden');
    });
    $('#admin-menu-applicants').addEventListener('click', () => {
        $('#admin-view-jobs').classList.add('hidden');
        $('#admin-view-applicants').classList.remove('hidden');
        renderAdminAppList();
    });

    $('#btn-add-job').addEventListener('click', () => {
        const title = prompt('공고 제목을 입력하세요:');
        if (title) {
            MOCK_DB.jobs.push({
                id: Date.now(),
                title: title,
                deadline: '2026-12-31',
                content: '추가된 공고'
            });
            renderAdminJobList();
        }
    });

    initInterview(); // Ensure interview init is called if valid
}

function initInterview() {
    // Placeholder if extra init needed
}

function renderAdminJobList() {
    const tbody = $('#admin-job-table tbody');
    tbody.innerHTML = '';
    MOCK_DB.jobs.forEach(job => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${job.id}</td>
            <td>${job.title}</td>
            <td>${job.deadline}</td>
            <td><button class="btn-small btn-secondary">수정</button></td>
        `;
        tbody.appendChild(tr);
    });
}

function renderAdminAppList() {
    const tbody = $('#admin-app-table tbody');
    tbody.innerHTML = '';
    MOCK_DB.applications.forEach(app => {
        const user = MOCK_DB.users.find(u => u.id === app.userId);
        const job = MOCK_DB.jobs.find(j => j.id === app.jobId);

        const avg = (app.scores.tech + app.scores.prob + app.scores.comm + app.scores.atti) / 4;

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${user ? user.name : 'Unknown'}</td>
            <td>${job ? job.title : 'Deleted Job'}</td>
            <td>${avg.toFixed(1)}</td>
            <td>${avg >= 80 ? 'Pass' : 'Fail'}</td>
            <td><button class="btn-small">상세보기</button></td>
        `;
        tbody.appendChild(tr);
    });
}

// --- Utilities ---
function showToast(msg, type = 'info') {
    const container = $('#toast-container');
    const div = document.createElement('div');
    div.className = `toast ${type}`;
    div.textContent = msg;
    container.appendChild(div);

    // Auto remove
    setTimeout(() => {
        div.remove();
    }, 3000);
}

// --- Audio Utilities ---

// TTS
function speakText(text, callback) {
    if (!('speechSynthesis' in window)) {
        console.warn("TTS not supported.");
        if (callback) callback();
        return;
    }

    // Stop previous
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'ko-KR';
    utterance.rate = 1.0;

    // Voices check (optional)
    const voices = window.speechSynthesis.getVoices();
    // Try to find a Korean voice
    const korVoice = voices.find(v => v.lang.includes('ko'));
    if (korVoice) utterance.voice = korVoice;

    utterance.onend = () => {
        if (callback) callback();
    };

    window.speechSynthesis.speak(utterance);
}

// STT
let recognitionInst = null;

function startListening() {
    $('#user-answer').value = ''; // Reset input

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        $('#user-answer').placeholder = "이 브라우저는 음성 인식을 지원하지 않습니다.";
        return;
    }

    recognitionInst = new SpeechRecognition();
    recognitionInst.lang = 'ko-KR';
    recognitionInst.interimResults = true;
    recognitionInst.continuous = true;

    recognitionInst.onstart = () => {
        $('#user-answer').placeholder = "듣고 있습니다... 답변해주세요.";
        showToast("답변을 말씀해주세요 (음성 인식 중)", "info");
    };

    recognitionInst.onresult = (event) => {
        const transcript = Array.from(event.results)
            .map(result => result[0].transcript)
            .join('');
        $('#user-answer').value = transcript;
    };

    recognitionInst.onerror = (event) => {
        console.error("STT Error:", event.error);
    };

    recognitionInst.start();
}

function stopListening() {
    if (recognitionInst) {
        recognitionInst.stop();
        recognitionInst = null;
    }
}
