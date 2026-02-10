/**
 * AI Interview Program - Main Application Logic
 * Stack: Vanilla JS (ES6+)
 * Features: SPA Routing, Mock Data Management, Interview Simulation
 */

// --- 0. Mock Data (데이터 모델) ---
const MOCK_DB = {
    users: [], // Compatibility: Actual users are now in SQLite/Server
    // users data removed - moved to SQLite DB via server.py
    jobs: [], // Will be fetched from API
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
    tempPassword: null, // Temporarily store confirmed password for update
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
    initInputMasking(); // Added Input Masking
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
        const id = $('#login-id').value.trim();
        const pw = $('#login-pw').value.trim();

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
            showToast('서버 연결에 실패했습니다.', 'error');
        }
    });

    // SignUp
    $('#signup-form').addEventListener('submit', async (e) => {
        e.preventDefault();

        const newUser = {
            id_name: $('#reg-id').value.trim(),
            pw: $('#reg-pw').value.trim(),
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

    // My Info Link -> Password Check Logic
    $('#link-my-info').addEventListener('click', () => {
        if (AppState.currentUser) {
            $('#check-pw-input').value = '';
            navigateTo('password-check-page');
        }
    });

    // Password Check Submit
    $('#password-check-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const inputPw = $('#check-pw-input').value;

        try {
            const response = await fetch('/api/verify-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_name: AppState.currentUser.id_name, pw: inputPw })
            });

            const result = await response.json();

            if (result.success) {
                // Success: Save PW temporarily and Fetch latest info
                AppState.tempPassword = inputPw;
                await fetchAndShowMyInfo();
            } else {
                showToast(result.message || '비밀번호가 일치하지 않습니다.', 'error');
            }
        } catch (error) {
            console.error('Verify PW Error:', error);
            showToast('서버 연결에 실패했습니다.', 'error');
        }
    });

    // Cancel Password Check
    $('#btn-cancel-pw-check').addEventListener('click', () => {
        goHome();
    });


    // Helper: Fetch User Info and Show Edit Page
    async function fetchAndShowMyInfo() {
        try {
            const response = await fetch(`/api/user/${AppState.currentUser.id_name}`);
            const result = await response.json();
            if (result.success) {
                AppState.currentUser = result.user; // Update local state

                $('#edit-id').value = result.user.id_name || '';
                $('#edit-name').value = result.user.name || '';
                $('#edit-dob').value = result.user.dob || '';

                const genderMap = { 'male': '남성', 'female': '여성' };
                $('#edit-gender').value = genderMap[result.user.gender] || result.user.gender || '';

                $('#edit-email').value = result.user.email || '';
                $('#edit-addr').value = result.user.address || '';

                // Phone number split
                const phone = result.user.phone || '';
                const phoneParts = phone.split('-');
                $('#edit-phone-1').value = phoneParts[0] || '';
                $('#edit-phone-2').value = phoneParts[1] || '';
                $('#edit-phone-3').value = phoneParts[2] || '';

                navigateTo('myinfo-page');
            } else {
                showToast('회원 정보를 불러오는데 실패했습니다.', 'error');
            }
        } catch (error) {
            console.error('Fetch User Info Error:', error);
            showToast('서버 연결에 실패했습니다.', 'error');
        }
    }


    // My Info Update
    $('#myinfo-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const newEmail = $('#edit-email').value;
        const newAddr = $('#edit-addr').value;
        const newPhone = `${$('#edit-phone-1').value}-${$('#edit-phone-2').value}-${$('#edit-phone-3').value}`;

        // Use previously verified password
        const verifiedPw = AppState.tempPassword;

        if (!verifiedPw) {
            showToast('세션이 만료되었습니다. 다시 시도해주세요.', 'error');
            navigateTo('password-check-page');
            return;
        }

        try {
            const response = await fetch(`/api/user/${AppState.currentUser.id_name}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pw: verifiedPw,
                    email: newEmail,
                    address: newAddr,
                    phone: newPhone
                })
            });
            const result = await response.json();

            if (result.success) {
                // Update local state
                AppState.currentUser.email = newEmail;
                AppState.currentUser.address = newAddr;
                AppState.currentUser.phone = newPhone;

                // Clear temp password for security
                AppState.tempPassword = null;

                showToast('정보가 수정되었습니다.', 'success');

                // Auto redirect to home
                setTimeout(() => {
                    goHome();
                }, 1000);

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
        AppState.tempPassword = null;
        goHome();
    });

    // Password Change Button (in My Info)
    $('#btn-change-pw').addEventListener('click', () => {
        $('#new-pw').value = '';
        $('#confirm-new-pw').value = '';
        navigateTo('password-change-page');
    });

    // Password Change Cancel
    $('#btn-cancel-pw-change').addEventListener('click', () => {
        navigateTo('myinfo-page');
    });

    // Password Change Submit
    $('#password-change-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const newPw = $('#new-pw').value;
        const confirmPw = $('#confirm-new-pw').value;

        if (newPw !== confirmPw) {
            showToast('비밀번호가 일치하지 않습니다.', 'error');
            return;
        }

        try {
            const response = await fetch('/api/change-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id_name: AppState.currentUser.id_name,
                    new_pw: newPw
                })
            });
            const result = await response.json();

            if (result.success) {
                showToast('비밀번호가 변경되었습니다.', 'success');
                AppState.tempPassword = null; // Clear temp password

                // Option: Logout or Go Home. 
                // Let's go to Home as per typical flow, or maybe Logout for security.
                // Request didn't specify, but "Moving to Change Password Page" imply flow.
                // Let's go to Login page to force re-login with new PW is safest.
                // But user might find it annoying. Let's go to Home.
                // Actually, let's follow the standard "Cancel" behavior which goes to Home/Dashboard.
                // Wait, "Cancel" goes to My Info page according to logic above.
                // "Change Complete" button.. let's go to Home.
                setTimeout(() => {
                    goHome();
                }, 1000);
            } else {
                showToast(result.message || '비밀번호 변경 실패', 'error');
            }
        } catch (error) {
            console.error('Change Password Error:', error);
            showToast('서버 연결에 실패했습니다.', 'error');
        }
    });

    function goHome() {
        if (AppState.currentUser && AppState.currentUser.type === 'admin') {
            navigateTo('admin-dashboard-page');
        } else {
            navigateTo('applicant-dashboard-page');
        }
    }
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
    // Initial fetch
    fetchJobs();

    $('#link-my-records').addEventListener('click', () => {
        showToast('아직 구현된 기록이 없습니다. (Mock Demo)', 'info');
    });
}

// Fetch Jobs from Server
async function fetchJobs() {
    try {
        const response = await fetch('/api/jobs');
        const result = await response.json();
        if (result.success) {
            MOCK_DB.jobs = result.jobs;
            renderJobList();
            if (AppState.currentUser && AppState.currentUser.type === 'admin') {
                renderAdminJobList();
            }
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



// --- Job Detail View ---
window.viewJobDetail = async (jobId) => {
    try {
        const response = await fetch(`/api/jobs/${jobId}`);
        const result = await response.json();

        if (result.success) {
            const job = result.job;
            AppState.currentJobId = job.id; // Set current Job ID

            $('#detail-job-title').textContent = `[${job.job || '-'}] ${job.title}`;
            $('#detail-job-job').textContent = job.job || '-';
            $('#detail-job-writer').textContent = job.id_name || '알 수 없음';
            $('#detail-job-created-at').textContent = job.created_at;
            $('#detail-job-deadline').textContent = job.deadline;

            // Handle newlines in content
            $('#detail-job-content').textContent = job.content;

            navigateTo('job-detail-page');
        } else {
            showToast(result.message || '공고 정보를 불러오는데 실패했습니다.', 'error');
        }
    } catch (error) {
        console.error('View Job Detail Error:', error);
        showToast('서버 연결에 실패했습니다.', 'error');
    }
};

$('#btn-back-to-list').addEventListener('click', () => {
    navigateTo('applicant-dashboard-page');
});

$('#btn-apply-job').addEventListener('click', () => {
    if (AppState.currentJobId) {
        startInterviewSetup(AppState.currentJobId);
    }
});

// --- Interview Flow ---
// Step 1: Setup
// --- Interview Flow ---
// Step 1: Setup
window.startInterviewSetup = (jobId) => {
    AppState.currentJobId = jobId;
    const job = MOCK_DB.jobs.find(j => j.id === jobId);
    $('#setup-job-title').textContent = `[${job.job || '-'}] ${job.title}`;

    // Reset Checks
    $('#resume-upload').value = '';
    $('#resume-status').textContent = '';
    $('#resume-status').className = '';

    // Reset Device Status
    $('#cam-status').className = 'status pending';
    $('#cam-status').textContent = '확인 필요';
    $('#mic-status').className = 'status pending';
    $('#mic-status').textContent = '확인 필요';
    $('#btn-start-interview').disabled = true;

    // Hide preview area initially
    const setupPreviewArea = document.getElementById('setup-preview-area');
    if (setupPreviewArea) setupPreviewArea.classList.add('hidden');

    navigateTo('interview-setup-page');
};

$('#btn-cancel-interview').addEventListener('click', () => {
    navigateTo('applicant-dashboard-page');
});

function initInterview() {
    console.log("Initializing Interview Module...");

    const btnTestDevices = $('#btn-test-devices');
    if (btnTestDevices) {
        console.log("Setting up Device Test Button Event...");

        // cloneNode 사용 대신 onclick 속성 직접 할당으로 변경하여 이벤트 바인딩 보장
        btnTestDevices.onclick = async () => {
            console.log("Device test initiated...");

            // 1. Camera & Mic Permission
            showToast('카메라/마이크 권한을 요청합니다...', 'info');
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });

                // Connect to Video Element (Main Interview Page)
                const video = document.getElementById('user-video');
                if (video) {
                    video.srcObject = stream;
                    document.getElementById('feed-label').textContent = '내 모습 (Camera On)';
                }

                // Connect to Setup Preview Video Element (New)
                const setupVideo = document.getElementById('setup-video-preview');
                const setupPreviewArea = document.getElementById('setup-preview-area');
                if (setupVideo && setupPreviewArea) {
                    setupPreviewArea.classList.remove('hidden');
                    setupVideo.srcObject = stream;
                    console.log("Preview video stream set.");
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
                showToast('카메라/마이크 접근 권한이 필요합니다. 브라우저 설정에서 허용해주세요.', 'error');
            }
        });
    } else {
        console.error("Test Device Button not found!");
    }
}

// Step 2: Main Interview Logic (Modified for Upload)
// Step 2: Main Interview Logic (Connected to Server)
$('#btn-start-interview').addEventListener('click', async () => {
    // Check if resume is uploaded
    const fileInput = $('#resume-upload');
    if (!fileInput.files || fileInput.files.length === 0) {
        showToast('이력서 파일을 업로드해주세요.', 'error');
        return;
    }

    // Upload Resume First
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('resume', file);
    formData.append('id_name', AppState.currentUser.id_name);

    // Find current job to get job title
    const job = MOCK_DB.jobs.find(j => j.id === AppState.currentJobId);
    formData.append('job_title', job ? job.job : 'Unknown');

    try {
        showToast('이력서 업로드 및 면접 준비 중...', 'info');
        const response = await fetch('/api/upload/resume', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        if (!result.success) {
            showToast(result.message || '이력서 업로드 실패', 'error');
            return;
        }

        // Call API to Start Interview
        const startResponse = await fetch('/api/interview/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id_name: AppState.currentUser.id_name,
                job_id: AppState.currentJobId
            })
        });
        const startResult = await startResponse.json();

        if (startResult.success) {
            // Init Interview State
            AppState.interview = {
                inProgress: true,
                interviewNumber: startResult.interview_number,
                currentQId: startResult.q_id,
                currentQuestion: startResult.question,
                questionCount: 1,
                timeLeft: 60,
                timer: null
            };

            showToast('면접을 시작합니다.', 'success');

            // Clear UI
            $('#chat-log').innerHTML = '';
            $('#user-answer').value = '';
            $('#coding-board').classList.add('hidden');

            navigateTo('interview-page');
            displayCurrentQuestion();

        } else {
            showToast(startResult.message || '면접 시작 실패', 'error');
        }

    } catch (error) {
        console.error('Interview Start Error:', error);
        showToast('서버 연결 실패', 'error');
        return;
    }
});

function displayCurrentQuestion() {
    if (!AppState.interview.inProgress) return;

    // Update UI
    $('#phase-label').textContent = `질문 ${AppState.interview.questionCount}`;
    const currentQ = AppState.interview.currentQuestion;

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
            $('#user-answer').focus();
        });
    }, 500);
}


function submitAnswer(forced) {
    if (AppState.interview.timer) clearInterval(AppState.interview.timer);
    stopListening(); // Stop STT on submit

    const answer = $('#user-answer').value.trim() || (forced ? '(시간 초과)' : '(답변 없음)');
    const timeTaken = 60 - AppState.interview.timeLeft;

    addChatLog('User', answer);
    $('#user-answer').value = '';

    // Send Answer to Server
    fetch('/api/interview/reply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            interview_number: AppState.interview.interviewNumber,
            q_id: AppState.interview.currentQId,
            answer: answer,
            time_taken: timeTaken
        })
    })
        .then(res => res.json())
        .then(result => {
            if (result.success) {
                if (result.finished) {
                    finishInterview();
                } else {
                    // Next Question
                    AppState.interview.currentQId = result.q_id;
                    AppState.interview.currentQuestion = result.question;
                    AppState.interview.questionCount++;
                    displayCurrentQuestion();
                }
            } else {
                showToast(result.message || '답변 제출 실패', 'error');
            }
        })
        .catch(err => {
            console.error('Reply Error:', err);
            showToast('서버 통신 오류', 'error');
        });
}

// function finishInterview() {
//     AppState.interview.inProgress = false;

//     // Fetch Real Result from Server
//     fetch(`/api/interview/result/${AppState.interview.interviewNumber}`)
//         .then(res => res.json())
//         .then(data => {
//             if (data.success) {
//                 const result = data.result;

//                 // Save to Mock DB (for local session consistency if needed)
//                 const appRecord = {
//                     userId: AppState.currentUser.id_name,
//                     jobId: AppState.currentJobId,
//                     date: new Date().toLocaleDateString(),
//                     scores: result.scores,
//                     interviewNumber: AppState.interview.interviewNumber
//                 };
//                 MOCK_DB.applications.push(appRecord);

//                 // Show Result Page
//                 navigateTo('result-page');

//                 setTimeout(() => {
//                     $('#score-tech').style.width = `${result.scores.tech}%`;
//                     $('#score-prob').style.width = `${result.scores.prob}%`;
//                     $('#score-comm').style.width = `${result.scores.comm}%`;
//                     $('#score-atti').style.width = `${result.scores.atti}%`;

//                     const avg = (result.scores.tech + result.scores.prob + result.scores.comm + result.scores.atti) / 4;
//                     $('#pass-fail-badge').textContent = avg >= 80 ? '합격 예측' : '불합격 예측';
//                     $('#pass-fail-badge').style.color = avg >= 80 ? 'green' : 'red';

//                     $('#result-desc').innerHTML = `
//                         수고하셨습니다. 면접 분석 결과입니다.<br>
//                         평균 점수: <strong>${avg}점</strong><br>
//                         <br>
//                         상세 질의응답 분석은 이메일로 발송됩니다.
//                     `;
//                 }, 500);

//             } else {
//                 showToast('결과 생성 중 오류가 발생했습니다.', 'error');
//             }
//         })
//         .catch(err => {
//             console.error('Result Fetch Error:', err);
//             showToast('결과 조회 실패', 'error');
//         });
// }

function finishInterview() {
    AppState.interview.inProgress = false;

    showToast("면접 결과를 분석 중입니다...", "info");

    // Fetch Real Result from Server
    fetch(`/api/interview/result/${AppState.interview.interviewNumber}`)
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const result = data.result;

                // Save to Mock DB (for local session consistency if needed)
                const appRecord = {
                    userId: AppState.currentUser.id_name,
                    jobId: AppState.currentJobId,
                    date: new Date().toLocaleDateString(),
                    scores: result.scores,
                    interviewNumber: AppState.interview.interviewNumber
                };
                MOCK_DB.applications.push(appRecord);

                // Show Result Page
                navigateTo('result-page');

                setTimeout(() => {
                    $('#score-tech').style.width = `${result.scores.tech}%`;
                    $('#score-prob').style.width = `${result.scores.prob}%`;
                    $('#score-comm').style.width = `${result.scores.comm}%`;
                    $('#score-atti').style.width = `${result.scores.atti}%`;

                    const avg = (result.scores.tech + result.scores.prob + result.scores.comm + result.scores.atti) / 4;
                    $('#pass-fail-badge').textContent = avg >= 80 ? '합격 예측' : '불합격 예측';
                    $('#pass-fail-badge').style.color = avg >= 80 ? 'green' : 'red';

                    $('#result-desc').innerHTML = `
                        수고하셨습니다. 면접 분석 결과입니다.<br>
                        평균 점수: <strong>${avg}점</strong><br>
                        <br>
                        상세 질의응답 분석은 이메일로 발송됩니다.
                    `;
                }, 500);

            } else {
                showToast('결과 생성 중 오류가 발생했습니다.', 'error');
            }
        })
        .catch(err => {
            console.error('Result Fetch Error:', err);
            showToast('결과 조회 실패', 'error');
        });
}

// --- Admin Section ---
function initAdmin() {
    $('#admin-menu-jobs').addEventListener('click', () => {
        $('#admin-view-jobs').classList.remove('hidden');
        $('#admin-view-applicants').classList.add('hidden');
        $('#admin-job-register-page').classList.add('hidden'); // Hide register page
        $('#admin-job-edit-page').classList.add('hidden'); // Hide edit page
        fetchJobs(); // Refresh list
    });
    $('#admin-menu-applicants').addEventListener('click', () => {
        $('#admin-view-jobs').classList.add('hidden');
        $('#admin-view-applicants').classList.remove('hidden');
        $('#admin-job-register-page').classList.add('hidden');
        $('#admin-job-edit-page').classList.add('hidden');
        renderAdminAppList();
    });

    // Admin My Info Link
    $('#admin-link-my-info').addEventListener('click', () => {
        if (AppState.currentUser) {
            $('#check-pw-input').value = '';
            navigateTo('password-check-page');
        }
    });


    // --- 4. Helper Functions (Timer, TTS, STT) ---

    // Timer Implementation
    function startTimer(duration) {
        if (AppState.interview.timer) clearInterval(AppState.interview.timer);

        AppState.interview.timeLeft = duration;
        updateTimerDisplay(duration);

        AppState.interview.timer = setInterval(() => {
            AppState.interview.timeLeft--;
            updateTimerDisplay(AppState.interview.timeLeft);

            if (AppState.interview.timeLeft <= 0) {
                clearInterval(AppState.interview.timer);
                submitAnswer(true); // Forced submission on timeout
            }
        }, 1000);
    }

    function updateTimerDisplay(seconds) {
        const min = Math.floor(seconds / 60);
        const sec = seconds % 60;
        const timeString = `${min.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;

        const timerDisplay = document.getElementById('timer-display');
        if (timerDisplay) timerDisplay.textContent = timeString;

        const progressBar = document.getElementById('progress-bar');
        if (progressBar) {
            const percentage = (seconds / 60) * 100; // Assuming 60s max
            progressBar.style.width = `${percentage}%`;
        }
    }

    // TTS (Text-to-Speech) Implementation
    function speakText(text, callback) {
        if (!window.speechSynthesis) {
            console.error("TTS not supported");
            if (callback) callback();
            return;
        }

        // Cancel any ongoing speech
        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'ko-KR'; // Korean
        utterance.rate = 1.0;

        utterance.onend = () => {
            if (callback) callback();
        };

        utterance.onerror = (e) => {
            console.error("TTS Error:", e);
            if (callback) callback();
        };

        window.speechSynthesis.speak(utterance);
    }

    // STT (Speech-to-Text) Implementation
    let recognition = null;

    function initSpeechRecognition() {
        if ('webkitSpeechRecognition' in window) {
            recognition = new webkitSpeechRecognition();
        } else if ('SpeechRecognition' in window) {
            recognition = new SpeechRecognition();
        } else {
            console.log("Speech Recognition API not supported in this browser.");
            return null;
        }

        recognition.continuous = true; // Keep listening
        recognition.interimResults = true; // Show interim results
        recognition.lang = 'ko-KR';

        recognition.onresult = function (event) {
            let finalTranscript = '';
            let interimTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }

            const answerInput = document.getElementById('user-answer');
            if (answerInput) {
                // Append only final results to existing text to avoid overwriting manual edits? 
                // Actually, usually we just update the value. 
                // Simple approach: append final to current value if it's new?
                // Better approach for demo: Just update with what we hear + existing content logic is complex.
                // We will just set value to finalTranscript if we clear it each time.
                // OR: We can just let the user see what is being typed.

                // Simple Logic: just display what is recognized in this session.
                // If user modifies it manually, it might get overwritten by subsequent recognition events if we strictly use `transcript`.
                // But for this demo, let's just append new final parts.

                if (finalTranscript) {
                    // Simplistic: Just add to the textarea. 
                    // Note: This logic might duplicate if `continuous` keeps sending old finals.
                    // Actually `event.resultIndex` helps processing only new results.

                    // We need to maintain state of what was already added?
                    // Let's just append the *new* final transcript part.

                    const currentVal = answerInput.value;
                    answerInput.value = currentVal + (currentVal ? ' ' : '') + finalTranscript;
                }

                // Show interim in placeholder or separate visual? 
                // For simplicity, maybe just ignore interim or show in console.
                // Or update value with interim temporarily? (Complex to undo)
            }
        };

        recognition.onerror = function (event) {
            console.error("Speech Recognition Error:", event.error);
        };

        return recognition;
    }

    function startListening() {
        if (!recognition) {
            recognition = initSpeechRecognition();
        }

        if (recognition) {
            try {
                recognition.start();
                console.log("Voice recognition started.");
            } catch (e) {
                console.warn("Recognition already started or error:", e);
            }
        }
    }

    function stopListening() {
        if (recognition) {
            try {
                recognition.stop();
                console.log("Voice recognition stopped.");
            } catch (e) {
                console.warn("Error stopping recognition:", e);
            }
        }
    }

    // Helper Toast
    function showToast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;

        container.appendChild(toast);

        // Animate In
        setTimeout(() => {
            toast.classList.add('show');
        }, 10);

        // Remove after 3s
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                container.removeChild(toast);
            }, 300);
        }, 3000);
    }
    // Show Job Register Page
    $('#btn-add-job').addEventListener('click', () => {
        $('#admin-view-jobs').classList.add('hidden');
        $('#admin-job-register-page').classList.remove('hidden');
        $('#admin-job-edit-page').classList.add('hidden');
        // Reset form
        $('#job-title').value = '';
        $('#job-job').value = '';
        $('#job-content').value = '';
        $('#job-deadline').value = '';
    });

    // Cancel Job Register
    $('#btn-cancel-job-register').addEventListener('click', () => {
        $('#admin-job-register-page').classList.add('hidden');
        $('#admin-view-jobs').classList.remove('hidden');
    });

    // Submit Job Register
    $('#admin-job-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const title = $('#job-title').value;
        const content = $('#job-content').value;
        const deadline = $('#job-deadline').value;

        try {
            const response = await fetch('/api/jobs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    job: $('#job-job').value,
                    content,
                    deadline,
                    id_name: AppState.currentUser.id_name // Add writer_id (now id_name)
                })
            });
            const result = await response.json();

            if (result.success) {
                showToast('공고가 등록되었습니다.', 'success');
                // Return to list
                $('#admin-job-register-page').classList.add('hidden');
                $('#admin-view-jobs').classList.remove('hidden');
                fetchJobs();
            } else {
                showToast(result.message || '공고 등록 실패', 'error');
            }
        } catch (error) {
            console.error('Create Job Error:', error);
            showToast('서버 오류가 발생했습니다.', 'error');
        }
    });

    // Cancel Job Edit
    $('#btn-cancel-job-edit').addEventListener('click', () => {
        $('#admin-job-edit-page').classList.add('hidden');
        $('#admin-view-jobs').classList.remove('hidden');
    });

    // Submit Job Edit
    $('#admin-job-edit-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = $('#edit-job-id').value;
        const title = $('#edit-job-title').value;
        const jobVal = $('#edit-job-job').value;
        const content = $('#edit-job-content').value;
        const deadline = $('#edit-job-deadline').value;

        try {
            const response = await fetch(`/api/jobs/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, job: jobVal, content, deadline })
            });
            const result = await response.json();

            if (result.success) {
                showToast('공고가 수정되었습니다.', 'success');
                $('#admin-job-edit-page').classList.add('hidden');
                $('#admin-view-jobs').classList.remove('hidden');
                fetchJobs();
            } else {
                showToast(result.message || '공고 수정 실패', 'error');
            }
        } catch (error) {
            console.error('Update Job Error:', error);
            showToast('서버 오류가 발생했습니다.', 'error');
        }
    });

    // initInterview(); // Called in DOMContentLoaded, defined above.
}

// function initInterview() { } // Removed duplicate

function renderAdminJobList() {
    const tbody = $('#admin-job-table tbody');
    tbody.innerHTML = '';
    MOCK_DB.jobs.forEach(job => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${job.id}</td>
            <td>${job.job || '-'}</td>
            <td>${job.title}</td>
            <td>${job.id_name || 'Unknown'}</td>
            <td>${job.created_at}</td>
            <td>${job.deadline}</td>
            <td>
                <button class="btn-small" onclick="openEditJob(${job.id})">수정</button>
                <button class="btn-small btn-secondary" onclick="deleteJob(${job.id})">삭제</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function openEditJob(id) {
    const job = MOCK_DB.jobs.find(j => j.id === id);
    if (job) {
        $('#edit-job-id').value = job.id;
        $('#edit-job-title').value = job.title;
        $('#edit-job-job').value = job.job || '';
        $('#edit-job-content').value = job.content;
        $('#edit-job-deadline').value = job.deadline;

        $('#admin-view-jobs').classList.add('hidden');
        $('#admin-job-edit-page').classList.remove('hidden');
    }
}

function openEditJobPage(jobId) {
    const job = MOCK_DB.jobs.find(j => j.id == jobId); // Loose equality for string/int match
    if (!job) return;

    $('#edit-job-id').value = job.id;
    $('#edit-job-title').value = job.title;
    $('#edit-job-content').value = job.content || '';
    $('#edit-job-deadline').value = job.deadline;

    $('#admin-view-jobs').classList.add('hidden');
    $('#admin-job-edit-page').classList.remove('hidden');
}

async function deleteJob(jobId) {
    if (!confirm('정말 이 공고를 삭제하시겠습니까?')) return;

    try {
        const response = await fetch(`/api/jobs/${jobId}`, {
            method: 'DELETE'
        });
        const result = await response.json();

        if (result.success) {
            showToast('공고가 삭제되었습니다.', 'success');
            fetchJobs();
        } else {
            showToast(result.message || '공고 삭제 실패', 'error');
        }
    } catch (error) {
        console.error('Delete Job Error:', error);
        showToast('서버 오류가 발생했습니다.', 'error');
    }
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

// --- Input Masking Utilities ---
function initInputMasking() {
    console.log("Input masking initialized.");
}

