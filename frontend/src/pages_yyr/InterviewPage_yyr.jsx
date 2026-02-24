// src/pages_yyr/InterviewPage_yyr.jsx
import React from "react";
import { FaFileUpload, FaCheckCircle, FaChartBar, FaTimes } from "react-icons/fa";

import WebcamView from "../components/WebcamView";
import AudioRecorder from "../components/AudioRecorder";
import ResultPage_yyr from "./ResultPage_yyr";

export default function InterviewPage_yyr({
    // 상태/데이터
    sessionId,
    visionResult,
    chatLog,
    isProcessing,
    isResumeUploaded,

    // 핸들러
    onLogout,
    onFileUpload,
    onAudioSubmit,
    onEndInterview,
    onVideoFrame,

    // 리포트 모달
    showReport,
    setShowReport,
    reportData,
    loadingReport,

    // 오디오 재생
    audioPlayerRef,
}) {
    return (
        <div className="min-h-screen bg-gray-100 flex flex-col items-center py-10 font-sans relative">
            <header className="mb-8 text-center">
                <h1 className="text-4xl font-extrabold text-gray-900 mb-2">
                    AI Interview Simulation
                </h1>
                <p className="text-gray-500">카메라를 보고 질문에 답해보세요.</p>

                {/* 현재 세션ID 표시 */}
                <p className="text-xs text-gray-400 mt-2">
                    thread_id: <span className="font-mono">{sessionId ?? "준비 중..."}</span>
                </p>

                <button
                    onClick={onLogout}
                    className="mt-4 px-4 py-2 rounded-lg bg-gray-200 text-gray-700 text-sm font-bold hover:bg-gray-300"
                >
                    로그아웃
                </button>
            </header>

            <main className="w-full max-w-6xl px-4 grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* 왼쪽 섹션 */}
                <section className="flex flex-col gap-4">
                    <div className="bg-white p-2 rounded-2xl shadow-lg border border-gray-200">
                        {/* ✅ 핵심: App.jsx에서 내려준 onVideoFrame을 그대로 연결 */}
                        <WebcamView onVideoFrame={onVideoFrame} isProcessing={isProcessing} />
                    </div>

                    <div className="bg-white p-6 rounded-2xl shadow-md border border-gray-200 flex items-center justify-between">
                        <div>
                            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
                                Vision Analysis
                            </h3>
                            <p className="text-2xl font-bold text-blue-600 mt-1">{visionResult}</p>
                        </div>
                        <div
                            className={`w-3 h-3 rounded-full ${visionResult !== "분석 대기 중..." ? "bg-green-500 animate-pulse" : "bg-gray-300"
                                }`}
                        />
                    </div>

                    <div className="bg-white p-6 rounded-2xl shadow-md border border-gray-200">
                        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
                            Resume Setup
                        </h3>

                        {!isResumeUploaded ? (
                            <label className="flex items-center justify-center w-full p-6 border-2 border-dashed border-gray-300 rounded-xl cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition group">
                                <div className="flex flex-col items-center">
                                    <FaFileUpload className="text-3xl text-gray-400 mb-2 group-hover:text-blue-500 transition" />
                                    <span className="text-sm text-gray-600 font-medium group-hover:text-blue-600">
                                        PDF 이력서 업로드하기
                                    </span>
                                </div>
                                <input type="file" className="hidden" accept=".pdf" onChange={onFileUpload} />
                            </label>
                        ) : (
                            <div className="flex items-center gap-3 p-4 bg-green-50 text-green-700 rounded-xl border border-green-200">
                                <FaCheckCircle className="text-2xl" />
                                <div>
                                    <p className="font-bold text-sm">이력서 분석 완료</p>
                                    <p className="text-xs text-green-600">AI가 내용을 숙지했습니다.</p>
                                </div>
                            </div>
                        )}
                    </div>
                </section>

                {/* 오른쪽 섹션 */}
                <section className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6 flex flex-col h-[750px] relative">
                    <div className="flex items-center justify-between border-b border-gray-100 pb-4 mb-4">
                        <h2 className="text-xl font-bold text-gray-800">💬 Interview Chat</h2>

                        <button
                            onClick={onEndInterview}
                            className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 text-white text-xs font-bold rounded-lg hover:bg-black transition"
                        >
                            <FaChartBar /> 결과 보기
                        </button>
                    </div>

                    <div className="flex-1 overflow-y-auto space-y-4 mb-6 pr-2">
                        {chatLog.length === 0 && (
                            <div className="text-center text-gray-400 mt-20">
                                준비가 되시면<br />
                                이력서를 업로드하고<br />
                                [답변 시작] 버튼을 눌러주세요.
                            </div>
                        )}

                        {chatLog.map((msg, idx) => (
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
                                    className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm ${msg.sender === "user"
                                            ? "bg-blue-600 text-white rounded-tr-none"
                                            : msg.sender === "system"
                                                ? "bg-green-100 text-green-800 text-xs py-2"
                                                : "bg-gray-100 text-gray-800 rounded-tl-none"
                                        }`}
                                >
                                    {msg.text}
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="pt-4 border-t border-gray-100">
                        <AudioRecorder onAudioSubmit={onAudioSubmit} isProcessing={isProcessing} />
                        {/* ✅ App.jsx에서 내려준 ref를 그대로 사용 */}
                        <audio ref={audioPlayerRef} hidden />
                    </div>
                </section>
            </main>

            {/* 결과 리포트 모달 */}
            {showReport && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
                        <div className="p-6 border-b border-gray-100 flex justify-between items-center sticky top-0 bg-white z-10">
                            <h2 className="text-2xl font-bold text-gray-900">📊 면접 분석 리포트</h2>
                            <button
                                onClick={() => setShowReport(false)}
                                className="text-gray-400 hover:text-gray-600"
                            >
                                <FaTimes size={24} />
                            </button>
                        </div>

                        <div className="p-6">
                            {loadingReport ? (
                                <div className="text-center py-20">
                                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
                                    <p className="text-gray-500">AI가 면접관들의 평가를 취합 중입니다...</p>
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