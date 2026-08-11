/** 개인정보처리방침 · 이용약관.
 *
 * 🔴 이 문서는 **코드가 실제로 하는 일**을 적은 것이다. 템플릿을 베껴 넣지 말 것 —
 * 여기 적힌 항목과 서버가 저장하는 항목이 다르면 그 자체가 위반이다.
 * 수집 항목을 바꾸면(필드 추가·외부 전송처 추가) 이 파일과 CONSENT_VERSION을 함께 고친다.
 *
 * 대조 지점:
 *   저장 항목   → src/server/accounts.ts StoredUser / StoredProfile
 *   퍼널 기록   → src/server/telemetry.ts FunnelEvent
 *   외부 전송   → src/jaramlaw_agent/openai_client.py · openrouter_client.py · law_live.py
 */

/** accounts.ts CONSENT_VERSION과 같아야 한다. 약관 개정 시 양쪽을 함께 올린다. */
export const CONSENT_VERSION = "2026-08-12";

/** 🔴 실제로 수신되는 주소여야 한다. 개인정보 열람·삭제 요청이 오는 창구다.
 *  여기 적힌 주소로 연락이 안 가면 처리방침이 거짓이 된다 — 주소를 바꿀 때는
 *  수신이 되는지 먼저 확인하고 바꿀 것. (2026-08-12 업무용 주소로 지정) */
export const CONTACT_EMAIL = "aithor@aithor.biz";

export function PrivacyView({ onExit }: { onExit: () => void }) {
  return (
    <main id="main-content" className="legal-shell" tabIndex={-1}>
      <article className="panel legal-doc">
        <h1>개인정보 처리방침</h1>
        <p className="legal-meta">시행일 {CONSENT_VERSION} · 자람법(JaramLaw) — 에이아이터</p>

        <p className="legal-lead">
          자람법은 아이 정보를 <strong>최소한만</strong> 받습니다. 아이 이름과 정확한 주소는 받지 않으며,
          받지 않은 정보는 잃어버릴 수도 없습니다.
        </p>

        <h2>1. 수집하는 항목</h2>
        <table className="legal-table">
          <thead><tr><th>구분</th><th>항목</th><th>왜 필요한가</th></tr></thead>
          <tbody>
            <tr><td>계정</td><td>이메일, 비밀번호, 부를 이름(선택)</td><td>로그인, 기기를 바꿔도 기록 유지</td></tr>
            <tr><td>가족</td><td>사는 시·도, 자녀 출생 <strong>연월</strong>(또는 출산 예정 연월), 양육 형태</td><td>적용 법령·지원 판정과 신청 기한 계산</td></tr>
            <tr><td>이용</td><td>상담 질문과 답변 기록</td><td>지난 상담 다시 보기</td></tr>
            <tr><td>통계</td><td>화면 이동 단계, 기기 종류(모바일/PC)</td><td>어디서 막히는지 파악 — 개선 목적</td></tr>
          </tbody>
        </table>
        <p>
          <strong>받지 않는 것</strong>: 아이 이름 · 주민등록번호 · 상세 주소 · 전화번호 · 결제정보.
          상담 글에 이런 정보가 섞여 들어오면 AI로 넘어가기 전에 자동으로 가려집니다.
        </p>

        <h2>2. 외부로 나가는 것</h2>
        <p>답변을 만들기 위해 아래로 <strong>질문 내용과 해당 법령</strong>이 전송됩니다. 계정 정보와 가족 프로필은 전송되지 않습니다.</p>
        <ul>
          <li><strong>법제처 Open API</strong> (open.law.go.kr) — 조문 원문 조회. 개인정보는 보내지 않고 법령명만 조회합니다.</li>
          <li><strong>OpenAI</strong> — 질문을 부모가 읽을 안내문으로 옮기는 데 사용합니다.</li>
          <li><strong>OpenRouter</strong> — 위 답변이 근거를 벗어나지 않았는지 독립 검증하는 데 사용합니다.</li>
        </ul>
        <p>세 곳 모두 <strong>답변 생성·검증 목적</strong>으로만 쓰며, 광고나 분석 목적의 제3자 제공은 하지 않습니다. 분석 도구(Google Analytics 등)는 사용하지 않습니다.</p>

        <h2>3. 보관 기간</h2>
        <ul>
          <li>계정·가족 정보 — 회원 탈퇴 요청 시 <strong>지체 없이 파기</strong>합니다.</li>
          <li>상담 기록 — 계정당 최근 50건까지 보관하고, 그보다 오래된 것은 자동으로 지워집니다.</li>
          <li>통계 기록 — 개인을 알아볼 수 없는 형태로 남으며, 방문 식별자는 브라우저를 닫으면 사라집니다.</li>
        </ul>

        <h2>4. 이용자의 권리</h2>
        <p>
          본인 상담 기록은 화면에서 직접 삭제할 수 있습니다. 계정 삭제·정보 열람·정정을 원하시면
          아래 연락처로 알려주시면 처리합니다.
        </p>

        <h2>5. 서비스의 성격</h2>
        <p>
          자람법은 <strong>양육 정보 보조 도구</strong>이며 법률 자문이 아닙니다.
          제공되는 안내는 참고 자료이고, 구체적인 사안은 해당 기관이나 전문가에게 확인하셔야 합니다.
        </p>

        <h2>6. 현재 베타 운영 중입니다</h2>
        <p>
          만들어가는 중이라 오류가 있을 수 있습니다. 잘못된 안내를 발견하시면 알려주시면 바로 고치겠습니다.
        </p>

        <h2>7. 문의</h2>
        <p>개인정보 보호책임자: 서현 · <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></p>

        <button type="button" className="btn-text" onClick={onExit}>← 돌아가기</button>
      </article>
    </main>
  );
}

export function TermsView({ onExit }: { onExit: () => void }) {
  return (
    <main id="main-content" className="legal-shell" tabIndex={-1}>
      <article className="panel legal-doc">
        <h1>이용약관</h1>
        <p className="legal-meta">시행일 {CONSENT_VERSION} · 자람법(JaramLaw) — 에이아이터</p>

        <h2>1. 무엇을 하는 서비스인가</h2>
        <p>
          입력하신 가족 정보를 바탕으로 적용될 수 있는 법령과 정부지원을 찾아 안내하고,
          신청서·요청서 <strong>초안</strong>을 만들어 드립니다.
        </p>

        <h2>2. 하지 않는 것</h2>
        <ul>
          <li><strong>법률 자문을 하지 않습니다.</strong> 승소 가능성이나 소송 전략은 안내하지 않습니다.</li>
          <li><strong>대신 제출하지 않습니다.</strong> 서류는 초안까지이며, 제출과 결정은 이용자 본인이 합니다.</li>
          <li><strong>자동으로 신고하지 않습니다.</strong> 외부 기관에 직접 접수하는 기능은 없습니다.</li>
        </ul>

        <h2>3. 안내의 정확성</h2>
        <p>
          법령 원문은 법제처에서 조회해 조문·시행일·출처를 함께 표시합니다. 다만 개별 상황에 따라
          적용이 달라질 수 있으므로, <strong>실제 신청·대응 전에는 표시된 출처와 관할 기관을 통해 확인</strong>해 주세요.
          안내 내용에 따른 판단과 그 결과에 대한 책임은 이용자에게 있습니다.
        </p>

        <h2>4. 위급 상황</h2>
        <p>
          아동학대가 의심되거나 응급 상황이라면 이 서비스를 거치지 말고 즉시 연락하세요.
          <br />아동학대 <strong>1577-1391</strong> · 응급 <strong>119</strong> · 자해·자살 <strong>1393</strong> · 가정폭력 <strong>1366</strong>
        </p>

        <h2>5. 이용료</h2>
        <p>현재 <strong>베타 기간으로 무료</strong>입니다. 유료 기능이 생기면 미리 안내하고 동의를 받습니다.</p>

        <h2>6. 서비스 변경·중단</h2>
        <p>베타 서비스라 기능이 바뀌거나 중단될 수 있습니다. 중단 시에는 미리 알리고, 저장된 정보를 내려받을 수 있게 하겠습니다.</p>

        <h2>7. 문의</h2>
        <p>에이아이터 · <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a></p>

        <button type="button" className="btn-text" onClick={onExit}>← 돌아가기</button>
      </article>
    </main>
  );
}
