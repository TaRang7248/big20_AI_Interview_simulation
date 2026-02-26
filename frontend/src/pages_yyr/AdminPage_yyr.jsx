import React, { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FaBriefcase, FaUsers, FaChartLine, FaArrowRight, FaRegClock, FaSignOutAlt } from "react-icons/fa";

export default function AdminPage_yyr() {
    const nav = useNavigate();
    const handleLogout = () => {
        // App.jsx랑 동일한 방식
        localStorage.removeItem("auth_token");
        localStorage.removeItem("role");
        nav("/login", { replace: true });
    };

    // ✅ 더미 데이터(지금은 구조만 잡기)
    const jobs = useMemo(
        () => [
            {
                jobId: "JOB-001",
                title: "백엔드 개발자 (FastAPI)",
                status: "모집중", // 모집중 | 마감 | 임시저장
                applicants: 12,
                updatedAt: "2026-02-25",
            },
            {
                jobId: "JOB-002",
                title: "데이터 분석가 (SQL/BI)",
                status: "모집중",
                applicants: 7,
                updatedAt: "2026-02-24",
            },
            {
                jobId: "JOB-003",
                title: "프론트엔드 개발자 (React)",
                status: "마감",
                applicants: 21,
                updatedAt: "2026-02-20",
            },
        ],
        []
    );

    const interviews = useMemo(
        () => [
            {
                threadId: "my_new_interview_01",
                applicantName: "지원자 A",
                jobTitle: "백엔드 개발자 (FastAPI)",
                score: 86,
                result: "PASS", // PASS | FAIL
                createdAt: "2026-02-07 06:29",
                status: "완료", // 진행중 | 완료
            },
            {
                threadId: "my_new_interview_02",
                applicantName: "지원자 B",
                jobTitle: "데이터 분석가 (SQL/BI)",
                score: 74,
                result: "FAIL",
                createdAt: "2026-02-08 14:10",
                status: "완료",
            },
            {
                threadId: "my_new_interview_03",
                applicantName: "지원자 C",
                jobTitle: "백엔드 개발자 (FastAPI)",
                score: null,
                result: null,
                createdAt: "2026-02-25 09:40",
                status: "진행중",
            },
        ],
        []
    );

    const stats = useMemo(() => {
        const openJobs = jobs.filter((j) => j.status === "모집중").length;
        const closedJobs = jobs.filter((j) => j.status === "마감").length;
        const totalApplicants = jobs.reduce((sum, j) => sum + j.applicants, 0);
        const completed = interviews.filter((i) => i.status === "완료").length;
        return { openJobs, closedJobs, totalApplicants, completed };
    }, [jobs, interviews]);

    const badge = (status) => {
        const base = "inline-flex items-center px-2 py-1 rounded-lg text-xs font-extrabold border";
        if (status === "모집중") return `${base} bg-emerald-50 text-emerald-700 border-emerald-200`;
        if (status === "마감") return `${base} bg-slate-100 text-slate-700 border-slate-200`;
        return `${base} bg-amber-50 text-amber-800 border-amber-200`;
    };

    const glass =
        "bg-white/70 backdrop-blur-xl border border-white/60 shadow-[0_20px_40px_-20px_rgba(0,0,0,0.15)] rounded-3xl";

    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-indigo-50 text-slate-900">
            {/* Header */}
            <header className="sticky top-0 z-40 backdrop-blur-xl bg-white/60 border-b border-white/60">
                <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-slate-900 to-indigo-600" />
                        <div>
                            <h1 className="text-sm font-extrabold">Admin Dashboard</h1>
                            <p className="text-[11px] text-slate-500">공고 상태 / 지원자 현황 / 면접 결과(관리자용)</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => alert("TODO: 관리자 화면에서는 면접 화면으로 이동하지 않음")}
                            className="px-3 py-2 rounded-xl bg-slate-900 text-white text-sm font-bold"
                        >
                            면접 화면으로
                        </button>

                        <button
                            onClick={handleLogout}
                            className="px-3 py-2 rounded-xl bg-white/70 border border-white/60 hover:bg-white transition text-sm font-bold"
                        >
                            {/* 아이콘 쓰면: <FaSignOutAlt className="inline -mt-[2px] mr-2" /> */}
                            로그아웃
                        </button>
                    </div>
                </div>
            </header>

            <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
                {/* Top stats */}
                <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className={`${glass} p-5`}>
                        <div className="flex items-center justify-between">
                            <p className="text-xs text-slate-500 font-semibold">Open Jobs</p>
                            <FaBriefcase />
                        </div>
                        <p className="text-2xl font-extrabold mt-2">{stats.openJobs}</p>
                        <p className="text-xs text-slate-500 mt-1">모집중 공고</p>
                    </div>

                    <div className={`${glass} p-5`}>
                        <div className="flex items-center justify-between">
                            <p className="text-xs text-slate-500 font-semibold">Closed Jobs</p>
                            <FaBriefcase />
                        </div>
                        <p className="text-2xl font-extrabold mt-2">{stats.closedJobs}</p>
                        <p className="text-xs text-slate-500 mt-1">마감 공고</p>
                    </div>

                    <div className={`${glass} p-5`}>
                        <div className="flex items-center justify-between">
                            <p className="text-xs text-slate-500 font-semibold">Applicants</p>
                            <FaUsers />
                        </div>
                        <p className="text-2xl font-extrabold mt-2">{stats.totalApplicants}</p>
                        <p className="text-xs text-slate-500 mt-1">총 지원자 수(더미)</p>
                    </div>

                    <div className={`${glass} p-5`}>
                        <div className="flex items-center justify-between">
                            <p className="text-xs text-slate-500 font-semibold">Completed</p>
                            <FaChartLine />
                        </div>
                        <p className="text-2xl font-extrabold mt-2">{stats.completed}</p>
                        <p className="text-xs text-slate-500 mt-1">완료된 면접(더미)</p>
                    </div>
                </section>

                {/* Main blocks */}
                <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                    {/* Jobs */}
                    <div className={`lg:col-span-7 ${glass} p-6`}>
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-xs text-slate-500 font-semibold">Jobs</p>
                                <p className="text-base font-extrabold mt-1">공고 상태</p>
                                <p className="text-sm text-slate-500 mt-2">
                                    (지금은 더미) 나중에 여기서 공고 생성/수정/마감까지 확장
                                </p>
                            </div>
                            <button
                                type="button"
                                className="px-3 py-2 rounded-xl bg-white/70 border border-white/60 hover:bg-white transition text-sm font-bold"
                                onClick={() => alert("다음 단계: 공고 관리 페이지(/admin/jobs) 뼈대 추가")}
                            >
                                + 공고 관리
                            </button>
                        </div>

                        <div className="mt-5 overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="text-left text-slate-500">
                                        <th className="py-2 pr-3">상태</th>
                                        <th className="py-2 pr-3">공고</th>
                                        <th className="py-2 pr-3">지원자</th>
                                        <th className="py-2 pr-3">업데이트</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {jobs.map((j) => (
                                        <tr key={j.jobId} className="border-t border-white/60">
                                            <td className="py-3 pr-3">
                                                <span className={badge(j.status)}>{j.status}</span>
                                            </td>
                                            <td className="py-3 pr-3">
                                                <div className="font-bold text-slate-900">{j.title}</div>
                                                <div className="text-xs text-slate-500">{j.jobId}</div>
                                            </td>
                                            <td className="py-3 pr-3 font-bold">{j.applicants}</td>
                                            <td className="py-3 pr-3 text-slate-600">{j.updatedAt}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Interviews */}
                    <div className={`lg:col-span-5 ${glass} p-6`}>
                        <p className="text-xs text-slate-500 font-semibold">Interviews</p>
                        <p className="text-base font-extrabold mt-1">최근 면접 결과</p>
                        <p className="text-sm text-slate-500 mt-2">
                            (지금은 더미) “관리자 결과 페이지(/admin/result/:threadId)”로 연결
                        </p>

                        <div className="mt-5 space-y-3">
                            {interviews.map((i) => (
                                <div
                                    key={i.threadId}
                                    className="bg-white/70 border border-white/60 rounded-2xl p-4 hover:bg-white transition"
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <div>
                                            <div className="text-sm font-extrabold">
                                                {i.applicantName} · {i.jobTitle}
                                            </div>
                                            <div className="text-xs text-slate-500 mt-1 flex items-center gap-2">
                                                <FaRegClock />
                                                {i.createdAt} · {i.status}
                                            </div>
                                        </div>

                                        <div className="text-right">
                                            {i.score == null ? (
                                                <div className="text-xs font-bold text-slate-500">진행중</div>
                                            ) : (
                                                <div className="text-sm font-extrabold">
                                                    {i.score}점{" "}
                                                    <span className={i.result === "PASS" ? "text-emerald-600" : "text-rose-600"}>
                                                        {i.result}
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div className="mt-3 flex items-center justify-between">
                                        <div className="text-xs text-slate-500">thread_id: {i.threadId}</div>

                                        {i.threadId === "my_new_interview_01" ? (
                                            <Link
                                                to={`/admin/result/${i.threadId}`}
                                                className="inline-flex items-center gap-2 text-sm font-extrabold text-indigo-700 hover:underline"
                                            >
                                                결과 보기 <FaArrowRight />
                                            </Link>
                                        ) : (
                                            <span className="text-xs font-bold text-slate-400">결과 없음</span>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="mt-5 text-xs text-slate-500">
                            다음 단계: “면접 리스트/검색/필터/통계”를 이 블록 아래로 확장
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
