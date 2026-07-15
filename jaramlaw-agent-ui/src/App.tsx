import {
  FormEvent,
  KeyboardEvent,
  Suspense,
  lazy,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  BookOpen,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  Cpu,
  Database,
  FileText,
  Home,
  KeyRound,
  Layers3,
  Loader2,
  Lock,
  MessageSquare,
  Play,
  RefreshCw,
  Scale,
  ShieldCheck,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { apiFetch, getOperatorToken, readApiError, setOperatorToken } from "./api";
import type { ConsultationSession, HealthStatus } from "./types";

const DocumentSummarizer = lazy(() => import("./components/DocumentSummarizer").then((module) => ({ default: module.DocumentSummarizer })));
const LawExplorer = lazy(() => import("./components/LawExplorer").then((module) => ({ default: module.LawExplorer })));
const DisputeChart = lazy(() => import("./components/DisputeChart").then((module) => ({ default: module.DisputeChart })));
const ExpertReviewPanel = lazy(() => import("./components/ExpertReviewPanel").then((module) => ({ default: module.ExpertReviewPanel })));
const SecurityConsole = lazy(() => import("./components/SecurityConsole").then((module) => ({ default: module.SecurityConsole })));

type ParentTab = "today" | "consult" | "documents" | "laws";
type AdminTab = "operations" | "reviews" | "security";
type JsonRecord = Record<string, unknown>;

interface FamilyProfile {
  birthMonth: string;
  region: string;
  household: "two-caregivers" | "single-caregiver" | "expecting";
}

const parentTabs: Array<{ key: ParentTab; label: string; icon: typeof Home }> = [
  { key: "today", label: "오늘", icon: Home },
  { key: "consult", label: "상담", icon: MessageSquare },
  { key: "documents", label: "서류", icon: FileText },
  { key: "laws", label: "법령", icon: BookOpen },
];

const adminTabs: Array<{ key: AdminTab; label: string; icon: typeof Activity }> = [
  { key: "operations", label: "운영 현황", icon: Activity },
  { key: "reviews", label: "전문가 검토", icon: UserCheck },
  { key: "security", label: "보안 검증", icon: ShieldCheck },
];

const demoPrompts = [
  { label: "학원 환불", text: "초등학생 영어학원 3개월분을 선결제했습니다. 한 달 이용 후 중도 해지를 요청했지만 할인 상품이라 환불이 안 된다고 합니다." },
  { label: "어린이집 사고", text: "아이 하원 후 멍을 발견했습니다. 어린이집에서 사고 경위와 CCTV 열람 절차 안내를 미루고 있습니다." },
  { label: "육아휴직", text: "회사원이며 출산전후휴가와 육아휴직 신청 시기, 회사가 거부할 때 확인할 절차를 알고 싶습니다." },
];

function parseRoute(): { parent: ParentTab; admin: AdminTab | null } {
  const value = window.location.hash.replace(/^#\/?/, "");
  if (value.startsWith("admin")) {
    const admin = value.split("/")[1] as AdminTab | undefined;
    return { parent: "today", admin: adminTabs.some((item) => item.key === admin) ? admin! : "operations" };
  }
  return { parent: parentTabs.some((item) => item.key === value) ? value as ParentTab : "today", admin: null };
}

function navigate(path: string) {
  window.location.hash = path;
}

function stageFromBirthMonth(birthMonth: string): string {
  if (!birthMonth) return "프로필 미등록";
  const birth = new Date(`${birthMonth}-01T00:00:00`);
  const now = new Date();
  const months = (now.getFullYear() - birth.getFullYear()) * 12 + now.getMonth() - birth.getMonth();
  if (months < 0) return "출산 준비";
  if (months < 12) return "영아기";
  if (months < 36) return "걸음마기";
  if (months < 84) return "유아기";
  return "학령기";
}

function LoadingPanel() {
  return <div className="panel loading-panel" role="status"><Loader2 className="spin" aria-hidden="true" /> 화면을 준비하고 있습니다.</div>;
}

export default function App() {
  const [route, setRoute] = useState(parseRoute);
  const [profile, setProfile] = useState<FamilyProfile>({ birthMonth: "", region: "", household: "two-caregivers" });
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [sessions, setSessions] = useState<ConsultationSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<ConsultationSession | null>(null);
  const [historyRestricted, setHistoryRestricted] = useState(false);
  const [query, setQuery] = useState("");
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState("상황을 입력하면 근거와 다음 행동을 분리해 정리합니다.");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    const update = () => setRoute(parseRoute());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);

  useEffect(() => {
    const label = route.admin ? "운영자 콘솔" : parentTabs.find((item) => item.key === route.parent)?.label;
    document.title = `${label || "오늘"} | 자람법`;
  }, [route]);

  useEffect(() => {
    void fetch("/api/health").then((response) => response.json()).then(setHealth).catch(() => setHealth(null));
    void loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const response = await apiFetch("/api/history");
      if (response.status === 401) {
        setHistoryRestricted(true);
        return false;
      }
      if (!response.ok) return false;
      const payload = await response.json();
      const items = payload.data as ConsultationSession[];
      setSessions(items);
      setSelectedSession((current) => current || items[0] || null);
      setHistoryRestricted(false);
      return true;
    } catch {
      return false;
    }
  };

  const familyStage = useMemo(() => stageFromBirthMonth(profile.birthMonth), [profile.birthMonth]);
  const profileReady = Boolean(profile.birthMonth && profile.region);
  const engineLabel = health?.python_bridge.source_present && health.python_bridge.workflow_present ? "상담 엔진 준비" : "내장 기준 모드";

  const sendConsultation = async (event: FormEvent) => {
    event.preventDefault();
    if (!query.trim() || sending) return;
    setSending(true);
    setNotice("입력 보호, 근거 확인, 답변 검증을 순서대로 진행하고 있습니다.");
    try {
      const response = await fetch("/api/consult", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: query.trim(),
          clientType: "layperson",
          language: "ko",
          profile: {
            reference_date: new Date().toISOString().slice(0, 10),
            region: profile.region,
            children: profile.birthMonth ? [{ birth_date: `${profile.birthMonth}-01` }] : [],
            parents: [{ role: "caregiver", household_type: profile.household }],
            flags: [profile.household],
          },
        }),
      });
      if (!response.ok) throw new Error(await readApiError(response, "상담을 생성하지 못했습니다."));
      const payload = await response.json();
      const session = payload.data as ConsultationSession;
      setSelectedSession(session);
      setSessions((current) => [session, ...current.filter((item) => item.id !== session.id)]);
      setQuery("");
      setNotice(payload.failover
        ? "실시간 상담 엔진 대신 앱에 포함된 기준 자료로 정리했습니다. 공식 출처를 다시 확인하세요."
        : "상담 정리가 완료되었습니다. 근거와 다음 행동을 확인하세요.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "상담 처리 중 오류가 발생했습니다.");
    } finally {
      setSending(false);
    }
  };

  const handleTabKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % parentTabs.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + parentTabs.length) % parentTabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = parentTabs.length - 1;
    else return;
    event.preventDefault();
    navigate(parentTabs[next].key);
    tabRefs.current[next]?.focus();
  };

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">본문으로 건너뛰기</a>
      <header className="app-header">
        <button type="button" className="brand-button" onClick={() => navigate("today")} aria-label="자람법 오늘 화면">
          <span className="brand-mark"><Scale aria-hidden="true" /></span>
          <span><strong>자람법</strong><small>가족 법령·정책 동반자</small></span>
        </button>
        <div className="header-actions">
          <span className="engine-status"><span aria-hidden="true" />{engineLabel}</span>
          <button type="button" className="operator-link" onClick={() => navigate("admin/operations")}>
            <Lock aria-hidden="true" /> 운영자
          </button>
        </div>
      </header>

      {route.admin ? (
        <AdminConsole
          activeTab={route.admin}
          sessions={sessions}
          selectedSession={selectedSession}
          onSelectSession={setSelectedSession}
          onReloadSessions={loadSessions}
          onSessionUpdated={(updated) => {
            setSelectedSession(updated);
            setSessions((current) => current.map((item) => item.id === updated.id ? updated : item));
          }}
        />
      ) : (
        <>
          <nav className="parent-tabs" aria-label="부모 화면 탐색">
            <div className="parent-tablist" role="tablist" aria-label="자람법 주요 화면">
              {parentTabs.map((tab, index) => {
                const Icon = tab.icon;
                const active = route.parent === tab.key;
                return (
                  <button
                    key={tab.key}
                    ref={(element) => { tabRefs.current[index] = element; }}
                    type="button"
                    id={`tab-${tab.key}`}
                    role="tab"
                    aria-selected={active}
                    aria-controls={`panel-${tab.key}`}
                    tabIndex={active ? 0 : -1}
                    className={active ? "is-active" : ""}
                    onClick={() => navigate(tab.key)}
                    onKeyDown={(event) => handleTabKey(event, index)}
                  >
                    <Icon aria-hidden="true" /> {tab.label}
                  </button>
                );
              })}
            </div>
          </nav>

          <main id="main-content" className="main-content">
            {route.parent === "today" && (
              <TodayView
                profile={profile}
                setProfile={setProfile}
                familyStage={familyStage}
                profileReady={profileReady}
                health={health}
                latestSession={selectedSession}
              />
            )}
            {route.parent === "consult" && (
              <ConsultView
                profileReady={profileReady}
                familyStage={familyStage}
                historyRestricted={historyRestricted}
                sessions={sessions}
                selectedSession={selectedSession}
                setSelectedSession={setSelectedSession}
                query={query}
                setQuery={setQuery}
                sending={sending}
                notice={notice}
                onSubmit={sendConsultation}
              />
            )}
            {route.parent === "documents" && <Suspense fallback={<LoadingPanel />}><DocumentSummarizer /></Suspense>}
            {route.parent === "laws" && <Suspense fallback={<LoadingPanel />}><LawExplorer /></Suspense>}
          </main>
        </>
      )}

      <footer className="app-footer">
        <span>자람법은 법률 자문이 아닌 양육 정보 보조 도구입니다.</span>
        <span>고위험 사안은 관계기관 또는 전문가 확인을 우선합니다.</span>
      </footer>
    </div>
  );
}

function TodayView({
  profile,
  setProfile,
  familyStage,
  profileReady,
  health,
  latestSession,
}: {
  profile: FamilyProfile;
  setProfile: (profile: FamilyProfile) => void;
  familyStage: string;
  profileReady: boolean;
  health: HealthStatus | null;
  latestSession: ConsultationSession | null;
}) {
  return (
    <div id="panel-today" role="tabpanel" aria-labelledby="tab-today">
      <section className="briefing-hero">
        <div>
          <span className="hero-kicker"><Sparkles aria-hidden="true" /> 오늘 놓치지 않을 일을 먼저</span>
          <h1>우리 가족에게 필요한 권리와 기한을 한곳에서 확인하세요.</h1>
          <p>최소한의 가족 정보와 최근 상황으로 적용 가능한 법령, 지원, 다음 행동을 구분해 정리합니다.</p>
          <button type="button" className="primary-button" onClick={() => navigate("consult")}>
            상황 상담 시작 <ArrowRight aria-hidden="true" />
          </button>
        </div>
      </section>

      <section className="today-grid" aria-label="오늘의 가족 브리핑">
        <form className="panel family-profile" onSubmit={(event) => event.preventDefault()}>
          <div className="section-title">
            <div><p className="eyebrow">가족 프로필</p><h2>{familyStage}</h2></div>
            <span className={`status-badge ${profileReady ? "tone-good" : "tone-attention"}`}>{profileReady ? "상담 준비됨" : "2개 항목 필요"}</span>
          </div>
          <div className="form-grid">
            <div>
              <label className="field-label" htmlFor="birth-month">아이 출생 연월</label>
              <input id="birth-month" type="month" value={profile.birthMonth} onChange={(event) => setProfile({ ...profile, birthMonth: event.target.value })} />
            </div>
            <div>
              <label className="field-label" htmlFor="region">거주 지역</label>
              <select id="region" value={profile.region} onChange={(event) => setProfile({ ...profile, region: event.target.value })}>
                <option value="">선택</option><option>서울</option><option>경기</option><option>인천</option><option>부산</option><option>대구</option><option>광주</option><option>대전</option><option>울산</option><option>세종</option><option>강원</option><option>충북</option><option>충남</option><option>전북</option><option>전남</option><option>경북</option><option>경남</option><option>제주</option>
              </select>
            </div>
            <div>
              <label className="field-label" htmlFor="household">가족 상황</label>
              <select id="household" value={profile.household} onChange={(event) => setProfile({ ...profile, household: event.target.value as FamilyProfile["household"] })}>
                <option value="two-caregivers">함께 양육</option><option value="single-caregiver">한부모 양육</option><option value="expecting">출산 준비</option>
              </select>
            </div>
          </div>
          <p className="privacy-note"><ShieldCheck aria-hidden="true" /> 이름과 정확한 주소는 받지 않으며, 입력값은 이 화면을 새로 열면 초기화됩니다.</p>
        </form>

        <section className="panel priority-panel">
          <div className="section-title"><div><p className="eyebrow">먼저 확인</p><h2>오늘의 체크리스트</h2></div><ClipboardCheck aria-hidden="true" /></div>
          <div className="priority-list">
            <button type="button" onClick={() => navigate("consult")}><MessageSquare aria-hidden="true" /><span><strong>최근 사건 정리</strong><small>기관 답변, 날짜, 금액을 함께 입력하세요.</small></span><ArrowRight aria-hidden="true" /></button>
            <button type="button" onClick={() => navigate("laws")}><BookOpen aria-hidden="true" /><span><strong>적용 법령 확인</strong><small>내장 자료의 최신성을 공식 출처에서 다시 확인하세요.</small></span><ArrowRight aria-hidden="true" /></button>
            <button type="button" onClick={() => navigate("documents")}><FileText aria-hidden="true" /><span><strong>받은 문서 정리</strong><small>개인정보를 지운 텍스트에서 쟁점을 찾습니다.</small></span><ArrowRight aria-hidden="true" /></button>
          </div>
        </section>

        <section className="panel support-panel">
          <div className="section-title"><div><p className="eyebrow">지원·기한</p><h2>확인할 항목</h2></div><CalendarClock aria-hidden="true" /></div>
          {profileReady ? (
            <div className="brief-list">
              <div><strong>{familyStage} 지원 조건 확인</strong><span>지역과 소득 등 추가 조건은 상담 결과에서 구분합니다.</span></div>
              <div><strong>신청·통지 기한 확인</strong><span>정확한 사건 날짜를 입력하면 다음 행동과 함께 정리합니다.</span></div>
            </div>
          ) : <p className="empty-copy">출생 연월과 지역을 입력하면 확인할 지원과 기한의 범위를 좁힐 수 있습니다.</p>}
          <div className="dataset-strip"><Database aria-hidden="true" /><span>내장 기준 자료</span><strong>법령 {health?.seed_data.laws ?? "-"} · 지원 {health?.seed_data.supports ?? "-"}</strong></div>
        </section>

        <section className="panel recent-panel">
          <div className="section-title"><div><p className="eyebrow">최근 상담</p><h2>{latestSession?.title || "아직 상담이 없습니다"}</h2></div></div>
          {latestSession ? (
            <><p>{latestSession.messages.at(-1)?.text}</p><button type="button" className="text-link" onClick={() => navigate("consult")}>상담 결과 열기 <ArrowRight aria-hidden="true" /></button></>
          ) : <p className="empty-copy">상황을 상담하면 근거, 확인 상태, 다음 행동이 여기에 연결됩니다.</p>}
        </section>
      </section>
    </div>
  );
}

function ConsultView({
  profileReady,
  familyStage,
  historyRestricted,
  sessions,
  selectedSession,
  setSelectedSession,
  query,
  setQuery,
  sending,
  notice,
  onSubmit,
}: {
  profileReady: boolean;
  familyStage: string;
  historyRestricted: boolean;
  sessions: ConsultationSession[];
  selectedSession: ConsultationSession | null;
  setSelectedSession: (session: ConsultationSession) => void;
  query: string;
  setQuery: (query: string) => void;
  sending: boolean;
  notice: string;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <section id="panel-consult" role="tabpanel" aria-labelledby="tab-consult" className="consult-layout">
      <aside className="consult-sidebar">
        <form className="panel consult-form" onSubmit={onSubmit}>
          <div className="section-title">
            <div><p className="eyebrow">상황 상담</p><h1>무슨 일이 있었나요?</h1></div>
            <span className={`status-badge ${profileReady ? "tone-good" : "tone-neutral"}`}>{familyStage}</span>
          </div>
          {!profileReady && <button type="button" className="profile-reminder" onClick={() => navigate("today")}><AlertCircle aria-hidden="true" /> 가족 프로필을 입력하면 결과 범위를 좁힐 수 있습니다.</button>}
          <div className="prompt-options" aria-label="상담 예시">
            {demoPrompts.map((item) => <button type="button" key={item.label} onClick={() => setQuery(item.text)}>{item.label}</button>)}
          </div>
          <label className="field-label" htmlFor="consult-query">사실관계와 궁금한 점</label>
          <textarea id="consult-query" value={query} onChange={(event) => setQuery(event.target.value)} disabled={sending} placeholder="날짜, 기관, 금액, 상대방 답변을 사실대로 적어주세요. 이름과 정확한 주소는 제외하세요." />
          <button className="primary-button" type="submit" disabled={sending || !query.trim()}>
            {sending ? <Loader2 className="spin" aria-hidden="true" /> : <Play aria-hidden="true" />}{sending ? "검토 중" : "근거와 다음 행동 정리"}
          </button>
          <p className="form-status" role="status" aria-live="polite">{notice}</p>
        </form>

        <section className="panel history-panel">
          <div className="section-title"><div><p className="eyebrow">이 화면의 기록</p><h2>상담 목록</h2></div><span className="status-badge tone-neutral">{sessions.length}</span></div>
          {historyRestricted && <p className="restricted-note"><Lock aria-hidden="true" /> 이전 상담 기록은 운영자 인증 후 조회할 수 있습니다.</p>}
          <div className="select-list compact">
            {sessions.map((session) => (
              <button type="button" className={`select-row ${selectedSession?.id === session.id ? "is-selected" : ""}`} key={session.id} onClick={() => setSelectedSession(session)}>
                <MessageSquare aria-hidden="true" /><span><strong>{session.title}</strong><small>{new Date(session.date).toLocaleDateString("ko-KR")}</small></span>
              </button>
            ))}
          </div>
        </section>
      </aside>

      <div className="consult-results">
        {selectedSession ? <ConsultationResult session={selectedSession} /> : (
          <div className="panel empty-state large"><Layers3 aria-hidden="true" /><strong>상담을 시작하면 근거와 다음 행동이 여기에 정리됩니다.</strong></div>
        )}
      </div>
    </section>
  );
}

function ConsultationResult({ session }: { session: ConsultationSession }) {
  const fallback = session.integration?.backend !== "python-engine";
  return (
    <>
      <section className="panel conversation-panel">
        <div className="section-title">
          <div><p className="eyebrow">상담 결과</p><h1>{session.title}</h1></div>
          <span className={`status-badge ${fallback ? "tone-attention" : "tone-good"}`}>{fallback ? "내장 기준" : "워크플로우 검증"}</span>
        </div>
        {fallback && <div className="fallback-banner"><AlertCircle aria-hidden="true" /> 실시간 연동이 아닌 앱 내 기준 자료로 작성했습니다. 공식 법령과 기관 안내를 다시 확인하세요.</div>}
        <div className="conversation-list">
          {session.messages.map((message) => (
            <article key={message.id} className={message.sender === "user" ? "message-user" : "message-agent"}>
              <strong>{message.sender === "user" ? "보호자" : "자람법"}</strong>
              <p>{message.text}</p>
              <time dateTime={message.timestamp}>{new Date(message.timestamp).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}</time>
            </article>
          ))}
        </div>
      </section>

      <div className="result-grid">
        {session.riskAnalysis && <section className="panel"><Suspense fallback={<LoadingPanel />}><DisputeChart analysis={session.riskAnalysis} /></Suspense></section>}
        <WorkflowSummary session={session} />
      </div>
    </>
  );
}

function WorkflowSummary({ session }: { session: ConsultationSession }) {
  const report = asRecord(session.workflowReport);
  const supports = asArray(report.support_matches);
  const rights = asArray(report.rights_cards);
  const drafts = asArray(report.draft_documents);
  const verifier = asRecord(report.verifier_results);
  return (
    <section className="panel workflow-summary">
      <div className="section-title"><div><p className="eyebrow">근거와 산출물</p><h2>확인 결과</h2></div><span className="status-badge tone-neutral">{session.auditLogId || "감사 ID 없음"}</span></div>
      <div className="metric-grid">
        <Metric icon={BookOpen} label="법령" value={session.recommendedLaws.length} />
        <Metric icon={CheckCircle2} label="권리 안내" value={rights.length} />
        <Metric icon={FileText} label="문서 초안" value={drafts.length} />
        <Metric icon={CalendarClock} label="지원 제도" value={supports.length} />
      </div>
      <h3>추천 법령</h3>
      <div className="brief-list">
        {session.recommendedLaws.slice(0, 4).map((law) => <div key={law.id}><strong>{law.title}</strong><span>{law.summary}</span></div>)}
        {!session.recommendedLaws.length && <p className="empty-copy">연결된 법령이 없습니다.</p>}
      </div>
      <div className="verification-receipt">
        <ShieldCheck aria-hidden="true" />
        <div><strong>검증 영수증</strong><span>확인 {Number(verifier.verified_count ?? 0)} · 부분 확인 {Number(verifier.partial_count ?? 0)} · 추가 검토 {Number(verifier.unverifiable_count ?? 0)}</span></div>
      </div>
      <div className="legal-disclaimer">법령명, 조문, 시행일, 공식 출처가 모두 확인되지 않은 항목은 제출 전에 다시 검증하세요.</div>
    </section>
  );
}

function AdminConsole({
  activeTab,
  sessions,
  selectedSession,
  onSelectSession,
  onReloadSessions,
  onSessionUpdated,
}: {
  activeTab: AdminTab;
  sessions: ConsultationSession[];
  selectedSession: ConsultationSession | null;
  onSelectSession: (session: ConsultationSession) => void;
  onReloadSessions: () => Promise<boolean>;
  onSessionUpdated: (session: ConsultationSession) => void;
}) {
  const [token, setToken] = useState(getOperatorToken());
  const [authenticated, setAuthenticated] = useState(false);
  const [authMessage, setAuthMessage] = useState("운영 기록과 전문가 검토는 별도 인증이 필요합니다.");

  const verify = async () => {
    setOperatorToken(token);
    try {
      const response = await apiFetch("/api/operator/status");
      if (!response.ok) throw new Error(await readApiError(response, "운영자 인증에 실패했습니다."));
      setAuthenticated(true);
      setAuthMessage("운영자 인증이 확인되었습니다.");
      await onReloadSessions();
    } catch (error) {
      setAuthenticated(false);
      setAuthMessage(error instanceof Error ? error.message : "운영자 인증에 실패했습니다.");
    }
  };

  useEffect(() => { void verify(); }, []);

  const invalidate = () => {
    setAuthenticated(false);
    setOperatorToken("");
    setToken("");
    setAuthMessage("인증이 만료되었습니다. 운영자 토큰을 다시 입력하세요.");
  };

  return (
    <main id="main-content" className="admin-shell">
      <div className="admin-header">
        <div><p className="eyebrow">분리된 운영 영역</p><h1>자람법 운영자 콘솔</h1><span>부모 화면과 분리된 감사·검토·보안 도구입니다.</span></div>
        <button type="button" className="secondary-button" onClick={() => navigate("today")}>부모 화면으로</button>
      </div>

      {!authenticated ? (
        <form className="panel auth-panel" onSubmit={(event) => { event.preventDefault(); void verify(); }}>
          <KeyRound aria-hidden="true" />
          <div><h2>운영자 인증</h2><p>외부 바인딩에서는 `JARAMLAW_API_TOKEN` 값을 입력합니다. 로컬 개발 모드는 비워둘 수 있습니다.</p></div>
          <label className="field-label" htmlFor="operator-token">운영자 토큰</label>
          <input id="operator-token" type="password" value={token} onChange={(event) => setToken(event.target.value)} autoComplete="current-password" />
          <button type="submit" className="primary-button">인증 확인</button>
          <p className="form-status" role="status" aria-live="polite">{authMessage}</p>
        </form>
      ) : (
        <>
          <nav className="admin-tabs" aria-label="운영자 도구">
            {adminTabs.map((tab) => {
              const Icon = tab.icon;
              return <button type="button" className={activeTab === tab.key ? "is-active" : ""} key={tab.key} onClick={() => navigate(`admin/${tab.key}`)}><Icon aria-hidden="true" />{tab.label}</button>;
            })}
          </nav>
          <Suspense fallback={<LoadingPanel />}>
            {activeTab === "operations" && <OperationsPanel onUnauthorized={invalidate} />}
            {activeTab === "security" && <SecurityConsole onUnauthorized={invalidate} />}
            {activeTab === "reviews" && (
              <ReviewQueue
                sessions={sessions}
                selectedSession={selectedSession}
                onSelectSession={onSelectSession}
                onSessionUpdated={onSessionUpdated}
                onUnauthorized={invalidate}
              />
            )}
          </Suspense>
        </>
      )}
    </main>
  );
}

function ReviewQueue({ sessions, selectedSession, onSelectSession, onSessionUpdated, onUnauthorized }: {
  sessions: ConsultationSession[];
  selectedSession: ConsultationSession | null;
  onSelectSession: (session: ConsultationSession) => void;
  onSessionUpdated: (session: ConsultationSession) => void;
  onUnauthorized: () => void;
}) {
  return (
    <section className="admin-review-layout">
      <div className="panel">
        <div className="section-title"><div><p className="eyebrow">검토 대기열</p><h2>상담 기록</h2></div><span className="status-badge tone-neutral">{sessions.length}</span></div>
        <div className="select-list">
          {sessions.map((session) => <button type="button" className={`select-row ${selectedSession?.id === session.id ? "is-selected" : ""}`} key={session.id} onClick={() => onSelectSession(session)}><MessageSquare aria-hidden="true" /><span><strong>{session.title}</strong><small>{session.expertFeedback?.status === "verified" ? "전문가 확인 완료" : "검토 필요"}</small></span></button>)}
        </div>
      </div>
      {selectedSession ? <ExpertReviewPanel session={selectedSession} onFeedbackSaved={onSessionUpdated} onUnauthorized={onUnauthorized} /> : <div className="panel empty-state"><UserCheck aria-hidden="true" /><strong>검토할 상담을 선택하세요.</strong></div>}
    </section>
  );
}

function OperationsPanel({ onUnauthorized }: { onUnauthorized: () => void }) {
  const [status, setStatus] = useState<JsonRecord>({});
  const [audits, setAudits] = useState<JsonRecord[]>([]);
  const [traces, setTraces] = useState<JsonRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [receipt, setReceipt] = useState("운영 상태를 불러오는 중입니다.");

  const load = async () => {
    setLoading(true);
    try {
      const responses = await Promise.all([
        apiFetch("/api/ops/workflow/status"),
        apiFetch("/api/ops/audit/logs?limit=8"),
        apiFetch("/api/ops/traces?limit=12"),
      ]);
      if (responses.some((response) => response.status === 401)) return onUnauthorized();
      if (responses.some((response) => !response.ok)) throw new Error("운영 상태 일부를 불러오지 못했습니다.");
      const [statusPayload, auditPayload, tracePayload] = await Promise.all(responses.map((response) => response.json()));
      setStatus(asRecord(statusPayload.data));
      setAudits(asArray(auditPayload.data));
      setTraces(asArray(tracePayload.data));
      setReceipt("최신 운영 상태를 확인했습니다.");
    } catch (error) {
      setReceipt(error instanceof Error ? error.message : "운영 상태를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const publish = async () => {
    if (!confirmed) return setReceipt("로컬 운영 스냅샷 기록 확인란을 먼저 선택하세요.");
    const response = await apiFetch("/api/ops/workflow/publish", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note: "Operator UI snapshot" }) });
    if (response.status === 401) return onUnauthorized();
    if (!response.ok) return setReceipt(await readApiError(response, "스냅샷을 기록하지 못했습니다."));
    const payload = await response.json();
    setReceipt(`로컬 기록 완료 · ${String(payload.data.workflow_sha1 || "no-sha").slice(0, 12)}`);
    setConfirmed(false);
    await load();
  };

  const workflow = asRecord(status.workflow);
  const topology = asRecord(status.topology);
  const trace = asRecord(status.trace);
  const budget = asRecord(status.budget);
  return (
    <section className="admin-stack">
      <div className="panel">
        <div className="section-title"><div><p className="eyebrow">운영 상태</p><h2>상담 워크플로우</h2></div><button type="button" className="icon-button" aria-label="운영 상태 새로고침" onClick={() => void load()} disabled={loading}><RefreshCw className={loading ? "spin" : ""} aria-hidden="true" /></button></div>
        <div className="metric-grid admin-metrics">
          <Metric icon={Layers3} label="팀 구성" value={topology.present ? "준비" : "누락"} />
          <Metric icon={Cpu} label="워크플로우" value={workflow.present ? "준비" : "누락"} />
          <Metric icon={Activity} label="최근 추적" value={Number(trace.recent_count ?? 0)} />
          <Metric icon={Database} label="실행 한도" value={`$${Number(budget.per_run_limit_usd ?? 0.25).toFixed(2)}`} />
        </div>
        <div className="approval-box">
          <label><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> 현재 상태를 `runs/workflow-publish.json`에 로컬 기록합니다.</label>
          <button type="button" className="primary-button" onClick={() => void publish()} disabled={!confirmed}>운영 스냅샷 기록</button>
        </div>
        <p className="form-status" role="status" aria-live="polite">{receipt}</p>
      </div>
      <div className="admin-columns">
        <AuditPanel title="최근 감사 기록" items={audits} primary="audit_log_id" secondary="generated_at" />
        <AuditPanel title="워크플로우 이벤트" items={traces} primary="node" secondary="generated_at" />
      </div>
    </section>
  );
}

function AuditPanel({ title, items, primary, secondary }: { title: string; items: JsonRecord[]; primary: string; secondary: string }) {
  return <section className="panel"><div className="section-title"><h2>{title}</h2><span className="status-badge tone-neutral">{items.length}</span></div><div className="audit-list">{items.map((item, index) => <div className="audit-row" key={`${recordString(item, primary, title)}-${index}`}><span className="status-dot" aria-hidden="true" /><div><strong>{recordString(item, primary, title)}</strong><small>{recordString(item, "source_file", "로컬 기록")}</small></div><time>{recordString(item, secondary, "시간 없음")}</time></div>)}{!items.length && <p className="empty-copy">표시할 기록이 없습니다.</p>}</div></section>;
}

function Metric({ icon: Icon, label, value }: { icon: typeof Activity; label: string; value: string | number }) {
  return <div className="metric"><Icon aria-hidden="true" /><span>{label}</span><strong>{value}</strong></div>;
}

function asRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : {};
}

function asArray(value: unknown): JsonRecord[] {
  return Array.isArray(value) ? value.map(asRecord) : [];
}

function recordString(record: JsonRecord, key: string, fallback: string): string {
  const value = record[key];
  return typeof value === "string" && value.trim() ? value : fallback;
}
