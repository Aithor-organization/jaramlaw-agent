/** 가입 · 로그인.
 *
 * 가입 시점에 진단에서 받은 프로필을 함께 올린다. 가입 직후 "가족 정보를 입력하세요"
 * 화면이 또 나오면 방금 답한 걸 다시 답하라는 뜻이고, 부모는 거기서 닫는다.
 */
import { FormEvent, useState } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import { familyStageOf, hasProfileInput, type FamilyProfile } from "../profile";
import { login as loginRequest, signup as signupRequest, type AccountUser } from "../auth";

export function AuthView({
  mode,
  profile,
  onAuthenticated,
  onSwitchMode,
  onExit,
}: {
  mode: "signup" | "login";
  profile: FamilyProfile;
  onAuthenticated: (user: AccountUser) => void;
  onSwitchMode: (mode: "signup" | "login") => void;
  onExit: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [consented, setConsented] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const signingUp = mode === "signup";
  const carriesProfile = signingUp && hasProfileInput(profile);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const user = signingUp
        ? await signupRequest(email, password, nickname, carriesProfile ? profile : null, consented)
        : await loginRequest(email, password);
      onAuthenticated(user);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "처리 중 오류가 발생했습니다.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main id="main-content" className="auth-shell" tabIndex={-1}>
      <form className="panel auth-card" onSubmit={submit}>
        <h1>{signingUp ? "자람법 시작하기" : "다시 오셨네요"}</h1>
        <p className="auth-lead">
          {signingUp
            ? "가입하면 맞춤 지원 전체와 상담 기록이 기기를 바꿔도 그대로 남습니다."
            : "가입하실 때 쓰신 이메일로 로그인해 주세요."}
        </p>

        {carriesProfile && (
          <p className="auth-carry">
            진단에서 입력하신 <strong>{profile.region} · {familyStageOf(profile)}</strong> 정보가 그대로 넘어갑니다.
          </p>
        )}

        <label className="field-label" htmlFor="auth-email">이메일</label>
        <input
          id="auth-email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />

        <label className="field-label" htmlFor="auth-password">비밀번호</label>
        <input
          id="auth-password"
          type="password"
          autoComplete={signingUp ? "new-password" : "current-password"}
          required
          minLength={8}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        {signingUp && <p className="auth-hint">8자 이상으로 정해 주세요.</p>}

        {signingUp && (
          <>
            <label className="field-label" htmlFor="auth-nickname">부를 이름 (선택)</label>
            <input
              id="auth-nickname"
              type="text"
              autoComplete="nickname"
              maxLength={20}
              placeholder="비워 두면 이메일 앞부분을 씁니다"
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
            />
          </>
        )}

        {/* 동의는 미리 체크해 두지 않는다. 기본 체크된 동의는 동의가 아니다.
            서버(accounts.createUser)도 같은 검사를 하므로 화면을 우회해도 계정은 안 생긴다. */}
        {signingUp && (
          <div className="consent-row">
            {/* 체크박스 이름은 짧게 고정한다. 설명 문단을 <label>로 감싸면 접근성 이름이
                세 줄짜리 문장이 되고("…저장하는 것은 이메일, 사는 시·도…"), 스크린리더가
                그걸 통째로 읽는다. 설명은 aria-describedby로 분리해 붙인다. */}
            <input
              id="auth-consent"
              type="checkbox"
              aria-label="개인정보 처리방침 및 이용약관 동의 (필수)"
              aria-describedby="auth-consent-desc"
              checked={consented}
              onChange={(event) => setConsented(event.target.checked)}
              required
            />
            <span id="auth-consent-desc">
              {/* 새 탭으로 연다 — 작성 중인 가입 폼을 잃지 않게. */}
              <a href="#/privacy" target="_blank" rel="noreferrer">개인정보 처리방침</a>
              {" 및 "}
              <a href="#/terms" target="_blank" rel="noreferrer">이용약관</a>
              에 동의합니다. (필수)
              <small>저장하는 것은 이메일, 사는 시·도, 아이 출생 연월입니다. 아이 이름과 정확한 주소는 받지 않습니다.</small>
            </span>
          </div>
        )}

        {error && <p className="form-status is-error" role="alert">{error}</p>}

        <button type="submit" className="btn btn-primary btn-lg" disabled={busy || (signingUp && !consented)}>
          {busy ? <><Loader2 className="spin" aria-hidden="true" /> 처리 중</> : <>{signingUp ? "가입하기" : "로그인"} <ArrowRight aria-hidden="true" /></>}
        </button>

        <div className="auth-switch">
          {signingUp ? (
            <button type="button" className="btn-text" onClick={() => onSwitchMode("login")}>
              이미 가입하셨나요? 로그인
            </button>
          ) : (
            <button type="button" className="btn-text" onClick={() => onSwitchMode("signup")}>
              처음이신가요? 가입하기
            </button>
          )}
          <button type="button" className="btn-text" onClick={onExit}>첫 화면으로</button>
        </div>
      </form>
    </main>
  );
}
