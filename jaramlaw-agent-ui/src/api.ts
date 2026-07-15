const TOKEN_KEY = "jaramlaw.operator-token";

export function getOperatorToken(): string {
  return sessionStorage.getItem(TOKEN_KEY) || "";
}

export function setOperatorToken(token: string): void {
  const normalized = token.trim();
  if (normalized) sessionStorage.setItem(TOKEN_KEY, normalized);
  else sessionStorage.removeItem(TOKEN_KEY);
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getOperatorToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}

export async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json();
    return typeof payload?.message === "string" ? payload.message : fallback;
  } catch {
    return fallback;
  }
}
