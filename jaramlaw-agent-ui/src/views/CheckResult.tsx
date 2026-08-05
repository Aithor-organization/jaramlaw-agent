/** 진단 결과 미리보기 — 가입 전환이 일어나는 유일한 화면.
 *
 * 상위 2건은 실제 매칭 결과를 그대로 보여주고, 나머지는 건수만 알려준다. 잠금은
 * 서버가 건다(server.ts /api/briefing의 preview 분기) — CSS 블러로 가리면 개발자도구를
 * 여는 순간 다 보이므로 가린 척에 지나지 않는다.
 *
 * 잠긴 자리에 가짜 항목 이름을 채워 넣지 않는다. 부모가 가입하고 나서 "그거 어디
 * 갔냐"고 묻게 되는 종류의 거짓말이기 때문이다. 건수만 정직하게 센다.
 */
import { useEffect, useState } from "react";
import { ArrowRight, CalendarClock, Info, Lock, Loader2, RefreshCw } from "lucide-react";
import { familyStageOf, type FamilyProfile } from "../profile";
import { formatKrw } from "../format";

interface PreviewSupport {
  name: string;
  amount_krw: number;
  amount_description: string;
  condition_summary: string;
  application_channel: string;
  deadline_days_left: number | null;
}

interface PreviewState {
  loading: boolean;
  error: string;
  supports: PreviewSupport[];
  lockedCount: number;
}

export function CheckResult({
  profile,
  onSignup,
  onLogin,
  onRestart,
}: {
  profile: FamilyProfile;
  onSignup: () => void;
  onLogin: () => void;
  onRestart: () => void;
}) {
  const [state, setState] = useState<PreviewState>({ loading: true, error: "", supports: [], lockedCount: 0 });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch("/api/briefing", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            region: profile.region,
            household: profile.household,
            children: profile.children.filter((child) => child.birthMonth),
            expectedDate: profile.household === "expecting" ? profile.expectedDate : "",
          }),
        });
        const payload = await response.json();
        if (cancelled) return;
        if (!response.ok || payload.status !== "success") {
          setState({
            loading: false,
            // 매칭 엔진이 내려가 있어도 가입 자체는 막지 않는다 — 아래 CTA는 그대로 산다.
            error: "지금은 결과를 계산하지 못했습니다. 잠시 후 다시 시도해 주세요.",
            supports: [],
            lockedCount: 0,
          });
          return;
        }
        setState({
          loading: false,
          error: "",
          supports: (payload.data?.supports ?? []) as PreviewSupport[],
          lockedCount: typeof payload.locked_count === "number" ? payload.locked_count : 0,
        });
      } catch {
        if (!cancelled) {
          setState({ loading: false, error: "네트워크 오류로 결과를 불러오지 못했습니다.", supports: [], lockedCount: 0 });
        }
      }
    })();
    return () => { cancelled = true; };
  }, [profile]);

  const stage = familyStageOf(profile);
  const found = state.supports.length + state.lockedCount;

  return (
    <main id="main-content" className="result-shell" tabIndex={-1}>
      <header className="result-head">
        <p className="eyebrow">{profile.region} · {stage}</p>
        {state.loading ? (
          <h1><Loader2 className="spin" aria-hidden="true" /> 우리 가족 기준으로 찾는 중입니다</h1>
        ) : state.error ? (
          <h1>결과를 불러오지 못했습니다</h1>
        ) : (
          <h1>지금 확인할 수 있는 항목 {found}건을 찾았습니다</h1>
        )}
      </header>

      {state.error && (
        <div className="panel result-error" role="status">
          <p>{state.error}</p>
          <button type="button" className="btn-text" onClick={onRestart}>
            <RefreshCw aria-hidden="true" /> 진단 다시 하기
          </button>
        </div>
      )}

      {!state.loading && !state.error && (
        <>
          <ul className="result-list">
            {state.supports.map((support) => (
              <li key={support.name} className="result-item">
                <div className="result-item-head">
                  <strong>{support.name}</strong>
                  {typeof support.deadline_days_left === "number" && (
                    /* 색만으로 상태를 전달하지 않는다 — 배지 안에 상태어를 함께 넣는다 */
                    <span className={`dday ${support.deadline_days_left <= 7 ? "dday-soon" : "dday-ok"}`}>
                      {support.deadline_days_left === 0
                        ? "오늘 마감"
                        : support.deadline_days_left <= 7
                          ? `D-${support.deadline_days_left} 마감 임박`
                          : `D-${support.deadline_days_left} 신청 기간`}
                    </span>
                  )}
                </div>
                {/* 숫자만 떼어 쓰면 "2,500,000원"이 일시금으로 읽힌다. 실제로는 월 상한이다.
                    단위와 조건이 붙어 있는 amount_description을 앞세운다. */}
                <p className="result-amount">
                  {support.amount_description || formatKrw(support.amount_krw) || "금액은 조건에 따라 달라집니다"}
                </p>
                {support.condition_summary && <p className="result-condition">{support.condition_summary}</p>}
                {support.application_channel && (
                  <p className="result-channel">신청: {support.application_channel}</p>
                )}
              </li>
            ))}

            {state.lockedCount > 0 && (
              <li className="result-item result-locked">
                <Lock aria-hidden="true" />
                <div>
                  <strong>나머지 {state.lockedCount}건</strong>
                  <p>남은 지원제도와 신청 기한, 우리아이 법령 캘린더는 가입 후 보실 수 있습니다.</p>
                </div>
              </li>
            )}
          </ul>

          {state.supports.length === 0 && state.lockedCount === 0 && (
            <p className="empty-copy">
              입력하신 조건으로 자동 매칭된 지원제도가 없습니다. 가입 후 상담에서 상황을 적어 주시면
              더 정확하게 확인해 드립니다.
            </p>
          )}
        </>
      )}

      <section className="result-cta">
        <button type="button" className="btn btn-primary btn-xl" onClick={onSignup}>
          가입하고 전부 보기 <ArrowRight aria-hidden="true" />
        </button>
        <p className="privacy-note">
          <CalendarClock aria-hidden="true" />
          지금 입력하신 내용은 가입할 때 그대로 넘어갑니다. 다시 적지 않으셔도 됩니다.
        </p>
        <button type="button" className="btn-text" onClick={onLogin}>이미 가입하셨나요? 로그인</button>
        <button type="button" className="btn-text" onClick={onRestart}>진단 다시 하기</button>
      </section>

      {/* 결과가 표시되는 화면에는 면책을 상시 노출한다 — 접거나 푸터로 밀지 않는다 */}
      <p className="disclaimer">
        <Info aria-hidden="true" />
        <span>
          여기 보이는 항목은 &lsquo;받을 가능성이 있는 지원&rsquo;이며 지급 결정이 아닙니다.
          금액과 조건은 예산·정책에 따라 달라질 수 있으니 신청 전 공식 사이트에서 다시 확인해 주세요.
        </span>
      </p>
    </main>
  );
}
