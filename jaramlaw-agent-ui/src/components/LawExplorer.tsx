import { useEffect, useMemo, useState } from "react";
import { BookOpen, ExternalLink, Info, Search } from "lucide-react";
import type { LawItem } from "../types";

type LawPayload = {
  status: string;
  source: "seed" | "live";
  updated_at: string | null;
  data: LawItem[];
};

function relevanceLabel(value: number): string {
  if (value >= 90) return "높은 관련도";
  if (value >= 75) return "관련 있음";
  return "참고";
}

export function LawExplorer() {
  const [laws, setLaws] = useState<LawItem[]>([]);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [source, setSource] = useState<LawPayload["source"]>("seed");
  const [message, setMessage] = useState("내장 법령 자료를 불러오는 중입니다.");

  useEffect(() => {
    void fetch("/api/laws")
      .then(async (response) => {
        if (!response.ok) throw new Error("법령 자료를 불러오지 못했습니다.");
        return response.json() as Promise<LawPayload>;
      })
      .then((payload) => {
        setLaws(payload.data);
        setSelectedId(payload.data[0]?.id || "");
        setSource(payload.source);
        setMessage(payload.source === "live" ? "공식 법령 연동 자료" : "앱에 포함된 기준 법령 자료");
      })
      .catch((error: Error) => setMessage(error.message));
  }, []);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("ko");
    if (!normalized) return laws;
    return laws.filter((law) =>
      [law.title, law.summary, law.clause, law.application]
        .filter(Boolean)
        .some((value) => value!.toLocaleLowerCase("ko").includes(normalized)),
    );
  }, [laws, query]);

  const selected = laws.find((law) => law.id === selectedId) || filtered[0] || null;

  return (
    <section id="panel-laws" className="tool-layout" role="tabpanel" aria-labelledby="tab-laws">
      <div className="panel tool-sidebar">
        <div className="section-title">
          <div>
            <p className="eyebrow">근거 찾기</p>
            <h1>가족 법령 자료</h1>
          </div>
          <span className="status-badge tone-neutral">{laws.length}건</span>
        </div>

        <div className="source-notice" role="status">
          <Info aria-hidden="true" />
          <div>
            <strong>{message}</strong>
            <span>
              {source === "seed"
                ? "실시간 최신성은 보장하지 않습니다. 적용 전 국가법령정보센터에서 시행일과 개정 여부를 확인하세요."
                : "조회 시점과 출처 링크를 함께 확인하세요."}
            </span>
          </div>
        </div>

        <label className="field-label" htmlFor="law-search">
          법령명·조문·상황 검색
        </label>
        <div className="input-with-icon">
          <Search aria-hidden="true" />
          <input
            id="law-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="예: 육아휴직, 학원 환불, CCTV"
          />
        </div>

        <div className="select-list" aria-label="검색된 법령">
          {filtered.map((law) => (
            <button
              key={law.id}
              type="button"
              className={`select-row ${selected?.id === law.id ? "is-selected" : ""}`}
              aria-pressed={selected?.id === law.id}
              onClick={() => setSelectedId(law.id)}
            >
              <BookOpen aria-hidden="true" />
              <span>
                <strong>{law.title}</strong>
                <small>{law.clause}</small>
              </span>
              <em>{relevanceLabel(law.relevance)}</em>
            </button>
          ))}
          {!filtered.length && <p className="empty-copy">검색 결과가 없습니다. 더 짧은 단어로 다시 검색해 보세요.</p>}
        </div>
      </div>

      <article className="panel tool-detail" aria-live="polite">
        {selected ? (
          <>
            <div className="section-title">
              <div>
                <p className="eyebrow">선택한 근거</p>
                <h2>{selected.title}</h2>
              </div>
              <a className="text-link" href="https://www.law.go.kr" target="_blank" rel="noreferrer">
                공식 법령 확인 <ExternalLink aria-hidden="true" />
              </a>
            </div>
            <dl className="evidence-list">
              <div>
                <dt>법령 체계</dt>
                <dd>{selected.clause || "세부 체계 정보 없음"}</dd>
              </div>
              <div>
                <dt>내장 요약</dt>
                <dd>{selected.summary}</dd>
              </div>
              <div>
                <dt>상황별 참고</dt>
                <dd>{selected.application}</dd>
              </div>
            </dl>
            <div className="legal-disclaimer">
              이 설명은 양육 정보 보조용 요약입니다. 사건별 법률 자문이나 승소 가능성 판단이 아닙니다.
            </div>
          </>
        ) : (
          <div className="empty-state">
            <BookOpen aria-hidden="true" />
            <strong>확인할 법령을 선택하세요.</strong>
          </div>
        )}
      </article>
    </section>
  );
}
