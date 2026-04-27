# 수동 검토 패킷: 1.5

- Generated: 2026-04-27 10:37:30
- Related change atoms: 60
- Source-only rows: 18
- Target-only rows: 15
- Evidence/metric impact rows: 38

## Mapping Candidates

- c4 1.3 재정 확보 및 집행 <- c3 1.5 재정 집행 (needs_review, sim=0.727)
- c4 1.5 교육성과 <- c3 1.1 교육목표 및 인재상 (이동 항목) (needs_review, sim=0.250)
- c4 1.5 교육성과 <- c3 5.1 성과관리 (이동 항목) (needs_review, sim=0.333)
- c4 1.5 교육성과 <- c3 5.2 교육성과 (needs_review, sim=1.000)
- c4 1.5 교육성과 <- c3 5.4 취·창업지원 및 성과 (needs_review, sim=0.317)

## Department Impact

- 기획처: 46
- 미지정: 14

## Change Review Rows

### chg_00005 | overview | 변경 | high

- Review reason: manual_complex_nm_criterion;needs_review_status
- Global match: not_applicable (0 reportable candidates)
- Departments: 기획처, 재무회계팀
- Source IDs: 4주기 `c4__1_3__overview__content` / 3주기 `c3__1_5__overview__content`
- 4주기 원문: 대학은 교육목표를 달성하기 위해 재정 운영 계획을 수립하고 이에 따라 필요한 재원을 안정적으로 확보하고 있으며, 지속적인 재원 확충을 위해 재원을 다양화하고 있다. 그리고 확보된 재원을 효율적으로 운영하기 위한 계획을 수립하고, 합리적 절차에 따라 예산을 편성·집행하며 학생들을 위한 교육활동에 적절히 환원하고 있다. 또한 예산 편성·집행 결과를 평가하여 대학재정 운영에 반영하고 있다.
- 3주기 원문: 대학은 확보된 재원을 효율적으로 운영하기 위한 계획을 수립하고, 합리적 절차에 따라 예산을 편성·집행하며 학생들을 위한 교육활동에 적절히 환원하고 있다. 또한 예산 편성·집행 결과를 평가하여 대학재정 운영에 반영하고 있다.

### chg_00008 | overview | 신설후보 | high

- Review reason: manual_complex_nm_criterion;low_similarity_match;needs_review_status
- Global match: weak_candidate (4 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__overview__content` / 3주기 `c3__5_2__overview__content`
- 4주기 원문: 대학은 교육목적에 부합하는 학생을 충원하여 유지하고, 학생학습성과 관리 체계에 따른 운영과 교육만족도 조사 결과에 따른 환류 체계를 갖추고 있으며, 졸업생의 취·창업 및 진학 등 진로 성과를 높이기 위한 노력을 기울이고 있다.
- 3주기 원문: 대학은 교육목적에 부합하는 학생을 충원하여 유지하고, 교육성과를 높이기 위한 노력을 기울이고 있다.
- Global candidates:
  - rank 1 score 0.630: c3__5_2__overview__content / 대학은 교육목적에 부합하는 학생을 충원하여 유지하고, 교육성과를 높이기 위한 노력을 기울이고 있다.
  - rank 2 score 0.391: c3__1_1__overview__content / 대학은 교육이념 및 교육목적을 달성하기 위한 명료한 교육목표와 인재상을 설정하고 있으며, 인재상에 도달할 수 있도록 학생학습성과 관리 체계를 구축하여 운영하고 있다.
  - rank 3 score 0.353: c3__5_1__overview__content / 대학은 대학경영 및 교육 전반에 대한 질 관리를 위하여 주기적으로 대학 자체평가, 교육만족도 조사를 포함한 다양한 방식으로 성과관리를 하고 있으며, 그 결과를 교육과 대학 운영에 충실히 반영하고 대학구성원이나 외부에 공개하는 등의 성과관리체계를 운영하고 있다.

### chg_00009 | overview | 삭제/이동후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status
- Global match: strong_candidate (3 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__5_4__overview__content`
- 4주기 원문: -
- 3주기 원문: 대학은 학생들의 진로와 취·창업을 위한 지원체계를 구축하고 예산과 전문 인력을 확보하여 운영하고 있으며 지속적인 개선을 위한 노력을 하고 있다.
- Global candidates:
  - rank 1 score 1.000: c4__4_3__overview__content / 대학은 학생들의 진로와 취·창업을 위한 지원 체계를 구축하고 예산과 전문 인력을 확보하여 운영하고 있으며 지속적인 개선을 위한 노력을 하고 있다.
  - rank 2 score 0.359: c4__4_6__overview__content / 대학은 교육과 연구에 필요한 자료 구입 예산과 전문 인력을 확보하고 있으며, 정보지원 인프라를 구축하여 효율적으로 운영하고 다양한 교수·학습 지원과 문화프로그램을 지원하고 있다.
  - rank 3 score 0.351: c4__1_5__overview__content / 대학은 교육목적에 부합하는 학생을 충원하여 유지하고, 학생학습성과 관리 체계에 따른 운영과 교육만족도 조사 결과에 따른 환류 체계를 갖추고 있으며, 졸업생의 취·창업 및 진학 등 진로 성과를 높이기 위한 노력을 기울이고 있다.

### chg_00058 | evidence | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__evidence__정보공시:002` / 3주기 `c3__1_5__evidence__정보공시:002`
- 4주기 원문: 9-나. 학생 1인당 교육비 산정근거
- 3주기 원문: 9-나. 학생 1인당 교육비 산정 근거

### chg_00059 | evidence | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__evidence__제출자료_관련규정:001` / 3주기 `c3__1_5__evidence__제출자료_관련규정:001`
- 4주기 원문: 예산 편성 관련 규정 및 지침
- 3주기 원문: 예산 편성 관련 규정 및 지침

### chg_00062 | evidence | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__evidence__현지확인자료:003` / 3주기 `c3__1_5__evidence__현지확인자료:003`
- 4주기 원문: 예산 편성 의견 수렴 관련 자료: 최근 3년 자료
- 3주기 원문: 예산 편성 의견 수렴 관련 자료: 최근 3년 자료

### chg_00064 | evidence | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__evidence__현지면담:002` / 3주기 `c3__1_5__evidence__현지면담:002`
- 4주기 원문: 예·결산 담당자
- 3주기 원문: 예・결산 담당자

### chg_00065 | evidence | 삭제/이동후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: strong_candidate (1 reportable candidates)
- Departments: 기획처, 재무회계팀
- Source IDs: 4주기 `-` / 3주기 `c3__1_5__evidence__정보공시:001`
- 4주기 원문: -
- 3주기 원문: 8. 예・결산 내역 등 학교 및 법인의 회계에 관한 사항
- Global candidates:
  - rank 1 score 1.000: c4__1_3__evidence__정보공시:001 / 8. 예·결산 내역 등 학교 및 법인의 회계에 관한 사항
  - rank 2 score 0.283: c4__1_3__evidence__현지면담:002 / 예·결산 담당자
  - rank 3 score 0.256: c4__1_1__evidence__정보공시:001 / 1-가. 학교규칙 및 그 밖에 학교운영에 관한 각종 규정

### chg_00066 | evidence | 삭제/이동후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: strong_candidate (3 reportable candidates)
- Departments: 기획처, 재무회계팀
- Source IDs: 4주기 `-` / 3주기 `c3__1_5__evidence__현지확인자료:001`
- 4주기 원문: -
- 3주기 원문: 중장기 재정 운영 계획서
- Global candidates:
  - rank 1 score 1.000: c4__1_3__evidence__현지확인자료:001 / 중장기 재정 운영 계획서
  - rank 2 score 0.398: c4__1_1__evidence__제출자료_첨부:002 / 대학 중장기 발전계획서
  - rank 3 score 0.398: c4__1_4__evidence__제출자료_첨부:001 / 대학 중장기 발전계획서

### chg_00067 | evidence | 삭제/이동후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: strong_candidate (5 reportable candidates)
- Departments: 기획처, 재무회계팀
- Source IDs: 4주기 `-` / 3주기 `c3__1_5__evidence__현지확인자료:002`
- 4주기 원문: -
- 3주기 원문: 예・결산보고서: 최근 3년 자료
- Global candidates:
  - rank 1 score 1.000: c4__1_3__evidence__현지확인자료:002 / 예·결산보고서: 최근 3년 자료
  - rank 2 score 0.520: c4__1_3__evidence__현지확인자료:003 / 예산 편성 의견 수렴 관련 자료: 최근 3년 자료
  - rank 3 score 0.511: c4__1_3__report__item:7 / 예산 집행 실적: 최근 3년 자료

### chg_00068 | evidence | 삭제/이동후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: strong_candidate (4 reportable candidates)
- Departments: 기획처, 재무회계팀
- Source IDs: 4주기 `-` / 3주기 `c3__1_5__evidence__현지면담:001`
- 4주기 원문: -
- 3주기 원문: 기획처장
- Global candidates:
  - rank 1 score 1.000: c4__1_2__evidence__현지면담:001 / 기획처장
  - rank 2 score 1.000: c4__1_3__evidence__현지면담:001 / 기획처장
  - rank 3 score 1.000: c4__1_4__evidence__현지면담:001 / 기획처장

### chg_00082 | evidence | 변경 | high

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__evidence__정보공시:001` / 3주기 `c3__5_2__evidence__정보공시:002`
- 4주기 원문: 4-라. 학생 충원 현황
- 3주기 원문: 4-라-1. 재학생 충원 현황

### chg_00083 | evidence | 유지 | high

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__evidence__정보공시:002` / 3주기 `c3__5_4__evidence__정보공시:001`
- 4주기 원문: 5-다. 졸업생의 취업 현황
- 3주기 원문: 5-다. 졸업생의 취업 현황

### chg_00084 | evidence | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: weak_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__evidence__제출자료_관련규정:001` / 3주기 `-`
- 4주기 원문: 교육만족도 조사 관련 규정
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.515: c3__3_1__evidence__제출자료_관련규정:002 / 강사 관련 규정
  - rank 2 score 0.486: c3__5_1__evidence__현지면담:001 / 기획처장, 교육만족도조사 담당자
  - rank 3 score 0.457: c3__3_4__evidence__제출자료_관련규정:003 / 교육지원인력 관련 규정

### chg_00085 | evidence | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: strong_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__evidence__현지확인자료:001` / 3주기 `-`
- 4주기 원문: 학생학습성과 관리 및 운영 체계 관련 자료: 최근 3년 자료
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.893: c3__1_1__evidence__현지확인자료:001 / 학생학습성과 관리 및 운영 체계 관련 자료
  - rank 2 score 0.528: c3__1_1__report__item:3 / 인재상에 부합하는 학생학습성과 관리 및 운영 체계
  - rank 3 score 0.514: c3__5_1__evidence__현지확인자료:001 / 대학 자체평가 결과 반영 자료: 최근 3년 자료

### chg_00086 | evidence | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: strong_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__evidence__현지확인자료:002` / 3주기 `-`
- 4주기 원문: 교육 만족도 조사 관련 자료(설문지, 분석 결과, 환류 실적 등): 최근 3년 자료
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.849: c3__5_1__evidence__현지확인자료:002 / 교육만족도 조사 관련 자료(설문지, 분석 결과, 결과 반영 등): 최근 3년 자료
  - rank 2 score 0.773: c3__5_4__evidence__현지확인자료:002 / 취·창업지원에 대한 만족도 조사 관련 자료(설문지, 분석 결과 등): 최근 3년 자료
  - rank 3 score 0.726: c3__4_2__evidence__현지확인자료:002 / 학생상담에 대한 만족도 조사 관련 자료(설문지, 분석 결과, 개선 실적 등): 최근 3년 자료

### chg_00087 | evidence | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: weak_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__evidence__현지면담:001` / 3주기 `-`
- 4주기 원문: 기획처장, 교무처장, 교육혁신원장, 취·창업지원처(센터)장
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.424: c3__5_4__evidence__현지면담:001 / 취・창업지원센터 센터장 또는 담당자
  - rank 2 score 0.415: c3__5_4__evidence__현지면담:002 / 취・창업지원센터 이용 학생
  - rank 3 score 0.410: c3__5_4__evidence__시설방문:001 / 취・창업지원센터

### chg_00088 | evidence | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: weak_candidate (4 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__evidence__현지면담:002` / 3주기 `-`
- 4주기 원문: 취·창업지원 관련 업무 담당자, 학생역량 담당자, 교육 만족도 조사 담당자
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.486: c3__5_1__evidence__현지면담:001 / 기획처장, 교육만족도조사 담당자
  - rank 2 score 0.404: c3__5_4__evidence__현지면담:001 / 취・창업지원센터 센터장 또는 담당자
  - rank 3 score 0.379: c3__5_4__evidence__현지면담:002 / 취・창업지원센터 이용 학생

### chg_00089 | evidence | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: strong_candidate (4 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__evidence__현지면담:003` / 3주기 `-`
- 4주기 원문: 학생 1 인원: 10명 내외 2 표집: 계열별, 학년별, 성별에 따라 고르게 분포
- 3주기 원문: -
- Global candidates:
  - rank 1 score 1.000: c3__2_2__evidence__현지면담:004 / 학생 1 인원: 10명 내외 2 표집: 계열별, 학년별, 성별에 따라 고르게 분포
  - rank 2 score 1.000: c3__2_3__evidence__현지면담:003 / 학생 1 인원: 10명 내외 2 표집: 계열별, 학년별, 성별에 따라 고르게 분포
  - rank 3 score 1.000: c3__5_1__evidence__현지면담:002 / 학생 1 인원: 10명 내외 2 표집: 계열별, 학년별, 성별에 따라 고르게 분포

### chg_00090 | evidence | 삭제후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: possible_candidate (3 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__5_2__evidence__정보공시:001`
- 4주기 원문: -
- 3주기 원문: 4-다. 신입생 충원 현황
- Global candidates:
  - rank 1 score 0.652: c4__1_5__evidence__정보공시:001 / 4-라. 학생 충원 현황
  - rank 2 score 0.407: c4__1_5__evidence__정보공시:002 / 5-다. 졸업생의 취업 현황
  - rank 3 score 0.371: c4__3_5__evidence__정보공시:001 / 14-사. 직원 현황

### chg_00091 | evidence | 삭제후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: weak_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__5_2__evidence__현지확인자료:001`
- 4주기 원문: -
- 3주기 원문: 신입생실태조사보고서(또는 재학생실태조사보고서): 최근 3년 자료
- Global candidates:
  - rank 1 score 0.450: c4__1_3__evidence__현지확인자료:002 / 예·결산보고서: 최근 3년 자료
  - rank 2 score 0.417: c4__1_2__evidence__현지확인자료:004 / 내·외부(교육부, 감사원 등) 감사보고서: 최근 3년 자료
  - rank 3 score 0.391: c4__1_5__evidence__현지확인자료:001 / 학생학습성과 관리 및 운영 체계 관련 자료: 최근 3년 자료

### chg_00327 | report | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__report__item:5` / 3주기 `c3__1_5__report__item:1`
- 4주기 원문: 교육비 환원율: 최근 3년 자료, 최근 3년간 평균 ※ 총 교육비 산출시 국가장학금 I유형, 다자녀 국가장학금은 제외함(기준값: 110%)
- 3주기 원문: 교육비 환원율: 최근 3년 자료, 최근 3년간 평균 ※ 총교육비 산출 시 국가장학금 I유형, 다자녀 국가장학금은 제외함(기준값: 110%)

### chg_00328 | report | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__report__item:6` / 3주기 `c3__1_5__report__item:2`
- 4주기 원문: 예산 편성 및 집행의 절차와 방법
- 3주기 원문: 예산 편성 및 집행의 절차와 방법

### chg_00329 | report | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__report__item:7` / 3주기 `c3__1_5__report__item:3`
- 4주기 원문: 예산 집행 실적: 최근 3년 자료
- 3주기 원문: 예산 집행 실적: 최근 3년 자료

### chg_00330 | report | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__report__item:8` / 3주기 `c3__1_5__report__item:4`
- 4주기 원문: 예산 집행의 평가 및 환류 실적: 최근 3년 자료
- 3주기 원문: 예산 집행의 평가 및 환류 실적: 최근 3년 자료

### chg_00337 | report | 변경 | high

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__report__item:1` / 3주기 `c3__5_2__report__item:2`
- 4주기 원문: 학생 충원 성과: 최근 3년 자료, 최근 3년간 평균(기준값: 85%)
- 3주기 원문: 정원내 재학생 충원율: 최근 3년 자료, 최근 3년간 평균(기준값: 80%)

### chg_00338 | report | 변경 | high

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__report__item:2` / 3주기 `c3__5_4__report__item:1`
- 4주기 원문: 졸업생 진로 성과: 최근 3년 자료, 최근 3년간 평균(기준값: 55%)
- 3주기 원문: 졸업생의 취업률: 최근 3년 자료, 최근 3년간 평균(기준값: 50%)

### chg_00339 | report | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: weak_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__report__item:3` / 3주기 `-`
- 4주기 원문: 학생학습성과 관리 및 운영 실적: 최근 3년 자료
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.597: c3__1_1__evidence__현지확인자료:001 / 학생학습성과 관리 및 운영 체계 관련 자료
  - rank 2 score 0.582: c3__1_1__report__item:3 / 인재상에 부합하는 학생학습성과 관리 및 운영 체계
  - rank 3 score 0.542: c3__5_1__report__item:3 / 대학 자체평가 결과 반영 개선 실적: 최근 3년 자료

### chg_00340 | report | 신설후보 | high

- Review reason: manual_complex_nm_criterion;low_similarity_match;needs_review_status;evidence_or_metric_impact
- Global match: strong_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__report__item:4` / 3주기 `c3__5_4__report__item:4`
- 4주기 원문: 교육 만족도 조사 방법, 내용, 결과, 환류 실적: 최근 3년 자료
- 3주기 원문: 취·창업지원에 대한 만족도 조사 결과와 개선 실적: 최근 3년 자료
- Global candidates:
  - rank 1 score 1.000: c3__5_1__report__item:4 / 교육만족도 조사 방법, 내용, 결과, 환류 실적: 최근 3년 자료
  - rank 2 score 0.587: c3__5_4__report__item:4 / 취·창업지원에 대한 만족도 조사 결과와 개선 실적: 최근 3년 자료
  - rank 3 score 0.559: c3__4_2__report__item:3 / 학생상담 만족도 조사 결과 및 개선 실적: 최근 3년 자료

### chg_00341 | report | 삭제/이동후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: possible_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__5_2__report__item:1`
- 4주기 원문: -
- 3주기 원문: 정원내 신입생 충원율: 최근 3년 자료, 최근 3년간 평균(기준값: 95%)
- Global candidates:
  - rank 1 score 0.727: c4__1_5__report__item:1 / 학생 충원 성과: 최근 3년 자료, 최근 3년간 평균(기준값: 85%)
  - rank 2 score 0.668: c4__1_5__report__item:2 / 졸업생 진로 성과: 최근 3년 자료, 최근 3년간 평균(기준값: 55%)
  - rank 3 score 0.610: c4__4_1__report__item:1 / 장학금 비율: 최근 3년 자료, 최근 3년간 평균(기준값: 12%)

### chg_00342 | report | 삭제/이동후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: weak_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__5_2__report__item:3`
- 4주기 원문: -
- 3주기 원문: 정원내 신입생 및 재학생 충원율 제고를 위한 노력: 최근 3년 자료
- Global candidates:
  - rank 1 score 0.432: c4__1_5__report__item:1 / 학생 충원 성과: 최근 3년 자료, 최근 3년간 평균(기준값: 85%)
  - rank 2 score 0.412: c4__1_5__report__item:3 / 학생학습성과 관리 및 운영 실적: 최근 3년 자료
  - rank 3 score 0.362: c4__2_6__report__item:5 / 프로그램 평가 및 개선 노력 실적: 최근 3년 자료

### chg_00343 | report | 이동후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status
- Global match: strong_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__5_4__report__item:2`
- 4주기 원문: -
- 3주기 원문: 취·창업지원 조직 현황
- Global candidates:
  - rank 1 score 0.832: c4__4_3__report__item:1 / 진로 및 취·창업 지원 조직 현황
  - rank 2 score 0.491: c4__4_3__evidence__시설방문:001 / 취·창업지원센터
  - rank 3 score 0.467: c4__2_6__report__item:1 / 전담 조직 현황

### chg_00344 | report | 이동후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: strong_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__5_4__report__item:3`
- 4주기 원문: -
- 3주기 원문: 취·창업지원 프로그램 운영 및 예산 편성·집행 현황: 최근 3년 자료
- Global candidates:
  - rank 1 score 0.982: c4__4_3__report__item:2 / 진로 및 취·창업 지원 프로그램 운영 및 예산 편성·집행 현황: 최근 3년 자료
  - rank 2 score 0.549: c4__3_6__report__item:3 / 직원 복지제도 운영 실적 및 예산 집행 현황: 최근 3년 자료
  - rank 3 score 0.483: c4__4_3__evidence__현지확인자료:004 / 진로 및 취·창업 관련 프로그램 운영 관련 자료(참여자(수료자) 현황, 예산 집행, 기타): 최근 3년 자료

### chg_00491 | notes | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: no_candidate (0 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__notes__item:1` / 3주기 `-`
- 4주기 원문: 졸업생 진로 성과는 취업자, 창업자, 진학자 수를 합산하여 산출함
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.280: c3__5_4__notes__item:1 / 졸업생의 취업률에서 종교관련 및 예체능계열 학생 비율이 50% 이상인 대학의 기준값은 25%로 함
  - rank 2 score 0.280: c3__1_1__notes__item:4 / 학생학습성과는 대학의 교육이념과 교육목표에 근거하여 대학 스스로 설정한 각 인재상에 부합하는 학생역량을 의미함
  - rank 3 score 0.269: c3__5_1__notes__item:2 / 학부 재학생 이외 졸업생 만족도 조사 실적도 포함 가능함

### chg_00492 | notes | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status
- Global match: possible_candidate (1 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__notes__item:2` / 3주기 `-`
- 4주기 원문: 학생학습성과는 대학의 교육이념과 교육목표에 근거하여 대학 스스로 설정한 각 인재상에 부합하는 학생역량을 의미하고, 학생역량 함양을 위한 교과 및 비교과 과정 운영 실적 중심으로 작성함
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.783: c3__1_1__notes__item:4 / 학생학습성과는 대학의 교육이념과 교육목표에 근거하여 대학 스스로 설정한 각 인재상에 부합하는 학생역량을 의미함
  - rank 2 score 0.323: c3__1_1__report__item:3 / 인재상에 부합하는 학생학습성과 관리 및 운영 체계
  - rank 3 score 0.307: c3__1_1__notes__item:3 / 교육이념-교육목적-교육목표의 위계에 따라 구성하는 것이 원칙이나 대학에 따라서는 이념과 목적을 명확하게 구분하지 않고 이 중 어느 하나를 선택하는 경우도 있기 때문에 그 내용의 보편성과 타당성 중심의 점검 및 진단을 원칙으로 함

### chg_00493 | notes | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status
- Global match: possible_candidate (2 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__notes__item:3` / 3주기 `-`
- 4주기 원문: 교육 만족도 조사실적에는 학부 재학생 이외 졸업생, 산업체, 지역사회 만족도 조사 실적도 포함 가능함
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.766: c3__5_1__notes__item:2 / 학부 재학생 이외 졸업생 만족도 조사 실적도 포함 가능함
  - rank 2 score 0.373: c3__5_1__notes__item:4 / 대학 자체평가, 교육만족도 조사 외의 성과관리체계가 있으면 추가 기술 가능함
  - rank 3 score 0.313: c3__5_1__notes__item:3 / 교육만족도 조사는 수업평가, 대학 자체평가 등과 연계한 것이 아닌 독립적으로 운영되는 것에 한함

### chg_00494 | notes | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status
- Global match: strong_candidate (2 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__notes__item:4` / 3주기 `-`
- 4주기 원문: 교육 만족도 조사는 비교과 프로그램 만족도 조사, 강의(수업) 평가, 대학 자체평가 등과 연계한 것이 아닌 독립적으로 운영되는 것에 한함
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.853: c3__5_1__notes__item:3 / 교육만족도 조사는 수업평가, 대학 자체평가 등과 연계한 것이 아닌 독립적으로 운영되는 것에 한함
  - rank 2 score 0.351: c3__5_1__notes__item:4 / 대학 자체평가, 교육만족도 조사 외의 성과관리체계가 있으면 추가 기술 가능함
  - rank 3 score 0.298: c3__5_1__notes__item:2 / 학부 재학생 이외 졸업생 만족도 조사 실적도 포함 가능함

### chg_00495 | notes | 삭제후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: no_candidate (0 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__5_2__notes__item:1`
- 4주기 원문: -
- 3주기 원문: 정원내 신입생 및 재학생 충원율 제고를 위한 노력은 학생을 선발하는 것을 포함하여 학생유지를 위한 전반적인 노력을 의미함
- Global candidates:
  - rank 1 score 0.279: c4__2_6__notes__item:1 / 대학의 교수-학습 지원은 전체 교수 및 학생을 대상으로 실시하는 것을 의미함
  - rank 2 score 0.260: c4__1_5__checkpoints__item:3 / 학생학습성과 제고를 위한 운영 실적 및 환류 체계는 적절한가
  - rank 3 score 0.258: c4__1_5__notes__item:3 / 교육 만족도 조사실적에는 학부 재학생 이외 졸업생, 산업체, 지역사회 만족도 조사 실적도 포함 가능함

### chg_00496 | notes | 삭제후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: weak_candidate (1 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__5_4__notes__item:1`
- 4주기 원문: -
- 3주기 원문: 졸업생의 취업률에서 종교관련 및 예체능계열 학생 비율이 50% 이상인 대학의 기준값은 25%로 함
- Global candidates:
  - rank 1 score 0.351: c4__3_3__notes__item:4 / 예술계열 학생 비율 50% 이상인 대학의 1:1 강의 강사 강의료는 별도 구분하여 작성 가능
  - rank 2 score 0.280: c4__1_5__notes__item:1 / 졸업생 진로 성과는 취업자, 창업자, 진학자 수를 합산하여 산출함
  - rank 3 score 0.265: c4__4_3__notes__item:1 / 진로 및 취·창업 지원 전문 인력 확보는 대학의 규모나 특성에 따라 겸직, 공동, 협약, 위탁 가능함

### chg_00497 | notes | 이동후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status
- Global match: strong_candidate (1 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__5_4__notes__item:2`
- 4주기 원문: -
- 3주기 원문: 취·창업지원센터를 독립적으로 운영하지 않더라도 동일한 역할을 하는 조직(기관)이 있다면 실적으로 인정함
- Global candidates:
  - rank 1 score 1.000: c4__4_3__notes__item:2 / 진로 및 취·창업지원센터를 독립적으로 운영하지 않더라도 동일한 역할을 하는 조직(기관)이 있다면 실적으로 인정함
  - rank 2 score 0.294: c4__1_5__notes__item:4 / 교육 만족도 조사는 비교과 프로그램 만족도 조사, 강의(수업) 평가, 대학 자체평가 등과 연계한 것이 아닌 독립적으로 운영되는 것에 한함
  - rank 3 score 0.286: c4__4_3__notes__item:1 / 진로 및 취·창업 지원 전문 인력 확보는 대학의 규모나 특성에 따라 겸직, 공동, 협약, 위탁 가능함

### chg_00498 | notes | 이동후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status
- Global match: strong_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__5_4__notes__item:3`
- 4주기 원문: -
- 3주기 원문: 멀티캠퍼스인 경우 캠퍼스별로 구분하여 작성함
- Global candidates:
  - rank 1 score 1.000: c4__4_1__notes__item:3 / 멀티캠퍼스인 경우 캠퍼스별로 구분하여 작성함
  - rank 2 score 1.000: c4__4_2__notes__item:7 / 멀티캠퍼스인 경우 캠퍼스별로 구분하여 작성함
  - rank 3 score 1.000: c4__4_3__notes__item:3 / 멀티캠퍼스인 경우 캠퍼스별로 구분하여 작성함

### chg_00697 | checkpoints | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__checkpoints__item:5` / 3주기 `c3__1_5__checkpoints__item:1`
- 4주기 원문: 교육비 환원율의 최근 3년간 평균이 기준값을 충족하는가
- 3주기 원문: 교육비 환원율의 최근 3년간 평균이 기준값을 충족하는가

### chg_00698 | checkpoints | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__checkpoints__item:6` / 3주기 `c3__1_5__checkpoints__item:2`
- 4주기 원문: 예산을 합리적으로 편성하고 있는가
- 3주기 원문: 예산을 합리적으로 편성하고 있는가

### chg_00699 | checkpoints | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__checkpoints__item:6.sub:001` / 3주기 `c3__1_5__checkpoints__item:2.sub:001`
- 4주기 원문: 대학발전계획과 연계하여 예산을 편성하고 있는가
- 3주기 원문: 대학발전계획과 연계하여 예산을 편성하고 있는가

### chg_00700 | checkpoints | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__checkpoints__item:6.sub:002` / 3주기 `c3__1_5__checkpoints__item:2.sub:002`
- 4주기 원문: 규정을 준수하고, 구성원의 의견을 수렴하여 예산을 편성하고 있는가
- 3주기 원문: 규정을 준수하고, 구성원의 의견을 수렴하여 예산을 편성하고 있는가

### chg_00701 | checkpoints | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__checkpoints__item:7` / 3주기 `c3__1_5__checkpoints__item:3`
- 4주기 원문: 예산을 적절하게 집행하고 있는가
- 3주기 원문: 예산을 적절하게 집행하고 있는가

### chg_00702 | checkpoints | 유지 | 

- Review reason: manual_complex_nm_criterion;needs_review_status
- Global match: not_applicable (0 reportable candidates)
- Departments: 
- Source IDs: 4주기 `c4__1_3__checkpoints__item:8` / 3주기 `c3__1_5__checkpoints__item:4`
- 4주기 원문: 예산 집행 결과를 평가하여 환류하고 있는가
- 3주기 원문: 예산 집행 결과를 평가하여 환류하고 있는가

### chg_00721 | checkpoints | 변경 | high

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__checkpoints__item:1` / 3주기 `c3__5_2__checkpoints__item:2`
- 4주기 원문: 학생 충원 성과의 최근 3년간 평균이 기준값을 충족하고 있는가
- 3주기 원문: 정원내 재학생 충원율의 최근 3년간 평균이 기준값을 충족하고 있는가

### chg_00722 | checkpoints | 변경 | high

- Review reason: manual_complex_nm_criterion;needs_review_status;evidence_or_metric_impact
- Global match: not_applicable (0 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__checkpoints__item:2` / 3주기 `c3__5_4__checkpoints__item:1`
- 4주기 원문: 졸업생 진로 성과의 최근 3년간 평균이 기준값을 충족하고 있는가
- 3주기 원문: 졸업생 취업률의 최근 3년간 평균이 기준값을 충족하고 있는가

### chg_00723 | checkpoints | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status
- Global match: weak_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__checkpoints__item:3` / 3주기 `-`
- 4주기 원문: 학생학습성과 제고를 위한 운영 실적 및 환류 체계는 적절한가
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.457: c3__5_2__checkpoints__item:3 / 정원내 신입생 및 재학생 충원율 제고를 위한 노력이 적절한가
  - rank 2 score 0.425: c3__5_1__checkpoints__item:2 / 대학 자체평가 실시를 위한 조직 운영이 적절한가
  - rank 3 score 0.411: c3__1_1__checkpoints__item:4 / 학생학습성과를 제고하기 위하여 어떻게 노력하고 있는가

### chg_00724 | checkpoints | 신설후보 | high

- Review reason: manual_complex_nm_criterion;low_similarity_match;needs_review_status
- Global match: possible_candidate (3 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__checkpoints__item:3.sub:001` / 3주기 `c3__1_1__checkpoints__item:4.sub:001`
- 4주기 원문: 학생역량을 함양하기 위한 제도와 프로그램 운영 실적
- 3주기 원문: 인재상에 부합하는 학생역량을 함양하기 위한 전반적인 제도와 프로그램
- Global candidates:
  - rank 1 score 0.690: c3__1_1__checkpoints__item:4.sub:001 / 인재상에 부합하는 학생역량을 함양하기 위한 전반적인 제도와 프로그램
  - rank 2 score 0.385: c3__4_3__report__item:6.sub:005 / 소수집단학생에 대한 이해 프로그램 운영 실적
  - rank 3 score 0.381: c3__4_3__report__item:6.sub:003 / 소수집단학생을 위한 대학생활 상담 및 적응 프로그램 운영 실적

### chg_00725 | checkpoints | 변경 | high

- Review reason: manual_complex_nm_criterion;needs_review_status
- Global match: not_applicable (0 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__checkpoints__item:3.sub:002` / 3주기 `c3__1_1__checkpoints__item:4.sub:002`
- 4주기 원문: 학생역량 진단 및 환류 체계
- 3주기 원문: 학생역량 평가 및 환류 체계

### chg_00726 | checkpoints | 신설후보 | high

- Review reason: manual_complex_nm_criterion;low_similarity_match;needs_review_status
- Global match: weak_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__checkpoints__item:4` / 3주기 `c3__5_1__checkpoints__item:5`
- 4주기 원문: 교육 만족도 조사 실시를 위한 체계 및 운영은 적절한가
- 3주기 원문: 교육만족도 조사를 실시하며 조사의 내용과 방법은 적절한가
- Global candidates:
  - rank 1 score 0.543: c3__5_1__checkpoints__item:6 / 교육만족도 조사 결과 환류가 적절한가
  - rank 2 score 0.527: c3__5_1__checkpoints__item:5 / 교육만족도 조사를 실시하며 조사의 내용과 방법은 적절한가
  - rank 3 score 0.496: c3__5_1__checkpoints__item:2 / 대학 자체평가 실시를 위한 조직 운영이 적절한가

### chg_00727 | checkpoints | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: weak_candidate (4 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__checkpoints__item:4.sub:001` / 3주기 `-`
- 4주기 원문: 관련 규정, 조직 구성, 위원회 운영 실적 등
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.569: c3__5_1__checkpoints__item:1.sub:001 / 관련 규정, 조직, 인력 등
  - rank 2 score 0.399: c3__5_1__checkpoints__item:2.sub:001 / 조직구성, 회의자료, 결과보고서 등
  - rank 3 score 0.360: c3__1_2__checkpoints__item:1.sub:001 / 조직 구성

### chg_00728 | checkpoints | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status
- Global match: weak_candidate (4 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__checkpoints__item:4.sub:002` / 3주기 `-`
- 4주기 원문: 교육 만족도 조사의 정기적 실시 및 조사 방법 등
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.469: c3__5_1__checkpoints__item:5 / 교육만족도 조사를 실시하며 조사의 내용과 방법은 적절한가
  - rank 2 score 0.415: c3__5_1__checkpoints__item:6 / 교육만족도 조사 결과 환류가 적절한가
  - rank 3 score 0.358: c3__5_1__report__item:4 / 교육만족도 조사 방법, 내용, 결과, 환류 실적: 최근 3년 자료

### chg_00729 | checkpoints | 신설후보 | high

- Review reason: manual_complex_nm_criterion;target_only_new_or_move_review;needs_review_status
- Global match: weak_candidate (3 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__checkpoints__item:4.sub:003` / 3주기 `-`
- 4주기 원문: 교육 만족도 조사 내용 및 문항 구성의 적절성 등
- 3주기 원문: -
- Global candidates:
  - rank 1 score 0.441: c3__5_1__checkpoints__item:6 / 교육만족도 조사 결과 환류가 적절한가
  - rank 2 score 0.408: c3__5_1__checkpoints__item:5 / 교육만족도 조사를 실시하며 조사의 내용과 방법은 적절한가
  - rank 3 score 0.357: c3__5_1__report__item:4 / 교육만족도 조사 방법, 내용, 결과, 환류 실적: 최근 3년 자료

### chg_00730 | checkpoints | 신설후보 | high

- Review reason: manual_complex_nm_criterion;low_similarity_match;needs_review_status
- Global match: weak_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `c4__1_5__checkpoints__item:5` / 3주기 `c3__5_1__checkpoints__item:6`
- 4주기 원문: 교육 만족도 조사 결과를 반영하여 적절하게 개선하고 있는가
- 3주기 원문: 교육만족도 조사 결과 환류가 적절한가
- Global candidates:
  - rank 1 score 0.539: c3__3_4__checkpoints__item:4 / 교원의 요구분석을 통해 관련 프로그램을 개발하고, 만족도 조사 결과를 반영하여 개선하고 있는가
  - rank 2 score 0.526: c3__5_1__checkpoints__item:6 / 교육만족도 조사 결과 환류가 적절한가
  - rank 3 score 0.525: c3__3_6__checkpoints__item:8 / 직원의 요구분석을 통해 관련 프로그램을 개발하고, 만족도 조사 결과를 반영하여 개선하고 있는가

### chg_00731 | checkpoints | 삭제/이동후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: possible_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__5_2__checkpoints__item:1`
- 4주기 원문: -
- 3주기 원문: 정원내 신입생 충원율의 최근 3년간 평균이 기준값을 충족하고 있는가
- Global candidates:
  - rank 1 score 0.809: c4__1_5__checkpoints__item:1 / 학생 충원 성과의 최근 3년간 평균이 기준값을 충족하고 있는가
  - rank 2 score 0.751: c4__1_5__checkpoints__item:2 / 졸업생 진로 성과의 최근 3년간 평균이 기준값을 충족하고 있는가
  - rank 3 score 0.635: c4__1_3__checkpoints__item:5 / 교육비 환원율의 최근 3년간 평균이 기준값을 충족하는가

### chg_00732 | checkpoints | 삭제후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status;evidence_or_metric_impact
- Global match: weak_candidate (3 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__5_2__checkpoints__item:3`
- 4주기 원문: -
- 3주기 원문: 정원내 신입생 및 재학생 충원율 제고를 위한 노력이 적절한가
- Global candidates:
  - rank 1 score 0.457: c4__1_5__checkpoints__item:3 / 학생학습성과 제고를 위한 운영 실적 및 환류 체계는 적절한가
  - rank 2 score 0.376: c4__3_4__checkpoints__item:5 / 대학 내 연구자의 연구윤리 확립을 위한 노력이 적절한가
  - rank 3 score 0.367: c4__1_5__checkpoints__item:4 / 교육 만족도 조사 실시를 위한 체계 및 운영은 적절한가

### chg_00733 | checkpoints | 이동후보 | high

- Review reason: manual_complex_nm_criterion;source_only_delete_or_move_review;needs_review_status
- Global match: weak_candidate (5 reportable candidates)
- Departments: 기획처, 교무처, 교육혁신원, 취·창업지원부서
- Source IDs: 4주기 `-` / 3주기 `c3__1_1__checkpoints__item:4`
- 4주기 원문: -
- 3주기 원문: 학생학습성과를 제고하기 위하여 어떻게 노력하고 있는가
- Global candidates:
  - rank 1 score 0.411: c4__1_5__checkpoints__item:3 / 학생학습성과 제고를 위한 운영 실적 및 환류 체계는 적절한가
  - rank 2 score 0.397: c4__1_5__checkpoints__item:5 / 교육 만족도 조사 결과를 반영하여 적절하게 개선하고 있는가
  - rank 3 score 0.392: c4__1_5__checkpoints__item:1 / 학생 충원 성과의 최근 3년간 평균이 기준값을 충족하고 있는가
