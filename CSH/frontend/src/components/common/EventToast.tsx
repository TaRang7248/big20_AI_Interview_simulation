"use client";
/**
 * EventToast — 서버 EventBus 이벤트를 실시간 알림으로 표시
 * =========================================================
 * WebSocket을 통해 수신된 이벤트를 토스트 형태로 화면에 렌더링합니다.
 * evaluation.completed, emotion.alert, report.generated 등
 * 주요 이벤트에 대해 사용자에게 시각적 피드백을 제공합니다.
 */

import { useState, useEffect, useCallback } from "react";
import { CheckCircle, AlertTriangle, BarChart3, Brain, FileText, X } from "lucide-react";

export interface EventToastItem {
  id: string;
  event_type: string;
  title: string;
  message: string;
  variant: "success" | "info" | "warning" | "error";
  timestamp: number;
}

/** 이벤트 타입 → 사용자 친화적 알림 매핑 */
function mapEventToToast(data: Record<string, unknown>): EventToastItem | null {
  const eventType = data.event_type as string;
  const eventData = (data.data || {}) as Record<string, unknown>;
  const id = (data.event_id as string) || `${Date.now()}-${Math.random()}`;

  switch (eventType) {
    case "evaluation.completed": {
      const score = eventData.score as number;
      return {
        id,
        event_type: eventType,
        title: "✅ 평가 완료",
        message: score != null ? `점수: ${score}/10` : "답변이 평가되었습니다",
        variant: "success",
        timestamp: Date.now(),
      };
    }
    case "emotion.alert": {
      const emotion = eventData.emotion as string;
      return {
        id,
        event_type: eventType,
        title: "🧠 감정 감지",
        message: emotion ? `감지된 감정: ${emotion}` : "감정 변화가 감지되었습니다",
        variant: "warning",
        timestamp: Date.now(),
      };
    }
    case "emotion.analyzed": {
      const dominant = eventData.dominant_emotion as string;
      if (!dominant || dominant === "neutral") return null; // 중립은 알림 불필요
      return {
        id,
        event_type: eventType,
        title: "🎭 감정 분석",
        message: `주요 감정: ${dominant}`,
        variant: "info",
        timestamp: Date.now(),
      };
    }
    case "report.generated":
      return {
        id,
        event_type: eventType,
        title: "📊 리포트 생성 완료",
        message: "면접 결과 리포트가 준비되었습니다",
        variant: "success",
        timestamp: Date.now(),
      };
    case "coding.analyzed":
      return {
        id,
        event_type: eventType,
        title: "💻 코드 분석 완료",
        message: "코딩 테스트 결과가 분석되었습니다",
        variant: "info",
        timestamp: Date.now(),
      };
    case "system.error":
      return {
        id,
        event_type: eventType,
        title: "⚠️ 시스템 오류",
        message: (eventData.message as string) || "오류가 발생했습니다",
        variant: "error",
        timestamp: Date.now(),
      };
    default:
      return null; // 알림 불필요 이벤트
  }
}

const ICON_MAP = {
  success: <CheckCircle size={18} />,
  info: <BarChart3 size={18} />,
  warning: <AlertTriangle size={18} />,
  error: <AlertTriangle size={18} />,
};

const COLOR_MAP = {
  success: "border-[rgba(0,255,136,0.5)] bg-[rgba(0,255,136,0.08)] text-[#00ff88]",
  info: "border-[rgba(0,217,255,0.5)] bg-[rgba(0,217,255,0.08)] text-[#00d9ff]",
  warning: "border-[rgba(255,193,7,0.5)] bg-[rgba(255,193,7,0.08)] text-[#ffc107]",
  error: "border-[rgba(244,67,54,0.5)] bg-[rgba(244,67,54,0.08)] text-[#f44336]",
};

// ========== 메인 컴포넌트 ==========

interface EventToastContainerProps {
  /** 외부에서 이벤트를 push 할 수 있는 ref callback */
  onPushEvent?: (handler: (raw: Record<string, unknown>) => void) => void;
}

export default function EventToastContainer({ onPushEvent }: EventToastContainerProps) {
  const [toasts, setToasts] = useState<EventToastItem[]>([]);

  const pushEvent = useCallback((raw: Record<string, unknown>) => {
    const toast = mapEventToToast(raw);
    if (!toast) return;
    setToasts((prev) => [...prev.slice(-4), toast]); // 최대 5개 유지
  }, []);

  // 부모에 핸들러 콜백 전달
  useEffect(() => {
    onPushEvent?.(pushEvent);
  }, [onPushEvent, pushEvent]);

  // 자동 제거 (5초)
  useEffect(() => {
    if (toasts.length === 0) return;
    const timer = setTimeout(() => {
      setToasts((prev) => prev.slice(1));
    }, 5000);
    return () => clearTimeout(timer);
  }, [toasts]);

  const dismiss = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-20 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl border backdrop-blur-md shadow-lg animate-slide-in ${COLOR_MAP[t.variant]}`}
        >
          <span className="mt-0.5 shrink-0">{ICON_MAP[t.variant]}</span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold">{t.title}</p>
            <p className="text-xs opacity-80 mt-0.5 truncate">{t.message}</p>
          </div>
          <button className="shrink-0 opacity-60 hover:opacity-100 transition" onClick={() => dismiss(t.id)}>
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
