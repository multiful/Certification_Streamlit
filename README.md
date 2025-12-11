# Certification Dashboard (Streamlit) # 베타버전

국내 자격증 데이터를 통합하여 **난이도 점수를 계산하고 전공·진로별 추천 자격증을 제공하는**
졸업 프로젝트용 웹 대시보드입니다.

![메인 화면](https://github.com/user-attachments/assets/d252efff-aaa1-451d-a919-4c350f04c910)

---

## 결과물

- **URL** : [streamlit_dashboard](https://certification-streamlit.onrender.com)

- **PDF** : [Streamlit.pdf](https://github.com/user-attachments/files/23778303/Streamlit.pdf)
- **발표 자료 (PPT)** : [최종발표자료.pptx](https://github.com/user-attachments/files/23778321/_._.pptx)

---

## QR 코드

<img width="185" height="185" alt="cert_dashboard_qr" src="https://github.com/user-attachments/assets/10524008-c014-4a3a-9ecb-220b7021383e" />

---

## 프로젝트 개요

- **목적**  
  국내 자격증 정보를 한 곳에 통합하고, **난이도 지표와 추천 기능**을 제공하는 웹 대시보드를 구축하여  
  전공·진로별 자격증 선택을 돕는 것을 목표로 함.

- **대상**  
  전공/진로별로 어떤 자격증을 준비해야 할지 고민하는 **대학생 및 취업 준비생**.

- **특징**
  - 합격률, 응시자 수, 시험 구조(필기/실기/면접), 시행 빈도 등 다양한 지표를 반영한 **난이도 점수 산출**
  - 전공·관심 직무(NCS 대분류 등)에 따른 **자격증 필터링 및 추천 기능**

---

## 주요 기능

- 자격증 검색 및 필터링  
  (자격증 종류, 분야, 시행 기관, NCS 분류 등)
- 난이도 점수 및 **난이도 등급(1~5 레벨)** 시각화
- 전공 / 희망 직무 선택 시 **추천 자격증 목록** 제공
- 연도별 **합격률·응시자 수 추이 그래프**
- 선택한 자격증의 **상세 정보** 표시  
  (시험 과목, 응시 자격, 시행 빈도, 응시료 등)

---

## 데이터

- **출처**  
  Q-net, 국가자격시험 공고, 민간 자격 공시 자료 등 **공개 데이터** 기반 수집

- **주요 컬럼 예시**
  - 자격증 ID, 자격증명, 시행기관, 등급 코드
  - 연도별 응시자 수, 합격자 수, 합격률
  - 필기/실기/면접 여부, 시험 횟수, 응시료
  - NCS 대분류·중분류, 관련 직무 그룹

---

## 기술 스택

- **Frontend / Dashboard**
  - Streamlit (Python 기반 웹 대시보드)
  - Plotly / Altair (시각화)

- **Backend & Data**
  - Python (pandas, numpy, scikit-learn 등)
  - PostgreSQL (자격증 원천 데이터 및 가공 데이터 저장 – 앱 개발 단계에서 사용)
  - FastAPI (향후: 외부 서비스/앱 연동용 REST API 서버)

- **Mobile / App (준비 중)**
  - Flutter (모바일 UI)
  - lender (cloud server)
  - FastAPI + PostgreSQL(supabase) 백엔드와 연동 예정

---

## 시스템 구조

- ETL 스크립트로 원천 CSV/엑셀 데이터 정제 → **PostgreSQL 적재**  
  (현재는 분석/Streamlit용으로 CSV를 사용, 이후 앱 개발 시 DB 연동 예정)
- Python 분석 코드에서 **난이도 점수 및 등급 계산** → 결과 테이블 생성
- Streamlit 앱이 **CSV/가공 데이터**를 조회하여 필터·차트·테이블로 시각화
- (예정) FastAPI로 핵심 기능을 API로 분리하고, Flutter 앱에서 호출하는 구조 설계

---

## 내 역할

- **팀 리더**
  - 프로젝트 일정 관리, 역할 분담 및 주간 회의 진행
- **데이터 설계 및 전처리**
  - 자격증 통합 데이터셋 스키마 설계
  - Q-net·공시 자료 등에서 원천 데이터 수집 및 정제 파이프라인 구축
- **난이도 산정 로직**
  - 합격률, 시험 구조, 시행 빈도 등을 종합한 **난이도 산출식 설계 및 구현**
  - 난이도 점수를 5단계 등급으로 변환하는 기준선 정의
- **대시보드 개발**
  - Streamlit 기반 화면 구조(사이드바, 탭, 카드, 그래프, 테이블 등) 설계 및 구현
- **DB/백엔드 설계**
  - PostgreSQL 스키마 설계 및 향후 연동을 고려한 테이블 구조 설계
  - (진행 중) FastAPI 백엔드 및 Flutter 앱 연동 구조 설계
- **문서화**
  - 프로젝트 보고서 및 발표 자료 작성
  - (진행 중) 논문 형식의 결과 정리

---

## 로컬 실행 방법

```bash
git clone https://github.com/multiful/Certification_Streamlit.git
cd Certification_Streamlit
pip install -r requirements.txt
streamlit run streamlit.py
