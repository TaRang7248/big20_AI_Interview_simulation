"use client";
import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Header from "@/components/common/Header";
import {
  codingApi,
  type CodingProblem,
  type CodeSubmitResult,
  type CodeAnalysis,
  type TestCaseResult,
} from "@/lib/api";
import { Play, Send, RotateCcw, RefreshCw, CheckCircle2, XCircle, Loader2, Terminal, FlaskConical, Keyboard, ChevronDown, ChevronRight, Clock } from "lucide-react";
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
  const [stdin, setStdin] = useState("");          // 사용자 커스텀 입력
  const [analysis, setAnalysis] = useState<CodeAnalysis | null>(null);
  const [testResults, setTestResults] = useState<TestCaseResult[]>([]);  // 테스트 결과
  const [testSummary, setTestSummary] = useState<{ passed: number; total: number; overall_score: number; avg_execution_time: number } | null>(null);
  const [running, setRunning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState<"problem" | "examples" | "hints">("problem");
  const [bottomTab, setBottomTab] = useState<"output" | "testResults" | "stdin">("output");  // 하단 탭
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [expandedTests, setExpandedTests] = useState<Set<number>>(new Set());  // 펼쳐진 테스트 상세

  // 테스트 상세 펼침 토글
  const toggleTestExpand = (testId: number) => {
    setExpandedTests(prev => {
      const next = new Set(prev);
      if (next.has(testId)) next.delete(testId);
      else next.add(testId);
      return next;
    });
  };

  // 문제 생성
  const generateProblem = async (diff?: string) => {
    setGenerating(true);
    setProblem(null);
    setOutput("");
    setAnalysis(null);
    setTestResults([]);
    setTestSummary(null);
    setShowAnalysis(false);
    setBottomTab("output");
    setExpandedTests(new Set());
    try {
      const p = await codingApi.generate(diff || difficulty);
      setProblem(p);
      // 첫 번째 예제 입력을 기본 stdin으로 설정
      if (p.examples?.length > 0) {
        setStdin(p.examples[0].input);
      }
      const tpl = await codingApi.getTemplate(language, p.id);
      setCode(tpl.template || "");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "알 수 없는 오류";
      // 타임아웃 에러인 경우 사용자에게 재시도 안내 메시지 표시
      if (msg.includes("시간이 초과") || msg.includes("timeout")) {
        setOutput("⏱ AI 문제 생성 시간이 초과되었습니다.\n기본 문제가 제공되었거나, 아래 '새 문제' 버튼을 눌러 다시 시도해주세요.");
      } else {
        setOutput(`문제 생성 실패: ${msg}`);
      }
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

  // 코드 실행 (커스텀 입력)
  const runCode = async () => {
    setRunning(true);
    setOutput("");
    setBottomTab("output");
    try {
      const res = await codingApi.run(code, language, stdin || undefined);
      let msg = "";
      if (res.success) {
        msg = res.output || "(출력 없음)";
        if (res.execution_time) msg += `\n\n⏱ 실행 시간: ${res.execution_time.toFixed(2)}ms`;
      } else {
        msg = `❌ Error:\n${res.error}`;
      }
      setOutput(msg);
    } catch (e: unknown) {
      setOutput(`실행 실패: ${e instanceof Error ? e.message : "알 수 없는 오류"}`);
    } finally { setRunning(false); }
  };

  // 예제 테스트 실행 (문제의 예제 테스트 케이스로 실행)
  const runExamples = async () => {
    if (!problem?.examples?.length) return;
    setRunning(true);
    setTestResults([]);
    setTestSummary(null);
    setBottomTab("testResults");
    try {
      // 예제를 테스트 케이스 형태로 변환
      const testCases = problem.examples.map(ex => ({
        input: ex.input,
        expected: ex.output,
      }));
      const res = await codingApi.execute(code, language, undefined, testCases);
      setTestResults(res.test_results || []);
      setTestSummary(res.summary || null);
      setExpandedTests(new Set(
        (res.test_results || []).filter(t => !t.passed).map(t => t.test_id)
      ));
    } catch (e: unknown) {
      setOutput(`예제 실행 실패: ${e instanceof Error ? e.message : "알 수 없는 오류"}`);
      setBottomTab("output");
    } finally { setRunning(false); }
  };

  // 코드 제출 (전체 테스트 케이스 + AI 분석)
  const submitCode = async () => {
    if (!problem) return;
    setSubmitting(true);
    setTestResults([]);
    setTestSummary(null);
    setAnalysis(null);
    setShowAnalysis(false);
    setBottomTab("testResults");
    try {
      const res = await codingApi.submit(code, language, problem.id);
      // 테스트 결과 설정
      setTestResults(res.test_results || []);
      setTestSummary(res.summary || null);
      // 실패한 테스트 자동 펼침
      setExpandedTests(new Set(
        (res.test_results || []).filter(t => !t.passed).map(t => t.test_id)
      ));
      // AI 분석
      if (res.analysis) {
        setAnalysis(res.analysis);
        setShowAnalysis(true);
      }
      // 요약 메시지
      const passed = res.summary?.passed ?? 0;
      const total = res.summary?.total ?? 0;
      if (passed === total && total > 0) {
        setOutput(`🎉 모든 테스트 통과! (${passed}/${total})\n종합 점수: ${res.summary?.overall_score ?? "-"}점`);
      } else {
        setOutput(`테스트 결과: ${passed}/${total} 통과\n종합 점수: ${res.summary?.overall_score ?? "-"}점`);
      }
    } catch (e: unknown) {
      setOutput(`제출 실패: ${e instanceof Error ? e.message : ""}`);
      setBottomTab("output");
    } finally { setSubmitting(false); }
  };

  // 키보드 단축키
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && !e.shiftKey && e.key === "Enter") { e.preventDefault(); runCode(); }
      if (e.ctrlKey && e.shiftKey && e.key === "Enter") { e.preventDefault(); submitCode(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [code, language, problem, stdin]);

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
                className={`px-3 py-1 rounded-full text-xs font-semibold transition ${difficulty === d.value ? d.color + " ring-1 ring-current" : "text-[#858585] hover:text-[#ccc]"
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
          <button onClick={runExamples} disabled={running || !problem?.examples?.length}
            className="flex items-center gap-1 px-4 py-1.5 rounded text-xs bg-[#6c5ce7] text-white hover:bg-[#5b4cdb] transition disabled:opacity-50">
            {running ? <Loader2 size={12} className="animate-spin" /> : <FlaskConical size={12} />}
            예제 테스트
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
                className={`flex-1 px-3 py-2 text-xs font-medium transition ${activeTab === tab ? "text-white border-b-2 border-[#007acc] bg-[#1e1e1e]" : "text-[#858585] hover:text-[#ccc]"
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

          {/* 하단 패널 (출력 / 테스트 결과 / 입력) */}
          <div className="h-[260px] border-t border-[#3c3c3c] flex flex-col shrink-0">
            {/* 탭 헤더 */}
            <div className="flex items-center bg-[#252526] border-b border-[#3c3c3c] shrink-0">
              <button onClick={() => setBottomTab("output")}
                className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium transition ${bottomTab === "output" ? "text-white border-b-2 border-[#007acc] bg-[#1e1e1e]" : "text-[#858585] hover:text-[#ccc]"
                  }`}>
                <Terminal size={12} /> 출력
              </button>
              <button onClick={() => setBottomTab("testResults")}
                className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium transition ${bottomTab === "testResults" ? "text-white border-b-2 border-[#007acc] bg-[#1e1e1e]" : "text-[#858585] hover:text-[#ccc]"
                  }`}>
                <FlaskConical size={12} /> 테스트 결과
                {testSummary && (
                  <span className={`ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold ${testSummary.passed === testSummary.total
                      ? "bg-green-500/20 text-green-400"
                      : "bg-red-500/20 text-red-400"
                    }`}>
                    {testSummary.passed}/{testSummary.total}
                  </span>
                )}
              </button>
              <button onClick={() => setBottomTab("stdin")}
                className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium transition ${bottomTab === "stdin" ? "text-white border-b-2 border-[#007acc] bg-[#1e1e1e]" : "text-[#858585] hover:text-[#ccc]"
                  }`}>
                <Keyboard size={12} /> 입력(stdin)
              </button>
            </div>

            {/* 탭 내용 */}
            <div className="flex-1 overflow-y-auto bg-[#1e1e1e]">
              {/* === 출력 탭 === */}
              {bottomTab === "output" && (
                <pre className="p-4 text-sm text-[#ccc] font-mono whitespace-pre-wrap">
                  {output || "실행 결과가 여기에 표시됩니다."}
                </pre>
              )}

              {/* === 테스트 결과 탭 === */}
              {bottomTab === "testResults" && (
                <div className="p-3">
                  {testResults.length === 0 ? (
                    <div className="text-center text-[#858585] text-sm py-8">
                      <FlaskConical size={32} className="mx-auto mb-2 opacity-50" />
                      <p>&quot;예제 테스트&quot; 또는 &quot;제출&quot; 버튼을 눌러<br />테스트 결과를 확인하세요.</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {/* 요약 바 */}
                      {testSummary && (
                        <div className={`flex items-center justify-between px-4 py-2.5 rounded-lg text-sm font-medium ${testSummary.passed === testSummary.total
                            ? "bg-green-500/10 border border-green-500/30 text-green-400"
                            : "bg-red-500/10 border border-red-500/30 text-red-400"
                          }`}>
                          <div className="flex items-center gap-2">
                            {testSummary.passed === testSummary.total
                              ? <CheckCircle2 size={16} />
                              : <XCircle size={16} />}
                            <span>
                              {testSummary.passed === testSummary.total
                                ? `모든 테스트 통과!`
                                : `${testSummary.total - testSummary.passed}개 테스트 실패`}
                            </span>
                            <span className="opacity-70">({testSummary.passed}/{testSummary.total})</span>
                          </div>
                          <div className="flex items-center gap-3 text-xs opacity-70">
                            <span className="flex items-center gap-1">
                              <Clock size={12} /> 평균 {testSummary.avg_execution_time.toFixed(1)}ms
                            </span>
                            {testSummary.overall_score > 0 && (
                              <span>점수: {testSummary.overall_score}점</span>
                            )}
                          </div>
                        </div>
                      )}

                      {/* 개별 테스트 케이스 */}
                      {testResults.map(tc => (
                        <div key={tc.test_id}
                          className={`rounded-lg border transition-all ${tc.passed
                              ? "border-green-500/20 bg-green-500/5"
                              : "border-red-500/20 bg-red-500/5"
                            }`}>
                          {/* 테스트 헤더 (클릭으로 펼침) */}
                          <button onClick={() => toggleTestExpand(tc.test_id)}
                            className="w-full flex items-center justify-between px-3 py-2 text-left">
                            <div className="flex items-center gap-2">
                              {tc.passed
                                ? <CheckCircle2 size={14} className="text-green-400 shrink-0" />
                                : <XCircle size={14} className="text-red-400 shrink-0" />}
                              <span className={`text-xs font-medium ${tc.passed ? "text-green-400" : "text-red-400"}`}>
                                테스트 {tc.test_id}
                              </span>
                              <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${tc.passed ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
                                }`}>
                                {tc.passed ? "PASS" : "FAIL"}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 text-[#858585]">
                              <span className="text-[10px] flex items-center gap-1">
                                <Clock size={10} /> {tc.execution_time.toFixed(1)}ms
                              </span>
                              {expandedTests.has(tc.test_id)
                                ? <ChevronDown size={12} />
                                : <ChevronRight size={12} />}
                            </div>
                          </button>

                          {/* 테스트 상세 (펼쳤을 때) */}
                          {expandedTests.has(tc.test_id) && (
                            <div className="px-3 pb-3 space-y-2 text-xs">
                              <div className="bg-[#1e1e1e] rounded p-2">
                                <p className="text-[#858585] mb-1">입력</p>
                                <pre className="text-[#ccc] font-mono whitespace-pre-wrap">{tc.input}</pre>
                              </div>
                              <div className="bg-[#1e1e1e] rounded p-2">
                                <p className="text-[#858585] mb-1">기대 출력</p>
                                <pre className="text-[#4ec9b0] font-mono whitespace-pre-wrap">{tc.expected}</pre>
                              </div>
                              <div className="bg-[#1e1e1e] rounded p-2">
                                <p className="text-[#858585] mb-1">실제 출력</p>
                                <pre className={`font-mono whitespace-pre-wrap ${tc.passed ? "text-[#4ec9b0]" : "text-red-400"}`}>
                                  {tc.actual || "(출력 없음)"}
                                </pre>
                              </div>
                              {tc.error && (
                                <div className="bg-red-500/10 border border-red-500/20 rounded p-2">
                                  <p className="text-[#858585] mb-1">에러</p>
                                  <pre className="text-red-400 font-mono whitespace-pre-wrap">{tc.error}</pre>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* === stdin 입력 탭 === */}
              {bottomTab === "stdin" && (
                <div className="p-3 h-full flex flex-col">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs text-[#858585]">실행 시 표준 입력 (stdin)으로 전달됩니다</p>
                    {problem?.examples?.length ? (
                      <button onClick={() => setStdin(problem.examples[0].input)}
                        className="text-[10px] px-2 py-1 rounded bg-[#3c3c3c] text-[#ccc] hover:bg-[#505050] transition">
                        예제 1 입력 불러오기
                      </button>
                    ) : null}
                  </div>
                  <textarea
                    value={stdin}
                    onChange={e => setStdin(e.target.value)}
                    className="flex-1 w-full bg-[#252526] text-[#ccc] font-mono text-sm p-3 rounded border border-[#3c3c3c] focus:border-[#007acc] outline-none resize-none"
                    placeholder="입력값을 입력하세요...&#10;예: 4&#10;2 7 11 15&#10;9"
                  />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* AI 분석 패널 (슬라이드) */}
        <div className={`w-[420px] border-l border-[#3c3c3c] bg-[#252526] overflow-y-auto transition-all duration-300 ${showAnalysis ? "translate-x-0" : "translate-x-full hidden"
          }`}>
          <div className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-white">🤖 AI 코드 분석</h3>
              <button onClick={() => setShowAnalysis(false)} className="text-[#858585] hover:text-white">✕</button>
            </div>

            {analysis && (
              <div className="space-y-4">
                {/* 종합 점수 */}
                <div className="text-center py-4">
                  <div className={`text-5xl font-bold ${analysis.overall_score >= 80 ? "text-green-400" :
                      analysis.overall_score >= 60 ? "text-yellow-400" :
                        analysis.overall_score >= 40 ? "text-orange-400" : "text-red-400"
                    }`}>{analysis.overall_score}</div>
                  <p className="text-sm text-[#858585] mt-1">종합 점수 / 100</p>
                </div>

                {/* 정확성 (테스트 통과율) */}
                <div className="bg-[#1e1e1e] rounded-lg p-3">
                  <div className="flex justify-between text-xs mb-1">
                    <span>정확성 ({analysis.correctness?.passed_tests ?? 0}/{analysis.correctness?.total_tests ?? 0} 통과)</span>
                    <span className="text-[#4ec9b0]">{analysis.correctness?.score ?? 0}/25점</span>
                  </div>
                  <div className="h-2 bg-[#3c3c3c] rounded-full">
                    <div className="h-full bg-[#4ec9b0] rounded-full transition-all"
                      style={{ width: `${((analysis.correctness?.score ?? 0) / 25) * 100}%` }} />
                  </div>
                  {analysis.correctness?.feedback && (
                    <p className="text-[10px] text-[#858585] mt-1">{analysis.correctness.feedback}</p>
                  )}
                </div>

                {/* 복잡도 */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-[#1e1e1e] rounded-lg p-3">
                    <p className="text-xs text-[#858585]">시간 복잡도</p>
                    <p className="text-sm font-mono text-[#dcdcaa] mt-1">{analysis.time_complexity?.estimated ?? "?"}</p>
                    {analysis.time_complexity?.optimal && (
                      <p className="text-[10px] text-[#858585] mt-1">최적: {analysis.time_complexity.optimal}</p>
                    )}
                    <p className="text-[10px] text-[#569cd6] mt-1">{analysis.time_complexity?.score ?? 0}/20점</p>
                  </div>
                  <div className="bg-[#1e1e1e] rounded-lg p-3">
                    <p className="text-xs text-[#858585]">공간 복잡도</p>
                    <p className="text-sm font-mono text-[#dcdcaa] mt-1">{analysis.space_complexity?.estimated ?? "?"}</p>
                    <p className="text-[10px] text-[#569cd6] mt-1">{analysis.space_complexity?.score ?? 0}/15점</p>
                  </div>
                </div>

                {/* 세부 점수 바 */}
                {[
                  { label: "코드 스타일", data: analysis.code_style, max: 20 },
                  { label: "주석/문서화", data: analysis.comments, max: 10 },
                  { label: "모범 사례", data: analysis.best_practices, max: 10 },
                ].map(({ label, data, max }) => (
                  <div key={label} className="bg-[#1e1e1e] rounded-lg p-3">
                    <div className="flex justify-between text-xs mb-1">
                      <span>{label}</span>
                      <span className="text-[#569cd6]">{data?.score ?? 0}/{max}점</span>
                    </div>
                    <div className="h-1.5 bg-[#3c3c3c] rounded-full">
                      <div className="h-full bg-[#569cd6] rounded-full transition-all"
                        style={{ width: `${((data?.score ?? 0) / max) * 100}%` }} />
                    </div>
                    {data?.feedback && (
                      <p className="text-[10px] text-[#858585] mt-1">{data.feedback}</p>
                    )}
                  </div>
                ))}

                {/* 스타일 이슈 */}
                {analysis.code_style?.issues?.length > 0 && (
                  <div className="bg-[rgba(255,152,0,0.1)] border border-[rgba(255,152,0,0.2)] rounded-lg p-3">
                    <p className="text-xs text-orange-400 font-medium mb-2">⚠️ 스타일 이슈</p>
                    <ul className="text-xs text-[#ccc] space-y-1">
                      {analysis.code_style.issues.map((issue, i) => (
                        <li key={i} className="flex items-start gap-1">
                          <span className="text-orange-400 shrink-0">•</span>
                          {issue}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* AI 피드백 */}
                {analysis.feedback?.length > 0 && (
                  <div className="bg-[#1e1e1e] rounded-lg p-3">
                    <p className="text-xs text-[#858585] mb-2">💡 개선 제안</p>
                    <ul className="text-sm text-[#ccc] space-y-2">
                      {analysis.feedback.map((fb, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <span className="text-[#007acc] shrink-0 mt-0.5">{i + 1}.</span>
                          <span className="leading-relaxed">{fb}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 상세 분석 */}
                {analysis.detailed_analysis && (
                  <div className="bg-[#1e1e1e] rounded-lg p-3">
                    <p className="text-xs text-[#858585] mb-2">📝 상세 분석</p>
                    <p className="text-sm text-[#ccc] leading-relaxed whitespace-pre-wrap">
                      {analysis.detailed_analysis}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
