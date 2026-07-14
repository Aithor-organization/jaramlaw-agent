import React, { useState } from "react";
import { UserCheck, Star, Save, CheckCircle, Edit, AlertCircle } from "lucide-react";
import { ConsultationSession, ExpertFeedback } from "../types";

interface ExpertReviewPanelProps {
  session: ConsultationSession;
  language: "ko" | "en";
  onFeedbackSaved: (updatedSession: ConsultationSession) => void;
}

export const ExpertReviewPanel: React.FC<ExpertReviewPanelProps> = ({ session, language, onFeedbackSaved }) => {
  const isEn = language === "en";

  const [reviewerName, setReviewerName] = useState(session.expertFeedback?.reviewerName || "");
  const [feedbackText, setFeedbackText] = useState(session.expertFeedback?.feedbackText || "");
  const [rating, setRating] = useState<number>(session.expertFeedback?.rating || 5);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");

  const handleSaveReview = async (status: "draft" | "verified") => {
    if (!reviewerName || !feedbackText) {
      setSaveMessage(isEn ? "Please fill name & feedback comment first" : "전문가 이름과 검토 의견을 모두 입력해주세요.");
      return;
    }

    setSaving(true);
    setSaveMessage("");

    try {
      const response = await fetch(`/api/history/${session.id}/expert-review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reviewerName,
          feedbackText,
          rating,
          status
        })
      });

      const data = await response.json();
      if (data.status === "success") {
        setSaveMessage(isEn ? "Expert review saved successfully." : "전문가 검토가 저장되었습니다.");
        onFeedbackSaved(data.data);
      } else {
        setSaveMessage(data.message || (isEn ? "Failed saving review." : "검토 저장에 실패했습니다."));
      }
    } catch (err) {
      setSaveMessage(isEn ? "Error synchronizing review" : "검토 저장 중 서버 통신 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border border-[#d7e4de] dark:border-slate-800 rounded-2xl bg-white/70 dark:bg-slate-900/40 p-5 mt-6" id="expert-assistance-loop">
      {/* Existing Verified Review Seal */}
      {session.expertFeedback && session.expertFeedback.status === "verified" ? (
        <div className="bg-emerald-50/50 dark:bg-emerald-950/15 border border-emerald-100 dark:border-emerald-900/50 rounded-xl p-4 space-y-3 relative overflow-hidden">
          {/* Visual absolute watermark seal background */}
          <div className="absolute right-[-10px] bottom-[-15px] opacity-10 select-none pointer-events-none transform rotate-12">
            <CheckCircle className="w-32 h-32 text-emerald-800" />
          </div>

          <div className="flex justify-between items-start gap-4">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center bg-emerald-700 text-white rounded-full p-1.5 shadow">
                <UserCheck className="w-4.5 h-4.5" />
              </span>
              <div>
                <span className="text-[10px] font-bold text-emerald-700 block tracking-wider uppercase">
                  {isEn ? "Legal Board Verified Audit" : "전문가 검토 완료"}
                </span>
                <h4 className="text-sm font-bold text-slate-800 dark:text-slate-100">
                  {session.expertFeedback.reviewerName}
                </h4>
              </div>
            </div>

            {/* Stars rendering */}
            <div className="flex gap-0.5">
              {[1, 2, 3, 4, 5].map((s) => (
                <Star
                  key={s}
                  className={`w-3.5 h-3.5 ${
                    s <= (session.expertFeedback?.rating || 5)
                      ? "fill-amber-400 text-amber-400"
                      : "text-slate-300 dark:text-slate-700"
                  }`}
                />
              ))}
            </div>
          </div>

          <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed pl-8">
            "{session.expertFeedback.feedbackText}"
          </p>

          <div className="flex justify-between items-center text-[10px] text-slate-600 dark:text-slate-500 pl-8 font-mono">
            <span>{isEn ? "Audit Locked" : "검토 서명 완료"}</span>
            <span>{new Date(session.expertFeedback.reviewedAt).toLocaleString()}</span>
          </div>
        </div>
      ) : null}

      {/* Editor Loop Form: Always render to allow modifications or signing */}
      <div className="space-y-4 mt-4">
        <div className="border-t border-slate-200/60 dark:border-slate-800 pt-4">
          <span className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <Edit className="w-4 h-4 text-teal-600" />
            {isEn ? "AI-Assisted Legal Expert Feedback Loop" : "전문가 검토 및 보완 메모"}
          </span>
          <p className="text-[10px] text-slate-600 mt-0.5">
            {isEn
              ? "Modify context, overwrite references, and authorize the legal advice correctness"
              : "전문가가 상담 내용을 보완하고 최종 확인 여부를 기록합니다."}
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Reviewer signature info */}
          <div className="space-y-1.5">
            <span className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest block">
              {isEn ? "Legal Expert Official Signature" : "전문가 이름/소속"}
            </span>
            <input
              type="text"
              className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-1.5 text-xs focus:ring-1 focus:ring-teal-500 outline-none"
              value={reviewerName}
              onChange={(e) => setReviewerName(e.target.value)}
              placeholder={isEn ? "e.g., Jane Cooper, Lead Partner Lawyer" : "예시: 김재윤 법무법인 가온 대표 변호사"}
            />
          </div>

          {/* Rating selector */}
          <div className="space-y-1.5">
            <span className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest block">
              {isEn ? "AI Advice Quality Assessment Rating" : "상담 품질 평가"}
            </span>
            <div className="flex gap-2 items-center h-8">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onClick={() => setRating(star)}
                  className="p-1 hover:scale-115 transition-transform cursor-pointer"
                >
                  <Star
                    className={`w-5 h-5 ${
                      star <= rating ? "fill-amber-400 text-amber-400" : "text-slate-300 dark:text-slate-700"
                    }`}
                  />
                </button>
              ))}
              <span className="text-xs font-bold text-amber-700 font-mono ml-2">({rating}.0 / 5.0)</span>
            </div>
          </div>
        </div>

        {/* Written evaluation */}
        <div className="space-y-1.5">
          <span className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-widest block">
            {isEn ? "Expert Review Commentary & Addendum Codes" : "보완 의견"}
          </span>
          <textarea
            className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 text-xs text-slate-800 dark:text-slate-100 focus:ring-1 focus:ring-teal-500 outline-none leading-relaxed"
            rows={3}
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder={isEn ? "Add addendums, correct legal codes or mention local litigation policies..." : "보완할 법령, 추가로 확인할 증거, 보호자에게 전달할 주의사항을 적어주세요."}
          />
        </div>

        {/* Actions panel */}
        <div className="flex flex-col sm:flex-row justify-between items-center bg-white dark:bg-slate-950/60 rounded-xl px-4 py-3 border border-slate-200/50 dark:border-slate-850 gap-4">
          <div className="flex items-center gap-1.5 text-slate-600 font-mono text-[10px]">
            <Star className="w-3.5 h-3.5 fill-slate-300" />
            <span>{isEn ? "Revision index" : "검토 상태"}: {session.expertFeedback ? "저장됨" : "대기"}</span>
          </div>

          <div className="flex gap-2 w-full sm:w-auto">
            <button
              onClick={() => handleSaveReview("verified")}
              disabled={saving}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-emerald-700 rounded-lg hover:bg-emerald-800 disabled:bg-slate-200 disabled:text-slate-700 disabled:border-slate-300 hover:shadow transition cursor-pointer"
              id="expert-verify-author-button"
            >
              <Save className="w-3.5 h-3.5" />
              {isEn ? "AUTHORIZE & PUBLISH SEAL" : "전문가 검토 저장"}
            </button>
          </div>
        </div>

        {/* Dynamic status feedback msg */}
        {saveMessage && (
          <div className="flex items-center gap-1.5 text-xs px-3 py-2 border rounded-lg bg-blue-50/50 border-blue-250 text-blue-800 dark:bg-blue-900/10 dark:border-blue-900/40 dark:text-blue-300">
            <AlertCircle className="w-4 h-4" />
            <span>{saveMessage}</span>
          </div>
        )}
      </div>
    </div>
  );
};
