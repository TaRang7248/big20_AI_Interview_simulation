"use client";
import { ReactNode, useRef, useCallback, useEffect, useId } from "react";
import { X } from "lucide-react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  maxWidth?: string;
}

/**
 * 공통 모달 컴포넌트 ─────────────────────
 * 접근성(a11y) 준수:
 *   - role="dialog", aria-modal="true", aria-labelledby  
 *   - Escape 키로 닫기
 *   - 포커스 트랩 (Tab/Shift+Tab이 모달 내부에서만 순환)
 *   - 열릴 때 첫 포커스 가능 요소로 자동 포커스
 *   - body 스크롤 잠금
 * UX:
 *   - overlay 드래그 오작동 방지 (mousedown+click 이중 검증)
 *   - 닫힘 시 fade-out 애니메이션 (300ms)
 */
export default function Modal({ open, onClose, title, children, maxWidth = "480px" }: ModalProps) {
  const titleId = useId();                     // aria-labelledby용 고유 ID
  const overlayRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const mouseDownTarget = useRef<EventTarget | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null); // 모달 열기 전 포커스 복원용

  // ── Escape 키로 닫기 ──
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  // ── body 스크롤 잠금 + 열릴 때 포커스 이동, 닫힐 때 포커스 복원 ──
  useEffect(() => {
    if (open) {
      // 현재 포커스된 요소 저장 (닫힐 때 복원용)
      previousFocusRef.current = document.activeElement as HTMLElement;
      // body 스크롤 잠금
      document.body.style.overflow = "hidden";

      // 모달 내부 첫 포커스 가능 요소로 포커스 이동 (약간의 딜레이 후)
      requestAnimationFrame(() => {
        if (dialogRef.current) {
          const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
          );
          if (focusable.length > 0) {
            focusable[0].focus();
          } else {
            dialogRef.current.focus();  // 포커스 가능 요소가 없으면 다이얼로그 자체에 포커스
          }
        }
      });
    } else {
      // 닫힐 때 body 스크롤 복원 + 이전 포커스 복원
      document.body.style.overflow = "";
      if (previousFocusRef.current) {
        previousFocusRef.current.focus();
      }
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  // ── 포커스 트랩: Tab/Shift+Tab이 모달 내부에서만 순환하도록 ──
  const handleTabTrap = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== "Tab" || !dialogRef.current) return;

    const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (focusable.length === 0) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (e.shiftKey) {
      // Shift+Tab: 첫 요소에서 → 마지막 요소로 순환
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      // Tab: 마지막 요소에서 → 첫 요소로 순환
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }, []);

  // ── overlay 클릭 핸들러 (드래그 오작동 방지) ──
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    mouseDownTarget.current = e.target;
  }, []);

  const handleClick = useCallback((e: React.MouseEvent) => {
    if (e.target === overlayRef.current && mouseDownTarget.current === overlayRef.current) {
      onClose();
    }
  }, [onClose]);

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className="modal-overlay"
      onMouseDown={handleMouseDown}
      onClick={handleClick}
    >
      <div
        ref={dialogRef}
        role="dialog"                          // 접근성: 다이얼로그 역할 선언
        aria-modal="true"                      // 접근성: 모달임을 명시 (배경 비활성)
        aria-labelledby={titleId}              // 접근성: 제목과 연결
        tabIndex={-1}                          // 포커스 가능하도록 (fallback)
        onKeyDown={handleTabTrap}              // 포커스 트랩
        className="glass-card animate-fade-in relative"
        style={{ maxWidth, width: "90%", maxHeight: "90vh", overflowY: "auto" }}
      >
        <div className="flex items-center justify-between mb-6 sticky top-0 z-10">
          <h2 id={titleId} className="text-xl font-bold gradient-text">{title}</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-[rgba(255,255,255,0.1)] transition"
            aria-label="모달 닫기"
          >
            <X size={20} className="text-[var(--text-secondary)]" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
