import { AlertTriangle, CheckCircle2, HelpCircle } from "lucide-react";
import type { RiskAnalysis } from "../types";

type SignalTone = "good" | "partial" | "attention";

function reviewTier(score: number): { label: string; detail: string; tone: SignalTone } {
  if (score >= 70) return { label: "우선 검토", detail: "전문가 또는 관계기관 확인을 먼저 권합니다.", tone: "attention" };
  if (score >= 40) return { label: "추가 확인", detail: "문서와 상대방 통지 기록을 더 확인해야 합니다.", tone: "partial" };
  return { label: "기본 확인", detail: "현재 자료로 안내할 수 있지만 예외를 확인해야 합니다.", tone: "good" };
}

function strengthTone(value: number, inverse = false): SignalTone {
  const normalized = inverse ? 100 - value : value;
  if (normalized >= 70) return "good";
  if (normalized >= 40) return "partial";
  return "attention";
}

function toneLabel(tone: SignalTone): string {
  if (tone === "good") return "확인됨";
  if (tone === "partial") return "부분 확인";
  return "추가 검토";
}

export function DisputeChart({ analysis }: { analysis: RiskAnalysis }) {
  const tier = reviewTier(analysis.overallScore);
  const signals = [
    { label: "계약 문구", tone: strengthTone(analysis.contractualAmbiguity, true), note: "계약서와 특약의 명확성" },
    { label: "증거 자료", tone: strengthTone(analysis.evidenceStrength), note: "영수증, 통지, 사진 등 확보 수준" },
    { label: "법령 근거", tone: strengthTone(analysis.precedentSupport), note: "현재 근거와 상황의 연결 정도" },
    { label: "생활 영향", tone: strengthTone(analysis.financialImpact, true), note: "금전·돌봄 부담의 확인 필요성" },
  ];

  return (
    <section className="review-summary" aria-labelledby="review-summary-title">
      <div className="section-title">
        <div>
          <p className="eyebrow">근거 기반 점검</p>
          <h2 id="review-summary-title">상담 검토 상태</h2>
        </div>
        <span className={`review-tier tone-${tier.tone}`}>{tier.label}</span>
      </div>

      <p className="trust-note">
        <HelpCircle aria-hidden="true" />
        이 표시는 통계적 승소·분쟁 확률이 아니라 입력된 자료를 규칙으로 점검한 우선순위입니다.
      </p>

      <div className="signal-table" role="table" aria-label="상담 근거별 확인 상태">
        {signals.map((signal) => {
          const Icon = signal.tone === "good" ? CheckCircle2 : AlertTriangle;
          return (
            <div className="signal-row" role="row" key={signal.label}>
              <Icon aria-hidden="true" className={`tone-icon-${signal.tone}`} />
              <span role="cell">
                <strong>{signal.label}</strong>
                <small>{signal.note}</small>
              </span>
              <em role="cell" className={`tone-text-${signal.tone}`}>{toneLabel(signal.tone)}</em>
            </div>
          );
        })}
      </div>

      <div className="reason-box">
        <strong>판단 근거</strong>
        <p>{analysis.riskReason}</p>
        <span>{tier.detail}</span>
      </div>

      <ol className="action-list">
        {analysis.recommendations.map((recommendation) => <li key={recommendation}>{recommendation}</li>)}
      </ol>
    </section>
  );
}
