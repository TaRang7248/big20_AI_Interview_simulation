"use client";
import { useState, useRef, useEffect, useCallback, Suspense, type PointerEvent as RPointerEvent, type MouseEvent as RMouseEvent } from "react";
import { useSearchParams } from "next/navigation";
import Header from "@/components/common/Header";
import { whiteboardApi } from "@/lib/api";
import {
  Pencil, Minus, Square, Circle, ArrowRight, Type, Eraser,
  Undo2, Redo2, Trash2, Download, Send, Loader2, Palette
} from "lucide-react";

/* ───────── 타입 ───────── */
type Tool = "pen" | "line" | "rect" | "circle" | "arrow" | "text" | "eraser";

interface Point { x: number; y: number }

interface DrawElement {
  id: string;
  tool: Tool;
  points: Point[];
  color: string;
  lineWidth: number;
  text?: string;
}

interface AnalysisResult {
  error?: string;
  score?: number | string;
  evaluation?: Record<string, string>;
  feedback?: string;
  [key: string]: unknown;
}

/* ───────── 상수 ───────── */
const TOOLS: { value: Tool; icon: typeof Pencil; label: string }[] = [
  { value: "pen", icon: Pencil, label: "펜" },
  { value: "line", icon: Minus, label: "직선" },
  { value: "rect", icon: Square, label: "사각형" },
  { value: "circle", icon: Circle, label: "원" },
  { value: "arrow", icon: ArrowRight, label: "화살표" },
  { value: "text", icon: Type, label: "텍스트" },
  { value: "eraser", icon: Eraser, label: "지우개" },
];

const COLORS = ["#ffffff", "#00d9ff", "#00ff88", "#ff6b6b", "#ffd93d", "#6c5ce7", "#fd79a8", "#a29bfe"];
const LINE_WIDTHS = [1, 2, 3, 5, 8];

export default function WhiteboardPageWrapper() {
  return <Suspense fallback={<div className="h-screen bg-[#1e1e2e] flex items-center justify-center text-gray-400">로딩 중...</div>}><WhiteboardPage /></Suspense>;
}

function WhiteboardPage() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session") || "";

  /* 상태 */
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [tool, setTool] = useState<Tool>("pen");
  const [color, setColor] = useState("#ffffff");
  const [lineWidth, setLineWidth] = useState(3);
  const [elements, setElements] = useState<DrawElement[]>([]);
  const [redoStack, setRedoStack] = useState<DrawElement[]>([]);
  const [drawing, setDrawing] = useState(false);
  const [currentElement, setCurrentElement] = useState<DrawElement | null>(null);

  // 문제
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [problemText, setProblemText] = useState("");
  const [loadingProblem, setLoadingProblem] = useState(false);

  // 분석
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  /* 카테고리 로드 */
  useEffect(() => {
    whiteboardApi.getCategories().then(setCategories).catch(() => {});
  }, []);

  /* uid */
  const uid = () => `el_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;

  /* ──── Canvas 렌더 ──── */
  const renderCanvas = useCallback(() => {
    const cvs = canvasRef.current;
    if (!cvs) return;
    const ctx = cvs.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, cvs.width, cvs.height);

    const draw = (el: DrawElement) => {
      ctx.strokeStyle = el.tool === "eraser" ? "#1e1e2e" : el.color;
      ctx.fillStyle = el.color;
      ctx.lineWidth = el.tool === "eraser" ? el.lineWidth * 3 : el.lineWidth;
      ctx.lineCap = "round"; ctx.lineJoin = "round";

      const pts = el.points;
      if (pts.length < 1) return;
      const [s, e] = [pts[0], pts[pts.length - 1]];

      switch (el.tool) {
        case "pen":
        case "eraser":
          ctx.beginPath();
          ctx.moveTo(pts[0].x, pts[0].y);
          pts.forEach(p => ctx.lineTo(p.x, p.y));
          ctx.stroke();
          break;
        case "line":
          ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(e.x, e.y); ctx.stroke();
          break;
        case "rect":
          ctx.strokeRect(s.x, s.y, e.x - s.x, e.y - s.y);
          break;
        case "circle": {
          const rx = Math.abs(e.x - s.x) / 2, ry = Math.abs(e.y - s.y) / 2;
          const cx = Math.min(s.x, e.x) + rx, cy = Math.min(s.y, e.y) + ry;
          ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2); ctx.stroke();
          break;
        }
        case "arrow": {
          ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(e.x, e.y); ctx.stroke();
          const angle = Math.atan2(e.y - s.y, e.x - s.x);
          const headLen = 16;
          ctx.beginPath();
          ctx.moveTo(e.x, e.y);
          ctx.lineTo(e.x - headLen * Math.cos(angle - 0.4), e.y - headLen * Math.sin(angle - 0.4));
          ctx.moveTo(e.x, e.y);
          ctx.lineTo(e.x - headLen * Math.cos(angle + 0.4), e.y - headLen * Math.sin(angle + 0.4));
          ctx.stroke();
          break;
        }
        case "text":
          if (el.text) {
            ctx.font = `${el.lineWidth * 5 + 10}px 'Pretendard', sans-serif`;
            ctx.fillText(el.text, s.x, s.y);
          }
          break;
      }
    };

    elements.forEach(draw);
    if (currentElement) draw(currentElement);
  }, [elements, currentElement]);

  useEffect(() => { renderCanvas(); }, [renderCanvas]);

  /* 캔버스 크기 */
  useEffect(() => {
    const resize = () => {
      const cvs = canvasRef.current;
      if (!cvs) return;
      const parent = cvs.parentElement!;
      cvs.width = parent.clientWidth;
      cvs.height = parent.clientHeight;
      renderCanvas();
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [renderCanvas]);

  /* ──── 이벤트 핸들러 ──── */
  const getPos = (e: RPointerEvent<HTMLCanvasElement>): Point => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const onPointerDown = (e: RPointerEvent<HTMLCanvasElement>) => {
    if (tool === "text") {
      const pos = getPos(e);
      const text = prompt("텍스트 입력:");
      if (text) {
        const el: DrawElement = { id: uid(), tool: "text", points: [pos], color, lineWidth, text };
        setElements(prev => [...prev, el]);
        setRedoStack([]);
      }
      return;
    }
    setDrawing(true);
    const pos = getPos(e);
    const el: DrawElement = { id: uid(), tool, points: [pos], color, lineWidth };
    setCurrentElement(el);
  };

  const onPointerMove = (e: RPointerEvent<HTMLCanvasElement>) => {
    if (!drawing || !currentElement) return;
    const pos = getPos(e);
    if (currentElement.tool === "pen" || currentElement.tool === "eraser") {
      setCurrentElement(prev => prev ? { ...prev, points: [...prev.points, pos] } : null);
    } else {
      setCurrentElement(prev => prev ? { ...prev, points: [prev.points[0], pos] } : null);
    }
  };

  const onPointerUp = () => {
    if (currentElement) {
      setElements(prev => [...prev, currentElement]);
      setRedoStack([]);
    }
    setCurrentElement(null);
    setDrawing(false);
  };

  /* ──── 기능 ──── */
  const undo = () => {
    if (!elements.length) return;
    setRedoStack(prev => [...prev, elements[elements.length - 1]]);
    setElements(prev => prev.slice(0, -1));
  };

  const redo = () => {
    if (!redoStack.length) return;
    setElements(prev => [...prev, redoStack[redoStack.length - 1]]);
    setRedoStack(prev => prev.slice(0, -1));
  };

  const clearAll = () => { if (confirm("전체 삭제하시겠습니까?")) { setElements([]); setRedoStack([]); } };

  const downloadImage = () => {
    const cvs = canvasRef.current;
    if (!cvs) return;
    // 배경 추가
    const tmpCanvas = document.createElement("canvas");
    tmpCanvas.width = cvs.width; tmpCanvas.height = cvs.height;
    const ctx = tmpCanvas.getContext("2d")!;
    ctx.fillStyle = "#1e1e2e";
    ctx.fillRect(0, 0, tmpCanvas.width, tmpCanvas.height);
    ctx.drawImage(cvs, 0, 0);
    const a = document.createElement("a");
    a.download = "whiteboard.png";
    a.href = tmpCanvas.toDataURL();
    a.click();
  };

  /* 문제 생성 */
  const generateProblem = async () => {
    if (!selectedCategory) return;
    setLoadingProblem(true);
    try {
      const res = await whiteboardApi.generate(selectedCategory);
      setProblemText(typeof res === "string" ? res : JSON.stringify(res, null, 2));
    } catch { setProblemText("문제 생성에 실패했습니다."); }
    finally { setLoadingProblem(false); }
  };

  /* AI 분석 */
  const analyzeWhiteboard = async () => {
    const cvs = canvasRef.current;
    if (!cvs) return;
    setAnalyzing(true);
    try {
      const blob = await new Promise<Blob>((res, rej) => cvs.toBlob(b => b ? res(b) : rej("toBlob failed"), "image/png"));
      const formData = new FormData();
      formData.append("image", blob, "whiteboard.png");
      if (sessionId) formData.append("session_id", sessionId);

      const resp = await fetch("/api/whiteboard/analyze", {
        method: "POST",
        headers: { Authorization: `Bearer ${sessionStorage.getItem("access_token") || ""}` },
        body: formData,
      });
      const data = await resp.json();
      setAnalysisResult(data);
    } catch {
      setAnalysisResult({ error: "분석에 실패했습니다." });
    } finally { setAnalyzing(false); }
  };

  /* ──── 렌더 ──── */
  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[#1e1e2e]">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#2d2d40] border-b border-[#3c3c50] shrink-0">
        <span className="text-cyan-400 font-semibold text-sm flex items-center gap-2">📐 화이트보드 아키텍처 설계</span>

        <div className="flex items-center gap-2">
          {/* 카테고리 & 문제 생성 */}
          <select value={selectedCategory} onChange={e => setSelectedCategory(e.target.value)}
            className="bg-[#252536] text-[#ccc] border border-[#3c3c50] px-2 py-1 rounded text-xs">
            <option value="">카테고리 선택...</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <button onClick={generateProblem} disabled={loadingProblem || !selectedCategory}
            className="px-3 py-1 rounded text-xs bg-cyan-600/20 text-cyan-400 hover:bg-cyan-600/40 border border-cyan-600/30 transition disabled:opacity-40">
            {loadingProblem ? "생성 중..." : "문제 생성"}
          </button>

          <div className="w-px h-5 bg-[#3c3c50] mx-1" />

          <button onClick={analyzeWhiteboard} disabled={analyzing || elements.length === 0}
            className="flex items-center gap-1 px-4 py-1.5 rounded text-xs bg-gradient-to-r from-cyan-500 to-green-500 text-white hover:brightness-110 transition disabled:opacity-40">
            {analyzing ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
            AI 분석
          </button>
        </div>
      </div>

      {/* 메인 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 도구 사이드바 */}
        <div className="w-14 bg-[#252536] border-r border-[#3c3c50] flex flex-col items-center py-3 gap-1 shrink-0">
          {TOOLS.map(t => {
            const Icon = t.icon;
            return (
              <button key={t.value} onClick={() => setTool(t.value)} title={t.label}
                className={`w-10 h-10 rounded-lg flex items-center justify-center transition ${
                  tool === t.value
                    ? "bg-cyan-500/20 text-cyan-400 ring-1 ring-cyan-500/50"
                    : "text-[#858585] hover:text-white hover:bg-[#3c3c50]"
                }`}>
                <Icon size={18} />
              </button>
            );
          })}

          <div className="border-t border-[#3c3c50] w-8 my-2" />

          {/* 색상 팔레트 */}
          <div className="flex flex-col gap-1 items-center">
            {COLORS.map(c => (
              <button key={c} onClick={() => setColor(c)}
                className={`w-6 h-6 rounded-full border-2 transition ${color === c ? "border-white scale-110" : "border-transparent"}`}
                style={{ backgroundColor: c }} />
            ))}
          </div>

          <div className="border-t border-[#3c3c50] w-8 my-2" />

          {/* 선 굵기 */}
          {LINE_WIDTHS.map(w => (
            <button key={w} onClick={() => setLineWidth(w)} title={`${w}px`}
              className={`w-8 h-6 flex items-center justify-center rounded transition ${
                lineWidth === w ? "bg-cyan-500/20" : "hover:bg-[#3c3c50]"
              }`}>
              <div className="rounded-full bg-white" style={{ width: w * 3 + 4, height: w + 1 }} />
            </button>
          ))}

          <div className="flex-1" />

          {/* 하단 도구 */}
          <button onClick={undo} title="실행 취소 (Ctrl+Z)" className="w-10 h-10 rounded-lg text-[#858585] hover:text-white hover:bg-[#3c3c50] flex items-center justify-center">
            <Undo2 size={16} />
          </button>
          <button onClick={redo} title="다시 실행 (Ctrl+Y)" className="w-10 h-10 rounded-lg text-[#858585] hover:text-white hover:bg-[#3c3c50] flex items-center justify-center">
            <Redo2 size={16} />
          </button>
          <button onClick={clearAll} title="전체 삭제" className="w-10 h-10 rounded-lg text-red-400/60 hover:text-red-400 hover:bg-red-500/10 flex items-center justify-center">
            <Trash2 size={16} />
          </button>
          <button onClick={downloadImage} title="이미지 저장" className="w-10 h-10 rounded-lg text-[#858585] hover:text-white hover:bg-[#3c3c50] flex items-center justify-center">
            <Download size={16} />
          </button>
        </div>

        {/* 캔버스 영역 */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* 문제 표시 */}
          {problemText && (
            <div className="px-4 py-3 bg-[#252536] border-b border-[#3c3c50] text-sm text-[#ccc] max-h-[120px] overflow-y-auto whitespace-pre-wrap">
              <span className="text-cyan-400 font-semibold mr-2">📋 문제:</span>{problemText}
            </div>
          )}

          <div className="flex-1 relative overflow-hidden">
            <canvas
              ref={canvasRef}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerLeave={onPointerUp}
              className={`absolute inset-0 ${tool === "eraser" ? "cursor-cell" : tool === "text" ? "cursor-text" : "cursor-crosshair"}`}
            />
          </div>
        </div>

        {/* AI 분석 결과 패널 */}
        {analysisResult && (
          <div className="w-[380px] bg-[#252536] border-l border-[#3c3c50] overflow-y-auto shrink-0">
            <div className="p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-white">🤖 AI 아키텍처 분석</h3>
                <button onClick={() => setAnalysisResult(null)} className="text-[#858585] hover:text-white text-xs">✕</button>
              </div>

              {"error" in analysisResult ? (
                <p className="text-red-400 text-sm">{String(analysisResult.error)}</p>
              ) : (
                <div className="space-y-4 text-sm text-[#ccc]">
                  {/* 점수 */}
                  {analysisResult.score != null && (
                    <div className="text-center py-3">
                      <div className="text-4xl font-bold gradient-text">{String(analysisResult.score)}</div>
                      <p className="text-xs text-[#858585] mt-1">종합 점수</p>
                    </div>
                  )}

                  {/* 평가 항목들 */}
                  {analysisResult.evaluation && typeof analysisResult.evaluation === "object" && (
                    <div className="space-y-2">
                      {Object.entries(analysisResult.evaluation as Record<string, unknown>).map(([k, v]) => (
                        <div key={k} className="bg-[#1e1e2e] rounded-lg p-3">
                          <p className="text-xs text-cyan-400 mb-1">{k}</p>
                          <p className="text-sm whitespace-pre-wrap">{String(v)}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 피드백 */}
                  {analysisResult.feedback && (
                    <div className="bg-[#1e1e2e] rounded-lg p-3">
                      <p className="text-xs text-cyan-400 mb-1">💬 피드백</p>
                      <p className="whitespace-pre-wrap leading-relaxed">{String(analysisResult.feedback)}</p>
                    </div>
                  )}

                  {/* 전체 JSON fallback */}
                  {!analysisResult.score && !analysisResult.evaluation && !analysisResult.feedback && (
                    <pre className="bg-[#1e1e2e] rounded-lg p-3 text-xs overflow-x-auto">
                      {JSON.stringify(analysisResult, null, 2)}
                    </pre>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 키보드 단축키 핸들러 */}
      <KeyboardShortcuts undo={undo} redo={redo} />
    </div>
  );
}

/* 키보드 단축키 */
function KeyboardShortcuts({ undo, redo }: { undo: () => void; redo: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === "z") { e.preventDefault(); undo(); }
      if (e.ctrlKey && e.key === "y") { e.preventDefault(); redo(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [undo, redo]);
  return null;
}
