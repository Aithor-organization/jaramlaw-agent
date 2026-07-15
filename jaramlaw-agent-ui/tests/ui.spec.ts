import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("parent journey exposes honest sources and keyboard navigation", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("오늘 | 자람법");
  await expect(page.getByRole("heading", { name: "우리 가족에게 필요한 권리와 기한을 한곳에서 확인하세요." })).toBeVisible();

  const todayTab = page.getByRole("tab", { name: "오늘" });
  await todayTab.focus();
  await todayTab.press("ArrowRight");
  await expect(page).toHaveURL(/#consult$/);
  await expect(page.getByRole("tab", { name: "상담" })).toHaveAttribute("aria-selected", "true");

  await page.getByRole("button", { name: "학원 환불", exact: true }).click();
  await page.getByRole("button", { name: "근거와 다음 행동 정리" }).click();
  await expect(page.getByText("실시간 연동이 아닌 앱 내 기준 자료로 작성했습니다.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "확인 결과" })).toBeVisible();

  await page.getByRole("tab", { name: "법령" }).click();
  await expect(page.getByText("앱에 포함된 기준 법령 자료", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "공식 법령 확인" }).first()).toHaveAttribute("href", /law\.go\.kr/);
  await expect(page.getByText(/180ms|Gemini|실시간 크롤링/)).toHaveCount(0);
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

test("primary parent and operator views have no automated accessibility violations", async ({ page }) => {
  const views = [
    { route: "/", ready: "#panel-today" },
    { route: "/#consult", ready: "#panel-consult" },
    { route: "/#documents", ready: "#panel-documents" },
    { route: "/#laws", ready: "#panel-laws" },
    { route: "/#admin/operations", ready: ".admin-stack" },
  ];
  for (const { route, ready } of views) {
    await page.goto(route);
    await page.locator(ready).waitFor();
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, `axe violations at ${route}`).toEqual([]);
  }
});

test("mobile layout has stable navigation and no horizontal overflow", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile project only");
  await page.goto("/");
  await expect(page.getByRole("tablist", { name: "자람법 주요 화면" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
