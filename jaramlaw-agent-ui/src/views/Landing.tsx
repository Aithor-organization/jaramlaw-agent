/** 랜딩 — 로그인하지 않은 보호자가 가장 먼저 보는 화면.
 *
 * 구성은 jaranda.kr 문법을 따른다: 이미지 슬라이드 히어로 → 서비스 설명 →
 * 기능별 실제 화면 → FAQ → 마감 CTA. 시각 언어는 자람법 디자인 시스템을 따른다
 * (light only · 깊이는 보더 · 그라디언트 없음).
 *
 * 기능 목업은 그림이 아니라 **실제 앱 화면 캡처**다 (public/assets/ui/*.png —
 * Playwright로 로컬 앱을 찍은 것). 자람법은 "근거를 보여주는 도구"라서, 랜딩의
 * 화면마저 지어낸 그림이면 제품의 약속과 어긋난다.
 *
 * 슬라이더는 자동재생하지 않는다. 디자인 시스템 §6이 모션을 진행바·아코디언·
 * 백드롭으로 제한하고, 자동으로 움직이는 배너는 저시력·고령 사용자가 읽는 중에
 * 화면을 빼앗는다. 수동 이동(화살표·점)만 둔다.
 */
import { useState } from "react";
import { ArrowRight, ChevronLeft, ChevronRight, Info } from "lucide-react";
import type { HealthStatus } from "../types";

export type StagePreset = "expecting" | "infant" | "preschool" | "school" | "trouble";

const STAGE_CARDS: Array<{ key: StagePreset; label: string; hint: string }> = [
  { key: "expecting", label: "임신 중", hint: "출산 전에 확인할 지원" },
  { key: "infant", label: "첫돌 전", hint: "부모급여 · 육아휴직" },
  { key: "preschool", label: "어린이집 · 유치원", hint: "보육료 · 사고 대응" },
  { key: "school", label: "초등학생", hint: "학원비 · 학교 문제" },
  { key: "trouble", label: "지금 일이 생겼어요", hint: "환불 · 사고 · 통지문" },
];

/* 히어로 슬라이드 2장.
   ① 사진 슬라이드 — 저장소에 있던 밝은 톤 제품 사진.
      (다른 한 장(legal-workflow-room)은 어두운 3D 렌더라 light-only 시스템과 충돌해
       랜딩에서 쓰지 않는다. 이미지 생성 API는 이 머신에 연결돼 있지 않다.)
   ② 제품 슬라이드 — 실제 진단 결과 화면. 그림 대신 실화면을 쓰는 것이 제품 약속과 맞다. */
const SLIDES = [
  {
    kind: "photo" as const,
    image: "/assets/jaramlaw-parent-guidance-hero.png",
    kicker: "가족 법령·정책 안내",
    title: "우리 아이에게 지금 해당하는\n지원과 기한을 정리해 드립니다",
    body: "아이가 태어난 달과 사는 시·도만 알려주시면 됩니다.",
  },
  {
    kind: "product" as const,
    image: "/assets/ui/feature-result.png",
    alt: "진단 결과 화면 — 아동수당·육아휴직 급여와 신청 D-day",
    kicker: "근거 있는 안내",
    title: "“된다”는 말 대신,\n어떤 법 몇 조인지 함께 보여드립니다",
    body: "판단마다 근거 조문 원문을 붙입니다. 확인은 공식 출처로 이어집니다.",
  },
];

const FEATURES = [
  {
    id: "check",
    image: "/assets/ui/feature-check.png",
    alt: "3분 진단 화면 — 아이가 태어난 달을 연도와 월 셀렉트로 입력",
    title: "다섯 문항, 3분 진단",
    body: "한 화면에 질문 하나씩. 아이 생년월과 사는 시·도만 답하면 됩니다. 이름과 정확한 주소는 받지 않습니다.",
  },
  {
    id: "result",
    image: "/assets/ui/feature-result.png",
    alt: "진단 결과 화면 — 아동수당 월 10만원 D-30, 육아휴직 급여 등 맞춤 지원 목록",
    title: "맞춤 지원과 신청 기한을 한눈에",
    body: "해당할 가능성이 있는 지원제도를 금액·조건과 함께 정리하고, 신청 기한은 D-day로 보여드립니다.",
  },
  {
    id: "laws",
    image: "/assets/ui/feature-laws.png",
    alt: "법령 화면 — 남녀고용평등법 제19조 육아휴직 조문과 요약",
    title: "판단마다 근거 조문을 붙입니다",
    body: "육아휴직·학원 환불·CCTV 열람 — 안내 하나하나에 어떤 법 몇 조에서 나온 것인지 원문을 함께 둡니다.",
  },
  {
    id: "docs",
    image: "/assets/ui/feature-docs.png",
    alt: "문서 정리 화면 — 학원 환불 요청 서한의 쟁점·주의할 부분·다음 행동 정리",
    title: "받은 문서의 쟁점을 찾아드립니다",
    body: "학원 안내문, 어린이집 통지문을 붙여 넣으면 확인할 부분과 다음 행동을 나눠 정리합니다.",
  },
];

const FAQS = [
  {
    q: "자람법이 법률 자문인가요?",
    a: "아닙니다. 자람법은 양육 정보 보조 도구입니다. 안내해 드리는 내용은 '받을 가능성이 있는 지원'이며 지급 결정이나 사건별 법률 판단이 아닙니다. 아동학대·사고·소송처럼 시급한 사안은 관계기관이나 전문가 확인을 먼저 받으세요.",
  },
  {
    q: "어떤 정보를 입력해야 하나요?",
    a: "아이가 태어난 연도와 월, 사는 시·도, 가족 상황(함께/혼자 양육)입니다. 이름, 정확한 주소, 주민등록번호는 받지 않습니다.",
  },
  {
    q: "이용료가 있나요?",
    a: "없습니다. 진단과 맞춤 지원 확인 모두 무료입니다.",
  },
  {
    q: "가입하면 무엇이 달라지나요?",
    a: "진단 결과 전체(모든 지원제도·신청 기한·우리아이 법령 캘린더)를 볼 수 있고, 상담 기록과 가족 정보가 계정에 남아 기기를 바꿔도 그대로 이어집니다.",
  },
  {
    q: "안내가 실제 법과 다르면 어떡하죠?",
    a: "화면 하단에 수록 법령의 기준 시행일을 항상 표시하고, 모든 안내에 공식 출처(국가법령정보센터·복지로 등) 링크를 붙입니다. 신청 전에는 반드시 공식 사이트에서 다시 확인하시길 안내드립니다.",
  },
  {
    q: "아이가 여러 명이어도 되나요?",
    a: "됩니다. 진단에서 아이를 최대 6명까지 추가할 수 있고, 지원제도는 각 아이의 나이에 맞춰 따로 계산됩니다.",
  },
];

export function Landing({
  health,
  onStart,
  onLogin,
}: {
  health: HealthStatus | null;
  onStart: (preset: StagePreset) => void;
  onLogin: () => void;
}) {
  const [slide, setSlide] = useState(0);
  const go = (next: number) => setSlide((next + SLIDES.length) % SLIDES.length);
  const current = SLIDES[slide];

  return (
    <main id="main-content" className="landing" tabIndex={-1}>
      {/* ① 히어로 — 이미지 슬라이드 */}
      <section className="landing-hero-slider" aria-roledescription="carousel" aria-label="자람법 소개 슬라이드">
        <div
          className={`hero-slide${current.kind === "product" ? " hero-slide-product" : ""}`}
          style={current.kind === "photo" ? { backgroundImage: `url(${current.image})` } : undefined}
        >
          {/* 사진 위 텍스트는 단색 오버레이 패널로 가독성을 확보한다 (§Source Assets) */}
          <div className="hero-slide-panel">
            <p className="hero-kicker">{current.kicker}</p>
            <h1 className="display">
              {current.title.split("\n").map((line) => <span key={line}>{line}<br /></span>)}
            </h1>
            <p className="hero-body">{current.body}</p>
            <button type="button" className="btn btn-primary btn-xl" onClick={() => onStart("trouble")}>
              3분 진단 시작하기 <ArrowRight aria-hidden="true" />
            </button>
          </div>
          {current.kind === "product" && (
            <figure className="hero-product-shot">
              <img src={current.image} alt={current.alt ?? ""} />
            </figure>
          )}
        </div>
        <div className="hero-controls">
          <button type="button" className="hero-arrow" aria-label="이전 슬라이드" onClick={() => go(slide - 1)}>
            <ChevronLeft aria-hidden="true" />
          </button>
          <div className="hero-dots" role="tablist" aria-label="슬라이드 선택">
            {SLIDES.map((s, index) => (
              <button
                key={s.kicker}
                type="button"
                role="tab"
                aria-selected={index === slide}
                aria-label={`${index + 1}번째 슬라이드`}
                className={index === slide ? "is-active" : ""}
                onClick={() => setSlide(index)}
              />
            ))}
          </div>
          <button type="button" className="hero-arrow" aria-label="다음 슬라이드" onClick={() => go(slide + 1)}>
            <ChevronRight aria-hidden="true" />
          </button>
          <span className="sr-only" aria-live="polite">{slide + 1}번째 슬라이드, 총 {SLIDES.length}장</span>
        </div>
      </section>

      {/* ② 진입 카드 */}
      <section className="landing-stages" aria-labelledby="stage-heading">
        <h2 id="stage-heading" className="section-heading">지금 어느 시기인가요?</h2>
        <p className="section-sub">하나를 고르면 진단이 시작됩니다.</p>
        <div className="stage-picker">
          {STAGE_CARDS.map((card) => (
            <button type="button" key={card.key} className="stage-pick" onClick={() => onStart(card.key)}>
              <strong>{card.label}</strong>
              <small>{card.hint}</small>
              <ArrowRight aria-hidden="true" />
            </button>
          ))}
        </div>
      </section>

      {/* ③ 자람법 설명 */}
      <section className="landing-about" aria-labelledby="about-heading">
        <h2 id="about-heading" className="section-heading">자람법은 이런 도구입니다</h2>
        <p className="about-lead">
          지원제도는 복지로·정부24·고용보험·교육청에 흩어져 있고, 신청 기간은 대부분 지난 뒤에는
          소급되지 않습니다. 자람법은 아이의 나이를 기준으로 <strong>지금 해당하는 것</strong>과
          <strong> 놓치면 안 되는 날짜</strong>를 한곳에 모아, 근거 조문과 함께 보여드립니다.
        </p>
        <p className="about-meta">
          법령 {health?.seed_data.laws ?? "–"}건 · 지원제도 {health?.seed_data.supports ?? "–"}건 수록
          {health?.seed_data.latest_effective_date ? ` · 최신 시행일 ${health.seed_data.latest_effective_date}` : ""}
        </p>
      </section>

      {/* ④ 기능 — 실제 앱 화면 */}
      <section className="landing-features" aria-labelledby="features-heading">
        <h2 id="features-heading" className="section-heading">이렇게 동작합니다</h2>
        <p className="section-sub">아래 화면은 목업이 아니라 실제 서비스 화면입니다.</p>
        {FEATURES.map((feature, index) => (
          <article key={feature.id} className={`feature-row${index % 2 ? " is-flipped" : ""}`}>
            <div className="feature-copy">
              <span className="step-no">{String(index + 1).padStart(2, "0")}</span>
              <h3>{feature.title}</h3>
              <p>{feature.body}</p>
            </div>
            <figure className="feature-shot">
              <img src={feature.image} alt={feature.alt} loading="lazy" />
            </figure>
          </article>
        ))}
      </section>

      {/* ⑤ FAQ */}
      <section className="landing-faq" aria-labelledby="faq-heading">
        <h2 id="faq-heading" className="section-heading">자주 묻는 질문</h2>
        <div className="faq-list">
          {FAQS.map((item) => (
            <details key={item.q} className="faq-item">
              <summary>{item.q}</summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* ⑥ 마감 CTA + 면책 */}
      <section className="landing-close">
        <h2 className="section-heading">지금 확인해 보시겠어요?</h2>
        <button type="button" className="btn btn-primary btn-xl" onClick={() => onStart("trouble")}>
          3분 진단 시작하기 <ArrowRight aria-hidden="true" />
        </button>
        <button type="button" className="btn-text" onClick={onLogin}>
          이미 가입하셨나요? 로그인
        </button>
        <p className="disclaimer">
          <Info aria-hidden="true" />
          <span>
            자람법은 법률 자문이 아닌 양육 정보 보조 도구입니다. 안내해 드리는 내용은
            &lsquo;받을 가능성이 있는 지원&rsquo;이며 지급 결정이 아닙니다. 아동학대·사고·소송처럼
            시급한 사안은 관계기관이나 전문가 확인을 먼저 받으시기 바랍니다.
          </span>
        </p>
      </section>
    </main>
  );
}
