"use client";

/**
 * Toast 알림 컴포넌트
 * ─────────────────────────────────────────
 * alert() / window.confirm() 대신 사용하는 커스텀 토스트 알림 시스템.
 * 4가지 타입: success(성공), error(에러), warning(경고), info(안내)
 * 자동 소멸(3~5초) + 수동 닫기(X 버튼) 지원.
 *
 * 사용법:
 *   import { useToast } from "@/contexts/ToastContext";
 *   const { toast } = useToast();
 *   toast.success("저장되었습니다!");
 *   toast.error("삭제 실패");
 */

import { useEffect, useState } from "react";
import { X, CheckCircle2, AlertCircle, AlertTriangle, Info } from "lucide-react";

// ── Toast 타입 정의 ──
export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastItem {
  id: string;              // 고유 식별자
  type: ToastType;         // 토스트 종류
  message: string;         // 표시할 메시지
  duration?: number;       // 자동 소멸 시간 (ms), 기본 4000
}

// ── 타입별 스타일 맵 ──
const TOAST_STYLES: Record<ToastType, { icon: typeof CheckCircle2; bg: string; border: string; text: string }> = {
  success: {
    icon: CheckCircle2,
    bg: "rgba(16, 185, 129, 0.15)",   // 초록 배경
    border: "rgba(16, 185, 129, 0.4)",
    text: "#10b981",
  },
  error: {
    icon: AlertCircle,
    bg: "rgba(239, 68, 68, 0.15)",    // 빨간 배경
    border: "rgba(239, 68, 68, 0.4)",
    text: "#ef4444",
  },
  warning: {
    icon: AlertTriangle,
    bg: "rgba(245, 158, 11, 0.15)",   // 노란 배경
    border: "rgba(245, 158, 11, 0.4)",
    text: "#f59e0b",
  },
  info: {
    icon: Info,
    bg: "rgba(59, 130, 246, 0.15)",   // 파란 배경
    border: "rgba(59, 130, 246, 0.4)",
    text: "#3b82f6",
  },
};

// ── 개별 Toast 아이템 렌더링 ──
function ToastItemComponent({ item, onRemove }: { item: ToastItem; onRemove: (id: string) => void }) {
  const [exiting, setExiting] = useState(false); // 종료 애니메이션 상태
  const style = TOAST_STYLES[item.type];
  const Icon = style.icon;

  // 자동 소멸 타이머 설정
  useEffect(() => {
    const duration = item.duration ?? 4000;
    // 소멸 300ms 전에 exit 애니메이션 시작
    const exitTimer = setTimeout(() => setExiting(true), duration - 300);
    // 실제 DOM에서 제거
    const removeTimer = setTimeout(() => onRemove(item.id), duration);
    return () => { clearTimeout(exitTimer); clearTimeout(removeTimer); };
  }, [item.id, item.duration, onRemove]);

  // 수동 닫기 (X 버튼 클릭)
  const handleClose = () => {
    setExiting(true);
    setTimeout(() => onRemove(item.id), 300);
  };

  return (
    <div
      role="alert"           // 접근성: 스크린 리더가 알림으로 인식
      aria-live="assertive"  // 접근성: 즉시 읽어줌
      style={{
        background: style.bg,
        borderColor: style.border,
      }}
      className={`
        flex items-start gap-3 px-4 py-3 rounded-xl border backdrop-blur-md
        shadow-lg shadow-black/20
        transition-all duration-300 ease-out
        ${exiting
          ? "opacity-0 translate-x-[100%]"   // 퇴장: 오른쪽으로 슬라이드 아웃
          : "opacity-100 translate-x-0"       // 진입: 제자리
        }
      `}
    >
      {/* 아이콘 */}
      <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: style.text }} />

      {/* 메시지 텍스트 */}
      <p className="text-sm text-white/90 flex-1 leading-relaxed break-words">
        {item.message}
      </p>

      {/* 닫기 버튼 */}
      <button
        onClick={handleClose}
        className="flex-shrink-0 p-0.5 rounded hover:bg-white/10 transition-colors"
        aria-label="알림 닫기"
      >
        <X className="w-4 h-4 text-white/50 hover:text-white/80" />
      </button>
    </div>
  );
}

// ── Toast 컨테이너 (화면 우상단에 고정) ──
export default function ToastContainer({
  toasts,
  removeToast,
}: {
  toasts: ToastItem[];
  removeToast: (id: string) => void;
}) {
  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed top-4 right-4 z-[9999] flex flex-col gap-3 w-[360px] max-w-[calc(100vw-2rem)]"
      aria-label="알림 목록"
    >
      {toasts.map((t) => (
        <ToastItemComponent key={t.id} item={t} onRemove={removeToast} />
      ))}
    </div>
  );
}
