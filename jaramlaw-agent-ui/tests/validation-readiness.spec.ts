/** 실사용자 검증(Phase 0)을 받을 준비가 됐는지 — 회귀 방지.
 *
 * 부모 30~50명을 받기 전에 반드시 서 있어야 하는 것 셋을 못박는다.
 *
 *   1. 동의 없이는 계정이 만들어지지 않는다   — 없으면 보관 근거 없는 개인정보가 쌓인다
 *   2. 약관·처리방침을 실제로 읽을 수 있다     — 동의 화면이 가리키는 문서가 없으면 동의가 아니다
 *   3. 부모가 말할 통로와 계측이 살아 있다     — 없으면 검증 기간을 지나고도 배운 게 없다
 *
 * 셋 중 하나라도 깨지면 검증 자체가 무효라, 기능 테스트와 분리해 둔다.
 */
import { expect, test } from "@playwright/test";

test("동의 없이는 가입되지 않는다 — 화면과 서버 양쪽에서", async ({ page, request }) => {
  await page.goto("/#signup", { waitUntil: "load" });
  await page.getByLabel("이메일").fill(`consent-${Date.now()}@jaramlaw.test`);
  await page.getByLabel("비밀번호").fill("jaramlaw-e2e-pass");

  // 화면: 동의 전에는 가입 버튼이 잠겨 있다.
  const submit = page.getByRole("button", { name: "가입하기" });
  await expect(submit, "동의 전 가입 버튼은 비활성").toBeDisabled();
  await page.getByRole("checkbox").check();
  await expect(submit, "동의하면 가입 가능").toBeEnabled();

  // 서버: 화면을 우회해 API를 직접 불러도 거절한다. 체크박스는 UI 편의일 뿐 게이트가 아니다.
  const bypass = await request.post("/api/auth/signup", {
    data: { email: `bypass-${Date.now()}@jaramlaw.test`, password: "jaramlaw-e2e-pass" },
  });
  expect(bypass.status(), "동의 없는 가입 요청은 400").toBe(400);
  expect(await bypass.text()).toContain("동의");
});

test("약관과 처리방침을 읽을 수 있고, 적힌 내용이 실제 수집 항목과 맞는다", async ({ page }) => {
  await page.goto("/#privacy", { waitUntil: "load" });
  await expect(page.getByRole("heading", { name: "개인정보 처리방침" })).toBeVisible();

  const privacy = await page.locator(".legal-doc").innerText();
  // 실제로 저장하는 것 (accounts.ts StoredProfile) 이 문서에 적혀 있어야 한다.
  expect(privacy, "저장 항목이 명시돼야 한다").toContain("출생");
  expect(privacy, "외부 전송처를 밝혀야 한다").toContain("법제처");
  expect(privacy, "받지 않는 것도 밝혀야 한다").toContain("주민등록번호");
  // 쓰지 않는 것을 쓴다고 적으면 그 자체가 거짓이 된다.
  expect(privacy, "GA를 쓰지 않는다는 사실이 적혀야 한다").toContain("Google Analytics");

  await page.goto("/#terms", { waitUntil: "load" });
  await expect(page.getByRole("heading", { name: "이용약관" })).toBeVisible();
  const terms = await page.locator(".legal-doc").innerText();
  expect(terms, "법률 자문이 아님을 밝혀야 한다").toContain("법률 자문");
  expect(terms, "위급 연락처가 있어야 한다").toContain("1577-1391");
});

test("첫 화면에서 약관으로 갈 수 있다", async ({ page }) => {
  await page.goto("/", { waitUntil: "load" });
  await page.getByRole("button", { name: "개인정보 처리방침" }).click();
  await expect(page).toHaveURL(/#privacy$/);
});

test("부모가 피드백을 남길 수 있다", async ({ page }) => {
  await page.goto("/", { waitUntil: "load" });
  await page.getByRole("button", { name: "이상한 점 알려주기" }).click();
  await page.getByPlaceholder(/짧게 적어주셔도/).fill("진단 3단계에서 뒤로가기가 안 됩니다");
  await page.getByRole("button", { name: "보내기" }).click();
  await expect(page.getByText("고맙습니다")).toBeVisible();
});

test("퍼널 이벤트가 기록된다 — 잘못된 단계는 조용히 버린다", async ({ request }) => {
  const ok = await request.post("/api/events", {
    data: { step: "landing_view", vid: "e2e-vid", device: "mobile" },
  });
  expect(ok.status(), "정상 단계는 기록").toBe(200);

  // 계측 오류가 부모 화면에 에러로 뜨면 안 되므로, 모르는 단계도 200으로 삼킨다.
  const junk = await request.post("/api/events", { data: { step: "made_up_step" } });
  expect(junk.status(), "모르는 단계도 200 — 계측이 서비스를 막지 않는다").toBe(200);
});

/* 백업은 세 덩이(계정·퍼널·피드백)를 한 번에 내려줘야 한다. 하나라도 조용히 빠지면
   "백업했다"고 믿는 상태에서 그 부분만 사라진다 — 재배포 한 번에 검증 표본이 날아가는
   시나리오가 바로 이 엔드포인트를 만든 이유다.
   접근 제어는 다른 운영자 엔드포인트와 같은 requireOperatorAuth를 쓴다 (ui.spec.ts의
   "operator tools are separated…"가 담당). 이 테스트 서버는 토큰 미설정 로컬 모드라
   여기서 401을 기대할 수 없다 — 프로덕션은 401을 낸다(2026-08-12 실측). */
test("운영자 백업이 계정·퍼널·피드백을 한 번에 내려준다", async ({ request }) => {
  const response = await request.get("/api/ops/export");
  expect(response.status()).toBe(200);
  const json = await response.json();
  expect(Object.keys(json.data ?? {}).sort(), "세 덩이가 모두 있어야 한다")
    .toEqual(["accounts", "feedback", "funnel"]);
  expect(Array.isArray(json.data.funnel)).toBe(true);
  expect(Array.isArray(json.data.feedback)).toBe(true);
  expect(typeof json.exportedAt, "언제 받은 백업인지 알 수 있어야 한다").toBe("string");
});
