import { Ref } from "react";

export const THIS_YEAR = new Date().getFullYear();

/** `YYYY-MM` 완전한 형태인가. 연·월을 따로 고르게 하면서 `2019-` 같은 부분 상태가
 *  생기므로, truthy 검사만으로는 "입력 완료"를 판정할 수 없다. */
export const isYearMonth = (value: string) => /^\d{4}-\d{2}$/.test(value);

/** 연·월 입력 — 네이티브 `<input type="month">` 대신 셀렉트 두 개.
 *
 * 디자인 시스템 §4.2 가 규정한 형태다("YYYY년 MM월 분리형 셀렉트 2개를 기본으로 하고,
 * 네이티브 date 입력은 폴백으로만"). 네이티브 위젯을 쓰면 세 가지가 깨진다:
 *   ① 빈 상태가 `----년 ---` 으로 뜬다 — 무엇을 넣으라는 건지 화면이 말해주지 않는다
 *   ② 생김새·달력 팝업이 OS/브라우저마다 다르다 (같은 화면이 사람마다 다르게 보인다)
 *   ③ 내부 pseudo-element 라 디자인 시스템의 높이·radius·focus ring 이 안 먹는다
 *
 * 값 형식은 그대로 `YYYY-MM` 이라 서버 계약(profile.children[].birthMonth)은 바뀌지 않는다.
 */
export function YearMonthPicker({
  value,
  onChange,
  label,
  yearFrom,
  yearTo,
  invalid,
  firstRef,
}: {
  value: string;
  onChange: (next: string) => void;
  label: string;
  yearFrom: number;
  yearTo: number;
  invalid?: boolean;
  firstRef?: Ref<HTMLSelectElement>;
}) {
  const [year = "", month = ""] = value ? value.split("-") : [];
  // 최신 연도가 위로 오게 — 아이 생년월은 최근일수록 고를 확률이 높다
  const years: number[] = [];
  for (let y = yearTo; y >= yearFrom; y--) years.push(y);

  /* 연도만 고른 중간 상태를 "" 로 날려버리면 방금 고른 것이 화면에서 사라진다.
     부분 입력도 그대로 들고 있다가(`YYYY-`), 완전한 값인지는 isYearMonth 가 판정한다. */
  const emit = (nextYear: string, nextMonth: string) =>
    onChange(nextYear || nextMonth ? `${nextYear}-${nextMonth}` : "");

  return (
    <div className={`ym-picker${invalid ? " is-invalid" : ""}`}>
      <div className="ym-field">
        <select
          ref={firstRef}
          aria-label={`${label} 연도`}
          aria-invalid={invalid ? "true" : undefined}
          value={year}
          onChange={(event) => emit(event.target.value, month)}
        >
          <option value="">연도</option>
          {years.map((y) => <option key={y} value={String(y)}>{y}년</option>)}
        </select>
      </div>
      <div className="ym-field ym-field-month">
        <select
          aria-label={`${label} 월`}
          aria-invalid={invalid ? "true" : undefined}
          value={month}
          onChange={(event) => emit(year, event.target.value)}
        >
          <option value="">월</option>
          {Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, "0")).map((m) => (
            <option key={m} value={m}>{Number(m)}월</option>
          ))}
        </select>
      </div>
    </div>
  );
}

