import React, { useState, useRef } from "react";

const AudioRecorder = ({ onAudioSubmit, isProcessing }) => {
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        onAudioSubmit(audioBlob);

        // 마이크 끄기
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error("마이크 접근 실패:", err);
      alert("마이크 권한이 필요합니다.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  // ✅ 공통 버튼 스타일 (너무 크지 않게, “제품 버튼” 느낌)
  const baseBtn =
    "inline-flex items-center justify-center gap-2 px-6 py-3 rounded-full font-extrabold " +
    "transition-all select-none focus:outline-none focus:ring-4 focus:ring-sky-200/50 " +
    "shadow-[0_14px_30px_-18px_rgba(2,132,199,0.6)]";

  // ✅ 상태별 스타일
  const idleBtn =
    "text-white bg-gradient-to-r from-sky-500 to-violet-500 " +
    "hover:from-sky-600 hover:to-violet-600 active:scale-[0.99]";

  const disabledBtn =
    "text-slate-400 bg-slate-200 cursor-not-allowed shadow-none";

  const recordingBtn =
    "text-white bg-gradient-to-r from-rose-500 to-red-500 " +
    "hover:from-rose-600 hover:to-red-600 animate-pulse";

  return (
    <div className="flex items-center justify-center">
      {!isRecording ? (
        <button
          type="button"
          onClick={startRecording}
          disabled={isProcessing}
          className={`${baseBtn} ${isProcessing ? disabledBtn : idleBtn}`}
          aria-label="답변 시작"
        >
          <span className="text-lg">{isProcessing ? "🤖" : "🎙️"}</span>
          {isProcessing ? "AI 응답 중..." : "답변 시작"}
        </button>
      ) : (
        <button
          type="button"
          onClick={stopRecording}
          className={`${baseBtn} ${recordingBtn}`}
          aria-label="답변 종료"
        >
          <span className="text-lg">⏹️</span>
          답변 종료
          <span className="ml-1 text-xs font-bold opacity-90">(녹음 중)</span>
        </button>
      )}
    </div>
  );
};

export default AudioRecorder;