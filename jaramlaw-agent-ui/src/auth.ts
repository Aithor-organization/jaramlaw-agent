/** 부모 계정 클라이언트. 세션은 httpOnly 쿠키라 토큰이 JS로 내려오지 않는다 —
 * 저장할 것이 없으므로 이 모듈은 상태를 갖지 않고 매번 서버에 묻는다. */
import { coerceProfile, type FamilyProfile } from "./profile";
import { readApiError } from "./api";

export interface AccountUser {
  id: string;
  email: string;
  nickname: string;
  profile: FamilyProfile | null;
}

function toAccount(raw: unknown): AccountUser | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  if (typeof value.id !== "string") return null;
  return {
    id: value.id,
    email: typeof value.email === "string" ? value.email : "",
    nickname: typeof value.nickname === "string" ? value.nickname : "",
    profile: value.profile ? coerceProfile(value.profile) : null,
  };
}

export async function fetchMe(): Promise<AccountUser | null> {
  try {
    const response = await fetch("/api/auth/me");
    if (!response.ok) return null;
    const payload = await response.json();
    return toAccount(payload.data);
  } catch {
    return null;
  }
}

async function post(url: string, body: unknown): Promise<AccountUser> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await readApiError(response, "요청을 처리하지 못했습니다."));
  const payload = await response.json();
  const account = toAccount(payload.data);
  if (!account) throw new Error("계정 정보를 읽지 못했습니다.");
  return account;
}

export function signup(
  email: string,
  password: string,
  nickname: string,
  profile: FamilyProfile | null,
): Promise<AccountUser> {
  return post("/api/auth/signup", { email, password, nickname, profile });
}

export function login(email: string, password: string): Promise<AccountUser> {
  return post("/api/auth/login", { email, password });
}

export async function logout(): Promise<void> {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch {
    /* 네트워크 실패해도 화면은 로그아웃 상태로 넘어간다 — 쿠키는 서버가 만료시킨다 */
  }
}

export async function saveProfileToServer(profile: FamilyProfile): Promise<AccountUser | null> {
  try {
    const response = await fetch("/api/me/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
    if (!response.ok) return null;
    const payload = await response.json();
    return toAccount(payload.data);
  } catch {
    return null;
  }
}
