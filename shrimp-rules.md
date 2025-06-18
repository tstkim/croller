# Development Guidelines

## 프로젝트 개요

### 프로젝트 정보
- **프로젝트명**: E-commerce Crawler (croller)
- **주요 기능**: 웹사이트 상품 정보 크롤링 및 엑셀 출력
- **기술 스택**: Python, Playwright, BeautifulSoup4, Pillow, openpyxl
- **작업 흐름**: 선택자 탐지 → 검증 → 크롤링 실행

### 핵심 파일 구조
- `smart_detector_final.py`: 웹사이트 선택자 자동 탐지
- `final_analyzer_universal.py`: 선택자 검증 및 perfect_result 생성
- `main.py`: 실제 크롤링 실행
- `config.py`: 프로젝트 설정
- `login_manager.py`: 로그인 처리
- `perfect_result_*.json`: 검증된 선택자 저장

## 코드 수정 규칙

### 선택자 사용 규칙
- **perfect_result_*.json의 선택자는 절대 수정 금지**
- **main.py에서 선택자 재탐지 코드 추가 금지**
- 최신 perfect_result 파일 사용: `max(json_files, key=os.path.getmtime)`
- 선택자 키: 상품리스트, 상품링크, 상품명, 가격, 선택옵션, 썸네일, 상세페이지

### 이미지 처리 규칙
- **썸네일 저장**: `{thumbnail_path}/{timestamp}_{image_counter}_cr.jpg`
- **상세페이지 저장**: `{output_path}/{timestamp}_{image_counter:03}_{i:03}.jpg`
- **임시 파일 규칙**:
  - 썸네일 임시 파일: `*_temp.jpg` → 사용 후 즉시 삭제
  - 상세 임시 파일: `detail_*_*.jpg` → 사용 후 즉시 삭제
- **상세 이미지는 반드시 10개로 분할**

### 경로 관리 규칙
- **기본 경로**: `C:/Users/ME/Pictures/{tdate}{code}/`
- **썸네일 폴더**: `{base_path}/cr/`
- **출력 폴더**: `{base_path}/output/`
- **엑셀 저장**: `C:/Users/ME/Pictures/{tdate}{code}.xlsx`
- **경로 생성시 기존 폴더 삭제 후 재생성**

## 기능 구현 표준

### 가격 처리
- 정규식으로 숫자만 추출: `re.sub(r'[^\d]', '', price)`
- 가격 인상률 적용: `math.ceil((original_price * price_increase_rate) / 100) * 100`
- 최소 가격 체크: `if adjusted_price < minimum_price: adjusted_price = "가격 정보 없음"`

### 옵션 처리
- `is_valid_option()` 함수로 유효성 검사 필수
- 제외 패턴: '선택', '배송비', '택배' 등
- 옵션 포맷: `{option_name}=={price_change}=10000=0=0=0=`
- 옵션 타입: 옵션이 있으면 "SM", 없으면 빈 문자열

### 로깅 규칙
- 모든 로그는 `app.log` 파일에 기록
- 로그 레벨: `logging.INFO`
- 디버그 출력: `print(f"[DEBUG] ...")` 형식 사용
- 에러 로깅: `logging.error()` 와 `print(f"[ERROR] ...")` 병행

## 워크플로우 표준

### 크롤링 순서
1. perfect_result_*.json에서 선택자 로드
2. 로그인 처리 (use_login=True인 경우)
3. 페이지별 상품 리스트 크롤링
4. 개별 상품 페이지 방문
5. 상품 정보 추출 (이름, 가격, 옵션)
6. 이미지 다운로드 및 처리
7. 엑셀 데이터 추가
8. 임시 파일 정리

### 중복 방지
- `visited_links` set으로 URL 중복 체크
- 상품 리스트에서 고유 링크만 추출
- 동일 요소 중복 제거: `id(product)` 사용

## AI 의사결정 표준

### 파일 수정시 우선순위
1. **최우선**: 이미지 저장 경로 문제 해결
2. **높음**: 임시 파일 삭제 로직 추가
3. **중간**: 로깅 개선
4. **낮음**: 코드 리팩토링

### 문제 해결 접근법
- 상세페이지 이미지 미저장 → output_path 확인 및 경로 수정
- 썸네일 중복 저장 → 임시 파일 삭제 로직 확인
- 선택자 오류 → perfect_result 재생성 (main.py 수정 금지)

## 금지 사항

### 절대 금지
- **perfect_result의 선택자 수정**
- **main.py에 선택자 재탐지 코드 추가**
- **config.py의 기본 경로 구조 변경**
- **엑셀 헤더 순서 변경**

### 조건부 금지
- 로그인 로직 수정 (use_login=False일 때)
- 가격 계산 로직 변경 (config 설정값 우선)
- 이미지 분할 개수 변경 (항상 10개)

## 주요 파일 상호작용

### 의존성 체인
```
config.py → main.py → perfect_result_*.json
         ↓
    login_manager.py (선택적)
```

### 데이터 흐름
```
웹사이트 → BeautifulSoup 파싱 → 선택자 적용 → 데이터 추출
        ↓                                    ↓
    이미지 다운로드                      엑셀 데이터
        ↓                                    ↓
    PIL 이미지 처리                     openpyxl 저장
```

### 동시 수정 필요 파일
- 선택자 변경시: smart_detector_final.py → final_analyzer_universal.py (main.py는 수정 금지)
- 경로 변경시: config.py → main.py
- 로그인 변경시: config.py → login_manager.py → main.py

## 테스트 및 검증

### 필수 테스트
- 이미지 저장 경로 존재 확인
- 임시 파일 삭제 확인
- 엑셀 파일 생성 확인
- 로그 파일 기록 확인

### 디버깅 체크리스트
- `[DEBUG]` 출력 확인
- `app.log` 에러 메시지 확인
- 이미지 폴더 구조 확인
- 엑셀 데이터 무결성 확인