// 목소리를 녹음하는 부품

import React, { useState, useRef } from 'react';

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
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        onAudioSubmit(audioBlob); // 녹음된 파일 부모에게 전달
        
        // 마이크 끄기 (빨간불 끄기)
        stream.getTracks().forEach(track => track.stop());
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

  return (
    <div className="flex gap-4 justify-center">
      {!isRecording ? (
        <button
          onClick={startRecording}
          disabled={isProcessing}
          className={`px-6 py-3 rounded-full font-bold shadow transition flex items-center gap-2
            ${isProcessing 
              ? 'bg-gray-400 cursor-not-allowed text-gray-200' 
              : 'bg-blue-600 hover:bg-blue-700 text-white'}`}
        >
          {isProcessing ? "⏳ AI 생각 중..." : "🎤 답변 시작"}
        </button>
      ) : (
        <button
          onClick={stopRecording}
          className="px-6 py-3 bg-red-500 hover:bg-red-600 text-white rounded-full font-bold shadow transition flex items-center gap-2 animate-pulse"
        >
          ⏹️ 답변 종료 (녹음 중...)
        </button>
      )}
    </div>
  );
};

export default AudioRecorder;