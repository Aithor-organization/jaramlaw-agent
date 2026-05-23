# 공모전 기획서 매핑 (붙임4 양식)

> 제2회 법령데이터 활용 아이디어 공모전 — "제품 및 서비스 개발 부문 (시제품 완료 상태)"

본 문서는 [`spec/spec.md`](../spec/spec.md), [`spec/plan.md`](../spec/plan.md), [`docs/architecture.md`](architecture.md) 내용을 공모전 기획서 양식에 매핑한다.

| 기획서 항목 | 본 프로젝트 출처 | 비고 |
|---|---|---|
| 아이디어명 | "자람법(JaramLaw)" + 부제 "똑똑맘이 만든 가족 라이프스테이지 법령 AI" | 제안서 §0, §부록A |
| 제안 배경 | 제안서 §2 문제 정의 (P1-P5 페인) | 부모의 5가지 페인 |
| 제안 내용 | 제안서 §3 핵심 가치 + §5 F1-F8 + §6 시나리오 A/B/C/D/E | 8 킬러 기능 |
| 법령데이터 활용 방안 | 제안서 §7 + `data/seed/laws/` 22개 시드 | 30+ 법령, 수백 조문 |
| AI 활용 방안 | 제안서 §8 14노드 아키텍처 + §9 AI 차별점 + `docs/architecture.md` | Multi-Agent Board + RAG + Verifier |
| 기대 효과 | 제안서 §13 사업화 + B2C/B2G/B2B 3축 | 매출 모델 + 본선 진출 |
| 차별성 | 제안서 §10 경쟁 분석 도표 (7개 차원 모두 ◎) | 양육 도메인 + 법령 인용 + 분쟁 대응 통합 |
| 실현 가능성 | 제안서 §8.1 AITHOR 자산 100% 재사용 + §12 MVP D-7 일정 + `tests/` 54 PASS | 시제품 완료 |
| 안전성·법률 리스크 대응 | 제안서 §11 + `spec/constitution.md` Constitution 5원칙 + `tests/test_constitution.py` | 변호사법/PII/safety/no-side-effect |

## 시제품 데모 시연 시나리오 (5분 발표용)

1. **Hook (0:30)**: 제안서 §14 똑똑맘 채널 월 10만 도달
2. **Problem (1:00)**: P1-P5 페인 — `data/seed/scenarios/` 3개로 가시화
3. **Solution (2:00)**:
   - 데모 1: 시나리오 B (학원 환불) — `python3 -m jaramlaw_agent demo --scenario B --print-first-card`
     - 환불액 ≈641,667원 (학원법 시행령 별표4 일할 계산)
     - 환불 요청서 markdown 출력
   - 데모 2: 시나리오 C (어린이집 사고) — `python3 -m jaramlaw_agent demo --scenario C`
     - safety 라우팅 발동 (1577-1391)
     - 권리카드 + 사고 경위서 + CCTV 열람 신청서 자동 생성
4. **Differentiation (1:00)**: 제안서 §10 경쟁 분석 도표 + `AITHOR-Agent-Framework + LAW.OS` 재사용 강조
5. **Why us (0:30)**: 똑똑맘 채널 자산 + AITHOR/LAW.OS 검증된 인프라
6. **Roadmap (0:30)**: 제안서 §13 B2C/B2G/B2B + 본선 진출 후 계획

## 제출 체크리스트

콘텐츠:
- [x] 아이디어명·부제 확정 — "자람법(JaramLaw)" / "똑똑맘이 만든 가족 라이프스테이지 법령 AI"
- [x] 페르소나 3명 디테일 확정 — `spec/spec.md` §2
- [x] 시나리오 3개 입출력 확정 — `data/seed/scenarios/`
- [x] 법령 시드 데이터 22개 조문 — `data/seed/laws/`
- [x] 경쟁 분석 도표 (제안서 §10)

시제품:
- [x] `family-legal` 도메인팩 코드 PASS — `pytest` 54 PASS
- [x] 시나리오 3개 e2e deterministic 동작 — `test_scenarios.py`
- [x] 권리카드 markdown 출력 확인 — `rights_card.render_card_markdown()`
- [x] 신청서·신고서 초안 출력 확인 — `document_drafter.py` 5 템플릿
- [ ] 데모 화면 캡처 또는 영상 (사용자 제작)

안전성:
- [x] 법률 자문 아님 고지 문구 표준화 적용 — `test_constitution.py::test_principle_1_disclaimer_in_all_outputs`
- [x] PII 마스킹 동작 확인 — `test_constitution.py::test_principle_5_pii_masking_*`
- [x] 학대 의심·자해 위험 라우팅 룰 확인 — `test_constitution.py::test_principle_3_safety_routing_child_abuse`
- [x] 고위험 답변 Human Review Gate 동작 — `human_review.determine_human_review()`

제출서류 (사용자 제작):
- [ ] 참가신청서 [붙임1]
- [ ] 참가서약서 [붙임2]
- [ ] 개인정보 수집·이용 동의서 [붙임3]
- [ ] 아이디어 기획서 [붙임4] — 본 문서 매핑 활용
- [ ] 발표자료 PPT 초안 (위 5분 스토리)
