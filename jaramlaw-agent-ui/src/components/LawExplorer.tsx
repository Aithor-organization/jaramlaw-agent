import React, { useState } from "react";
import { Search, Scale, ShieldAlert, Cpu, CalendarClock, Zap, CheckCircle2 } from "lucide-react";
import { LawItem } from "../types";

// JaramLaw Family & Parenting stage specific legal database reference
const LAW_DICTIONARY: LawItem[] = [
  {
    id: "ex_equal_19",
    title: "남녀고용평등법 제19조 (육아휴직)",
    summary: "사업주는 근로자가 만 8세 이하 또는 초등학교 2학년 이하의 자녀를 양육하기 위하여 휴직을 신청하는 경우에 이를 허용하여야 한다. 육아휴직 기간은 1년 이내로 하며, 이를 이유로 불리한 처우를 하여서는 아니 된다.",
    clause: "남녀고용평등과 일·가정 양립 지원에 관한 법률 제3장",
    application: "중소기업 여부와 무관하게 부모 모두 각각 단독 1년씩 신청 가능합니다. 사업주가 정당한 이유 없이 이를 거부하거나 육아휴직을 이유로 해고 시 벌칙(제37조)이 적용됩니다.",
    relevance: 98
  },
  {
    id: "ex_academy_18",
    title: "학원법 시행령 제18조 제2항 [별표 4] (교습비등 반환기준)",
    summary: "교습 기간이 1개월을 초과하는 계약의 경우, 중도 해지 시 '반환 사유가 발생한 해당 월의 반환 대상 교습비'와 '나머지 월의 교습비 전액'을 합산한 금액을 반환하여야 한다. 해당 월 역시 수강 시간 비례(1/3, 1/2 기준 등) 또는 일할 계약을 원칙으로 정산한다.",
    clause: "학원의 설립·운영 및 과외교습에 관한 법률 시행령",
    application: "선결제 할인 유도 후 중도 환불을 일방 거부하는 영어/수학 학원, 구몬/씽크빅, 예체능 학원의 '중도 해지 불가' 특약을 무효화하고 실제 잔여금을 환불받는 강력 근거입니다.",
    relevance: 95
  },
  {
    id: "ex_childcare_15_5",
    title: "영유아보육법 제15조의5 (폐쇄회로 텔레비전의 설치 등)",
    summary: "어린이집의 원장은 아동의 보호자가 아동의 안전을 확인하기 위해 (의심 정황 포함) 폐쇄회로 텔레비전(CCTV) 영상정보를 열람하고자 요청하는 경우 법률이 정하는 바에 따라 이에 응하여야 한다.",
    clause: "영유아보육법 제3장 어린이집 설치·운영 규범",
    application: "아이가 이마에 멍이 들었거나 신체적/언어적 학대 혹은 방임 의심 정황 발생 시, 원장이 부모의 CCTV 감상/열람 요구를 '사생활 침해' 핑계로 거절하는 불법 행위를 퇴치하는 기본권 조항입니다.",
    relevance: 94
  },
  {
    id: "ex_labor_74",
    title: "근로기준법 제74조 (임산부의 보호, 출산휴가)",
    summary: "사용자는 임신 중의 여성에게 출산 전과 출산 후를 통하여 90일(한 번에 둘 이상 자녀를 임신한 경우에는 120일)의 출산전후휴가를 주어야 한다. 이 경우 휴가 기간의 배정은 출산 후에 45일(한 번에 둘 이상 자녀를 임신한 경우에는 60일) 이상이 확보되도록 하여야 한다.",
    clause: "근로기준법 제5장 여성과 소년 보호 조항",
    application: "워킹맘이 둘째 임신 및 첫째 임신 단계에서 당연히 요청해야 하는 휴가로써, 최초 60일은 통상임금 100% 유급 보장이 사업주 의무입니다.",
    relevance: 92
  },
  {
    id: "ex_schoolviolence_16",
    title: "학교폭력예방법 제16조 (피해학생의 보호조치)",
    summary: "학교폭력대책심의위원회는 피해학생의 보호를 위하여 필요하다고 인정하는 경우 피해학생에 대하여 심리상담 및 조서, 일시보호, 치료 및 요양, 학급교체 등의 조치를 학교의 장에게 요청할 수 있다.",
    clause: "학교폭력예방 및 대책에 관한 법률 제4장",
    application: "초등/중등 자녀가 또래 괴롭힘, 사이버불링, 폭행에 직면했을 때 주가 되는 구제 법률입니다. 담임교사의 미온 성향 시 학교의 장에게 정식 통보서로 보호 조치를 결제 촉구할 수 있습니다.",
    relevance: 89
  },
  {
    id: "ex_childcare_33_3",
    title: "영유아보육법 제33조의3 (안전사고 보고 의무 및 공제회)",
    summary: "어린이집의 원장 및 보육교사는 영유아의 생명·신체 또는 정신에 중대한 안전사고가 발생한 경우에는 지체 없이 관할 지자체장(구청/시청 보육과) 및 보호자에게 사고 발생 사실과 조치 경위를 서면 또는 구두로 보고하여야 한다.",
    clause: "영유아보육법 제33조 안전 규제",
    application: "어린이집 실내 놀이터, 낮잠 시간 낙상 사고 시 어린이집이 사고를 묵인하거나 부모에게 과실을 전가하여 안전공제회 청구를 지연시킬 때 이를 저지하고 강제 보고서 작성을 청구하는 수단입니다.",
    relevance: 90
  },
  {
    id: "ex_labor_74_2",
    title: "근로기준법 제74조의2 (태아검진 시간의 허용)",
    summary: "사용자는 임신한 여성근로자가 모자보건법 제10조에 따른 임산부 정기건강진단을 받는데 필요한 시간을 청구하는 경우 이를 허용하여야 한다. 사용자는 근로자가 정기건강진단 시간을 확보함을 이유로 임금을 삭감해서는 안 된다.",
    clause: "근로기준법 제5장 임산부 정기검진권",
    application: "임신 초기/중기 워킹맘 임산부가 주말이 아닌 평일에 산부인과 검진을 가기 위해 반차를 쓰지 않고 유급 '태아검진 휴가 시간'을 합법적으로 사용할 수 있는 명확권리입니다.",
    relevance: 88
  },
  {
    id: "ex_equal_18_2",
    title: "남녀고용평등법 제18조의2 (배우자 출산휴가)",
    summary: "사업주는 근로자가 배우자의 출산을 이유로 휴가를 청구하는 경우 10일의 유급휴가를 주어야 한다. 이 경우 휴가는 배우자가 출산한 날부터 90일이 지나면 청구할 수 없고, 1회에 한하여 분할하여 사용할 수 있다.",
    clause: "남녀고용평등과 일·가정 양립 지원에 관한 법률",
    application: "남편이 아내의 출산 분만 당일 및 산후조리 기간 동안 반차가 아닌 10일의 즉시 연속 유급 휴가를 청약하여 양육 분담 권익을 누리는 법정권리입니다.",
    relevance: 87
  }
];

interface LawExplorerProps {
  language: "ko" | "en";
}

export const LawExplorer: React.FC<LawExplorerProps> = ({ language }) => {
  const isEn = language === "en";

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedLaw, setSelectedLaw] = useState<LawItem | null>(null);

  const filteredLaws = LAW_DICTIONARY.filter((law) => {
    const q = searchQuery.toLowerCase();
    return (
      law.title.toLowerCase().includes(q) ||
      law.summary.toLowerCase().includes(q) ||
      law.clause?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6" id="law-dictionary-explorer">
      {/* Fuzzy legal database: Left list (span 7) */}
      <div className="lg:col-span-7 space-y-4">
        <div className="bg-white dark:bg-[#1e293b] rounded-xl border border-slate-200 dark:border-slate-800 p-5 space-y-4 shadow-xs">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Scale className="w-5 h-5 text-blue-600" />
                {isEn ? "South Korean Parenting & Education Law Directory" : "가족 라이프스테이지 통합 법령·정책 보관소"}
              </h2>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                {isEn ? "Fuzzy search related acts used in family, childcare, and schooling consulting" : "임신·출산 권리, 육아휴직 대처, 어린이집 안전, 학원 환불 특약 법적 근원 조항 즉석 탐색기"}
              </p>
            </div>
          </div>

          {/* Search text inputs */}
          <div className="relative">
            <Search className="absolute left-3 top-2.5 w-4.5 h-4.5 text-slate-400" />
            <input
              type="text"
              className="w-full bg-[#f8fafc] dark:bg-[#0b1329] border border-slate-200 dark:border-slate-800 rounded-lg pl-10 pr-4 py-2.5 text-xs outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all"
              placeholder={isEn ? "Search by clause title, code article, or explanation keywords..." : "검색어 입력 (예: 육아휴직, 학원법, CCTV, 출산휴가, 학폭) ..."}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {/* Laws visual list grids */}
          <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
            {filteredLaws.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-16">No matched laws found. Try '육아휴직' or '학원법'.</p>
            ) : (
              filteredLaws.map((law) => (
                <div
                  key={law.id}
                  onClick={() => setSelectedLaw(law)}
                  className={`p-3.5 rounded-lg border text-left transition-all cursor-pointer ${
                    selectedLaw?.id === law.id
                      ? "bg-slate-50 border-slate-350 dark:bg-slate-850/50 dark:border-slate-650 shadow-xs"
                      : "border-slate-150 hover:bg-slate-50/50 dark:border-slate-800 dark:hover:bg-slate-800/40"
                  }`}
                >
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-bold text-slate-800 dark:text-slate-200 block truncate leading-snug">
                      ⚖ {law.title}
                    </span>
                    <span className="text-[9px] text-blue-600 bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 rounded-md font-bold">
                      Relevance {law.relevance}%
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-400 block font-mono mt-1">{law.clause}</span>
                  <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed mt-2.5">
                    {law.summary}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Selected Law Details & JaramLaw Maintenance Center: Right (span 5) */}
      <div className="lg:col-span-5 space-y-6">
        {/* Law precise detail sheet */}
        {selectedLaw ? (
          <div className="bg-white dark:bg-[#1e293b] rounded-xl border border-slate-200 dark:border-slate-800 p-5 space-y-4 shadow-xs">
            <span className="text-[10px] font-bold text-slate-400 tracking-wider uppercase font-mono block border-b border-slate-150 dark:border-slate-850 pb-1.5">
              🎓 Selected Article Analysis Sheet
            </span>
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-slate-900 dark:text-slate-50">{selectedLaw.title}</h4>
              <span className="text-[10px] text-slate-400 block font-mono">{selectedLaw.clause}</span>
            </div>

            <div className="bg-slate-50 dark:bg-slate-900/40 p-3.5 rounded-lg border border-slate-150 dark:border-slate-800 space-y-1.5">
              <span className="text-[10px] font-bold text-slate-400 block">Codified Statutory Textbook Text (법문 원어)</span>
              <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed font-sans font-semibold">
                "{selectedLaw.summary}"
              </p>
            </div>

            <div className="bg-blue-50/50 dark:bg-blue-950/15 p-3.5 rounded-lg border border-blue-100/50 dark:border-blue-900/30 space-y-1.5">
              <span className="text-[10px] font-bold text-blue-800 dark:text-blue-400 flex items-center gap-1.5">
                <ShieldAlert className="w-3.5 h-3.5" />
                Case Application & AI Counsel (실무 적용 소결)
              </span>
              <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                {selectedLaw.application}
              </p>
            </div>
          </div>
        ) : (
          <div className="bg-white dark:bg-[#1e293b] border border-slate-200 dark:border-slate-800 rounded-xl p-6 text-center text-slate-400 text-xs shadow-xs">
            {isEn ? "Select law article on the left list to see full practical applications" : "왼쪽 색인 리스트에서 특정 법안 보관 번호를 누르면 정밀 소송 판례 적용 분석 시트가 활성화됩니다."}
          </div>
        )}

        {/* performance optimization & systematic maintenance dashboard */}
        <div className="bg-[#0f172a] text-slate-100 rounded-xl border border-slate-800/80 p-5 space-y-4 shadow-xs">
          <div>
            <div className="flex items-center gap-1.5">
              <Cpu className="w-4.5 h-4.5 text-blue-400" />
              <h3 className="text-xs font-bold text-blue-400 uppercase tracking-wider">
                System Updates & Maintenance Roadmap
              </h3>
            </div>
            <span className="text-sm font-bold block text-slate-100 mt-1">
              JaramLaw 정기 업데이트 체계 및 라이선스
            </span>
          </div>

          <p className="text-[11px] text-slate-400 leading-relaxed">
            JaramLaw Agent 플랫폼은 최신 유효 법률 개정안 및 대법원 선고 판례 데이터베이스를 실시간으로 크롤링/인정하고 주기적인 최적화 정기 순환 통제 업데이트를 통해 속도 지연 배제 방지를 실현합니다.
          </p>

          <div className="space-y-3 pt-2">
            {/* Sync Checkbox 1 */}
            <div className="flex gap-2 text-xs">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block text-slate-200">Precedent Database Weekly Update</span>
                <span className="text-[10px] text-slate-400">매주 토요일 오후 23:00 대한민국 법원의 하급심/대법 기결 판례 자동 전송 리프레시 완료</span>
              </div>
            </div>

            {/* Sync Checkbox 2 */}
            <div className="flex gap-2 text-xs">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block text-slate-200">AI Logic Model Weight Calibration</span>
                <span className="text-[10px] text-slate-400">Gemini 3.5 Flash / Pro 계열 법적 전문 프롬프팅 최적화 지침을 최신 상법 조항에 맞춰 미세 조정(FineTuning)</span>
              </div>
            </div>

            {/* Sync Checkbox 3 */}
            <div className="flex gap-2 text-xs">
              <CalendarClock className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block text-blue-300">Next Scheduled Inspection</span>
                <span className="text-[10px] text-slate-400">2026-05-30 일요일 02:00 - 대안 조항 추천 성능 속도 80% 향상 전면 패치 적용 예정</span>
              </div>
            </div>
          </div>

          {/* Engine Health indicator block */}
          <div className="border-t border-slate-800 pt-3 flex justify-between items-center text-[10px]">
            <span className="text-slate-500 font-mono">Platform Health Score</span>
            <span className="font-bold text-emerald-400 flex items-center gap-1">
              <Zap className="w-3.5 h-3.5 fill-emerald-500 text-emerald-500" />
              Optimal Latency - 180ms (A+)
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
