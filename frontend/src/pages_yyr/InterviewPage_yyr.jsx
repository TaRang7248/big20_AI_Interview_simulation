// src/pages_yyr/InterviewPage_yyr.jsx
import React, { useMemo } from "react";
import { FaFileUpload, FaCheckCircle, FaChartBar, FaTimes } from "react-icons/fa";

import WebcamView from "../components/WebcamView";
import AudioRecorder from "../components/AudioRecorder";
import ResultPage_yyr from "./ResultPage_yyr";

export default function InterviewPage_yyr({
    sessionId,
    visionResult,
    chatLog,
    isProcessing,
    isResumeUploaded,

    interviewPhase,
    onStartInterview,

    onLogout,
    onFileUpload,
    onAudioSubmit,
    onEndInterview,
    onVideoFrame,

    showReport,
    setShowReport,
    reportData,
    loadingReport,

    audioPlayerRef,
}) {
    /* =========================
       진행도 계산
    ========================= */
    const progress = useMemo(() => {
        if (showReport) return 100;
        const userTurns = chatLog.filter((m) => m.sender === "user").length;
        const base = isResumeUploaded ? 22 : 10;
        const inc = Math.min(userTurns * 12, 68);
        return Math.min(base + inc, 92);
    }, [chatLog, isResumeUploaded, showReport]);

    const stageLabel = useMemo(() => {
        if (showReport) return "리포트";
        if (!isResumeUploaded) return "준비";
        if (isProcessing) return "AI 응답";
        if (chatLog.length === 0) return "대기";
        return "진행";
    }, [showReport, isResumeUploaded, isProcessing, chatLog.length]);

    const currentQuestion = useMemo(() => {
        if (!isResumeUploaded) return "이력서를 업로드하면 맞춤 질문이 시작돼요.";
        return "자기소개를 30초~1분으로 해주세요.";
    }, [isResumeUploaded]);

    const hint = useMemo(() => {
        if (!isResumeUploaded) return "PDF 업로드 후, 맞춤 질문이 자동 생성됩니다.";
        if (isProcessing) return "AI가 답변을 생성 중입니다.";
        return "준비가 되면 아래에서 답변을 녹음하세요.";
    }, [isResumeUploaded, isProcessing]);

    /* =========================
       공통 스타일
    ========================= */
    const glass =
        "bg-white/55 backdrop-blur-xl border border-white/60 shadow-[0_20px_40px_-20px_rgba(0,0,0,0.15)] rounded-3xl";

    return (
        <div className="min-h-screen bg-gradient-to-b from-sky-50 via-white to-indigo-50 text-slate-900">

            {/* =========================
                Glass Header
            ========================= */}
            <header className="sticky top-0 z-40 backdrop-blur-xl bg-white/60 border-b border-white/60">
                <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-sky-500 to-violet-500" />
                        <div>
                            <h1 className="text-sm font-extrabold">AI Interview</h1>
                            <p className="text-[11px] text-slate-500">{hint}</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <span className="text-xs font-semibold text-slate-700">
                            진행도 {progress}%
                        </span>
                        <button
                            onClick={onLogout}
                            className="px-3 py-2 rounded-xl bg-slate-900 text-white text-sm font-bold"
                        >
                            로그아웃
                        </button>
                    </div>
                </div>

                <div className="max-w-6xl mx-auto px-4 pb-3">
                    <div className="h-2 rounded-full bg-sky-100 overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-sky-500 to-violet-500 transition-all"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                </div>
            </header>

            {/* =========================
                Main Layout
            ========================= */}
            <main className="max-w-6xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-12 gap-6">

                {/* ================= LEFT */}
                <section className="lg:col-span-5 space-y-4">

                    {/* Camera Card */}
                    <div className={`${glass}`}>
                        <div className="px-5 py-4 flex justify-between items-center">
                            <div>
                                <p className="text-xs text-slate-500 font-semibold">Live</p>
                                <p className="text-sm font-extrabold">면접 화면</p>
                            </div>

                            {interviewPhase === "live" ? (
                                <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-600 text-white text-xs font-bold">
                                    <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                                    LIVE
                                </span>
                            ) : (
                                <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-200 text-slate-800 text-xs font-bold">
                                    READY
                                </span>
                            )}
                        </div>

                        <div className="px-5 pb-5">
                            {interviewPhase === "live" ? (
                                <WebcamView onVideoFrame={onVideoFrame} isProcessing={isProcessing} />
                            ) : (
                                <div className="h-[260px] rounded-2xl bg-slate-900 text-white flex items-center justify-center text-center px-6">
                                    <p className="text-sm font-bold opacity-90">
                                        {interviewPhase === "lobby"
                                            ? "면접 시작 전입니다. 이력서를 업로드하고 ‘면접 시작’을 눌러주세요."
                                            : "준비 완료! ‘면접 시작’을 누르면 카메라/마이크가 활성화됩니다."}
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Status Chips */}
                    <div className="flex flex-wrap gap-2">
                        <span className="px-3 py-2 rounded-full text-xs font-semibold bg-white/70 border border-white/60">
                            Vision: <b>{visionResult}</b>
                        </span>
                        <span className="px-3 py-2 rounded-full text-xs font-semibold bg-white/70 border border-white/60">
                            Resume: <b>{isResumeUploaded ? "완료" : "미등록"}</b>
                        </span>
                        <span className="px-3 py-2 rounded-full text-xs font-semibold bg-white/70 border border-white/60">
                            Status: <b>{isProcessing ? "Processing" : "Ready"}</b>
                        </span>
                    </div>

                    {/* Resume Upload */}
                    <div className={`${glass} p-5`}>
                        <p className="text-xs text-slate-500 font-semibold">Resume</p>
                        <p className="text-base font-extrabold mt-1">
                            PDF 이력서 업로드
                        </p>

                        <div className="mt-3">
                            {!isResumeUploaded ? (
                                <label className="inline-flex items-center gap-2 px-4 py-2 rounded-2xl cursor-pointer text-white text-sm font-bold bg-gradient-to-r from-sky-500 to-violet-500">
                                    <FaFileUpload />
                                    업로드
                                    <input type="file" hidden accept=".pdf" onChange={onFileUpload} />
                                </label>
                            ) : (
                                <span className="inline-flex items-center gap-2 px-4 py-2 rounded-2xl bg-emerald-50 text-emerald-700 font-bold">
                                    <FaCheckCircle />
                                    완료
                                </span>
                            )}
                        </div>
                    </div>
                </section>

                {/* ================= RIGHT */}
                <section className="lg:col-span-7">
                    <div
                        className={`${glass} flex flex-col h-[calc(100vh-190px)] min-h-[520px]`}
                    >
                        {/* Question Header */}
                        <div className="px-6 py-5 border-b border-white/60">
                            <div className="flex justify-between gap-4">
                                <div>
                                    <p className="text-[11px] text-slate-500 font-semibold">
                                        현재 질문
                                    </p>
                                    <h2 className="mt-1 text-xl font-extrabold">
                                        {currentQuestion}
                                    </h2>
                                </div>

                                <button
                                    onClick={onEndInterview}
                                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-white text-sm font-bold bg-gradient-to-r from-sky-500 to-violet-500"
                                >
                                    <FaChartBar />
                                    결과 보기
                                </button>
                            </div>
                        </div>

                        {/* Timeline */}
                        <div className="flex-1 px-6 py-5 overflow-y-auto">
                            {chatLog.length === 0 ? (
                                <div className="h-full flex items-center justify-center text-center">
                                    <div className="space-y-3">
                                        <span className="inline-flex px-3 py-1 rounded-full text-xs font-bold bg-white/70 border border-white/60">
                                            질문 대기
                                        </span>
                                        <p className="text-sm text-slate-500">
                                            준비가 되면 이력서를 업로드하고<br />
                                            <b>[면접 시작]</b>을 눌러주세요.
                                        </p>
                                    </div>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {chatLog.map((msg, idx) => (
                                        <div key={idx} className="flex gap-3">
                                            <div className="w-7 h-7 rounded-xl flex items-center justify-center text-xs font-bold bg-slate-900 text-white">
                                                {msg.sender === "user" ? "U" : "A"}
                                            </div>
                                            <div className="px-4 py-3 rounded-2xl bg-white/70 border border-white/60 text-sm">
                                                {msg.text}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Action */}
                        <div className="px-6 py-5 border-t border-white/60">
                            {interviewPhase === "live" ? (
                                <>
                                    <AudioRecorder onTextSubmit={onAudioSubmit} isProcessing={isProcessing} />
                                    <audio ref={audioPlayerRef} hidden />
                                </>
                            ) : (
                                <div className="flex items-center justify-center">
                                    <button
                                        onClick={onStartInterview}
                                        disabled={!isResumeUploaded}
                                        className={`px-6 py-4 rounded-2xl text-white font-extrabold text-lg
          ${isResumeUploaded
                                                ? "bg-gradient-to-r from-sky-500 to-violet-500 hover:opacity-95"
                                                : "bg-slate-300 cursor-not-allowed"
                                            }`}
                                    >
                                        면접 시작
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </section>
            </main>

            {/* ================= Report Modal */}
            {showReport && (
                <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-3xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
                        <div className="p-6 border-b flex justify-between items-center">
                            <h2 className="text-xl font-extrabold">📊 면접 분석 리포트</h2>
                            <button onClick={() => setShowReport(false)}>
                                <FaTimes />
                            </button>
                        </div>
                        <div className="p-6">
                            {loadingReport ? (
                                <p className="text-center text-slate-500">리포트 생성 중…</p>
                            ) : (
                                <ResultPage_yyr reportData={reportData} />
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}