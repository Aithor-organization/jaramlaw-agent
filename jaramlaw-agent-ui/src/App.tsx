import {
  FormEvent,
  Fragment,
  KeyboardEvent,
  ReactNode,
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
  Gift,
  Home,
  KeyRound,
  Layers3,
  Loader2,
  Lock,
  MessageSquare,
  Play,
  Plus,
  RefreshCw,
  Scale,
  ShieldCheck,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { apiFetch, getOperatorToken, readApiError, setOperatorToken } from "./api";
import type {
  CalculationBreakdown,
  CaseData,
  ConsultationSession,
  DraftDocument,
  HealthStatus,
  WorkflowReport,
} from "./types";

const DocumentSummarizer = lazy(() => import("./components/DocumentSummarizer").then((module) => ({ default: module.DocumentSummarizer })));
const LawExplorer = lazy(() => import("./components/LawExplorer").then((module) => ({ default: module.LawExplorer })));
const DisputeChart = lazy(() => import("./components/DisputeChart").then((module) => ({ default: module.DisputeChart })));
const ExpertReviewPanel = lazy(() => import("./components/ExpertReviewPanel").then((module) => ({ default: module.ExpertReviewPanel })));
const SecurityConsole = lazy(() => import("./components/SecurityConsole").then((module) => ({ default: module.SecurityConsole })));

type ParentTab = "today" | "support" | "consult" | "documents" | "laws";
type AdminTab = "operations" | "reviews" | "security";
type JsonRecord = Record<string, unknown>;

// 봇 답변은 markdown이다. 예전엔 <p>에 그대로 넣어 ###·**·- 기호가 날것으로 보였다
// (사용자 지적, 2026-07-15). 답변이 쓰는 부분집합(헤더/볼드/목록/링크/인용/구분선)만
// 가볍게 렌더한다 — 외부 markdown 의존성 없이. 인라인: **볼드**, [텍스트](url).
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const regex = /(\*\*([^*]+)\*\*)|(\[([^\]]+)\]\((https?:\/\/[^)\s]+)\))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (m[1]) nodes.push(<strong key={`${keyPrefix}-b${i}`}>{m[2]}</strong>);
    else if (m[3]) nodes.push(<a key={`${keyPrefix}-a${i}`} href={m[5]} target="_blank" rel="noopener noreferrer">{m[4]}</a>);
    last = m.index + m[0].length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function MarkdownMessage({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;
  const isBullet = (l: string) => /^\s*[-*]\s/.test(l);
  const isOrdered = (l: string) => /^\s*\d+\.\s/.test(l);
  while (i < lines.length) {
    const raw = lines[i];
    const trimmed = raw.trim();
    if (trimmed === "") { i++; continue; }
    if (trimmed === "---" || trimmed === "***") { blocks.push(<hr key={key++} />); i++; continue; }
    const h = /^(#{1,6})\s+(.*)$/.exec(trimmed);
    if (h) {
      blocks.push(<p key={key++} className={`md-h md-h${h[1].length}`}>{renderInline(h[2], `h${key}`)}</p>);
      i++;
      continue;
    }
    if (trimmed.startsWith(">")) {
      const quote: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        quote.push(lines[i].trim().replace(/^>\s?/, ""));
        i++;
      }
      blocks.push(<blockquote key={key++}>{renderInline(quote.join(" "), `q${key}`)}</blockquote>);
      continue;
    }
    if (isOrdered(raw)) {
      const items: ReactNode[] = [];
      while (i < lines.length && isOrdered(lines[i])) {
        const content = lines[i].replace(/^\s*\d+\.\s/, "");
        i++;
        const subs: string[] = [];
        while (i < lines.length && /^\s{2,}[-*]\s/.test(lines[i])) {
          subs.push(lines[i].replace(/^\s*[-*]\s/, ""));
          i++;
        }
        items.push(
          <li key={items.length}>
            {renderInline(content, `oli${key}-${items.length}`)}
            {subs.length > 0 && (
              <ul>{subs.map((s, si) => <li key={si}>{renderInline(s, `osub${key}-${items.length}-${si}`)}</li>)}</ul>
            )}
          </li>,
        );
      }
      blocks.push(<ol key={key++}>{items}</ol>);
      continue;
    }
    if (isBullet(raw)) {
      const items: ReactNode[] = [];
      while (i < lines.length && isBullet(lines[i]) && !isOrdered(lines[i])) {
        items.push(<li key={items.length}>{renderInline(lines[i].replace(/^\s*[-*]\s/, ""), `uli${key}-${items.length}`)}</li>);
        i++;
      }
      blocks.push(<ul key={key++}>{items}</ul>);
      continue;
    }
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      lines[i].trim() !== "---" &&
      !/^#{1,6}\s/.test(lines[i].trim()) &&
      !lines[i].trim().startsWith(">") &&
      !isBullet(lines[i]) &&
      !isOrdered(lines[i])
    ) {
      para.push(lines[i].trim());
      i++;
    }
    blocks.push(<p key={key++}>{renderInline(para.join("\n"), `p${key}`)}</p>);
  }
  return <div className="md-body">{blocks}</div>;
}

interface FamilyProfile {
  household: "two-caregivers" | "single-caregiver" | "expecting";
  region: string;
  children: { birthMonth: string }[]; // 자녀별 출생 연월
  expectedDate: string; // 출산 예정일 (household=expecting)
}

// familyStage 표시는 가장 어린(최근 출생) 자녀 기준.
function primaryBirthMonth(profile: FamilyProfile): string {
  const months = profile.children.map((c) => c.birthMonth).filter(Boolean).sort();
  return months.length ? months[months.length - 1] : "";
}
// 프로필이 매칭을 돌릴 만큼 채워졌는가 (지역 + 자녀 최소 1명 또는 출산예정+예정일).
function hasProfileInput(profile: FamilyProfile): boolean {
  const anyChild = profile.children.some((c) => c.birthMonth);
  return Boolean(profile.region) && (anyChild || (profile.household === "expecting" && Boolean(profile.expectedDate)));
}

const parentTabs: Array<{ key: ParentTab; label: string; icon: typeof Home }> = [
  { key: "today", label: "오늘", icon: Home },
  { key: "support", label: "지원", icon: Gift },
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

/** Mirrors the server's inferScenarioType (server.ts) so the form can prompt for the
 * facts a scenario needs. Kept deliberately narrow: only academy_refund currently drives
 * a structured calculation (the refund figure), so only it asks for structured input. */
function inferScenario(text: string): "academy_refund" | "general" {
  return /학원|환불|교습|수강료|선결제/.test(text) ? "academy_refund" : "general";
}

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
  const [profile, setProfile] = useState<FamilyProfile>({ household: "two-caregivers", region: "", children: [{ birthMonth: "" }], expectedDate: "" });
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [sessions, setSessions] = useState<ConsultationSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<ConsultationSession | null>(null);
  const [historyRestricted, setHistoryRestricted] = useState(false);
  const [query, setQuery] = useState("");
  const [caseData, setCaseData] = useState<CaseData>({});
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

  const familyStage = useMemo(() => {
    const pm = primaryBirthMonth(profile);
    if (pm) return stageFromBirthMonth(pm);
    if (profile.household === "expecting" && profile.expectedDate) return "출산 준비";
    return "프로필 미등록";
  }, [profile]);
  const profileReady = hasProfileInput(profile);
  const engineLabel = health?.python_bridge.source_present && health.python_bridge.workflow_present ? "상담 엔진 준비" : "내장 기준 모드";

  const sendConsultation = async (event: FormEvent) => {
    event.preventDefault();
    if (!query.trim() || sending) return;
    setSending(true);
    setNotice("입력 보호, 근거 확인, 답변 검증을 순서대로 진행하고 있습니다.");
    try {
      // Only forward facts the user actually entered — an empty case_data is dropped so
      // the backend's "don't invent missing facts" contract is preserved. Also gate on the
      // current query still being a refund scenario: otherwise a leftover caseData from an
      // earlier refund consult would silently drive a later, unrelated question.
      const enteredCase = inferScenario(query.trim()) === "academy_refund"
        ? Object.fromEntries(
            Object.entries(caseData).filter(([, v]) => typeof v === "number" && Number.isFinite(v)),
          )
        : {};
      // 이어지는 문답: 현재 선택된 상담이 실시간 엔진 스레드면 그 대화를 이어간다.
      const activeThread = selectedSession && selectedSession.integration?.backend === "python-engine"
        ? selectedSession
        : null;
      const response = await fetch("/api/consult", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: query.trim(),
          clientType: "layperson",
          language: "ko",
          history: activeThread ? activeThread.messages.slice(-6) : [],
          profile: {
            reference_date: new Date().toISOString().slice(0, 10),
            region: profile.region,
            children: [
              ...profile.children.filter((c) => c.birthMonth).map((c) => ({ birth_date: `${c.birthMonth}-01` })),
              ...(profile.household === "expecting" && profile.expectedDate ? [{ expected_birth_date: profile.expectedDate }] : []),
            ],
            parents: [{ role: "caregiver", household_type: profile.household }],
            flags: [profile.household],
            ...(Object.keys(enteredCase).length ? { case_data: enteredCase } : {}),
          },
        }),
      });
      if (!response.ok) throw new Error(await readApiError(response, "상담을 생성하지 못했습니다."));
      const payload = await response.json();
      const session = payload.data as ConsultationSession;
      if (activeThread && !payload.failover) {
        // 같은 스레드에 이번 문답(질문+답변)을 이어붙이고, 근거·리스크는 최신 결과로 갱신.
        const merged: ConsultationSession = {
          ...activeThread,
          messages: [...activeThread.messages, ...session.messages],
          workflowReport: session.workflowReport ?? activeThread.workflowReport,
          riskAnalysis: session.riskAnalysis ?? activeThread.riskAnalysis,
          recommendedLaws: session.recommendedLaws?.length ? session.recommendedLaws : activeThread.recommendedLaws,
          auditLogId: session.auditLogId ?? activeThread.auditLogId,
          integration: session.integration ?? activeThread.integration,
        };
        setSelectedSession(merged);
        setSessions((current) => current.map((item) => (item.id === activeThread.id ? merged : item)));
      } else {
        setSelectedSession(session);
        setSessions((current) => [session, ...current.filter((item) => item.id !== session.id)]);
      }
      setQuery("");
      setCaseData({}); // don't let this run's facts leak into the next consultation
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

          <main id="main-content" className="main-content" tabIndex={-1}>
            {route.parent === "today" && (
              <TodayView
                profile={profile}
                setProfile={setProfile}
                familyStage={familyStage}
                profileReady={profileReady}
                health={health}
                sessions={sessions}
                setSelectedSession={setSelectedSession}
              />
            )}
            {route.parent === "support" && (
              <SupportView profile={profile} familyStage={familyStage} />
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
                caseData={caseData}
                setCaseData={setCaseData}
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

interface BriefingSupport {
  name: string;
  amount_krw: number;
  amount_description: string;
  condition_summary: string;
  application_channel: string;
  deadline_days_left: number | null;
}
interface GovSupport {
  name: string;
  summary: string;
  content: string;
  target: string;
  agency: string;
  apply_method: string;
  deadline: string;
  detail_url: string;
}
interface BriefingData {
  life_stages: string[];
  supports: BriefingSupport[];
  events: { title: string; scheduled_date: string }[];
  rights: { title: string; holder: string }[];
  government?: GovSupport[];
}

// 프로필 → 매칭 지원제도/기한/권리 브리핑 (오늘 탭·지원 탭 공용). 프로필 변경 시 debounce 후 재조회.
function useBriefing(profile: FamilyProfile): { briefing: BriefingData | null; loading: boolean } {
  const [briefing, setBriefing] = useState<BriefingData | null>(null);
  const [loading, setLoading] = useState(false);
  const childKey = profile.children.map((c) => c.birthMonth).join(",");
  useEffect(() => {
    if (!hasProfileInput(profile)) { setBriefing(null); return; }
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const res = await apiFetch("/api/briefing", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            region: profile.region,
            household: profile.household,
            children: profile.children.filter((c) => c.birthMonth).map((c) => ({ birthMonth: c.birthMonth })),
            expectedDate: profile.household === "expecting" ? profile.expectedDate : "",
          }),
        });
        const json = await res.json();
        if (!cancelled) setBriefing(res.ok && json.status === "success" ? json.data as BriefingData : null);
      } catch {
        if (!cancelled) setBriefing(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 500);
    return () => { cancelled = true; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [childKey, profile.region, profile.household, profile.expectedDate]);
  return { briefing, loading };
}

function TodayView({
  profile,
  setProfile,
  familyStage,
  profileReady,
  health,
  sessions,
  setSelectedSession,
}: {
  profile: FamilyProfile;
  setProfile: (profile: FamilyProfile) => void;
  familyStage: string;
  profileReady: boolean;
  health: HealthStatus | null;
  sessions: ConsultationSession[];
  setSelectedSession: (session: ConsultationSession) => void;
}) {
  const openSession = (session: ConsultationSession) => {
    setSelectedSession(session);
    navigate("consult");
  };

  // 입력한 프로필로 매칭 지원제도·기한을 즉시 계산해 이 화면에 보여준다 (LLM 없이 ~1-4초).
  const { briefing, loading: briefingLoading } = useBriefing(profile);
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

      {/* 발표자료 4p '자람법 소개' — 첫 화면에서 제품 흐름(①입력→②엔진→③산출물)을 바로 전달. */}
      <section className="panel how-panel" aria-label="자람법 소개">
        <div className="section-title">
          <div><p className="eyebrow"><Sparkles aria-hidden="true" /> 자람법 소개</p><h2>묻기 전에 먼저 챙기는 가족 법령 AI 동반자</h2></div>
        </div>
        <div className="stage-grid">
          <article className="stage-card">
            <div className="stage-head"><span className="stage-num">1</span><UserCheck aria-hidden="true" /><h3>가족 정보 입력</h3></div>
            <ul>
              <li>아이 생년월일 · 지역</li>
              <li>가족 구성 · 고용 형태</li>
              <li>라이프이벤트 (임신·입학 등)</li>
              <li>받은 문서 (알림장·통지문)</li>
            </ul>
          </article>
          <article className="stage-card">
            <div className="stage-head"><span className="stage-num">2</span><Cpu aria-hidden="true" /><h3>자람법 엔진</h3></div>
            <ul>
              <li>라이프스테이지 자동 분류</li>
              <li>법령 · 지원 자동 매칭</li>
              <li>문서 분석 → 대응 설계</li>
              <li>인용 · 보안 · 안전 검증</li>
            </ul>
          </article>
          <article className="stage-card">
            <div className="stage-head"><span className="stage-num">3</span><FileText aria-hidden="true" /><h3>맞춤 산출물</h3></div>
            <ul>
              <li>적용 법령·지원 + 신청 D-day</li>
              <li>근거 조문 포함 권리 카드</li>
              <li>신고서 · 신청서 초안</li>
              <li>우리아이 법령 캘린더 (iCal)</li>
            </ul>
          </article>
        </div>
        <p className="how-tagline">검색해서 찾아 읽는 서비스가 아니라, <strong>아이의 성장 단계에 맞춰 먼저 도착하는</strong> 법령·정책 안내입니다.</p>
      </section>

      <section className="today-grid" aria-label="오늘의 가족 브리핑">
        <form className="panel family-profile" onSubmit={(event) => event.preventDefault()}>
          <div className="section-title">
            <div><p className="eyebrow">가족 프로필</p><h2>{familyStage}</h2></div>
            <span className={`status-badge ${profileReady ? "tone-good" : "tone-attention"}`}>{profileReady ? "상담 준비됨" : "2개 항목 필요"}</span>
          </div>
          <div className="form-grid">
            <div>
              <label className="field-label" htmlFor="household">가족 상황</label>
              <select id="household" value={profile.household} onChange={(event) => setProfile({ ...profile, household: event.target.value as FamilyProfile["household"] })}>
                <option value="two-caregivers">함께 양육</option><option value="single-caregiver">한부모 양육</option><option value="expecting">출산 준비</option>
              </select>
            </div>
            <div>
              <label className="field-label" htmlFor="region">거주 지역</label>
              <select id="region" value={profile.region} onChange={(event) => setProfile({ ...profile, region: event.target.value })}>
                <option value="">선택</option><option>서울</option><option>경기</option><option>인천</option><option>부산</option><option>대구</option><option>광주</option><option>대전</option><option>울산</option><option>세종</option><option>강원</option><option>충북</option><option>충남</option><option>전북</option><option>전남</option><option>경북</option><option>경남</option><option>제주</option>
              </select>
            </div>
          </div>

          {profile.household === "expecting" && (
            <div className="expecting-field">
              <label className="field-label" htmlFor="expected-date">출산 예정일</label>
              <input id="expected-date" type="date" value={profile.expectedDate} onChange={(event) => setProfile({ ...profile, expectedDate: event.target.value })} />
              <p className="privacy-note">예정일 기준으로 첫만남이용권·부모급여 등 출산 지원을 미리 안내합니다.</p>
            </div>
          )}

          <div className="children-field">
            <div className="children-head">
              <label className="field-label">자녀 {profile.household === "expecting" ? "(이미 태어난 아이가 있으면)" : ""}</label>
              <div className="children-count">
                <button
                  type="button"
                  aria-label="자녀 줄이기"
                  disabled={profile.children.length <= (profile.household === "expecting" ? 0 : 1)}
                  onClick={() => setProfile({ ...profile, children: profile.children.slice(0, -1) })}
                >−</button>
                <span>{profile.children.length}명</span>
                <button
                  type="button"
                  aria-label="자녀 늘리기"
                  disabled={profile.children.length >= 6}
                  onClick={() => setProfile({ ...profile, children: [...profile.children, { birthMonth: "" }] })}
                >+</button>
              </div>
            </div>
            {profile.children.map((child, i) => (
              <div key={i} className="child-row">
                <span className="child-label">{i + 1}째</span>
                <input
                  type="month"
                  aria-label={`${i + 1}째 아이 출생 연월`}
                  value={child.birthMonth}
                  onChange={(event) => {
                    const next = profile.children.map((c, j) => (j === i ? { birthMonth: event.target.value } : c));
                    setProfile({ ...profile, children: next });
                  }}
                />
              </div>
            ))}
            {profile.household === "expecting" && profile.children.length === 0 && (
              <p className="privacy-note">첫 아이 출산 준비 중이시면 위 예정일만 입력하셔도 됩니다.</p>
            )}
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
          <div className="section-title"><div><p className="eyebrow">지원·기한</p><h2>{familyStage} 맞춤</h2></div><CalendarClock aria-hidden="true" /></div>
          {!hasProfileInput(profile) ? (
            <p className="empty-copy">가족 상황·지역·자녀 정보를 입력하면 우리 가족에게 해당하는 지원제도와 기한을 바로 계산합니다.</p>
          ) : briefingLoading && !briefing ? (
            <p className="empty-copy">우리 가족에게 맞는 지원제도를 확인하는 중…</p>
          ) : briefing && (briefing.supports.length || briefing.events.length) ? (
            <>
              <div className="support-rows">
                {briefing.supports.slice(0, 3).map((s) => (
                  <button type="button" className="support-row" key={s.name} onClick={() => navigate("support")}>
                    <span className="support-row-main">
                      <strong>
                        {s.name}
                        {s.amount_krw > 0 ? ` · ${formatKrw(s.amount_krw)}` : s.amount_description ? ` · ${s.amount_description.split(" ")[0]}` : ""}
                      </strong>
                      {typeof s.deadline_days_left === "number" && (
                        <span className="deadline-chip">{s.deadline_days_left === 0 ? "오늘 마감" : `D-${s.deadline_days_left}`}</span>
                      )}
                    </span>
                    <ArrowRight aria-hidden="true" />
                  </button>
                ))}
                {briefing.events.slice(0, 2).map((e) => (
                  <button type="button" className="support-row" key={e.title} onClick={() => navigate("support")}>
                    <span className="support-row-main">
                      <strong>{e.title}</strong>
                      <span className="deadline-chip tone-cal">{e.scheduled_date}</span>
                    </span>
                    <ArrowRight aria-hidden="true" />
                  </button>
                ))}
              </div>
              <button type="button" className="more-button" onClick={() => navigate("support")}>
                맞춤 지원 전체 보기 <ArrowRight aria-hidden="true" />
              </button>
            </>
          ) : (
            <p className="empty-copy">입력한 프로필로 자동 매칭된 지원제도가 없습니다. 상담에서 상황을 입력하면 더 정확히 안내합니다.</p>
          )}
          <div className="dataset-strip"><Database aria-hidden="true" /><span>내장 기준 자료</span><strong>법령 {health?.seed_data.laws ?? "-"} · 지원 {health?.seed_data.supports ?? "-"}</strong></div>
        </section>

        <section className="panel recent-panel">
          <div className="section-title"><div><p className="eyebrow">최근 상담</p><h2>이어서 보기</h2></div><MessageSquare aria-hidden="true" /></div>
          {sessions.length ? (
            <div className="priority-list">
              {sessions.slice(0, 5).map((session) => (
                <button type="button" key={session.id} onClick={() => openSession(session)}>
                  <MessageSquare aria-hidden="true" />
                  <span>
                    <strong>{session.title}</strong>
                    <small>{new Date(session.date).toLocaleDateString("ko-KR", { month: "long", day: "numeric" })} · {session.integration?.connected ? "워크플로우 검증" : "내장 기준"}</small>
                  </span>
                  <ArrowRight aria-hidden="true" />
                </button>
              ))}
            </div>
          ) : <p className="empty-copy">상황을 상담하면 근거, 확인 상태, 다음 행동이 여기에 연결됩니다.</p>}
        </section>
      </section>
    </div>
  );
}

// 신청 경로 텍스트에서 공식 신청 사이트 링크를 유추한다 (알려진 채널만).
const OFFICIAL_LINKS: Array<{ match: RegExp; url: string; label: string }> = [
  { match: /복지로|국민행복카드|첫만남/, url: "https://www.bokjiro.go.kr", label: "복지로" },
  { match: /정부24/, url: "https://www.gov.kr", label: "정부24" },
  { match: /고용보험|고용센터|고용24/, url: "https://www.ei.go.kr", label: "고용보험" },
];
function officialLinkFor(channel: string): { url: string; label: string } | null {
  for (const l of OFFICIAL_LINKS) if (l.match.test(channel)) return { url: l.url, label: l.label };
  return null;
}

// 지원 전용 탭 — 입력한 프로필에 매칭된 지원제도를 상세 카드로, 캘린더·권리와 함께 정리.
function SupportView({ profile, familyStage }: { profile: FamilyProfile; familyStage: string }) {
  const { briefing, loading } = useBriefing(profile);
  return (
    <div id="panel-support" role="tabpanel" aria-labelledby="tab-support">
      <section className="panel">
        <div className="section-title"><div><p className="eyebrow"><Gift aria-hidden="true" /> 맞춤 지원</p><h2>{familyStage} 지원 혜택</h2></div></div>
        {!hasProfileInput(profile) ? (
          <p className="empty-copy">'오늘' 탭에서 가족 상황·지역·자녀 정보를 입력하면 우리 가족에게 해당하는 지원제도를 모두 정리해 드립니다.</p>
        ) : loading && !briefing ? (
          <p className="empty-copy">우리 가족에게 맞는 지원제도를 확인하는 중…</p>
        ) : briefing && briefing.supports.length ? (
          <div className="support-cards">
            {briefing.supports.map((s) => {
              const link = officialLinkFor(s.application_channel);
              return (
                <article className="support-card" key={s.name}>
                  <div className="support-card-head">
                    <h3>{s.name}</h3>
                    {typeof s.deadline_days_left === "number" && (
                      <span className="deadline-chip">{s.deadline_days_left === 0 ? "오늘 마감" : `신청 D-${s.deadline_days_left}`}</span>
                    )}
                  </div>
                  {(s.amount_description || s.amount_krw > 0) && (
                    <p className="support-amount">{s.amount_description || (formatKrw(s.amount_krw) ?? "")}</p>
                  )}
                  {s.condition_summary && <p className="support-cond">{s.condition_summary}</p>}
                  {s.application_channel && <p className="brief-meta">신청 경로: {s.application_channel}</p>}
                  {link && (
                    <a className="support-link" href={link.url} target="_blank" rel="noopener noreferrer">
                      {link.label}에서 신청하기 <ArrowRight aria-hidden="true" />
                    </a>
                  )}
                </article>
              );
            })}
          </div>
        ) : (
          <p className="empty-copy">입력한 프로필로 자동 매칭된 지원제도가 없습니다. 상담에서 상황을 입력하면 더 정확히 안내합니다.</p>
        )}
      </section>

      {briefing && briefing.government && briefing.government.length > 0 && (
        <section className="panel">
          <div className="section-title">
            <div><p className="eyebrow"><Database aria-hidden="true" /> 실시간 지자체 지원</p><h2>우리 지역 맞춤 (보조금24)</h2></div>
          </div>
          <p className="source-notice">
            정부 <strong>보조금24 오픈API</strong>에서 거주지역·자녀에 맞춰 실시간으로 가져온 지자체 지원입니다.
            (법령데이터가 아닌 행정서비스 정보 — 신청 전 공식 안내를 확인하세요.)
          </p>
          <div className="support-cards">
            {briefing.government.map((g) => (
              <article className="support-card" key={g.name + g.agency}>
                <div className="support-card-head">
                  <h3>{g.name}</h3>
                </div>
                <p className="brief-meta">{g.agency}{g.deadline ? ` · 신청기한 ${g.deadline}` : ""}</p>
                {g.content && <p className="support-cond">{g.content}</p>}
                {g.target && <p className="brief-meta">지원대상: {g.target}</p>}
                {g.detail_url && (
                  <a className="support-link" href={g.detail_url} target="_blank" rel="noopener noreferrer">
                    정부24에서 자세히 보기 <ArrowRight aria-hidden="true" />
                  </a>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      {briefing && briefing.events.length > 0 && (
        <section className="panel">
          <div className="section-title"><div><p className="eyebrow">우리아이 법령 캘린더</p><h2>다가오는 일정</h2></div><CalendarClock aria-hidden="true" /></div>
          <div className="brief-list">
            {briefing.events.map((e) => (
              <div key={e.title}><strong>{e.title}<span className="deadline-chip tone-cal">{e.scheduled_date}</span></strong></div>
            ))}
          </div>
        </section>
      )}

      {briefing && briefing.rights.length > 0 && (
        <section className="panel">
          <div className="section-title"><div><p className="eyebrow">권리 안내</p><h2>알아두면 좋은 권리</h2></div><CheckCircle2 aria-hidden="true" /></div>
          <div className="brief-list">
            {briefing.rights.map((r) => (
              <div key={r.title}><strong>{r.title}</strong>{r.holder && <span>대상: {r.holder}</span>}</div>
            ))}
          </div>
        </section>
      )}

      <p className="legal-disclaimer">지원 금액·조건은 예산·정책에 따라 달라질 수 있습니다. 신청 전 공식 사이트에서 최신 기준을 확인하세요.</p>
    </div>
  );
}

/** Fields the academy-refund calculation needs. Shown only when the query looks like a
 * refund case; leaving them blank is fine — the backend reports which facts are missing
 * rather than guessing, and the UI now surfaces that too. */
function AcademyRefundFields({ caseData, setCaseData, disabled }: {
  caseData: CaseData;
  setCaseData: (data: CaseData) => void;
  disabled: boolean;
}) {
  const fields: Array<{ key: keyof CaseData; label: string }> = [
    { key: "total_paid_krw", label: "총 결제액 (원)" },
    { key: "total_days", label: "총 수강일수 (일)" },
    { key: "days_used", label: "이용한 일수 (일)" },
    // Collected because the draft body interpolates it as "결제금액 … (N개월분)";
    // without it the backend renders a malformed "(개월분)".
    { key: "months_paid", label: "결제 개월 수 (개월)" },
    { key: "monthly_fee_krw", label: "월 수강료 (원, 선택)" },
  ];
  const update = (key: keyof CaseData, raw: string) => {
    const next = { ...caseData };
    if (raw.trim() === "") delete next[key];
    else next[key] = Number(raw);
    setCaseData(next);
  };
  // Days used cannot exceed the course length; the backend would clamp remaining days to
  // zero and emit a misleading "0원" refund, so flag it instead of silently submitting.
  const daysInconsistent =
    typeof caseData.days_used === "number" &&
    typeof caseData.total_days === "number" &&
    caseData.days_used > caseData.total_days;
  return (
    <fieldset className="case-fields">
      <legend>환불 계산에 필요한 사실 (입력 시 정확한 금액을 계산합니다)</legend>
      <div className="form-grid">
        {fields.map(({ key, label }) => (
          <div key={String(key)}>
            <label className="field-label" htmlFor={`case-${String(key)}`}>{label}</label>
            <input
              id={`case-${String(key)}`}
              type="number"
              inputMode="numeric"
              min="0"
              disabled={disabled}
              value={typeof caseData[key] === "number" ? String(caseData[key]) : ""}
              onChange={(event) => update(key, event.target.value)}
            />
          </div>
        ))}
      </div>
      {daysInconsistent && (
        <p className="case-warning" role="alert">
          이용한 일수가 총 수강일수보다 많습니다. 값을 다시 확인하세요.
        </p>
      )}
    </fieldset>
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
  caseData,
  setCaseData,
  sending,
  notice,
  onSubmit,
}: {
  profileReady: boolean;
  familyStage: string;
  historyRestricted: boolean;
  sessions: ConsultationSession[];
  selectedSession: ConsultationSession | null;
  setSelectedSession: (session: ConsultationSession | null) => void;
  query: string;
  setQuery: (query: string) => void;
  caseData: CaseData;
  setCaseData: (data: CaseData) => void;
  sending: boolean;
  notice: string;
  onSubmit: (event: FormEvent) => void;
}) {
  const isFollowUp = Boolean(selectedSession && selectedSession.integration?.backend === "python-engine");
  const composer = (
    <ChatComposer
      query={query}
      setQuery={setQuery}
      sending={sending}
      onSubmit={onSubmit}
      caseData={caseData}
      setCaseData={setCaseData}
      isFollowUp={isFollowUp}
      notice={notice}
    />
  );
  return (
    <section id="panel-consult" role="tabpanel" aria-labelledby="tab-consult" className="consult-layout">
      <aside className="consult-sidebar">
        <section className="panel history-panel">
          <div className="section-title">
            <div><p className="eyebrow">상황 상담</p><h2>상담 목록</h2></div>
            {selectedSession
              ? <button type="button" className="ghost-button" onClick={() => { setSelectedSession(null); setQuery(""); }}><Plus aria-hidden="true" /> 새 상담</button>
              : <span className={`status-badge ${profileReady ? "tone-good" : "tone-neutral"}`}>{familyStage}</span>}
          </div>
          {!profileReady && <button type="button" className="profile-reminder" onClick={() => navigate("today")}><AlertCircle aria-hidden="true" /> 가족 프로필을 입력하면 결과 범위를 좁힐 수 있습니다.</button>}
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
        {selectedSession ? (
          <ConsultationResult session={selectedSession} composer={composer} />
        ) : (
          <section className="panel chat-start">
            <div className="section-title">
              <div><p className="eyebrow">상황 상담</p><h1>무슨 일이 있었나요?</h1></div>
              <span className={`status-badge ${profileReady ? "tone-good" : "tone-neutral"}`}>{familyStage}</span>
            </div>
            <p className="chat-start-hint">아래 예시를 누르거나, 겪은 일을 직접 적어 상담을 시작하세요. 답변이 나오면 이 창에서 바로 이어서 문답할 수 있습니다.</p>
            <div className="prompt-options" aria-label="상담 예시">
              {demoPrompts.map((item) => <button type="button" key={item.label} onClick={() => setQuery(item.text)}>{item.label}</button>)}
            </div>
            {composer}
          </section>
        )}
      </div>
    </section>
  );
}

function ChatComposer({
  query,
  setQuery,
  sending,
  onSubmit,
  caseData,
  setCaseData,
  isFollowUp,
  notice,
}: {
  query: string;
  setQuery: (query: string) => void;
  sending: boolean;
  onSubmit: (event: FormEvent) => void;
  caseData: CaseData;
  setCaseData: (data: CaseData) => void;
  isFollowUp: boolean;
  notice: string;
}) {
  const scenario = inferScenario(query);
  const formRef = useRef<HTMLFormElement>(null);
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // 채팅 관례: Enter=전송, Shift+Enter=줄바꿈.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (query.trim() && !sending) formRef.current?.requestSubmit();
    }
  };
  return (
    <form ref={formRef} className="chat-composer" onSubmit={onSubmit}>
      {scenario === "academy_refund" && !isFollowUp && <AcademyRefundFields caseData={caseData} setCaseData={setCaseData} disabled={sending} />}
      {isFollowUp && <p className="followup-note"><MessageSquare aria-hidden="true" /> 이전 상담 흐름을 이어갑니다. 추가로 궁금한 점을 물어보세요.</p>}
      <div className="composer-row">
        <textarea
          id="consult-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={sending}
          rows={isFollowUp ? 2 : 3}
          placeholder={isFollowUp ? "예: 그럼 환불을 거부하면 어디에 신고하나요? (Enter 전송 · Shift+Enter 줄바꿈)" : "날짜, 기관, 금액, 상대방 답변을 사실대로 적어주세요. 이름과 정확한 주소는 제외하세요."}
        />
        <button className="primary-button send-button" type="submit" disabled={sending || !query.trim()}>
          {sending ? <Loader2 className="spin" aria-hidden="true" /> : <Play aria-hidden="true" />}
          <span>{sending ? "검토 중" : isFollowUp ? "이어서 질문" : "질문하기"}</span>
        </button>
      </div>
      {notice && <p className="form-status" role="status" aria-live="polite">{notice}</p>}
    </form>
  );
}

function ConsultationResult({ session, composer }: { session: ConsultationSession; composer?: ReactNode }) {
  const fallback = session.integration?.backend !== "python-engine";
  const canChat = session.integration?.backend === "python-engine";
  return (
    <>
      <section className="panel conversation-panel chat-window">
        <div className="section-title">
          <div><p className="eyebrow">상담 대화</p><h1>{session.title}</h1></div>
          <span className={`status-badge ${fallback ? "tone-attention" : "tone-good"}`}>{fallback ? "내장 기준" : "워크플로우 검증"}</span>
        </div>
        {fallback && <div className="fallback-banner"><AlertCircle aria-hidden="true" /> 실시간 연동이 아닌 앱 내 기준 자료로 작성했습니다. 공식 법령과 기관 안내를 다시 확인하세요.</div>}
        <div className="conversation-list">
          {session.messages.map((message) => (
            <article key={message.id} className={message.sender === "user" ? "message-user" : "message-agent"}>
              <strong>{message.sender === "user" ? "보호자" : "자람법"}</strong>
              {message.sender === "user" ? <p>{message.text}</p> : <MarkdownMessage text={message.text} />}
              <time dateTime={message.timestamp}>{new Date(message.timestamp).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}</time>
            </article>
          ))}
        </div>
        {canChat && composer}
      </section>

      <div className="result-grid">
        {session.riskAnalysis && <section className="panel"><Suspense fallback={<LoadingPanel />}><DisputeChart analysis={session.riskAnalysis} /></Suspense></section>}
        <WorkflowSummary session={session} />
      </div>
    </>
  );
}

const KRW = new Intl.NumberFormat("ko-KR");
function formatKrw(value: unknown): string | null {
  return typeof value === "number" && Number.isFinite(value) ? `${KRW.format(value)}원` : null;
}

/** Refund/settlement calculation. The backend computes it exactly (e.g. 641,667원); this
 * renders the figure and its formula, or explains which facts are missing so the user
 * knows the number was withheld for a reason rather than lost. */
function CalculationCard({ calc }: { calc: CalculationBreakdown }) {
  if (calc.status === "insufficient_facts") {
    const missingLabels: Record<string, string> = {
      total_paid_krw: "총 결제액",
      total_days: "총 수강일수",
      days_used: "이용 일수",
      monthly_fee_krw: "월 수강료",
    };
    const missing = (calc.missing ?? []).map((k) => missingLabels[k] ?? k);
    return (
      <div className="calc-card calc-incomplete">
        <strong>정산 금액 미산정</strong>
        <span>{missing.length ? `${missing.join(", ")} 정보가 있으면 정확한 금액을 계산합니다.` : "계산에 필요한 사실관계가 부족합니다."}</span>
      </div>
    );
  }
  const refund = formatKrw(calc.refund_krw);
  if (!refund) return null;
  return (
    <div className="calc-card">
      <strong>예상 정산 금액 {refund}</strong>
      {typeof calc.remaining_days === "number" && typeof calc.total_days === "number" && (
        <span>총 {formatKrw(calc.total_paid_krw)} 중 잔여 {calc.remaining_days}/{calc.total_days}일 기준</span>
      )}
      <span className="calc-note">근거 계산식으로 산출된 참고값입니다. 실제 반환액은 공식 기준으로 재확인하세요.</span>
    </div>
  );
}

function DraftCard({ draft }: { draft: DraftDocument }) {
  return (
    <div className="draft-block">
      {/* The calculation (the refund figure) stays outside the collapsible so the key
          number is always visible; only the long document body is behind the summary. */}
      {draft.calculation_breakdown && <CalculationCard calc={draft.calculation_breakdown} />}
      <details className="draft-card">
        <summary><FileText aria-hidden="true" /> {draft.title}</summary>
        {draft.body_markdown && (
          <div className="draft-body">
            <MarkdownMessage text={draft.body_markdown} />
            <button
              type="button"
              className="copy-button"
              onClick={() => { void navigator.clipboard?.writeText(draft.body_markdown ?? ""); }}
            >
              <ClipboardCheck aria-hidden="true" /> 초안 텍스트 복사
            </button>
          </div>
        )}
        {!!draft.next_actions?.length && (
          <div className="draft-actions">
            <strong>다음 행동</strong>
            <ol>{draft.next_actions.map((action, i) => <li key={i}>{action}</li>)}</ol>
          </div>
        )}
      </details>
    </div>
  );
}

function WorkflowSummary({ session }: { session: ConsultationSession }) {
  const report: WorkflowReport = session.workflowReport ?? {};
  const supports = report.support_matches ?? [];
  const rights = report.rights_cards ?? [];
  const drafts = report.draft_documents ?? [];
  const events = report.calendar?.events ?? [];
  const verifier = report.verifier_results ?? {};
  const safety = report.safety_routing;
  return (
    <section className="panel workflow-summary">
      <div className="section-title"><div><p className="eyebrow">근거와 산출물</p><h2>확인 결과</h2></div><span className="status-badge tone-neutral">{session.auditLogId || "감사 ID 없음"}</span></div>

      {safety?.triggered && (
        <div className="safety-callout" role="alert">
          <AlertCircle aria-hidden="true" />
          <div>
            <strong>안전 신호 감지 — 법령·문서 생성을 중단했습니다.</strong>
            {safety.contact && <span>먼저 연락하세요: {safety.contact}</span>}
          </div>
        </div>
      )}

      <div className="metric-grid">
        <Metric icon={BookOpen} label="법령" value={session.recommendedLaws.length} />
        <Metric icon={CheckCircle2} label="권리 안내" value={rights.length} />
        <Metric icon={FileText} label="문서 초안" value={drafts.length} />
        <Metric icon={CalendarClock} label="지원 제도" value={supports.length} />
      </div>

      {!!drafts.length && (
        <div className="artifact-block">
          <h3>문서 초안</h3>
          {drafts.map((draft, i) => <Fragment key={draft.doc_id ?? i}><DraftCard draft={draft} /></Fragment>)}
        </div>
      )}

      {!!supports.length && (
        <div className="artifact-block">
          <h3>지원 제도</h3>
          <div className="brief-list">
            {supports.map((support, i) => (
              <div key={support.support_id ?? i}>
                {/* amount_krw is 0 for variable-value benefits ("20일간 통상임금 100%" etc.);
                    show the descriptive amount there instead of a misleading "0원". */}
                <strong>{support.name}{support.amount_krw && support.amount_krw > 0 ? ` · ${formatKrw(support.amount_krw)}` : support.amount_description ? ` · ${support.amount_description}` : ""}</strong>
                <span>{support.condition_summary ?? ""}</span>
                <span className="brief-meta">
                  {support.application_channel && `신청: ${support.application_channel}`}
                  {typeof support.deadline_days_left === "number" && support.deadline_days_left >= 0 &&
                    (support.deadline_days_left === 0 ? " · 오늘 마감" : ` · D-${support.deadline_days_left}`)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!!rights.length && (
        <div className="artifact-block">
          <h3>권리 안내</h3>
          <div className="brief-list">
            {rights.map((card, i) => (
              <div key={card.card_id ?? i}>
                <strong>{card.title}</strong>
                {card.holder && <span>대상: {card.holder}</span>}
                {card.denial?.report_channel && <span className="brief-meta">신고·대응: {card.denial.report_channel}</span>}
                {card.example_denial && <span className="brief-meta">예시: {card.example_denial}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {!!events.length && (
        <div className="artifact-block">
          <h3>법령 캘린더</h3>
          <div className="brief-list">
            {events.slice(0, 6).map((event, i) => (
              <div key={i}>
                <strong>{event.title}</strong>
                {event.scheduled_date && <span className="brief-meta">{event.scheduled_date}</span>}
              </div>
            ))}
          </div>
          {report.calendar?.ical_export && <p className="empty-copy">일정 {events.length}건 — iCal 내보내기 가능</p>}
        </div>
      )}

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
    <main id="main-content" className="admin-shell" tabIndex={-1}>
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
