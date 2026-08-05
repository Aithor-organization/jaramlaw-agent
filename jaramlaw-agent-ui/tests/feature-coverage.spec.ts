/**
 * Feature-coverage probe: does the UI actually surface what the Python backend computes?
 *
 * The existing suites (ui.spec.ts, readme-contract.spec.ts) run with
 * JARAMLAW_DISABLE_PYTHON_BRIDGE=1 — they exercise the UI shell and the deterministic
 * fallback, never the real workflow. So the question "does the UI implement every
 * backend feature" was, until this file, untested.
 *
 * This suite drives the REAL bridge (POST /api/consult with the Python engine on) using
 * the seed scenarios as worked examples, then asserts on what reaches the user. It
 * documents, as executable checks, the gap found on 2026-07-15:
 *
 *   The backend computes rich, structured artifacts — a 641,667 KRW refund calculation,
 *   document drafts, rights cards, support matches, a calendar with iCal — and returns
 *   them in session.workflowReport. But React's WorkflowSummary renders only the COUNTS
 *   of those arrays (App.tsx:490-495). The document body, the refund figure, the card
 *   details, the support amounts are never rendered; they only exist inside the chat
 *   bot text, and the refund number is not even there.
 *
 * Tests are split into two groups:
 *   - "backend contract": what the workflow returns. These pass today and guard the
 *     backend against regressing.
 *   - "UI rendering gap": what the user can see. The render-detail checks are marked
 *     test.fail() — they assert the CURRENT (incomplete) behaviour so the suite stays
 *     green, and each carries a TODO. When the UI starts rendering the detail, the
 *     corresponding test.fail() will itself fail ("expected to fail but passed"),
 *     which is the signal to flip it to a positive assertion.
 *
 * Requires the Python engine reachable, so this file opts OUT of the global
 * DISABLE_PYTHON_BRIDGE server by starting its own server with the bridge ON.
 * Run explicitly:  npx playwright test feature-coverage --project=chromium
 */
import { test, expect, request as pwRequest } from "@playwright/test";
import { CHECK_ANSWERS, enterApp, runCheck } from "./helpers";
import { spawn, execSync, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const UI_ROOT = path.dirname(fileURLToPath(import.meta.url)).replace(/\/tests$/, "");
const PARENT_ROOT = path.dirname(UI_ROOT);
const PORT = 4373; // distinct from the shared 4321 server so the bridge stays ON here
const BASE = `http://127.0.0.1:${PORT}`;

let server: ChildProcess;

test.beforeAll(async () => {
  test.setTimeout(120_000); // building the bundle can take a while on a cold cache

  // Run the PRODUCTION server (node dist/server.cjs), not `npm run dev`. The Vite dev
  // middleware injects an HMR client that opens a WebSocket to a port the server does not
  // proxy; that WS handshake fails and surfaces as a pageerror that makes the page look
  // "broken" to the browser even though React mounted fine. The prod build serves static
  // assets with no such client — and it is what actually ships.
  if (!existsSync(path.join(UI_ROOT, "dist", "server.cjs"))) {
    execSync("npm run build", { cwd: UI_ROOT, stdio: "ignore" });
  }
  server = spawn("node", ["dist/server.cjs"], {
    cwd: UI_ROOT,
    env: {
      ...process.env,
      NODE_ENV: "production",
      PORT: String(PORT),
      JARAMLAW_HOST: "127.0.0.1",
      PYTHON_BIN: process.env.PYTHON_BIN ?? "python3",
      JARAMLAW_PYTHON_SRC: path.join(PARENT_ROOT, "src"),
      JARAMLAW_DISABLE_PYTHON_BRIDGE: "0", // the whole point: bridge ON
      // 공용 서버와 같은 이유로 레이트리밋을 푼다 (playwright.config.ts 주석 참조).
      JARAMLAW_RATE_LIMIT_MAX: "500",
      // 계정 저장소를 저장소 루트가 아닌 임시 경로로 뺀다 (accounts.json 오염 방지).
      JARAMLAW_DATA_DIR: path.join(UI_ROOT, ".playwright-data"),
    },
    stdio: "ignore",
  });

  // Wait for the engine to be reachable (bridge present), up to ~40s.
  const ctx = await pwRequest.newContext();
  for (let i = 0; i < 40; i++) {
    try {
      const res = await ctx.get(`${BASE}/api/health`, { timeout: 2000 });
      if (res.ok()) {
        const body = await res.json();
        if (body?.python_bridge?.enabled && body?.python_bridge?.workflow_present) break;
      }
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  await ctx.dispose();
});

test.afterAll(async () => {
  server?.kill("SIGTERM");
});

/** One real consult against the live Python workflow. LLM in the loop → allow 60s. */
async function consult(body: Record<string, unknown>) {
  const ctx = await pwRequest.newContext();
  const res = await ctx.post(`${BASE}/api/consult`, { data: body, timeout: 60_000 });
  expect(res.ok(), "consult should return 200").toBeTruthy();
  const json = await res.json();
  await ctx.dispose();
  return json.data as Record<string, any>;
}

/** 진단 결과 화면(#result)이 쓰는 미리보기 매칭. consult 와 달리 LLM 은 안 타고
 *  시드 데이터 매칭만 도므로 빠르다. */
async function briefing() {
  const ctx = await pwRequest.newContext();
  const res = await ctx.post(`${BASE}/api/briefing`, {
    data: {
      region: CHECK_ANSWERS.region,
      household: "two-caregivers",
      children: [{ birthMonth: `${CHECK_ANSWERS.birthYear}-${CHECK_ANSWERS.birthMonth}` }],
      expectedDate: "",
    },
    timeout: 60_000,
  });
  const json = await res.json();
  await ctx.dispose();
  return { ok: res.ok(), json };
}

const ACADEMY_REFUND = {
  message: "학원에서 환불을 안 해줘요. 어떻게 받을 수 있나요?",
  profile: {
    region: "41590",
    parents: [{ role: "father", age: 38, region_code: "41590" }],
    children: [{ birth_date: "2019-08-10", sex: "F" }],
    case_data: { monthly_fee_krw: 350000, months_paid: 3, total_paid_krw: 1050000, days_used: 35, total_days: 90 },
  },
};

test.describe("backend contract (via the UI's own bridge)", () => {
  test("the consult route really invokes the Python engine, not the fallback", async () => {
    const session = await consult(ACADEMY_REFUND);
    expect(session.integration?.backend, "must be the real engine, not deterministic fallback").toBe("python-engine");
    expect(session.integration?.connected).toBe(true);
    expect(session.auditLogId, "a real run leaves an audit id").toBeTruthy();
    expect(session.workflowReport, "the full report should ride along").toBeTruthy();
  });

  test("academy refund is computed exactly (55/90 of 1,050,000 = 641,667 KRW)", async () => {
    const session = await consult(ACADEMY_REFUND);
    const draft = session.workflowReport?.draft_documents?.[0];
    expect(draft, "a refund-request draft should exist").toBeTruthy();
    expect(draft.calculation_breakdown?.refund_krw, "exact refund figure").toBe(641667);
    expect(draft.body_markdown, "the figure is written into the draft body").toContain("641,667원");
  });

  test("the safety scenario halts law/document work and surfaces a report line", async () => {
    const session = await consult({
      message: "어린이집에서 아이 몸에 멍이 크게 있었는데 CCTV 열람을 거부해요. 학대가 의심됩니다.",
      profile: { children: [{ birth_date: "2022-03-15", sex: "M" }] },
    });
    const safety = session.workflowReport?.safety_routing;
    expect(safety?.triggered, "abuse keywords must trip safety routing").toBe(true);
    expect(safety?.category).toBe("child_abuse_suspected");
    // safety routing IS surfaced to the user (this is the good case) — the hotline
    // appears in the bot text, unlike the refund figure below.
    const botText = (session.messages ?? []).filter((m: any) => m.sender !== "user").map((m: any) => m.text).join("\n");
    expect(botText).toContain("1577-1391");
  });
});

test.describe("UI rendering — the gap closed on 2026-07-15", () => {
  // These were test.fail() TODOs when the audit found the gap. The UI now renders the
  // backend's structured artifacts (WorkflowSummary + AcademyRefundFields), so they are
  // positive assertions: the refund figure the backend computes is visible on screen,
  // and if a regression drops it these fail loudly.

  /** Type a refund query, fill the structured facts (which appear only for a refund
   * query, mirroring the server's scenario inference), and submit. */
  async function submitRefund(page: import("@playwright/test").Page) {
    // 부모 화면 전체가 로그인 뒤로 옮겨갔다 — 가입해서 들어간 뒤 탭을 만진다.
    await enterApp(page, BASE);
    await page.getByRole("tab", { name: "물어보기" }).click();
    // The "학원 환불" demo button seeds a refund query, so inferScenario() returns
    // academy_refund and mounts the structured fields.
    await page.getByRole("button", { name: "학원 환불", exact: true }).click();
    await page.getByLabel("총 결제액 (원)").fill("1050000");
    await page.getByLabel("총 수강일수 (일)").fill("90");
    await page.getByLabel("이용한 일수 (일)").fill("35");
    await page.getByRole("button", { name: "질문하기" }).click();
  }

  test("the computed refund figure is rendered in the workflow panel", async ({ page }) => {
    test.setTimeout(90_000); // real LLM round-trip in the loop
    await submitRefund(page);
    // The exact figure the backend computes (55/90 × 1,050,000) must be on screen. It
    // appears in both the calculation card and the draft body, so match the first.
    await expect(page.getByText("641,667원").first()).toBeVisible({ timeout: 70_000 });
  });

  test("the document draft body is rendered, not just its count", async ({ page }) => {
    test.setTimeout(90_000);
    await submitRefund(page);
    // The draft is a <details> whose summary is the document title; expand it and the
    // body_markdown becomes visible — content, not a bare "문서 초안: 1" count.
    const draft = page.locator("details.draft-card").first();
    await expect(draft).toBeVisible({ timeout: 70_000 });
    await draft.locator("summary").click();
    await expect(draft.locator(".draft-body")).toBeVisible();
  });
});

/* 진단 결과 화면 — 랜딩이 끌고 오는 퍼널의 결론인데도 e2e 가 한 번도 밟지 않던 구간이다
   (2026-08-04 확인: 어느 스위트에서도 briefing 이 grep 0건). 공용 서버는 브리지를 끄고
   돌아 /api/briefing 이 503 을 내므로, ui.spec.ts 는 장애 경로밖에 볼 수 없다. 성공
   경로는 브리지가 켜진 이 파일에서만 검증할 수 있다. */
test.describe("check result — the funnel's payoff screen", () => {
  test("the briefing route matches real supports against the seed data", async () => {
    const { ok, json } = await briefing();
    expect(ok, `/api/briefing should return 200, got ${json?.message ?? "?"}`).toBeTruthy();
    expect(json.status).toBe("success");
    expect(json.preview, "the pre-signup call is a preview").toBe(true);
    expect(Array.isArray(json.data?.supports)).toBe(true);
    // 만 8세 미만 아이라 최소 하나는 걸려야 한다. 0건이면 아래 렌더 테스트가
    // "아무것도 안 보임"을 통과로 읽어버리므로 여기서 먼저 막는다.
    expect(json.data.supports.length, "seed matching should find at least one support").toBeGreaterThan(0);
    expect(typeof json.locked_count, "locked count drives the signup CTA").toBe("number");
  });

  test("what the engine matched is what the parent actually sees", async ({ page }) => {
    test.setTimeout(90_000);
    // 먼저 백엔드에 직접 물어 "무엇이 나와야 하는가"를 확정한 뒤 화면과 대조한다.
    // 고정 문자열을 박으면 시드가 바뀔 때 테스트가 제품보다 먼저 썩는다.
    const { json } = await briefing();
    const expected = json.data.supports[0];

    await runCheck(page, BASE);

    await expect(page.getByRole("heading", { level: 1, name: /항목 \d+건을 찾았습니다/ })).toBeVisible({ timeout: 30_000 });
    const first = page.locator(".result-item").first();
    await expect(first).toContainText(expected.name);
    // 금액은 숫자만 떼면 월 상한이 일시금으로 읽힌다 — 단위·조건이 붙은 문구가 떠야 한다
    // (CheckResult.tsx 가 amount_description 을 앞세우는 이유).
    if (expected.amount_description) {
      await expect(first.locator(".result-amount")).toHaveText(expected.amount_description);
    }

    // 잠긴 건수는 가입 CTA 의 근거다 — 숫자가 틀리면 "가입하면 더 보인다"가 거짓말이 된다.
    if (json.locked_count > 0) {
      await expect(page.locator(".result-locked")).toContainText(`나머지 ${json.locked_count}건`);
    }
  });
});
