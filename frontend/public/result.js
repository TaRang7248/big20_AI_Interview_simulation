(function () {
    // ✅ 스크립트 중복 실행 방지
    if (window.__RESULT_PAGE_BOOTED__) return;
    window.__RESULT_PAGE_BOOTED__ = true;

    let radarChart = null;

    function renderRadarChart(data) {
        const canvas = document.getElementById("radarChart");
        if (!canvas || !data?.radar?.length) return;

        const labels = data.radar.map((x) => x.label);
        const values = data.radar.map((x) => x.score);

        if (radarChart) radarChart.destroy();

        const isDark = document.body.dataset.theme === "dark";
        const TEXT = isDark ? "rgba(243,246,255,.90)" : "rgba(18,24,38,.85)";
        const MUTED = isDark ? "rgba(243,246,255,.70)" : "rgba(18,24,38,.60)";
        const GRID = isDark ? "rgba(243,246,255,.14)" : "rgba(18,24,38,.10)";

        radarChart = new Chart(canvas, {
            type: "radar",
            data: {
                labels,
                datasets: [{ label: "점수(1~5)", data: values }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: 16 },
                plugins: {
                    legend: { labels: { color: TEXT } },
                },
                scales: {
                    r: {
                        suggestedMin: 0,
                        suggestedMax: 5,
                        pointLabels: { color: TEXT },
                        ticks: { stepSize: 1, color: MUTED },
                        grid: { color: GRID },
                        angleLines: { color: GRID },
                    },
                },
            },
        });
    }

    /**
     * ✅ URL에서 리포트 식별자 가져오기
     * - 1순위: thread_id (예: my_new_interview_01)
     * - 2순위: session_id (구버전 호환)
     */
    function getReportId() {
        const params = new URLSearchParams(location.search);

        const threadId = params.get("thread_id");
        if (threadId) return { key: "thread_id", value: threadId };

        const sessionId = params.get("session_id");
        if (sessionId) return { key: "session_id", value: sessionId };

        return null;
    }

    function renderError(msg) {
        document.body.innerHTML = `<pre style="padding:16px;white-space:pre-wrap">${msg}</pre>`;
    }

    async function loadReportOnce() {
        const reportId = getReportId();

        if (!reportId) {
            renderError(
                "thread_id 또는 session_id가 URL에 없습니다.\n" +
                "예) result.html?thread_id=my_new_interview_01\n" +
                "예) result.html?session_id=1"
            );
            return;
        }

        /**
         * ✅ 여기 핵심:
         * 기존: /report/session/{session_id}/result (session_id int 요구 → threadId 넣으면 422)
         * 변경: /report/{id}/result 로 통일 (React ResultRoutePage_yyr.jsx와 동일)
         */
        const url = `http://127.0.0.1:8001/report/${encodeURIComponent(
            reportId.value
        )}/result`;

        let res;
        try {
            res = await fetch(url);
        } catch (e) {
            renderError(`API 호출 실패(백엔드 실행 여부 확인):\n${String(e)}`);
            return;
        }

        if (!res.ok) {
            renderError(`API 오류: ${res.status}\n${await res.text()}`);
            return;
        }

        const data = await res.json();

        // 상단 카드
        document.getElementById("totalScore").textContent = data.total_score ?? "-";

        const badge = document.getElementById("resultBadge");
        badge.textContent = data.final_result ?? "-";
        badge.classList.remove("pass", "fail");
        badge.classList.add(data.final_result === "PASS" ? "pass" : "fail");

        document.getElementById("summaryText").textContent = data.summary || "-";
        document.getElementById("createdAt").textContent = data.created_at
            ? `생성 시각: ${data.created_at}`
            : "";

        renderRadarChart(data);

        // 피드백 카드
        const grid = document.getElementById("feedbackGrid");
        grid.innerHTML = "";

        // radar 축 매핑 (axis -> label)
        const axisToLabel = Object.fromEntries(
            (data.radar || []).map((x) => [x.axis, x.label])
        );

        const feedback = data.feedback || {};
        for (const [axis, obj] of Object.entries(feedback)) {
            const label = axisToLabel[axis] || axis;

            const div = document.createElement("div");
            div.className = "card";
            div.innerHTML = `
        <div class="pill">${label} <small>· ${obj?.score ?? "-"}점</small></div>

        <div class="muted"><b>피드백</b><br />${obj?.feedback ?? "-"}</div>

        <button class="toggle-btn" type="button">근거 보기</button>
        <div class="rationale muted" hidden>
          <b>근거</b><br />${obj?.rationale ?? "-"}
        </div>
      `;
            grid.appendChild(div);
        }
    }

    // ✅ 페이지 로드 시 1회만 실행
    window.addEventListener("DOMContentLoaded", loadReportOnce, { once: true });

    // ✅ 근거 접기/펼치기 이벤트
    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".toggle-btn");
        if (!btn) return;

        const box = btn.parentElement.querySelector(".rationale");
        const open = !box.hasAttribute("hidden");

        if (open) {
            box.setAttribute("hidden", "");
            btn.textContent = "근거 보기";
        } else {
            box.removeAttribute("hidden");
            btn.textContent = "근거 접기";
        }
    });

    // ===== Theme toggle =====
    const themeBtn = document.getElementById("themeToggle");
    if (themeBtn) {
        const saved = localStorage.getItem("theme");
        if (saved === "dark") {
            document.body.dataset.theme = "dark";
            themeBtn.textContent = "라이트모드";
        }

        themeBtn.addEventListener("click", () => {
            const isDark = document.body.dataset.theme === "dark";
            if (isDark) {
                delete document.body.dataset.theme;
                localStorage.setItem("theme", "light");
                themeBtn.textContent = "다크모드";
            } else {
                document.body.dataset.theme = "dark";
                localStorage.setItem("theme", "dark");
                themeBtn.textContent = "라이트모드";
            }

            // 테마 변경 후 차트 스타일 반영 위해 재호출
            loadReportOnce();
        });
    }
})();

// if (window.__reportLoaded) throw new Error("STOP: loadReport duplicated");
// window.__reportLoaded = true;

// async function loadReport() {
//     const params = new URLSearchParams(location.search);
//     const sessionId = params.get("session_id");
//     const url = `http://127.0.0.1:8001/report/session/${sessionId}/result`;

//     const res = await fetch(url);
//     if (!res.ok) {
//         document.body.innerHTML = `<pre>API 오류: ${res.status}\n${await res.text()}</pre>`;
//         return;
//     }

//     const data = await res.json();

//     document.getElementById("totalScore").textContent = data.total_score;

//     const badge = document.getElementById("resultBadge");
//     badge.textContent = data.final_result;
//     badge.classList.remove("pass", "fail");
//     badge.classList.add(data.final_result === "PASS" ? "pass" : "fail");

//     document.getElementById("summaryText").textContent = data.summary || "-";
//     document.getElementById("createdAt").textContent =
//         data.created_at ? `생성 시각: ${data.created_at}` : "";

//     const labels = data.radar.map(x => x.label);
//     const values = data.radar.map(x => x.score);

//     new Chart(document.getElementById("radarChart"), {
//         type: "radar",
//         data: { labels, datasets: [{ label: "점수(1~5)", data: values }] },
//         options: {
//             scales: { r: { suggestedMin: 0, suggestedMax: 5, ticks: { stepSize: 1 } } }
//         }
//     });

//     const axisToLabel = Object.fromEntries(data.radar.map(x => [x.axis, x.label]));
//     const grid = document.getElementById("feedbackGrid");
//     grid.innerHTML = "";

//     for (const [axis, obj] of Object.entries(data.feedback)) {
//         const label = axisToLabel[axis] || axis;
//         const div = document.createElement("div");
//         div.className = "card";
//         div.innerHTML = `
//       <div class="pill">${label} <small>· ${obj.score}점</small></div>
//       <div class="muted"><b>피드백</b><br />${obj.feedback}</div>
//       <div class="muted"><b>근거</b><br />${obj.rationale}</div>
//     `;
//         grid.appendChild(div);
//         console.log("cards:", grid.children.length);
//     }
// }

// window.addEventListener("DOMContentLoaded", loadReport);

// 두번째.
// (function () {
//     // ✅ 스크립트가 실수로 2번 로드돼도 1번만 실행
//     if (window.__RESULT_PAGE_BOOTED__) return;
//     window.__RESULT_PAGE_BOOTED__ = true;

//     let radarChart = null;

//     function getSessionId() {
//         const params = new URLSearchParams(location.search);
//         return params.get("session_id");
//     }

//     function renderError(msg) {
//         document.body.innerHTML = `<pre style="padding:16px;white-space:pre-wrap">${msg}</pre>`;
//     }

//     async function loadReportOnce() {
//         const sessionId = getSessionId();
//         if (!sessionId) {
//             renderError("session_id가 URL에 없습니다.\n예) result.html?session_id=1");
//             return;
//         }

//         const url = `http://127.0.0.1:8001/report/session/${sessionId}/result`;

//         let res;
//         try {
//             res = await fetch(url);
//         } catch (e) {
//             renderError(`API 호출 실패(백엔드 실행 여부 확인):\n${String(e)}`);
//             return;
//         }

//         if (!res.ok) {
//             renderError(`API 오류: ${res.status}\n${await res.text()}`);
//             return;
//         }

//         const data = await res.json();

//         // --- 상단 카드 ---
//         const totalEl = document.getElementById("totalScore");
//         const badgeEl = document.getElementById("resultBadge");
//         const summaryEl = document.getElementById("summaryText");
//         const createdEl = document.getElementById("createdAt");

//         if (totalEl) totalEl.textContent = data.total_score ?? "-";
//         if (badgeEl) {
//             badgeEl.textContent = data.final_result ?? "-";
//             badgeEl.classList.remove("pass", "fail");
//             badgeEl.classList.add(data.final_result === "PASS" ? "pass" : "fail");
//         }
//         if (summaryEl) summaryEl.textContent = data.summary || "-";
//         if (createdEl) createdEl.textContent = data.created_at ? `생성 시각: ${data.created_at}` : "";

//         // --- 레이더 차트 ---
//         const canvas = document.getElementById("radarChart");
//         if (canvas && data?.radar?.length) {
//             const labels = data.radar.map(x => x.label);
//             const values = data.radar.map(x => x.score);

//             // ✅ 차트 중복 생성 방지
//             if (radarChart) radarChart.destroy();

//             radarChart = new Chart(canvas, {
//                 type: "radar",
//                 data: {
//                     labels,
//                     datasets: [{ label: "점수(1~5)", data: values }]
//                 },
//                 options: {
//                     responsive: true,
//                     maintainAspectRatio: false,
//                     layout: { padding: 16 },
//                     scales: {
//                         r: {
//                             suggestedMin: 0,
//                             suggestedMax: 5,
//                             ticks: { stepSize: 1 }
//                         }
//                     }
//                 }
//             });
//         }

//         // --- 피드백 카드 ---
//         const grid = document.getElementById("feedbackGrid");
//         if (grid) {
//             // ✅ 누적 방지: 항상 비우고 다시 그림
//             grid.innerHTML = "";

//             const axisToLabel = data?.radar
//                 ? Object.fromEntries(data.radar.map(x => [x.axis, x.label]))
//                 : {};

//             const feedback = data?.feedback || {};
//             for (const [axis, obj] of Object.entries(feedback)) {
//                 const label = axisToLabel[axis] || axis;

//                 const div = document.createElement("div");
//                 div.className = "card";
//                 div.innerHTML = `
//                 <div class="pill">${label} <small>· ${obj?.score ?? "-"}점</small></div>

//                 <div class="muted"><b>피드백</b><br />${obj?.feedback ?? "-"}</div>

//                 <button class="toggle-btn" type="button">근거 보기</button>
//                 <div class="rationale muted" hidden>
//                 <b>근거</b><br />${obj?.rationale ?? "-"}
//                 </div>
//                 `;
//                 grid.appendChild(div);
//             }
//         }
//     }

//     window.addEventListener("DOMContentLoaded", loadReportOnce, { once: true });
// })();

// ====================
// (function () {
//     // ✅ 스크립트 중복 실행 방지
//     if (window.__RESULT_PAGE_BOOTED__) return;
//     window.__RESULT_PAGE_BOOTED__ = true;

//     let radarChart = null;

//     function getSessionId() {
//         const params = new URLSearchParams(location.search);
//         return params.get("session_id");
//     }

//     function renderError(msg) {
//         document.body.innerHTML = `<pre style="padding:16px;white-space:pre-wrap">${msg}</pre>`;
//     }

//     async function loadReportOnce() {
//         const sessionId = getSessionId();
//         if (!sessionId) {
//             renderError("session_id가 URL에 없습니다.\n예) result.html?session_id=1");
//             return;
//         }

//         const url = `http://127.0.0.1:8001/report/session/${sessionId}/result`;

//         let res;
//         try {
//             res = await fetch(url);
//         } catch (e) {
//             renderError(`API 호출 실패(백엔드 실행 여부 확인):\n${String(e)}`);
//             return;
//         }

//         if (!res.ok) {
//             renderError(`API 오류: ${res.status}\n${await res.text()}`);
//             return;
//         }

//         const data = await res.json();

//         // 상단 카드
//         document.getElementById("totalScore").textContent = data.total_score ?? "-";

//         const badge = document.getElementById("resultBadge");
//         badge.textContent = data.final_result ?? "-";
//         badge.classList.remove("pass", "fail");
//         badge.classList.add(data.final_result === "PASS" ? "pass" : "fail");

//         document.getElementById("summaryText").textContent = data.summary || "-";
//         document.getElementById("createdAt").textContent =
//             data.created_at ? `생성 시각: ${data.created_at}` : "";

//         // 레이더 차트
//         const canvas = document.getElementById("radarChart");
//         if (canvas && data?.radar?.length) {
//             const labels = data.radar.map(x => x.label);
//             const values = data.radar.map(x => x.score);

//             if (radarChart) radarChart.destroy();

//             const isDark = document.body.dataset.theme === "dark";
//             const TEXT = isDark ? "rgba(243,246,255,.90)" : "rgba(18,24,38,.85)";
//             const MUTED = isDark ? "rgba(243,246,255,.70)" : "rgba(18,24,38,.60)";
//             const GRID = isDark ? "rgba(243,246,255,.14)" : "rgba(18,24,38,.10)";

//             radarChart = new Chart(canvas, {
//                 type: "radar",
//                 data: {
//                     labels,
//                     datasets: [{ label: "점수(1~5)", data: values }]
//                 },
//                 options: {
//                     responsive: true,
//                     maintainAspectRatio: false,
//                     layout: { padding: 16 },

//                     plugins: {
//                         legend: {
//                             labels: { color: TEXT }   // ✅ 범례 글자색
//                         }
//                     },

//                     scales: {
//                         r: {
//                             suggestedMin: 0,
//                             suggestedMax: 5,

//                             pointLabels: { color: TEXT },     // ✅ 기술역량/문제해결/… 라벨
//                             ticks: { stepSize: 1, color: MUTED }, // ✅ 1~5 눈금 글자
//                             grid: { color: GRID },            // ✅ 격자선
//                             angleLines: { color: GRID }       // ✅ 방사선
//                         }
//                     }
//                 }
//             });
//         }


//         // 피드백 카드
//         const grid = document.getElementById("feedbackGrid");
//         grid.innerHTML = "";

//         const axisToLabel = Object.fromEntries(
//             data.radar.map(x => [x.axis, x.label])
//         );

//         for (const [axis, obj] of Object.entries(data.feedback)) {
//             const label = axisToLabel[axis] || axis;

//             const div = document.createElement("div");
//             div.className = "card";
//             div.innerHTML = `
//         <div class="pill">${label} <small>· ${obj.score}점</small></div>

//         <div class="muted"><b>피드백</b><br />${obj.feedback}</div>

//         <button class="toggle-btn" type="button">근거 보기</button>
//         <div class="rationale muted" hidden>
//           <b>근거</b><br />${obj.rationale}
//         </div>
//       `;
//             grid.appendChild(div);
//         }
//     }

//     // ✅ 페이지 로드 시 1회만 실행
//     window.addEventListener("DOMContentLoaded", loadReportOnce, { once: true });

//     // ✅ 근거 접기/펼치기 이벤트 (여기다 합침)
//     document.addEventListener("click", (e) => {
//         const btn = e.target.closest(".toggle-btn");
//         if (!btn) return;

//         const box = btn.parentElement.querySelector(".rationale");
//         const open = !box.hasAttribute("hidden");

//         if (open) {
//             box.setAttribute("hidden", "");
//             btn.textContent = "근거 보기";
//         } else {
//             box.removeAttribute("hidden");
//             btn.textContent = "근거 접기";
//         }
//     });
//     // ===== Theme toggle (C) =====
//     const themeBtn = document.getElementById("themeToggle");
//     if (themeBtn) {
//         const saved = localStorage.getItem("theme");
//         if (saved === "dark") {
//             document.body.dataset.theme = "dark";
//             themeBtn.textContent = "라이트모드";
//         }

//         themeBtn.addEventListener("click", () => {
//             const isDark = document.body.dataset.theme === "dark";
//             if (isDark) {
//                 delete document.body.dataset.theme;
//                 localStorage.setItem("theme", "light");
//                 themeBtn.textContent = "다크모드";
//             } else {
//                 document.body.dataset.theme = "dark";
//                 localStorage.setItem("theme", "dark");
//                 themeBtn.textContent = "라이트모드";
//             }
//         });
//     }


// })();


// 26. 02. 25 까지의 가장 최신 코드
// (function () {
//     // ✅ 스크립트 중복 실행 방지
//     if (window.__RESULT_PAGE_BOOTED__) return;
//     window.__RESULT_PAGE_BOOTED__ = true;

//     let radarChart = null;

//     function renderRadarChart(data) {
//         const canvas = document.getElementById("radarChart");
//         if (!canvas || !data?.radar?.length) return;

//         const labels = data.radar.map(x => x.label);
//         const values = data.radar.map(x => x.score);

//         if (radarChart) radarChart.destroy();

//         const isDark = document.body.dataset.theme === "dark";
//         const TEXT = isDark ? "rgba(243,246,255,.90)" : "rgba(18,24,38,.85)";
//         const MUTED = isDark ? "rgba(243,246,255,.70)" : "rgba(18,24,38,.60)";
//         const GRID = isDark ? "rgba(243,246,255,.14)" : "rgba(18,24,38,.10)";

//         radarChart = new Chart(canvas, {
//             type: "radar",
//             data: {
//                 labels,
//                 datasets: [{ label: "점수(1~5)", data: values }]
//             },
//             options: {
//                 responsive: true,
//                 maintainAspectRatio: false,
//                 layout: { padding: 16 },
//                 plugins: {
//                     legend: { labels: { color: TEXT } }
//                 },
//                 scales: {
//                     r: {
//                         suggestedMin: 0,
//                         suggestedMax: 5,
//                         pointLabels: { color: TEXT },
//                         ticks: { stepSize: 1, color: MUTED },
//                         grid: { color: GRID },
//                         angleLines: { color: GRID }
//                     }
//                 }
//             }
//         });
//     }

//     function getSessionId() {
//         const params = new URLSearchParams(location.search);
//         return params.get("session_id");
//     }

//     function renderError(msg) {
//         document.body.innerHTML = `<pre style="padding:16px;white-space:pre-wrap">${msg}</pre>`;
//     }

//     async function loadReportOnce() {
//         const sessionId = getSessionId();
//         if (!sessionId) {
//             renderError("session_id가 URL에 없습니다.\n예) result.html?session_id=1");
//             return;
//         }

//         const url = `http://127.0.0.1:8001/report/session/${sessionId}/result`;

//         let res;
//         try {
//             res = await fetch(url);
//         } catch (e) {
//             renderError(`API 호출 실패(백엔드 실행 여부 확인):\n${String(e)}`);
//             return;
//         }

//         if (!res.ok) {
//             renderError(`API 오류: ${res.status}\n${await res.text()}`);
//             return;
//         }

//         const data = await res.json();

//         // 상단 카드
//         document.getElementById("totalScore").textContent = data.total_score ?? "-";

//         const badge = document.getElementById("resultBadge");
//         badge.textContent = data.final_result ?? "-";
//         badge.classList.remove("pass", "fail");
//         badge.classList.add(data.final_result === "PASS" ? "pass" : "fail");

//         document.getElementById("summaryText").textContent = data.summary || "-";
//         document.getElementById("createdAt").textContent =
//             data.created_at ? `생성 시각: ${data.created_at}` : "";

//         renderRadarChart(data);

//         // 피드백 카드
//         const grid = document.getElementById("feedbackGrid");
//         grid.innerHTML = "";

//         const axisToLabel = Object.fromEntries(
//             data.radar.map(x => [x.axis, x.label])
//         );

//         for (const [axis, obj] of Object.entries(data.feedback)) {
//             const label = axisToLabel[axis] || axis;

//             const div = document.createElement("div");
//             div.className = "card";
//             div.innerHTML = `
//         <div class="pill">${label} <small>· ${obj.score}점</small></div>

//         <div class="muted"><b>피드백</b><br />${obj.feedback}</div>

//         <button class="toggle-btn" type="button">근거 보기</button>
//         <div class="rationale muted" hidden>
//           <b>근거</b><br />${obj.rationale}
//         </div>
//       `;
//             grid.appendChild(div);
//         }
//     }

//     // ✅ 페이지 로드 시 1회만 실행
//     window.addEventListener("DOMContentLoaded", loadReportOnce, { once: true });

//     // ✅ 근거 접기/펼치기 이벤트 (여기다 합침)
//     document.addEventListener("click", (e) => {
//         const btn = e.target.closest(".toggle-btn");
//         if (!btn) return;

//         const box = btn.parentElement.querySelector(".rationale");
//         const open = !box.hasAttribute("hidden");

//         if (open) {
//             box.setAttribute("hidden", "");
//             btn.textContent = "근거 보기";
//         } else {
//             box.removeAttribute("hidden");
//             btn.textContent = "근거 접기";
//         }
//     });

//     // ===== Theme toggle (C) =====
//     const themeBtn = document.getElementById("themeToggle");
//     if (themeBtn) {
//         const saved = localStorage.getItem("theme");
//         if (saved === "dark") {
//             document.body.dataset.theme = "dark";
//             themeBtn.textContent = "라이트모드";
//         }

//         themeBtn.addEventListener("click", () => {
//             const isDark = document.body.dataset.theme === "dark";
//             if (isDark) {
//                 delete document.body.dataset.theme;
//                 localStorage.setItem("theme", "light");
//                 themeBtn.textContent = "다크모드";
//             } else {
//                 document.body.dataset.theme = "dark";
//                 localStorage.setItem("theme", "dark");
//                 themeBtn.textContent = "라이트모드";
//             }

//             loadReportOnce();
//         });
//     }

// })();
