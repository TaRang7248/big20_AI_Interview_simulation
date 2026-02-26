import React, { useEffect, useMemo, useRef, useState } from "react";

/**
 * Web Speech API 기반 "답변 시작/종료" 컴포넌트
 * - onTextSubmit(transcript: string) 콜백으로 최종 텍스트를 넘김
 * - 한국어(ko-KR) 기본
 * - 인식 결과를 화면에 미리보기로 보여줌(테스트/디버깅용)
 */
const AudioRecorder = ({ onTextSubmit, isProcessing }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [partial, setPartial] = useState(""); // 중간 인식(미완)
  const [finalText, setFinalText] = useState(""); // 확정 인식

  const recognitionRef = useRef(null);

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  const supported = !!SpeechRecognition;

  useEffect(() => {
    if (!supported) return;

    const recognition = new SpeechRecognition();
    recognition.lang = "ko-KR";
    recognition.interimResults = true; // 중간 결과 받기
    recognition.continuous = true; // 길게 말해도 이어서 받기

    recognition.onresult = (event) => {
      let interim = "";
      let finalAccum = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const text = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalAccum += text;
        else interim += text;
      }

      if (finalAccum) {
        setFinalText((prev) => (prev ? `${prev} ${finalAccum}` : finalAccum));
      }
      setPartial(interim);
    };

    recognition.onerror = (e) => {
      console.error("[WebSpeech] error:", e);
      // 네 UX 취향에 맞춰 alert 최소화
      alert(`음성 인식 오류: ${e?.error || "unknown"}`);
      setIsRecording(false);
    };

    recognition.onend = () => {
      // 사용자가 stop 누르면 onend로 떨어짐.
      // (자동 종료도 있을 수 있음)
      setIsRecording(false);
    };

    recognitionRef.current = recognition;

    return () => {
      try {
        recognition.stop();
      } catch { }
    };
  }, [supported]);

  const startRecording = async () => {
    if (!supported) {
      alert("이 브라우저는 Web Speech API를 지원하지 않아요. (Chrome 권장)");
      return;
    }
    if (isProcessing) return;

    setFinalText("");
    setPartial("");

    try {
      recognitionRef.current?.start();
      setIsRecording(true);
    } catch (e) {
      // start() 중복 호출 시 예외가 날 수 있음
      console.error("[WebSpeech] start failed:", e);
      alert("음성 인식을 시작하지 못했습니다. (이미 실행 중인지 확인)");
    }
  };

  const stopRecording = () => {
    try {
      recognitionRef.current?.stop();
    } catch { }

    const merged = `${finalText} ${partial}`.trim();
    setIsRecording(false);
    setPartial("");

    if (!merged) {
      alert("음성이 인식되지 않았습니다. 다시 한 번 또박또박 말씀해 주세요.");
      return;
    }

    // ✅ 핵심: 텍스트를 상위로 전달
    onTextSubmit?.(merged);
  };

  // 버튼 스타일(기존 느낌 유지)
  const baseBtn =
    "inline-flex items-center justify-center gap-2 px-6 py-3 rounded-full font-extrabold " +
    "transition-all select-none focus:outline-none focus:ring-4 focus:ring-sky-200/50 " +
    "shadow-[0_14px_30px_-18px_rgba(2,132,199,0.6)]";

  const idleBtn =
    "text-white bg-gradient-to-r from-sky-500 to-violet-500 " +
    "hover:from-sky-600 hover:to-violet-600 active:scale-[0.99]";

  const disabledBtn =
    "text-slate-400 bg-slate-200 cursor-not-allowed shadow-none";

  const recordingBtn =
    "text-white bg-gradient-to-r from-rose-500 to-red-500 " +
    "hover:from-rose-600 hover:to-red-600 animate-pulse";

  return (
    <div className="flex flex-col items-center gap-3">
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
          <span className="ml-1 text-xs font-bold opacity-90">(인식 중)</span>
        </button>
      )}

      {/* ✅ 디버깅/테스트용 미리보기 (보고서 캡쳐에도 좋음) */}
      <div className="w-full max-w-xl text-xs text-slate-600 bg-white/60 border border-white/60 rounded-2xl px-4 py-3">
        <div className="font-bold text-slate-700 mb-1">음성 인식 텍스트(미리보기)</div>
        <div className="whitespace-pre-wrap">
          {finalText || partial ? (
            <>
              <span>{finalText}</span>
              <span className="opacity-60">{partial ? ` ${partial}` : ""}</span>
            </>
          ) : (
            <span className="opacity-60">아직 인식된 텍스트가 없어요.</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default AudioRecorder;