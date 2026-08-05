import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { enterApp } from "./helpers";

test("skip link moves keyboard focus to the main content", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.locator(".skip-link")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
});

test("README parent profile and fallback consultation contract", async ({ page }) => {
  await enterApp(page);
  // 연·월은 네이티브 month 입력이 아니라 분리형 셀렉트다 (디자인 시스템 §4.2)
  await page.getByLabel("1째 아이 출생 연도").selectOption("2024");
  await page.getByLabel("1째 아이 출생 월").selectOption("01");
  await page.getByLabel("거주 지역").selectOption({ label: "서울" });
  // 프로필이 채워지면 폼을 접을 수 있게 되는 것이 "매칭 가능" 신호다
  // (예전의 "상담 준비됨" 배지를 대신한다).
  await expect(page.getByRole("button", { name: "접기" })).toBeVisible();
  // 이전 단언은 "지원 조건 확인" 문자열을 찾았는데, 그 문자열은 제품 어디에도 없다
  // (이 파일에만 남아 있던 죽은 단언). 실제 계약으로 바꾼다: 프로필이 채워지면
  // 지원 패널이 "정보를 입력하세요" 안내를 더 이상 띄우지 않는다.
  await expect(page.getByText(/가족 상황·지역·자녀 정보를 입력하면/)).toHaveCount(0);

  // 저장하지 않은 입력은 새로고침하면 사라진다 — 저장은 명시적인 행동이다.
  await page.reload();
  await expect(page.getByRole("tab", { name: "홈" })).toBeVisible();
  await expect(page.getByLabel("1째 아이 출생 연도")).toHaveValue("");
  await expect(page.getByLabel("1째 아이 출생 월")).toHaveValue("");
  await expect(page.getByLabel("거주 지역")).toHaveValue("");

  await page.getByRole("tab", { name: "물어보기" }).click();
  await page.getByRole("button", { name: "학원 환불", exact: true }).click();
  await page.getByRole("button", { name: "질문하기" }).click();
  await expect(page.getByText("실시간 연동이 아닌 앱 내 기준 자료로 작성했습니다.")).toBeVisible();

  const results = page.locator(".consult-results");
  await expect(results).toContainText(/기본 확인|추가 확인|우선 검토/);
  await expect(results).toContainText("통계적 승소·분쟁 확률이 아니라");
  await expect(results).not.toContainText(/\d+\s*%/);
});

test("README document and law source contract", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium", "desktop contract test");
  await enterApp(page);
  await page.goto("/#documents");
  const fileInput = page.getByLabel("텍스트 문서 선택");

  await fileInput.setInputFiles({
    name: "sample.docx",
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: Buffer.from("not a real Word document"),
  });
  await expect(page.getByText(/현재는 \.txt와 \.md 파일만 지원/)).toBeVisible();

  await fileInput.setInputFiles({
    name: "large.txt",
    mimeType: "text/plain",
    buffer: Buffer.alloc(1024 * 1024 + 1, 65),
  });
  await expect(page.getByText(/파일이 1MB를 초과/)).toBeVisible();

  await fileInput.setInputFiles({
    name: "refund.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("학원 수강료 환불 요청. 계약일 2026-07-01, 해지 요청일 2026-07-15, 결제 금액 300000원."),
  });
  await page.getByRole("button", { name: "쟁점 정리 시작" }).click();
  await expect(page.getByText(/문서 검토가 완료/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "한눈에 보기" })).toBeVisible();

  await page.getByRole("tab", { name: "법령" }).click();
  await expect(page.getByText("앱에 포함된 기준 법령 자료", { exact: true })).toBeVisible();
  await page.getByRole("searchbox", { name: "법령명·조문·상황 검색" }).fill("육아휴직");
  await expect(page.locator('[aria-label="검색된 법령"] button')).not.toHaveCount(0);
  await expect(page.getByRole("link", { name: "공식 법령 확인" })).toHaveAttribute("href", "https://www.law.go.kr");
});

test("README API trust-boundary contract", async ({ request }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium", "single API contract run");
  const healthResponse = await request.get("/api/health");
  expect(healthResponse.ok()).toBeTruthy();
  const healthText = JSON.stringify(await healthResponse.json());
  expect(healthText).not.toMatch(/parent_root|python_bin|workflow_path|audit_log_dir|trace_path/);

  const lawsResponse = await request.get("/api/laws");
  const laws = await lawsResponse.json();
  expect(laws.source).toBe("seed");
  expect(laws.data.length).toBeGreaterThan(0);

  const tooLarge = await request.post("/api/summarize", {
    data: { title: "large", content: "가".repeat(400_000) },
  });
  expect(tooLarge.status()).toBe(413);

  const encryptedResponse = await request.post("/api/encrypt-demo", {
    data: { mode: "encrypt", text: "integrity-test" },
  });
  expect(encryptedResponse.ok()).toBeTruthy();
  const encrypted = await encryptedResponse.json();
  const envelope = JSON.parse(Buffer.from(encrypted.cipherText, "base64url").toString("utf8"));
  envelope.data = `${envelope.data.startsWith("A") ? "B" : "A"}${envelope.data.slice(1)}`;
  const tampered = Buffer.from(JSON.stringify(envelope)).toString("base64url");
  const rejected = await request.post("/api/encrypt-demo", {
    data: { mode: "decrypt", cipher: tampered },
  });
  expect(rejected.status()).toBe(400);
});

test("README primary views remain axe-clean after loading", async ({ page }) => {
  await enterApp(page);
  for (const route of ["/#today", "/#consult", "/#documents", "/#laws", "/#admin/operations", "/#admin/security"]) {
    await page.goto(route);
    if (route.includes("documents")) await page.locator("#panel-documents").waitFor();
    else if (route.includes("laws")) await page.locator("#panel-laws").waitFor();
    else if (route.includes("admin")) await page.locator(".admin-stack").waitFor();
    else await page.locator("[role=tabpanel]").waitFor();
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, `axe violations at ${route}`).toEqual([]);
  }
});
