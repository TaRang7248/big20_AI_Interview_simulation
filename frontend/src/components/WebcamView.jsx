import React, { useRef, useEffect, useState } from 'react';

// [수정] isProcessing props 추가 (AI가 생각 중인지 알기 위해)
const WebcamView = ({ onVideoFrame, isProcessing }) => {
  const videoRef = useRef(null);
  const [stream, setStream] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const startWebcam = async () => {
      try {
        const mediaStream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });
        setStream(mediaStream);
        if (videoRef.current) {
          videoRef.current.srcObject = mediaStream;
        }
      } catch (err) {
        console.error("웹캠 접근 실패:", err);
        setError("카메라 권한을 허용해 주세요.");
      }
    };

    startWebcam();

    return () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  // [수정] 스냅샷 주기 최적화
  useEffect(() => {
    if (!stream) return;

    const interval = setInterval(() => {
      // 1. 비디오가 준비되지 않았거나
      // 2. AI가 현재 답변을 생성 중이라면 (isProcessing === true)
      // --> 분석 요청을 보내지 않음 (리소스 절약)
      if (!videoRef.current || isProcessing) return;

      const canvas = document.createElement('canvas');
      canvas.width = videoRef.current.videoWidth;
      canvas.height = videoRef.current.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(videoRef.current, 0, 0);

      canvas.toBlob((blob) => {
        if (onVideoFrame && blob) {
          onVideoFrame(blob);
        }
      }, 'image/jpeg', 0.7); // 품질을 0.8 -> 0.7로 낮춰서 전송 속도 향상
    }, 3000); // [중요] 1000ms(1초) -> 3000ms(3초)로 변경

    return () => clearInterval(interval);
  }, [stream, onVideoFrame, isProcessing]); // 의존성 배열에 isProcessing 추가

  return (
    <div className="relative w-full max-w-lg mx-auto bg-black rounded-lg overflow-hidden shadow-xl aspect-video">
      {error ? (
        <div className="flex items-center justify-center h-full text-white bg-gray-800">
          <p>{error}</p>
        </div>
      ) : (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-cover transform scale-x-[-1]"
        />
      )}

      {/* <div className="absolute top-4 right-4 px-3 py-1 bg-red-600 bg-opacity-75 rounded-full flex items-center gap-2">
        <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
        <span className="text-white text-xs font-bold">LIVE</span>
      </div> */}
    </div>
  );
};

export default WebcamView;