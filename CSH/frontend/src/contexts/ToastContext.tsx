"use client";

/**
 * Toast Context (전역 토스트 알림 상태 관리)
 * ─────────────────────────────────────────────
 * 앱 전체에서 toast.success / toast.error / toast.warning / toast.info 호출로
 * 네이티브 alert() 없이 커스텀 토스트 알림을 표시할 수 있도록 Context API를 제공합니다.
 *
 * 추가로 confirm() 대체용 toast.confirm() 메서드를 제공합니다.
 * confirm()은 Promise 기반으로 동작하며, 사용자가 "확인" / "취소" 를 클릭할 때까지 대기합니다.
 *
 * 사용법:
 *   const { toast } = useToast();
 *   toast.success("저장 완료!");                          // 성공 토스트
 *   toast.error("오류 발생");                             // 에러 토스트
 *   const ok = await toast.confirm("정말 삭제할까요?");   // 확인 모달 (true/false 반환)
 */

import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from "react";
import ToastContainer, { type ToastItem, type ToastType } from "@/components/common/Toast";

// ── Confirm 모달용 타입 ──
interface ConfirmState {
  open: boolean;         // 모달 열림 여부
  message: string;       // 표시할 메시지 (줄바꿈 포함 가능)
  confirmText?: string;  // 확인 버튼 텍스트
  cancelText?: string;   // 취소 버튼 텍스트
}

// ── Toast 메서드 인터페이스 ──
interface ToastMethods {
  /** 성공 알림 (초록색) */
  success: (message: string, duration?: number) => void;
  /** 에러 알림 (빨간색) */
  error: (message: string, duration?: number) => void;
  /** 경고 알림 (노란색) */
  warning: (message: string, duration?: number) => void;
  /** 정보 알림 (파란색) */
  info: (message: string, duration?: number) => void;
  /**
   * 확인(Confirm) 모달 — window.confirm() 대체
   * @param message 표시할 메시지 (줄바꿈 가능)
   * @param confirmText 확인 버튼 텍스트 (기본: "확인")
   * @param cancelText 취소 버튼 텍스트 (기본: "취소")
   * @returns Promise<boolean> 사용자가 확인 → true, 취소 → false
   */
  confirm: (message: string, confirmText?: string, cancelText?: string) => Promise<boolean>;
}

// ── Context 정의 ──
const ToastContext = createContext<{ toast: ToastMethods } | null>(null);

/**
 * useToast() 훅 — 토스트/컨펌 기능 사용
 */
export function useToast(): { toast: ToastMethods } {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast는 ToastProvider 내에서만 사용 가능합니다.");
  return ctx;
}

/**
 * ToastProvider — 루트 레이아웃에서 감싸면 앱 전체에서 toast 사용 가능
 */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  // ── 토스트 목록 상태 ──
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  // ── Confirm 모달 상태 ──
  const [confirmState, setConfirmState] = useState<ConfirmState>({
    open: false,
    message: "",
    confirmText: "확인",
    cancelText: "취소",
  });
  // confirm()의 Promise resolve 함수를 ref로 보관  
  const confirmResolveRef = useRef<((value: boolean) => void) | null>(null);

  /**
   * 토스트 제거 (id 기반)
   */
  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  /**
   * 토스트 추가 (타입, 메시지, 지속시간)
   */
  const addToast = useCallback((type: ToastType, message: string, duration?: number) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setToasts((prev) => [...prev, { id, type, message, duration }]);
  }, []);

  /**
   * confirm 모달 열기 — Promise 반환
   */
  const openConfirm = useCallback(
    (message: string, confirmText?: string, cancelText?: string): Promise<boolean> => {
      return new Promise<boolean>((resolve) => {
        confirmResolveRef.current = resolve;
        setConfirmState({
          open: true,
          message,
          confirmText: confirmText ?? "확인",
          cancelText: cancelText ?? "취소",
        });
      });
    },
    []
  );

  /**
   * confirm 모달 닫기 (결과 반환)
   */
  const closeConfirm = (result: boolean) => {
    setConfirmState((prev) => ({ ...prev, open: false }));
    confirmResolveRef.current?.(result);
    confirmResolveRef.current = null;
  };

  // ── AuthContext 등 Provider 외부에서 발행한 커스텀 이벤트 수신 ──
  useEffect(() => {
    const handler = (e: Event) => {
      const { type, message } = (e as CustomEvent).detail;
      addToast(type, message);
    };
    window.addEventListener("toast-event", handler);
    return () => window.removeEventListener("toast-event", handler);
  }, [addToast]);

  // ── toast 메서드 객체 ──
  const toast: ToastMethods = {
    success: (msg, dur) => addToast("success", msg, dur),
    error: (msg, dur) => addToast("error", msg, dur ?? 5000),
    warning: (msg, dur) => addToast("warning", msg, dur),
    info: (msg, dur) => addToast("info", msg, dur),
    confirm: openConfirm,
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}

      {/* ── 토스트 컨테이너 (화면 우상단) ── */}
      <ToastContainer toasts={toasts} removeToast={removeToast} />

      {/* ── Confirm 모달 (window.confirm 대체) ── */}
      {confirmState.open && (
        <div
          className="fixed inset-0 z-[10000] flex items-center justify-center"
          style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
        >
          <div
            role="alertdialog"             // 접근성: 경고 다이얼로그
            aria-modal="true"
            aria-labelledby="confirm-title"
            className="glass-card p-6 rounded-2xl max-w-md w-[90vw] shadow-2xl"
            style={{
              border: "1px solid rgba(255,255,255,0.1)",
              animation: "fadeIn 0.2s ease-out",
            }}
          >
            {/* 경고 아이콘 */}
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-full" style={{ background: "rgba(245, 158, 11, 0.15)" }}>
                <svg className="w-6 h-6 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 id="confirm-title" className="text-lg font-semibold text-white">확인</h3>
            </div>

            {/* 메시지 본문 (줄바꿈 지원) */}
            <p className="text-white/80 text-sm leading-relaxed whitespace-pre-line mb-6">
              {confirmState.message}
            </p>

            {/* 액션 버튼 */}
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => closeConfirm(false)}
                className="px-5 py-2.5 rounded-xl text-sm font-medium
                  text-white/70 hover:text-white bg-white/5 hover:bg-white/10
                  border border-white/10 transition-all duration-200"
              >
                {confirmState.cancelText}
              </button>
              <button
                onClick={() => closeConfirm(true)}
                autoFocus  // 접근성: 열리자마자 확인 버튼에 포커스
                className="px-5 py-2.5 rounded-xl text-sm font-medium
                  text-white btn-gradient transition-all duration-200"
              >
                {confirmState.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  );
}
