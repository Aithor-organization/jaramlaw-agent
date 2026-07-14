import React from "react";
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell
} from "recharts";
import { RiskAnalysis } from "../types";

interface DisputeChartProps {
  analysis: RiskAnalysis;
  language: "ko" | "en";
}

export const DisputeChart: React.FC<DisputeChartProps> = ({ analysis, language }) => {
  const isEn = language === "en";

  // Translate labels based on active language
  const chartData = [
    {
      subject: isEn ? "Contract Ambiguity" : "계약서 모호성",
      score: analysis.contractualAmbiguity,
      fullMark: 100
    },
    {
      subject: isEn ? "Evidence Lack" : "유효 증거 부재율",
      score: 100 - analysis.evidenceStrength, // lower evidence means higher conflict risk
      fullMark: 100
    },
    {
      subject: isEn ? "Precedent Gap" : "판례 공백율",
      score: 100 - analysis.precedentSupport, // lower precedent support means higher risk
      fullMark: 100
    },
    {
      subject: isEn ? "Financial Impact" : "재무적 피해 비중",
      score: analysis.financialImpact,
      fullMark: 100
    }
  ];

  const getScoreColor = (score: number) => {
    if (score >= 70) return "text-red-700 bg-red-50 dark:bg-red-950/25";
    if (score >= 40) return "text-amber-700 bg-amber-50 dark:bg-amber-950/25";
    return "text-emerald-700 bg-emerald-50 dark:bg-emerald-950/25";
  };

  const barData = Object.entries({
    [isEn ? "Contract Ambiguity" : "계약 모호도"]: analysis.contractualAmbiguity,
    [isEn ? "Evidence Strength" : "증거 수집력"]: analysis.evidenceStrength,
    [isEn ? "Precedent Support" : "판례 일치율"]: analysis.precedentSupport,
    [isEn ? "Financial Scale" : "금전 규모율"]: analysis.financialImpact,
  }).map(([key, val]) => ({ name: key, score: val }));

  const COLORS = ["#f87171", "#60a5fa", "#34d399", "#fbbf24"];

  return (
    <div className="space-y-6" id="dispute-probability-analysis">
      {/* Title block */}
      <div className="flex justify-between items-center bg-slate-50 dark:bg-slate-900 px-4 py-3 rounded-lg border border-slate-100 dark:border-slate-800">
        <div>
          <span className="text-xs font-mono text-slate-600 block uppercase tracking-wider">
            {isEn ? "Conflict Forecast Engine" : "분쟁 정밀 계측 엔진 v2.1"}
          </span>
          <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            {isEn ? "Computed Dispute Probability" : "종합 법률 분쟁 가능성"}
          </span>
        </div>
        <div className={`px-3 py-2 rounded-lg text-center font-bold text-lg border ${getScoreColor(analysis.overallScore)}`}>
          {analysis.overallScore}%
        </div>
      </div>

      {/* Numerical breakdown with warning bar */}
      <div className="space-y-4">
        <div>
          <div className="flex justify-between text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
            <span>{isEn ? "Dispute Loss Probability" : "원고 측 소송 및 중재 대립 가능도"}</span>
            <span>{analysis.overallScore}%</span>
          </div>
          <div className="w-full bg-slate-200 dark:bg-slate-800 h-2.5 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ${
                analysis.overallScore >= 70
                  ? "bg-gradient-to-r from-red-500 to-rose-600"
                  : analysis.overallScore >= 40
                  ? "bg-gradient-to-r from-amber-400 to-orange-500"
                  : "bg-gradient-to-r from-emerald-400 to-teal-500"
              }`}
              style={{ width: `${analysis.overallScore}%` }}
            />
          </div>
        </div>

        <p className="text-xs text-slate-500 leading-relaxed bg-slate-50 dark:bg-slate-900 p-2.5 rounded border border-slate-100 dark:border-slate-800">
          <strong>{isEn ? "AI Risk Reason: " : "AI 소송 소견: "}</strong>
          {analysis.riskReason}
        </p>
      </div>

      {/* Grid layouts for Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Radar Map of Factors */}
        <div className="border border-slate-100 dark:border-slate-800 rounded-xl p-3 bg-white dark:bg-slate-900/50 flex flex-col items-center">
          <span className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-2">
            {isEn ? "1. Litigious Risk Topology" : "1. 잠재 위험 위상 위상도 (Radar)"}
          </span>
          <div className="w-full h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="70%" data={chartData}>
                <PolarGrid stroke="#e2e8f0" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: "#64748b", fontSize: 10 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 8 }} />
                <Radar
                  name="Risk Coefficient"
                  dataKey="score"
                  stroke="#3b82f6"
                  fill="#3b82f6"
                  fillOpacity={0.25}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Bar breakdown of Metrics */}
        <div className="border border-slate-100 dark:border-slate-800 rounded-xl p-3 bg-white dark:bg-slate-900/50 flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-600 dark:text-slate-400 mb-2 block">
            {isEn ? "2. Specific Defense Capabilities" : "2. 세부 입증 인프라 평가 (Bar)"}
          </span>
          <div className="w-full h-[180px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fill: "#64748b", fontSize: 9 }} />
                <YAxis domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 8 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1e293b",
                    borderColor: "#334155",
                    borderRadius: "8px",
                    color: "#f8fafc",
                    fontSize: "11px"
                  }}
                />
                <Bar dataKey="score" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={24}>
                  {barData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[10px] text-slate-600 mt-2 text-center">
            {isEn ? "*Higher Evidence & Precedent scores reduce overall litigation risk" : "*유효 증거 수집력 및 판례 일치율이 높을수록 최종 리스크가 하락 조정됩니다."}
          </p>
        </div>
      </div>

      {/* Advisory recommendations list */}
      <div className="bg-amber-50/50 dark:bg-amber-950/10 border border-amber-100 dark:border-amber-900/50 rounded-xl p-4 space-y-2.5">
        <span className="text-xs font-bold text-amber-800 dark:text-amber-400 flex items-center gap-1.5 uppercase tracking-wider">
          💡 {isEn ? "Immediate Tactical Actions" : "법리적 방어 즉각 조치사항"}
        </span>
        <ul className="space-y-1.5 text-xs text-slate-700 dark:text-slate-300">
          {analysis.recommendations.map((rec, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-amber-700 font-bold font-mono select-none flex-shrink-0">[{i+1}]</span>
              <span className="leading-relaxed">{rec}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
