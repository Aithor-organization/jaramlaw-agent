/** 부모 계정 · 프로필 · 상담 이력 영속 저장소.
 *
 * 지금까지 자람법에는 "회원"이 없었다. 프로필은 브라우저 localStorage에만 있었고
 * (폰을 바꾸면 사라진다) 상담 이력은 프로세스 메모리에 있어서 재배포하면 날아갔다.
 * 게다가 부모가 자기 상담 기록을 보려면 운영자 토큰이 필요했다 — 남의 열쇠로
 * 내 서랍을 여는 구조였다. 이 모듈이 그 셋을 한 번에 푼다.
 *
 * 저장 매체는 JARAMLAW_DATA_DIR 아래 JSON 파일 하나다. DB를 쓰지 않는 이유:
 * Railway는 서비스당 볼륨 1개라 이미 그 경로가 영속 지점으로 잡혀 있고(server.ts
 * DATA_ROOT 주석), better-sqlite3 같은 네이티브 모듈은 Docker 빌드에 컴파일 단계를
 * 하나 더 얹는다. 부모 수천 명 규모까지는 파일 하나로 충분하고, 넘어가면 이 모듈의
 * 함수 시그니처를 유지한 채 내부만 DB로 갈아끼우면 된다.
 *
 * 비밀번호는 node:crypto scrypt로 해싱한다 (bcrypt 의존성 없이 동일 계열 방어).
 */
import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export interface StoredProfile {
  household: string;
  region: string;
  children: { birthMonth: string }[];
  expectedDate: string;
  /** 진단에서 고른 지금 겪는 일 — 상담 첫 화면 프리필에 쓴다. */
  concern?: string;
}

interface StoredUser {
  id: string;
  email: string;
  nickname: string;
  salt: string;
  passwordHash: string;
  createdAt: string;
  profile: StoredProfile | null;
  /** 개인정보 수집·이용 동의 시각. 동의 없이 만들어진 계정은 존재할 수 없다.
   *  버전을 함께 남기는 이유: 약관이 바뀌면 "무엇에 동의했는지"가 달라지므로,
   *  시각만으로는 나중에 소명이 안 된다. */
  consentedAt?: string;
  consentVersion?: string;
}

/** 약관·처리방침 개정 시 올린다. 클라이언트(src/legal.ts)와 값이 같아야 한다. */
export const CONSENT_VERSION = "2026-08-12";

interface StoredSession {
  token: string;
  userId: string;
  createdAt: number;
}

interface StoreShape {
  version: 1;
  users: StoredUser[];
  sessions: StoredSession[];
  /** userId → 상담 기록. 사용자당 상한을 둬 파일이 무한정 자라지 않게 한다. */
  consultations: Record<string, unknown[]>;
}

const SESSION_TTL_MS = 1000 * 60 * 60 * 24 * 30; // 30일
const MAX_CONSULTATIONS_PER_USER = 50;
const SCRYPT_KEYLEN = 64;

const EMPTY: StoreShape = { version: 1, users: [], sessions: [], consultations: {} };

let storePath = "";
let cache: StoreShape | null = null;

export function initAccountStore(dataRoot: string): void {
  storePath = path.join(dataRoot, "accounts.json");
  cache = null;
  read();
}

function read(): StoreShape {
  if (cache) return cache;
  try {
    const raw = fs.readFileSync(storePath, "utf8");
    const parsed = JSON.parse(raw) as Partial<StoreShape>;
    cache = {
      version: 1,
      users: Array.isArray(parsed.users) ? (parsed.users as StoredUser[]) : [],
      sessions: Array.isArray(parsed.sessions) ? (parsed.sessions as StoredSession[]) : [],
      consultations: parsed.consultations && typeof parsed.consultations === "object"
        ? (parsed.consultations as Record<string, unknown[]>)
        : {},
    };
  } catch {
    // 파일이 없거나(첫 부팅) 깨졌을 때 빈 저장소로 시작한다. 깨진 파일을 지우지는
    // 않는다 — 사람이 원인을 볼 수 있어야 한다.
    cache = { ...EMPTY, users: [], sessions: [], consultations: {} };
  }
  return cache;
}

/** 임시 파일에 쓰고 rename — 쓰는 도중 프로세스가 죽어도 반쪽 파일이 남지 않는다. */
function write(next: StoreShape): void {
  cache = next;
  if (!storePath) return;
  const tmp = `${storePath}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(next), "utf8");
  fs.renameSync(tmp, storePath);
}

function hashPassword(password: string, salt: string): string {
  return scryptSync(password, salt, SCRYPT_KEYLEN).toString("hex");
}

function verifyPassword(password: string, user: StoredUser): boolean {
  const candidate = Buffer.from(hashPassword(password, user.salt), "hex");
  const stored = Buffer.from(user.passwordHash, "hex");
  // 길이가 다르면 timingSafeEqual이 던진다 — 먼저 걸러낸다.
  if (candidate.length !== stored.length) return false;
  return timingSafeEqual(candidate, stored);
}

export function normalizeEmail(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

export interface PublicUser {
  id: string;
  email: string;
  nickname: string;
  profile: StoredProfile | null;
}

function toPublic(user: StoredUser): PublicUser {
  return { id: user.id, email: user.email, nickname: user.nickname, profile: user.profile };
}

/* 판별자를 boolean이 아니라 문자열로 둔다: 이 저장소는 strictNullChecks가 꺼져 있고,
 * 그 모드에서 TS는 true/false 리터럴 판별자로 union을 좁히지 못한다. */
export type SignupResult =
  | { kind: "ok"; user: PublicUser; token: string }
  | { kind: "error"; message: string };

export function createUser(
  email: string,
  password: string,
  nickname: string,
  profile: StoredProfile | null,
  consented: boolean = false,
): SignupResult {
  const normalized = normalizeEmail(email);
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)) {
    return { kind: "error", message: "이메일 형식을 확인해 주세요." };
  }
  if (typeof password !== "string" || password.length < 8) {
    return { kind: "error", message: "비밀번호는 8자 이상으로 정해 주세요." };
  }
  // 동의는 서버에서 막는다. 화면의 체크박스만으로는 API 직접 호출을 거를 수 없고,
  // 동의 기록이 없는 계정이 하나라도 생기면 그 계정의 데이터는 근거 없이 보관된 것이 된다.
  if (!consented) {
    return { kind: "error", message: "개인정보 수집·이용에 동의해 주세요." };
  }
  const store = read();
  if (store.users.some((user) => user.email === normalized)) {
    return { kind: "error", message: "이미 가입된 이메일입니다. 로그인해 주세요." };
  }
  const salt = randomBytes(16).toString("hex");
  const user: StoredUser = {
    id: `user_${randomBytes(9).toString("hex")}`,
    email: normalized,
    nickname: (nickname || "").trim().slice(0, 20) || normalized.split("@")[0],
    salt,
    passwordHash: hashPassword(password, salt),
    createdAt: new Date().toISOString(),
    profile,
    consentedAt: new Date().toISOString(),
    consentVersion: CONSENT_VERSION,
  };
  const token = randomBytes(32).toString("hex");
  write({
    ...store,
    users: [...store.users, user],
    sessions: [...pruneSessions(store.sessions), { token, userId: user.id, createdAt: Date.now() }],
  });
  return { kind: "ok", user: toPublic(user), token };
}

export type LoginResult =
  | { kind: "ok"; user: PublicUser; token: string }
  | { kind: "error"; message: string };

export function login(email: string, password: string): LoginResult {
  const store = read();
  const user = store.users.find((item) => item.email === normalizeEmail(email));
  // 존재하지 않는 이메일과 틀린 비밀번호를 같은 문구로 돌려준다 — 가입 여부가
  // 응답으로 새어 나가면 계정 열거(enumeration)가 된다.
  const failure = { kind: "error" as const, message: "이메일 또는 비밀번호가 맞지 않습니다." };
  if (!user) return failure;
  if (!verifyPassword(typeof password === "string" ? password : "", user)) return failure;
  const token = randomBytes(32).toString("hex");
  write({
    ...store,
    sessions: [...pruneSessions(store.sessions), { token, userId: user.id, createdAt: Date.now() }],
  });
  return { kind: "ok", user: toPublic(user), token };
}

function pruneSessions(sessions: StoredSession[]): StoredSession[] {
  const now = Date.now();
  return sessions.filter((session) => now - session.createdAt < SESSION_TTL_MS);
}

export function userForToken(token: string): PublicUser | null {
  if (!token) return null;
  const store = read();
  const session = store.sessions.find((item) => item.token === token);
  if (!session || Date.now() - session.createdAt >= SESSION_TTL_MS) return null;
  const user = store.users.find((item) => item.id === session.userId);
  return user ? toPublic(user) : null;
}

export function logout(token: string): void {
  if (!token) return;
  const store = read();
  write({ ...store, sessions: store.sessions.filter((item) => item.token !== token) });
}

/** 운영자 전용 — 주간 알림 대상을 뽑을 때 쓴다.
 *
 * 알림 발송을 자동화하기 전에, 사람이 직접 보내며 "알림이 행동을 만드나"를 먼저 확인한다.
 * 30~50명 규모에서는 그게 더 빠르고, 반응이 없으면 발송 인프라를 아예 안 만들어도 된다. */
export function listUsersForOps(): Array<{
  id: string;
  email: string;
  nickname: string;
  createdAt: string;
  profile: StoredProfile | null;
}> {
  return read().users.map((user) => ({
    id: user.id,
    email: user.email,
    nickname: user.nickname,
    createdAt: user.createdAt,
    profile: user.profile,
  }));
}

export function saveProfile(userId: string, profile: StoredProfile): PublicUser | null {
  const store = read();
  const index = store.users.findIndex((item) => item.id === userId);
  if (index === -1) return null;
  const updated: StoredUser = { ...store.users[index], profile };
  const users = [...store.users];
  users[index] = updated;
  write({ ...store, users });
  return toPublic(updated);
}

export function recordConsultation(userId: string, session: unknown, sessionId: string): void {
  const store = read();
  const existing = store.consultations[userId] || [];
  // 같은 스레드를 이어가면 id가 같다 — 교체하고 맨 앞으로 올린다.
  const withoutSame = existing.filter((item) => (item as { id?: string })?.id !== sessionId);
  const next = [session, ...withoutSame].slice(0, MAX_CONSULTATIONS_PER_USER);
  write({ ...store, consultations: { ...store.consultations, [userId]: next } });
}

export function listConsultations(userId: string): unknown[] {
  return read().consultations[userId] || [];
}

export function deleteConsultation(userId: string, sessionId: string): boolean {
  const store = read();
  const existing = store.consultations[userId] || [];
  const next = existing.filter((item) => (item as { id?: string })?.id !== sessionId);
  if (next.length === existing.length) return false;
  write({ ...store, consultations: { ...store.consultations, [userId]: next } });
  return true;
}

/** 요청 쿠키에서 세션 토큰을 꺼낸다. cookie-parser 의존성을 더하지 않으려고 직접 판다. */
export const SESSION_COOKIE = "jaramlaw_session";
export function tokenFromCookie(cookieHeader: string | undefined): string {
  if (!cookieHeader) return "";
  for (const part of cookieHeader.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name === SESSION_COOKIE) return decodeURIComponent(rest.join("="));
  }
  return "";
}
