import React, { useState, useEffect } from "react";
import { Lock, Shield, Server, RefreshCw, Key, ArrowRightLeft, Smartphone, CheckCircle, Database } from "lucide-react";
import { CryptoLog } from "../types";

interface SecurityConsoleProps {
  language: "ko" | "en";
}

export const SecurityConsole: React.FC<SecurityConsoleProps> = ({ language }) => {
  const isEn = language === "en";

  const [inputText, setInputText] = useState(
    isEn
      ? "Confidential claim amount $50,000, Client ID: Lee-893"
      : "당사자 개인정보: 이민우(890522-1112222), 정산 연체대금: 50,000,000원"
  );
  const [cipherText, setCipherText] = useState("");
  const [decryptedText, setDecryptedText] = useState("");
  const [encrypting, setEncrypting] = useState(false);
  const [decrypting, setDecrypting] = useState(false);
  const [logs, setLogs] = useState<CryptoLog[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"idle" | "pairing" | "completed">("idle");
  const [activeTab, setActiveTab] = useState<"cipher" | "sync" | "audit">("cipher");

  // Fetch security audit logs
  const fetchLogs = async () => {
    try {
      const response = await fetch("/api/security-logs");
      const d = await response.json();
      if (d.status === "success") {
        setLogs(d.logs);
      }
    } catch (err) {
      console.error("Error fetching cryptology logs", err);
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 8000);
    return () => clearInterval(interval);
  }, []);

  const handleEncrypt = async () => {
    if (!inputText) return;
    setEncrypting(true);
    setDecryptedText("");
    
    // Simulate encryption overhead
    await new Promise((r) => setTimeout(r, 600));

    try {
      const res = await fetch("/api/encrypt-demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: inputText, mode: "encrypt" })
      });
      const data = await res.json();
      if (data.status === "success") {
        setCipherText(data.cipherText);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setEncrypting(false);
      fetchLogs();
    }
  };

  const handleDecrypt = async () => {
    if (!cipherText) return;
    setDecrypting(true);
    
    await new Promise((r) => setTimeout(r, 600));

    try {
      const res = await fetch("/api/encrypt-demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cipher: cipherText, mode: "decrypt" })
      });
      const data = await res.json();
      if (data.status === "success") {
        setDecryptedText(data.decrypted);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setDecrypting(false);
      fetchLogs();
    }
  };

  const handleTriggerSync = async () => {
    setSyncing(true);
    setSyncStatus("pairing");
    
    // Multi-phase challenges
    await new Promise((r) => setTimeout(r, 1000));
    
    try {
      const res = await fetch("/api/sync-cloud", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionIds: ["session_1", "session_2"] })
      });
      const data = await res.json();
      if (data.status === "success") {
        setSyncStatus("completed");
      }
    } catch (err) {
      console.error(err);
      setSyncStatus("idle");
    } finally {
      setSyncing(false);
      fetchLogs();
    }
  };

  const getLogBadge = (type: CryptoLog['type']) => {
    switch (type) {
      case "TLS_HANDSHAKE":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300";
      case "AES_GCM_ENCRYPT":
        return "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300";
      case "AES_GCM_DECRYPT":
        return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300";
      case "KEY_ROTATION":
        return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300";
      default:
        return "bg-slate-100 text-slate-800 dark:bg-slate-900/30";
    }
  };

  return (
    <div className="bg-white dark:bg-slate-950 rounded-2xl border border-slate-150 dark:border-slate-800/80 shadow-md p-6" id="security-cryptography-manager">
      {/* Header and status flags */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center pb-4 border-b border-slate-100 dark:border-slate-800 gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-600" />
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-50">
              {isEn ? "Security & Encryption Control Center" : "보안 암호화 및 다중 동기화 관제장치"}
            </h2>
          </div>
          <p className="text-secondary text-xs mt-1">
            {isEn
              ? "Military-grade end-to-end envelope cryptography and synchronization center"
              : "전송/기록물 전 과정 AES-256-GCM 봉인 및 다차원 단말 동기화 모듈 통제"}
          </p>
        </div>

        {/* Global Security Metrics */}
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400 border border-emerald-200/50">
            <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
            TLS 1.3 Active
          </span>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400 border border-blue-200/50">
            <Lock className="w-3.5 h-3.5" />
            AES-256-GCM
          </span>
        </div>
      </div>

      {/* Internal Navigation Tabs */}
      <div className="flex border-b border-slate-100 dark:border-slate-800 mb-6 mt-4">
        <button
          onClick={() => setActiveTab("cipher")}
          className={`px-4 py-2 text-xs font-semibold border-b-2 mr-2 transition-all ${
            activeTab === "cipher"
              ? "border-blue-600 text-blue-600 dark:text-blue-400"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          {isEn ? "AES Cryptography Sandbox" : "AES-256 암호화 기성검증"}
        </button>
        <button
          onClick={() => setActiveTab("sync")}
          className={`px-4 py-2 text-xs font-semibold border-b-2 mr-2 transition-all ${
            activeTab === "sync"
              ? "border-blue-600 text-blue-600 dark:text-blue-400"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          {isEn ? "Device Synchronization" : "모바일-데스크톱 동기화"}
        </button>
        <button
          onClick={() => setActiveTab("audit")}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition-all ${
            activeTab === "audit"
              ? "border-blue-600 text-blue-600 dark:text-blue-400"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          {isEn ? "Cryptographic Ledger" : "보안 접속 통제 로그상황"}
        </button>
      </div>

      {/* Tab contents 1: Cryptography Engine */}
      {activeTab === "cipher" && (
        <div className="space-y-4">
          <div className="bg-slate-50 dark:bg-slate-900/40 p-4 rounded-xl border border-slate-100 dark:border-slate-800">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-2">
              📋 {isEn ? "Input Plaintext (Client Secret)" : "암호화 대상 원문 입력 (의뢰 기밀 사항)"}
            </span>
            <textarea
              className="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 text-xs text-slate-800 dark:text-slate-100 font-mono focus:ring-1 focus:ring-blue-500 focus:outline-none"
              rows={3}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder={isEn ? "Enter sensitive data to encrypt..." : "비밀 이메일, 정산금, 주민번호 등 기밀 원서 입력..."}
            />
            <div className="flex justify-end mt-2">
              <button
                onClick={handleEncrypt}
                disabled={encrypting || !inputText}
                className="inline-flex items-center gap-1 px-3.5 py-1.5 text-xs font-bold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors cursor-pointer"
              >
                {encrypting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    {isEn ? "Encrypting..." : "암호화 처리 중..."}
                  </>
                ) : (
                  <>
                    <Lock className="w-3.5 h-3.5" />
                    {isEn ? "AES GCM SEAL DATA" : "실시간 봉인 암호화"}
                  </>
                )}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Cipher output */}
            <div className="bg-slate-50 dark:bg-slate-900/40 p-4 rounded-xl border border-slate-100 dark:border-slate-800 flex flex-col justify-between">
              <div>
                <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-2">
                  🔒 {isEn ? "Generated Ciphertext Block (Base64)" : "생성된 암호문 블록 (Base64)"}
                </span>
                <div className="bg-slate-950 p-2.5 rounded font-mono text-[10px] text-purple-400 break-all h-24 overflow-y-auto border border-neutral-800 select-all">
                  {cipherText || (isEn ? "Click encrypt sandboxed data..." : "위 원문을 실시간 암호화하면 여기에 보안 블록이 보관됩니다.")}
                </div>
              </div>
              <div className="flex justify-end mt-3">
                <button
                  onClick={handleDecrypt}
                  disabled={decrypting || !cipherText}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-bold text-purple-700 bg-purple-50 dark:bg-purple-900/20 dark:text-purple-300 rounded-lg hover:bg-purple-100 border border-purple-200/50 disabled:opacity-50 transition-colors cursor-pointer"
                >
                  {decrypting ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      {isEn ? "Decrypting..." : "복호화 작동 중..."}
                    </>
                  ) : (
                    <>
                      <Key className="w-3.5 h-3.5" />
                      {isEn ? "TEST SANDBOX DECRYPT" : "암호화 무결성 복호 검증"}
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Decrypted plaintext recovery verification */}
            <div className="bg-slate-50 dark:bg-slate-900/40 p-4 rounded-xl border border-slate-100 dark:border-slate-800">
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-2">
                🔓 {isEn ? "Decrypted Plaintext Recovery Result" : "복호화 무결 복원 검증 결과"}
              </span>
              <div className="bg-white dark:bg-slate-950 p-3 rounded font-mono text-xs text-slate-800 dark:text-slate-100 h-24 border border-slate-200/60 dark:border-slate-850 overflow-y-auto">
                {decryptedText ? (
                  <div className="space-y-1">
                    <div className="text-[10px] text-emerald-600 font-bold flex items-center gap-1 bg-emerald-50 dark:bg-emerald-900/10 px-1 py-0.5 rounded w-max">
                      <CheckCircle className="w-3 h-3" /> Integrity Check: OK (TLS Verified)
                    </div>
                    <p className="text-slate-800 dark:text-slate-200">{decryptedText}</p>
                  </div>
                ) : (
                  <span className="text-slate-400 text-xs">
                    {isEn ? "Decrypted outcomes will be displayed here..." : "암호화 무결 복원 버튼 클릭 시, 가로챈 복호 텍스트 데이터가 출력됩니다."}
                  </span>
                )}
              </div>
              <p className="text-[9px] text-slate-400 mt-2">
                * {isEn ? "AES-GCM guarantees both confidentiality and ciphertext authenticity (integrity check)." : "AES-GCM은 대칭키 기밀성을 충족시키면서, 일방적 위변조 시 복화 단계에서 자동 무효 조치합니다."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tab contents 2: Desktop-Mobile sync */}
      {activeTab === "sync" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
            {/* Desktop client card */}
            <div className="border border-slate-150 dark:border-slate-800 rounded-xl p-4 bg-slate-50 dark:bg-slate-900/30 text-center flex flex-col items-center">
              <Server className="w-10 h-10 text-blue-600 mb-2" />
              <span className="text-xs font-bold text-slate-800 dark:text-slate-100 block">JaramLaw Desk PC Client</span>
              <span className="text-[10px] text-slate-400 font-mono mt-1">IP: 192.168.1.185 (Secured)</span>
              <span className="inline-flex items-center gap-1 text-[10px] text-emerald-600 bg-emerald-50 dark:bg-emerald-900/15 px-2 py-0.5 rounded-full font-bold mt-3 border border-emerald-100 dark:border-emerald-900/20">
                ● Master Authority
              </span>
            </div>

            {/* Interaction arrows */}
            <div className="flex flex-col items-center justify-center py-2 h-full text-blue-600">
              <ArrowRightLeft className={`w-8 h-8 ${syncing ? "animate-spin" : ""}`} />
              <span className="text-[10px] font-mono text-slate-500 mt-1">
                {syncing ? "Challenge Exchange..." : "Diffie-Hellman Key Agreement"}
              </span>
            </div>

            {/* Mobile terminal card */}
            <div className="border border-slate-150 dark:border-slate-800 rounded-xl p-4 bg-slate-50 dark:bg-slate-900/30 text-center flex flex-col items-center">
              <Smartphone className="w-10 h-10 text-purple-600 mb-2" />
              <span className="text-xs font-bold text-slate-800 dark:text-slate-100 block">Samsung Mobile Terminal</span>
              <span className="text-[10px] text-slate-400 font-mono mt-1">ID: HW-SM-992F (TLS Verified)</span>
              <span className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-bold mt-3 border ${
                syncStatus === "completed"
                  ? "text-emerald-600 bg-emerald-50 border-emerald-100 dark:bg-emerald-900/25"
                  : "text-amber-600 bg-amber-50 border-amber-100 dark:bg-amber-900/25"
              }`}>
                {syncStatus === "completed" ? "✓ Fully Synced" : "● Sync Divergent (4 Pending)"}
              </span>
            </div>
          </div>

          <div className="bg-slate-50 dark:bg-slate-900/40 p-4 rounded-xl border border-slate-100 dark:border-slate-800 flex flex-col md:flex-row justify-between items-center gap-4">
            <div>
              <span className="text-xs font-bold text-slate-800 dark:text-slate-200 block">
                {isEn ? "Run Mutual Desync Reconciliation" : "모바일-PC간 상담 이력 무결 동기화 수행"}
              </span>
              <p className="text-[11px] text-slate-500 max-w-xl leading-relaxed mt-0.5">
                {isEn
                  ? "Forces cryptographically validated reconcile loop. All chats, legal risk graphics, and expert reviews will synchronize to zero discrepancies."
                  : "디바이스 간 상담 이력 데이터의 지문 해시(SHA-256 Signature)를 교환 대조하고, 미비 기록물을 동기화하여 다계정 동시 열람 무장 장벽을 구축합니다."}
              </p>
            </div>
            <button
              onClick={handleTriggerSync}
              disabled={syncing}
              className="inline-flex items-center gap-1 px-4 py-2 text-xs font-bold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 hover:shadow transition"
              id="sync-trigger-button"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${syncing ? "animate-spin" : ""}`} />
              {syncerLabel(syncStatus, syncing, isEn)}
            </button>
          </div>
        </div>
      )}

      {/* Tab contents 3: Security Logs */}
      {activeTab === "audit" && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <span className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1">
              <Database className="w-4 h-4 text-blue-600" />
              {isEn ? "Real-time Access & Encrypted Audit Ledger" : "실시간 백엔드 기밀 연산 및 접근 기록"}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">Auto updates every 8s</span>
          </div>

          <div className="bg-slate-950 rounded-xl p-3 border border-neutral-900 h-64 overflow-y-auto font-mono text-[11px] text-slate-300 space-y-2">
            {logs.length === 0 ? (
              <p className="text-slate-500 text-center py-12">No active logs captured.</p>
            ) : (
              logs.map((log) => (
                <div key={log.id} className="border-b border-neutral-900 pb-1.5 last:border-0 hover:bg-slate-900/20 p-1 rounded">
                  <div className="flex flex-wrap justify-between items-center gap-1.5">
                    <span className="text-[10px] text-slate-500">{new Date(log.timestamp).toLocaleTimeString()}</span>
                    <span className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${getLogBadge(log.type)}`}>
                      {log.type}
                    </span>
                    <span className="text-[10px] text-neutral-400 ml-auto">Payload: {log.payloadSize}</span>
                    <span className="inline-flex items-center px-1.5 py-0.2 text-[9px] font-mono text-emerald-400 border border-emerald-950 bg-emerald-950/40 rounded-full">
                      {log.status}
                    </span>
                  </div>
                  <p className="text-neutral-300 mt-1 pl-4 border-l border-neutral-800 text-[10px] leading-relaxed">
                    ⚙ {log.details}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// Help helper
function syncerLabel(status: "idle" | "pairing" | "completed", syncing: boolean, isEn: boolean): string {
  if (syncing) return isEn ? "Pairing devices..." : "기기 신호 교환 중...";
  if (status === "completed") return isEn ? "Check Harmony Synchronized" : "동기화 완료";
  return isEn ? "FORCE SYNC DEVICES" : "기기 동기화 무결 수행";
}
