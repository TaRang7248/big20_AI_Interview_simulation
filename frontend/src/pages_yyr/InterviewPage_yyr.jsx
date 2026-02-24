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

                            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-600 text-white text-xs font-bold">
                                <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                                LIVE
                            </span>
                        </div>

                        <div className="px-5 pb-5">
                            <WebcamView onVideoFrame={onVideoFrame} isProcessing={isProcessing} />
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
                                            <b>[답변 시작]</b>을 눌러주세요.
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
                            <AudioRecorder onAudioSubmit={onAudioSubmit} isProcessing={isProcessing} />
                            <audio ref={audioPlayerRef} hidden />
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

// 세번째 ?

// src/pages_yyr/InterviewPage_yyr.jsx
// import React, { useMemo } from "react";
// import { FaFileUpload, FaCheckCircle, FaChartBar, FaTimes } from "react-icons/fa";

// import WebcamView from "../components/WebcamView";
// import AudioRecorder from "../components/AudioRecorder";
// import ResultPage_yyr from "./ResultPage_yyr";

// export default function InterviewPage_yyr({
//     sessionId,
//     visionResult,
//     chatLog,
//     isProcessing,
//     isResumeUploaded,

//     onLogout,
//     onFileUpload,
//     onAudioSubmit,
//     onEndInterview,
//     onVideoFrame,

//     showReport,
//     setShowReport,
//     reportData,
//     loadingReport,

//     audioPlayerRef,
// }) {
//     const progress = useMemo(() => {
//         if (showReport) return 100;
//         const userTurns = chatLog.filter((m) => m.sender === "user").length;
//         const base = isResumeUploaded ? 22 : 10;
//         const inc = Math.min(userTurns * 12, 68);
//         return Math.min(base + inc, 92);
//     }, [chatLog, isResumeUploaded, showReport]);

//     const stageLabel = useMemo(() => {
//         if (showReport) return "리포트";
//         if (!isResumeUploaded) return "준비";
//         if (isProcessing) return "AI 응답";
//         if (chatLog.length === 0) return "대기";
//         return "진행";
//     }, [showReport, isResumeUploaded, isProcessing, chatLog.length]);

//     const stageDot = useMemo(() => {
//         if (stageLabel === "진행") return "bg-emerald-500";
//         if (stageLabel === "AI 응답") return "bg-amber-500";
//         if (stageLabel === "리포트") return "bg-violet-500";
//         return "bg-slate-300";
//     }, [stageLabel]);

//     const currentQuestion = useMemo(() => {
//         if (!isResumeUploaded) return "이력서를 업로드하면 맞춤 질문이 시작돼요.";
//         return "자기소개를 30초~1분으로 해주세요.";
//     }, [isResumeUploaded]);

//     const hint = useMemo(() => {
//         if (!isResumeUploaded) return "PDF 업로드 후, 맞춤 질문이 자동 생성됩니다.";
//         if (isProcessing) return "AI가 답변을 생성 중이에요. 잠시만 기다려주세요.";
//         return "준비가 되면 아래에서 답변을 녹음하세요.";
//     }, [isResumeUploaded, isProcessing]);

//     return (
//         <div className="min-h-screen bg-slate-50 text-slate-900">
//             {/* ✅ Top bar (대시보드형) */}
//             <div className="sticky top-0 z-50 bg-white border-b border-slate-200">
//                 <div className="max-w-[1400px] mx-auto px-4 py-3 flex items-center justify-between">
//                     <div className="flex items-center gap-3 min-w-0">
//                         <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-sky-500 to-violet-500" />
//                         <div className="min-w-0">
//                             <h1 className="text-sm sm:text-base font-extrabold truncate">AI Interview Dashboard</h1>
//                             <p className="text-[11px] text-slate-500 truncate">{hint}</p>
//                         </div>
//                     </div>

//                     <div className="flex items-center gap-2">
//                         <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full border border-slate-200 bg-white">
//                             <span className={`w-2 h-2 rounded-full ${stageDot} ${stageLabel !== "준비" ? "animate-pulse" : ""}`} />
//                             <span className="text-xs font-semibold text-slate-700">{stageLabel}</span>
//                             <span className="text-xs text-slate-400">·</span>
//                             <span className="text-xs font-extrabold text-slate-900">{progress}%</span>
//                         </div>

//                         <button
//                             onClick={onLogout}
//                             className="px-3 py-2 rounded-xl bg-slate-900 text-white text-sm font-bold hover:bg-black transition"
//                         >
//                             로그아웃
//                         </button>
//                     </div>
//                 </div>

//                 {/* thin progress */}
//                 <div className="max-w-[1400px] mx-auto px-4 pb-3">
//                     <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
//                         <div
//                             className="h-full rounded-full bg-gradient-to-r from-sky-500 to-violet-500"
//                             style={{ width: `${progress}%` }}
//                         />
//                     </div>
//                 </div>
//             </div>

//             {/* ✅ 3-panel dashboard */}
//             <main className="max-w-[1400px] mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-12 gap-4">
//                 {/* LEFT SIDEBAR */}
//                 <aside className="lg:col-span-3 space-y-4">
//                     <div className="bg-white border border-slate-200 rounded-2xl p-4">
//                         <p className="text-[11px] text-slate-500">thread_id</p>
//                         <p className="font-mono text-sm text-slate-800 mt-1 break-all">
//                             {sessionId ?? "준비 중..."}
//                         </p>

//                         <div className="mt-3 flex items-center justify-between">
//                             <span className="text-xs text-slate-500">면접 진행도</span>
//                             <span className="text-sm font-extrabold text-slate-900">{progress}%</span>
//                         </div>
//                     </div>

//                     <div className="bg-white border border-slate-200 rounded-2xl p-4">
//                         <div className="flex items-start justify-between gap-3">
//                             <div>
//                                 <p className="text-xs font-semibold text-slate-500">Resume</p>
//                                 <p className="text-sm font-extrabold text-slate-900 mt-1">
//                                     {isResumeUploaded ? "업로드 완료" : "PDF 이력서 업로드"}
//                                 </p>
//                                 <p className="text-[11px] text-slate-500 mt-1">
//                                     {isResumeUploaded ? "맞춤 질문 준비 완료" : "업로드하면 질문이 정교해져요"}
//                                 </p>
//                             </div>

//                             {!isResumeUploaded ? (
//                                 <label className="shrink-0 inline-flex items-center gap-2 px-3 py-2 rounded-xl text-white text-xs font-extrabold bg-slate-900 hover:bg-black cursor-pointer transition">
//                                     <FaFileUpload />
//                                     업로드
//                                     <input type="file" className="hidden" accept=".pdf" onChange={onFileUpload} />
//                                 </label>
//                             ) : (
//                                 <div className="shrink-0 inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-100 text-xs font-extrabold">
//                                     <FaCheckCircle />
//                                     완료
//                                 </div>
//                             )}
//                         </div>
//                     </div>

//                     <div className="bg-white border border-slate-200 rounded-2xl p-4">
//                         <p className="text-xs font-semibold text-slate-500">Status</p>
//                         <div className="mt-2 flex flex-wrap gap-2">
//                             <span className="inline-flex items-center gap-2 px-3 py-2 rounded-full bg-slate-50 border border-slate-200 text-xs font-semibold">
//                                 <span className={`w-2 h-2 rounded-full ${stageDot}`} />
//                                 {stageLabel}
//                             </span>
//                             <span className="inline-flex items-center gap-2 px-3 py-2 rounded-full bg-slate-50 border border-slate-200 text-xs font-semibold">
//                                 <span className={`w-2 h-2 rounded-full ${isProcessing ? "bg-amber-500 animate-pulse" : "bg-slate-300"}`} />
//                                 {isProcessing ? "Processing" : "Ready"}
//                             </span>
//                         </div>
//                     </div>
//                 </aside>

//                 {/* CENTER MAIN */}
//                 <section className="lg:col-span-6">
//                     <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden flex flex-col min-h-[760px]">
//                         {/* Question row */}
//                         <div className="p-5 border-b border-slate-200 flex items-start justify-between gap-4">
//                             <div className="min-w-0">
//                                 <p className="text-[11px] font-semibold text-slate-500">현재 질문</p>
//                                 <h2 className="mt-1 text-xl font-extrabold text-slate-900 leading-snug">
//                                     {currentQuestion}
//                                 </h2>
//                                 <p className="text-xs text-slate-500 mt-2">{hint}</p>
//                             </div>

//                             <button
//                                 onClick={onEndInterview}
//                                 className="shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-xl text-white text-sm font-extrabold bg-gradient-to-r from-sky-500 to-violet-500 hover:from-sky-600 hover:to-violet-600 transition"
//                             >
//                                 <FaChartBar />
//                                 결과 보기
//                             </button>
//                         </div>

//                         {/* Log / Timeline */}
//                         <div className="flex-1 p-5 overflow-y-auto bg-white">
//                             {chatLog.length === 0 ? (
//                                 <div className="h-full flex items-center justify-center text-center">
//                                     <div className="max-w-md">
//                                         <div className="mx-auto w-14 h-14 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-center text-slate-800 font-extrabold">
//                                             Q
//                                         </div>
//                                         <p className="mt-4 text-sm text-slate-500">
//                                             이력서 업로드 후 <span className="font-semibold text-slate-700">[답변 시작]</span>을 눌러주세요.
//                                         </p>
//                                     </div>
//                                 </div>
//                             ) : (
//                                 <div className="space-y-3">
//                                     {chatLog.map((msg, idx) => (
//                                         <div key={idx} className="flex gap-3">
//                                             <div className="pt-1">
//                                                 <div
//                                                     className={[
//                                                         "w-8 h-8 rounded-2xl flex items-center justify-center text-xs font-extrabold border",
//                                                         msg.sender === "user"
//                                                             ? "bg-slate-900 text-white border-slate-900"
//                                                             : msg.sender === "system"
//                                                                 ? "bg-emerald-50 text-emerald-700 border-emerald-100"
//                                                                 : "bg-slate-50 text-slate-800 border-slate-200",
//                                                     ].join(" ")}
//                                                 >
//                                                     {msg.sender === "user" ? "U" : msg.sender === "system" ? "S" : "A"}
//                                                 </div>
//                                             </div>

//                                             <div className="flex-1">
//                                                 <div
//                                                     className={[
//                                                         "px-4 py-3 rounded-2xl text-sm leading-relaxed border",
//                                                         msg.sender === "user"
//                                                             ? "bg-slate-900 text-white border-slate-900"
//                                                             : msg.sender === "system"
//                                                                 ? "bg-emerald-50 text-emerald-800 border-emerald-100"
//                                                                 : "bg-slate-50 text-slate-900 border-slate-200",
//                                                     ].join(" ")}
//                                                 >
//                                                     {msg.text}
//                                                 </div>
//                                             </div>
//                                         </div>
//                                     ))}
//                                 </div>
//                             )}
//                         </div>

//                         {/* Action bar */}
//                         <div className="p-5 border-t border-slate-200 bg-white">
//                             <div className="flex items-center justify-between mb-3">
//                                 <p className="text-xs text-slate-500">
//                                     {isProcessing ? "AI 응답 생성 중…" : "버튼을 눌러 답변을 녹음하세요."}
//                                 </p>
//                                 <span className="text-xs font-semibold text-slate-700">
//                                     {isProcessing ? "Processing" : "Ready"}
//                                 </span>
//                             </div>

//                             <AudioRecorder onAudioSubmit={onAudioSubmit} isProcessing={isProcessing} />
//                             <audio ref={audioPlayerRef} hidden />
//                         </div>
//                     </div>
//                 </section>

//                 {/* RIGHT INSPECTOR (camera small) */}
//                 <aside className="lg:col-span-3 space-y-4">
//                     <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
//                         <div className="p-4 flex items-center justify-between">
//                             <div>
//                                 <p className="text-xs font-semibold text-slate-500">Live Camera</p>
//                                 <p className="text-sm font-extrabold text-slate-900 mt-1">미리보기</p>
//                             </div>

//                             {/* 파란 위치 LIVE -> 빨강 LIVE */}
//                             <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-white text-xs font-extrabold bg-red-600 shadow-sm">
//                                 <span className="w-2 h-2 rounded-full bg-white/90 animate-pulse" />
//                                 LIVE
//                             </span>
//                         </div>

//                         <div className="px-4 pb-4">
//                             {/* ✅ 카메라 크기 작게: inspector 패널에 들어감 */}
//                             <WebcamView onVideoFrame={onVideoFrame} isProcessing={isProcessing} />
//                         </div>
//                     </div>

//                     <div className="bg-white border border-slate-200 rounded-2xl p-4">
//                         <p className="text-xs font-semibold text-slate-500">Vision</p>
//                         <p className="mt-1 text-base font-extrabold text-slate-900">{visionResult}</p>
//                         <p className="text-[11px] text-slate-500 mt-1">표정/상태 기반 참고 정보</p>
//                     </div>

//                     <div className="bg-white border border-slate-200 rounded-2xl p-4">
//                         <p className="text-xs font-semibold text-slate-500">Notes</p>
//                         <p className="text-sm text-slate-700 mt-2">
//                             - 질문/답변 로그는 중앙 타임라인에 기록됩니다.<br />
//                             - 결과 페이지는 동일한 thread_id로 공유 가능합니다.
//                         </p>
//                     </div>
//                 </aside>
//             </main>

//             {/* Report modal */}
//             {showReport && (
//                 <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
//                     <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto border border-slate-200">
//                         <div className="p-6 border-b border-slate-200 flex justify-between items-center sticky top-0 bg-white z-10">
//                             <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900">
//                                 📊 면접 분석 리포트
//                             </h2>
//                             <button
//                                 onClick={() => setShowReport(false)}
//                                 className="text-slate-400 hover:text-slate-600"
//                                 aria-label="Close"
//                             >
//                                 <FaTimes size={22} />
//                             </button>
//                         </div>

//                         <div className="p-6">
//                             {loadingReport ? (
//                                 <div className="text-center py-20">
//                                     <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto mb-4" />
//                                     <p className="text-slate-500">AI가 면접관들의 평가를 취합 중입니다...</p>
//                                 </div>
//                             ) : reportData ? (
//                                 <ResultPage_yyr reportData={reportData} />
//                             ) : (
//                                 <p className="text-center text-red-500">데이터를 불러오지 못했습니다.</p>
//                             )}
//                         </div>
//                     </div>
//                 </div>
//             )}
//         </div>
//     );
// }
// ========================================

// 두번째 ?
// src/pages_yyr/InterviewPage_yyr.jsx
// import React, { useMemo } from "react";
// import { FaFileUpload, FaCheckCircle, FaChartBar, FaTimes } from "react-icons/fa";

// import WebcamView from "../components/WebcamView";
// import AudioRecorder from "../components/AudioRecorder";
// import ResultPage_yyr from "./ResultPage_yyr";

// export default function InterviewPage_yyr({
//     sessionId,
//     visionResult,
//     chatLog,
//     isProcessing,
//     isResumeUploaded,

//     onLogout,
//     onFileUpload,
//     onAudioSubmit,
//     onEndInterview,
//     onVideoFrame,

//     showReport,
//     setShowReport,
//     reportData,
//     loadingReport,

//     audioPlayerRef,
// }) {
//     const progress = useMemo(() => {
//         if (showReport) return 100;
//         const userTurns = chatLog.filter((m) => m.sender === "user").length;
//         const base = isResumeUploaded ? 22 : 10;
//         const inc = Math.min(userTurns * 12, 68);
//         return Math.min(base + inc, 92);
//     }, [chatLog, isResumeUploaded, showReport]);

//     const stageLabel = useMemo(() => {
//         if (showReport) return "리포트";
//         if (!isResumeUploaded) return "준비";
//         if (isProcessing) return "AI 응답";
//         if (chatLog.length === 0) return "대기";
//         return "진행";
//     }, [showReport, isResumeUploaded, isProcessing, chatLog.length]);

//     const currentQuestion = useMemo(() => {
//         if (!isResumeUploaded) return "이력서를 업로드하면 맞춤 질문이 시작돼요.";
//         return "자기소개를 30초~1분으로 해주세요.";
//     }, [isResumeUploaded]);

//     const hint = useMemo(() => {
//         if (!isResumeUploaded) return "PDF 업로드 후, 맞춤 질문이 자동 생성됩니다.";
//         if (isProcessing) return "AI가 답변을 생성 중이에요. 잠시만 기다려주세요.";
//         return "준비가 되면 아래에서 답변을 녹음하세요.";
//     }, [isResumeUploaded, isProcessing]);

//     const stageDot = useMemo(() => {
//         if (stageLabel === "진행") return "bg-emerald-500";
//         if (stageLabel === "AI 응답") return "bg-amber-500";
//         if (stageLabel === "리포트") return "bg-violet-500";
//         return "bg-slate-300";
//     }, [stageLabel]);

//     return (
//         <div className="min-h-screen bg-gradient-to-b from-sky-50 via-white to-indigo-50 text-slate-900">
//             {/* ✅ Slim Topbar */}
//             <div className="sticky top-0 z-40 bg-white/75 backdrop-blur border-b border-sky-100">
//                 <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
//                     <div className="flex items-center gap-2 min-w-0">
//                         <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-sky-500 to-violet-500 shadow-sm shrink-0" />
//                         <div className="min-w-0">
//                             <h1 className="text-sm sm:text-base font-extrabold truncate">AI Interview</h1>
//                             <p className="text-[11px] text-slate-500 truncate">{hint}</p>
//                         </div>
//                     </div>

//                     <div className="flex items-center gap-2 shrink-0">
//                         <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-white border border-sky-100 shadow-sm">
//                             <span className={`w-2 h-2 rounded-full ${stageDot} ${stageLabel !== "준비" ? "animate-pulse" : ""}`} />
//                             <span className="text-xs font-semibold text-slate-700">{stageLabel}</span>
//                             <span className="text-xs text-slate-400">·</span>
//                             <span className="text-xs font-extrabold text-slate-900">{progress}%</span>
//                         </div>

//                         <button
//                             onClick={onLogout}
//                             className="px-3 py-2 rounded-xl bg-slate-900 text-white text-sm font-bold hover:bg-black transition"
//                         >
//                             로그아웃
//                         </button>
//                     </div>
//                 </div>

//                 <div className="max-w-6xl mx-auto px-4 pb-3">
//                     <div className="flex items-center justify-between mb-1">
//                         <p className="text-[11px] text-slate-500">
//                             thread_id: <span className="font-mono text-slate-700">{sessionId ?? "준비 중..."}</span>
//                         </p>
//                         <p className="text-[11px] text-slate-500">
//                             진행도 <span className="font-extrabold text-slate-900">{progress}%</span>
//                         </p>
//                     </div>

//                     <div className="h-2 w-full rounded-full bg-sky-100 overflow-hidden">
//                         <div
//                             className="h-full rounded-full bg-gradient-to-r from-sky-500 to-violet-500 transition-all"
//                             style={{ width: `${progress}%` }}
//                         />
//                     </div>
//                 </div>
//             </div>

//             {/* ✅ 완전 새 레이아웃 */}
//             <main className="max-w-6xl mx-auto px-4 py-7 grid grid-cols-1 lg:grid-cols-12 gap-6">
//                 {/* LEFT: Camera + Chips + Upload (기존 Vision/Resume 카드 제거) */}
//                 <section className="lg:col-span-5 space-y-4">
//                     {/* Camera */}
//                     <div className="rounded-3xl border border-sky-100 bg-white shadow-sm overflow-hidden">
//                         <div className="px-5 py-4 flex items-center justify-between">
//                             <div>
//                                 <p className="text-xs font-semibold text-slate-500">Live</p>
//                                 <p className="text-sm font-extrabold text-slate-900 mt-0.5">면접 화면</p>
//                             </div>

//                             <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-white text-xs font-extrabold bg-red-600 shadow-sm">
//                                 <span className="w-2 h-2 rounded-full bg-white/90 animate-pulse" />
//                                 LIVE
//                             </span>
//                         </div>

//                         <div className="px-5 pb-5">
//                             <WebcamView onVideoFrame={onVideoFrame} isProcessing={isProcessing} />
//                         </div>
//                     </div>

//                     {/* Status chips (작게) */}
//                     <div className="flex flex-wrap gap-2">
//                         <span className="inline-flex items-center gap-2 px-3 py-2 rounded-full bg-white border border-sky-100 shadow-sm text-xs font-semibold text-slate-700">
//                             <span className="w-2 h-2 rounded-full bg-sky-500/80" />
//                             Vision: <span className="font-extrabold">{visionResult}</span>
//                         </span>

//                         <span className="inline-flex items-center gap-2 px-3 py-2 rounded-full bg-white border border-sky-100 shadow-sm text-xs font-semibold text-slate-700">
//                             <span className={`w-2 h-2 rounded-full ${isResumeUploaded ? "bg-emerald-500" : "bg-slate-300"}`} />
//                             Resume: <span className="font-extrabold">{isResumeUploaded ? "완료" : "미등록"}</span>
//                         </span>

//                         <span className="inline-flex items-center gap-2 px-3 py-2 rounded-full bg-white border border-sky-100 shadow-sm text-xs font-semibold text-slate-700">
//                             <span className={`w-2 h-2 rounded-full ${isProcessing ? "bg-amber-500 animate-pulse" : "bg-slate-300"}`} />
//                             Status: <span className="font-extrabold">{isProcessing ? "Processing" : "Ready"}</span>
//                         </span>
//                     </div>

//                     {/* Upload card (단 하나) */}
//                     <div className="rounded-3xl border border-sky-100 bg-white shadow-sm p-5">
//                         <div className="flex items-start justify-between gap-4">
//                             <div className="min-w-0">
//                                 <p className="text-xs font-semibold text-slate-500">Resume</p>
//                                 <p className="text-base font-extrabold text-slate-900 mt-1">
//                                     {isResumeUploaded ? "업로드 완료" : "PDF 이력서 업로드"}
//                                 </p>
//                                 <p className="text-xs text-slate-500 mt-1">
//                                     {isResumeUploaded
//                                         ? "맞춤 질문이 생성될 준비가 되었어요."
//                                         : "이력서를 업로드하면 질문이 더 정교해집니다."}
//                                 </p>
//                             </div>

//                             {!isResumeUploaded ? (
//                                 <label className="shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-2xl cursor-pointer text-white text-sm font-extrabold bg-gradient-to-r from-sky-500 to-violet-500 hover:from-sky-600 hover:to-violet-600 transition shadow-sm">
//                                     <FaFileUpload />
//                                     업로드
//                                     <input type="file" className="hidden" accept=".pdf" onChange={onFileUpload} />
//                                 </label>
//                             ) : (
//                                 <div className="shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-2xl bg-emerald-50 text-emerald-700 border border-emerald-100 text-sm font-extrabold">
//                                     <FaCheckCircle />
//                                     완료
//                                 </div>
//                             )}
//                         </div>
//                     </div>
//                 </section>

//                 {/* RIGHT: Question + Timeline + Action (기존 큰 빈 공간 제거) */}
//                 <section className="lg:col-span-7">
//                     <div className="rounded-3xl border border-sky-100 bg-white shadow-sm overflow-hidden flex flex-col min-h-[720px]">
//                         {/* Question header */}
//                         <div className="px-6 py-5 border-b border-sky-100 bg-gradient-to-b from-white to-sky-50/40">
//                             <div className="flex items-start justify-between gap-4">
//                                 <div className="min-w-0">
//                                     <p className="text-[11px] font-semibold text-slate-500">현재 질문</p>
//                                     <h2 className="mt-1 text-xl sm:text-2xl font-extrabold text-slate-900 leading-snug">
//                                         {currentQuestion}
//                                     </h2>
//                                     <p className="text-xs text-slate-500 mt-2">{hint}</p>
//                                 </div>

//                                 <button
//                                     onClick={onEndInterview}
//                                     className="shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-xl text-white text-sm font-extrabold bg-gradient-to-r from-sky-500 to-violet-500 hover:from-sky-600 hover:to-violet-600 transition shadow-sm"
//                                 >
//                                     <FaChartBar />
//                                     결과 보기
//                                 </button>
//                             </div>
//                         </div>

//                         {/* Timeline / Chat */}
//                         <div className="flex-1 px-6 py-5 overflow-y-auto bg-white">
//                             {chatLog.length === 0 ? (
//                                 <div className="h-full flex items-center justify-center text-center">
//                                     <div className="max-w-md">
//                                         <div className="mx-auto w-14 h-14 rounded-2xl bg-sky-50 border border-sky-100 flex items-center justify-center text-slate-800 font-extrabold">
//                                             Q
//                                         </div>
//                                         <p className="mt-4 text-sm text-slate-500">
//                                             준비가 되시면 이력서를 업로드하고<br />
//                                             <span className="font-semibold text-slate-700">[답변 시작]</span>을 눌러주세요.
//                                         </p>
//                                     </div>
//                                 </div>
//                             ) : (
//                                 <div className="space-y-3">
//                                     {chatLog.map((msg, idx) => (
//                                         <div key={idx} className="flex gap-3">
//                                             <div className="pt-1">
//                                                 <div
//                                                     className={[
//                                                         "w-7 h-7 rounded-2xl flex items-center justify-center text-xs font-extrabold border",
//                                                         msg.sender === "user"
//                                                             ? "bg-slate-900 text-white border-slate-900"
//                                                             : msg.sender === "system"
//                                                                 ? "bg-emerald-50 text-emerald-700 border-emerald-100"
//                                                                 : "bg-sky-50 text-slate-800 border-sky-100",
//                                                     ].join(" ")}
//                                                 >
//                                                     {msg.sender === "user" ? "U" : msg.sender === "system" ? "S" : "A"}
//                                                 </div>
//                                             </div>

//                                             <div className="flex-1">
//                                                 <div
//                                                     className={[
//                                                         "px-4 py-3 rounded-2xl text-sm leading-relaxed border",
//                                                         msg.sender === "user"
//                                                             ? "bg-slate-900 text-white border-slate-900"
//                                                             : msg.sender === "system"
//                                                                 ? "bg-emerald-50 text-emerald-800 border-emerald-100"
//                                                                 : "bg-sky-50/70 text-slate-900 border-sky-100",
//                                                     ].join(" ")}
//                                                 >
//                                                     {msg.text}
//                                                 </div>
//                                             </div>
//                                         </div>
//                                     ))}
//                                 </div>
//                             )}
//                         </div>

//                         {/* Action footer (버튼은 그대로) */}
//                         <div className="px-6 py-5 border-t border-sky-100 bg-white">
//                             <div className="flex items-center justify-between mb-3">
//                                 <p className="text-xs text-slate-500">
//                                     {isProcessing ? "AI 응답 생성 중…" : "버튼을 눌러 답변을 녹음하세요."}
//                                 </p>
//                                 <span className="text-xs font-semibold text-slate-700">
//                                     {isProcessing ? "Processing" : "Ready"}
//                                 </span>
//                             </div>

//                             <AudioRecorder onAudioSubmit={onAudioSubmit} isProcessing={isProcessing} />
//                             <audio ref={audioPlayerRef} hidden />
//                         </div>
//                     </div>
//                 </section>
//             </main>

//             {/* Report modal */}
//             {showReport && (
//                 <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
//                     <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto border border-sky-100">
//                         <div className="p-6 border-b border-sky-100 flex justify-between items-center sticky top-0 bg-white z-10">
//                             <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900">
//                                 📊 면접 분석 리포트
//                             </h2>
//                             <button
//                                 onClick={() => setShowReport(false)}
//                                 className="text-slate-400 hover:text-slate-600"
//                                 aria-label="Close"
//                             >
//                                 <FaTimes size={22} />
//                             </button>
//                         </div>

//                         <div className="p-6">
//                             {loadingReport ? (
//                                 <div className="text-center py-20">
//                                     <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-sky-500 mx-auto mb-4" />
//                                     <p className="text-slate-500">AI가 면접관들의 평가를 취합 중입니다...</p>
//                                 </div>
//                             ) : reportData ? (
//                                 <ResultPage_yyr reportData={reportData} />
//                             ) : (
//                                 <p className="text-center text-red-500">데이터를 불러오지 못했습니다.</p>
//                             )}
//                         </div>
//                     </div>
//                 </div>
//             )}
//         </div>
//     );
// }
// ===================================

// // src/pages_yyr/InterviewPage_yyr.jsx
// import React, { useMemo } from "react";
// import { FaFileUpload, FaCheckCircle, FaChartBar, FaTimes } from "react-icons/fa";

// import WebcamView from "../components/WebcamView";
// import AudioRecorder from "../components/AudioRecorder";
// import ResultPage_yyr from "./ResultPage_yyr";

// export default function InterviewPage_yyr({
//     sessionId,
//     visionResult,
//     chatLog,
//     isProcessing,
//     isResumeUploaded,

//     onLogout,
//     onFileUpload,
//     onAudioSubmit,
//     onEndInterview,
//     onVideoFrame,

//     showReport,
//     setShowReport,
//     reportData,
//     loadingReport,

//     audioPlayerRef,
// }) {
//     // ✅ 진행도(임시 정책)
//     const progress = useMemo(() => {
//         if (showReport) return 100;
//         const userTurns = chatLog.filter((m) => m.sender === "user").length;
//         const base = isResumeUploaded ? 20 : 8;
//         const inc = Math.min(userTurns * 12, 68);
//         return Math.min(base + inc, 90);
//     }, [chatLog, isResumeUploaded, showReport]);

//     const stageLabel = useMemo(() => {
//         if (showReport) return "리포트 생성";
//         if (!isResumeUploaded) return "준비";
//         if (isProcessing) return "AI 응답 중";
//         if (chatLog.length === 0) return "대기";
//         return "진행";
//     }, [showReport, isResumeUploaded, isProcessing, chatLog.length]);

//     const currentQuestion = useMemo(() => {
//         if (!isResumeUploaded) return "이력서를 업로드하면 맞춤 질문이 시작돼요.";
//         return "자기소개를 30초~1분으로 해주세요.";
//     }, [isResumeUploaded]);

//     const hint = useMemo(() => {
//         if (!isResumeUploaded) return "PDF 업로드 후, 맞춤 질문이 자동 생성됩니다.";
//         if (isProcessing) return "AI가 답변을 생성 중이에요. 잠시만 기다려주세요.";
//         return "준비가 되면 아래에서 답변을 녹음하세요.";
//     }, [isResumeUploaded, isProcessing]);

//     // 상태 배지 색(절제)
//     const badgeDot = useMemo(() => {
//         if (stageLabel === "진행") return "bg-emerald-500";
//         if (stageLabel === "AI 응답 중") return "bg-amber-500";
//         if (stageLabel === "리포트 생성") return "bg-violet-500";
//         return "bg-slate-300";
//     }, [stageLabel]);

//     return (
//         <div className="min-h-screen bg-gradient-to-b from-sky-50 via-white to-indigo-50 text-slate-900">
//             {/* ✅ Slim topbar (작게) */}
//             <div className="sticky top-0 z-40 bg-white/70 backdrop-blur border-b border-sky-100">
//                 <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
//                     <div className="min-w-0">
//                         <div className="flex items-center gap-2">
//                             <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-sky-500 to-violet-500 shadow-sm" />
//                             <div className="min-w-0">
//                                 <h1 className="text-sm sm:text-base font-extrabold leading-tight truncate">
//                                     AI Interview
//                                 </h1>
//                                 <p className="text-[11px] text-slate-500 truncate">
//                                     {hint}
//                                 </p>
//                             </div>
//                         </div>
//                     </div>

//                     <div className="flex items-center gap-2 shrink-0">
//                         <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-white border border-sky-100 shadow-sm">
//                             <span className={`w-2 h-2 rounded-full ${badgeDot} ${stageLabel !== "준비" ? "animate-pulse" : ""}`} />
//                             <span className="text-xs font-semibold text-slate-700">{stageLabel}</span>
//                             <span className="text-xs text-slate-400">·</span>
//                             <span className="text-xs font-extrabold text-slate-900">{progress}%</span>
//                         </div>

//                         <button
//                             onClick={onLogout}
//                             className="px-3 py-2 rounded-xl bg-slate-900 text-white text-sm font-bold hover:bg-black transition"
//                         >
//                             로그아웃
//                         </button>
//                     </div>
//                 </div>

//                 {/* ✅ progress bar only (thin) */}
//                 <div className="max-w-6xl mx-auto px-4 pb-3">
//                     <div className="flex items-center justify-between mb-1">
//                         <p className="text-[11px] text-slate-500">
//                             thread_id: <span className="font-mono text-slate-700">{sessionId ?? "준비 중..."}</span>
//                         </p>
//                         <p className="text-[11px] text-slate-500">
//                             면접 진행도 <span className="font-extrabold text-slate-900">{progress}%</span>
//                         </p>
//                     </div>

//                     <div className="h-2 w-full rounded-full bg-sky-100 overflow-hidden">
//                         <div
//                             className="h-full rounded-full bg-gradient-to-r from-sky-500 to-violet-500 transition-all"
//                             style={{ width: `${progress}%` }}
//                         />
//                     </div>
//                 </div>
//             </div>

//             {/* ✅ New layout: left = camera big + 2 small chips / right = question + chat + action */}
//             <main className="max-w-6xl mx-auto px-4 py-7 grid grid-cols-1 lg:grid-cols-12 gap-6">
//                 {/* LEFT */}
//                 <section className="lg:col-span-5 space-y-4">
//                     {/* Camera card (bigger & cleaner) */}
//                     <div className="rounded-3xl border border-sky-100 bg-white shadow-sm overflow-hidden">
//                         <div className="px-5 py-4 flex items-center justify-between">
//                             <div>
//                                 <p className="text-xs font-semibold text-slate-500">Live Camera</p>
//                                 <p className="text-sm font-extrabold text-slate-900 mt-0.5">면접 화면</p>
//                             </div>

//                             <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-white text-xs font-bold bg-gradient-to-r from-sky-500 to-violet-500 shadow-sm">
//                                 <span className="w-2 h-2 rounded-full bg-white/90 animate-pulse" />
//                                 LIVE
//                             </span>
//                         </div>

//                         <div className="px-5 pb-5">
//                             <WebcamView onVideoFrame={onVideoFrame} isProcessing={isProcessing} />
//                         </div>
//                     </div>

//                     {/* Chips row */}
//                     <div className="grid grid-cols-2 gap-4">
//                         <div className="rounded-3xl border border-sky-100 bg-white shadow-sm p-4">
//                             <p className="text-xs font-semibold text-slate-500">Vision</p>
//                             <p className="mt-1 text-base font-extrabold text-slate-900">{visionResult}</p>
//                             <div className="mt-2 h-1.5 w-full rounded-full bg-sky-100 overflow-hidden">
//                                 <div className="h-full w-1/2 rounded-full bg-sky-400/70" />
//                             </div>
//                             <p className="text-[11px] text-slate-500 mt-2">
//                                 {visionResult === "분석 대기 중..." ? "카메라 연결 후 자동 분석" : "실시간 표정 추정"}
//                             </p>
//                         </div>

//                         <div className="rounded-3xl border border-sky-100 bg-white shadow-sm p-4">
//                             <p className="text-xs font-semibold text-slate-500">Resume</p>
//                             {!isResumeUploaded ? (
//                                 <>
//                                     <p className="mt-1 text-base font-extrabold text-slate-900">미등록</p>
//                                     <p className="text-[11px] text-slate-500 mt-2">
//                                         PDF 업로드 후 맞춤 질문 시작
//                                     </p>
//                                 </>
//                             ) : (
//                                 <>
//                                     <p className="mt-1 text-base font-extrabold text-slate-900">완료</p>
//                                     <p className="text-[11px] text-slate-500 mt-2">
//                                         이력서 기반으로 질문 생성
//                                     </p>
//                                 </>
//                             )}

//                             <div className="mt-3">
//                                 {!isResumeUploaded ? (
//                                     <label className="flex items-center justify-between w-full px-4 py-3 rounded-2xl border border-sky-100 bg-sky-50/50 hover:bg-sky-50 cursor-pointer transition">
//                                         <div className="flex items-center gap-3">
//                                             <div className="w-9 h-9 rounded-2xl bg-slate-900 text-white flex items-center justify-center">
//                                                 <FaFileUpload />
//                                             </div>
//                                             <div className="leading-tight">
//                                                 <p className="text-sm font-extrabold text-slate-900">업로드</p>
//                                                 <p className="text-[11px] text-slate-500">PDF만 가능</p>
//                                             </div>
//                                         </div>
//                                         <span className="text-xs font-bold text-slate-900">선택</span>
//                                         <input type="file" className="hidden" accept=".pdf" onChange={onFileUpload} />
//                                     </label>
//                                 ) : (
//                                     <div className="flex items-center gap-2 px-4 py-3 rounded-2xl border border-emerald-200 bg-emerald-50 text-emerald-800">
//                                         <FaCheckCircle />
//                                         <span className="text-sm font-extrabold">업로드 완료</span>
//                                     </div>
//                                 )}
//                             </div>
//                         </div>
//                     </div>
//                 </section>

//                 {/* RIGHT */}
//                 <section className="lg:col-span-7">
//                     <div className="rounded-3xl border border-sky-100 bg-white shadow-sm overflow-hidden flex flex-col min-h-[720px]">
//                         {/* Question header */}
//                         <div className="px-6 py-5 border-b border-sky-100 bg-gradient-to-b from-white to-sky-50/40">
//                             <div className="flex items-start justify-between gap-4">
//                                 <div className="min-w-0">
//                                     <p className="text-[11px] font-semibold text-slate-500">현재 질문</p>
//                                     <h2 className="mt-1 text-xl sm:text-2xl font-extrabold text-slate-900 leading-snug">
//                                         {currentQuestion}
//                                     </h2>
//                                     <p className="text-xs text-slate-500 mt-2">{hint}</p>
//                                 </div>

//                                 <button
//                                     onClick={onEndInterview}
//                                     className="shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-xl text-white text-sm font-extrabold bg-gradient-to-r from-sky-500 to-violet-500 hover:from-sky-600 hover:to-violet-600 transition shadow-sm"
//                                 >
//                                     <FaChartBar />
//                                     결과 보기
//                                 </button>
//                             </div>
//                         </div>

//                         {/* Chat body */}
//                         <div className="flex-1 px-6 py-5 overflow-y-auto space-y-3 bg-white">
//                             {chatLog.length === 0 ? (
//                                 <div className="h-full flex items-center justify-center text-center">
//                                     <div className="max-w-md">
//                                         <div className="mx-auto w-14 h-14 rounded-2xl bg-sky-50 border border-sky-100 flex items-center justify-center text-slate-700 font-extrabold">
//                                             Q
//                                         </div>
//                                         <p className="mt-4 text-sm text-slate-500">
//                                             준비가 되시면 이력서를 업로드하고<br />
//                                             <span className="font-semibold text-slate-700">[답변 시작]</span>을 눌러주세요.
//                                         </p>
//                                     </div>
//                                 </div>
//                             ) : (
//                                 chatLog.map((msg, idx) => (
//                                     <div
//                                         key={idx}
//                                         className={`flex ${msg.sender === "user"
//                                             ? "justify-end"
//                                             : msg.sender === "system"
//                                                 ? "justify-center"
//                                                 : "justify-start"
//                                             }`}
//                                     >
//                                         <div
//                                             className={`max-w-[84%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${msg.sender === "user"
//                                                 ? "bg-slate-900 text-white rounded-tr-md shadow-sm"
//                                                 : msg.sender === "system"
//                                                     ? "bg-emerald-50 text-emerald-800 border border-emerald-100 text-xs py-2"
//                                                     : "bg-sky-50/70 text-slate-900 border border-sky-100 rounded-tl-md"
//                                                 }`}
//                                         >
//                                             {msg.text}
//                                         </div>
//                                     </div>
//                                 ))
//                             )}
//                         </div>

//                         {/* Action footer */}
//                         <div className="px-6 py-5 border-t border-sky-100 bg-white">
//                             <div className="flex items-center justify-between mb-3">
//                                 <p className="text-xs text-slate-500">
//                                     {isProcessing ? "AI 응답 생성 중…" : "버튼을 눌러 답변을 녹음하세요."}
//                                 </p>
//                                 <span className="text-xs font-semibold text-slate-700">
//                                     {isProcessing ? "Processing" : "Ready"}
//                                 </span>
//                             </div>

//                             <AudioRecorder onAudioSubmit={onAudioSubmit} isProcessing={isProcessing} />
//                             <audio ref={audioPlayerRef} hidden />
//                         </div>
//                     </div>
//                 </section>
//             </main>

//             {/* Report modal */}
//             {showReport && (
//                 <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
//                     <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto border border-sky-100">
//                         <div className="p-6 border-b border-sky-100 flex justify-between items-center sticky top-0 bg-white z-10">
//                             <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900">
//                                 📊 면접 분석 리포트
//                             </h2>
//                             <button
//                                 onClick={() => setShowReport(false)}
//                                 className="text-slate-400 hover:text-slate-600"
//                                 aria-label="Close"
//                             >
//                                 <FaTimes size={22} />
//                             </button>
//                         </div>

//                         <div className="p-6">
//                             {loadingReport ? (
//                                 <div className="text-center py-20">
//                                     <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-sky-500 mx-auto mb-4" />
//                                     <p className="text-slate-500">AI가 면접관들의 평가를 취합 중입니다...</p>
//                                 </div>
//                             ) : reportData ? (
//                                 <ResultPage_yyr reportData={reportData} />
//                             ) : (
//                                 <p className="text-center text-red-500">데이터를 불러오지 못했습니다.</p>
//                             )}
//                         </div>
//                     </div>
//                 </div>
//             )}
//         </div>
//     );
// }