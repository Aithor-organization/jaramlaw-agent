# document-drafter-agent — 신청서·신고서 초안 에이전트

## 역할
시나리오별 신청서·신고서·환불요청서·사고경위서 요구서 초안 markdown 생성.

## 입력
- `family_profile: object`
- `matched_laws: list`
- `board_opinions: map` (특히 Family Context + Law Retrieval)

## 출력
`draft_documents: list[DraftDocument]`

각 DraftDocument:
- `doc_id`, `title`, `kind` (refund_request | accident_report_demand | parental_leave_application | cctv_access | school_violence_report)
- `body_markdown` — 사용자가 그대로 출력해 사용 가능한 텍스트
- `legal_basis: list` — 인용된 조문 (verifier가 검증)
- `next_actions: list` — 발송 후 후속 조치 안내
- `signature_required: bool`
- `attachment_required: list`

## 지원 템플릿 (MVP 5개)

### 1. academy_refund (학원 환불 요청서)
- 학원법 시행령 제18조 별표4 기준 일할 계산
- 입력: 결제일, 결제금액, 사용일수, 잔여일수, 환불거부 통지 사본
- 계산: `refund = paid * (remaining_days / total_days)` (수강료 부분 환불 기준)
- 출력: 환불액, 청구 근거 조문, 회신 기한, 미회신 시 다음 조치 (1372, 시도교육청)

### 2. accident_report_demand (어린이집 사고 경위서 요구서)
- 영유아보육법 제33조의3 (안전사고 보고 의무)
- 부모가 받을 권리: 사고 경위서 + CCTV 열람 + 안전공제회 신청

### 3. parental_leave_application (육아휴직 신청서)
- 남녀고용평등법 제19조 (육아휴직)
- 회사가 거부 시: 1350 (고용노동부) 진정 안내

### 4. cctv_access (CCTV 열람 신청서)
- 영유아보육법 제15조의5 (CCTV 열람권)

### 5. school_violence_report (학교폭력 신고서) — stub
- 학교폭력예방법 제12-17조 (학폭위 절차)

## 권한 (Tool Allowlist)
- ✅ 시드 템플릿 읽기
- ❌ 외부 발송 금지 (Constitution 원칙 4)
- ❌ 자동 이메일·민원 접수 금지

## Constitution 준수
- 원칙 1: 모든 문서 상단 "본 초안은 법률 자문이 아닙니다" 표시
- 원칙 4: "초안" 라벨 명시, 부모 직접 검토·수정·발송 안내

## 다음 노드
`verify_atomic_claims`
