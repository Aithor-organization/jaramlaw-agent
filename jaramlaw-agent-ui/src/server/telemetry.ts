/** 퍼널 이벤트 · 부모 피드백 기록.
 *
 * 왜 자체 기록인가 (2026-08-12):
 * 1. 광고차단·ITP로 클라이언트 추적은 국내 모바일에서 상당량이 유실된다. 여기는 서버 기록이라 안 샌다.
 * 2. GA 같은 제3자 행태 추적을 붙이면 쿠키 동의 배너가 필요해지고, 무엇보다 이 서비스가
 *    내세우는 "외부 전송 최소화"와 정면으로 충돌한다. 아동 정보를 다루는 서비스에서
 *    분석 목적으로 제3자에 데이터를 넘길 이유가 없다.
 * 3. 검증 표본이 30~50명이다. 대시보드가 아니라 **개별 경로**를 읽어야 하는 규모다.
 *
 * 무엇을 남기지 않는가 — IP · User-Agent 원문 · 질문 내용 · 아이 생년월일.
 * 남기는 것은 "언제 어느 단계를 지나갔나"뿐이다. 방문자 식별자는 브라우저 탭 수명
 * (sessionStorage)만 사는 임시값이라 방문 간 추적이 불가능하다 — 재방문은 로그인
 * 사용자에 한해서만 센다. 그게 실제로 알고 싶은 리텐션이기도 하다.
 */

import fs from "fs";
import path from "path";

/** 퍼널 6단계. 순서가 의미를 갖는다 — 리포트가 이 배열 순으로 이탈률을 계산한다. */
export const FUNNEL_STEPS = [
  "landing_view",   // 첫 화면을 봤다
  "check_start",    // 진단을 시작했다
  "check_done",     // 진단 5문항을 끝냈다
  "signup_done",    // 가입까지 왔다
  "first_question", // 실제로 질문을 한 번 했다
  "return_visit",   // 가입 후 다른 날 다시 왔다
] as const;

export type FunnelStep = (typeof FUNNEL_STEPS)[number];

export interface FunnelEvent {
  ts: string;
  step: FunnelStep;
  /** 방문 단위 임시 식별자 (sessionStorage). 방문이 끝나면 사라진다. */
  vid: string;
  /** 로그인 상태면 사용자 id. 재방문·전환은 이 값으로만 잇는다. */
  uid?: string;
  device: "mobile" | "desktop";
  /** 단계별 부가 정보. 자유 텍스트·개인정보는 넣지 않는다. */
  meta?: Record<string, string | number | boolean>;
}

export interface FeedbackEntry {
  ts: string;
  text: string;
  /** 어느 화면에서 눌렀나 — 재현에 필요하다. */
  route: string;
  uid?: string;
  contact?: string;
}

let funnelDir = "";
let feedbackPath = "";

export function initTelemetry(dataRoot: string): void {
  funnelDir = path.join(dataRoot, "funnel");
  feedbackPath = path.join(dataRoot, "feedback.jsonl");
  try {
    fs.mkdirSync(funnelDir, { recursive: true });
  } catch {
    // 디렉터리를 못 만들면 기록만 못 한다. 상담은 계속돼야 하므로 던지지 않는다.
  }
}

/** 월별 파일로 쪼갠다 — 한 파일이 무한정 자라면 리포트가 느려지고 백업도 통째로 커진다. */
function currentFile(): string {
  return path.join(funnelDir, `events-${new Date().toISOString().slice(0, 7)}.jsonl`);
}

function appendLine(file: string, value: unknown): void {
  try {
    fs.appendFileSync(file, `${JSON.stringify(value)}\n`, "utf8");
  } catch {
    // 계측 실패가 서비스를 멈추면 안 된다 (Rule: success is silent, 여기선 실패도 조용히).
  }
}

export function isFunnelStep(value: unknown): value is FunnelStep {
  return typeof value === "string" && (FUNNEL_STEPS as readonly string[]).includes(value);
}

export function recordFunnelEvent(event: Omit<FunnelEvent, "ts">): void {
  if (!funnelDir) return;
  appendLine(currentFile(), { ts: new Date().toISOString(), ...event });
}

export function recordFeedback(entry: Omit<FeedbackEntry, "ts">): void {
  if (!feedbackPath) return;
  appendLine(feedbackPath, { ts: new Date().toISOString(), ...entry });
}

/** 리포트·백업용. 월 파일을 전부 읽어 시간순으로 돌려준다. */
export function readFunnelEvents(): FunnelEvent[] {
  if (!funnelDir) return [];
  let files: string[];
  try {
    files = fs.readdirSync(funnelDir).filter((f) => f.startsWith("events-") && f.endsWith(".jsonl"));
  } catch {
    return [];
  }
  const out: FunnelEvent[] = [];
  for (const file of files.sort()) {
    let raw: string;
    try {
      raw = fs.readFileSync(path.join(funnelDir, file), "utf8");
    } catch {
      continue;
    }
    for (const line of raw.split("\n")) {
      if (!line.trim()) continue;
      try {
        out.push(JSON.parse(line) as FunnelEvent);
      } catch {
        // 깨진 줄 하나가 리포트 전체를 막지 않게 한다.
      }
    }
  }
  return out.sort((a, b) => a.ts.localeCompare(b.ts));
}

export function readFeedback(): FeedbackEntry[] {
  if (!feedbackPath) return [];
  let raw: string;
  try {
    raw = fs.readFileSync(feedbackPath, "utf8");
  } catch {
    return [];
  }
  const out: FeedbackEntry[] = [];
  for (const line of raw.split("\n")) {
    if (!line.trim()) continue;
    try {
      out.push(JSON.parse(line) as FeedbackEntry);
    } catch {
      // 동일 — 한 줄 손상이 전체를 막지 않는다.
    }
  }
  return out;
}
