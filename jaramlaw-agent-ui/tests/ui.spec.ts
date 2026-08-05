import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { enterApp, runCheck } from "./helpers";

test("landing sells before it asks: no form, one tap into the check", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("자람법 | 가족 법령·정책 안내");
  await expect(page.getByRole("heading", { level: 1, name: /지원과 기한을 정리해 드립니다/ })).toBeVisible();
  // 랜딩에는 입력 폼이 없다 — 설득 전에 입력 노동을 요구하지 않는 것이 이 화면의 전제다.
  await expect(page.locator(".landing input, .landing select")).toHaveCount(0);

  await page.getByRole("button", { name: /초등학생/ }).click();
  await expect(page).toHaveURL(/#check$/);
  await expect(page.getByRole("heading", { name: "아이가 태어난 달을 알려주세요", level: 1 })).toBeVisible();
});

test("the check asks one thing per screen and can go back", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /지금 일이 생겼어요/ }).click();
  await expect(page.getByRole("heading", { name: "지금 어느 시기인가요?", level: 1 })).toBeVisible();
  // 한 화면 한 질문: 이 단계에 보이는 선택지는 두 개뿐이다.
  // 선택 행은 div+onClick 이 아니라 실제 radio 다 (디자인 시스템이 명시적으로 요구).
  await expect(page.getByRole("radio")).toHaveCount(2);
  await expect(page.getByRole("radiogroup", { name: "지금 어느 시기인가요?" })).toBeVisible();
  // 아무것도 고르지 않은 상태여야 한다 — 기본값이 답을 대신 채우면 안 된다.
  await expect(page.getByRole("radio", { checked: true })).toHaveCount(0);

  await page.getByText("아이가 태어났어요").click();
  await expect(page.getByRole("heading", { name: "아이가 태어난 달을 알려주세요", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "이전" }).click();
  await expect(page.getByRole("heading", { name: "지금 어느 시기인가요?", level: 1 })).toBeVisible();
});

/* 매칭 엔진이 내려가 있어도 가입은 막지 않는다 — CheckResult.tsx 가 주석으로만 적어 둔
   설계 결정이라 지금까지 아무것도 지켜주지 않았다. 이 스위트는 브리지를 끄고 돌아
   (playwright.config.ts) /api/briefing 이 503 을 내므로, 그 장애 경로가 여기서 그대로
   재현된다. 결과 화면이 통째로 죽어 CTA 까지 사라지면 퍼널이 끊기는데, 그때도 위쪽
   진단 단계 테스트는 전부 초록이라 아무도 눈치채지 못한다. */
test("engine outage degrades the result screen but never kills the signup path", async ({ page }) => {
  await runCheck(page);

  await expect(page.getByRole("heading", { name: "결과를 불러오지 못했습니다", level: 1 })).toBeVisible();
  await expect(page.locator(".result-error")).toContainText("잠시 후 다시 시도해 주세요");
  // 장애를 소리 없이 삼키지 않는다 — 오류 패널은 보조기술에도 알려져야 한다.
  await expect(page.locator(".result-error")).toHaveAttribute("role", "status");

  // 여기가 핵심: 결과가 비어도 전환 경로 세 개는 살아 있어야 한다.
  await expect(page.getByRole("button", { name: /가입하고 전부 보기/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "이미 가입하셨나요? 로그인" })).toBeVisible();
  await expect(page.getByRole("button", { name: "진단 다시 하기" }).first()).toBeVisible();

  // 계산에 실패했으면 건수를 지어내면 안 된다 ("0건을 찾았습니다"도 거짓 확언이다).
  await expect(page.locator(".result-list")).toHaveCount(0);
  await expect(page.getByText(/항목 \d+건을 찾았습니다/)).toHaveCount(0);
});

test("the signup CTA on a failed result still leads into the app", async ({ page }) => {
  await runCheck(page);
  await page.getByRole("button", { name: /가입하고 전부 보기/ }).click();
  // 진단에서 넘어온 값이 가입 화면까지 이어진다 — 다시 적게 만들지 않겠다는 약속.
  await expect(page).toHaveURL(/#signup$/);
  await expect(page.getByLabel("이메일")).toBeVisible();
});

test("app screens require a login and expose the parent tabs", async ({ page }) => {
  // 로그인 없이 앱 해시로 들어가면 로그인 화면으로 돌려보낸다.
  await page.goto("/#consult");
  await expect(page).toHaveURL(/#login$/);
  await expect(page.getByRole("heading", { name: "다시 오셨네요" })).toBeVisible();

  await enterApp(page);
  const homeTab = page.getByRole("tab", { name: "홈" });
  await homeTab.focus();
  await homeTab.press("ArrowRight");
  await expect(page).toHaveURL(/#support$/);
  await expect(page.getByRole("tab", { name: "내 지원" })).toHaveAttribute("aria-selected", "true");
});

test("parent journey exposes honest sources and keyboard navigation", async ({ page }) => {
  await enterApp(page);
  await page.getByRole("tab", { name: "물어보기" }).click();
  await expect(page).toHaveURL(/#consult$/);

  await page.getByRole("button", { name: "학원 환불", exact: true }).click();
  await page.getByRole("button", { name: "질문하기" }).click();
  await expect(page.getByText("실시간 연동이 아닌 앱 내 기준 자료로 작성했습니다.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "확인 결과" })).toBeVisible();

  await page.getByRole("tab", { name: "법령" }).click();
  await expect(page.getByText("앱에 포함된 기준 법령 자료", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "공식 법령 확인" }).first()).toHaveAttribute("href", /law\.go\.kr/);
  await expect(page.getByText(/180ms|Gemini|실시간 크롤링/)).toHaveCount(0);
});

test("a parent reads their own consultations without an operator token", async ({ page }) => {
  await enterApp(page);
  await page.getByRole("tab", { name: "물어보기" }).click();
  // 예전에는 이 자리에 "이전 상담 기록은 운영자 인증 후 조회할 수 있습니다"가 떴다.
  await expect(page.getByText(/운영자 인증 후 조회/)).toHaveCount(0);

  await page.getByRole("button", { name: "육아휴직", exact: true }).click();
  await page.getByRole("button", { name: "질문하기" }).click();
  await expect(page.getByRole("heading", { name: "확인 결과" })).toBeVisible();

  // 새로고침해도 본인 기록이 남아 있다 — 서버에 저장되기 때문이다 (예전에는 메모리라 사라졌다).
  await page.reload();
  await expect(page.getByText("상담 목록이 비어 있습니다")).toHaveCount(0, { timeout: 15_000 });
});

test("operator tools are separated and local authentication works", async ({ page }) => {
  await page.goto("/#admin/operations");
  await expect(page.getByRole("heading", { name: "자람법 운영자 콘솔" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "운영자 도구" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "상담 워크플로우" })).toBeVisible();
  await page.getByRole("button", { name: "보안 검증" }).click();
  await expect(page).toHaveURL(/#admin\/security$/);
  await expect(page.getByRole("heading", { name: /AES-256-GCM/ })).toBeVisible();
  await page.getByRole("button", { name: "암호화", exact: true }).click();
  await expect(page.getByLabel("암호화 봉투")).not.toHaveValue("");
  await page.getByRole("button", { name: "무결성 확인·복호화" }).click();
  await expect(page.locator(".decrypted-output").getByText("민감정보가 없는 테스트 문장", { exact: true })).toBeVisible();
});

test("public and parent views have no automated accessibility violations", async ({ page }) => {
  for (const { route, ready } of [
    { route: "/", ready: ".landing" },
    { route: "/#check", ready: ".check-shell" },
    { route: "/#signup", ready: ".auth-shell" },
  ]) {
    await page.goto(route);
    await page.locator(ready).waitFor();
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, `axe violations at ${route}`).toEqual([]);
  }

  await enterApp(page);
  for (const { route, ready } of [
    { route: "/#today", ready: "#panel-today" },
    { route: "/#consult", ready: "#panel-consult" },
    { route: "/#documents", ready: "#panel-documents" },
    { route: "/#laws", ready: "#panel-laws" },
    { route: "/#admin/operations", ready: ".admin-stack" },
  ]) {
    await page.goto(route);
    await page.locator(ready).waitFor();
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, `axe violations at ${route}`).toEqual([]);
  }
});

test("mobile layout has stable navigation and no horizontal overflow", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile project only");
  // 랜딩(비로그인)과 앱(로그인) 양쪽 다 가로 스크롤이 없어야 한다.
  await page.goto("/");
  await expect(page.locator(".stage-picker")).toBeVisible();
  let overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "landing overflows horizontally").toBeLessThanOrEqual(1);

  await enterApp(page);
  await expect(page.getByRole("tablist", { name: "자람법 주요 화면" })).toBeVisible();
  overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "app overflows horizontally").toBeLessThanOrEqual(1);
});
