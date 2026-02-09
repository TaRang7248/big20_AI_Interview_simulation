"use client";
import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Header from "@/components/common/Header";
import { emotionApi } from "@/lib/api";
import { BarChart3, Activity, Clock, Play, Square, RefreshCw } from "lucide-react";
import dynamic from "next/dynamic";

/* Chart.js – SSR 비활성화 */
const ChartComponent = dynamic(() => import("@/components/emotion/EmotionCharts"), { ssr: false });

/* ───── 상수 ───── */
const EMOTIONS = ["happy", "sad", "angry", "surprise", "fear", "disgust", "neutral"] as const;
type Emotion = (typeof EMOTIONS)[number];

const EMOTION_COLORS: Record<Emotion, string> = {
  happy: "rgba(255,217,61,0.8)", sad: "rgba(116,185,255,0.8)",
  angry: "rgba(255,71,87,0.8)", surprise: "rgba(162,155,254,0.8)",
  fear: "rgba(99,110,114,0.8)", disgust: "rgba(0,184,148,0.8)",
  neutral: "rgba(178,190,195,0.8)",
};
const EMOTION_EMOJIS: Record<Emotion, string> = {
  happy: "😊", sad: "😢", angry: "😠", surprise: "😲",
  fear: "😨", disgust: "🤢", neutral: "😐",
};
const EMOTION_KO: Record<Emotion, string> = {
  happy: "행복", sad: "슬픔", angry: "분노", surprise: "놀람",
  fear: "공포", disgust: "혐오", neutral: "중립",
};
const BAR_GRADIENTS: Record<Emotion, string> = {
  happy: "from-yellow-400 to-orange-400", sad: "from-blue-300 to-blue-500",
  angry: "from-red-400 to-red-600", surprise: "from-purple-300 to-purple-500",
  fear: "from-gray-500 to-gray-600", disgust: "from-emerald-400 to-emerald-600",
  neutral: "from-gray-300 to-gray-400",
};

const MAX_POINTS = 60;
const REFRESH_OPTIONS = [
  { value: 500, label: "0.5초" }, { value: 1000, label: "1초" },
  { value: 2000, label: "2초" }, { value: 5000, label: "5초" },
];

function initProbs(): Record<Emotion, number> {
  return { happy: 0, sad: 0, angry: 0, surprise: 0, fear: 0, disgust: 0, neutral: 0 };
}
function initTimeSeries(): Record<Emotion, number[]> {
  return { happy: [], sad: [], angry: [], surprise: [], fear: [], disgust: [], neutral: [] };
}

export default function EmotionDashboardWrapper() {
  return <Suspense fallback={<div className="min-h-screen bg-gradient-to-br from-[#1a1a2e] via-[#16213e] to-[#0f3460] flex items-center justify-center text-gray-400">로딩 중...</div>}><EmotionDashboardPage /></Suspense>;
}

function EmotionDashboardPage() {
  const searchParams = useSearchParams();

  const [sessionId, setSessionId] = useState(searchParams.get("session_id") || "");
  const [refreshRate, setRefreshRate] = useState(1000);
  const [monitoring, setMonitoring] = useState(false);
  const [connected, setConnected] = useState(false);

  // 현재 감정
  const [dominant, setDominant] = useState<Emotion>("neutral");
  const [probabilities, setProbabilities] = useState<Record<Emotion, number>>(initProbs);

  // 시계열
  const [timeLabels, setTimeLabels] = useState<string[]>([]);
  const [timeData, setTimeData] = useState<Record<Emotion, number[]>>(initTimeSeries);
  const [dataPoints, setDataPoints] = useState(0);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /* 데이터 fetch */
  const fetchData = useCallback(async () => {
    try {
      const data = await emotionApi.getCurrent();
      if (data.status === "no_data") { setConnected(false); return; }
      setConnected(true);

      const probs: Record<string, number> = data.probabilities || {};
      const dom = (data.dominant_emotion || "neutral") as Emotion;
      setDominant(dom);

      const newProbs = {} as Record<Emotion, number>;
      EMOTIONS.forEach(e => { newProbs[e] = (probs[e] || 0) * 100; });
      setProbabilities(newProbs);

      // 시계열 누적
      const now = new Date().toLocaleTimeString();
      setTimeLabels(prev => [...prev.slice(-(MAX_POINTS - 1)), now]);
      setTimeData(prev => {
        const next = { ...prev };
        EMOTIONS.forEach(e => { next[e] = [...prev[e].slice(-(MAX_POINTS - 1)), newProbs[e]]; });
        return next;
      });
      setDataPoints(prev => prev + 1);
    } catch {
      setConnected(false);
    }
  }, []);

  /* 시작 / 중지 */
  const start = () => {
    if (!sessionId.trim()) { alert("세션 ID를 입력하세요."); return; }
    // 초기화
    setTimeLabels([]); setDataPoints(0);
    setTimeData(initTimeSeries());
    setMonitoring(true);
    fetchData();
    intervalRef.current = setInterval(fetchData, refreshRate);
  };

  const stop = () => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    setMonitoring(false); setConnected(false);
  };

  useEffect(() => () => { if (intervalRef.current) clearInterval(intervalRef.current); }, []);

  /* 통계 */
  const avgForEmotion = (e: Emotion) => {
    const d = timeData[e];
    return d.length ? (d.reduce((a, b) => a + b, 0) / d.length).toFixed(1) : "0.0";
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#1a1a2e] via-[#16213e] to-[#0f3460] text-white">
      <Header />

      <main className="max-w-[1600px] mx-auto px-6 py-8">
        {/* 헤더 */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold gradient-text">🎯 AI 면접 감정 분석 대시보드</h1>
          <p className="text-gray-400 mt-2">실시간 감정 분석 결과를 시각화합니다</p>
        </div>

        {/* 컨트롤 */}
        <div className="flex items-center justify-center gap-4 flex-wrap mb-6">
          <input type="text" value={sessionId} onChange={e => setSessionId(e.target.value)}
            placeholder="세션 ID 입력..." className="input-field w-64" />
          <select value={refreshRate} onChange={e => setRefreshRate(Number(e.target.value))}
            className="input-field w-28">
            {REFRESH_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          {!monitoring ? (
            <button onClick={start} className="btn-gradient px-5 py-2.5 rounded-xl text-sm font-semibold flex items-center gap-2">
              <Play size={14} /> 모니터링 시작
            </button>
          ) : (
            <button onClick={stop}
              className="px-5 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-red-500 to-pink-500 text-white flex items-center gap-2">
              <Square size={14} /> 중지
            </button>
          )}
        </div>

        {/* 상태 표시 */}
        <div className={`text-center py-3 rounded-xl mb-8 text-sm ${
          connected ? "bg-green-500/10 border border-green-500/30" : "bg-cyan-500/10 border border-cyan-500/20"
        }`}>
          {monitoring
            ? connected ? `✅ 세션 ${sessionId} 모니터링 중...` : "⏳ 데이터 대기 중..."
            : "💡 세션 ID를 입력하고 모니터링을 시작하세요"}
        </div>

        {/* 대시보드 그리드 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 현재 감정 (full-width) */}
          <div className="glass-card rounded-2xl p-6 lg:col-span-2">
            <h2 className="text-lg font-semibold mb-5 flex items-center gap-2">
              <Activity size={18} className="text-cyan-400" /> 현재 감정 상태
            </h2>
            <div className="flex items-center gap-10 flex-wrap justify-center">
              {/* 메인 이모지 */}
              <div className="text-center">
                <div className="text-7xl mb-2">{EMOTION_EMOJIS[dominant]}</div>
                <div className="text-xl font-semibold">{EMOTION_KO[dominant]}</div>
              </div>
              {/* 바 차트 */}
              <div className="flex-1 max-w-xl space-y-3">
                {EMOTIONS.map(e => (
                  <div key={e} className="flex items-center gap-3">
                    <span className="w-12 text-sm text-right">{EMOTION_KO[e]}</span>
                    <div className="flex-1 h-6 bg-white/10 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full bg-gradient-to-r ${BAR_GRADIENTS[e]} transition-all duration-300`}
                        style={{ width: `${probabilities[e]}%` }} />
                    </div>
                    <span className="w-14 text-right text-sm font-semibold">{probabilities[e].toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 차트들 (Chart.js) */}
          <ChartComponent
            emotions={EMOTIONS as unknown as string[]}
            emotionColors={EMOTION_COLORS}
            emotionKo={EMOTION_KO}
            probabilities={probabilities}
            timeLabels={timeLabels}
            timeData={timeData}
          />

          {/* 통계 요약 (full-width) */}
          <div className="glass-card rounded-2xl p-6 lg:col-span-2">
            <h2 className="text-lg font-semibold mb-5 flex items-center gap-2">
              <BarChart3 size={18} className="text-cyan-400" /> 세션 통계 요약
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-4">
              {EMOTIONS.map(e => (
                <div key={e} className="bg-white/5 rounded-xl p-4 text-center">
                  <div className="text-xl font-bold gradient-text">{avgForEmotion(e)}%</div>
                  <p className="text-xs text-gray-400 mt-1">{EMOTION_EMOJIS[e]} {EMOTION_KO[e]} 평균</p>
                </div>
              ))}
              <div className="bg-white/5 rounded-xl p-4 text-center">
                <div className="text-xl font-bold gradient-text">{dataPoints}</div>
                <p className="text-xs text-gray-400 mt-1">📊 데이터 포인트</p>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
