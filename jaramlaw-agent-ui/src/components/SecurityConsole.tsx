import { useEffect, useState } from "react";
import { KeyRound, LockKeyhole, RefreshCw, ShieldCheck } from "lucide-react";
import { apiFetch, readApiError } from "../api";
import type { CryptoLog } from "../types";

export function SecurityConsole({ onUnauthorized }: { onUnauthorized?: () => void }) {
  const [plainText, setPlainText] = useState("민감정보가 없는 테스트 문장");
  const [cipherText, setCipherText] = useState("");
  const [decryptedText, setDecryptedText] = useState("");
  const [keyPersistence, setKeyPersistence] = useState<"configured" | "process-only">("process-only");
  const [logs, setLogs] = useState<CryptoLog[]>([]);
  const [status, setStatus] = useState("이 도구는 암호화 연결 상태를 확인하기 위한 운영자용 샌드박스입니다.");
  const [busy, setBusy] = useState(false);

  const handleUnauthorized = () => {
    onUnauthorized?.();
    setStatus("운영자 인증이 필요합니다.");
  };

  const loadLogs = async () => {
    const response = await apiFetch("/api/security-logs");
    if (response.status === 401) return handleUnauthorized();
    if (!response.ok) return setStatus(await readApiError(response, "보안 로그를 불러오지 못했습니다."));
    const payload = await response.json();
    setLogs(payload.logs || []);
  };

  useEffect(() => { void loadLogs(); }, []);

  const encrypt = async () => {
    if (!plainText.trim()) return;
    setBusy(true);
    setStatus("AES-256-GCM으로 테스트 데이터를 암호화하고 있습니다.");
    try {
      const response = await apiFetch("/api/encrypt-demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "encrypt", text: plainText }),
      });
      if (!response.ok) throw new Error(await readApiError(response, "암호화하지 못했습니다."));
      const payload = await response.json();
      setCipherText(payload.cipherText);
      setDecryptedText("");
      setKeyPersistence(payload.key_persistence === "configured" ? "configured" : "process-only");
      setStatus("인증 암호화가 완료되었습니다. 암호문 변조 시 복호화가 거부됩니다.");
      await loadLogs();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "암호화 중 오류가 발생했습니다.");
    } finally {
      setBusy(false);
    }
  };

  const decrypt = async () => {
    if (!cipherText) return;
    setBusy(true);
    setStatus("암호문 무결성을 확인하고 복호화하고 있습니다.");
    try {
      const response = await apiFetch("/api/encrypt-demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "decrypt", cipher: cipherText }),
      });
      if (!response.ok) throw new Error(await readApiError(response, "복호화하지 못했습니다."));
      const payload = await response.json();
      setDecryptedText(payload.decrypted);
      setStatus("암호문 무결성 확인과 복호화가 완료되었습니다.");
      await loadLogs();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "복호화 중 오류가 발생했습니다.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="admin-stack" aria-labelledby="security-console-title">
      <div className="panel">
        <div className="section-title">
          <div><p className="eyebrow">보안 검증</p><h2 id="security-console-title">AES-256-GCM 샌드박스</h2></div>
          <span className="status-badge tone-good"><ShieldCheck aria-hidden="true" /> 인증 암호화</span>
        </div>

        <div className="trust-note">
          <KeyRound aria-hidden="true" />
          {keyPersistence === "configured"
            ? "환경변수로 설정된 서버 키를 사용합니다. 실제 운영 키 관리는 별도 KMS가 필요합니다."
            : "현재 키는 서버 프로세스가 종료되면 사라집니다. 운영 저장용이 아닌 기능 검증 모드입니다."}
        </div>

        <label className="field-label" htmlFor="crypto-plain">테스트 문장</label>
        <textarea id="crypto-plain" value={plainText} onChange={(event) => setPlainText(event.target.value)} />
        <div className="button-row">
          <button type="button" className="primary-button" onClick={encrypt} disabled={busy || !plainText.trim()}>
            <LockKeyhole aria-hidden="true" /> 암호화
          </button>
          <button type="button" className="secondary-button" onClick={decrypt} disabled={busy || !cipherText}>
            <RefreshCw aria-hidden="true" /> 무결성 확인·복호화
          </button>
        </div>

        <label className="field-label" htmlFor="crypto-cipher">암호화 봉투</label>
        <textarea id="crypto-cipher" className="mono-output" value={cipherText} readOnly />
        {decryptedText && <div className="decrypted-output"><strong>복호화 결과</strong><p>{decryptedText}</p></div>}
        <p className="form-status" role="status" aria-live="polite">{status}</p>
      </div>

      <div className="panel">
        <div className="section-title">
          <div><p className="eyebrow">감사 추적</p><h2>최근 보안 이벤트</h2></div>
          <button type="button" className="icon-button" aria-label="보안 로그 새로고침" onClick={() => void loadLogs()}>
            <RefreshCw aria-hidden="true" />
          </button>
        </div>
        <div className="audit-list">
          {logs.slice(0, 12).map((log) => (
            <div className="audit-row" key={log.id}>
              <span className="status-dot" aria-hidden="true" />
              <div><strong>{log.type.replaceAll("_", " ")}</strong><small>{log.details}</small></div>
              <time dateTime={log.timestamp}>{new Date(log.timestamp).toLocaleString("ko-KR")}</time>
            </div>
          ))}
          {!logs.length && <p className="empty-copy">표시할 보안 이벤트가 없습니다.</p>}
        </div>
      </div>
    </section>
  );
}
