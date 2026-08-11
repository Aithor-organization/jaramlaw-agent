import { expect, type Page } from "@playwright/test";

let seq = 0;

/** 가입해서 앱 안으로 들어간다.
 *
 * 랜딩·진단·가입이 생기면서 부모 화면 전체가 로그인 뒤로 옮겨갔다. 테스트도 같은
 * 문을 통과해야 한다 — 이메일은 매번 새로 만들어 서버의 accounts.json과 충돌하지
 * 않게 한다. */
export async function enterApp(page: Page, baseUrl = ""): Promise<void> {
  const email = `e2e-${Date.now()}-${seq++}@jaramlaw.test`;
  await page.goto(`${baseUrl}/#signup`, { waitUntil: "load" });
  await page.getByLabel("이메일").fill(email);
  await page.getByLabel("비밀번호").fill("jaramlaw-e2e-pass");
  // 개인정보 수집·이용 동의는 필수다 (2026-08-12). 체크하지 않으면 버튼이 잠기고,
  // 우회해서 API를 직접 불러도 서버가 거절한다 — 테스트도 부모와 같은 문을 지난다.
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "가입하기" }).click();
  await expect(page.getByRole("tab", { name: "홈" })).toBeVisible({ timeout: 20_000 });
}

/** 진단이 프로필로 받는 값. runCheck 가 이 값으로 마법사를 채우고, 호출부는 같은 값을
 *  /api/briefing 에 직접 보내 화면과 백엔드를 대조할 수 있다. */
export const CHECK_ANSWERS = {
  region: "서울",
  /** 만 8세 미만이라 아동수당류가 항상 걸리는 나이대 — 매칭 0건이면 테스트 의미가 없다.
   *  절대 연도를 박으면 해가 바뀔 때 셀렉트 범위(올해-18 ~ 올해) 밖으로 나가 썩는다. */
  birthYear: String(new Date().getFullYear() - 3),
  birthMonth: "07",
} as const;

/** 랜딩에서 5단계 진단을 통과해 결과 화면(#result)까지 간다.
 *
 * 결과 화면은 랜딩이 끌고 오는 퍼널의 결론인데도 e2e 가 한 번도 밟지 않던 구간이다
 * (2026-08-04 확인). 공용 서버는 브리지를 끈 채로 돌아 /api/briefing 이 503 을 내므로,
 * 이 헬퍼는 성공/실패 어느 쪽이든 **결과 화면에 도달했다는 사실만** 보장하고 내용
 * 판정은 호출부에 맡긴다. */
export async function runCheck(page: Page, baseUrl = ""): Promise<void> {
  await page.goto(`${baseUrl}/`, { waitUntil: "load" });
  // 히어로가 캐러셀이라 슬라이드마다 같은 CTA 가 하나씩 있다 — 보이는 첫 장을 누른다.
  await page.getByRole("button", { name: /3분 진단 시작하기/ }).first().click();

  await page.getByText("아이가 태어났어요").click();
  await page.getByLabel("1째 아이 출생 연도").selectOption(CHECK_ANSWERS.birthYear);
  await page.getByLabel("1째 아이 출생 월").selectOption(CHECK_ANSWERS.birthMonth);
  await page.getByRole("button", { name: "다음" }).click();

  await page.getByText("둘이서 함께 키워요").click();
  /* 지역은 고르는 즉시 다음 단계로 넘어간다 (Check.tsx 의 onChange 가 advance 를 부른다).
     그래서 `.check()` 는 못 쓴다 — 클릭 자체는 되지만 라디오가 곧바로 언마운트돼
     "checked 가 됐는지" 사후 확인이 영영 끝나지 않는다. 라벨의 <span> 을 눌러도 안 된다:
     시각적으로 숨긴 <input> 이 그 위를 덮고 있어 포인터 이벤트를 가로챈다.
     남는 방법은 input 을 직접 누르는 것 — 사후 검증이 없는 click 이라 언마운트와 경합하지 않는다. */
  await page.getByRole("radio", { name: CHECK_ANSWERS.region, exact: true }).click();

  await page.getByText("아직 특별한 일은 없어요").click();
  await expect(page).toHaveURL(/#result$/);
}
