import React, { useState, useEffect } from "react";
import { FileText, Upload, RefreshCw, AlertTriangle, ShieldCheck, CheckSquare, Plus } from "lucide-react";
import { DocSummary } from "../types";

interface DocumentSummarizerProps {
  language: "ko" | "en";
}

export const DocumentSummarizer: React.FC<DocumentSummarizerProps> = ({ language }) => {
  const isEn = language === "en";

  const [customText, setCustomText] = useState("");
  const [docTitle, setDocTitle] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [documents, setDocuments] = useState<DocSummary[]>([]);
  const [activeDoc, setActiveDoc] = useState<DocSummary | null>(null);

  // Preloaded templates for fast user testing
  const TEMPLATES = [
    {
      title: isEn ? "Private Academy Tuition Refund Request.txt" : "학원 수강료 중도 해지 환불 요청 서한.txt",
      text: `[학원 과목 교습비 중도 해지 청구 통보 서한]
수신: 마포구 스파르타 영어학원 원장님
발신: 학부모 김지원 (수강생: 김하람 / 초1)
제목: 학원 수강료 중도 해지 및 잔여 교습비 환불 청구

본 수강생은 귀 학원의 영어 종합 과정에 대해 3개월분 총 1,050,000원을 선납 기결제하였습니다. 개인 사정상 1개월 4일이 경과한 시점에서 유선으로 중도 해지를 요청하였으나, 귀 학원은 '선결제 할인 및 내부 규정상 3개월 미만은 환불 불가'를 이유로 정산을 거절하고 있습니다.
학원의 설립·운영 및 과외교습에 관한 법률 시행령 제18조 제2항 [별표 4]에 정한 바에 의하여, 1개월 초과 계약의 중도 해지 시 경과하지 아니한 부분에 대한 교습비를 일할 적정 부과 후 즉시 반환할 것을 청구합니다. 정당한 사유 없는 환불 지연 시 교육지원청 민원 및 소비자원 고발 조치하겠음을 알립니다.`
    },
    {
      title: isEn ? "Care Center CCTV Inspection Request.txt" : "어린이집 안전사고 원인 조사 및 CCTV 열람 요청서.txt",
      text: `[어린이집 폐쇄회로 텔레비전 CCTV 열람 청구서]
수신: 마포 자람 어린이집 원장
신청인: 아동 보호자 김지원 (아동: 김나율 / 24개월)
열람 사유: 영유아 안전 확인 및 사고 경위 파악

상기 아동은 지난 5월 20일 하원 후 이마에 직경 5cm 가량의 심각한 뇌진탕성 타박상 및 멍이 발견되었습니다. 어린이집 측은 '낮잠 시간 후 일어나다 미끄러진 단순 미경미 사고'라고 구두 알림장으로 소명하였으나, 사고 발생 상황에 관한 정밀 경위 및 교사의 보호 의무 소홀 여부 확인을 위해 CCTV 영상정보 열람을 신청합니다.
영유아보육법 제15조의5 및 개인정보보호법 가이드라인에 의거하여, 보호자는 아동의 안전 확인을 목적으로 원내 CCTV 영상정보 열람을 정당히 요구할 수 있으며 원장은 이에 응하여야 합니다. 사생활 침해나 타 아동 노출의 핑계로 열람을 거부하거나 지연할 시 불법으로 처벌될 수 있음을 고지합니다.`
    }
  ];

  const fetchDocs = async () => {
    try {
      const response = await fetch("/api/documents");
      const d = await response.json();
      if (d.status === "success") {
        setDocuments(d.data);
        if (d.data.length > 0 && !activeDoc) {
          setActiveDoc(d.data[0]);
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      setDocTitle(file.name);
      
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          setCustomText(event.target.result as string);
        }
      };
      reader.readAsText(file);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      setDocTitle(file.name);
      
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          setCustomText(event.target.result as string);
        }
      };
      reader.readAsText(file);
    }
  };

  const selectTemplate = (index: number) => {
    setDocTitle(TEMPLATES[index].title);
    setCustomText(TEMPLATES[index].text);
  };

  const triggerAnalysis = async () => {
    if (!customText) return;
    setAnalyzing(true);
    
    try {
      const res = await fetch("/api/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: docTitle || (isEn ? "Manual Upload Contract" : "신규 검토 합의서.txt"),
          content: customText,
          language: language
        })
      });
      const data = await res.json();
      if (data.status === "success") {
        setDocuments((prev) => [data.data, ...prev]);
        setActiveDoc(data.data);
        setCustomText("");
        setDocTitle("");
      }
    } catch (err) {
      console.error("Analysis error", err);
    } finally {
      setAnalyzing(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 70) return "text-emerald-500 bg-emerald-50 dark:bg-emerald-950/20 dark:border-emerald-900/30";
    if (score >= 40) return "text-amber-500 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-900/30";
    return "text-red-500 bg-red-50 dark:bg-red-950/20 dark:border-red-900/30";
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6" id="legal-document-summarizer">
      {/* Selection Left Grid */}
      <div className="lg:col-span-5 space-y-6">
        <div className="bg-white dark:bg-[#1e293b] rounded-xl border border-slate-200 dark:border-slate-800 p-5 space-y-4 shadow-xs">
          <div>
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
              <Upload className="w-4.5 h-4.5 text-blue-600" />
              {isEn ? "Contract/Document Analyzer" : "신규 계약 보증서 분석/업로드"}
            </h3>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {isEn ? "Support drag-and-drop or select preloaded templates to discover toxic clauses" : "계약서 약정 텍스트를 드래그 앤 드롭하거나 서식을 기재해 불합리한 독소 조항을 수사하십시오."}
            </p>
          </div>

          {/* Drag & Drop uploader area */}
          <div
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            className="border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-xl p-6 text-center hover:border-blue-500 hover:bg-slate-50/50 dark:hover:bg-slate-900/20 transition-all cursor-pointer relative"
          >
            <input
              type="file"
              accept=".txt,.doc,.docx"
              onChange={handleFileSelect}
              className="absolute inset-0 opacity-0 cursor-pointer"
            />
            <FileText className="w-8 h-8 text-slate-400 mx-auto mb-2" />
            <span className="text-xs font-bold text-slate-700 dark:text-slate-300 block">
              {docTitle || (isEn ? "Drop txt/doc file here or click" : "원 서식 파일 드래그 또는 수동 파일 첨부")}
            </span>
            <span className="text-[10px] text-slate-400 mt-1 block">
              {isEn ? "Supports .txt up to 10MB" : "텍스트 및 영문/국문 로컬 파일 지원 (최대 10MB)"}
            </span>
          </div>

          {/* Quick template pick list */}
          <div className="space-y-2">
            <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">
              {isEn ? "Quick Selection Preloads" : "전문 예시 계약특약 간편 탐방"}
            </span>
            <div className="grid grid-cols-1 gap-2">
              {TEMPLATES.map((tpl, i) => (
                <button
                  key={i}
                  onClick={() => selectTemplate(i)}
                  className="w-full text-left p-2.5 rounded-lg border border-slate-150 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900 text-xs transition cursor-pointer"
                >
                  <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-0.5 break-all">
                    📄 {tpl.title}
                  </span>
                  <span className="text-[10px] text-slate-400 block truncate">{tpl.text}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Direct Text Pasting Area */}
          <div className="space-y-1.5">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">
              {isEn ? "Paste Custom Agreement Copy Direct" : "약정 특약 수정 입력 (직접 작정)"}
            </span>
            <textarea
              className="w-full bg-[#f8fafc] dark:bg-[#0b1329] border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 text-xs text-slate-800 dark:text-slate-100 font-mono outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all"
              rows={4}
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              placeholder={isEn ? "Paste contract texts here..." : "제3조... 갑은 을에게 손해배상액으로..."}
            />
          </div>

          <button
            onClick={triggerAnalysis}
            disabled={analyzing || !customText}
            className="w-full inline-flex items-center justify-center gap-1.5 py-2.5 text-xs font-bold text-white bg-blue-600 rounded-lg hover:bg-blue-700 hover:shadow-xs disabled:opacity-50 transition cursor-pointer"
            id="run-analysis-button"
          >
            {analyzing ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                {isEn ? "Analyzing via Gemini AI..." : "Gemini AI 정밀 수집/독소 수사 대기..."}
              </>
            ) : (
              <>
                <FileText className="w-3.5 h-3.5" />
                {isEn ? "RUN AI ANALYSIS SHEET" : "AI 독소 조항 완벽 해소 수사"}
              </>
            )}
          </button>
        </div>

        {/* Saved Logs Sidebar list */}
        <div className="bg-white dark:bg-[#1e293b] rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-xs">
          <span className="text-xs font-bold text-slate-500 dark:text-slate-400 block mb-3 uppercase tracking-wider">
            {isEn ? "Historically Audited Invoices" : "분석 완료 서류 이력"}
          </span>
          <div className="space-y-2 h-48 overflow-y-auto pr-1">
            {documents.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-10">No document analyzed yet.</p>
            ) : (
              documents.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => setActiveDoc(doc)}
                  className={`w-full text-left p-3.5 rounded-lg border transition-all cursor-pointer ${
                    activeDoc?.id === doc.id
                      ? "bg-slate-50 border-slate-350 dark:bg-slate-800 dark:border-slate-600 shadow-xs"
                      : "border-slate-150 hover:bg-slate-50/50 dark:border-slate-800 dark:hover:bg-slate-800/40"
                  }`}
                >
                  <span className="text-xs font-bold text-slate-800 dark:text-slate-100 block truncate">
                    💼 {doc.title}
                  </span>
                  <div className="flex justify-between items-center text-[10px] text-slate-400 mt-1 font-mono">
                    <span>{new Date(doc.date).toLocaleDateString()}</span>
                    <span>{(doc.length / 1024).toFixed(2)} KB</span>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Analysis Output Sheet: Right Grid */}
      <div className="lg:col-span-7">
        {activeDoc ? (
          <div className="bg-white dark:bg-[#1e293b] rounded-xl border border-slate-200 dark:border-slate-800 p-6 space-y-6 shadow-xs">
            {/* Active File Title Block */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center pb-4 border-b border-slate-200 dark:border-slate-800 gap-4">
              <div>
                <span className="text-[10px] font-bold text-slate-400 font-mono uppercase tracking-wider block">
                  {isEn ? "Audit Report Invoice" : "서명 특약 독소 조항 평가 진단서"}
                </span>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-50 mt-0.5">
                  📁 {activeDoc.title}
                </h3>
              </div>
              <div className={`px-4 py-2 border rounded-xl flex items-center gap-1.5 font-bold ${getScoreColor(activeDoc.analysisScore || 60)}`}>
                <span className="text-2xl font-mono">{activeDoc.analysisScore || 60}</span>
                <div className="text-left font-sans">
                  <span className="text-[9px] text-slate-400 block tracking-wide uppercase">Safety Score</span>
                  <span className="text-[10px] block">
                    {(activeDoc.analysisScore || 60) >= 70
                      ? (isEn ? "Fair/Equal" : "권익 대칭")
                      : (activeDoc.analysisScore || 60) >= 40
                      ? (isEn ? "Moderate Risk" : "주의 필요")
                      : (isEn ? "Toxic/Biased" : "독소 과다")}
                  </span>
                </div>
              </div>
            </div>

            {/* Overall summary section */}
            <div className="space-y-2">
              <span className="text-xs font-bold text-slate-800 dark:text-slate-350 flex items-center gap-1 border-b border-slate-100 dark:border-slate-800 pb-1.5 uppercase tracking-wide">
                ⚖ {isEn ? "Senior AI Analysis Assessment" : "AI 변론 수석 소견"}
              </span>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed bg-slate-50 dark:bg-slate-900/60 p-3 rounded-xl">
                {activeDoc.overallSummary}
              </p>
            </div>

            {/* Core commitments */}
            <div className="space-y-2">
              <span className="text-xs font-bold text-blue-800 dark:text-blue-400 flex items-center gap-1 uppercase tracking-wide">
                <CheckSquare className="w-4 h-4" />
                {isEn ? "Obligations and Core Understandings" : "약정상 명시된 상대방과의 의무 사항 (이행선언)"}
              </span>
              <ul className="grid grid-cols-1 gap-2">
                {activeDoc.coreArguments.map((arg, idx) => (
                  <li key={idx} className="flex gap-2.5 text-xs text-slate-700 dark:text-slate-300 bg-slate-50/50 dark:bg-slate-900/10 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800">
                    <span className="text-blue-500 font-bold text-xs">[{idx+1}]</span>
                    <span className="leading-relaxed">{arg}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Critical Risks and loopholes */}
            <div className="space-y-2">
              <span className="text-xs font-bold text-rose-800 dark:text-rose-400 flex items-center gap-1 uppercase tracking-wide">
                <AlertTriangle className="w-4 h-4" />
                {isEn ? "Detrimental Loopholes / Toxic Terms" : "합의 독소 리스크 및 불평등 독소 조항"}
              </span>
              <ul className="grid grid-cols-1 gap-2">
                {activeDoc.criticalRisks.map((risk, idx) => (
                  <li key={idx} className="flex gap-2.5 text-xs text-slate-700 dark:text-slate-300 bg-rose-50/35 dark:bg-rose-950/5 p-2.5 rounded-lg border border-rose-100/50 dark:border-rose-900/20">
                    <span className="text-rose-500 font-bold text-xs select-none">⚠️</span>
                    <span className="leading-relaxed">{risk}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Alternate safe provisions */}
            <div className="space-y-2">
              <span className="text-xs font-bold text-emerald-800 dark:text-emerald-400 flex items-center gap-1 bg-emerald-50 dark:bg-emerald-950/15 p-2 rounded-lg border border-emerald-100 dark:border-emerald-900/20 uppercase tracking-wide">
                <ShieldCheck className="w-4.5 h-4.5" />
                {isEn ? "Revised Mitigation Counter-Drafts" : "권익 보호 목적 안전 대안 조항 배합 제안"}
              </span>
              <ul className="grid grid-cols-1 gap-2">
                {activeDoc.actionableSteps.map((step, idx) => (
                  <li key={idx} className="flex gap-2.5 text-xs text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-900/20 p-2.5 rounded-lg border border-slate-150 dark:border-slate-800">
                    <span className="text-emerald-600 font-bold font-mono">[{idx+1}]</span>
                    <span className="leading-relaxed font-sans">{step}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Recommended regulations checklist */}
            {activeDoc.lawChecklist && activeDoc.lawChecklist.length > 0 && (
              <div className="bg-slate-50 dark:bg-slate-900 p-4 rounded-xl border border-slate-150 dark:border-slate-800">
                <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block mb-2">
                  🛡 {isEn ? "Direct Regulatory Precedents" : "대조 연계 민상법/하도급 관련 법령 준거"}
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {activeDoc.lawChecklist.map((law, idx) => (
                    <span key={idx} className="bg-white dark:bg-slate-950 px-2.5 py-1 text-[10px] text-slate-600 dark:text-slate-300 rounded border border-slate-200/50 dark:border-slate-800/80 font-semibold shadow-sm">
                      ⚖ {law}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="border border-slate-150 dark:border-slate-800 rounded-2xl bg-white dark:bg-slate-950 p-12 text-center text-slate-400 flex flex-col justify-center items-center h-full">
            <FileText className="w-12 h-12 text-slate-300 mb-2" />
            <h4 className="font-bold text-slate-700 dark:text-slate-350">
              {isEn ? "No Document Active" : "불러올 진단서가 없습니다."}
            </h4>
            <p className="text-xs text-slate-400 mt-1 max-w-sm">
              {isEn ? "Please upload contract or choose templates on the left sidebar to generate detailed safety report" : "좌측 사이드바에서 약정을 불러오거나 파일을 투입해 정밀 진단을 발급하십시오."}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
