/**
 * AI Interview Program - Main Application Logic
 * Stack: Vanilla JS (ES6+)
 * Features: SPA Routing, API Integration, Audio Recording, Interview Logic
 */

// --- 0. Mock Data (Data Model) ---
const MOCK_DB = {
    jobs: [],
};

// --- 1. Global State ---
const AppState = {
    currentUser: null,
    currentJobId: null,
    tempPassword: null,
    interview: {
        inProgress: false,
        interviewNumber: null,
        currentQuestion: null,
        timer: null,
        timeLeft: 0,
        mediaRecorder: null,
        audioChunks: [],
        devicesReady: false,
    }
};

// --- 2. Helper Functions ---
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

function showLoading(show, text = "잠시만 기다려주세요...") {
    const overlay = $('#loading-overlay');
    const textEl = $('#loading-text');
    if (show) {
        textEl.textContent = text;
        overlay.classList.remove('hidden');
    } else {
        overlay.classList.add('hidden');
    }
}

function showToast(message, type = 'info') {
    const container = $('#toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// --- 3. Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initRouter();
    initAuth();
    initDashboard();
    initAdmin();
    initInterview();
});

// --- 4. Router ---
function initRouter() {
    window.navigateTo = (pageId) => {
        $$('.page').forEach(el => el.classList.add('hidden'));
        $$('.page').forEach(el => el.classList.remove('active'));

        const target = $(`#${pageId}`);
        if (target) {
            target.classList.remove('hidden');
            target.classList.add('active');

            if (pageId === 'applicant-dashboard-page') fetchJobs();
            if (pageId === 'admin-dashboard-page') fetchJobs();

            // Auto-start device test when entering setup page
            if (pageId === 'interview-setup-page') {
                testDevices();
            }
        }
    };

    $('#link-signup').addEventListener('click', (e) => { e.preventDefault(); navigateTo('signup-page'); });
    $('#btn-back-login').addEventListener('click', () => navigateTo('login-page'));
    $('#btn-go-home').addEventListener('click', () => {
        if (AppState.currentUser?.type === 'admin') navigateTo('admin-dashboard-page');
        else navigateTo('applicant-dashboard-page');
    });
}

// --- 5. Auth ---
function initAuth() {
    $('#login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = $('#login-id').value;
        const pw = $('#login-pw').value;

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_name: id, pw })
            });
            const result = await response.json();
            if (result.success) {
                loginUser(result.user);
            } else {
                showToast(result.message, 'error');
            }
        } catch (error) {
            console.error('Login Error:', error);
            showToast('서버 연결 실패', 'error');
        }
    });

    $('#signup-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const newUser = {
            id_name: $('#reg-id').value,
            pw: $('#reg-pw').value,
            name: $('#reg-name').value,
            dob: `${$('#reg-dob-year').value}-${$('#reg-dob-month').value.padStart(2, '0')}-${$('#reg-dob-day').value.padStart(2, '0')}`,
            gender: $('#reg-gender').value,
            email: $('#reg-email').value,
            address: $('#reg-addr').value,
            phone: `${$('#reg-phone-1').value}-${$('#reg-phone-2').value}-${$('#reg-phone-3').value}`,
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
            showToast('서버 연결 실패', 'error');
        }
    });

    $('#btn-logout').addEventListener('click', () => {
        AppState.currentUser = null;
        $('#navbar').classList.add('hidden');
        navigateTo('login-page');
    });
}

function loginUser(user) {
    AppState.currentUser = user;
    $('#user-display').textContent = `${user.name}님 (${user.type === 'admin' ? '관리자' : '지원자'})`;
    $('#navbar').classList.remove('hidden');
    $('#login-id').value = '';
    $('#login-pw').value = '';

    if (user.type === 'admin') navigateTo('admin-dashboard-page');
    else navigateTo('applicant-dashboard-page');
}

// --- 6. Dashboard & Jobs ---
function initDashboard() {
    $('#link-my-info').addEventListener('click', () => navigateTo('myinfo-page'));
}

async function fetchJobs() {
    try {
        const response = await fetch('/api/jobs');
        const result = await response.json();
        if (result.success) {
            MOCK_DB.jobs = result.jobs;
            renderJobList();
            if ($('#admin-job-table')) renderAdminJobList();
        }
    } catch (error) {
        console.error('Fetch Jobs Error:', error);
    }
}

function renderJobList() {
    const list = $('#job-list');
    list.innerHTML = '';
    MOCK_DB.jobs.forEach(job => {
        const li = document.createElement('li');
        li.className = 'job-card';
        li.innerHTML = `
            <div class="job-info">
                <h4>[${job.job || '직무 미정'}] ${job.title}</h4>
                <p>생성일: ${job.created_at} | 마감일: ${job.deadline}</p>
            </div>
            <button class="btn-small" onclick="viewJobDetail(${job.id})">확인하기</button>
        `;
        list.appendChild(li);
    });
}

window.viewJobDetail = async (jobId) => {
    try {
        const response = await fetch(`/api/jobs/${jobId}`);
        const result = await response.json();
        if (result.success) {
            const job = result.job;
            AppState.currentJobId = job.id;
            $('#detail-job-title').textContent = `[${job.job || '-'}] ${job.title}`;
            $('#detail-job-job').textContent = job.job || '-';
            $('#detail-job-writer').textContent = job.id_name || '-';
            $('#detail-job-created-at').textContent = job.created_at;
            $('#detail-job-deadline').textContent = job.deadline;
            $('#detail-job-content').textContent = job.content;
            navigateTo('job-detail-page');
        }
    } catch (e) { console.error(e); }
};

$('#btn-back-to-list').addEventListener('click', () => navigateTo('applicant-dashboard-page'));
$('#btn-apply-job').addEventListener('click', () => {
    if (AppState.currentJobId) startInterviewSetup(AppState.currentJobId);
});

// --- 7. Interview Setup ---
window.startInterviewSetup = (jobId) => {
    AppState.currentJobId = jobId;
    const job = MOCK_DB.jobs.find(j => j.id === jobId);
    $('#setup-job-title').textContent = `[${job.job || '-'}] ${job.title}`;
    $('#resume-upload').value = '';
    $('#resume-status').textContent = '';
    // $('#btn-start-interview').disabled = true; // Don't disable initially
    navigateTo('interview-setup-page');
};


// Automatic Device Test
async function testDevices() {
    $('#cam-status').className = 'status pending';
    $('#cam-status').textContent = '연결 중...';
    $('#mic-status').className = 'status pending';
    $('#mic-status').textContent = '연결 중...';

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        // Use global user-video if possible, or bind here?
        // Actually, we bind to #user-video in the Interview Page mostly, 
        // but for test we assume it's "Ready".
        // We can't show video in Setup page unless we add a video element there.
        // Assuming "Background" check is sufficient to enable button.

        $('#cam-status').className = 'status ok';
        $('#cam-status').textContent = '정상';
        $('#mic-status').className = 'status ok';
        $('#mic-status').textContent = '정상';
        $('#btn-start-interview').disabled = false;

        // Stop stream to release for now
        // stream.getTracks().forEach(track => track.stop()); // Don't stop, keep it open or just release. 
        // Keeping it open might be better for seamless transition? 
        // But let's stop and request again in interview. 
        // Actually, if we stop, permissions might persist. 
        stream.getTracks().forEach(track => track.stop());

        AppState.interview.devicesReady = true;

    } catch (err) {
        console.error("Device Error:", err);
        $('#cam-status').className = 'status error';
        $('#cam-status').textContent = '실패';
        $('#mic-status').className = 'status error';
        $('#mic-status').textContent = '실패';
        // showToast('카메라/마이크 권한이 필요합니다.', 'error'); // Don't toast immediately on load
        AppState.interview.devicesReady = false;
    }
}

$('#btn-cancel-interview').addEventListener('click', () => navigateTo('applicant-dashboard-page'));

// --- 8. Interview Logic ---
function initInterview() {
    $('#btn-start-interview').addEventListener('click', handleStartInterview);
    $('#btn-submit-answer').addEventListener('click', handleSubmitAnswer);
}

async function handleStartInterview() {
    const fileInput = $('#resume-upload');
    if (!fileInput.files || fileInput.files.length === 0) {
        alert('이력서를 업로드해주세요.');
        return;
    }

    // 1. Navigate Immediately (Optimistic UI)
    navigateTo('interview-page');

    // UI Initialization on Interview Page
    $('#ai-message').textContent = "이력서를 분석하고 면접을 준비 중입니다...";
    $('#chat-log').innerHTML = ''; // Clear previous log
    addChatLog('System', '면접 환경을 설정하고 있습니다.');

    // 2. Perform Setup in Background
    try {
        // Check Devices (Post-navigation)
        if (!AppState.interview.devicesReady) {
            addChatLog('System', '카메라/마이크 권한 확인 중...');
            await testDevices();
            if (!AppState.interview.devicesReady) {
                alert('카메라와 마이크 사용 권한이 필요합니다.');
                navigateTo('interview-setup-page'); // Go back if failed
                return;
            }
        }

        // Upload Resume
        addChatLog('System', '이력서 업로드 중...');
        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('resume', file);
        formData.append('id_name', AppState.currentUser.id_name);

        const job = MOCK_DB.jobs.find(j => j.id === AppState.currentJobId);
        formData.append('job_title', job.job);

        const upResp = await fetch('/api/upload/resume', { method: 'POST', body: formData });
        const upResult = await upResp.json();
        if (!upResult.success) throw new Error(upResult.message);

        // Start Interview
        addChatLog('System', 'AI 면접관 연결 중...');
        const startResp = await fetch('/api/interview/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id_name: AppState.currentUser.id_name,
                job_title: job.job
            })
        });
        const startResult = await startResp.json();
        if (!startResult.success) throw new Error(startResult.message);

        // Success
        AppState.interview.inProgress = true;
        AppState.interview.interviewNumber = startResult.interview_number;
        AppState.interview.currentQuestion = startResult.question;

        // Start Interaction
        startQuestionSequence(startResult.question);

    } catch (error) {
        console.error(error);
        alert(`오류 발생: ${error.message}`);
        navigateTo('interview-setup-page'); // Go back on error
    }
}

function startQuestionSequence(question) {
    // UI Update
    addChatLog('AI', question);
    $('#ai-message').textContent = question;
    $('#user-answer').value = '';
    $('#user-answer').placeholder = "답변을 말씀해주세요 (녹음 중...)";

    // 1. TTS
    speakText(question, () => {
        // 2. Start Timer & Recording after TTS
        startTimer(90); // 90 seconds (increased for speech)
        startRecording();
    });
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
            handleSubmitAnswer(true); // Force submit
        }
    }, 1000);
}

function updateTimerDisplay() {
    const min = Math.floor(AppState.interview.timeLeft / 60);
    const sec = AppState.interview.timeLeft % 60;
    $('#timer-display').textContent = `${min.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true }); // Video for feed

        // Video Feed
        const video = $('#user-video');
        video.srcObject = stream;

        // Audio Recorder
        AppState.interview.mediaRecorder = new MediaRecorder(stream);
        AppState.interview.audioChunks = [];

        AppState.interview.mediaRecorder.ondataavailable = event => {
            AppState.interview.audioChunks.push(event.data);
        };

        AppState.interview.mediaRecorder.start();
        $('#feed-label').textContent = "녹음 중... (Speaking)";

    } catch (err) {
        console.error("Recording Error:", err);
        showToast("마이크 접근 실패", 'error');
    }
}

function stopRecording() {
    if (AppState.interview.mediaRecorder && AppState.interview.mediaRecorder.state !== 'inactive') {
        AppState.interview.mediaRecorder.stop();
        $('#feed-label').textContent = "녹음 종료 (Processing)";
    }
}

async function handleSubmitAnswer(forced = false) {
    if (!AppState.interview.inProgress) return;

    clearInterval(AppState.interview.timer);
    stopRecording();

    // Wait slightly for recorder to finish saving chunks
    await new Promise(r => setTimeout(r, 500));

    const audioBlob = new Blob(AppState.interview.audioChunks, { type: 'audio/webm' });
    const audioFile = new File([audioBlob], "answer.webm", { type: 'audio/webm' });

    showLoading(true, "답변을 분석하고 다음 질문을 생성 중입니다...");

    const formData = new FormData();
    formData.append('interview_number', AppState.interview.interviewNumber);
    formData.append('applicant_name', AppState.currentUser.name);
    // Find job title
    const job = MOCK_DB.jobs.find(j => j.id === AppState.currentJobId);
    formData.append('job_title', job.job);

    // Calc time used
    const timeUsed = 90 - AppState.interview.timeLeft;
    formData.append('answer_time', `${timeUsed}초`);
    formData.append('audio', audioFile);

    try {
        const response = await fetch('/api/interview/answer', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        if (!result.success) throw new Error(result.message);

        showLoading(false);

        // Show Transcript (Optional)
        if (result.transcript) {
            addChatLog('User', result.transcript);
        } else {
            addChatLog('User', '(음성 답변 제출됨)');
        }

        // Check if finished
        if (result.next_question.includes("면접을 마칩니다")) {
            finishInterview();
        } else {
            AppState.interview.currentQuestion = result.next_question;
            startQuestionSequence(result.next_question);
        }

    } catch (error) {
        showLoading(false);
        console.error(error);
        showToast('답변 제출 실패. 다시 시도해주세요.', 'error');
        // Restart recording? Or just let them retry? 
        // For simplicity, let's just let them retry clicking submit? 
        // But audio is gone. 
        // Ideally should allow re-record. 
        // But for this simulation, we just error out.
    }
}

function finishInterview() {
    AppState.interview.inProgress = false;
    navigateTo('result-page');

    // Stop Camera
    const video = $('#user-video');
    if (video.srcObject) {
        video.srcObject.getTracks().forEach(track => track.stop());
        video.srcObject = null;
    }
}

function addChatLog(sender, text) {
    const div = document.createElement('div');
    div.className = `chat-msg ${sender.toLowerCase()}`;
    div.innerHTML = `<strong>${sender}:</strong> ${text}`;
    $('#chat-log').appendChild(div);
    $('#chat-log').scrollTop = $('#chat-log').scrollHeight;
}

// --- TTS Utility ---
function speakText(text, callback) {
    if (!window.speechSynthesis) {
        if (callback) callback();
        return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'ko-KR';
    utterance.rate = 1.0;
    utterance.onend = () => {
        if (callback) callback();
    };
    window.speechSynthesis.speak(utterance);
}


// --- 9. Admin Functions ---
function initAdmin() {
    $('#admin-menu-jobs').addEventListener('click', () => {
        $('#admin-view-jobs').classList.remove('hidden');
        $('#admin-view-applicants').classList.add('hidden');
        $('#admin-job-register-page').classList.add('hidden');
        $('#admin-job-edit-page').classList.add('hidden');
        fetchJobs();
    });

    $('#btn-add-job').addEventListener('click', () => {
        $('#admin-view-jobs').classList.add('hidden');
        $('#admin-job-register-page').classList.remove('hidden');
        $('#job-title').value = '';
        $('#job-job').value = '';
        $('#job-content').value = '';
        $('#job-deadline').value = '';
    });

    $('#btn-cancel-job-register').addEventListener('click', () => {
        $('#admin-job-register-page').classList.add('hidden');
        $('#admin-view-jobs').classList.remove('hidden');
    });

    $('#admin-job-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            const resp = await fetch('/api/jobs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: $('#job-title').value,
                    job: $('#job-job').value,
                    content: $('#job-content').value,
                    deadline: $('#job-deadline').value,
                    id_name: AppState.currentUser.id_name
                })
            });
            const res = await resp.json();
            if (res.success) {
                showToast('등록 완료', 'success');
                $('#admin-job-register-page').classList.add('hidden');
                $('#admin-view-jobs').classList.remove('hidden');
                fetchJobs();
            }
        } catch (e) { console.error(e); }
    });
}

function renderAdminJobList() {
    const tbody = $('#admin-job-table tbody');
    tbody.innerHTML = '';
    MOCK_DB.jobs.forEach(job => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${job.id}</td>
            <td>${job.job || '-'}</td>
            <td>${job.title}</td>
            <td>${job.id_name || '-'}</td>
            <td>${job.created_at}</td>
            <td>${job.deadline}</td>
            <td>
                <button class="btn-small btn-secondary" onclick="deleteJob(${job.id})">삭제</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

window.deleteJob = async (id) => {
    if (!confirm('정말 삭제하시겠습니까?')) return;
    try {
        const resp = await fetch(`/api/jobs/${id}?id_name=${AppState.currentUser.id_name}`, { method: 'DELETE' });
        const res = await resp.json();
        if (res.success) fetchJobs();
        else showToast(res.message, 'error');
    } catch (e) { showToast('오류 발생', 'error'); }
};
