import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FileText, Loader2, Upload } from "lucide-react";
import type { DocSummary } from "../types";

const MAX_TEXT_FILE_BYTES = 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".txt", ".md"];

const TEMPLATES = [
  {
    title: "학원 수강료 환불 요청 초안.txt",
    text: "수신: 학원 담당자\n제목: 수강료 중도 해지 및 잔여 교습비 정산 요청\n\n계약일, 결제 금액, 실제 수강 기간과 해지 요청일을 아래와 같이 정리합니다. 관련 법령의 반환 기준에 따라 정산 내역과 반환 예정일을 서면으로 회신해 주세요.",
  },
  {
    title: "어린이집 사고기록 요청 초안.txt",
    text: "수신: 어린이집 원장\n제목: 안전사고 경위 및 관련 기록 확인 요청\n\n보호자는 사고 발생 일시, 장소, 당시 담당자, 초기 조치와 보호자 통지 경위를 확인하고자 합니다. 가능한 범위에서 사고보고서와 영상 열람 절차를 안내해 주세요.",
  },
];

function fileExtension(name: string): string {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
}

export function DocumentSummarizer() {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [documents, setDocuments] = useState<DocSummary[]>([]);
  const [activeId, setActiveId] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [status, setStatus] = useState("TXT 또는 Markdown 문서를 선택하거나 내용을 직접 붙여 넣으세요.");
  const fileInput = useRef<HTMLInputElement>(null);

  const loadDocuments = useCallback(async () => {
    try {
      const response = await fetch("/api/documents");
      const payload = await response.json();
      if (response.ok && payload.status === "success") {
        setDocuments(payload.data);
        setActiveId((current) => current || payload.data[0]?.id || "");
      }
    } catch {
      setStatus("이전에 분석한 문서 목록을 불러오지 못했습니다.");
    }
  }, []);

  useEffect(() => { void loadDocuments(); }, [loadDocuments]);

  const readTextFile = (file: File) => {
    if (!ACCEPTED_EXTENSIONS.includes(fileExtension(file.name))) {
      setStatus("현재는 .txt와 .md 파일만 지원합니다. Word 문서는 텍스트로 내보낸 뒤 업로드하세요.");
      return;
    }
    if (file.size > MAX_TEXT_FILE_BYTES) {
      setStatus("파일이 1MB를 초과합니다. 필요한 부분만 텍스트로 정리해 주세요.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setTitle(file.name);
      setContent(typeof reader.result === "string" ? reader.result : "");
      setStatus(`${file.name}을 불러왔습니다. 분석 전 개인정보를 다시 확인하세요.`);
    };
    reader.onerror = () => setStatus("파일을 읽지 못했습니다.");
    reader.readAsText(file, "utf-8");
  };

  const analyze = async () => {
    if (!content.trim()) return;
    setAnalyzing(true);
    setStatus("문서에서 쟁점과 다음 행동을 정리하고 있습니다.");
    try {
      const response = await fetch("/api/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title.trim() || "직접 입력 문서", content: content.trim() }),
      });
      const payload = await response.json();
      if (!response.ok || payload.status !== "success") throw new Error(payload.message || "문서 분석에 실패했습니다.");
      setDocuments((current) => [payload.data, ...current.filter((item) => item.id !== payload.data.id)]);
      setActiveId(payload.data.id);
      setContent("");
      setTitle("");
      setStatus("문서 검토가 완료되었습니다. 결과는 법률 자문이 아닌 쟁점 정리입니다.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "문서 분석 중 오류가 발생했습니다.");
    } finally {
      setAnalyzing(false);
    }
  };

  const active = documents.find((item) => item.id === activeId) || null;

  return (
    <section id="panel-documents" className="tool-layout" role="tabpanel" aria-labelledby="tab-documents">
      <div className="panel tool-sidebar">
        <div className="section-title">
          <div>
            <p className="eyebrow">문서 정리</p>
            <h1>내용에서 쟁점 찾기</h1>
          </div>
          <FileText aria-hidden="true" />
        </div>

        <div
          className="upload-zone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            const file = event.dataTransfer.files[0];
            if (file) readTextFile(file);
          }}
        >
          <Upload aria-hidden="true" />
          <strong>텍스트 파일을 놓거나 선택하세요</strong>
          <span>.txt, .md · 최대 1MB</span>
          <button type="button" className="secondary-button" onClick={() => fileInput.current?.click()}>파일 선택</button>
          <input
            ref={fileInput}
            className="visually-hidden"
            type="file"
            accept=".txt,.md,text/plain,text/markdown"
            aria-label="텍스트 문서 선택"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) readTextFile(file);
              event.target.value = "";
            }}
          />
        </div>

        <div className="template-row" aria-label="문서 예시">
          {TEMPLATES.map((template) => (
            <button
              type="button"
              className="text-button"
              key={template.title}
              onClick={() => { setTitle(template.title); setContent(template.text); setStatus("개인정보가 없는 예시 문서를 불러왔습니다."); }}
            >
              {template.title.replace(".txt", "")}
            </button>
          ))}
        </div>

        <label className="field-label" htmlFor="document-title">문서 제목</label>
        <input id="document-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="예: 학원 환불 요청서" />

        <label className="field-label" htmlFor="document-content">검토할 내용</label>
        <textarea
          id="document-content"
          className="document-textarea"
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder="이름, 전화번호, 정확한 주소 등 불필요한 개인정보는 지우고 붙여 넣으세요."
        />

        <button type="button" className="primary-button" disabled={!content.trim() || analyzing} onClick={analyze}>
          {analyzing ? <Loader2 className="spin" aria-hidden="true" /> : <CheckCircle2 aria-hidden="true" />}
          {analyzing ? "검토 중" : "쟁점 정리 시작"}
        </button>
        <p className="form-status" role="status" aria-live="polite">{status}</p>

        {documents.length > 0 && (
          <div className="select-list compact" aria-label="분석한 문서">
            {documents.map((document) => (
              <button
                type="button"
                className={`select-row ${document.id === activeId ? "is-selected" : ""}`}
                key={document.id}
                onClick={() => setActiveId(document.id)}
              >
                <FileText aria-hidden="true" />
                <span><strong>{document.title}</strong><small>{new Date(document.date).toLocaleDateString("ko-KR")}</small></span>
              </button>
            ))}
          </div>
        )}
      </div>

      <article className="panel tool-detail" aria-live="polite">
        {active ? (
          <>
            <div className="section-title">
              <div><p className="eyebrow">검토 결과</p><h2>{active.title}</h2></div>
              <span className="status-badge tone-good">정리 완료</span>
            </div>
            <section className="document-section"><h3>한눈에 보기</h3><p>{active.overallSummary}</p></section>
            <section className="document-section"><h3>핵심 쟁점</h3><ul>{active.coreArguments.map((item) => <li key={item}>{item}</li>)}</ul></section>
            <section className="document-section warning"><h3><AlertTriangle aria-hidden="true" /> 주의할 부분</h3><ul>{active.criticalRisks.map((item) => <li key={item}>{item}</li>)}</ul></section>
            <section className="document-section"><h3>다음 행동</h3><ol>{active.actionableSteps.map((item) => <li key={item}>{item}</li>)}</ol></section>
            <section className="document-section"><h3>함께 확인할 법령</h3><div className="tag-list">{active.lawChecklist.map((item) => <span key={item}>{item}</span>)}</div></section>
            <div className="legal-disclaimer">자동 요약에는 누락이 있을 수 있습니다. 제출 전 원문과 공식 법령을 다시 확인하세요.</div>
          </>
        ) : (
          <div className="empty-state"><FileText aria-hidden="true" /><strong>문서를 분석하면 결과가 여기에 정리됩니다.</strong></div>
        )}
      </article>
    </section>
  );
}
