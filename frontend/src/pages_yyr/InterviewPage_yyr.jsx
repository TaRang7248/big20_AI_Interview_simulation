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
    // ✅ 진행도(임시 정책): 기능 유지 + UX용
    const progress = useMemo(() => {
        if (showReport) return 100;
        const userTurns = chatLog.filter((m) => m.sender === "user").length;
        const base = isResumeUploaded ? 18 : 6;
        const inc = Math.min(userTurns * 12, 68);
        return Math.min(base + inc, 88);
    }, [chatLog, isResumeUploaded, showReport]);

    const stageLabel = useMemo(() => {
        if (showReport) return "평가/리포트";
        if (!isResumeUploaded) return "준비";
        if (isProcessing) return "AI 응답 중";
        if (chatLog.length === 0) return "첫 답변 대기";
        return "진행 중";
    }, [showReport, isResumeUploaded, isProcessing, chatLog.length]);

    const stageHint = useMemo(() => {
        if (!isResumeUploaded) return "이력서를 업로드하면 맞춤 질문이 시작돼요.";
        if (isProcessing) return "AI가 답변을 생성 중이에요. 잠시만 기다려주세요.";
        if (chatLog.length === 0) return "준비가 되면 ‘답변 시작’을 눌러 첫 답변을 진행해보세요.";
        return "답변을 시작하면 다음 질문 흐름이 이어집니다.";
    }, [isResumeUploaded, isProcessing, chatLog.length]);

    // ✅ “현재 질문” placeholder (질문 API 연결 전 임시)
    const currentQuestion = useMemo(() => {
        if (!isResumeUploaded) return "이력서를 업로드하면 맞춤 질문이 시작돼요.";
        return "자기소개를 30초~1분으로 해주세요.";
    }, [isResumeUploaded]);

    return (
        <div className="min-h-screen font-sans bg-gradient-to-b from-sky-50 via-white to-indigo-50">
            {/* Top bar */}
            <div className="sticky top-0 z-40 border-b border-sky-100/70 bg-white/70 backdrop-blur">
                <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between gap-4">
                    <div className="min-w-0">
                        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 leading-tight">
                            AI Interview Simulation
                        </h1>
                        <p className="text-sm text-slate-500 mt-1">
                            카메라를 보고 질문에 답해보세요.
                        </p>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full border border-sky-100 bg-white shadow-sm">
                            <span
                                className={[
                                    "w-2 h-2 rounded-full",
                                    stageLabel === "진행 중"
                                        ? "bg-emerald-500 animate-pulse"
                                        : stageLabel === "AI 응답 중"
                                            ? "bg-amber-500 animate-pulse"
                                            : stageLabel === "평가/리포트"
                                                ? "bg-violet-500 animate-pulse"
                                                : "bg-slate-300",
                                ].join(" ")}
                            />
                            <span className="text-xs font-semibold text-slate-700">{stageLabel}</span>
                        </div>

                        <button
                            onClick={onLogout}
                            className="px-3 py-2 rounded-xl bg-slate-900 text-white text-sm font-bold hover:bg-black transition"
                        >
                            로그아웃
                        </button>
                    </div>
                </div>

                {/* Progress card */}
                <div className="max-w-6xl mx-auto px-4 pb-5">
                    <div className="rounded-2xl border border-sky-100 bg-white shadow-sm px-4 py-3">
                        <div className="flex items-center justify-between gap-4">
                            <div className="min-w-0">
                                <p className="text-[11px] text-slate-500">
                                    thread_id:{" "}
                                    <span className="font-mono text-slate-700">
                                        {sessionId ?? "준비 중..."}
                                    </span>
                                </p>
                                <p className="text-sm font-semibold text-slate-800 mt-1">
                                    {stageHint}
                                </p>
                            </div>

                            <div className="shrink-0 text-right">
                                <p className="text-[11px] text-slate-500">면접 진행도</p>
                                <p className="text-xl font-extrabold text-slate-900">
                                    {progress}%
                                </p>
                            </div>
                        </div>

                        <div className="mt-3 w-full h-2.5 rounded-full bg-sky-100 overflow-hidden">
                            <div
                                className="h-full rounded-full bg-gradient-to-r from-sky-500 to-violet-500 transition-all"
                                style={{ width: `${progress}%` }}
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* Body */}
            <main className="max-w-6xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* LEFT */}
                <section className="space-y-5">
                    <div className="bg-white rounded-3xl shadow-sm border border-sky-100 overflow-hidden">
                        <div className="p-4 flex items-center justify-between">
                            <div>
                                <h2 className="text-base font-extrabold text-slate-900">Live</h2>
                                <p className="text-xs text-slate-500 mt-1">
                                    카메라/표정 분석은 자동으로 진행돼요
                                </p>
                            </div>

                            {/* ✅ 절제 그라데이션 포인트: LIVE 뱃지 */}
                            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-white text-xs font-bold bg-gradient-to-r from-sky-500 to-violet-500 shadow-sm">
                                <span className="w-2 h-2 rounded-full bg-white/90 animate-pulse" />
                                LIVE
                            </span>
                        </div>

                        <div className="px-4 pb-4">
                            <WebcamView onVideoFrame={onVideoFrame} isProcessing={isProcessing} />
                        </div>

                        <div className="px-4 pb-4 grid grid-cols-2 gap-3">
                            <div className="rounded-2xl border border-sky-100 bg-sky-50/60 p-4">
                                <p className="text-xs font-semibold text-slate-500">Vision</p>
                                <p className="mt-1 text-lg font-extrabold text-slate-900">
                                    {visionResult}
                                </p>
                                <p className="text-[11px] text-slate-500 mt-1">
                                    {visionResult === "분석 대기 중..."
                                        ? "카메라가 연결되면 자동 분석됩니다."
                                        : "실시간 표정 정보를 참고합니다."}
                                </p>
                            </div>

                            <div className="rounded-2xl border border-sky-100 bg-sky-50/60 p-4">
                                <p className="text-xs font-semibold text-slate-500">Resume</p>
                                {!isResumeUploaded ? (
                                    <>
                                        <p className="mt-1 text-lg font-extrabold text-slate-900">미등록</p>
                                        <p className="text-[11px] text-slate-500 mt-1">
                                            PDF 업로드 후 맞춤 질문이 시작돼요.
                                        </p>
                                    </>
                                ) : (
                                    <>
                                        <p className="mt-1 text-lg font-extrabold text-slate-900">완료</p>
                                        <p className="text-[11px] text-slate-500 mt-1">
                                            AI가 이력서를 반영해 질문을 만들어요.
                                        </p>
                                    </>
                                )}
                            </div>
                        </div>

                        <div className="px-4 pb-5">
                            {!isResumeUploaded ? (
                                <label className="flex items-center justify-between w-full px-4 py-4 rounded-2xl border border-sky-100 bg-white hover:bg-sky-50/40 cursor-pointer transition">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-2xl bg-slate-900 text-white flex items-center justify-center">
                                            <FaFileUpload />
                                        </div>
                                        <div>
                                            <p className="text-sm font-extrabold text-slate-900">PDF 이력서 업로드</p>
                                            <p className="text-xs text-slate-500 mt-0.5">맞춤 질문을 위해 필요해요</p>
                                        </div>
                                    </div>
                                    <span className="text-xs font-bold text-slate-900">업로드</span>
                                    <input type="file" className="hidden" accept=".pdf" onChange={onFileUpload} />
                                </label>
                            ) : (
                                <div className="flex items-center gap-3 px-4 py-4 rounded-2xl border border-emerald-200 bg-emerald-50 text-emerald-800">
                                    <FaCheckCircle className="text-xl" />
                                    <div>
                                        <p className="text-sm font-extrabold">이력서 분석 완료</p>
                                        <p className="text-xs text-emerald-700 mt-0.5">이제 면접을 진행해보세요</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </section>

                {/* RIGHT */}
                <section className="bg-white rounded-3xl shadow-sm border border-sky-100 p-6 flex flex-col min-h-[760px]">
                    {/* Question card */}
                    <div className="rounded-2xl border border-sky-100 bg-sky-50/60 p-4">
                        <div className="flex items-start justify-between gap-4">
                            <div className="min-w-0">
                                <p className="text-[11px] font-semibold text-slate-500">현재 질문</p>
                                <h2 className="mt-1 text-lg sm:text-xl font-extrabold text-slate-900 leading-snug">
                                    {currentQuestion}
                                </h2>
                                <p className="text-xs text-slate-500 mt-2">
                                    {isResumeUploaded
                                        ? "준비가 되면 아래에서 답변을 시작해보세요."
                                        : "이력서 업로드 후 맞춤 질문이 자동 생성됩니다."}
                                </p>
                            </div>

                            {/* ✅ 절제 그라데이션 포인트: 결과 보기 버튼 */}
                            <button
                                onClick={onEndInterview}
                                className="shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-xl text-white text-sm font-extrabold bg-gradient-to-r from-sky-500 to-violet-500 hover:from-sky-600 hover:to-violet-600 transition shadow-sm"
                            >
                                <FaChartBar />
                                결과 보기
                            </button>
                        </div>
                    </div>

                    {/* Chat */}
                    <div className="mt-5 flex-1 overflow-y-auto pr-2 space-y-3">
                        {chatLog.length === 0 ? (
                            <div className="mt-14 text-center text-slate-400">
                                <p className="text-sm">
                                    준비가 되시면 이력서를 업로드하고<br />
                                    <span className="font-semibold text-slate-500">[답변 시작]</span>을 눌러주세요.
                                </p>
                            </div>
                        ) : (
                            chatLog.map((msg, idx) => (
                                <div
                                    key={idx}
                                    className={`flex ${msg.sender === "user"
                                            ? "justify-end"
                                            : msg.sender === "system"
                                                ? "justify-center"
                                                : "justify-start"
                                        }`}
                                >
                                    <div
                                        className={`max-w-[86%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${msg.sender === "user"
                                                ? "bg-slate-900 text-white rounded-tr-md"
                                                : msg.sender === "system"
                                                    ? "bg-emerald-50 text-emerald-800 border border-emerald-100 text-xs py-2"
                                                    : "bg-sky-50/60 text-slate-900 border border-sky-100 rounded-tl-md"
                                            }`}
                                    >
                                        {msg.text}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>

                    {/* Action bar */}
                    <div className="pt-5 mt-5 border-t border-sky-100">
                        <div className="flex items-center justify-between gap-3 mb-3">
                            <p className="text-xs text-slate-500">
                                {isProcessing
                                    ? "AI가 응답을 생성 중입니다. 잠시만 기다려주세요."
                                    : "버튼을 눌러 답변을 녹음하세요."}
                            </p>
                            <span className="text-xs font-semibold text-slate-700">
                                {isProcessing ? "Processing" : "Ready"}
                            </span>
                        </div>

                        <AudioRecorder onAudioSubmit={onAudioSubmit} isProcessing={isProcessing} />
                        <audio ref={audioPlayerRef} hidden />
                    </div>
                </section>
            </main>

            {/* Report modal */}
            {showReport && (
                <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto border border-sky-100">
                        <div className="p-6 border-b border-sky-100 flex justify-between items-center sticky top-0 bg-white z-10">
                            <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900">
                                📊 면접 분석 리포트
                            </h2>
                            <button
                                onClick={() => setShowReport(false)}
                                className="text-slate-400 hover:text-slate-600"
                                aria-label="Close"
                            >
                                <FaTimes size={22} />
                            </button>
                        </div>

                        <div className="p-6">
                            {loadingReport ? (
                                <div className="text-center py-20">
                                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-sky-500 mx-auto mb-4" />
                                    <p className="text-slate-500">AI가 면접관들의 평가를 취합 중입니다...</p>
                                </div>
                            ) : reportData ? (
                                <ResultPage_yyr reportData={reportData} />
                            ) : (
                                <p className="text-center text-red-500">데이터를 불러오지 못했습니다.</p>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}