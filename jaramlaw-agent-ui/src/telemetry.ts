/** 퍼널 이벤트 전송 (클라이언트).
 *
 * Google Analytics를 쓰지 않는다. 이 서비스는 "아이 정보를 외부로 최소한만 보낸다"를
 * 설계 원칙으로 내세우는데, 분석 목적으로 제3자에 행태정보를 넘기면 그 원칙이 무너진다.
 * 게다가 광고차단·ITP로 국내 모바일에서는 상당량이 유실돼 수치 자체를 못 믿는다.
 *
 * 방문자 식별자는 **sessionStorage**에 둔다 — 탭을 닫으면 사라지므로 방문 간 추적이
 * 구조적으로 불가능하다. 재방문은 로그인 사용자만 세고, 그 판정에 쓰는 마지막 방문
 * 날짜(localStorage)는 '날짜'까지만 저장한다.
 */

const VID_KEY = "jaramlaw_vid";
const LAST_VISIT_KEY = "jaramlaw_last_visit";

export type FunnelStep =
  | "landing_view"
  | "check_start"
  | "check_done"
  | "signup_done"
  | "first_question"
  | "return_visit";

function visitorId(): string {
  try {
    const existing = sessionStorage.getItem(VID_KEY);
    if (existing) return existing;
    const next = (crypto.randomUUID?.() || String(Math.random()).slice(2)).slice(0, 36);
    sessionStorage.setItem(VID_KEY, next);
    return next;
  } catch {
    // 사파리 프라이빗 모드 등 저장소가 막힌 환경. 식별자 없이도 단계 수는 세어진다.
    return "";
  }
}

/** 계측 실패는 조용히 넘긴다 — 분석 때문에 부모 화면이 깨지면 본말전도다. */
export function track(step: FunnelStep, meta?: Record<string, string | number | boolean>): void {
  const payload = {
    step,
    vid: visitorId(),
    device: typeof window !== "undefined" && window.innerWidth < 768 ? "mobile" : "desktop",
    ...(meta ? { meta } : {}),
  };
  try {
    const body = JSON.stringify(payload);
    // 화면 전환 직전에 찍는 이벤트가 있어서 sendBeacon을 우선 쓴다 — fetch는 이동 중 취소된다.
    if (navigator.sendBeacon?.(("/api/events"), new Blob([body], { type: "application/json" }))) return;
    void fetch("/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    // 무시
  }
}

/**
 * 로그인 사용자가 '다른 날' 다시 들어왔으면 재방문 1회를 센다.
 *
 * 같은 날 여러 번 들어온 것은 재방문이 아니다 — 리텐션을 부풀리지 않으려고 날짜로 끊는다.
 */
export function trackReturnVisitIfNewDay(): void {
  const today = new Date().toISOString().slice(0, 10);
  try {
    const last = localStorage.getItem(LAST_VISIT_KEY);
    localStorage.setItem(LAST_VISIT_KEY, today);
    if (last && last !== today) track("return_visit", { since: last });
  } catch {
    // 저장소가 막혔으면 재방문 판정을 포기한다. 다른 지표는 그대로 걷힌다.
  }
}
