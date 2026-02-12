"use client";
import { ReactNode, useRef, useCallback } from "react";
import { X } from "lucide-react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  maxWidth?: string;
}

export default function Modal({ open, onClose, title, children, maxWidth = "480px" }: ModalProps) {
  if (!open) return null;

  // ── overlay(배경) 직접 클릭 시에만 닫기 ──
  // mousedown이 overlay 자체에서 시작된 경우에만 닫도록 하여,
  // 모달 내부에서 드래그하다 overlay로 빠져나갔을 때 의도치 않게 닫히는 것을 방지
  const overlayRef = useRef<HTMLDivElement>(null);
  const mouseDownTarget = useRef<EventTarget | null>(null);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    mouseDownTarget.current = e.target;
  }, []);

  const handleClick = useCallback((e: React.MouseEvent) => {
    // mousedown과 click 모두 overlay 자체에서 발생한 경우에만 닫기
    if (e.target === overlayRef.current && mouseDownTarget.current === overlayRef.current) {
      onClose();
    }
  }, [onClose]);

  return (
    <div
      ref={overlayRef}
      className="modal-overlay"
      onMouseDown={handleMouseDown}
      onClick={handleClick}
    >
      <div
        className="glass-card animate-fade-in relative"
        style={{ maxWidth, width: "90%", maxHeight: "90vh", overflowY: "auto" }}
      >
        <div className="flex items-center justify-between mb-6 sticky top-0 z-10">
          <h2 className="text-xl font-bold gradient-text">{title}</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-[rgba(255,255,255,0.1)] transition"
          >
            <X size={20} className="text-[var(--text-secondary)]" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
