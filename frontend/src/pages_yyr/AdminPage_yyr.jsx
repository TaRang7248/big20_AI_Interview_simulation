// frontend/src/pages_yyr/AdminPage_yyr.jsx
import React from "react";
import { useNavigate } from "react-router-dom";
import { FaClipboardList, FaChartRadar, FaSignOutAlt, FaArrowRight } from "react-icons/fa";

export default function AdminPage_yyr() {
    const nav = useNavigate();

    const glass =
        "bg-white/55 backdrop-blur-xl border border-white/60 shadow-[0_20px_40px_-20px_rgba(0,0,0,0.15)] rounded-3xl";

    // ✅ 더미 데이터 (MVP: 구조 고정용)
    const stats = [
        { label: "오늘 면접 수", value: 4 },
        { label: "최근 7일 면접 수", value: 23 },
        { label: "합격률(7일)", value: "39%" },
        { label: "평균 점수(7일)", value: 72 },
    ];

    const recentJobs = [
        { jobId: "job-101", title: "프론트엔드 인턴", status: "게시중", createdAt: "2026-02-25" },
        { jobId: "job-102", title: "백엔드 주니어", status: "게시중", createdAt: "2026-02-24" },
        { jobId: "job-103", title: "데이터 분석 인턴", status: "마감", createdAt: "2026-02-20" },
        { jobId: "job-104", title: "AI 엔지니어(주니어)", status: "조기종료", createdAt: "2026-02-18" },
    ];

    const recentResults = [
        {
            threadId: "session_1700000000001",
            candidateName: "김민지 (A-01)",
            jobTitle: "프론트엔드 인턴",
            verdict: "PASS",
            score: 81,
            createdAt: "2026-02-25 09:14",
        },
        {
            threadId: "session_1700000000002",
            candidateName: "박준호 (A-02)",
            jobTitle: "백엔드 주니어",
            verdict: "FAIL",
            score: 63,
            createdAt: "2026-02-25 08:42",
        },
        {
            threadId: "session_1700000000003",
            candidateName: "이서연 (A-03)",
            jobTitle: "데이터 분석 인턴",
            verdict: "PASS",
            score: 76,
            createdAt: "2026-02-24 18:01",
        },
        {
            threadId: "session_1700000000004",
            candidateName: "정우진 (A-04)",
            jobTitle: "프론트엔드 인턴",
            verdict: "FAIL",
            score: 58,
            createdAt: "2026-02-24 16:10",
        },
        {
            threadId: "session_1700000000005",
            candidateName: "최하늘 (A-05)",
            jobTitle: "AI 엔지니어(주니어)",
            verdict: "PASS",
            score: 88,
            createdAt: "2026-02-23 20:33",
        },
    ];

    const badgeForJobStatus = (status) => {
        const base = "inline-flex items-center px-2 py-1 rounded-xl text-[11px] font-extrabold";
        if (status === "게시중") return `${base} bg-emerald-50 text-emerald-700`;
        if (status === "마감") return `${base} bg-slate-100 text-slate-700`;
        if (status === "조기종료") return `${base} bg-rose-50 text-rose-700`;
        return `${base} bg-slate-100 text-slate-700`;
    };

    const badgeForVerdict = (verdict) => {
        const base = "inline-flex items-center px-2 py-1 rounded-xl text-[11px] font-extrabold";
        if (verdict === "PASS") return `${base} bg-emerald-50 text-emerald-700`;
        return `${base} bg-rose-50 text-rose-700`;
    };

    const handleLogout = () => {
        localStorage.removeItem("auth_token");
        localStorage.removeItem("role");
        window.location.href = "/login";
    };

    return (
        <div className="min-h-screen bg-gradient-to-b from-sky-50 via-white to-indigo-50 text-slate-900">
            {/* Header */}
            <header className="sticky top-0 z-40 backdrop-blur-xl bg-white/60 border-b border-white/60">
                <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-sky-500 to-violet-500" />
                        <div>
                            <h1 className="text-sm font-extrabold">Admin Dashboard</h1>
                            <p className="text-[11px] text-slate-500">
                                관리자 홈(MVP) — 공고/지원자/결과로 빠르게 이동
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => nav("/user/home")}
                            className="px-3 py-2 rounded-xl bg-white/70 border border-white/60 text-slate-900 text-sm font-extrabold hover:bg-white transition"
                        >
                            면접자 로비로 <FaArrowRight className="inline ml-1" />
                        </button>
                        <button
                            onClick={handleLogout}
                            className="px-3 py-2 rounded-xl bg-slate-900 text-white text-sm font-extrabold"
                        >
                            로그아웃 <FaSignOutAlt className="inline ml-1" />
                        </button>
                    </div>
                </div>
            </header>

            <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
                {/* Quick Actions */}
                <section className={`${glass} p-6`}>
                    <p className="text-xs text-slate-500 font-semibold">Quick Actions</p>
                    <p className="text-base font-extrabold mt-1">빠른 실행</p>

                    <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <button
                            onClick={() => nav("/admin/jobs")}
                            className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-2xl text-sm font-extrabold text-white bg-gradient-to-r from-sky-500 to-violet-500 hover:opacity-95 transition"
                        >
                            <FaClipboardList /> 공고 관리로 이동
                        </button>

                        <button
                            onClick={() => {
                                // ✅ 너희 기존 "샘플 결과 보기(레이더)" 동작이 새 창이라면 그대로 유지
                                // 필요하면 아래를 원하는 경로로 바꿔도 됨.
                                window.open("/admin/result/session_1700000000001", "_blank", "noopener,noreferrer");
                            }}
                            className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-2xl text-sm font-extrabold bg-white/70 border border-white/60 hover:bg-white transition"
                        >
                            <FaChartRadar /> 샘플 결과 보기(레이더)
                        </button>
                    </div>

                    <p className="text-[11px] text-slate-500 mt-3">
                        * MVP 단계에서는 더미 데이터 기반으로 화면 구조만 먼저 고정합니다.
                    </p>
                </section>

                {/* Stats */}
                <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {stats.map((s) => (
                        <div key={s.label} className={`${glass} p-5`}>
                            <p className="text-xs text-slate-500 font-semibold">{s.label}</p>
                            <p className="text-2xl font-extrabold mt-2">{s.value}</p>
                            <p className="text-[11px] text-slate-500 mt-1">더미 데이터</p>
                        </div>
                    ))}
                </section>

                {/* Recent */}
                <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Recent Jobs */}
                    <div className={`${glass} p-6`}>
                        <p className="text-xs text-slate-500 font-semibold">Recent Jobs</p>
                        <p className="text-base font-extrabold mt-1">최근 공고</p>

                        <div className="mt-4 divide-y divide-white/60">
                            {recentJobs.slice(0, 5).map((j) => (
                                <button
                                    key={j.jobId}
                                    onClick={() => nav(`/admin/jobs/${j.jobId}`)}
                                    className="w-full py-3 flex items-center justify-between hover:bg-white/40 rounded-2xl px-3 transition text-left"
                                >
                                    <div>
                                        <p className="text-sm font-extrabold">{j.title}</p>
                                        <p className="text-[11px] text-slate-500 mt-1">
                                            {j.createdAt} · {j.jobId}
                                        </p>
                                    </div>
                                    <span className={badgeForJobStatus(j.status)}>{j.status}</span>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Recent Results */}
                    <div className={`${glass} p-6`}>
                        <p className="text-xs text-slate-500 font-semibold">Recent Results</p>
                        <p className="text-base font-extrabold mt-1">최근 면접 결과</p>

                        <div className="mt-4 divide-y divide-white/60">
                            {recentResults.slice(0, 6).map((r) => (
                                <button
                                    key={r.threadId}
                                    onClick={() => nav(`/admin/result/${r.threadId}`)}
                                    className="w-full py-3 flex items-center justify-between hover:bg-white/40 rounded-2xl px-3 transition text-left"
                                >
                                    <div>
                                        <p className="text-sm font-extrabold">
                                            {r.candidateName} <span className="text-slate-400">·</span>{" "}
                                            <span className="text-slate-700">{r.jobTitle}</span>
                                        </p>
                                        <p className="text-[11px] text-slate-500 mt-1">
                                            점수 {r.score} · {r.createdAt}
                                        </p>
                                    </div>
                                    <span className={badgeForVerdict(r.verdict)}>{r.verdict}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                </section>
            </main>
        </div>
    );
}

// import React from "react";
// import { Link } from "react-router-dom";

// export default function AdminPage_yyr() {
//     const sampleThreadId = "my_new_interview_01";

//     return (
//         <div className="min-h-screen bg-gray-100 p-6">
//             <div className="max-w-4xl mx-auto space-y-6">
//                 <div className="flex items-center justify-between">
//                     <div>
//                         <h1 className="text-2xl font-extrabold text-gray-900">🛠 Admin Dashboard</h1>
//                         <p className="text-sm text-gray-500 mt-1">관리자 전용 페이지 (뼈대)</p>
//                     </div>

//                     <Link
//                         to="/interview"
//                         className="px-3 py-2 rounded-lg bg-gray-800 text-white text-sm font-bold hover:bg-black"
//                     >
//                         면접 화면으로
//                     </Link>
//                 </div>

//                 <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6 space-y-3">
//                     <h2 className="text-lg font-bold text-gray-900">빠른 링크</h2>

//                     <button
//                         type="button"
//                         onClick={() => window.open(`/result.html?session_id=1`, "_blank", "noopener,noreferrer")}
//                         className="inline-block px-4 py-2 rounded-lg bg-blue-600 text-white font-bold hover:bg-blue-700"
//                     >
//                         샘플 결과 보기(레이더)
//                     </button>

//                     <div className="text-xs text-gray-500">
//                         나중에 여기에 “최근 thread 목록”, “검색”, “통계”, “사용자별 히스토리”를 붙이면 됨.
//                     </div>
//                 </div>
//             </div>
//         </div>
//     );
// }
