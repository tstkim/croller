# 범용 쇼핑몰 크롤러 개발 규칙

## 프로젝트 개요

- **목적**: 어떤 쇼핑몰이든 최소 설정으로 크롤링 가능한 범용 크롤러
- **기술스택**: Python + Playwright + BeautifulSoup + PIL + OpenPyXL
- **결과물**: 엑셀파일, 썸네일이미지(_cr.jpg), 상세페이지이미지(10개 조각)
- **핵심원칙**: 범용성 > 특정사이트 최적화, 하드코딩 최소화

## 핵심 아키텍처

### 4개 핵심 모듈 의존성
```
config.py → final_analyzer_universal.py → perfect_result_*.json → main.py
```

- **config.py**: 사이트별 설정 (유일한 사이트 특화 설정 파일)
- **final_analyzer_universal.py**: AI 기반 선택자 자동 탐지
- **smart_detector_final.py**: 지능형 선택자 탐지 보조
- **main.py**: 실제 크롤링 및 결과물 생성

### 필수 실행 순서
1. config.py 설정 확인
2. `python final_analyzer_universal.py` 실행
3. perfect_result_*.json 파일 생성 확인
4. `python main.py` 실행

## 범용성 유지 규칙

### 절대 금지사항
- **사이트별 하드코딩 추가 금지** - 특정 쇼핑몰만을 위한 선택자나 로직 작성 금지
- **사용자가 하드코딩 필요성을 명시한 경우에만 문의**
- **범용 로직을 특정 사이트에 맞춰 변경 금지**

### 허용되는 사이트별 설정
- config.py의 `PRODUCT_LINK_PATTERN` 변경
- config.py의 브랜드명, URL, 로그인 정보 변경
- config.py의 페이지 범위, 가격 설정 변경

## 파일별 수정 가이드라인

### config.py 수정 시
- **허용**: PRODUCT_LINK_PATTERN, 브랜드명, URL, 로그인정보, 페이지범위
- **금지**: 기본 구조 변경, 새로운 사이트별 하드코딩 변수 추가
- **필수 후속작업**: final_analyzer_universal.py의 PRODUCT_LINK_PATTERN 동기화

### final_analyzer_universal.py 수정 시  
- **허용**: 탐지 로직 개선, 새로운 범용 선택자 패턴 추가
- **금지**: perfect_result_*.json의 키 이름 변경
- **필수 검증**: perfect_result_*.json 생성 및 키 확인

### smart_detector_final.py 수정 시
- **허용**: base_selectors에 범용 선택자 추가, 탐지 알고리즘 개선
- **금지**: 특정 사이트만을 위한 선택자 추가
- **필수 동기화**: main.py의 선택자 사용 부분과 일치성 확인

### main.py 수정 시
- **절대 금지**: 엑셀 헤더 순서 변경, sheet.append([...]) 인덱스 변경
- **절대 금지**: 썸네일 경로(_cr.jpg), 상세이미지 경로(output/*.jpg) 변경
- **절대 금지**: 이미지 크기 규격 변경 (600x600 캔버스, 400x400 상품이미지)
- **허용**: 로그 메시지 개선, 오류 처리 강화, 성능 최적화

## 다중 파일 동기화 규칙

### config.py 수정 시 동시 수정 필요
- final_analyzer_universal.py의 PRODUCT_LINK_PATTERN 동기화

### 선택자 관련 수정 시 동시 확인 필요
- smart_detector_final.py의 base_selectors
- main.py의 선택자 사용 부분
- perfect_result_*.json의 키 일치성

### 이미지 처리 로직 수정 시 동시 확인 필요
- main.py의 썸네일 생성 부분
- main.py의 상세이미지 처리 부분
- 이미지 경로 및 명명 규칙 일치성

## 코딩 표준

### 파이썬 코드 규칙
- **절대 금지**: 이모지 사용 (인코딩 오류 방지)
- **로그 메시지**: [DEBUG], [INFO], [ERROR], [WARNING] 접두사 사용
- **예외 처리**: 모든 네트워크 요청 및 파일 작업에 try-catch 필수
- **변수명**: 기존 명명 규칙 유지 (product_name, adjusted_price 등)

### JSON 파일 규칙
- **perfect_result_*.json 키 고정**: '상품리스트', '상품명', '가격', '선택옵션', '썸네일', '상세페이지'
- **키 이름 변경 절대 금지**
- **새로운 키 추가는 허용하되 기존 키는 유지**

## 구체적인 DO/DON'T 예시

### ✅ 허용되는 작업
```python
# config.py에서 사이트별 설정 변경
PRODUCT_LINK_PATTERN = '/item/view.html'  # OK
brandname = "새브랜드"  # OK

# smart_detector_final.py에서 범용 선택자 추가
base_selectors = {
    '상품명': '.name, h1, h2, .title, .product-title',  # OK
}

# main.py에서 로그 개선
print(f"[INFO] 상품 처리 완료: {product_name}")  # OK
```

### ❌ 금지되는 작업
```python
# 특정 사이트 하드코딩
if "kidgym" in page.url:  # 금지
    selector = ".kidgym-specific"

# 엑셀 헤더 순서 변경
sheet.append([product_name, adjusted_price, ...])  # 금지 - 순서 바뀜

# JSON 키 이름 변경
result = {"product_name": ...}  # 금지 - "상품명"을 사용해야 함

# 이모지 사용
print("상품 처리 완료! 🎉")  # 금지
```

## AI 의사결정 우선순위

### 충돌 상황 시 우선순위
1. **범용성 > 특정 사이트 최적화**
2. **자동 탐지 > 수동 선택자 설정**  
3. **기존 구조 보존 > 새로운 기능 추가**
4. **안정성 > 성능 최적화**

### 애매한 요청 처리 방법
- "특정 사이트만을 위한" 요청 → 범용 해결책 제안 후 하드코딩 필요성 문의
- "구조 변경" 요청 → 결과물에 영향 여부 먼저 확인
- "새로운 기능" 요청 → 기존 기능 영향도 분석 후 진행

## 테스트 및 검증 절차

### 필수 검증 단계
1. **config.py 수정 후**: `python final_analyzer_universal.py` 실행 테스트
2. **선택자 수정 후**: perfect_result_*.json 생성 및 키 확인
3. **main.py 수정 후**: 전체 워크플로우 테스트 (final_analyzer → main)
4. **결과물 검증**: 엑셀 파일, 썸네일, 상세이미지 정상 생성 확인

### 오류 발생 시 대응
- **선택자 탐지 실패**: smart_detector의 기본 선택자로 fallback
- **이미지 다운로드 실패**: 로그 기록 후 다음 상품 진행
- **로그인 실패**: 비로그인 모드로 자동 전환
- **심각한 오류**: 이전 버전으로 즉시 롤백

## 결과물 품질 보장

### 필수 결과물
- **엑셀파일**: C:/Users/ME/Pictures/{tdate}{code}.xlsx
- **썸네일**: {base_path}/cr/{image_counter}_cr.jpg
- **상세이미지**: {base_path}/output/{image_counter:03}_{1-10:03}.jpg

### 품질 기준
- 썸네일: 600x600 캔버스, 400x400 상품이미지, S2B 배지 포함
- 상세이미지: 10개 조각으로 균등 분할
- 엑셀: 기존 헤더 순서 및 형식 완전 준수

---

**⚠️ 경고**: 이 규칙들은 범용 크롤러의 핵심 원칙입니다. 위반 시 전체 시스템의 범용성이 손상될 수 있습니다.
