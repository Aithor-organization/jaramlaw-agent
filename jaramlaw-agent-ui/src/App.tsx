import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  BookOpen,
  CalendarClock,
  CheckCircle2,
  Cpu,
  Database,
  FileText,
  Gavel,
  History,
  Layers3,
  Loader2,
  Lock,
  MessageSquare,
  Play,
  Scale,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";

import { DisputeChart } from "./components/DisputeChart";
import { DocumentSummarizer } from "./components/DocumentSummarizer";
import { ExpertReviewPanel } from "./components/ExpertReviewPanel";
import { LawExplorer } from "./components/LawExplorer";
import { SecurityConsole } from "./components/SecurityConsole";
import type { ConsultationSession, HealthStatus } from "./types";

type WorkspaceTab = "consult" | "documents" | "security" | "laws" | "ops";
type JsonRecord = Record<string, unknown>;

const demoPrompts = [
  {
    key: "academy",
    label: "학원 환불",
    title: "선결제 수강료 환불 거부",
    prompt:
      "초등학생 영어학원 3개월분 105만원을 선결제했습니다. 1개월 정도 이용한 뒤 중도 해지를 요청했는데 학원장이 할인 패키지라 환불이 어렵다고 합니다.",
  },
  {
    key: "daycare",
    label: "어린이집 사고",
    title: "CCTV 열람과 사고보고서",
    prompt:
      "24개월 아이가 어린이집 하원 뒤 이마에 멍이 생겼습니다. 어린이집은 단순 사고라고만 하고 CCTV 열람과 사고보고서 제공을 미루고 있습니다.",
  },
  {
    key: "parental",
    label: "육아휴직",
    title: "임신·출산휴가와 육아휴직",
    prompt:
      "현재 임신 12주차 회사원입니다. 출산전후휴가, 배우자 출산휴가, 육아휴직 급여와 회사가 거부할 때 필요한 절차를 알고 싶습니다.",
  },
];

const workspaceTabs: Array<{ key: WorkspaceTab; label: string; icon: typeof MessageSquare }> = [
  { key: "consult", label: "상담", icon: MessageSquare },
  { key: "documents", label: "서류", icon: FileText },
  { key: "security", label: "보호", icon: Lock },
  { key: "laws", label: "법령", icon: BookOpen },
  { key: "ops", label: "운영", icon: Activity },
];

export default function App() {
  const [language, setLanguage] = useState<"ko" | "en">("ko");
  const [clientType, setClientType] = useState<"layperson" | "lawyer">("layperson");
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("consult");
  const [sessions, setSessions] = useState<ConsultationSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<ConsultationSession | null>(null);
  const [userInput, setUserInput] = useState("");
  const [sending, setSending] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [health, setHealth] = useState<HealthStatus | null>(null);

  useEffect(() => {
    void fetchHealth();
    void loadSessionsList(true);
  }, []);

  const latestEngine = useMemo(() => {
    if (selectedSession?.integration?.backend === "python-engine") return "실행 완료";
    if (health?.python_bridge.source_present && health?.python_bridge.workflow_present) return "준비됨";
    if (health?.python_bridge.source_present) return "연결됨";
    return "대기 중";
  }, [health, selectedSession]);

  const commandMetrics = useMemo(
    () => [
      {
        label: "상담 흐름",
        value: health?.python_bridge.source_present ? "연결" : "대기",
        detail: health?.python_bridge.workflow_present ? "14단계 검토" : latestEngine,
        icon: Cpu,
      },
      {
        label: "법령 근거",
        value: health ? `${health.seed_data.laws}` : "확인 중",
        detail: `지원 ${health?.seed_data.supports ?? "-"}`,
        icon: Database,
      },
      {
        label: "검증 기록",
        value: health?.audit.present ? "준비" : "로컬",
        detail: `${health?.audit.recent_count ?? 0}건 기록`,
        icon: ShieldCheck,
      },
      {
        label: "운영 계층",
        value: health?.operations?.team_topology_present ? "활성" : "확인 중",
        detail: health?.operations?.trace_recent_count ? `${health.operations.trace_recent_count}건 추적` : "부모 친화형 UI",
        icon: Activity,
      },
    ],
    [health, latestEngine, selectedSession],
  );

  const loadSessionsList = async (selectFirst = false) => {
    try {
      const response = await fetch("/api/history");
      const data = await response.json();
      if (data.status === "success") {
        const nextSessions = data.data as ConsultationSession[];
        setSessions(nextSessions);
        if (nextSessions.length > 0) {
          setSelectedSession((current) => {
            if (selectFirst || !current) return nextSessions[0];
            return nextSessions.find((session) => session.id === current.id) || nextSessions[0];
          });
        }
      }
    } catch (error) {
      console.error("Failed fetching consultations logs:", error);
      setErrorMsg("상담 이력을 불러오지 못했습니다.");
    }
  };

  const fetchHealth = async () => {
    try {
      const response = await fetch("/api/health");
      if (response.ok) setHealth(await response.json());
    } catch {
      setHealth(null);
    }
  };

  const handleSendQuery = async (event: FormEvent) => {
    event.preventDefault();
    if (!userInput.trim() || sending) return;

    const query = userInput.trim();
    setSending(true);
    setErrorMsg("");
    setUserInput("");

    try {
      const response = await fetch("/api/consult", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: query,
          history: selectedSession?.messages || [],
          clientType,
          language,
        }),
      });
      const payload = await response.json();
      if (!response.ok || payload.status !== "success") {
        throw new Error(payload.message || "상담 생성에 실패했습니다.");
      }
      const nextSession = payload.data as ConsultationSession;
      setSessions((current) => [nextSession, ...current.filter((session) => session.id !== nextSession.id)]);
      setSelectedSession(nextSession);
      await fetchHealth();
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : "서버 통신 중 오류가 발생했습니다.");
    } finally {
      setSending(false);
    }
  };

  const handleFeedbackUpdate = (updated: ConsultationSession) => {
    setSelectedSession(updated);
    setSessions((current) => current.map((session) => (session.id === updated.id ? updated : session)));
  };

  return (
    <div className="app-shell" id="jaramlaw-agent-workspace">
      <header className="app-header">
        <div className="header-inner">
          <div className="brand-block">
            <div className="brand-mark">
              <Scale className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h1>JaramLaw Agent</h1>
              <p>부모 법률 케어 워크스페이스</p>
            </div>
          </div>

          <div className="header-actions">
            <div className="header-status">
              <span className={`health-dot ${health?.python_bridge.source_present ? "health-on" : "health-warn"}`} />
              <span>{latestEngine}</span>
            </div>
            <button type="button" className="header-pill" onClick={() => setLanguage(language === "ko" ? "en" : "ko")}>
              {language === "ko" ? "KO" : "EN"}
            </button>
          </div>
        </div>
      </header>

      <section className="visual-command-band" aria-label="JaramLaw 상담 흐름 요약">
        <div className="visual-command-copy">
          <span className="visual-command-kicker">
            <Sparkles className="h-4 w-4" />
            부모를 위한 차분한 법률 동반자
          </span>
          <h2>아이를 키우며 마주한 법률 고민을 부드럽게 정리합니다</h2>
          <p>걱정되는 상황을 적으면 JaramLaw가 근거 법령, 제출 서류, 다음 행동과 전문가 검토 필요성을 한 화면에 정돈합니다.</p>
        </div>

        <div className="visual-command-metrics">
          {commandMetrics.map((metric) => {
            const Icon = metric.icon;
            return (
              <div className="visual-metric" key={metric.label}>
                <Icon className="h-4 w-4" />
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <em>{metric.detail}</em>
              </div>
            );
          })}
        </div>
      </section>

      <main className="workspace-layout">
        <nav className="workspace-tabs" role="tablist" aria-label="JaramLaw 작업 공간">
          {workspaceTabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.key}
                type="button"
                className={`workspace-tab ${activeTab === tab.key ? "workspace-tab-active" : ""}`}
                onClick={() => setActiveTab(tab.key)}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>

        {errorMsg && (
          <div className="error-banner">
            <AlertCircle className="h-4 w-4" />
            <span>{errorMsg}</span>
          </div>
        )}

        {activeTab === "consult" ? (
          <section className="consult-grid">
            <aside className="side-stack">
              <section className="panel">
                <div className="section-title">
                  <div>
                    <p className="eyebrow">상담 준비</p>
                    <h2>가정 상황</h2>
                  </div>
                  <span className="mini-chip">{clientType === "lawyer" ? "전문가 모드" : "부모 상담"}</span>
                </div>

                <div className="profile-toggle" aria-label="상담 대상 선택">
                  <button
                    type="button"
                    className={clientType === "layperson" ? "profile-active" : ""}
                    onClick={() => setClientType("layperson")}
                  >
                    <UserRound className="h-4 w-4" />
                    일반인
                  </button>
                  <button
                    type="button"
                    className={clientType === "lawyer" ? "profile-active" : ""}
                    onClick={() => setClientType("lawyer")}
                  >
                    <Gavel className="h-4 w-4" />
                    전문가
                  </button>
                </div>

                <div className="scenario-list">
                  {demoPrompts.map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      className="scenario-button"
                      onClick={() => setUserInput(item.prompt)}
                    >
                      <span className="scenario-icon">
                        <Search className="h-4 w-4" />
                      </span>
                      <span>
                        <small>{item.label}</small>
                        <strong>{item.title}</strong>
                      </span>
                    </button>
                  ))}
                </div>

                <form onSubmit={handleSendQuery} className="consult-form">
                  <label htmlFor="legal-query-input" className="field-label">
                    <MessageSquare className="h-4 w-4" />
                    상담 내용
                  </label>
                  <textarea
                    id="legal-query-input"
                    className="consult-textarea"
                    value={userInput}
                    onChange={(event) => setUserInput(event.target.value)}
                    disabled={sending}
                    placeholder="사실관계, 날짜, 기관명, 금액, 상대방 답변을 함께 입력하세요."
                  />
                  <button type="submit" className="primary-button w-full" disabled={sending || !userInput.trim()}>
                    {sending ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        상담 흐름 실행 중
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4" />
                        상담 정리 시작
                      </>
                    )}
                  </button>
                </form>
              </section>

              <section className="panel">
                <div className="section-title">
                  <div>
                    <p className="eyebrow">이전 상담</p>
                    <h2>상담 이력</h2>
                  </div>
                  <span className="mini-chip">{sessions.length}</span>
                </div>
                <div className="history-list">
                  {sessions.map((session) => (
                    <button
                      key={session.id}
                      type="button"
                      className={`history-item ${selectedSession?.id === session.id ? "history-item-active" : ""}`}
                      onClick={() => setSelectedSession(session)}
                    >
                      <History className="h-4 w-4" />
                      <span>
                        <strong>{session.title}</strong>
                        <small>
                          {formatDate(session.date)} · {formatBackend(session.integration?.backend)}
                        </small>
                      </span>
                    </button>
                  ))}
                </div>
              </section>
            </aside>

            <section className="main-stack">
              <section className="panel chat-panel">
                <div className="section-title">
                  <div>
                    <p className="eyebrow">정리 결과</p>
                    <h2>{selectedSession?.title || "상담 결과 대기"}</h2>
                  </div>
                  <span className={`status-pill ${selectedSession?.integration?.connected ? "tone-green" : "tone-amber"}`}>
                    {formatBackend(selectedSession?.integration?.backend)}
                  </span>
                </div>

                <div className="chat-stream">
                  {selectedSession ? (
                    selectedSession.messages.map((message) => (
                      <article key={message.id} className={`chat-message ${message.sender === "user" ? "chat-user" : "chat-agent"}`}>
                        <span className="chat-author">
                          {message.sender === "user" ? <UserRound className="h-3.5 w-3.5" /> : <Sparkles className="h-3.5 w-3.5" />}
                          {message.sender === "user" ? "보호자" : "JaramLaw"}
                        </span>
                        <div className="chat-bubble">{message.text}</div>
                        <time>{new Date(message.timestamp).toLocaleTimeString()}</time>
                      </article>
                    ))
                  ) : (
                    <div className="empty-state">
                      <Layers3 className="h-10 w-10" />
                      <strong>상담을 시작하면 검토 결과가 여기에 정리됩니다.</strong>
                    </div>
                  )}
                </div>

                {sending && (
                  <div className="loading-row">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    상담 엔진이 내용을 차분히 정리하고 있습니다
                  </div>
                )}
              </section>

              {selectedSession?.riskAnalysis && (
                <section className="analysis-grid">
                  <div className="panel">
                    <DisputeChart analysis={selectedSession.riskAnalysis} language={language} />
                  </div>
                  <WorkflowPanel session={selectedSession} />
                </section>
              )}

              {selectedSession && (
                <ExpertReviewPanel session={selectedSession} language={language} onFeedbackSaved={handleFeedbackUpdate} />
              )}
            </section>
          </section>
        ) : (
          <section className="workspace-main">
            {activeTab === "documents" && <DocumentSummarizer language={language} />}
            {activeTab === "security" && <SecurityConsole language={language} />}
            {activeTab === "laws" && <LawExplorer language={language} />}
            {activeTab === "ops" && <OperationsPanel />}
          </section>
        )}
      </main>

      <footer className="app-footer">
        <span>JaramLaw Agent</span>
        <span>상담 엔진: {health?.python_bridge.source_present ? "연결" : "로컬"}</span>
        <span>워크플로우: {health?.python_bridge.workflow_present ? "준비" : "확인 필요"}</span>
        <span>고위험 사안은 전문가 검토를 우선합니다.</span>
      </footer>
    </div>
  );
}

function OperationsPanel() {
  const [status, setStatus] = useState<JsonRecord>({});
  const [audits, setAudits] = useState<JsonRecord[]>([]);
  const [traces, setTraces] = useState<JsonRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [publishResult, setPublishResult] = useState("");

  const loadOps = async () => {
    setLoading(true);
    try {
      const [statusResponse, auditResponse, traceResponse] = await Promise.all([
        fetch("/api/ops/workflow/status"),
        fetch("/api/ops/audit/logs?limit=8"),
        fetch("/api/ops/traces?limit=12"),
      ]);
      const statusPayload = await statusResponse.json();
      const auditPayload = await auditResponse.json();
      const tracePayload = await traceResponse.json();
      setStatus(asRecord(statusPayload.data));
      setAudits(asArray(auditPayload.data));
      setTraces(asArray(tracePayload.data));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadOps();
  }, []);

  const publishWorkflow = async () => {
    setPublishResult("");
    const response = await fetch("/api/ops/workflow/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: "UI ops publish" }),
    });
    const payload = await response.json();
    const data = asRecord(payload.data);
    setPublishResult(recordString(data, "workflow_sha1", "published"));
    await loadOps();
  };

  const workflow = asRecord(status.workflow);
  const modelRouting = asRecord(workflow.model_routing);
  const brain = asRecord(workflow.brain);
  const topology = asRecord(status.topology);
  const audit = asRecord(status.audit);
  const trace = asRecord(status.trace);
  const budget = asRecord(status.budget);

  return (
    <section className="ops-console">
      <div className="panel">
        <div className="section-title">
          <div>
            <p className="eyebrow">운영 확인</p>
            <h2>에이전트 제어 콘솔</h2>
          </div>
          <button type="button" className="secondary-button" onClick={loadOps} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Activity className="h-4 w-4" />}
            새로고침
          </button>
        </div>

        <div className="ops-grid">
          <MetricTile icon={Layers3} label="팀 구조" value={topology.present ? "준비" : "누락"} detail="agents/team.yaml" />
          <MetricTile icon={Cpu} label="모델 라우팅" value={modelRouting.present ? "준비" : "누락"} detail="routing workflow" />
          <MetricTile icon={Database} label="기억 계층" value={brain.present ? "준비" : "누락"} detail="metadata RAG" />
          <MetricTile icon={ShieldCheck} label="추적" value={trace.present ? "활성" : "대기"} detail={`${Number(trace.recent_count ?? 0)}건`} />
        </div>

        <div className="ops-actions">
          <button type="button" className="primary-button" onClick={publishWorkflow}>
            <CheckCircle2 className="h-4 w-4" />
            워크플로우 기록
          </button>
          <span>{publishResult ? `sha1 ${publishResult.slice(0, 12)}` : "runs/workflow-publish.json에 로컬 기록"}</span>
          <span>실행 예산 ${Number(budget.per_run_limit_usd ?? 0.25).toFixed(2)}</span>
        </div>
      </div>

      <div className="ops-columns">
        <section className="panel">
          <div className="section-title">
            <div>
              <p className="eyebrow">감사 기록</p>
              <h2>최근 검토 리포트</h2>
            </div>
            <span className="mini-chip">{Number(audit.recent_count ?? audits.length)}</span>
          </div>
          <div className="compact-list">
            {audits.slice(0, 8).map((item, index) => (
              <div className="compact-row" key={recordString(item, "audit_log_id", `audit-${index}`)}>
                <strong>{recordString(item, "audit_log_id", recordString(item, "source_file", "감사 기록"))}</strong>
                <span>{recordString(item, "generated_at", "시간 정보 없음")}</span>
              </div>
            ))}
            {!audits.length && (
              <div className="compact-row">
                <strong>감사 기록 없음</strong>
                <span>상담을 실행하면 검토 기록이 생성됩니다.</span>
              </div>
            )}
          </div>
        </section>

        <section className="panel">
          <div className="section-title">
            <div>
              <p className="eyebrow">실행 추적</p>
              <h2>워크플로우 이벤트</h2>
            </div>
            <span className="mini-chip">{traces.length}</span>
          </div>
          <div className="compact-list">
            {traces.slice(0, 10).map((item, index) => (
              <div className="compact-row" key={recordString(item, "trace_id", `trace-${index}`)}>
                <strong>{recordString(item, "node", "워크플로우 이벤트")}</strong>
                <span>{recordString(item, "generated_at", recordString(item, "session_id", "추적 메타데이터"))}</span>
              </div>
            ))}
            {!traces.length && (
              <div className="compact-row">
                <strong>추적 이벤트 없음</strong>
                <span>감사 워크플로우 실행 후 메타데이터가 표시됩니다.</span>
              </div>
            )}
          </div>
        </section>
      </div>
    </section>
  );
}

function WorkflowPanel({ session }: { session: ConsultationSession }) {
  const report = asRecord(session.workflowReport);
  const laws = asArray(report.matched_laws);
  const supports = asArray(report.support_matches);
  const rights = asArray(report.rights_cards);
  const docs = asArray(report.draft_documents);
  const board = asRecord(report.board_opinions);
  const human = asRecord(report.human_review);
  const verifier = asRecord(report.verifier_results);

  return (
    <div className="panel workflow-panel">
      <div className="section-title">
        <div>
          <p className="eyebrow">상담 엔진</p>
          <h2>통합 결과</h2>
        </div>
        <span className="mini-chip">{session.auditLogId || "감사 ID 없음"}</span>
      </div>

      <div className="ops-grid">
        <MetricTile icon={BookOpen} label="법령" value={String(session.recommendedLaws.length || laws.length)} detail="검토 법령" />
        <MetricTile icon={CheckCircle2} label="권리카드" value={String(rights.length)} detail="권리 안내" />
        <MetricTile icon={FileText} label="문서" value={String(docs.length)} detail="초안" />
        <MetricTile icon={CalendarClock} label="지원" value={String(supports.length)} detail="지원 제도" />
      </div>

      <div className="workflow-split">
        <section>
          <h3>추천 법령</h3>
          <div className="compact-list">
            {session.recommendedLaws.slice(0, 5).map((law) => (
              <div className="compact-row" key={law.id}>
                <strong>{law.title}</strong>
                <span>{law.summary}</span>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h3>보드 진단</h3>
          <div className="compact-list">
            {Object.entries(board).slice(0, 4).map(([name, value]) => {
              const item = asRecord(value);
              return (
                <div className="compact-row" key={name}>
                  <strong>{name.replaceAll("_", " ")}</strong>
                  <span>{recordSummary(item)}</span>
                </div>
              );
            })}
            {!Object.keys(board).length && (
              <div className="compact-row">
                <strong>{formatBackend(session.integration?.backend)}</strong>
                <span>{session.integration?.fallback_reason || "이 상담에는 보드 진단 데이터가 연결되지 않았습니다."}</span>
              </div>
            )}
          </div>
        </section>
      </div>

      <div className="workflow-split">
        <section>
          <h3>문서 초안</h3>
          <div className="compact-list">
            {docs.slice(0, 3).map((doc, index) => (
              <div className="compact-row" key={recordString(doc, "doc_id", `doc-${index}`)}>
                <strong>{recordString(doc, "title", "문서 초안")}</strong>
                <span>{recordString(doc, "kind", "초안")}</span>
              </div>
            ))}
            {!docs.length && (
              <div className="compact-row">
                <strong>문서 대기열</strong>
                <span>이 상담에서는 자동 문서 초안이 생성되지 않았습니다.</span>
              </div>
            )}
          </div>
        </section>

        <section>
          <h3>검증 게이트</h3>
          <div className="verifier-box">
            <strong>{Math.round(Number(verifier.verified_ratio ?? 0) * 100)}%</strong>
            <span>
              확인 {Number(verifier.verified_count ?? 0)} · 부분 확인 {Number(verifier.partial_count ?? 0)} · 추가 검토{" "}
              {Number(verifier.unverifiable_count ?? 0)}
            </span>
            <em>{human.needed ? recordString(human, "reason", "전문가 검토 권장") : "자동 검증 통과"}</em>
          </div>
        </section>
      </div>
    </div>
  );
}

function MetricTile({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: typeof BookOpen;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="metric-tile">
      <Icon className="h-4 w-4" />
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{detail}</em>
    </div>
  );
}

function asRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonRecord) : {};
}

function asArray(value: unknown): JsonRecord[] {
  return Array.isArray(value) ? value.map(asRecord).filter((item) => Object.keys(item).length > 0) : [];
}

function recordString(record: JsonRecord, key: string, fallback: string) {
  const value = record[key];
  return typeof value === "string" && value.trim() ? value : fallback;
}

function recordSummary(record: JsonRecord) {
  if (Array.isArray(record.findings)) return `${record.findings.length}개 검토 · ${recordString(record, "verdict", "리뷰")}`;
  if (Array.isArray(record.top_laws)) return `${record.top_laws.length}개 법령`;
  if (Array.isArray(record.flags)) return record.flags.join(", ") || "특이사항 없음";
  if (Array.isArray(record.kinds)) return record.kinds.join(", ") || "문서 없음";
  return JSON.stringify(record).slice(0, 120);
}

function formatBackend(backend?: string) {
  if (backend === "python-engine") return "상담 엔진";
  if (backend === "local-seed") return "로컬 근거";
  if (backend === "standby" || !backend) return "대기";
  return backend;
}

function formatDate(date: string) {
  return new Date(date).toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
}
