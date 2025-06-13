# 🎯 선택자 탐지 도구

## 🚀 목적
- **주목적**: 웹사이트 상품 정보 선택자 자동 탐지
- **부목적**: 선택자 정확성을 3개 상품으로 검증
- **결과**: JSON 파일 1개 출력

## 📋 사용법

### 1. 라이브러리 설치
```bash
pip install -r requirements.txt
playwright install
```

### 2. 설정 입력 (`site_config.py`)
```python
MAIN_URL = "https://협력업체.com"                    # 메인페이지
GALLERY_URL = "https://협력업체.com/products"         # 상품목록페이지  
SAMPLE_PRODUCT_URL = "https://협력업체.com/product/123"  # 샘플상품페이지

# 로그인 필요시
LOGIN_REQUIRED = True
USERNAME = "your_id"
PASSWORD = "your_password"
```

### 3. 실행
```bash
python selector_finder.py
```

## 📊 출력 결과

### JSON 파일 구조
```json
{
  "site_info": {
    "site_name": "테스트사이트",
    "main_url": "https://협력업체.com",
    "scan_date": "2025-06-10T14:30:25"
  },
  "selectors": {
    "상품명": "h1.product-title",
    "가격": ".price-current",
    "선택옵션": "select.option-select",
    "썸네일": ".product-image img",
    "상세페이지": ".product-detail"
  },
  "validation_data": [
    {
      "상품1": {
        "url": "https://협력업체.com/product/123",
        "data": {
          "상품명": "삼성 갤럭시 S24",
          "가격": "1,200,000원",
          "선택옵션": "3개 옵션",
          "썸네일": "https://img.com/galaxy.jpg",
          "상세페이지": "1,250자 상세설명"
        },
        "html": {
          "선택옵션": "<select class='option-select'><option>블랙</option></select>",
          "썸네일": "<img src='https://img.com/galaxy.jpg' alt='갤럭시'>",
          "상세페이지": "<div class='product-detail'>상세 설명...</div>"
        }
      }
    }
  ]
}
```

### 콘솔 출력
```
🎯 탐지된 선택자:
   상품명: h1.product-title
   가격: .price-current
   선택옵션: select.option-select
   썸네일: .product-image img
   상세페이지: .product-detail

🧪 검증 완료: 3개 상품
📄 상세 결과는 JSON 파일을 확인하세요.
```

## ⚡ 특징

✅ **로그인 지원** - 로그인 필요한 사이트도 처리  
✅ **자동 선택자 탐지** - 휴리스틱 방식으로 선택자 발견  
✅ **JSON 결과** - 선택자 + 검증 데이터 모두 포함  
✅ **빠른 검증** - 3개 상품으로 빠르게 테스트  

---

🎉 **간단하고 실용적인 선택자 탐지 도구!** 🔍
