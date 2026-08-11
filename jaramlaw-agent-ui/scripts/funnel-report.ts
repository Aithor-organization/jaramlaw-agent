/** 퍼널 리포트 — `npm run funnel`
 *
 * 대시보드를 만들지 않는 이유: 검증 표본이 30~50명이다. 그 규모에서 알고 싶은 건
 * "전환율 4.2%"가 아니라 **어느 단계에서 몇 명이 사라졌나**이고, 그건 한 화면에 다 들어간다.
 *
 * 사용:
 *   npm run funnel                     로컬 데이터
 *   npm run funnel -- --days 7         최근 7일만
 *   npm run funnel -- --file backup.json   /api/ops/export 로 받은 백업 파일
 */

import fs from "fs";
import path from "path";
import { FUNNEL_STEPS, type FunnelEvent } from "../src/server/telemetry.js";

const args = process.argv.slice(2);
function flag(name: string): string | undefined {
  const index = args.indexOf(`--${name}`);
  return index >= 0 ? args[index + 1] : undefined;
}

const days = Number(flag("days") || 0);
const backupFile = flag("file");
const dataRoot = process.env.JARAMLAW_DATA_DIR || path.resolve(process.cwd(), "..");

function loadEvents(): FunnelEvent[] {
  if (backupFile) {
    const parsed = JSON.parse(fs.readFileSync(backupFile, "utf8"));
    return (parsed?.data?.funnel ?? []) as FunnelEvent[];
  }
  const dir = path.join(dataRoot, "funnel");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((f) => f.startsWith("events-") && f.endsWith(".jsonl"))
    .sort()
    .flatMap((f) => fs.readFileSync(path.join(dir, f), "utf8")
      .split("\n")
      .filter((line) => line.trim())
      .flatMap((line) => { try { return [JSON.parse(line) as FunnelEvent]; } catch { return []; } }));
}

let events = loadEvents();
if (days > 0) {
  const cutoff = new Date(Date.now() - days * 86400_000).toISOString();
  events = events.filter((e) => e.ts >= cutoff);
}

if (!events.length) {
  console.log(`기록 없음 (${backupFile || path.join(dataRoot, "funnel")})`);
  process.exit(0);
}

/* 단계별로 '사람 수'를 센다. 이벤트 수가 아니다 — 한 사람이 진단을 두 번 해도 한 명이다.
   로그인 뒤에는 uid, 그 전에는 방문 식별자로 센다. */
const reach = new Map<string, Set<string>>();
for (const step of FUNNEL_STEPS) reach.set(step, new Set());
for (const event of events) {
  const who = event.uid || event.vid;
  if (!who) continue;
  reach.get(event.step)?.add(who);
}

const first = events[0].ts.slice(0, 10);
const last = events[events.length - 1].ts.slice(0, 10);
console.log(`\n자람법 퍼널 — ${first} ~ ${last} · 이벤트 ${events.length}건\n`);

const LABEL: Record<string, string> = {
  landing_view: "첫 화면",
  check_start: "진단 시작",
  check_done: "진단 완주",
  signup_done: "가입",
  first_question: "첫 질문",
  return_visit: "재방문",
};

const top = reach.get("landing_view")!.size || 1;
let previous = 0;
for (const step of FUNNEL_STEPS) {
  const count = reach.get(step)!.size;
  const fromTop = Math.round((count / top) * 100);
  // 직전 단계 대비 유지율이 실제 병목을 가리킨다. 첫 화면 대비 비율만 보면
  // 뒤쪽 단계가 전부 낮아 보여서 어디가 문제인지 분간이 안 된다.
  const fromPrev = previous ? `직전 대비 ${Math.round((count / previous) * 100)}%` : "";
  const bar = "█".repeat(Math.max(0, Math.round(fromTop / 5)));
  console.log(
    `  ${LABEL[step].padEnd(6, " ")} ${String(count).padStart(4)}명  ${String(fromTop).padStart(3)}%  ${bar}  ${fromPrev}`,
  );
  if (step !== "return_visit") previous = count;
}

const mobile = new Set(events.filter((e) => e.device === "mobile").map((e) => e.uid || e.vid)).size;
const all = new Set(events.map((e) => e.uid || e.vid)).size;
console.log(`\n  모바일 ${mobile}/${all}명\n`);

/* 가장 큰 이탈 구간을 한 줄로 짚어 준다 — 매주 볼 때 여기만 봐도 된다.
   재방문은 퍼널의 다음 단계가 아니라 별개 지표라 이탈 계산에서 뺀다. */
let worstStep = "";
let worstDrop = 0;
for (let i = 1; i < FUNNEL_STEPS.length - 1; i += 1) {
  const before = reach.get(FUNNEL_STEPS[i - 1])!.size;
  const after = reach.get(FUNNEL_STEPS[i])!.size;
  if (!before) continue;
  const drop = before - after;
  if (drop > worstDrop) { worstDrop = drop; worstStep = `${LABEL[FUNNEL_STEPS[i - 1]]} → ${LABEL[FUNNEL_STEPS[i]]}`; }
}
if (worstStep) console.log(`  ⚠ 가장 큰 이탈: ${worstStep} (${worstDrop}명)\n`);
