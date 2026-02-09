"use client";
import { useRef, useEffect } from "react";
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, RadialLinearScale,
  PointElement, LineElement, ArcElement, Filler,
  Tooltip, Legend,
} from "chart.js";
import { Line, Doughnut, Radar } from "react-chartjs-2";

ChartJS.register(
  CategoryScale, LinearScale, RadialLinearScale,
  PointElement, LineElement, ArcElement, Filler,
  Tooltip, Legend,
);

interface Props {
  emotions: string[];
  emotionColors: Record<string, string>;
  emotionKo: Record<string, string>;
  probabilities: Record<string, number>;
  timeLabels: string[];
  timeData: Record<string, number[]>;
}

export default function EmotionCharts({
  emotions, emotionColors, emotionKo, probabilities, timeLabels, timeData,
}: Props) {
  /* ── 시계열 라인 차트 ── */
  const lineData = {
    labels: timeLabels,
    datasets: emotions.map(e => ({
      label: emotionKo[e] || e,
      data: timeData[e] || [],
      borderColor: emotionColors[e],
      backgroundColor: emotionColors[e]?.replace("0.8", "0.1"),
      borderWidth: 2, tension: 0.3, fill: false, pointRadius: 0,
    })),
  };
  const lineOpts = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: "#fff", font: { size: 11 } } } },
    scales: {
      x: { ticks: { color: "#8892b0", maxTicksLimit: 10 }, grid: { color: "rgba(255,255,255,0.08)" } },
      y: { min: 0, max: 100, ticks: { color: "#8892b0", callback: (v: unknown) => `${v}%` }, grid: { color: "rgba(255,255,255,0.08)" } },
    },
    interaction: { intersect: false as const, mode: "index" as const },
    animation: false as const,
  };

  /* ── 도넛 차트 ── */
  const doughnutData = {
    labels: emotions.map(e => emotionKo[e] || e),
    datasets: [{
      data: emotions.map(e => probabilities[e] || 0),
      backgroundColor: emotions.map(e => emotionColors[e]),
      borderColor: "#1e2a47", borderWidth: 2,
    }],
  };
  const doughnutOpts = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: "right" as const, labels: { color: "#fff", font: { size: 11 }, padding: 10 } } },
    cutout: "60%",
    animation: false as const,
  };

  /* ── 레이더 차트 ── */
  const radarData = {
    labels: emotions.map(e => emotionKo[e] || e),
    datasets: [{
      label: "감정 강도",
      data: emotions.map(e => probabilities[e] || 0),
      backgroundColor: "rgba(0,217,255,0.2)",
      borderColor: "rgba(0,217,255,0.8)",
      borderWidth: 2,
      pointBackgroundColor: emotions.map(e => emotionColors[e]),
      pointRadius: 4,
    }],
  };
  const radarOpts = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      r: {
        min: 0, max: 100,
        ticks: { display: false },
        grid: { color: "rgba(255,255,255,0.1)" },
        angleLines: { color: "rgba(255,255,255,0.1)" },
        pointLabels: { color: "#fff", font: { size: 11 } },
      },
    },
    animation: false as const,
  };

  return (
    <>
      {/* 시계열 그래프 (full-width) */}
      <div className="glass-card rounded-2xl p-6 lg:col-span-2">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          📈 감정 변화 추이 (시계열)
        </h2>
        <div className="h-[300px]">
          <Line data={lineData} options={lineOpts} />
        </div>
      </div>

      {/* 도넛 */}
      <div className="glass-card rounded-2xl p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">🥧 현재 감정 분포</h2>
        <div className="h-[300px]">
          <Doughnut data={doughnutData} options={doughnutOpts} />
        </div>
      </div>

      {/* 레이더 */}
      <div className="glass-card rounded-2xl p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">🎯 감정 레이더</h2>
        <div className="h-[300px]">
          <Radar data={radarData} options={radarOpts} />
        </div>
      </div>
    </>
  );
}
