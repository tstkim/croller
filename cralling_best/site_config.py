# 선택자 탐지용 크롤러 설정
# 아래 정보만 입력하고 크롤러를 실행하세요

# ===========================================
# 사이트 정보 (필수)
# ===========================================

# 1. 메인페이지 주소 (로그인이 필요하면 로그인 페이지 주소)
MAIN_URL = "https://dawoori-sports.kr/intro/member_only?return_url=%2F"

# 2. 상품 갤러리 페이지 주소
GALLERY_URL = "https://dawoori-sports.kr/goods/catalog?page=2&searchMode=catalog&category=c0019&per=20&filter_display=lattice&code=0019&auto=1&popup=&iframe="

# 3. 상품 개별 페이지 샘플 주소 (1개만)
SAMPLE_PRODUCT_URL = "https://dawoori-sports.kr/goods/view?no=617"


# ===========================================
# 로그인 정보 (필요시만 입력)
# ===========================================

# 로그인이 필요한가요? (True 또는 False)
LOGIN_REQUIRED = True

# 로그인 정보 (LOGIN_REQUIRED가 True인 경우에만 입력)
USERNAME = "flowing"
PASSWORD = "q6160q6160q"


# ===========================================
# 테스트 설정
# ===========================================

# 테스트할 상품 개수 (선택자 검증용)
TEST_PRODUCTS = 3

# 사이트 이름 (결과 파일명에 사용)
SITE_NAME = "dawoori"
