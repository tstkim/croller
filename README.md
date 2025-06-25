# 키드짐 B2B 크롤러 (Kidgym B2B Crawler)

범용 쇼핑몰 크롤러 AI Agent - 키드짐 B2B 사이트 전용

## 📁 프로젝트 구조

### 🟢 핵심 실행 파일들
```
croller/
├── main.py                      # 메인 크롤링 엔진
├── config.py                    # 사이트별 설정 파일 (사용자 수정)
├── final_analyzer_universal.py  # 범용 선택자 자동 탐지
├── smart_detector_final.py      # 스마트 DOM 분석기
├── login_manager.py             # 로그인 관리 도구
└── utils/
    ├── image_optimizer.py       # 이미지 다운로드 및 썸네일 생성
    └── __init__.py             # 패키지 초기화
```

### 📂 폴더 구조
- **`images/`** - 크롤링 결과물 저장 폴더
  - `YYYYMMDDHHMM_kidgym/` - 각 실행별 결과 폴더
    - `cr/` - 썸네일 이미지 (650x650px, S2B 배지 포함)
    - `output/` - 상세 이미지 (10개씩 분할)
    - `YYYYMMDDHHMMkr.xlsx` - 엑셀 결과 파일

- **`archived/`** - 백업 및 참고 파일들
  - 이전 버전 메인 파일들
  - JSON 백업 파일들
  - 문서 및 분석 보고서
  - Supabase 관련 도구들

- **`test/`** - 테스트 및 디버깅 파일들
  - 다양한 테스트 스크립트
  - 폰트 테스트 이미지들
  - 썸네일 개선 테스트 파일들

## 🚀 사용 방법

### 1. 기본 실행
```bash
python main.py
```

### 2. 설정 변경 (config.py)
```python
TEST_PRODUCT_COUNT = 2          # 테스트할 상품 개수
PRODUCT_LINK_PATTERN = "..."    # 상품 페이지 패턴
brandname = "키드짐"             # 브랜드명
```

### 3. 결과 확인
- 이미지: `images/YYYYMMDDHHMM_kidgym/`
- 엑셀: `images/YYYYMMDDHHMM_kidgym/YYYYMMDDHHMMkr.xlsx`

## ✨ 주요 기능

### 🎯 범용 크롤링 엔진
- 자동 선택자 탐지 (SmartDetector)
- 실시간 DOM 분석
- 범용 패턴 매칭

### 🖼️ 고품질 썸네일 생성
- 650x650px 흰색 캔버스
- S2B 배지 자동 추가 (150x80px)
- 동적 폰트 크기 조정 (32pt-80pt)
- 상품명 자동 배치

### 📊 완전한 데이터 추출
- 상품명, 가격, 옵션 정보
- 고해상도 이미지 (660px 이상)
- 상세 설명 텍스트
- 엑셀 호환 형식

## 🔧 최근 개선사항

### v2.3 (2025-06-25)
- ✅ 썸네일 폰트 크기 대폭 개선 (80pt 최대)
- ✅ S2B 배지 크기 및 위치 최적화
- ✅ REGISTERED 텍스트 30% 축소
- ✅ 엑셀 저장 위치를 이미지 폴더로 통합
- ✅ 파일 구조 정리 및 문서화

### 성능 지표
- 썸네일 생성: 650x650px 고품질
- 상품명 폰트: 32pt-80pt 동적 조정
- S2B 배지: 파란색(150x80px) + 빨간색(150x50px)
- 처리 속도: 약 25-30초/상품

## 📝 주의사항

⚠️ **절대 수정 금지**: `config.py`는 AI가 수정하지 않음
⚠️ **범용성 우선**: 특정 사이트 하드코딩 금지
⚠️ **안정성 우선**: 기존 구조 보존 중요

## 🔄 백업 및 복구

- 모든 이전 버전은 `archived/` 폴더에 보관
- 테스트 파일은 `test/` 폴더에서 확인 가능
- Git을 통한 버전 관리 활용

---

**개발자**: Claude AI Agent  
**최종 업데이트**: 2025-06-25  
**버전**: v2.3 (Production Ready)
