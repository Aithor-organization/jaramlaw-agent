/** 부모가 한 줄 남기는 통로.
 *
 * 여태 피드백 경로는 운영자용 전문가 검토 패널뿐이었다 — 정작 쓰는 사람이 말할 데가 없었다.
 * 검증 기간에는 인터뷰보다 이 한 줄에서 더 많이 건진다. 인터뷰는 약속을 잡아야 하지만
 * 이건 막힌 그 순간, 그 화면에서 나온다.
 *
 * 설계 의도:
 * - 별점·객관식을 두지 않는다. "4.2점"은 무엇을 고쳐야 할지 알려주지 않는다.
 * - 로그인을 요구하지 않는다. 가입 전에 막힌 사람의 말이 제일 중요하다.
 * - 연락처는 선택. 답을 받고 싶은 사람만 남긴다.
 */
import { FormEvent, useState } from "react";
import { MessageCircle, X } from "lucide-react";

export function FeedbackButton({ route }: { route: string }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [contact, setContact] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const close = () => {
    setOpen(false);
    setSent(false);
    setText("");
    setContact("");
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || !text.trim()) return;
    setBusy(true);
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim(), route, contact: contact.trim() }),
      });
      setSent(true);
    } catch {
      // 전송 실패도 보낸 것으로 처리한다. 여기서 에러를 띄우면 이미 불편해서 글을 쓴
      // 사람에게 불편을 한 번 더 주는 셈이고, 우리가 잃는 건 피드백 한 건이다.
      setSent(true);
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    // 좁은 화면에서는 CSS가 글자를 감춘다. aria-label을 박아 두지 않으면 그 순간
    // 버튼의 접근성 이름이 사라져 스크린리더에 '버튼'으로만 읽힌다.
    return (
      <button type="button" className="feedback-fab" aria-label="이상한 점 알려주기" onClick={() => setOpen(true)}>
        <MessageCircle aria-hidden="true" />
        <span>이상한 점 알려주기</span>
      </button>
    );
  }

  return (
    <div className="feedback-panel" role="dialog" aria-label="의견 보내기">
      <div className="feedback-head">
        <strong>{sent ? "고맙습니다" : "무엇이 불편하셨나요?"}</strong>
        <button type="button" className="feedback-close" onClick={close} aria-label="닫기">
          <X aria-hidden="true" />
        </button>
      </div>

      {sent ? (
        <p className="feedback-done">
          잘 받았습니다. 알려주신 내용은 바로 확인하겠습니다.
        </p>
      ) : (
        <form onSubmit={submit}>
          <label className="sr-only" htmlFor="feedback-text">의견</label>
          <textarea
            id="feedback-text"
            rows={3}
            maxLength={1000}
            placeholder="틀린 안내, 막힌 화면, 이해 안 되는 말 — 짧게 적어주셔도 됩니다"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <label className="sr-only" htmlFor="feedback-contact">답변받을 연락처 (선택)</label>
          <input
            id="feedback-contact"
            type="text"
            maxLength={120}
            placeholder="답을 받고 싶으시면 이메일 (선택)"
            value={contact}
            onChange={(event) => setContact(event.target.value)}
          />
          <button type="submit" className="btn btn-primary" disabled={busy || !text.trim()}>
            {busy ? "보내는 중" : "보내기"}
          </button>
        </form>
      )}
    </div>
  );
}
