/** 3분 진단 — 로그인 없이 도는 온보딩 (디자인 시스템 §4.6).
 *
 * 한 화면에 질문 하나. Primary 버튼도 화면당 하나(`다음`)이고 `이전`은 텍스트 링크다.
 *
 * 선택지는 **실제 `<input type="radio">`** 위에 얹는다. div + onClick으로 만들면
 * 스크린리더에 그룹으로 읽히지 않고 화살표 탐색도 죽는다 — 시스템이 명시적으로
 * 금지한 형태다. 라디오를 시각적으로 숨기고 `:has(input:checked)`로 선택 행을 그린다.
 *
 * 아이 태어난 달은 버킷(0-1세 등)이 아니라 실제 연월을 받는다. 신청 기한 D-day가
 * 생년월에서 나오므로 대표값을 지어내면 화면의 날짜가 틀린 날짜가 된다.
 */
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Check as CheckIcon } from "lucide-react";
import { DEFAULT_PROFILE, REGIONS, type FamilyProfile } from "../profile";
import { THIS_YEAR, YearMonthPicker, isYearMonth } from "../components/YearMonthPicker";
import type { StagePreset } from "./Landing";

const CONCERNS = [
  { key: "academy", label: "학원비 · 환불 문제" },
  { key: "daycare", label: "어린이집 · 유치원 일" },
  { key: "leave", label: "육아휴직 · 직장 문제" },
  { key: "none", label: "아직 특별한 일은 없어요" },
];

/** 랜딩 카드 → 진단 시작 지점. 시기를 이미 고른 분께 같은 질문을 또 하지 않는다. */
function startFrom(preset: StagePreset | null): { step: number; profile: FamilyProfile } {
  const base: FamilyProfile = { ...DEFAULT_PROFILE, children: [{ birthMonth: "" }] };
  if (preset === "expecting") return { step: 1, profile: { ...base, household: "expecting", children: [] } };
  if (preset === "infant" || preset === "preschool" || preset === "school") return { step: 1, profile: base };
  return { step: 0, profile: base };
}

/** 선택 행 하나. 라디오가 실체이고 나머지는 표시다. */
function OptionRow({
  name,
  checked,
  label,
  onSelect,
}: {
  key?: string;
  name: string;
  checked: boolean;
  label: string;
  onSelect: () => void;
}) {
  return (
    <label className="option-row">
      <input type="radio" name={name} checked={checked} onChange={onSelect} />
      <CheckIcon className="option-check" aria-hidden="true" />
      <span>{label}</span>
    </label>
  );
}

export function CheckWizard({
  preset,
  onDone,
  onExit,
}: {
  preset: StagePreset | null;
  onDone: (profile: FamilyProfile) => void;
  onExit: () => void;
}) {
  const initial = startFrom(preset);
  const [step, setStep] = useState(initial.step);
  const [profile, setProfile] = useState<FamilyProfile>(initial.profile);
  const [error, setError] = useState("");
  /* 선택 여부를 프로필 값에서 유추하면 안 된다. FamilyProfile 은 기본값을 들고 있어서
     (household="two-caregivers") 아무것도 고르지 않은 첫 화면에서 두 번째 선택지가
     이미 선택된 것처럼 보인다 — 질문을 대신 답해버리는 셈이다. 실제로 누른 답만 따로 센다. */
  const [picked, setPicked] = useState<Record<string, string>>({});
  const firstFieldRef = useRef<HTMLSelectElement | null>(null);

  const expecting = profile.household === "expecting";
  const TOTAL = 5;

  // 단계가 바뀌면 오류 문구를 지운다 — 이전 단계의 경고가 다음 화면에 남지 않게.
  useEffect(() => { setError(""); }, [step]);

  const back = () => (step === 0 ? onExit() : setStep((s) => s - 1));
  const advance = () => setStep((s) => Math.min(s + 1, TOTAL - 1));

  const missingMessage = (): string => {
    if (step === 1) {
      if (expecting && !isYearMonth(profile.expectedDate.slice(0, 7))) return "출산 예정 연도와 월을 모두 골라 주세요.";
      if (!expecting && !profile.children.some((c) => isYearMonth(c.birthMonth))) return "아이가 태어난 연도와 월을 모두 골라 주세요.";
    }
    if (step === 3 && !profile.region) return "사시는 시·도를 골라 주세요.";
    return "";
  };

  /** 검증 실패 시 문구만 띄우지 않고 해당 필드로 포커스를 옮긴다 (§4.6). */
  const next = () => {
    const message = missingMessage();
    if (message) {
      setError(message);
      firstFieldRef.current?.focus();
      return;
    }
    setError("");
    advance();
  };

  const pick = (question: string, answer: string, patch: Partial<FamilyProfile>) => {
    setPicked((current) => ({ ...current, [question]: answer }));
    setProfile((current) => ({ ...current, ...patch }));
    setError("");
    advance();
  };

  return (
    <main id="main-content" className="check-shell" tabIndex={-1}>
      <div className="check-progress">
        {/* 1단계에서는 '이전'을 렌더하지 않는다 — 대신 첫 화면으로 나가는 링크 */}
        <button type="button" className="check-back" onClick={back}>
          <ArrowLeft aria-hidden="true" /> {step === 0 ? "첫 화면" : "이전"}
        </button>
        <span className="check-step-counter">
          {step + 1} / {TOTAL}
          <span className="sr-only">단계</span>
        </span>
        <div
          className="check-bar"
          role="progressbar"
          aria-valuenow={step + 1}
          aria-valuemin={1}
          aria-valuemax={TOTAL}
          aria-label={`${TOTAL}단계 중 ${step + 1}단계`}
        >
          <span style={{ width: `${((step + 1) / TOTAL) * 100}%` }} />
        </div>
      </div>

      <div className="check-body">
        {step === 0 && (
          <fieldset className="check-step">
            <legend><h1>지금 어느 시기인가요?</h1></legend>
            <div className="check-options" role="radiogroup" aria-label="지금 어느 시기인가요?">
              <OptionRow
                name="stage"
                label="임신 중이에요"
                checked={picked.stage === "expecting"}
                onSelect={() => pick("stage", "expecting", { household: "expecting", children: [] })}
              />
              <OptionRow
                name="stage"
                label="아이가 태어났어요"
                checked={picked.stage === "born"}
                onSelect={() => pick("stage", "born", { household: "two-caregivers", children: [{ birthMonth: "" }] })}
              />
            </div>
          </fieldset>
        )}

        {step === 1 && expecting && (
          <fieldset className="check-step">
            <legend><h1>출산 예정일이 언제인가요?</h1></legend>
            <p className="check-hint">
              예정 월까지만 여쭤봅니다. 첫만남이용권·부모급여 신청 시기를 안내하는 데는 그것으로 충분합니다.
            </p>
            <YearMonthPicker
              label="출산 예정"
              firstRef={firstFieldRef}
              invalid={Boolean(error)}
              yearFrom={THIS_YEAR}
              yearTo={THIS_YEAR + 1}
              value={profile.expectedDate.slice(0, 7)}
              onChange={(next) => setProfile({ ...profile, expectedDate: next })}
            />
          </fieldset>
        )}

        {step === 1 && !expecting && (
          <fieldset className="check-step">
            <legend><h1>아이가 태어난 달을 알려주세요</h1></legend>
            <p className="check-hint">
              날짜는 묻지 않습니다. 연도와 월만 있으면 신청 기한을 계산할 수 있어, 그만큼만 받습니다.
            </p>
            {profile.children.map((child, index) => (
              <div key={index} className="check-child-row">
                <span>{index + 1}째</span>
                <YearMonthPicker
                  label={`${index + 1}째 아이 출생`}
                  firstRef={index === 0 ? firstFieldRef : undefined}
                  invalid={Boolean(error) && index === 0}
                  yearFrom={THIS_YEAR - 18}
                  yearTo={THIS_YEAR}
                  value={child.birthMonth}
                  onChange={(next) => {
                    const children = profile.children.map((c, i) =>
                      i === index ? { birthMonth: next } : c);
                    setProfile({ ...profile, children });
                  }}
                />
              </div>
            ))}
            <div className="check-child-actions">
              {profile.children.length < 6 && (
                <button
                  type="button"
                  className="btn-text"
                  onClick={() => setProfile({ ...profile, children: [...profile.children, { birthMonth: "" }] })}
                >아이 추가</button>
              )}
              {profile.children.length > 1 && (
                <button
                  type="button"
                  className="btn-text"
                  onClick={() => setProfile({ ...profile, children: profile.children.slice(0, -1) })}
                >마지막 아이 지우기</button>
              )}
            </div>
          </fieldset>
        )}

        {step === 2 && (
          <fieldset className="check-step">
            <legend><h1>누가 함께 키우고 있나요?</h1></legend>
            <p className="check-hint">한부모 가정만 해당하는 지원이 따로 있어 여쭤봅니다.</p>
            <div className="check-options" role="radiogroup" aria-label="누가 함께 키우고 있나요?">
              <OptionRow
                name="household"
                label="둘이서 함께 키워요"
                checked={picked.household === "together"}
                onSelect={() => pick("household", "together", { household: expecting ? "expecting" : "two-caregivers" })}
              />
              <OptionRow
                name="household"
                label="혼자 키우고 있어요"
                checked={picked.household === "single"}
                onSelect={() => pick("household", "single", { household: "single-caregiver" })}
              />
            </div>
          </fieldset>
        )}

        {step === 3 && (
          <fieldset className="check-step">
            <legend><h1>어디에 사시나요?</h1></legend>
            <p className="check-hint">지자체마다 지원이 달라 시·도까지만 확인합니다. 상세 주소는 받지 않습니다.</p>
            <div className="check-region-grid" role="radiogroup" aria-label="거주 지역">
              {REGIONS.map((region, index) => (
                <label key={region}>
                  <input
                    ref={index === 0 ? firstFieldRef : undefined}
                    type="radio"
                    name="region"
                    checked={profile.region === region}
                    onChange={() => { setProfile({ ...profile, region }); setError(""); advance(); }}
                  />
                  <span>{region}</span>
                </label>
              ))}
            </div>
          </fieldset>
        )}

        {step === 4 && (
          <fieldset className="check-step">
            <legend><h1>요즘 걸리는 일이 있나요?</h1></legend>
            <p className="check-hint">있으면 상담 화면에 미리 올려 두겠습니다. 없으면 건너뛰셔도 됩니다.</p>
            <div className="check-options" role="radiogroup" aria-label="요즘 걸리는 일">
              {CONCERNS.map((concern) => (
                <OptionRow
                  key={concern.key}
                  name="concern"
                  label={concern.label}
                  checked={profile.concern === concern.key}
                  onSelect={() => onDone({ ...profile, concern: concern.key === "none" ? "" : concern.key })}
                />
              ))}
            </div>
          </fieldset>
        )}
      </div>

      {(step === 1 || step === 3) && (
        <div className="check-footer">
          {/* 오류는 aria-live 로 읽히고, 포커스는 위 next() 가 해당 필드로 옮긴다 */}
          {error && <p className="check-error" role="alert">{error}</p>}
          <button type="button" className="btn btn-primary btn-xl" onClick={next}>
            다음 <ArrowRight aria-hidden="true" />
          </button>
        </div>
      )}

      {step === 4 && (
        <div className="check-footer">
          <button type="button" className="btn-text" onClick={() => onDone({ ...profile, concern: "" })}>
            건너뛰고 결과 보기
          </button>
        </div>
      )}
    </main>
  );
}
