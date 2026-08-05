/** 금액 표기 — 본 앱과 진단 결과가 같은 형식을 쓰도록 한곳에 둔다. */
const KRW = new Intl.NumberFormat("ko-KR");

export function formatKrw(value: unknown): string | null {
  return typeof value === "number" && Number.isFinite(value) ? `${KRW.format(value)}원` : null;
}

/** 좁은 행에 넣을 금액 한 토막.
 *
 * 숫자만 떼면 "2,500,000원"이 일시금으로 읽힌다 — 실제로는 월 상한이다. 단위와
 * 조건이 붙어 있는 amount_description에서 첫 구절만 잘라 쓰고, 그것도 없을 때만
 * 숫자로 떨어진다. ("월 10만원 (만 8세 미만…)" → "월 10만원") */
export function shortAmount(support: { amount_krw?: number; amount_description?: string }): string | null {
  const head = (support.amount_description || "").split("(")[0].split(",")[0].trim();
  if (head) return head;
  return formatKrw(support.amount_krw);
}
