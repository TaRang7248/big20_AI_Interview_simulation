"use client";

import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  PieChart, Pie, Cell,
  ResponsiveContainer,
  AreaChart, Area,
} from "recharts";

/* ============================== */
/*        타입 정의                */
/* ============================== */

interface StarAnalysis {
  situation: { count: number };
  task: { count: number };
  action: { count: number };
  result: { count: number };
}

interface LLMEvaluation {
  answer_count: number;
  average_scores: {
    specificity: number;
    logic: number;
    technical: number;
    star: number;
    communication: number;
  };
  total_average: number;
  all_evaluations: Array<{
    scores?: Record<string, number>;
    total_score?: number;
    question?: string;
    answer?: string;
    brief_feedback?: string;
    strengths?: string[];
    improvements?: string[];
  }>;
}

interface EmotionStats {
  dominant_emotion?: string;
  probabilities?: Record<string, number>;
  emotion?: Record<string, number>;
}

interface SpeechAnalysis {
  total_words?: number;
  total_duration_sec?: number;
  avg_spm?: number;
  avg_wpm?: number;
  turn_count?: number;
  turns?: Array<{
    turn_idx: number;
    word_count: number;
    duration_sec: number;
    spm: number;
  }>;
}

interface GazeAnalysis {
  avg_eye_contact_ratio?: number;
  total_frames?: number;
  turns?: Array<{
    turn_idx: number;
    eye_contact_ratio: number;
    frame_count: number;
  }>;
}

export interface ReportData {
  session_id: string;
  generated_at: string;
  metrics: {
    total: number;
    avg_length: number;
    total_chars?: number;
  };
  star_analysis: StarAnalysis;
  keywords: {
    tech_keywords: [string, number][];
    general_keywords: [string, number][];
  };
  emotion_stats?: EmotionStats | null;
  feedback: string[];
  llm_evaluation?: LLMEvaluation;
  speech_analysis?: SpeechAnalysis;
  gaze_analysis?: GazeAnalysis;
}

/* ============================== */
/*        색상 팔레트              */
/* ============================== */

const COLORS = {
  cyan: "#00d9ff",
  green: "#00ff88",
  purple: "#a78bfa",
  orange: "#f97316",
  pink: "#ec4899",
  yellow: "#fbbf24",
  red: "#f87171",
  blue: "#60a5fa",
};

const PIE_PALETTE = [
  COLORS.cyan, COLORS.green, COLORS.purple,
  COLORS.orange, COLORS.pink, COLORS.yellow,
  COLORS.red, COLORS.blue,
];

const EMOTION_COLORS: Record<string, string> = {
  happy: "#fbbf24",
  sad: "#60a5fa",
  angry: "#f87171",
  fear: "#a78bfa",
  surprise: "#f97316",
  disgust: "#10b981",
  neutral: "#94a3b8",
};

const SCORE_LABELS: Record<string, string> = {
  specificity: "구체성",
  logic: "논리성",
  technical: "기술이해도",
  star: "STAR",
  communication: "전달력",
};

/* ============================== */
/*        서브 차트 컴포넌트        */
/* ============================== */

/** 1) 역량 레이더 차트 (5가지 평가 기준) */
function EvalRadarChart({ scores }: { scores: Record<string, number> }) {
  const data = Object.entries(scores).map(([key, val]) => ({
    subject: SCORE_LABELS[key] || key,
    value: val,
    fullMark: 5,
  }));

  return (
    <div className="glass-card">
      <h3 className="text-sm font-bold gradient-text mb-4">🎯 역량 레이더</h3>
      <ResponsiveContainer width="100%" height={280}>
        <RadarChart data={data}>
          <PolarGrid stroke="rgba(255,255,255,0.1)" />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fill: "#8892b0", fontSize: 12 }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 5]}
            tick={{ fill: "#8892b0", fontSize: 10 }}
          />
          <Radar
            dataKey="value"
            stroke={COLORS.cyan}
            fill={COLORS.cyan}
            fillOpacity={0.25}
            strokeWidth={2}
          />
          <Tooltip
            contentStyle={{
              background: "#1a1a2e",
              border: `1px solid ${COLORS.cyan}`,
              borderRadius: 8,
              color: "#fff",
            }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** 2) 답변별 점수 막대 그래프 */
function EvalBarChart({ evaluations }: { evaluations: LLMEvaluation["all_evaluations"] }) {
  const data = evaluations.map((ev, idx) => ({
    name: `Q${idx + 1}`,
    구체성: ev.scores?.specificity ?? 0,
    논리성: ev.scores?.logic ?? 0,
    기술이해도: ev.scores?.technical ?? 0,
    STAR: ev.scores?.star ?? 0,
    전달력: ev.scores?.communication ?? 0,
  }));

  return (
    <div className="glass-card">
      <h3 className="text-sm font-bold gradient-text mb-4">📊 답변별 평가 점수</h3>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} barGap={2}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis dataKey="name" tick={{ fill: "#8892b0", fontSize: 12 }} />
          <YAxis domain={[0, 5]} tick={{ fill: "#8892b0", fontSize: 10 }} />
          <Tooltip
            contentStyle={{
              background: "#1a1a2e",
              border: `1px solid ${COLORS.cyan}`,
              borderRadius: 8,
              color: "#fff",
            }}
          />
          <Legend wrapperStyle={{ color: "#8892b0", fontSize: 11 }} />
          <Bar dataKey="구체성" fill={COLORS.cyan} radius={[3, 3, 0, 0]} />
          <Bar dataKey="논리성" fill={COLORS.green} radius={[3, 3, 0, 0]} />
          <Bar dataKey="기술이해도" fill={COLORS.purple} radius={[3, 3, 0, 0]} />
          <Bar dataKey="STAR" fill={COLORS.orange} radius={[3, 3, 0, 0]} />
          <Bar dataKey="전달력" fill={COLORS.pink} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** 3) STAR 기법 분석 바 차트 */
function StarBarChart({ star }: { star: StarAnalysis }) {
  const data = [
    { name: "상황 (S)", count: star.situation.count, fill: COLORS.cyan },
    { name: "과제 (T)", count: star.task.count, fill: COLORS.green },
    { name: "행동 (A)", count: star.action.count, fill: COLORS.purple },
    { name: "결과 (R)", count: star.result.count, fill: COLORS.orange },
  ];

  return (
    <div className="glass-card">
      <h3 className="text-sm font-bold gradient-text mb-4">⭐ STAR 기법 분석</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} layout="vertical" barSize={24}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis type="number" tick={{ fill: "#8892b0", fontSize: 10 }} />
          <YAxis
            dataKey="name"
            type="category"
            tick={{ fill: "#8892b0", fontSize: 12 }}
            width={80}
          />
          <Tooltip
            contentStyle={{
              background: "#1a1a2e",
              border: `1px solid ${COLORS.cyan}`,
              borderRadius: 8,
              color: "#fff",
            }}
          />
          <Bar dataKey="count" radius={[0, 6, 6, 0]}>
            {data.map((entry, idx) => (
              <Cell key={idx} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** 4) 감정 분석 파이 차트 */
function EmotionPieChart({ emotions }: { emotions: EmotionStats }) {
  const probs = emotions.probabilities || emotions.emotion || {};
  const data = Object.entries(probs)
    .filter(([, v]) => v > 0.01)
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      value: Math.round(value * 100),
    }));

  if (data.length === 0) return null;

  return (
    <div className="glass-card">
      <h3 className="text-sm font-bold gradient-text mb-4">😊 감정 분석</h3>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={90}
            dataKey="value"
            label={({ name, value }) => `${name} ${value}%`}
            labelLine={{ stroke: "rgba(255,255,255,0.3)" }}
          >
            {data.map((entry, idx) => (
              <Cell
                key={idx}
                fill={EMOTION_COLORS[entry.name.toLowerCase()] || PIE_PALETTE[idx % PIE_PALETTE.length]}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: "#1a1a2e",
              border: `1px solid ${COLORS.cyan}`,
              borderRadius: 8,
              color: "#fff",
            }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

/** 5) 기술 키워드 바 차트 */
function KeywordBarChart({ techKw, generalKw }: {
  techKw: [string, number][];
  generalKw: [string, number][];
}) {
  const techData = techKw.slice(0, 8).map(([name, count]) => ({ name, count }));
  const genData = generalKw.slice(0, 8).map(([name, count]) => ({ name, count }));
  const combined = [...techData, ...genData]
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);

  if (combined.length === 0) return null;

  return (
    <div className="glass-card">
      <h3 className="text-sm font-bold gradient-text mb-4">🔑 주요 키워드</h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={combined} barSize={20}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis
            dataKey="name"
            tick={{ fill: "#8892b0", fontSize: 10 }}
            interval={0}
            angle={-30}
            textAnchor="end"
            height={60}
          />
          <YAxis tick={{ fill: "#8892b0", fontSize: 10 }} />
          <Tooltip
            contentStyle={{
              background: "#1a1a2e",
              border: `1px solid ${COLORS.cyan}`,
              borderRadius: 8,
              color: "#fff",
            }}
          />
          <Bar dataKey="count" fill={COLORS.green} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** 6) 발화 속도 영역 차트 (턴별 SPM) */
function SpeechAreaChart({ speech }: { speech: SpeechAnalysis }) {
  const turns = speech.turns || [];
  if (turns.length === 0) return null;

  const data = turns.map((t) => ({
    name: `Q${t.turn_idx + 1}`,
    SPM: Math.round(t.spm),
    단어수: t.word_count,
  }));

  return (
    <div className="glass-card">
      <h3 className="text-sm font-bold gradient-text mb-4">🎤 발화 속도 (SPM)</h3>
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="spmGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={COLORS.cyan} stopOpacity={0.3} />
              <stop offset="95%" stopColor={COLORS.cyan} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis dataKey="name" tick={{ fill: "#8892b0", fontSize: 12 }} />
          <YAxis tick={{ fill: "#8892b0", fontSize: 10 }} />
          <Tooltip
            contentStyle={{
              background: "#1a1a2e",
              border: `1px solid ${COLORS.cyan}`,
              borderRadius: 8,
              color: "#fff",
            }}
          />
          <Legend wrapperStyle={{ color: "#8892b0", fontSize: 11 }} />
          <Area
            type="monotone"
            dataKey="SPM"
            stroke={COLORS.cyan}
            fill="url(#spmGrad)"
            strokeWidth={2}
          />
          <Area
            type="monotone"
            dataKey="단어수"
            stroke={COLORS.green}
            fill="none"
            strokeWidth={2}
            strokeDasharray="5 5"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** 7) 시선 추적 바 차트 (턴별 아이컨택 비율) */
function GazeBarChart({ gaze }: { gaze: GazeAnalysis }) {
  const turns = gaze.turns || [];
  if (turns.length === 0) return null;

  const data = turns.map((t) => ({
    name: `Q${t.turn_idx + 1}`,
    비율: Math.round((t.eye_contact_ratio || 0) * 100),
  }));

  return (
    <div className="glass-card">
      <h3 className="text-sm font-bold gradient-text mb-4">👁️ 시선 추적 (아이컨택 %)</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} barSize={28}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis dataKey="name" tick={{ fill: "#8892b0", fontSize: 12 }} />
          <YAxis domain={[0, 100]} tick={{ fill: "#8892b0", fontSize: 10 }} />
          <Tooltip
            contentStyle={{
              background: "#1a1a2e",
              border: `1px solid ${COLORS.cyan}`,
              borderRadius: 8,
              color: "#fff",
            }}
          />
          <Bar dataKey="비율" fill={COLORS.purple} radius={[4, 4, 0, 0]}>
            {data.map((entry, idx) => (
              <Cell
                key={idx}
                fill={entry.비율 >= 60 ? COLORS.green : entry.비율 >= 30 ? COLORS.yellow : COLORS.red}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ============================== */
/*     종합 스코어 카드              */
/* ============================== */

function ScoreCard({ label, value, unit, icon }: {
  label: string; value: number | string; unit?: string; icon: string;
}) {
  return (
    <div className="glass-card flex flex-col items-center justify-center min-h-[120px]">
      <span className="text-2xl mb-1">{icon}</span>
      <span className="text-2xl font-bold gradient-text">{value}{unit}</span>
      <span className="text-xs text-[var(--text-secondary)] mt-1">{label}</span>
    </div>
  );
}

/* ============================== */
/*     메인 리포트 대시보드          */
/* ============================== */

export default function InterviewReportCharts({ report }: { report: ReportData }) {
  const evalScores = report.llm_evaluation?.average_scores;
  const totalAvg = report.llm_evaluation?.total_average ?? 0;
  const allEvals = report.llm_evaluation?.all_evaluations ?? [];

  // 등급 계산
  const grade =
    totalAvg >= 4.5 ? "S" :
    totalAvg >= 3.5 ? "A" :
    totalAvg >= 2.5 ? "B" :
    totalAvg >= 1.5 ? "C" : "D";

  const gradeColors: Record<string, string> = {
    S: "text-yellow-400",
    A: "text-green-400",
    B: "text-cyan-400",
    C: "text-orange-400",
    D: "text-red-400",
  };

  return (
    <div className="space-y-6">
      {/* ── 헤더 ── */}
      <div className="text-center">
        <h2 className="text-3xl font-bold gradient-text mb-2">📊 면접 분석 리포트</h2>
        <p className="text-sm text-[var(--text-secondary)]">
          {new Date(report.generated_at).toLocaleString("ko-KR")} 생성
        </p>
      </div>

      {/* ── 종합 스코어 카드 ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <ScoreCard icon="🏆" label="종합 등급" value={grade} />
        <ScoreCard icon="📈" label="평균 점수" value={totalAvg.toFixed(1)} unit="/5" />
        <ScoreCard icon="💬" label="총 답변 수" value={report.metrics.total} unit="개" />
        <ScoreCard
          icon="📝"
          label="평균 답변 길이"
          value={Math.round(report.metrics.avg_length)}
          unit="자"
        />
      </div>

      {/* ── 등급 배지 ── */}
      {totalAvg > 0 && (
        <div className="glass-card text-center">
          <div className={`text-7xl font-black ${gradeColors[grade] || "text-white"} drop-shadow-lg`}>
            {grade}
          </div>
          <p className="text-sm text-[var(--text-secondary)] mt-2">
            종합 평균 {totalAvg.toFixed(1)}점 / 5점 만점
          </p>
        </div>
      )}

      {/* ── 차트 그리드 ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 역량 레이더 */}
        {evalScores && <EvalRadarChart scores={evalScores} />}

        {/* STAR 분석 */}
        {report.star_analysis && <StarBarChart star={report.star_analysis} />}

        {/* 답변별 평가 */}
        {allEvals.length > 0 && <EvalBarChart evaluations={allEvals} />}

        {/* 감정 분석 */}
        {report.emotion_stats && <EmotionPieChart emotions={report.emotion_stats} />}

        {/* 키워드 */}
        {report.keywords && (
          <KeywordBarChart
            techKw={report.keywords.tech_keywords || []}
            generalKw={report.keywords.general_keywords || []}
          />
        )}

        {/* 발화 속도 */}
        {report.speech_analysis && <SpeechAreaChart speech={report.speech_analysis} />}

        {/* 시선 추적 */}
        {report.gaze_analysis && <GazeBarChart gaze={report.gaze_analysis} />}
      </div>

      {/* ── 답변별 상세 피드백 ── */}
      {allEvals.length > 0 && (
        <div className="glass-card">
          <h3 className="text-sm font-bold gradient-text mb-4">💡 답변별 피드백</h3>
          <div className="space-y-4">
            {allEvals.map((ev, idx) => (
              <div
                key={idx}
                className="border border-[rgba(255,255,255,0.06)] rounded-xl p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-[var(--cyan)]">
                    Q{idx + 1}
                  </span>
                  <span className="text-xs px-3 py-1 rounded-full bg-[rgba(0,217,255,0.1)] text-[var(--cyan)]">
                    {ev.total_score ?? "—"}점 / 25점
                  </span>
                </div>
                {ev.brief_feedback && (
                  <p className="text-sm text-[var(--text-secondary)] mb-2">
                    {ev.brief_feedback}
                  </p>
                )}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {ev.strengths && ev.strengths.length > 0 && (
                    <div>
                      <span className="text-[var(--green)]">✅ 강점</span>
                      <ul className="mt-1 space-y-0.5 text-[var(--text-secondary)]">
                        {ev.strengths.map((s, i) => (
                          <li key={i}>• {s}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {ev.improvements && ev.improvements.length > 0 && (
                    <div>
                      <span className="text-[var(--warning)]">📌 개선점</span>
                      <ul className="mt-1 space-y-0.5 text-[var(--text-secondary)]">
                        {ev.improvements.map((s, i) => (
                          <li key={i}>• {s}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 종합 피드백 ── */}
      {report.feedback && report.feedback.length > 0 && (
        <div className="glass-card">
          <h3 className="text-sm font-bold gradient-text mb-4">📋 종합 피드백</h3>
          <ul className="space-y-2">
            {report.feedback.map((fb, idx) => (
              <li
                key={idx}
                className="flex items-start gap-2 text-sm text-[var(--text-secondary)]"
              >
                <span className="shrink-0">{fb.startsWith("✅") || fb.startsWith("📝") || fb.startsWith("💡") || fb.startsWith("🔧") ? "" : "•"}</span>
                <span>{fb}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
