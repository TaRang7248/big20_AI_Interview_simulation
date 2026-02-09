"use client";
import { ReactNode } from "react";
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

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="glass-card animate-fade-in relative"
        style={{ maxWidth, width: "90%" }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
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
