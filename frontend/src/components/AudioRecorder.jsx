import React, { useEffect, useRef, useState } from "react";

/**
 * Web Speech API 기반 음성 입력 컴포넌트
 * - 답변 종료 시 onTextSubmit(transcript: string) 호출
 * - 스트리밍 미리보기 제공 (보고서 캡쳐용)
 */
const AudioRecorder = ({ onTextSubmit, isProcessing }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [partial, setPartial] = useState("");
  const [finalText, setFinalText] = useState("");

  const recognitionRef = useRef(null);

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  const supported = !!SpeechRecognition;

  useEffect(() => {
    if (!supported) return;

    const recognition = new SpeechRecognition();
    recognition.lang = "ko-KR";
    recognition.interimResults = true;
    recognition.continuous = true;

    recognition.onresult = (event) => {
      let interim = "";
      let finalAccum = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const text = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalAccum += text;
        else interim += text;
      }

      if (finalAccum) {
        setFinalText((prev) =>
          prev ? `${prev} ${finalAccum}`.trim() : finalAccum.trim()
        );
      }
      setPartial(interim);
    };

    recognition.onerror = (e) => {
      console.error("[WebSpeech] error:", e);
      alert(`음성 인식 오류: ${e?.error || "unknown"}`);
      setIsRecording(false);
    };

    // ⚠️ 자동 종료 시: 상태만 정리 (전송 ❌)
    recognition.onend = () => {
      setIsRecording(false);
    };

    recognitionRef.current = recognition;

    return () => {
      try {
        recognition.stop();
      } catch { }
    };
  }, [supported]);

  const startRecording = () => {
    if (!supported) {
      alert("이 브라우저는 Web Speech API를 지원하지 않습니다. (Chrome 권장)");
      return;
    }
    if (isProcessing || isRecording) return;

    setFinalText("");
    setPartial("");

    try {
      recognitionRef.current?.start();
      setIsRecording(true);
    } catch (e) {
      console.error("[WebSpeech] start failed:", e);
      alert("음성 인식을 시작하지 못했습니다.");
    }
  };

  const stopRecording = () => {
    try {
      recognitionRef.current?.stop();
    } catch { }

    setIsRecording(false);

    const merged = `${finalText} ${partial}`.replace(/\s+/g, " ").trim();
    setPartial("");

    if (!merged) {
      alert("음성이 인식되지 않았습니다. 다시 말씀해 주세요.");
      return;
    }

    // ✅ 최종 텍스트 전송 (유일한 전송 지점)
    onTextSubmit?.(merged);
  };

  // 버튼 스타일
  const baseBtn =
    "inline-flex items-center justify-center gap-2 px-6 py-3 rounded-full font-extrabold " +
    "transition-all select-none focus:outline-none focus:ring-4 focus:ring-sky-200/50 " +
    "shadow-[0_14px_30px_-18px_rgba(2,132,199,0.6)]";

  const idleBtn =
    "text-white bg-gradient-to-r from-sky-500 to-violet-500 hover:opacity-95";

  const disabledBtn =
    "text-slate-400 bg-slate-200 cursor-not-allowed shadow-none";

  const recordingBtn =
    "text-white bg-gradient-to-r from-rose-500 to-red-500 animate-pulse";

  return (
    <div className="flex flex-col items-center gap-3">
      {!isRecording ? (
        <button
          type="button"
          onClick={startRecording}
          disabled={isProcessing}
          className={`${baseBtn} ${isProcessing ? disabledBtn : idleBtn}`}
        >
          <span className="text-lg">{isProcessing ? "🤖" : "🎙️"}</span>
          {isProcessing ? "AI 응답 중..." : "답변 시작"}
        </button>
      ) : (
        <button
          type="button"
          onClick={stopRecording}
          className={`${baseBtn} ${recordingBtn}`}
        >
          <span className="text-lg">⏹️</span>
          답변 종료
        </button>
      )}

      {/* 🔎 스트리밍 미리보기 */}
      <div className="w-full max-w-xl text-xs text-slate-600 bg-white/60 border rounded-2xl px-4 py-3">
        <div className="font-bold mb-1">음성 인식 텍스트(미리보기)</div>
        <div className="whitespace-pre-wrap">
          {finalText || partial ? (
            <>
              <span>{finalText}</span>
              <span className="opacity-60">{partial ? ` ${partial}` : ""}</span>
            </>
          ) : (
            <span className="opacity-60">아직 인식된 텍스트가 없습니다.</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default AudioRecorder;