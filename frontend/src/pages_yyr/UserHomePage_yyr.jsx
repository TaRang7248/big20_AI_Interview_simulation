// src/pages_yyr/UserHomePage_yyr.jsx
import React from "react";
import { FaFileUpload, FaCheckCircle, FaPlay, FaTools } from "react-icons/fa";

export default function UserHomePage_yyr({
    sessionId,
    interviewPhase, // "lobby" | "ready" | "live" | "report"
    isResumeUploaded,
    onFileUpload,
    onStartInterview,
    onLogout,
}) {
    const glass =
        "bg-white/55 backdrop-blur-xl border border-white/60 shadow-[0_20px_40px_-20px_rgba(0,0,0,0.15)] rounded-3xl";

    const canStart = isResumeUploaded; // MVP 기준: 이력서 업로드 완료하면 시작 가능

    return (
        <div className="min-h-screen bg-gradient-to-b from-sky-50 via-white to-indigo-50 text-slate-900">
            {/* Header */}
            <header className="sticky top-0 z-40 backdrop-blur-xl bg-white/60 border-b border-white/60">
                <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-sky-500 to-violet-500" />
                        <div>
                            <h1 className="text-sm font-extrabold">AI Interview</h1>
                            <p className="text-[11px] text-slate-500">
                                면접 시작 전(로비) — 공고 선택 / 이력서 업로드 / 환경 테스트
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <span className="text-xs font-semibold text-slate-700">
                            Phase: {String(interviewPhase).toUpperCase()}
                        </span>
                        <button
                            onClick={onLogout}
                            className="px-3 py-2 rounded-xl bg-slate-900 text-white text-sm font-bold"
                        >
                            로그아웃
                        </button>
                    </div>
                </div>
            </header>

            <main className="max-w-6xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left */}
                <section className="lg:col-span-7 space-y-6">
                    {/* 2.1-1 이전 면접 기록 조회 (MVP: 자리만) */}
                    <div className={`${glass} p-6`}>
                        <p className="text-xs text-slate-500 font-semibold">History</p>
                        <p className="text-base font-extrabold mt-1">이전 면접 기록</p>
                        <p className="text-sm text-slate-500 mt-2">
                            (MVP) 합/불합 + 간단 요약 리스트 영역. 나중에 API 연결.
                        </p>
                    </div>

                    {/* 2.1-2 지원 공고 선택 (MVP: 자리만) */}
                    <div className={`${glass} p-6`}>
                        <p className="text-xs text-slate-500 font-semibold">Job</p>
                        <p className="text-base font-extrabold mt-1">지원 공고 선택</p>
                        <p className="text-sm text-slate-500 mt-2">
                            (MVP) 공고 리스트/검색 영역. 선택된 공고가 면접 세션과 연결될 예정.
                        </p>
                    </div>
                </section>

                {/* Right */}
                <section className="lg:col-span-5 space-y-6">
                    {/* 2.1-3 이력서 업로드 */}
                    <div className={`${glass} p-6`}>
                        <p className="text-xs text-slate-500 font-semibold">Resume</p>
                        <p className="text-base font-extrabold mt-1">PDF 이력서 업로드</p>

                        <p className="text-[12px] text-slate-500 mt-2">
                            sessionId: <b>{sessionId ?? "(발급 중...)"}</b>
                        </p>

                        <div className="mt-4">
                            {!isResumeUploaded ? (
                                <label className="inline-flex items-center gap-2 px-4 py-2 rounded-2xl cursor-pointer text-white text-sm font-bold bg-gradient-to-r from-sky-500 to-violet-500">
                                    <FaFileUpload />
                                    업로드
                                    <input type="file" hidden accept=".pdf" onChange={onFileUpload} />
                                </label>
                            ) : (
                                <span className="inline-flex items-center gap-2 px-4 py-2 rounded-2xl bg-emerald-50 text-emerald-700 font-bold">
                                    <FaCheckCircle />
                                    업로드 완료
                                </span>
                            )}
                        </div>
                    </div>

                    {/* 2.1-4 면접 환경 테스트 (MVP: 안내만) */}
                    <div className={`${glass} p-6`}>
                        <p className="text-xs text-slate-500 font-semibold">Environment</p>
                        <p className="text-base font-extrabold mt-1">면접 환경 테스트</p>
                        <div className="mt-3 text-sm text-slate-500 flex items-start gap-2">
                            <FaTools className="mt-1" />
                            <div>
                                카메라/마이크/네트워크 상태 확인 영역 (MVP는 안내만).
                                <br />
                                실제 테스트 UI는 다음 단계에서 붙여도 OK.
                            </div>
                        </div>
                    </div>

                    {/* 면접 시작 */}
                    <div className={`${glass} p-6`}>
                        <p className="text-xs text-slate-500 font-semibold">Start</p>
                        <p className="text-base font-extrabold mt-1">면접 시작</p>
                        <button
                            onClick={onStartInterview}
                            disabled={!canStart}
                            className={`mt-4 w-full inline-flex items-center justify-center gap-2 px-4 py-3 rounded-2xl text-sm font-extrabold transition
                ${canStart
                                    ? "text-white bg-gradient-to-r from-sky-500 to-violet-500 hover:opacity-95"
                                    : "bg-slate-200 text-slate-500 cursor-not-allowed"
                                }`}
                        >
                            <FaPlay />
                            면접 시작
                        </button>

                        {!canStart && (
                            <p className="text-xs text-slate-500 mt-2">
                                이력서 업로드가 완료되면 면접을 시작할 수 있어요.
                            </p>
                        )}
                    </div>
                </section>
            </main>
        </div>
    );
}