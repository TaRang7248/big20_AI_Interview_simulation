/**
 * AI 면접 프로그램 - 메인 애플리케이션 로직
 * 스택: 바닐라 JS (ES6+)
 * 기능: SPA 라우팅, API 연동, 오디오 녹음, 면접 로직
 */

// --- 0. 목 데이터 (데이터 모델) ---
const MOCK_DB = {
    jobs: [],
};

// --- 1. 전역 상태 ---
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
        recognition: null, // Web Speech API
        currentQuestionIndex: 0, // Added for progress tracking
        totalQuestions: 12,
        videoInterval: null, // Added for video analysis
        // 선택된 기기 ID 저장공간 추가
        selectedDevices: {
            videoInputId: null,
            audioInputId: null,
            audioOutputId: null
        }
    }
};

// --- 2. 헬퍼 함수 ---
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

function clearSignupForm() {
    const form = $('#signup-form');
    if (form) {
        form.reset();
        const msgBox = $('#id-check-msg');
        if (msgBox) {
            msgBox.textContent = '';
        }
    }
}

// --- 3. 초기화 ---
document.addEventListener('DOMContentLoaded', () => {
    console.log("[시스템] 애플리케이션 초기화 시작.");

    const initFunctions = [
        { name: 'Router', func: initRouter },
        { name: 'Auth', func: initAuth },
        { name: 'Dashboard', func: initDashboard },
        { name: 'Admin', func: initAdmin },
        { name: 'Interview', func: initInterview },
        { name: 'FindAccount', func: initFindAccount }
    ];

    initFunctions.forEach(item => {
        try {
            item.func();
            console.log(`[System] ${item.name} initialized successfully.`);
        } catch (error) {
            console.error(`[Error] Failed to initialize ${item.name}:`, error);
        }
    });

    console.log("[시스템] 애플리케이션 초기화 완료.");
});

// --- ID/PW 찾기 로직 ---
function initFindAccount() {
    console.log("[인증] ID/PW 찾기 이벤트 초기화.");

    // 탭 전환: ID 찾기
    $('#btn-tab-find-id').addEventListener('click', () => {
        console.log("[Nav] Switching to Find ID tab.");
        $('#btn-tab-find-id').classList.add('active');
        $('#btn-tab-find-pw').classList.remove('active');
        $('#form-find-id').classList.remove('hidden');
        $('#form-find-pw').classList.add('hidden');
        resetFindForms();
    });

    // 탭 전환: PW 찾기
    $('#btn-tab-find-pw').addEventListener('click', () => {
        $('#btn-tab-find-pw').classList.add('active');
        $('#btn-tab-find-id').classList.remove('active');
        $('#form-find-pw').classList.remove('hidden');
        $('#form-find-id').classList.add('hidden');
        resetFindForms();
    });

    // ID 찾기 양식 제출
    $('#find-id-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = $('#find-id-name').value;
        const email = $('#find-id-email').value;

        try {
            const response = await fetch('/api/find-id', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email })
            });
            const result = await response.json();
            const resultBox = $('#find-id-result');
            resultBox.style.display = 'block';

            if (result.success) {
                // 여러 개의 아이디가 있을 수 있으므로 join 하여 표시
                const idsText = result.id_names.join(', ');
                resultBox.innerHTML = `찾으시는 아이디는 <strong>${idsText}</strong> 입니다.`;
                resultBox.style.color = 'blue';
                // 아이디 출력 후 5초 뒤 로그인 화면으로 이동 (사용자가 아이디를 기록할 시간을 충분히 줌)
                setTimeout(() => {
                    alert(`아이디 확인 완료. 로그인 화면으로 돌아갑니다.`);
                    navigateTo('login-page');
                }, 5000);
            } else {
                resultBox.textContent = result.message;
                resultBox.style.color = 'red';
                // 실패 시 2초 뒤 로그인 화면으로 이동
                setTimeout(() => {
                    navigateTo('login-page');
                }, 2000);
            }
        } catch (error) {
            console.error(error);
            showToast('서버 오류 발생', 'error');
        }
    });

    // PW 찾기 Step 1 (아이디 입력) 제출
    $('#find-pw-form-step1').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id_name = $('#find-pw-id').value;

        try {
            const response = await fetch('/api/find-pw-step1', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_name })
            });
            const result = await response.json();
            if (result.success) {
                $('#find-pw-step1-ui').classList.add('hidden');
                $('#find-pw-step2-ui').classList.remove('hidden');
                $('#find-pw-msg').textContent = result.message;
                // 테스트를 위한 인증번호 알림 (실제 운영 시 제거)
                if (result.debug_code) {
                    console.log(`[DEBUG] Verification Code: ${result.debug_code}`);
                    showToast(`[테스트용] 인증번호: ${result.debug_code}`, 'info');
                }
            } else {
                showToast(result.message, 'error');
            }
        } catch (error) {
            console.error(error);
            showToast('서버 오류 발생', 'error');
        }
    });

    // PW 찾기 Step 2 (인증번호 입력) 제출
    $('#find-pw-form-step2').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id_name = $('#find-pw-id').value;
        const verification_code = $('#find-pw-code').value;

        try {
            const response = await fetch('/api/find-pw-step2', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_name, verification_code })
            });
            const result = await response.json();
            const resultBox = $('#find-pw-result');
            resultBox.style.display = 'block';

            if (result.success) {
                resultBox.innerHTML = `귀하의 비밀번호는 <strong>${result.pw}</strong> 입니다.`;
                resultBox.style.color = 'blue';
            } else {
                resultBox.textContent = result.message;
                resultBox.style.color = 'red';
            }
        } catch (error) {
            console.error(error);
            showToast('서버 오류 발생', 'error');
        }
    });

    $('#btn-find-back-login').addEventListener('click', () => navigateTo('login-page'));
    $('#link-find-account').addEventListener('click', (e) => {
        e.preventDefault();
        navigateTo('find-account-page');
    });
}

function resetFindForms() {
    $('#find-id-form').reset();
    $('#find-pw-form-step1').reset();
    $('#find-pw-form-step2').reset();
    $('#find-id-result').style.display = 'none';
    $('#find-pw-result').style.display = 'none';
    $('#find-pw-step1-ui').classList.remove('hidden');
    $('#find-pw-step2-ui').classList.add('hidden');
}

// --- 4. 라우터 ---
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
            if (pageId === 'my-records-page') fetchMyRecords();

            // 설정 페이지 진입 시 기기 테스트 자동 시작
            if (pageId === 'interview-setup-page') {
                testDevices();
            }

            // 회원가입 페이지 진입 시 폼 초기화
            if (pageId === 'signup-page') {
                clearSignupForm();
            }

            // ID/PW 찾기 페이지 진입 시 이전 기록 초기화
            if (pageId === 'find-account-page') {
                resetFindForms();
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

// --- 5. 인증 ---
function initAuth() {
    // 아이디 중복 확인
    $('#btn-check-id').addEventListener('click', async () => {
        const idInput = $('#reg-id');
        const msgBox = $('#id-check-msg');
        const idValue = idInput.value.trim();

        if (!idValue) {
            msgBox.textContent = '아이디를 입력해주세요.';
            msgBox.style.color = 'red';
            return;
        }

        try {
            const response = await fetch('/api/check-id', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id_name: idValue })
            });
            const result = await response.json();

            if (result.available) {
                msgBox.textContent = result.message; // "사용 가능한 아이디입니다."
                msgBox.style.color = 'green';
                // Optional: Lock ID input or set a flag (not strictly required by prompt but good practice)
            } else {
                msgBox.textContent = result.message; // "이미 존재하는 아이디입니다."
                msgBox.style.color = 'red';
            }
        } catch (error) {
            console.error('ID Check Error:', error);
            msgBox.textContent = '서버 오류가 발생했습니다.';
            msgBox.style.color = 'red';
        }
    });

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

// --- 6. 대시보드 및 공고 ---
function initDashboard() {
    $('#link-my-info').addEventListener('click', () => {
        // [Modified] Show Password Check Page first
        navigateTo('password-check-page');
        $('#check-pw-input').value = '';
        $('#check-pw-input').focus();
    });

    $('#link-my-info-side').addEventListener('click', () => {
        navigateTo('password-check-page');
        $('#check-pw-input').value = '';
        $('#check-pw-input').focus();
    });

    $('#link-my-records').addEventListener('click', (e) => {
        e.preventDefault();
        navigateTo('my-records-page');
    });
}

async function fetchJobs() {
    try {
        let url = '/api/jobs';
        if (AppState.currentUser && AppState.currentUser.id_name) {
            url += `?user_id=${encodeURIComponent(AppState.currentUser.id_name)}`;
        }
        const response = await fetch(url);
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
            $('#detail-job-qualifications').textContent = job.qualifications || '-';
            $('#detail-job-preferred').textContent = job.preferred_qualifications || '-';
            $('#detail-job-benefits').textContent = job.benefits || '-';
            $('#detail-job-hiring-process').textContent = job.hiring_process || '-';
            $('#detail-job-number-of-hires').textContent = job.number_of_hires || '-';
            navigateTo('job-detail-page');
        }
    } catch (e) { console.error(e); }
};

$('#btn-back-to-list').addEventListener('click', () => navigateTo('applicant-dashboard-page'));
$('#btn-apply-job').addEventListener('click', () => {
    if (AppState.currentJobId) startInterviewSetup(AppState.currentJobId);
});

async function fetchMyRecords() {
    if (!AppState.currentUser) return;

    try {
        const response = await fetch(`/api/interview-results/${AppState.currentUser.id_name}`);
        const result = await response.json();
        if (result.success) {
            renderMyRecords(result.results);
        }
    } catch (error) {
        console.error('Fetch My Records Error:', error);
        showToast('면접 기록을 가져오는데 실패했습니다.', 'error');
    }
}

function renderMyRecords(records) {
    const list = $('#my-records-list');
    list.innerHTML = '';

    if (records.length === 0) {
        list.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 20px;">면접 기록이 없습니다.</td></tr>';
        return;
    }

    records.forEach(record => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${record.announcement_title}</td>
            <td>${record.announcement_job}</td>
            <td>${record.interview_time}</td>
            <td style="color: ${record.pass_fail === '합격' ? 'green' : (record.pass_fail === '불합격' ? 'red' : 'orange')}; font-weight: bold;">
                ${record.pass_fail}
            </td>
        `;
        list.appendChild(tr);
    });
}

// --- 6.1 내 정보 로직 ---
async function loadMyInfo() {
    if (!AppState.currentUser) return;

    try {
        const response = await fetch(`/api/user/${AppState.currentUser.id_name}`);
        const result = await response.json();

        if (result.success) {
            const user = result.user;
            // Fill form
            $('#edit-id').value = user.id_name;
            $('#edit-name').value = user.name;
            $('#edit-dob').value = user.dob || '';
            $('#edit-gender').value = user.gender === 'male' ? '남성' : (user.gender === 'female' ? '여성' : user.gender);
            $('#edit-email').value = user.email || '';
            $('#edit-addr').value = user.address || '';

            if (user.phone) {
                const parts = user.phone.split('-');
                if (parts.length === 3) {
                    $('#edit-phone-1').value = parts[0];
                    $('#edit-phone-2').value = parts[1];
                    $('#edit-phone-3').value = parts[2];
                } else {
                    $('#edit-phone-1').value = '';
                    $('#edit-phone-2').value = '';
                    $('#edit-phone-3').value = '';
                }
            }
        } else {
            showToast('회원 정보를 불러오지 못했습니다.', 'error');
        }
    } catch (error) {
        console.error('Load MyInfo Error:', error);
        showToast('서버 통신 오류', 'error');
    }
}

$('#myinfo-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!confirm('정말 수정하시겠습니까?')) return;

    // We need current password to update info? The API requires 'pw' field in UserUpdate model.
    // However, the UI does not have a password field in 'myinfo-form'.
    // We should probably prompt for password or fetch it if possible (security risk), 
    // OR we can ask user to input password to confirm update.
    // For now, let's assume we need to prompt for password or add a password field to the form.
    // Checking server.py: UserUpdate requires 'pw'.
    // Let's ask via prompt or add a hidden field if we rely on session logic (which we don't fully have safely).
    // Better UX: Add a password confirm modal or field.
    // SHORTCUT for this task: prompt user for password.

    // [Modified] Password prompt removed as per request
    // const pw = prompt("정보 수정을 위해 현재 비밀번호를 입력해주세요:");
    // if (!pw) return;

    const updatedData = {
        // pw: pw, // Removed
        email: $('#edit-email').value,
        address: $('#edit-addr').value,
        phone: `${$('#edit-phone-1').value}-${$('#edit-phone-2').value}-${$('#edit-phone-3').value}`
    };

    try {
        const response = await fetch(`/api/user/${AppState.currentUser.id_name}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatedData)
        });
        const result = await response.json();
        if (result.success) {
            showToast('정보가 수정되었습니다.', 'success');
            // Update local state if needed
            AppState.currentUser.email = updatedData.email;
            AppState.currentUser.address = updatedData.address;
            AppState.currentUser.phone = updatedData.phone;

            // Redirect to Dashboard
            setTimeout(() => {
                if (AppState.currentUser.type === 'admin') navigateTo('admin-dashboard-page');
                else navigateTo('applicant-dashboard-page');
            }, 1000); // Wait 1 sec for toast
        } else {
            showToast(result.message || '수정 실패', 'error');
        }
    } catch (error) {
        console.error(error);
        showToast('서버 오류', 'error');
    }
});

// Password Change Button
$('#btn-change-pw').addEventListener('click', () => {
    navigateTo('password-change-page');
});

// 회원 탈퇴 버튼 이벤트 핸들러 추가
$('#btn-delete-user').addEventListener('click', async () => {
    // 1. 비밀번호 입력 확인
    const password = prompt("회원 탈퇴를 위해 비밀번호를 입력해주세요:");
    if (!password) return;

    try {
        // 비밀번호 검증 API 호출
        const verifyResp = await fetch('/api/verify-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id_name: AppState.currentUser.id_name,
                pw: password
            })
        });
        const verifyResult = await verifyResp.json();

        if (verifyResult.success) {
            // 2. 최종 탈퇴 확인
            if (confirm("정말 회원을 탈퇴하시겠습니까? 탈퇴 시 모든 정보가 삭제되며 이 작업은 취소할 수 없습니다.")) {
                // 회원 탈퇴 API (DELETE) 호출
                const deleteResp = await fetch(`/api/user/${AppState.currentUser.id_name}`, {
                    method: 'DELETE'
                });
                const deleteResult = await deleteResp.json();

                if (deleteResult.success) {
                    alert("회원 탈퇴가 완료되었습니다. 그동안 이용해주셔서 감사합니다.");
                    // 로그아웃 처리 및 초기 화면 이동
                    AppState.currentUser = null;
                    $('#navbar').classList.add('hidden');
                    navigateTo('login-page');
                } else {
                    alert(deleteResult.message || "탈퇴 처리 중 오류가 발생했습니다.");
                }
            }
        } else {
            alert("비밀번호가 일치하지 않습니다.");
        }
    } catch (error) {
        console.error("회원 탈퇴 오류:", error);
        alert("서버 통신 중 오류가 발생했습니다.");
    }
});

$('#btn-cancel-myinfo').addEventListener('click', () => {
    if (AppState.currentUser.type === 'admin') navigateTo('admin-dashboard-page');
    else navigateTo('applicant-dashboard-page');
});

// Password Change Logic
$('#password-change-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const newPw = $('#new-pw').value;
    const confirmPw = $('#confirm-new-pw').value;

    if (newPw !== confirmPw) {
        alert('새 비밀번호가 일치하지 않습니다.');
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
            alert('비밀번호가 변경되었습니다. 다시 로그인해주세요.');
            AppState.currentUser = null;
            $('#navbar').classList.add('hidden');
            navigateTo('login-page');
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error(error);
        alert('오류 발생');
    }
});

$('#btn-cancel-pw-change').addEventListener('click', () => {
    navigateTo('myinfo-page');
});

// --- 6.2 비밀번호 확인 로직 (신규) ---
$('#password-check-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const pw = $('#check-pw-input').value;

    try {
        const response = await fetch('/api/verify-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id_name: AppState.currentUser.id_name,
                pw: pw
            })
        });
        const result = await response.json();

        if (result.success) {
            // Password Correct -> Go to My Info
            loadMyInfo(); // Load data
            navigateTo('myinfo-page'); // Show page
        } else {
            alert(result.message || '비밀번호가 일치하지 않습니다.');
            $('#check-pw-input').value = '';
            $('#check-pw-input').focus();
        }
    } catch (error) {
        console.error(error);
        alert('서버 오류 발생');
    }
});

$('#btn-cancel-pw-check').addEventListener('click', () => {
    if (AppState.currentUser.type === 'admin') navigateTo('admin-dashboard-page');
    else navigateTo('applicant-dashboard-page');
});

// --- 7. 면접 설정 ---
window.startInterviewSetup = (jobId) => {
    AppState.currentJobId = jobId;
    const job = MOCK_DB.jobs.find(j => j.id === jobId);
    $('#setup-job-title').textContent = `[${job.job || '-'}] ${job.title}`;
    $('#resume-upload').value = '';
    $('#resume-status').textContent = '';

    // 미리보기 영역 및 iframe 초기화
    const previewContainer = $('#resume-preview-container');
    const previewIframe = $('#resume-preview');
    if (previewContainer) previewContainer.style.display = 'none';
    if (previewIframe) previewIframe.src = '';

    // $('#btn-start-interview').disabled = true; // Don't disable initially
    navigateTo('interview-setup-page');
};


// 자동 환경 테스트: 카메라, 마이크, 오디오(스피커) 연결 확인
async function testDevices() {
    // 상태 초기화
    $('#cam-status').className = 'status pending';
    $('#cam-status').textContent = '연결 중...';
    $('#mic-status').className = 'status pending';
    $('#mic-status').textContent = '연결 중...';
    $('#audio-status').className = 'status pending';
    $('#audio-status').textContent = '연결 중...';

    // 기기명 초기화
    $('#cam-device').textContent = '';
    $('#mic-device').textContent = '';
    $('#audio-device').textContent = '';

    try {
        // 카메라 및 마이크 권한 요청
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });

        // 연결된 기기 목록 가져오기
        const devices = await navigator.mediaDevices.enumerateDevices();

        let camName = '카메라';
        let micName = '마이크';
        let speakerName = '기본 스피커';

        // 실제 기기명 추출 (label이 활성화된 기기 찾기)
        const videoInput = devices.find(d => d.kind === 'videoinput' && d.deviceId);
        const audioInput = devices.find(d => d.kind === 'audioinput' && d.deviceId);
        const audioOutput = devices.find(d => d.kind === 'audiooutput' && d.deviceId);

        if (videoInput && videoInput.label) camName = videoInput.label;
        if (audioInput && audioInput.label) micName = audioInput.label;
        if (audioOutput && audioOutput.label) speakerName = audioOutput.label;

        // 선택된 기기 ID를 AppState에 저장 (면접 시작 시 사용)
        AppState.interview.selectedDevices.videoInputId = videoInput ? videoInput.deviceId : null;
        AppState.interview.selectedDevices.audioInputId = audioInput ? audioInput.deviceId : null;
        AppState.interview.selectedDevices.audioOutputId = audioOutput ? audioOutput.deviceId : null;

        console.log("[System] 기기 정보 저장 완료:", AppState.interview.selectedDevices);

        // UI 업데이트: 카메라
        $('#cam-status').className = 'status ok';
        $('#cam-status').textContent = '정상';
        $('#cam-device').textContent = `(${camName})`;

        // UI 업데이트: 마이크
        $('#mic-status').className = 'status ok';
        $('#mic-status').textContent = '정상';
        $('#mic-device').textContent = `(${micName})`;

        // UI 업데이트: 오디오
        $('#audio-status').className = 'status ok';
        $('#audio-status').textContent = '정상';
        $('#audio-device').textContent = `(${speakerName})`;

        // 모든 기기 확인 완료 시 버튼 활성화
        $('#btn-start-interview').disabled = false;

        // 테스트 스트림 종료 (리소르 해제)
        stream.getTracks().forEach(track => track.stop());
        AppState.interview.devicesReady = true;

    } catch (err) {
        console.error("[오류] 기기 테스트 실패:", err);
        $('#cam-status').className = 'status error';
        $('#cam-status').textContent = '실패';
        $('#mic-status').className = 'status error';
        $('#mic-status').textContent = '실패';
        $('#audio-status').className = 'status error';
        $('#audio-status').textContent = '실패';
        AppState.interview.devicesReady = false;
    }
}

$('#btn-cancel-interview').addEventListener('click', () => navigateTo('applicant-dashboard-page'));

// --- 8. 면접 로직 ---
function initInterview() {
    $('#btn-start-interview').addEventListener('click', handleStartInterview);
    $('#btn-submit-answer').addEventListener('click', handleSubmitAnswer);

    // 이력서 파일 업로드 시 썸네일(미리보기) 표시 기능 추가
    $('#resume-upload').addEventListener('change', (e) => {
        const file = e.target.files[0];
        const previewContainer = $('#resume-preview-container');
        const previewIframe = $('#resume-preview');

        if (file && file.type === 'application/pdf') {
            const fileURL = URL.createObjectURL(file);
            previewIframe.src = fileURL + '#toolbar=0&navpanes=0&scrollbar=0'; // 툴바 등 숨김
            previewContainer.style.display = 'block'; // 썸네일 영역 보이기
        } else {
            previewContainer.style.display = 'none';
            previewIframe.src = '';
        }
    });

    // 썸네일 영역 클릭 시 원본 크기 확대 모달 띄우기
    $('#resume-preview-container').addEventListener('click', () => {
        const previewIframe = $('#resume-preview');
        if (previewIframe.src) {
            // 원본 크기로 띄울 때는 툴바 파라미터 제외 (원래 URL로)
            const fileURL = previewIframe.src.split('#')[0];
            $('#zoomed-pdf').src = fileURL;
            $('#pdf-zoom-modal').classList.remove('hidden');
        }
    });

    // 확대 모달 닫기 이벤트
    $('#close-pdf-zoom').addEventListener('click', () => {
        $('#pdf-zoom-modal').classList.add('hidden');
        $('#zoomed-pdf').src = ''; // 메모리 최적화를 위해 src 초기화
    });
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
    // $('#ai-message').textContent = "이력서를 분석하고 면접을 준비 중입니다...";
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
                job_title: job.job,
                announcement_id: job.id
            })
        });
        const startResult = await startResp.json();
        if (!startResult.success) throw new Error(startResult.message);

        // Success
        AppState.interview.inProgress = true;
        AppState.interview.interviewNumber = startResult.interview_number;
        AppState.interview.currentQuestion = startResult.question;
        AppState.interview.currentAudioUrl = startResult.audio_url; // 미디어 URL 저장
        AppState.interview.currentAudioType = startResult.audio_type || 'audio'; // 미디어 타입 저장 (video/audio)
        AppState.interview.currentQuestionIndex = 1;

        // Start Interaction
        updateProgressUI();
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
    // $('#ai-message').textContent = question;
    $('#user-answer').value = '';
    $('#user-answer').placeholder = "답변을 말씀해주세요 (녹음 중...)";

    // 1. TTS using Server Audio
    $('#btn-submit-answer').disabled = true; // AI가 말하는 동안 버튼 비활성화

    // Check if we have audio_url in AppState (need to update state logic to store it)
    // Actually startQuestionSequence is called with just 'question'. 
    // We should pass audio_url too or store it in state.
    // Let's modify startQuestionSequence signature or use AppState.

    const audioUrl = AppState.interview.currentAudioUrl;
    console.log(`[StartQuestion] Question: "${question}", AudioURL: ${audioUrl}`);

    if (audioUrl) {
        console.log(`[StartQuestion] Attempting to play audio from: ${audioUrl}`);
        playAudio(audioUrl, () => {
            console.log("[StartQuestion] Audio playback finished.");

            // 2. Start Timer & Recording immediately after TTS
            startTimer(120);
            startRecording();

            // 3. Button Logic: Keep disabled for 10 seconds
            const btnSubmit = $('#btn-submit-answer');
            btnSubmit.disabled = true;
            const originalText = "답변 제출 (녹음 종료)";
            btnSubmit.textContent = "답변 제출 (10초 후 활성화)";

            setTimeout(() => {
                // Ensure we are still in the same interview state/question
                // (Simple check: if we are still in progress and button exists)
                if (AppState.interview.inProgress && btnSubmit) {
                    btnSubmit.disabled = false;
                    btnSubmit.textContent = originalText;
                }
            }, 10000); // 10 seconds delay
        });
    } else {
        console.warn("[StartQuestion] No Audio URL provided. Skipping playback.");
        // Fallback: Start immediately
        startTimer(120);
        startRecording();

        // Apply same 10s delay logic for consistency
        const btnSubmit = $('#btn-submit-answer');
        btnSubmit.disabled = true;
        const originalText = "답변 제출 (녹음 종료)";
        btnSubmit.textContent = "답변 제출 (10초 후 활성화)";

        setTimeout(() => {
            if (AppState.interview.inProgress && btnSubmit) {
                btnSubmit.disabled = false;
                btnSubmit.textContent = originalText;
            }
        }, 10000);
    }
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
        // 환경 테스트에서 선택된 기기를 명시적으로 사용하도록 제약 조건 설정
        const constraints = {
            audio: AppState.interview.selectedDevices.audioInputId ?
                { deviceId: { exact: AppState.interview.selectedDevices.audioInputId } } : true,
            video: AppState.interview.selectedDevices.videoInputId ?
                { deviceId: { exact: AppState.interview.selectedDevices.videoInputId } } : true
        };

        console.log("[Recording] 기기 제약 조건 적용:", constraints);
        const stream = await navigator.mediaDevices.getUserMedia(constraints);

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

        // Start Video Analysis Interval (every 1 second)
        if (AppState.interview.videoInterval) clearInterval(AppState.interview.videoInterval);
        AppState.interview.videoInterval = setInterval(captureAndAnalyzeFrame, 1000);

        // --- Real-time STT (Web Speech API) ---
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            AppState.interview.recognition = new SpeechRecognition();
            AppState.interview.recognition.lang = 'ko-KR';
            AppState.interview.recognition.continuous = true;
            AppState.interview.recognition.interimResults = true;

            AppState.interview.recognition.onresult = (event) => {
                let interimTranscript = '';
                let finalTranscript = '';

                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript;
                    } else {
                        interimTranscript += event.results[i][0].transcript;
                    }
                }

                // Update Textarea (Visual only)
                const textArea = $('#user-answer');
                // Append if needed, or just show current session text
                // Since this is a new answer, we can just overwrite or append to what we have for this turn
                // But simplified: just show what is being recognized now
                textArea.value = finalTranscript + interimTranscript;
                textArea.scrollTop = textArea.scrollHeight;
            };

            AppState.interview.recognition.onerror = (event) => {
                console.warn("Speech Recognition Error:", event.error);
            };

            // Restart if it stops but we are still recording (e.g. silence)
            AppState.interview.recognition.onend = () => {
                if (AppState.interview.inProgress && AppState.interview.mediaRecorder && AppState.interview.mediaRecorder.state === 'recording') {
                    try { AppState.interview.recognition.start(); } catch (e) { }
                }
            };

            AppState.interview.recognition.start();
        }

    } catch (err) {
        console.error("Recording Error:", err);
        showToast("마이크 접근 실패", 'error');
    }
}

// --- Video Analysis Helper ---
async function captureAndAnalyzeFrame() {
    const video = $('#user-video');
    const canvas = $('#video-capture-canvas');
    if (!video || !canvas) return;

    // Check if video is playing
    if (video.paused || video.ended) return;

    const ctx = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(blob => {
        if (!blob) return;

        const formData = new FormData();
        formData.append('interview_number', AppState.interview.interviewNumber);
        formData.append('frame', blob, 'frame.jpg');

        fetch('/api/video/analyze', {
            method: 'POST',
            body: formData
        }).catch(err => console.error("Video Analysis Error:", err));
    }, 'image/jpeg', 0.8);
}

function stopRecording() {
    // Stop Speech Recognition
    if (AppState.interview.recognition) {
        AppState.interview.recognition.onend = null; // Prevent restart
        AppState.interview.recognition.stop();
        AppState.interview.recognition = null;
    }

    if (AppState.interview.videoInterval) {
        clearInterval(AppState.interview.videoInterval);
        AppState.interview.videoInterval = null;
    }

    return new Promise(resolve => {
        if (!AppState.interview.mediaRecorder || AppState.interview.mediaRecorder.state === 'inactive') {
            resolve();
            return;
        }

        AppState.interview.mediaRecorder.onstop = () => {
            resolve();
        };

        AppState.interview.mediaRecorder.stop();
        $('#feed-label').textContent = "녹음 종료 (Processing)";
    });
}

async function handleSubmitAnswer(forced = false) {
    if (!AppState.interview.inProgress) return;

    // [Prevent Double Submission]
    $('#btn-submit-answer').disabled = true;

    clearInterval(AppState.interview.timer);
    await stopRecording();

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
    const timeUsed = 120 - AppState.interview.timeLeft;
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
        if (result.interview_finished) {
            // Play closing remark properly
            const closingRemark = result.next_question || "면접이 종료되었습니다. 수고하셨습니다.";
            addChatLog('AI', closingRemark);
            // $('#ai-message').textContent = closingRemark;

            // [Prevent Double Submission] Disable controls immediately
            $('#btn-submit-answer').disabled = true;
            $('#user-answer').disabled = true;
            $('#feed-label').textContent = "면접 종료 (Redirecting...)";

            // Clear timer just in case
            if (AppState.interview.timer) clearInterval(AppState.interview.timer);
            stopRecording(); // Ensure recording is stopped

            // Use a flag to prevent double-calling finishInterview
            let finished = false;

            // Call finish after TTS with timeout safety
            const doFinish = () => {
                if (finished) return;
                finished = true;
                console.log("Finishing interview...");
                finishInterview();
            };

            // 1. Try Audio
            $('#btn-submit-answer').disabled = true;

            // Note: result.audio_url should be available here
            if (result.audio_url) {
                playAudio(result.audio_url, () => {
                    console.log("Audio Finished, calling doFinish");
                    doFinish();
                });
            } else {
                console.log("No Audio URL, forcing finish");
                doFinish();
            }

            // 2. Safety Timeout (3 seconds)
            setTimeout(() => {
                if (!finished) {
                    console.log("TTS Timeout, forcing finish");
                    doFinish();
                }
            }, 3000);

        } else {
            AppState.interview.currentQuestion = result.next_question;
            AppState.interview.currentAudioUrl = result.audio_url; // 미디어 URL 저장
            AppState.interview.currentAudioType = result.audio_type || 'audio'; // 미디어 타입 저장
            AppState.interview.currentQuestionIndex++;
            updateProgressUI();
            startQuestionSequence(result.next_question);
        }

    } catch (error) {
        showLoading(false);
        console.error(error);
        showToast('답변 제출 실패. 다시 시도해주세요.', 'error');
    }
}

function finishInterview() {
    // Already finished check handles the double-call from fallback
    // But we also need to ensure we don't re-run if already gone.
    // However, we set inProgress = false here.

    AppState.interview.inProgress = false;
    navigateTo('result-page');

    // Stop Camera
    const video = $('#user-video');
    if (video.srcObject) {
        video.srcObject.getTracks().forEach(track => track.stop());
        video.srcObject = null;
    }

    // Fetch Result
    loadInterviewResult();
}

async function loadInterviewResult() {
    const resultContainer = $('#result-desc');
    resultContainer.innerHTML = '면접 결과를 분석 중입니다...<br>잠시만 기다려주세요.';

    // Poll for result
    let attempts = 0;
    const maxAttempts = 10;

    const interval = setInterval(async () => {
        attempts++;
        try {
            const response = await fetch(`/api/interview/result/${AppState.interview.interviewNumber}`);
            const data = await response.json();

            if (data.success) {
                clearInterval(interval);
                renderResult(data.result);
            } else if (attempts >= maxAttempts) {
                clearInterval(interval);
                resultContainer.innerHTML = '결과 분석에 시간이 걸리고 있습니다.<br>나중에 마이페이지에서 확인해주세요.';
            }
        } catch (e) {
            console.error(e);
        }
    }, 2000); // Check every 2 seconds
}

function renderResult(result) {
    const resultContainer = $('#result-desc');
    const isPass = result.pass_fail === '합격';
    const color = isPass ? '#2ecc71' : '#e74c3c';

    resultContainer.innerHTML = `
        <div style="font-size: 2rem; font-weight: bold; color: ${color}; margin-bottom: 20px;">
            ${result.pass_fail}
        </div>
        <p>
            ${isPass ? '축하합니다! 면접에 합격하셨습니다.' : '아쉽게도 불합격하셨습니다.'}<br>
            수고하셨습니다.
        </p>
    `;
}

function updateProgressUI() {
    const total = AppState.interview.totalQuestions;
    const current = AppState.interview.currentQuestionIndex;
    const gauge = $('#progress-gauge');
    const text = $('#progress-text');

    if (!gauge || !text) return;

    text.textContent = `${current}/${total}`;
    gauge.innerHTML = '';

    for (let i = 1; i <= total; i++) {
        const li = document.createElement('li');
        if (i <= current) li.classList.add('active');
        gauge.appendChild(li);
    }
}

function addChatLog(sender, text) {
    const div = document.createElement('div');
    div.className = `chat-msg ${sender.toLowerCase()}`;
    div.innerHTML = `<strong>${sender}:</strong> ${text}`;
    $('#chat-log').appendChild(div);
    $('#chat-log').scrollTop = $('#chat-log').scrollHeight;
}

// --- 오디오/비디오 재생 유틸리티 ---
function playAudio(url, callback) {
    if (!url) {
        console.warn("[playAudio] URL이 제공되지 않았습니다.");
        if (callback) callback();
        return;
    }

    // URL 확장자로 비디오/오디오 구분
    const isVideo = url.toLowerCase().endsWith('.mp4');

    if (isVideo) {
        // 비디오 파일: <video> 태그로 재생 (Wav2Lip 립싱크 비디오)
        console.log(`[playVideo] 비디오 재생: ${url}`);
        const video = document.getElementById('ai-video');
        if (!video) {
            console.error("ai-video 요소를 찾을 수 없습니다!");
            if (callback) callback();
            return;
        }

        video.src = url;
        video.volume = 1.0;

        // 오디오 출력 장치 변경 (스피커 고정)
        if (AppState.interview.selectedDevices.audioOutputId && typeof video.setSinkId === 'function') {
            console.log(`[playVideo] 출력 장치 설정: ${AppState.interview.selectedDevices.audioOutputId}`);
            video.setSinkId(AppState.interview.selectedDevices.audioOutputId)
                .catch(err => console.error("setSinkId 오류 (Video):", err));
        }

        video.onended = () => {
            console.log(`[playVideo] 비디오 재생 종료: ${url}`);
            if (callback) callback();
        };

        video.onerror = (e) => {
            console.error("비디오 재생 오류:", e);
            if (video.error) {
                console.error(`[playVideo] 오류 코드: ${video.error.code}, 메시지: ${video.error.message}`);
            }
            if (callback) callback();
        };

        video.play().catch(e => {
            console.error("비디오 재생 실패:", e);
            if (callback) callback();
        });
    } else {
        // 오디오 파일 (.mp3 등): <audio> 요소로 재생 (비디오 생성 실패 시 폴백)
        console.log(`[playAudio] 오디오 재생: ${url}`);
        const audio = new Audio(url);
        audio.volume = 1.0;

        // 오디오 출력 장치 변경 (스피커 고정)
        if (AppState.interview.selectedDevices.audioOutputId && typeof audio.setSinkId === 'function') {
            console.log(`[playAudio] 출력 장치 설정: ${AppState.interview.selectedDevices.audioOutputId}`);
            audio.setSinkId(AppState.interview.selectedDevices.audioOutputId)
                .catch(err => console.error("setSinkId 오류 (Audio):", err));
        }

        audio.onended = () => {
            console.log(`[playAudio] 오디오 재생 종료: ${url}`);
            if (callback) callback();
        };

        audio.onerror = (e) => {
            console.error("오디오 재생 오류:", e);
            if (callback) callback();
        };

        audio.play().catch(e => {
            console.error("오디오 재생 실패:", e);
            if (callback) callback();
        });
    }
}


// --- 9. 관리자 기능 ---
function initAdmin() {
    $('#admin-menu-jobs').addEventListener('click', () => {
        $('#admin-view-jobs').classList.remove('hidden');
        $('#admin-view-applicants').classList.add('hidden');
        $('#admin-job-register-page').classList.add('hidden');
        $('#admin-job-edit-page').classList.add('hidden');
        fetchJobs();
    });

    $('#admin-link-my-info').addEventListener('click', () => {
        navigateTo('password-check-page');
        $('#check-pw-input').value = '';
        $('#check-pw-input').focus();
    });

    $('#btn-add-job').addEventListener('click', () => {
        $('#admin-view-jobs').classList.add('hidden');
        $('#admin-job-register-page').classList.remove('hidden');
        $('#job-title').value = '';
        $('#job-job').value = '';
        $('#job-content').value = '';
        $('#job-deadline').value = '';
        $('#job-qualifications').value = '';
        $('#job-preferred').value = '';
        $('#job-benefits').value = '';
        $('#job-hiring-process').value = '';
        $('#job-number-of-hires').value = '';
    });

    $('#btn-cancel-job-register').addEventListener('click', () => {
        $('#admin-job-register-page').classList.add('hidden');
        $('#admin-view-jobs').classList.remove('hidden');
    });

    // Job Edit Cancel
    $('#btn-cancel-job-edit').addEventListener('click', () => {
        $('#admin-job-edit-page').classList.add('hidden');
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
                    qualifications: $('#job-qualifications').value,
                    preferred_qualifications: $('#job-preferred').value,
                    benefits: $('#job-benefits').value,
                    hiring_process: $('#job-hiring-process').value,
                    number_of_hires: $('#job-number-of-hires').value,
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

    // Job Edit Submit
    $('#admin-job-edit-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = $('#edit-job-id').value;
        try {
            const resp = await fetch(`/api/jobs/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: $('#edit-job-title').value,
                    job: $('#edit-job-job').value,
                    content: $('#edit-job-content').value,
                    deadline: $('#edit-job-deadline').value,
                    qualifications: $('#edit-job-qualifications').value,
                    preferred_qualifications: $('#edit-job-preferred').value,
                    benefits: $('#edit-job-benefits').value,
                    hiring_process: $('#edit-job-hiring-process').value,
                    number_of_hires: $('#edit-job-number-of-hires').value,
                    id_name: AppState.currentUser.id_name
                })
            });
            const res = await resp.json();
            if (res.success) {
                showToast('수정 완료', 'success');
                $('#admin-job-edit-page').classList.add('hidden');
                $('#admin-view-jobs').classList.remove('hidden');
                fetchJobs();
            } else {
                showToast(res.message || '수정 실패', 'error');
            }
        } catch (e) { console.error(e); showToast('오류 발생', 'error'); }
    });

    // --- Applicant Management ---
    $('#admin-menu-applicants').addEventListener('click', () => {
        $('#admin-view-jobs').classList.add('hidden');
        $('#admin-view-applicants').classList.remove('hidden');
        $('#admin-job-register-page').classList.add('hidden');
        $('#admin-job-edit-page').classList.add('hidden');

        // Update active class
        $('#admin-menu-applicants').classList.add('active');
        $('#admin-menu-jobs').classList.remove('active');

        fetchAdminApplicants();
    });

    // Close Modal
    $('#btn-close-modal').addEventListener('click', () => {
        $('#applicant-detail-modal').classList.add('hidden');
    });

    window.addEventListener('click', (e) => {
        if (e.target === $('#applicant-detail-modal')) {
            $('#applicant-detail-modal').classList.add('hidden');
        }
    });
}

async function fetchAdminApplicants() {
    try {
        showLoading(true, '지원자 목록을 가져오는 중...');
        const adminId = AppState.currentUser ? AppState.currentUser.id_name : '';
        const response = await fetch(`/api/admin/applicants?admin_id=${adminId}`);
        const result = await response.json();
        showLoading(false);

        if (result.success) {
            renderAdminApplicantList(result.applicants);
        } else {
            showToast(result.message || '목록 로드 실패', 'error');
        }
    } catch (error) {
        showLoading(false);
        console.error(error);
        showToast('서버 통신 오류', 'error');
    }
}

function renderAdminApplicantList(applicants) {
    const tbody = $('#admin-app-table tbody');
    tbody.innerHTML = '';

    if (applicants.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px;">지원자가 없습니다.</td></tr>';
        return;
    }

    applicants.forEach(app => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${app.applicant_name} <br><span style="font-size: 0.8em; color: gray;">(req)</span></td>
            <td>${app.announcement_title}</td>
            <td>${app.announcement_job}</td>
            <td>${app.interview_time}</td>
            <td>
                <button class="btn-small" onclick="showApplicantDetail('${app.interview_number}')">상세보기</button>
                <button class="btn-small" onclick="deleteApplicant('${app.interview_number}')" style="background-color: #e74c3c; color: white;">삭제</button>
            </td>
        `;
        // 이메일 유지
        tr.innerHTML = tr.innerHTML.replace('(req)', app.email || '이메일 미등록');
        tbody.appendChild(tr);
    });
}

window.deleteApplicant = async (interviewNumber) => {
    if (!confirm('해당 지원자의 면접 정보를 정말 삭제하시겠습니까?')) return;

    try {
        const response = await fetch(`/api/admin/applicants/${interviewNumber}`, {
            method: 'DELETE'
        });
        const result = await response.json();

        if (result.success) {
            showToast(result.message || '삭제가 완료되었습니다.', 'success');
            // 목록 새로고침
            fetchAdminApplicants();
        } else {
            showToast(result.message || '삭제에 실패했습니다.', 'error');
        }
    } catch (error) {
        console.error('삭제 중 오류 발생:', error);
        showToast('서버 통신 오류가 발생했습니다.', 'error');
    }
};

window.showApplicantDetail = async (interviewNumber) => {
    try {
        showLoading(true, '상세 정보를 가져오는 중...');
        const response = await fetch(`/api/admin/applicant-details/${interviewNumber}`);
        const result = await response.json();
        showLoading(false);

        if (result.success) {
            const data = result.result;
            const progress = result.progress;
            const resumeText = result.resume_text;
            const resumeImagePaths = result.resume_image_path ? JSON.parse(result.resume_image_path) : null;

            // 1. Fill Header
            $('#detail-modal-title').textContent = `${data.title} - 지원자 상세 정보`;

            // 2. Fill Summary Scores & Evaluations
            const passFail = data.pass_fail;
            const passEl = $('#detail-pass-status');
            passEl.textContent = passFail;
            passEl.className = `pass-status ${passFail === '합격' ? 'pass' : 'fail'}`;

            // Update to show Text Evaluations as requested
            // Tech
            $('#score-val-tech').textContent = `${data.tech_score || 0}점`;
            $('#eval-text-tech').textContent = data.tech_eval || '평가 없음';

            // Problem Solving
            $('#score-val-problem').textContent = `${data.problem_solving_score || 0}점`;
            $('#eval-text-problem').textContent = data.problem_solving_eval || '평가 없음';

            // Communication
            $('#score-val-comm').textContent = `${data.communication_score || 0}점`;
            $('#eval-text-comm').textContent = data.communication_eval || '평가 없음';

            // Attitude
            $('#score-val-attitude').textContent = `${data.non_verbal_score || 0}점`;
            $('#eval-text-attitude').textContent = data.non_verbal_eval || '평가 없음';

            // 3. Fill Resume
            // 3. Fill Resume (Text + Images)
            const resumeContainer = $('#detail-resume');
            resumeContainer.innerHTML = ''; // Clear previous content

            // If images exist, show them
            if (resumeImagePaths && resumeImagePaths.length > 0) {
                const gallery = document.createElement('div');
                gallery.className = 'resume-gallery';

                resumeImagePaths.forEach(path => {
                    const img = document.createElement('img');
                    img.src = path;
                    img.className = 'resume-thumb';
                    img.alt = '이력서 이미지';
                    img.onclick = function () {
                        openZoomModal(this.src);
                    };
                    gallery.appendChild(img);
                });
                resumeContainer.appendChild(gallery);

                // Also show text below if needed, or just images. User asked for images mainly.
                // Let's hide text if images are present to keep it clean, or toggle?
                // Request said "view in 'Resume Content'".
                // We can append text in a details summary if needed, but images are better.
            } else {
                // Fallback to text
                resumeContainer.textContent = resumeText || '이력서 내용이 없습니다.';
            }

            // 4. Fill Interview Log
            const logBox = $('#detail-log');
            logBox.innerHTML = '';

            if (progress && progress.length > 0) {
                progress.forEach((p, idx) => {
                    const logItem = document.createElement('div');
                    logItem.className = 'log-item';

                    // interview_progress columns: create_question, question_answer
                    const question = p.create_question || p.Create_Question || '질문 없음';
                    const answer = p.question_answer || p.Question_answer || '(답변 없음)';
                    const evaluation = p.answer_evaluation || p.Answer_Evaluation || '평가 없음';

                    logItem.innerHTML = `
                        <div class="log-q">Q${idx + 1}. ${question}</div>
                        <div class="log-a">A: ${answer}</div>
                    `;
                    // <div class="log-e">평가: ${evaluation}</div> // Individual answer eval optional in summary logic? Keep it if useful.
                    logBox.appendChild(logItem);
                });
            } else {
                logBox.innerHTML = '<p>대화 기록이 없습니다.</p>';
            }

            // Show Modal
            $('#applicant-detail-modal').classList.remove('hidden');
        } else {
            showToast(result.message || '상세 정보 로드 실패', 'error');
        }
    } catch (error) {
        showLoading(false);
        console.error(error);
        showToast('서버 통신 오류', 'error');
    }
};

function renderAdminJobList() {
    const tbody = $('#admin-job-table tbody');
    tbody.innerHTML = '';
    MOCK_DB.jobs.forEach(job => {
        const tr = document.createElement('tr');
        const isOwner = job.id_name === AppState.currentUser.id_name;

        let actionButtons = '';
        if (isOwner) {
            actionButtons = `
                <button class="btn-small btn-original" style="background-color: #95a5a6; color: white; margin-right: 5px;" onclick="editJob(${job.id})">수정</button>
                <button class="btn-small btn-secondary" onclick="deleteJob(${job.id})">삭제</button>
            `;
        } else {
            actionButtons = `<span style="color: #ccc; font-size: 0.9em;">권한 없음</span>`;
        }

        tr.innerHTML = `
            <td>${job.id}</td>
            <td>${job.job || '-'}</td>
            <td>${job.title}</td>
            <td>${job.id_name || '-'}</td>
            <td>${job.created_at}</td>
            <td>${job.deadline}</td>
            <td>${actionButtons}</td>
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

window.editJob = (id) => {
    const job = MOCK_DB.jobs.find(j => j.id === id);
    if (!job) return;

    // Check permission again (Client-side)
    if (job.id_name !== AppState.currentUser.id_name) {
        showToast('수정 권한이 없습니다.', 'error');
        return;
    }

    $('#edit-job-id').value = job.id;
    $('#edit-job-title').value = job.title;
    $('#edit-job-job').value = job.job || '';
    $('#edit-job-content').value = job.content || '';
    $('#edit-job-deadline').value = job.deadline || '';
    $('#edit-job-qualifications').value = job.qualifications || '';
    $('#edit-job-preferred').value = job.preferred_qualifications || '';
    $('#edit-job-benefits').value = job.benefits || '';
    $('#edit-job-hiring-process').value = job.hiring_process || '';
    $('#edit-job-number-of-hires').value = job.number_of_hires || '';

    $('#admin-view-jobs').classList.add('hidden');
    $('#admin-job-edit-page').classList.remove('hidden');
};


// --- Image Zoom Logic ---
function openZoomModal(src) {
    const modal = $('#image-zoom-modal');
    const modalImg = $('#zoomed-image');
    modal.style.display = "block"; // Override flex? No, CSS has display:flex for modal. 
    // But .hidden handles display:none.
    modal.classList.remove('hidden');
    modalImg.src = src;
}

// Close Zoom Modal
document.querySelector('.close-zoom').addEventListener('click', () => {
    $('#image-zoom-modal').classList.add('hidden');
});

// Close when clicking outside image
$('#image-zoom-modal').addEventListener('click', (e) => {
    if (e.target === $('#image-zoom-modal')) {
        $('#image-zoom-modal').classList.add('hidden');
    }
});
