import { useEffect, useState } from "react";
import { CheckCircle2, Save, Star, UserCheck } from "lucide-react";
import { apiFetch, readApiError } from "../api";
import type { ConsultationSession } from "../types";

interface ExpertReviewPanelProps {
  session: ConsultationSession;
  onFeedbackSaved: (updated: ConsultationSession) => void;
  onUnauthorized?: () => void;
}

export function ExpertReviewPanel({ session, onFeedbackSaved, onUnauthorized }: ExpertReviewPanelProps) {
  const [reviewerName, setReviewerName] = useState("");
  const [feedbackText, setFeedbackText] = useState("");
  const [rating, setRating] = useState(3);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("검토 내용을 입력한 뒤 초안 또는 확인 완료로 저장하세요.");

  useEffect(() => {
    setReviewerName(session.expertFeedback?.reviewerName || "");
    setFeedbackText(session.expertFeedback?.feedbackText || "");
    setRating(session.expertFeedback?.rating || 3);
    setMessage("검토 내용을 입력한 뒤 초안 또는 확인 완료로 저장하세요.");
  }, [session.id, session.expertFeedback]);

  const save = async (status: "draft" | "verified") => {
    if (!reviewerName.trim() || !feedbackText.trim()) {
      setMessage("전문가 이름과 검토 의견을 모두 입력하세요.");
      return;
    }
    setSaving(true);
    setMessage("검토 내용을 저장하고 있습니다.");
    try {
      const response = await apiFetch(`/api/history/${session.id}/expert-review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewerName: reviewerName.trim(), feedbackText: feedbackText.trim(), rating, status }),
      });
      if (response.status === 401) {
        onUnauthorized?.();
        throw new Error("운영자 인증이 만료되었습니다.");
      }
      if (!response.ok) throw new Error(await readApiError(response, "검토 저장에 실패했습니다."));
      const payload = await response.json();
      onFeedbackSaved(payload.data);
      setMessage(status === "verified" ? "전문가 확인 완료로 저장했습니다." : "검토 초안을 저장했습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "검토 저장 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="panel expert-review" aria-labelledby="expert-review-title">
      <div className="section-title">
        <div>
          <p className="eyebrow">사람의 확인</p>
          <h2 id="expert-review-title">전문가 검토 기록</h2>
        </div>
        <span className={`status-badge ${session.expertFeedback?.status === "verified" ? "tone-good" : "tone-neutral"}`}>
          {session.expertFeedback?.status === "verified" ? "확인 완료" : session.expertFeedback ? "초안" : "대기"}
        </span>
      </div>

      {session.expertFeedback?.status === "verified" && (
        <div className="verified-review">
          <CheckCircle2 aria-hidden="true" />
          <div>
            <strong>{session.expertFeedback.reviewerName}</strong>
            <p>{session.expertFeedback.feedbackText}</p>
            <span>{new Date(session.expertFeedback.reviewedAt).toLocaleString("ko-KR")}</span>
          </div>
        </div>
      )}

      <div className="form-grid two-columns">
        <div>
          <label className="field-label" htmlFor="reviewer-name">전문가 이름·소속</label>
          <input id="reviewer-name" value={reviewerName} onChange={(event) => setReviewerName(event.target.value)} autoComplete="organization-title" />
        </div>
        <fieldset className="rating-field">
          <legend className="field-label">상담 품질 평가</legend>
          <div className="star-rating">
            {[1, 2, 3, 4, 5].map((value) => (
              <button
                key={value}
                type="button"
                aria-label={`5점 중 ${value}점`}
                aria-pressed={rating === value}
                onClick={() => setRating(value)}
              >
                <Star className={value <= rating ? "is-filled" : ""} aria-hidden="true" />
              </button>
            ))}
            <span>{rating}점</span>
          </div>
        </fieldset>
      </div>

      <label className="field-label" htmlFor="review-feedback">보완 의견</label>
      <textarea
        id="review-feedback"
        value={feedbackText}
        onChange={(event) => setFeedbackText(event.target.value)}
        placeholder="추가로 확인할 증거, 수정할 법령, 보호자에게 전달할 주의사항을 기록하세요."
      />

      <div className="form-actions">
        <p className="form-status" role="status" aria-live="polite">{message}</p>
        <button type="button" className="secondary-button" disabled={saving} onClick={() => save("draft")}>
          <Save aria-hidden="true" /> 초안 저장
        </button>
        <button type="button" className="primary-button" disabled={saving} onClick={() => save("verified")}>
          <UserCheck aria-hidden="true" /> 확인 완료
        </button>
      </div>
    </section>
  );
}
