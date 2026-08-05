/** 가족 프로필 — 랜딩·진단·가입·본 앱이 공유하는 단일 정의.
 *
 * 원래 App.tsx 안에만 있었다. 진단(비로그인)에서 만든 프로필을 가입 시점에 계정으로
 * 넘겨야 해서 화면 밖으로 꺼냈다. 진단에서 입력한 걸 가입 후 또 입력하게 만들면
 * 그 지점에서 부모가 이탈한다.
 */

export interface FamilyProfile {
  household: "two-caregivers" | "single-caregiver" | "expecting";
  region: string;
  children: { birthMonth: string }[]; // 자녀별 출생 연월
  expectedDate: string; // 출산 예정일 (household=expecting)
  /** 진단에서 고른 "요즘 걸리는 일" — 상담 화면 프리필에 쓴다. 매칭에는 쓰지 않는다. */
  concern?: string;
}

export const DEFAULT_PROFILE: FamilyProfile = {
  household: "two-caregivers",
  region: "",
  children: [{ birthMonth: "" }],
  expectedDate: "",
  concern: "",
};

export const REGIONS = [
  "서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
  "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
];

/** familyStage 표시는 가장 어린(최근 출생) 자녀 기준. */
export function primaryBirthMonth(profile: FamilyProfile): string {
  const months = profile.children.map((c) => c.birthMonth).filter(Boolean).sort();
  return months.length ? months[months.length - 1] : "";
}

/** 프로필이 매칭을 돌릴 만큼 채워졌는가 (지역 + 자녀 최소 1명 또는 출산예정+예정일).
 *
 *  연·월을 분리 셀렉트로 받으면서 `2019-` 같은 부분 입력이 생긴다. truthy 검사만
 *  하면 그런 값도 "입력됨"으로 통과해 서버가 조용히 무시하는 요청을 보내게 된다. */
export function hasProfileInput(profile: FamilyProfile): boolean {
  const complete = (value: string) => /^\d{4}-\d{2}/.test(value);
  const anyChild = profile.children.some((c) => complete(c.birthMonth));
  return Boolean(profile.region)
    && (anyChild || (profile.household === "expecting" && complete(profile.expectedDate)));
}

export function stageFromBirthMonth(birthMonth: string): string {
  if (!birthMonth) return "프로필 미등록";
  const birth = new Date(`${birthMonth}-01T00:00:00`);
  const now = new Date();
  const months = (now.getFullYear() - birth.getFullYear()) * 12 + now.getMonth() - birth.getMonth();
  if (months < 0) return "출산 준비";
  if (months < 12) return "영아기";
  if (months < 36) return "걸음마기";
  if (months < 84) return "유아기";
  return "학령기";
}

export function familyStageOf(profile: FamilyProfile): string {
  const pm = primaryBirthMonth(profile);
  if (pm) return stageFromBirthMonth(pm);
  if (profile.household === "expecting" && profile.expectedDate) return "출산 준비";
  return "프로필 미등록";
}

/* ── 로컬 보관 ──────────────────────────────────────────────────────────────
 * 로그인 전(진단 도중)의 임시 보관소다. 로그인하면 서버 프로필이 정본이 되고
 * 이 값은 초기값 역할만 한다.
 */
export const PROFILE_STORAGE_KEY = "jaramlaw:family-profile";

export function loadStoredProfile(): FamilyProfile {
  try {
    const raw = typeof localStorage !== "undefined" ? localStorage.getItem(PROFILE_STORAGE_KEY) : null;
    if (!raw) return DEFAULT_PROFILE;
    return coerceProfile(JSON.parse(raw));
  } catch {
    return DEFAULT_PROFILE;
  }
}

export function storeProfile(profile: FamilyProfile): void {
  try {
    if (typeof localStorage !== "undefined") localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
  } catch {
    /* localStorage 접근 불가(사생활 모드 등) — 저장 실패해도 앱은 계속 동작 */
  }
}

/** 저장 스키마가 바뀌었을 수 있으니 필드별로 방어적으로 복원한다. */
export function coerceProfile(value: unknown): FamilyProfile {
  const parsed = (value || {}) as Partial<FamilyProfile>;
  return {
    household:
      parsed.household === "single-caregiver" || parsed.household === "expecting"
        ? parsed.household
        : "two-caregivers",
    region: typeof parsed.region === "string" ? parsed.region : "",
    children: Array.isArray(parsed.children) && parsed.children.length
      ? parsed.children.map((c) => ({ birthMonth: typeof c?.birthMonth === "string" ? c.birthMonth : "" }))
      : [{ birthMonth: "" }],
    expectedDate: typeof parsed.expectedDate === "string" ? parsed.expectedDate : "",
    concern: typeof parsed.concern === "string" ? parsed.concern : "",
  };
}
