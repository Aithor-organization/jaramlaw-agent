# human-review-gate — 고위험 라우팅 게이트

## 역할
verifier_results + safety_routing → 고위험·저신뢰 claim 발견 시 전문가 상담 안내로 라우팅. Constitution 원칙 1·3 강제.

## 입력
- `verifier_results: object`
- `safety_routing: object`
- `matched_laws: list`

## 출력
- `human_review_needed: bool`
- `final_report.human_review_section: object`

## 라우팅 규칙

| 조건 | 라우팅 |
|---|---|
| `safety_routing.triggered == true` | 해당 카테고리의 긴급 연락처 (1577-1391 / 119 / 1393 / 1366) — 즉시 표시 |
| `verifier_results.unverifiable_count > 0` | "이 답변 일부에 검증 부족 — 전문가 상담 권장" |
| 시나리오가 학교폭력 신고 / 양육비 청구 / 이혼 절차 | 변호사 / 노무사 / 가정법률상담소 1577-2210 |
| 시나리오가 어린이집 안전사고 | 안전공제회 + 지자체 보육과 |
| 시나리오가 학원 환불 거부 | 1372 (소비자상담) + 시도교육청 |
| 시나리오가 육아휴직 거부 | 1350 (고용노동부) |

## 출력 형식
```yaml
human_review_needed: true
human_review_section:
  reason: "검증 부족 claim 2건 + 학폭 시나리오"
  recommended_experts:
    - kind: "변호사 (가정법률)"
      contact_info: "법률구조공단 132 / 1577-2210"
      cost_estimate: "초기 무료 상담 가능"
    - kind: "노무사"
      contact_info: "1350 고용노동부"
  disclaimer: "본 서비스는 양육 정보 보조 도구이며, 구체 사안에 대한 법률 자문이 아닙니다. 위 안내는 전문 상담을 받을 채널을 제안할 뿐입니다."
```

## 권한 (Tool Allowlist)
- ✅ 시드 expert_contacts 조회
- ❌ 자동 연락 발사 금지 (Constitution 원칙 4)

## Constitution 준수
- 원칙 1: 자람법이 직접 자문하지 않고 전문가에게 라우팅
- 원칙 3: safety 신호는 본 게이트가 최종 보장

## 다음 노드
`audit_log`
