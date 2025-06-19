import time
from datetime import datetime
import ssl
import requests
from bs4 import BeautifulSoup as bs
import os
import shutil
import re
import openpyxl
from PIL import Image, ImageDraw, ImageFont
import urllib.request
import math

# 테스트할 상품 개수 (선택자 검증용)
TEST_PRODUCTS = 3

# ===================== 사용자 편의 테스트 모드 =====================
# 테스트 모드가 True면 상품을 TEST_PRODUCT_COUNT개만 추출하고, 엑셀도 정상 생성됨
# False면 start_page ~ end_page 전체 페이지 크롤링
TEST_MODE = False  # 테스트 모드 (True: 일부 상품만 추출, False: 전체 페이지 크롤링)
TEST_PRODUCT_COUNT = 10  # 테스트 모드에서 추출할 상품 개수

# ===================== 기본 설정 =====================
code = "littlebigkids"  # 브랜드영문
brandname = "리틀빅키즈"  # 브랜드한글
category = "39130000"  # 카테고리 구분 (학교체육:39130000)
price_increase_rate = 1.1  # 가격 인상률 (예: 10% 인상 1.1)
start_page = 1  # 시작 페이지 번호
end_page = 9 # 끝 페이지 번호
minimum_price = 10000  # 최소 가격 설정
use_login = False  # 로그인 사용 여부
login_url = 'https://littlebigkids.kr/'  # 로그인 페이지 URL
catalog_url_template = 'https://littlebigkids.kr/product/list.html?cate_no=24&page={page}'  # 카탈로그 페이지 URL 템플릿
product_base_url = 'https://littlebigkids.kr/'  # 제품 페이지 베이스 URL
base_url2= ''  # (필요시만 사용) 2차 이동시 썸네일이나 상세페이지 주소를 위한 도메인
login_credentials = {
    'userid': 'flowing',
    'password': 'q6160q6160q'
}



# 상품 링크 패턴 설정 (사이트별 맞춤 설정)
PRODUCT_LINK_PATTERN = '/product/detail.html'  # littlebigkids.kr용 (개별 상품 페이지만)

# final_analyzer.py에서 사용할 설정
LOGIN_REQUIRED = use_login
MAIN_URL = login_url if use_login else product_base_url
GALLERY_URL = catalog_url_template.format(page=1)
SAMPLE_PRODUCT_URL = product_base_url + "product/경찰서무대배경/163/"
USERNAME = login_credentials['userid']
PASSWORD = login_credentials['password']
SITE_NAME = code

# 작업 시작 시간 기록
now = datetime.now()  # 현재 시간을 기록
start_time = time.time()  # 작업 시작 시간을 기록
print("택수님 ! 작업을 시작할께요.. 조금만 기다려주세요*^.^*")  # 작업 시작 알림
tdate = now.strftime("%Y%m%d%H%M")

# SSL 오류 방지 설정
ssl._create_default_https_context = ssl._create_unverified_context

# 폴더 생성
base_path = f'C:/Users/ME/Pictures/{tdate}{code}'
thumbnail_path = f'{base_path}/cr'
output_path = f'{base_path}/output'
if os.path.exists(base_path):
    shutil.rmtree(base_path)
os.makedirs(thumbnail_path)
os.makedirs(output_path)

# 엑셀 파일 설정
wb = openpyxl.Workbook()
sheet = wb.active
sheet.append([
    "업체상품코드", "모델명", "브랜드", "제조사", "원산지", "상품명", "홍보문구", "요약상품명", "카테고리코드", "사용자분류명", "한줄메모", "시중가", "원가", "표준공급가", "판매가", "배송방법", "배송비", "구매수량", "과세여부", "판매수량", "이미지1URL", "이미지2URL", "이미지3URL", "이미지4URL", "GIF생성", "이미지6URL", "이미지7URL", "이미지8URL", "이미지9URL", "이미지10URL", "추가정보입력사항", "옵션구분", "선택옵션", "입력형옵션", "추가구매옵션", "상세설명", "추가상세설명", "광고/홍보", "제조일자", "유효일자", "사은품내용", "키워드", "인증구분", "인증정보", "거래처", "영어상품명", "중국어상품명", "일본어상품명", "영어상세설명", "중국어상세설명", "일본어상세설명", "상품무게", "영어키워드", "중국어키워드", "일본어키워드", "생산지국가", "전세계배송코드", "사이즈", "포장방법", "표준산업코드", "미성년자구매", "상품상세코드", "상품상세1", "상품상세2", "상품상세3", "상품상세4", "상품상세5", "상품상세6", "상품상세7", "상품상세8", "상품상세9", "상품상세10", "상품상세11", "상품상세12", "상품상세13", "상품상세14", "상품상세15", "상품상세16", "상품상세17", "상품상세18", "상품상세19", "상품상세20", "상품상세21", "상품상세22", "상품상세23", "상품상세24", "상품상세25", "상품상세26"
])
