"use client";
import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Header from "@/components/common/Header";
import { codingApi, type CodingProblem, type CodeSubmitResult } from "@/lib/api";
import { Play, Send, RotateCcw, RefreshCw, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import dynamic from "next/dynamic";

// Monaco Editor – SSR 비활성화
const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

const LANGUAGES = [
  { value: "python", label: "Python" },
  { value: "javascript", label: "JavaScript" },
  { value: "java", label: "Java" },
  { value: "c", label: "C" },
  { value: "cpp", label: "C++" },
];

const DIFFICULTIES = [
  { value: "easy", label: "Easy", color: "bg-[rgba(76,175,80,0.2)] text-green-400" },
  { value: "medium", label: "Medium", color: "bg-[rgba(255,152,0,0.2)] text-orange-400" },
  { value: "hard", label: "Hard", color: "bg-[rgba(244,67,54,0.2)] text-red-400" },
];

const DIFFICULTY_COLORS: Record<string, string> = {
  easy: "bg-[rgba(76,175,80,0.2)] text-green-400",
  medium: "bg-[rgba(255,152,0,0.2)] text-orange-400",
  hard: "bg-[rgba(244,67,54,0.2)] text-red-400",
};

export default function CodingTestPageWrapper() {
  return <Suspense fallback={<div className="h-screen bg-[#1e1e1e] flex items-center justify-center text-gray-400">로딩 중...</div>}><CodingTestPage /></Suspense>;
}

function CodingTestPage() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session") || "";

  // 상태
  const [problem, setProblem] = useState<CodingProblem | null>(null);
  const [difficulty, setDifficulty] = useState("medium");
  const [language, setLanguage] = useState("python");
  const [code, setCode] = useState("");
  const [output, setOutput] = useState("");
  const [analysis, setAnalysis] = useState<CodeSubmitResult["analysis"] | null>(null);
  const [running, setRunning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState<"problem" | "examples" | "hints">("problem");
  const [showAnalysis, setShowAnalysis] = useState(false);

  // 문제 생성
  const generateProblem = async (diff?: string) => {
    setGenerating(true);
    setProblem(null);
    setOutput("");
    setAnalysis(null);
    setShowAnalysis(false);
    try {
      const p = await codingApi.generate(diff || difficulty);
      setProblem(p);
      const tpl = await codingApi.getTemplate(language, p.id);
      setCode(tpl.template || "");
    } catch (e: unknown) {
      setOutput(`문제 생성 실패: ${e instanceof Error ? e.message : "알 수 없는 오류"}`);
    } finally {
      setGenerating(false);
    }
  };

  // 페이지 로드 시 자동으로 문제 생성
  useEffect(() => { generateProblem(); }, []);

  // 언어 변경
  const changeLang = async (lang: string) => {
    setLanguage(lang);
    if (problem) {
      const tpl = await codingApi.getTemplate(lang, problem.id);
      setCode(tpl.template || "");
    }
  };

  // 난이도 변경 시 새 문제 생성
  const changeDifficulty = (diff: string) => {
    setDifficulty(diff);
    generateProblem(diff);
  };

  // 코드 실행
  const runCode = async () => {
    setRunning(true); setOutput("");
    try {
      const res = await codingApi.run(code, language);
      setOutput(res.success ? res.output : `❌ Error:\n${res.error}`);
    } catch (e: unknown) {
      setOutput(`실행 실패: ${e instanceof Error ? e.message : "알 수 없는 오류"}`);
    } finally { setRunning(false); }
  };

  // 코드 제출
  const submitCode = async () => {
    if (!problem) return;
    setSubmitting(true);
    try {
      const res = await codingApi.submit(code, language, problem.id);
      setOutput(res.success ? "✅ 제출 완료!" : `❌ ${res.error}`);
      if (res.analysis) { setAnalysis(res.analysis); setShowAnalysis(true); }
    } catch (e: unknown) {
      setOutput(`제출 실패: ${e instanceof Error ? e.message : ""}`);
    } finally { setSubmitting(false); }
  };

  // 키보드 단축키
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === "Enter") { e.preventDefault(); runCode(); }
      if (e.ctrlKey && e.shiftKey && e.key === "Enter") { e.preventDefault(); submitCode(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [code, language, problem]);

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[#1e1e1e]">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-5 py-2 bg-[#2d2d30] border-b border-[#3c3c3c] shrink-0">
        <div className="flex items-center gap-4">
          <span className="text-[#007acc] font-semibold flex items-center gap-2">💻 AI 코딩 테스트</span>

          {/* 난이도 선택 */}
          <div className="flex items-center gap-1">
            {DIFFICULTIES.map(d => (
              <button key={d.value} onClick={() => changeDifficulty(d.value)}
                className={`px-3 py-1 rounded-full text-xs font-semibold transition ${
                  difficulty === d.value ? d.color + " ring-1 ring-current" : "text-[#858585] hover:text-[#ccc]"
                }`}>
                {d.label}
              </button>
            ))}
          </div>

          {/* 새 문제 버튼 */}
          <button onClick={() => generateProblem()} disabled={generating}
            className="flex items-center gap-1 px-3 py-1.5 rounded text-xs bg-[#4a3f8a] text-[#c4b5fd] hover:bg-[#5b4fa8] transition disabled:opacity-50">
            {generating ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            새 문제
          </button>

          {problem && (
            <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${DIFFICULTY_COLORS[problem.difficulty] || ""}`}>
              {problem.difficulty}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* 언어 선택 */}
          <select className="bg-[#252526] text-[#ccc] border border-[#3c3c3c] px-3 py-1 rounded text-sm"
            value={language} onChange={e => changeLang(e.target.value)}>
            {LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>

          <button onClick={() => problem && generateProblem(difficulty)}
            className="flex items-center gap-1 px-3 py-1.5 rounded text-xs bg-[#3c3c3c] text-[#ccc] hover:bg-[#505050] transition">
            <RotateCcw size={12} /> 초기화
          </button>
          <button onClick={runCode} disabled={running}
            className="flex items-center gap-1 px-4 py-1.5 rounded text-xs bg-[#0e639c] text-white hover:bg-[#1177bb] transition disabled:opacity-50">
            {running ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            실행 <span className="opacity-60 ml-1">Ctrl+↵</span>
          </button>
          <button onClick={submitCode} disabled={submitting || !problem}
            className="flex items-center gap-1 px-4 py-1.5 rounded text-xs bg-[#4caf50] text-white hover:bg-[#388e3c] transition disabled:opacity-50">
            {submitting ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
            제출
          </button>
        </div>
      </div>

      {/* 메인 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 문제 패널 */}
        <div className="w-[35%] min-w-[300px] border-r border-[#3c3c3c] flex flex-col overflow-hidden">
          {/* 탭 */}
          <div className="flex border-b border-[#3c3c3c]">
            {(["problem", "examples", "hints"] as const).map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`flex-1 px-3 py-2 text-xs font-medium transition ${
                  activeTab === tab ? "text-white border-b-2 border-[#007acc] bg-[#1e1e1e]" : "text-[#858585] hover:text-[#ccc]"
                }`}>
                {tab === "problem" ? "📋 문제" : tab === "examples" ? "📝 예제" : "💡 힌트"}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-4 text-sm text-[#ccc] leading-relaxed">
            {generating ? (
              <div className="flex flex-col items-center justify-center mt-12 gap-3">
                <Loader2 size={32} className="animate-spin text-[#007acc]" />
                <p className="text-[#858585]">AI가 문제를 생성하고 있습니다...</p>
              </div>
            ) : !problem ? (
              <p className="text-center text-[#858585] mt-12">문제가 없습니다. &quot;새 문제&quot; 버튼을 눌러주세요.</p>
            ) : activeTab === "problem" ? (
              <div>
                <h2 className="text-lg font-bold text-white mb-4">{problem.title}</h2>
                <div className="whitespace-pre-wrap">{problem.description}</div>
              </div>
            ) : activeTab === "examples" ? (
              <div className="space-y-4">
                {problem.examples?.map((ex, i) => (
                  <div key={i} className="bg-[#252526] rounded-lg p-3">
                    <p className="text-xs text-[#858585] mb-1">예제 {i + 1}</p>
                    <p><span className="text-[#569cd6]">입력:</span> <code>{ex.input}</code></p>
                    <p><span className="text-[#569cd6]">출력:</span> <code>{ex.output}</code></p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {problem.hints?.map((h, i) => (
                  <div key={i} className="bg-[rgba(255,152,0,0.1)] border border-[rgba(255,152,0,0.2)] rounded-lg p-3 text-sm">
                    💡 {h}
                  </div>
                )) || <p className="text-[#858585]">힌트가 없습니다.</p>}
              </div>
            )}
          </div>
        </div>

        {/* 에디터 + 출력 */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Monaco Editor */}
          <div className="flex-1 min-h-0">
            <MonacoEditor
              height="100%"
              language={language === "cpp" ? "cpp" : language}
              theme="vs-dark"
              value={code}
              onChange={v => setCode(v || "")}
              options={{
                fontSize: 14,
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                padding: { top: 12 },
                lineNumbers: "on",
                renderLineHighlight: "gutter",
                tabSize: 4,
              }}
            />
          </div>

          {/* 출력 패널 */}
          <div className="h-[200px] border-t border-[#3c3c3c] flex flex-col shrink-0">
            <div className="flex items-center px-4 py-1.5 bg-[#252526] text-xs text-[#858585] border-b border-[#3c3c3c]">
              출력
            </div>
            <pre className="flex-1 overflow-y-auto p-4 text-sm text-[#ccc] font-mono whitespace-pre-wrap bg-[#1e1e1e]">
              {output || "실행 결과가 여기에 표시됩니다."}
            </pre>
          </div>
        </div>

        {/* AI 분석 패널 (슬라이드) */}
        <div className={`w-[400px] border-l border-[#3c3c3c] bg-[#252526] overflow-y-auto transition-all duration-300 ${
          showAnalysis ? "translate-x-0" : "translate-x-full hidden"
        }`}>
          <div className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-white">🤖 AI 코드 분석</h3>
              <button onClick={() => setShowAnalysis(false)} className="text-[#858585] hover:text-white">✕</button>
            </div>

            {analysis && (
              <div className="space-y-4">
                {/* 점수 */}
                <div className="text-center py-4">
                  <div className="text-5xl font-bold gradient-text">{analysis.score}</div>
                  <p className="text-sm text-[#858585] mt-1">종합 점수</p>
                </div>

                {/* 메트릭 */}
                <div className="space-y-3">
                  <div className="bg-[#1e1e1e] rounded-lg p-3">
                    <div className="flex justify-between text-xs mb-1">
                      <span>정확성</span><span className="text-[#4ec9b0]">{analysis.accuracy}%</span>
                    </div>
                    <div className="h-2 bg-[#3c3c3c] rounded-full">
                      <div className="h-full bg-[#4ec9b0] rounded-full" style={{ width: `${analysis.accuracy}%` }} />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-[#1e1e1e] rounded-lg p-3 text-center">
                      <p className="text-xs text-[#858585]">시간 복잡도</p>
                      <p className="text-sm font-mono text-[#dcdcaa]">{analysis.time_complexity}</p>
                    </div>
                    <div className="bg-[#1e1e1e] rounded-lg p-3 text-center">
                      <p className="text-xs text-[#858585]">공간 복잡도</p>
                      <p className="text-sm font-mono text-[#dcdcaa]">{analysis.space_complexity}</p>
                    </div>
                  </div>
                </div>

                {/* 피드백 */}
                <div className="bg-[#1e1e1e] rounded-lg p-3">
                  <p className="text-xs text-[#858585] mb-2">AI 피드백</p>
                  <p className="text-sm text-[#ccc] leading-relaxed whitespace-pre-wrap">{analysis.feedback}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
