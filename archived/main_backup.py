from config import *
from playwright.sync_api import sync_playwright
from PIL import ImageFont
import logging
import urllib.request
from PIL import Image, ImageDraw
import math
import time
import glob
import os
import json
from urllib.parse import urljoin
import requests
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

class ImageDownloadOptimizer:
    """이미지 다운로드 성능 최적화 클래스"""
    
    def __init__(self, max_workers=4, timeout=15):
        self.session = requests.Session()
        # 키드짐 사이트에 맞는 헤더 설정
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://kidgymb2b.co.kr/',
            'Accept': 'image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'same-origin'
        })
        self.max_workers = max_workers
        self.timeout = timeout
        self.verified_urls = {}  # URL -> (valid, file_size) 캐시
        self.lock = Lock()
        
    def check_image_size_parallel(self, urls):
        """병렬로 이미지 크기 검증"""
        print(f"[PERF] 병렬 이미지 크기 검증 시작: {len(urls)}개 URL")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {executor.submit(self._check_single_image, url): url for url in urls}
            results = {}
            
            for future in future_to_url:
                url = future_to_url[future]
                try:
                    results[url] = future.result()
                except Exception as e:
                    print(f"[ERROR] 이미지 크기 검증 실패 {url}: {e}")
                    results[url] = (False, 0)
                    
        print(f"[PERF] 병렬 검증 완료: {sum(1 for valid, _ in results.values() if valid)}개 유효")
        return results
    
    def _check_single_image(self, url):
        """단일 이미지 크기 검증 (캐시 활용)"""
        with self.lock:
            if url in self.verified_urls:
                return self.verified_urls[url]
        
        try:
            # HEAD 요청으로 파일 크기 확인
            head_response = self.session.head(url, timeout=self.timeout, allow_redirects=True)
            
            if head_response.status_code == 200:
                content_length = head_response.headers.get('content-length')
                if content_length:
                    file_size = int(content_length)
                    # 50KB 이상만 유효로 판단
                    is_valid = file_size >= 50000
                    
                    with self.lock:
                        self.verified_urls[url] = (is_valid, file_size)
                    
                    return (is_valid, file_size)
                    
        except Exception as e:
            print(f"[DEBUG] HEAD 요청 실패 {url}: {e}")
            
        # HEAD 실패 시 기본값
        with self.lock:
            self.verified_urls[url] = (False, 0)
        return (False, 0)
    
    def download_image_optimized(self, url, save_path):
        """최적화된 이미지 다운로드"""
        try:
            response = self.session.get(url, timeout=self.timeout, stream=True)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"[PERF] 최적화 다운로드 성공: {save_path}")
            return True
            
        except Exception as e:
            print(f"[ERROR] 최적화 다운로드 실패 {url}: {e}")
            # fallback to urllib
            try:
                urllib.request.urlretrieve(url, save_path)
                print(f"[FALLBACK] urllib 다운로드 성공: {save_path}")
                return True
            except Exception as e2:
                print(f"[ERROR] fallback 다운로드도 실패: {e2}")
                return False
    
    def close(self):
        """세션 정리"""
        self.session.close()
        print("[PERF] ImageDownloadOptimizer 세션 정리 완료")

def is_valid_option(text):
    """유효한 선택옵션인지 판단"""
    if not text:
        return False
    
    text_lower = text.lower().strip()
    
    # 완전히 제외할 패턴들 (정확히 일치하는 경우만)
    exact_exclude = [
        '선택', '-- 선택 --', '옵션선택', '옵션을 선택해주세요',
        '- 무게 선택 -', '- 색상 선택 -', '- 사이즈 선택 -',
        '- 종류 선택 -', '- 크기 선택 -'
    ]
    
    # 포함된 경우 제외할 패턴들
    partial_exclude = [
        '택배(주문 시 결제)', '배송비', '주문 시 결제', '택배'
    ]
    
    # 정확히 일치하는 제외 패턴 확인
    for pattern in exact_exclude:
        if text.strip() == pattern or text_lower == pattern.lower():
            return False
    
    # 부분 일치하는 제외 패턴 확인
    for pattern in partial_exclude:
        if pattern.lower() in text_lower:
            return False
    
    return True

# 로그 설정
logging.basicConfig(filename='app.log', level=logging.INFO)

# 유효한 상세 이미지인지 판단하는 함수
def is_valid_detail_image(url):
    """유효한 상세 이미지인지 판단"""
    if not url:
        return False
    
    url_lower = url.lower()
    
    # 제외할 패턴들
    exclude_patterns = [
        'logo', 'icon', 'btn', 'button', 'menu', 'nav', 
        'arrow', 'quick', 'zzim', 'wishlist',
        'banner', 'common', 'header', 'footer',
        'popup', 'close', 'search', 'cart',
        'sns', 'facebook', 'twitter', 'kakao',
        'top_btn', 'scroll', 'floating',
        '_wg/', 'detail_img_info', 'delivery_info',
        'exchange_info', 'return_info', 'notice_info'
    ]
    
    for pattern in exclude_patterns:
        if pattern in url_lower:
            # print(f"[DEBUG] '{pattern}' 패턴 발견, 이미지 제외: {url}")  # 디버깅 메시지 주석처리
            return False
    
    # 포함되어야 할 패턴들
    include_patterns = [
        'detail', 'content', 'description', 'product',
        'item', 'goods', 'view', 'main', 'sub'
    ]
    has_include = any(pattern in url_lower for pattern in include_patterns)
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
    has_image_ext = any(ext in url_lower for ext in image_extensions)
    return has_include or has_image_ext

def get_fitting_font(draw, text, max_width, font_path, max_font_size=65, min_font_size=30):
    """상품명 길이에 따라 글자 크기를 동적으로 조정 (최소 30pt)"""
    font_size = max_font_size
    while font_size >= min_font_size:
        try:
            font = ImageFont.truetype(font_path, font_size)
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
            except AttributeError:
                text_width, _ = draw.textsize(text, font=font)
            if text_width <= max_width:
                return font
        except Exception as e:
            print(f"[ERROR] 폰트 사이즈 {font_size}에서 오류: {e}")
        font_size -= 2
    return ImageFont.truetype(font_path, min_font_size)

# Playwright를 사용한 웹드라이버 설정 및 시작
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)  # 헤드리스 모드로 변경
    page = browser.new_page()
    
    # 성능 최적화 객체 초기화
    download_optimizer = ImageDownloadOptimizer(max_workers=4, timeout=15)
    print("[PERF] 이미지 다운로드 최적화 시스템 초기화 완료")
    
    # 데스크탑 모드로 설정
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.set_extra_http_headers({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    })
    
    # 이미지 파일명을 고유하게 만들기 위한 카운터
    image_counter = 1

    start_time = time.time()
    
    # 성능 측정 변수들
    json_products_count = 0
    fallback_products_count = 0
    json_processing_time = 0
    fallback_processing_time = 0
    network_requests_saved = 0

    try:
        # 최신 perfect_result_*.json 파일에서 선택자 읽기
        json_files = glob.glob("perfect_result_*.json")
        if not json_files:
            raise FileNotFoundError("perfect_result_*.json 파일이 없습니다.")
        latest_json = max(json_files, key=os.path.getmtime)
        with open(latest_json, "r", encoding="utf-8") as f:
            data = json.load(f)
            selectors = data["선택자"]
            extracted_products = data.get("추출데이터", [])

        if use_login:
            try:
                # 로그인 페이지로 이동
                page.goto(login_url)
                # 선택자 json에서 로그인 selector 사용
                id_selector = selectors.get('로그인_아이디_선택자')
                pw_selector = selectors.get('로그인_비밀번호_선택자')
                btn_selector = selectors.get('로그인_버튼_선택자')
                if not id_selector or not pw_selector:
                    raise Exception('로그인 selector 정보가 부족합니다.')
                page.wait_for_selector(id_selector, timeout=5000)
                page.wait_for_selector(pw_selector, timeout=5000)
                # 디버깅: 선택자에 해당하는 input 개수 출력
                id_inputs = page.query_selector_all(id_selector)
                pw_inputs = page.query_selector_all(pw_selector)
                print(f"[DEBUG] id_selector matches {len(id_inputs)} elements")
                print(f"[DEBUG] pw_selector matches {len(pw_inputs)} elements")
                page.fill(id_selector, login_credentials['userid'])
                page.fill(pw_selector, login_credentials['password'])
                if btn_selector:
                    page.click(btn_selector)
                else:
                    page.keyboard.press('Enter')
                page.wait_for_timeout(5000)
                
                # 로그인 성공 여부 확인
                if "login" in page.url.lower() or "로그인" in page.content():
                    raise Exception("로그인 실패 - 로그인 페이지에 여전히 있음")
                
                logging.info("로그인 성공")
                print("[DEBUG] 로그인 성공")
                print(f"[DEBUG] 로그인 후 URL: {page.url}")
            except Exception as e:
                logging.error(f"로그인 중 오류 발생: {e}")
                print(f"[DEBUG] 로그인 실패: {e}")
                print(f"[DEBUG] 현재 페이지 URL: {page.url}")
                print(f"[DEBUG] 페이지 제목: {page.title()}")
                page.screenshot(path="login_error.png")

        visited_links = set()
        seen_product_names = set()  # 상품명 중복 검증용 (유효한 상품명만 추가)
        product_infos = []  # (image_counter, product_name, adjusted_price, product_link, ...) 저장용
        
        def is_valid_product_name(name):
            """상품명 유효성 검증 함수"""
            if not name or not name.strip():
                return False
            
            # 기본값 또는 오류 메시지 제외
            invalid_patterns = [
                '상품명을 찾을 수 없습니다', '제품명 없음', '상품명 오류',
                '좋아요', '장바구니', '버튼', '클릭', '메뉴', '네비게이션',
                # 키드짐 특화 UI 요소
                '볼&골대', '댄스&창', '댄스&소셜', '네트게임', '타겟게임',
                '흔바테감', '네트리더', '게임도구', '음향기기', '무대배경',
                '교구', '체육용품', '놀이기구', '무대도구'
            ]
            
            # 너무 짧거나 긴 상품명 제외
            if len(name.strip()) < 2 or len(name.strip()) > 100:
                return False
                
            # 유효하지 않은 패턴 포함 여부 확인
            for pattern in invalid_patterns:
                if pattern.lower() in name.lower():
                    return False
                    
            return True

        # JSON 추출데이터가 있으면 우선 사용, 없으면 기존 페이지 크롤링 로직 사용
        if extracted_products:
            print(f"[JSON_DATA] {len(extracted_products)}개 상품의 JSON 추출데이터 발견, JSON 데이터 우선 사용")
            
            # JSON 데이터 기반 상품 처리
            json_start_time = time.time()
            for product_data in extracted_products:
                try:
                    product_start_time = time.time()
                    product_url = product_data.get("url", "")
                    if not product_url:
                        print("[WARNING] JSON 데이터에 url이 없습니다.")
                        continue
                    
                    print(f"[JSON_DATA] 상품 처리 시작: {product_url}")
                    
                    # 중복 링크 방지
                    if product_url in visited_links:
                        continue
                    visited_links.add(product_url)
                    
                    # 상품페이지 이동 (이미지 로드를 위해)
                    try:
                        page.goto(product_url)
                        page.wait_for_timeout(2000)
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(1000)
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(2000)
                    except Exception as e:
                        print(f"[ERROR] 상품 페이지 이동 중 오류: {e}")
                        continue
                    
                    # JSON 데이터에서 상품 정보 직접 가져오기
                    product_name = product_data.get("상품명", "상품명을 찾을 수 없습니다.")
                    price_text = product_data.get("가격", "0원")
                    options = product_data.get("선택옵션", [])
                    thumbnail_url = product_data.get("썸네일", "")
                    detail_img_urls = product_data.get("상세페이지", [])
                    
                    print(f"[JSON_DATA] 상품정보 - 이름: {product_name}, 가격: {price_text}, 상세이미지: {len(detail_img_urls)}개")
                    
                    # 가격 파싱 및 처리 (기존 로직과 동일)
                    try:
                        # 가격에서 숫자만 추출
                        import re
                        clean_price = re.sub(r'[^\d]', '', price_text)
                        if clean_price and clean_price.isdigit():
                            original_price = float(clean_price)
                            adjusted_price = math.ceil((original_price * price_increase_rate) / 100) * 100
                            if adjusted_price < minimum_price:
                                print(f"[SKIP] minimum_price({minimum_price}) 미달: {adjusted_price}원")
                                continue
                            else:
                                adjusted_price = int(adjusted_price)
                                print(f"[JSON_DATA] 가격 처리 성공: {adjusted_price}")
                        else:
                            adjusted_price = "가격 정보 없음"
                            print(f"[WARNING] JSON 데이터에서 유효한 가격을 찾을 수 없음: {price_text}")
                    except Exception as e:
                        adjusted_price = "가격 정보 없음"
                        print(f"[ERROR] JSON 가격 처리 중 오류: {e}")
                    
                    # 옵션 처리 (기존 로직 참조)
                    try:
                        option_string = []
                        if options and len(options) > 0:
                            for option_name in options:
                                if option_name and option_name.strip() and not option_name.startswith('-'):
                                    formatted_option = f"{option_name}==0=10000=0=0=0="
                                    option_string.append(formatted_option)
                        
                        if not option_string:
                            option_string.append("없음")
                        
                        formatted_options = "\\n".join(option_string)
                        option_string = "[필수선택]\\n" + formatted_options
                        
                        if option_string.count("10000") == 1:
                            option_string = ""
                    except Exception as e:
                        option_string = ""
                        print(f"[ERROR] JSON 옵션 처리 중 오류: {e}")
                    
                    # 이미지 다운로드 및 처리를 위한 ImageDownloadOptimizer 사용
                    try:
                        # 썸네일 다운로드
                        if thumbnail_url:
                            thumbnail_result = download_optimizer.download_and_process_thumbnail(
                                thumbnail_url, image_counter, product_name
                            )
                            if thumbnail_result:
                                print(f"[JSON_DATA] 썸네일 다운로드 성공: {image_counter}_cr.jpg")
                            else:
                                print(f"[WARNING] JSON 썸네일 다운로드 실패: {thumbnail_url}")
                        
                        # 상세이미지 다운로드
                        if detail_img_urls:
                            detail_result = download_optimizer.download_and_process_detail_images(
                                detail_img_urls, image_counter, product_name
                            )
                            if detail_result:
                                print(f"[JSON_DATA] 상세이미지 다운로드 성공: {len(detail_img_urls)}개")
                            else:
                                print(f"[WARNING] JSON 상세이미지 다운로드 실패")
                        
                        # 엑셀에 데이터 추가 (기존 format과 동일)
                        product_infos.append((image_counter, product_name, adjusted_price, product_url, option_string))
                        sheet.append([image_counter, product_name, adjusted_price, product_url, option_string])
                        
                        print(f"[JSON_DATA] 저장: {image_counter}_cr.jpg | {product_name} | {adjusted_price} | {product_url}")
                        image_counter += 1
                        
                        # 성능 지표 업데이트
                        json_products_count += 1
                        product_processing_time = time.time() - product_start_time
                        json_processing_time += product_processing_time
                        network_requests_saved += 5  # 대략적으로 상품당 5번의 네트워크 요청 절약 추정
                        
                        print(f"[PERF] JSON 상품 처리 시간: {product_processing_time:.2f}초, 누적 절약 요청: {network_requests_saved}개")
                        
                        # 상품 개수 제한 (테스트 모드)
                        if TEST_MODE and image_counter > TEST_PRODUCT_COUNT:
                            print(f"[INFO] TEST_MODE: {TEST_PRODUCT_COUNT}개 상품만 추출 후 중단합니다.")
                            break
                            
                    except Exception as e:
                        print(f"[ERROR] JSON 이미지 처리 중 오류: {e}")
                        continue
                    
                except Exception as e:
                    print(f"[ERROR] JSON 데이터 상품 처리 중 오류: {e}")
                    continue
        else:
            print("[FALLBACK_DOM] JSON 추출데이터가 없습니다. 기존 페이지 크롤링 로직 사용")

        # 페이지 반복 처리 (JSON 데이터가 없는 경우에만 실행) - 테스트를 위해 임시 비활성화
        if False:  # not extracted_products:
            fallback_start_time = time.time()
            for page_number in range(start_page, end_page + 1):
                try:
                    url = catalog_url_template.format(page=page_number)
                    print(f"[DEBUG] 카탈로그 URL: {url}")
                    page.goto(url)
                    page.wait_for_timeout(3000)
                    
                    # 스크롤을 아래로 내리면서 상품 로드 대기
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(3000)
                    
                    soup = bs(page.content(), 'html.parser')
                    base_url = product_base_url

                    # 제품 리스트 선택자 적용 (perfect_result에서 가져온 선택자 직접 사용)
                    product_list_selector = selectors.get("상품리스트")
                    print(f"[DEBUG] 사용할 상품리스트 선택자: {product_list_selector}")
                
                    # perfect_result의 선택자로 상품 찾기
                    try:
                        product_list = soup.select(product_list_selector)
                        print(f"[FALLBACK_DOM] 선택자로 {len(product_list)}개 상품 발견")
                        
                        # 간소화된 fallback 처리 (테스트용)
                        if len(product_list) == 0:
                            print("[FALLBACK_DOM] 상품을 찾지 못했습니다.")
                        else:
                            fallback_products_count += len(product_list)
                            print(f"[FALLBACK_DOM] {len(product_list)}개 상품 처리 완료")
                            
                    except Exception as e:
                        print(f"[FALLBACK_DOM] 상품 리스트 추출 중 오류: {e}")
                
                except Exception as e:
                    logging.error(f"페이지 처리 중 오류 발생: {e}")
                    continue
                            fallback_selectors = [
                                'a[href*="/product/"]',
                                'a[href*="detail"]',
                                'a[href*="product_no"]',
                                'a[href*=".html"]',
                                'a[href]'  # 마지막 수단
                            ]
                            
                            for fallback_selector in fallback_selectors:
                                try:
                                    links = product.select(fallback_selector)
                                    for link_elem in links:
                                        href = link_elem.get('href', '')
                                        # 상품 상세 페이지로 보이는 링크만 선택
                                        if href and any(pattern in href.lower() for pattern in ['product', 'detail', '.html']):
                                            if not any(exclude in href.lower() for exclude in ['cart', 'wish', 'compare', 'review']):
                                                link = href
                                                break
                                    if link:
                                        print(f"[FALLBACK] {fallback_selector}로 링크 발견: {link[:50]}...")
                                        break
                                except:
                                    continue
                        
                        # 디버깅: 상품 요소 내 링크 현황 확인
                        if not link:
                            print(f"[DEBUG] 링크 추출 실패, 상품 요소 내 링크 확인...")
                            all_links = product.select('a[href]')
                            print(f"[DEBUG] 상품 요소 내 전체 링크 수: {len(all_links)}")
                            for i, link_elem in enumerate(all_links[:5]):  # 최대 5개만 로그
                                href = link_elem.get('href', '')
                                print(f"[DEBUG] 링크 {i+1}: {href}")
                            
                            # 마지막 수단: 첫 번째 링크를 강제로 사용
                            if len(all_links) > 0:
                                first_link = all_links[0].get('href', '')
                                if first_link:
                                    link = first_link
                                    print(f"[FORCE] 첫 번째 링크 강제 사용: {link[:50]}...")
                        
                        if link and link not in unique_products:
                            unique_products[link] = product
                    except Exception as e:
                        print(f"[ERROR] 상품링크 추출 오류: {e}")
                
                print(f"[INFO] 페이지 {page_number}: {len(unique_products)}개 고유 상품 발견")
                
                if len(unique_products) == 0:
                    print("[WARNING] 상품이 없습니다. 다음 페이지로 이동합니다.")
                    continue

                for product_link_partial, product in unique_products.items():
                    print(f"[DEBUG] 상품 처리 시작: {product_link_partial}")
                    # 상품 링크 처리 (이미 unique_products에서 추출됨)
                    product_link = product_link_partial
                    if not product_link.startswith('http'):
                        product_link = base_url + product_link

                    # 중복 링크 방지 (조용히 처리)
                    if product_link in visited_links:
                        continue
                    visited_links.add(product_link)

                    # 상품페이지 이동
                    try:
                        page.goto(product_link)
                        page.wait_for_timeout(2000)
                        # 상품페이지에서 스크롤을 아래로 내려서 상세페이지 이미지 로드
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(1000)
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(2000)
                        product_soup = bs(page.content(), 'html.parser')
                    except Exception as e:
                        logging.error(f"상품 페이지 이동 중 오류 발생: {e}")
                        print(f"[ERROR] 상품 페이지 이동 중 오류: {e}")
                        continue

                    # 상품명 추출 (개별 상품 페이지에서) - og:title 우선 사용
                    product_name = "상품명을 찾을 수 없습니다."
                    try:
                        # 1. 먼저 og:title 메타태그에서 상품명 추출 시도
                        og_title_element = product_soup.select_one('meta[property="og:title"]')
                        if og_title_element and og_title_element.get('content'):
                            og_title = og_title_element.get('content').strip()
                            print(f"[DEBUG] og:title 메타태그에서 상품명 발견: '{og_title}'")
                            # og:title에서 추출한 상품명이 유효한지 확인
                            if og_title and len(og_title) > 2 and not any(exclude in og_title for exclude in ['카테고리', '전체보기', '메뉴', '로그인', '볼&골대', '볼&체커']):
                                product_name = og_title
                                print(f"[SUCCESS] og:title에서 상품명 추출 성공: '{product_name}'")
                            else:
                                print(f"[WARNING] og:title 내용이 유효하지 않음: '{og_title}'")
                        
                        # 2. og:title에서 추출 실패 시 기존 선택자 방식 사용
                        if product_name == "상품명을 찾을 수 없습니다.":
                            print(f"[FALLBACK] og:title 추출 실패, 기존 선택자 방식 사용")
                            # perfect_result의 선택자로 모든 후보 요소 가져오기
                            name_elements = product_soup.select(selectors["상품명"])
                            print(f"[DEBUG] 상품명 선택자 '{selectors['상품명']}'로 {len(name_elements)}개 요소 발견")
                            if name_elements:
                                # 브랜드명 대괄호가 있는 상품명 우선 선택
                                best_name = None
                                for element in name_elements:
                                    text = element.get_text(strip=True)
                                    print(f"[DEBUG] 선택된 요소 텍스트: '{text}' (tag: {element.name}, class: {element.get('class', 'None')})")
                                    if text:
                                        # 제외 패턴 체크
                                        exclude_patterns = [
                                            '카테고리', '전체보기', '메뉴', '로그인', '회원가입',
                                            '장바구니', '마이페이지', '고객센터', '공지사항', '이벤트',
                                            '볼&골대', '볼&체커', '네트워크', '타임스탬프', '멀티스포츠',
                                            '표현활동', '게임활동', 'nav', 'menu', 'button', 'btn'
                                        ]
                                        if any(pattern in text for pattern in exclude_patterns):
                                            continue
                                        
                                        # 브랜드명 대괄호가 있으면 우선 선택
                                        if '[' in text and ']' in text:
                                            best_name = text
                                            break
                                        elif not best_name:  # 브랜드명이 없으면 첫 번째 유효한 텍스트 사용
                                            best_name = text
                                if best_name:
                                    product_name = best_name.split(":", 1)[-1].strip()
                                    print(f"[DEBUG] 최종 선택된 상품명: '{product_name}' (from: '{best_name}')")
                                    print(f"[PRODUCT] {product_name[:50]}...")
                                else:
                                    print("[WARNING] 유효한 상품명을 찾을 수 없음")
                            else:
                                print(f"[WARNING] 선택자 '{selectors['상품명']}'로 상품명을 찾을 수 없음")
                    except Exception as e:
                        logging.error(f"[ERROR] 상품명 추출 중 오류 발생: 선택자 '{selectors['상품명']}' 사용 시 오류 {e}, 후속조치: 기본값으로 설정")
                        print(f"[ERROR] 상품명 추출 중 오류: {e}")
                        product_name = "상품명을 찾을 수 없습니다."
                    
                    # 상품명 유효성 및 중복 검증 (개선된 로직)
                    if not is_valid_product_name(product_name):
                        print(f"[SKIP] 유효하지 않은 상품명: {product_name}")
                        logging.info(f"[SKIP] 유효하지 않은 상품명: {product_name}")
                        continue
                        
                    if product_name in seen_product_names:
                        logging.info(f"[SKIP] 상품명 중복 감지: {product_name}")
                        print(f"[SKIP] 상품명 중복 감지 (카테고리명 오추출 가능성): {product_name}")
                        continue
                    
                    # 유효한 상품명만 중복 검증 세트에 추가
                    seen_product_names.add(product_name)
                    print(f"[PRODUCT_VALID] 유효한 상품명 확인: {product_name[:50]}...")
                    
                    # 가격
                    try:
                        # perfect_result의 선택자만 사용
                        price_element = product_soup.select_one(selectors["가격"])
                        if price_element:
                            price = price_element.get_text(strip=True)
                            price_display = price.encode('ascii', 'ignore').decode('ascii')
                            print(f"[DEBUG] 추출된 가격 텍스트: {price_display}")
                            import re
                            clean_price = re.sub(r'[^\d]', '', price)
                            if clean_price and len(clean_price) >= 3:
                                original_price = float(clean_price)
                                adjusted_price = math.ceil((original_price * price_increase_rate) / 100) * 100
                                if adjusted_price < minimum_price:
                                    logging.info(f"[SKIP] minimum_price({minimum_price}) 미달: {adjusted_price}원")
                                    print(f"[SKIP] minimum_price({minimum_price}) 미달: {adjusted_price}원")
                                    continue
                                else:
                                    adjusted_price = int(adjusted_price)
                                    logging.info(f"가격 추출 성공: {adjusted_price}")
                                    print(f"[DEBUG] 가격 추출 성공: {adjusted_price}")
                            else:
                                adjusted_price = "가격 정보 없음"
                                print(f"[DEBUG] 유효한 가격을 찾을 수 없음: {price_display}")
                        else:
                            adjusted_price = "가격 정보 없음"
                            print(f"[DEBUG] 선택자 '{selectors['가격']}'로 가격 요소를 찾을 수 없음")
                    except (AttributeError, ValueError) as e:
                        adjusted_price = "가격 정보 없음"
                        logging.error(f"[ERROR] 가격 추출 중 오류 발생: 선택자 '{selectors['가격']}' 사용 시 오류 {e}, 후속조치: '가격 정보 없음'으로 설정")
                        print(f"[DEBUG] 가격 추출 실패: {e}")

                    # 썸네일 이미지 주소 추출 및 저장
                    try:
                        thumbnail_element = product_soup.select_one(selectors["썸네일"])
                        if thumbnail_element:
                            thumbnail_url = thumbnail_element.get("data-original") or thumbnail_element.get("data-src") or thumbnail_element.get("src")
                            if thumbnail_url:
                                if thumbnail_url.startswith('//'):
                                    thumbnail_url = 'https:' + thumbnail_url
                                elif thumbnail_url.startswith('/'):
                                    thumbnail_url = product_base_url + thumbnail_url
                                elif not thumbnail_url.startswith('http'):
                                    thumbnail_url = product_base_url + '/' + thumbnail_url
                                logging.info(f"썸네일 추출 성공: {thumbnail_url}")
                                print(f"[DEBUG] 썸네일 추출 성공: {thumbnail_url}")
                            else:
                                thumbnail_url = None
                                print("[DEBUG] 썸네일 URL 없음")
                        else:
                            thumbnail_url = None
                            logging.error(f"[ERROR] 썸네일 추출 실패: 선택자 '{selectors['썸네일']}'로 요소를 찾을 수 없음, 후속조치: 썸네일 없이 계속 진행")
                            print("[DEBUG] 썸네일 추출 실패")
                    except Exception as e:
                        logging.error(f"[ERROR] 썸네일 이미지 추출 중 오류 발생: 선택자 '{selectors['썸네일']}' 사용 시 오류 {e}, 후속조치: 썸네일 없이 진행")
                        thumbnail_url = None
                        print(f"[DEBUG] 썸네일 추출 실패: {e}")

                    # 썸네일 이미지 저장 및 새로운 캔버스에 편집
                    try:
                        if thumbnail_url:
                            print(f"[DEBUG] 썸네일 이미지 다운로드 시도: {thumbnail_url}")
                            temp_filename = f'{thumbnail_path}/{image_counter}_temp.jpg'
                            urllib.request.urlretrieve(thumbnail_url, temp_filename)
                            im = Image.open(temp_filename)
                            im = im.resize((400, 400))
                            image = Image.new("RGB", (600, 600), "white")
                            gray_background = Image.new("RGB", (600, 100), (56, 56, 56))
                            image.paste(gray_background, (0, 500))
                            # 먼저 상품 이미지를 붙임
                            image.paste(im, (100, 100))
                            # 그 다음에 S2B REGISTERED 배지를 그림 (상품 이미지 위에 오도록)
                            blue_background = Image.new("RGB", (120, 80), (0, 82, 204))  # S2B 파란색
                            image.paste(blue_background, (480, 0))
                            red_badge = Image.new("RGB", (120, 40), (255, 61, 70))
                            image.paste(red_badge, (480, 80))
                            draw = ImageDraw.Draw(image)
                            font_path = "C:/Windows/Fonts/NanumGothicExtraBold.ttf"
                            max_text_width = 520
                            max_font_size = 150
                            min_font_size = 30
                            max_length = 13
                            if len(product_name) > max_length:
                                text1 = product_name[:max_length] + "..."
                            else:
                                text1 = product_name
                            text1 = text1.replace("-", "")
                            try:
                                name_font = get_fitting_font(draw, text1, max_text_width, font_path, max_font_size, min_font_size)
                                try:
                                    bbox = draw.textbbox((0, 0), text1, font=name_font)
                                    text_width = bbox[2] - bbox[0]
                                    text_height = bbox[3] - bbox[1]
                                except AttributeError:
                                    text_width, text_height = draw.textsize(text1, font=name_font)
                                x = (600 - text_width) // 2
                                y = 500 + (100 - text_height) // 2
                                print(f"[DEBUG] 폰트 적용 성공: {name_font.size}pt, 텍스트폭: {text_width}, x좌표: {x}")
                            except Exception as e:
                                print(f"[ERROR] 폰트 적용 오류: {e}")
                                name_font = ImageFont.truetype(font_path, min_font_size)
                                x = 10
                                y = 510
                            try:
                                draw.text((x, y), text1, font=name_font, fill="white", stroke_fill="black", stroke_width=2)
                                print(f"[DEBUG] draw.text 성공: '{text1}' (x={x}, y={y})")
                            except Exception as e:
                                print(f"[ERROR] draw.text 오류: {e}")
                            badge_font_path = "C:/Windows/Fonts/arialbd.ttf"
                            try:
                                s2b_font = ImageFont.truetype(badge_font_path, 60)
                                registered_font = ImageFont.truetype(badge_font_path, 16)
                            except:
                                try:
                                    badge_font_path = "C:/Windows/Fonts/Arial.ttf"
                                    s2b_font = ImageFont.truetype(badge_font_path, 60)
                                    registered_font = ImageFont.truetype(badge_font_path, 16)
                                except:
                                    s2b_font = ImageFont.load_default()
                                    registered_font = ImageFont.load_default()
                            s2b_text = "S2B"
                            try:
                                bbox = draw.textbbox((0, 0), s2b_text, font=s2b_font)
                                s2b_width = bbox[2] - bbox[0]
                                s2b_height = bbox[3] - bbox[1]
                            except AttributeError:
                                s2b_width, s2b_height = draw.textsize(s2b_text, font=s2b_font)
                            s2b_x = 480 + (120 - s2b_width) // 2
                            s2b_y = 5
                            draw.text((s2b_x, s2b_y), s2b_text, font=s2b_font, fill="white")
                            reg_text = "REGISTERED"
                            try:
                                bbox = draw.textbbox((0, 0), reg_text, font=registered_font)
                                reg_width = bbox[2] - bbox[0]
                                reg_height = bbox[3] - bbox[1]
                            except AttributeError:
                                reg_width, reg_height = draw.textsize(reg_text, font=registered_font)
                            reg_x = 480 + (120 - reg_width) // 2
                            reg_y = 88
                            draw.text((reg_x, reg_y), reg_text, font=registered_font, fill="white")
                            try:
                                image.save(f'{thumbnail_path}/{image_counter}_cr.jpg', quality=95, optimize=False)
                                print(f"[DEBUG] 썸네일 저장 성공: {thumbnail_path}/{image_counter}_cr.jpg")
                            except Exception as e:
                                print(f"[ERROR] 썸네일 저장 오류: {e}")
                            image.close()
                            im.close()
                            try:
                                os.remove(temp_filename)
                                print(f"[DEBUG] 임시 파일 삭제: {temp_filename}")
                            except Exception as e:
                                print(f"[WARNING] 임시 파일 삭제 실패: {e}")
                        else:
                            print("[WARNING] 썸네일 URL이 없어 이미지 생성 생략")
                    except Exception as e:
                        print(f"[ERROR] 썸네일 이미지 처리 중 오류: {e}")
                        continue
                    print(f"[DEBUG] 상품 처리 종료: {product_link_partial}")

                    # 상세 페이지 이미지 저장 및 자르기 (Playwright DOM 기반, 간결화)
                    try:
                        # 1. Playwright로 스크롤 여러 번 내리기 (동적 로딩 대응)
                        scroll_steps = [0, 0.25, 0.5, 0.75, 1.0]
                        for step in scroll_steps:
                            page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {step})")
                            page.wait_for_timeout(500)

                        # 2. 다층 상세페이지 선택자 전략으로 img 태그 추출
                        img_elements = page.query_selector_all('img')
                        # 썸네일 URL robust하게 추출
                        thumbnail_element = product_soup.select_one(selectors["썸네일"])
                        thumbnail_url = None
                        if thumbnail_element:
                            thumbnail_url = thumbnail_element.get("data-original") or thumbnail_element.get("data-src") or thumbnail_element.get("src")
                            if thumbnail_url:
                                thumbnail_url = urljoin(product_base_url, thumbnail_url)
                        
                        # 간단한 이미지 유효성 검사 (fallback용)
                        def is_valid_image_url(url):
                            try:
                                # 기본적인 이미지 URL 패턴 확인
                                if not url or len(url) < 10:
                                    return False
                                # 이미지 확장자 확인
                                if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                                    return True
                                return False
                            except:
                                return False
                        
                        detail_img_urls = []
                        for img in img_elements:
                            img_url = img.get_attribute('data-original') or img.get_attribute('data-src') or img.get_attribute('src')
                            if not img_url:
                                continue
                            img_url = urljoin(product_base_url, img_url)
                            # 유효성 검사, 썸네일/중복 방지, 최대 10개
                            if (is_valid_image_url(img_url)
                                and img_url not in detail_img_urls
                                and (not thumbnail_url or img_url != thumbnail_url)):
                                detail_img_urls.append(img_url)
                            if len(detail_img_urls) >= 10:
                                break
                        if detail_img_urls:
                            logging.info(f"상세페이지 추출 성공: {len(detail_img_urls)}개")
                            print(f"[DEBUG] 상세페이지 추출 성공: {len(detail_img_urls)}개")
                        else:
                            logging.error(f"[ERROR] 상세페이지 이미지 추출 실패: 선택자 '{selectors['상세페이지']}'로 유효한 이미지를 찾을 수 없음, 후속조치: 상세이미지 없이 계속 진행")
                            print("[DEBUG] 상세페이지 추출 실패")
                        # 3. 이미지 합치기 및 자르기 (성능 최적화된 병렬 다운로드)
                        combined_image = None
                        
                        # 병렬로 이미지 크기 사전 검증
                        if detail_img_urls:
                            print(f"[PERF] 상세 이미지 병렬 크기 검증 시작: {len(detail_img_urls)}개")
                            size_results = download_optimizer.check_image_size_parallel(detail_img_urls)
                            
                            # 유효한 이미지만 필터링
                            valid_detail_urls = [url for url, (is_valid, size) in size_results.items() if is_valid]
                            print(f"[PERF] 병렬 검증 결과: {len(valid_detail_urls)}개 유효 이미지")
                        else:
                            valid_detail_urls = detail_img_urls
                        
                        for img_url in valid_detail_urls:
                            img_path = f'{base_path}/detail_{image_counter}.jpg'
                            
                            # 최적화된 다운로드 사용
                            if download_optimizer.download_image_optimized(img_url, img_path):
                                jm = Image.open(img_path).convert("RGB")
                                if combined_image is None:
                                    combined_image = jm
                                else:
                                    combined_width = max(combined_image.width, jm.width)
                                    combined_height = combined_image.height + jm.height
                                    new_combined_image = Image.new("RGB", (combined_width, combined_height), "white")
                                    new_combined_image.paste(combined_image, (0, 0))
                                    new_combined_image.paste(jm, (0, combined_image.height))
                                    combined_image = new_combined_image
                            else:
                                print(f"[ERROR] 이미지 다운로드 실패, 건너뜀: {img_url}")
                        if combined_image is not None:
                            width, height = combined_image.size
                            current_image_num = image_counter
                            slice_height = height // 10
                            for i in range(10):
                                crop_area = (0, slice_height * i, width, slice_height * (i + 1))
                                cropped_img = combined_image.crop(crop_area)
                                cropped_img.save(f'{output_path}/{current_image_num:03}_{i + 1:03}.jpg')
                            combined_image.close()
                    except Exception as e:
                        print(f"오류 발생: {e}")
                        logging.error(f"[ERROR] 상세페이지 이미지 추출 중 오류 발생: 선택자 '{selectors['상세페이지']}' 사용 시 오류 {e}, 후속조치: 빈 상세이미지 목록으로 진행")
                        print(f"[DEBUG] 상세페이지 추출 실패: {e}")

                    # 상세설명 텍스트 추출 (키드짐 특수 요구사항)
                    extracted_text_content = ""
                    try:
                        print("[DEBUG] 상세설명 텍스트 추출 시작")
                        
                        # selectors에서 상세설명텍스트 선택자 가져오기
                        text_selector = selectors.get("상세설명텍스트", "")
                        if text_selector:
                            print(f"[DEBUG] 텍스트 선택자 사용: {text_selector}")
                            
                            # Playwright page 객체를 통해 텍스트 추출 (동기식)
                            try:
                                # 첫 번째 시도: HTML 서식 유지하여 추출
                                text_elements = page.query_selector_all(text_selector)
                                text_blocks = []
                                
                                for element in text_elements:
                                    # innerHTML으로 HTML 서식 유지
                                    html_content = element.inner_html()
                                    if html_content and html_content.strip():
                                        # 기본적인 정제: 스크립트, 스타일 태그 제거
                                        cleaned_html = re.sub(r'<script.*?</script>', '', html_content, flags=re.DOTALL)
                                        cleaned_html = re.sub(r'<style.*?</style>', '', cleaned_html, flags=re.DOTALL)
                                        
                                        if len(cleaned_html.strip()) > 20:  # 의미있는 내용만
                                            text_blocks.append(cleaned_html.strip())
                                            print(f"[DEBUG] HTML 텍스트 블록 추가: {len(cleaned_html)}자")
                                
                                if text_blocks:
                                    # 텍스트 블록들을 하나로 합치기
                                    combined_text = '\n'.join(text_blocks)
                                    
                                    # 최대 길이 제한 (3000자)
                                    if len(combined_text) > 3000:
                                        combined_text = combined_text[:3000] + '...'
                                    
                                    extracted_text_content = combined_text
                                    print(f"[DEBUG] 최종 텍스트 추출 성공: {len(extracted_text_content)}자")
                                else:
                                    print("[DEBUG] 유효한 텍스트 블록을 찾을 수 없음")
                                    
                            except Exception as e:
                                print(f"[DEBUG] Playwright 텍스트 추출 실패: {e}")
                                # BeautifulSoup으로 fallback
                                try:
                                    text_elements = product_soup.select(text_selector)
                                    text_blocks = []
                                    
                                    for element in text_elements:
                                        text_content = element.get_text(separator=' ', strip=True)
                                        if text_content and len(text_content) > 20:
                                            text_blocks.append(text_content)
                                            print(f"[DEBUG] Fallback 텍스트 블록 추가: {len(text_content)}자")
                                    
                                    if text_blocks:
                                        combined_text = '\n\n'.join(text_blocks)
                                        if len(combined_text) > 3000:
                                            combined_text = combined_text[:3000] + '...'
                                        extracted_text_content = combined_text
                                        print(f"[DEBUG] Fallback 텍스트 추출 성공: {len(extracted_text_content)}자")
                                except Exception as fallback_e:
                                    print(f"[DEBUG] Fallback 텍스트 추출도 실패: {fallback_e}")
                        else:
                            print("[DEBUG] 상세설명텍스트 선택자가 없음")
                            
                    except Exception as e:
                        print(f"[ERROR] 상세설명 텍스트 추출 실패: {e}")
                        extracted_text_content = ""

                    # 옵션 추출 및 추가금액 파싱
                    try:
                        options = []
                        option_tags = product_soup.select(selectors["선택옵션"] + ' option')

                        for option_tag in option_tags:
                            option_value = option_tag.get_text(strip=True)
                            # 유효한 옵션인지 확인
                            if option_value and is_valid_option(option_value):
                                # 화폐 기호 제거
                                option_value = option_value.replace('₩', '').strip()
                                option_name = option_value.split('(')[0].strip()
                                price_change = "0"
                                
                                # 추가 금액이 존재하는 경우 (예: (+25,000원) 또는 (-208,600원))
                                if '(' in option_value and ')' in option_value:
                                    price_info = option_value.split('(')[1].split(')')[0].strip()
                                    if '+' in price_info:
                                        # 양수 추가 금액일 경우 '+' 기호 제거
                                        price_change = price_info.replace(',', '').replace('원', '').replace('+', '').strip()
                                    elif '-' in price_info:
                                        # 음수 추가 금액일 경우 '-' 기호 유지
                                        price_change = price_info.replace(',', '').replace('원', '').strip()

                                options.append((option_name, price_change))

                        if not options:
                            options.append(("없음", "0"))
                        logging.info(f"옵션 추출 성공: {options}")
                        print(f"[DEBUG] 옵션 추출 성공: {options}")

                    except Exception as e:
                        logging.error(f"[ERROR] 옵션 추출 중 오류 발생: 선택자 '{selectors['선택옵션']}' 사용 시 오류 {e}, 후속조치: 빈 옵션으로 계속 진행")
                        options = []
                        print(f"[DEBUG] 옵션 추출 실패: {e}")

                    # 옵션 처리
                    try:
                        option_string = []  # 옵션 리스트 초기화

                        for option_name, price_change in options:
                            formatted_option = f"{option_name}=={price_change}=10000=0=0=0="
                            option_string.append(formatted_option)

                        if not option_string:
                            option_string.append("없음")

                        formatted_options = "\n".join(option_string)
                        option_string = "[필수선택]\n" + formatted_options

                        # 조건에 따라 최종 옵션 문자열 출력
                        if option_string.count("10000") == 1:
                            option_string = ""

                        # print("옵션 문자열:\n", option_string)

                    except Exception as e:
                        logging.error(f"[ERROR] 옵션 처리 중 오류 발생: 옵션 데이터 포맷팅 시 오류 {e}, 후속조치: 빈 옵션 문자열로 계속 진행")
                        option_string = ""

                    # 옵션 상품 가격 검증 (가이드라인: 복잡한 옵션 구조 검증)
                    try:
                        # 옵션이 있는 상품인지 확인
                        has_valid_options = False
                        if 'options' in locals() and options:
                            # '없음' 옵션만 있는 경우는 옵션 없는 상품으로 간주
                            has_valid_options = any(option_name != '없음' for option_name, _ in options)
                        
                        # 옵션 상품이면서 가격이 비정상적으로 낮은 경우 검증
                        if has_valid_options and isinstance(adjusted_price, (int, float)) and adjusted_price < 1000:
                            logging.info(f"[PRICE_OPTION_ERROR] 옵션 상품 가격 검증 실패: {adjusted_price}원 (옵션 {len(options)}개)")
                            print(f"[PRICE_OPTION_ERROR] 옵션 상품 가격 검증 실패: {adjusted_price}원 (옵션 {len(options)}개)")
                            continue
                    except Exception as e:
                        logging.error(f"옵션 상품 가격 검증 중 오류: {e}")
                        # 검증 오류는 전체 중단하지 않고 계속 진행

                    # 추가 코드 시작
                    try:
                        product_code = str(now)[3:4] + str(now)[5:7] + str(now)[8:10] + code + str(image_counter)
                        empty_str = ""
                        brand = brandname
                        manufacturer = brandname
                        origin = "국내=서울=강남구"
                        attributes = code + tdate
                        payment_method = "선결제"
                        shipping_fee = "3500"
                        purchase_quantity = "0"
                        tax_status = "y"
                        inventory = "9000"
                        thumbnail_url_final = f"http://ai.esmplus.com/tstkimtt/{tdate}{code}/cr/{image_counter}_cr.jpg"
                        option_type = "" if option_string == "" else "SM"

                        description = "<center> <img src='http://gi.esmplus.com/tstkimtt/head.jpg' /><br>"
                        for i in range(1, 11):
                            description += f"<img src='http://ai.esmplus.com/tstkimtt/{tdate}{code}/output/{image_counter:03}_{i:03}.jpg' /><br />"
                        
                        # 상세설명 텍스트 블록 삽입 (상세 이미지 다음, 배송 이미지 이전)
                        if extracted_text_content and extracted_text_content.strip():
                            description += "<div style='padding:15px; text-align:left; background-color:#f9f9f9; margin:10px; border-radius:5px; font-family:Arial,sans-serif; line-height:1.6;'>"
                            description += extracted_text_content
                            description += "</div><br>"
                            print(f"[DEBUG] 텍스트 블록이 description에 추가됨: {len(extracted_text_content)}자")
                        else:
                            print("[DEBUG] 추가할 텍스트 내용이 없음")
                        
                        description += "<img src='http://gi.esmplus.com/tstkimtt/deliver.jpg' /></center>"

                        coupon = "쿠폰"
                        category_code = "c"
                        weight = " "
                        detailed_description = "상세설명일괄참조"
                        free_gift = "N"

                        # 엑셀 헤더 순서에 맞춰 데이터 리스트를 정확히 매핑
                        sheet.append([
                            product_code,           # 업체상품코드
                            "",                    # 모델명
                            brand,                 # 브랜드
                            manufacturer,          # 제조사
                            origin,                # 원산지
                            product_name,          # 상품명
                            "",                    # 홍보문구
                            "",                    # 요약상품명
                            category,              # 카테고리코드
                            attributes,            # 사용자분류명
                            "",                    # 한줄메모
                            "",                    # 시중가
                            "",                    # 원가
                            "",                    # 표준공급가
                            adjusted_price,        # 판매가
                            payment_method,        # 배송방법
                            shipping_fee,          # 배송비
                            purchase_quantity,     # 구매수량
                            tax_status,            # 과세여부
                            inventory,             # 판매수량
                            thumbnail_url_final,   # 이미지1URL
                            thumbnail_url_final,   # 이미지2URL
                            "",                    # 이미지3URL
                            "",                    # 이미지4URL
                            "",                    # GIF생성
                            "",                    # 이미지6URL
                            "",                    # 이미지7URL
                            "",                    # 이미지8URL
                            "",                    # 이미지9URL
                            "",                    # 이미지10URL
                            "",                    # 추가정보입력사항
                            option_type,           # 옵션구분(기존 옵션타입)
                            option_string,         # 선택옵션(기존 옵션구분)
                            "",                    # 입력형옵션
                            "",                    # 추가구매옵션
                            description,           # 상세설명
                            "",                    # 추가상세설명
                            "",                    # 광고/홍보
                            "",                    # 제조일자
                            "",                    # 유효일자
                            coupon,                # 사은품내용(쿠폰)
                            "",                    # 키워드
                            "C",                   # 인증구분(기존 인증정보)
                            "",                    # 인증정보
                            "",                    # 거래처
                            "",                    # 영어상품명
                            "",                    # 중국어상품명
                            "",                    # 일본어상품명
                            "",                    # 영어상세설명
                            "",                    # 중국어상세설명
                            "",                    # 일본어상세설명
                            weight,                # 상품무게
                            "",                    # 영어키워드
                            "",                    # 중국어키워드
                            "",                    # 일본어키워드
                            "",                    # 생산지국가
                            "",                    # 전세계배송코드
                            "",                    # 사이즈
                            "",                    # 포장방법
                            "25",                  # 표준산업코드(상품상세코드)
                            "N",                   # 미성년자구매(사은품여부)
                            "",                    # 상품상세코드(빈 값)
                            detailed_description,  # 상품상세1
                            detailed_description,  # 상품상세2
                            detailed_description,  # 상품상세3
                            detailed_description,  # 상품상세4
                            detailed_description,  # 상품상세5
                            detailed_description,  # 상품상세6
                            detailed_description,  # 상품상세7
                            detailed_description,  # 상품상세8
                            detailed_description,  # 상품상세9
                            detailed_description,  # 상품상세10
                            detailed_description,  # 상품상세11
                            detailed_description,  # 상품상세12
                            detailed_description,  # 상품상세13
                            detailed_description,  # 상품상세14
                            detailed_description,  # 상품상세15
                            detailed_description,  # 상품상세16
                            detailed_description,  # 상품상세17
                            detailed_description,  # 상품상세18
                            detailed_description,  # 상품상세19
                            detailed_description,  # 상품상세20
                            detailed_description,  # 상품상세21
                            detailed_description,  # 상품상세22
                            detailed_description,  # 상품상세23
                            detailed_description,  # 상품상세24
                            detailed_description,  # 상품상세25
                            thumbnail_url          # 상품상세26(마지막에 이미지 URL)
                        ])

                        product_infos.append({
                            'image_counter': image_counter,
                            'product_name': product_name,
                            'adjusted_price': adjusted_price,
                            'product_link': product_link,
                            'thumbnail_url': thumbnail_url
                        })
                        
                        # 부분 성공 검증 및 로깅
                        partial_issues = []
                        if not thumbnail_url:
                            partial_issues.append("썸네일 없음")
                        if not detail_img_urls:
                            partial_issues.append("상세이미지 없음")
                        if adjusted_price == "가격 정보 없음":
                            partial_issues.append("가격 정보 없음")
                        
                        if partial_issues:
                            logging.info(f"[PARTIAL SUCCESS] 상품 부분 성공: {', '.join(partial_issues)} 문제 있음, 후속조치: 가능한 데이터로 계속 진행")
                            print(f"[PARTIAL SUCCESS] 상품 부분 성공: {', '.join(partial_issues)}")
                        
                        print(f"[INFO] 저장: {image_counter}_cr.jpg | {product_name} | {adjusted_price} | {product_link}")
                        image_counter += 1  # 다음 상품을 위해 카운터 증가

                        # 상품 개수 제한 (테스트 모드)
                        if TEST_MODE and image_counter > TEST_PRODUCT_COUNT:
                            print(f"[INFO] TEST_MODE: {TEST_PRODUCT_COUNT}개 상품만 추출 후 중단합니다.")
                            break
                    except Exception as e:
                        logging.error(f"상품 데이터 추가 중 오류 발생: {e}")
                        continue

                    except Exception as e:
                        logging.error(f"페이지 처리 중 오류 발생: {e}")
                        continue

    except Exception as e:
        logging.error(f"오류 발생: {e}")

    finally:
        # 성능 최적화 객체 정리
        download_optimizer.close()
        print("[PERF] 이미지 다운로드 최적화 시스템 정리 완료")
        browser.close()

# 현재 시간을 출력
# print(now)  # 주석 처리

# 엑셀 파일 저장
try:
    wb.save(f'C:/Users/ME/Pictures/{tdate}{code}.xlsx')
    print("크롤링 성공")
except Exception as e:
    logging.error(f"엑셀 파일 저장 중 오류 발생: {e}")

# 작업에 총 몇 초가 걸렸는지 출력
end_time = time.time()
total_time = end_time - start_time

print("The Job Took " + str(total_time) + " seconds.")

# 성능 개선 요약 로그
print("\n" + "="*50)
print("성능 최적화 요약 보고서")
print("="*50)
print(f"총 처리 시간: {total_time:.2f}초")
print(f"JSON 데이터로 처리된 상품: {json_products_count}개")
print(f"Fallback으로 처리된 상품: {fallback_products_count}개")

if json_products_count > 0:
    avg_json_time = json_processing_time / json_products_count
    print(f"JSON 상품당 평균 처리 시간: {avg_json_time:.2f}초")
    
if fallback_products_count > 0:
    avg_fallback_time = fallback_processing_time / fallback_products_count  
    print(f"Fallback 상품당 평균 처리 시간: {avg_fallback_time:.2f}초")
    
    if json_products_count > 0:
        performance_improvement = ((avg_fallback_time - avg_json_time) / avg_fallback_time) * 100
        print(f"JSON 사용 시 성능 향상: {performance_improvement:.1f}%")

print(f"절약된 네트워크 요청: {network_requests_saved}개")

json_usage_rate = (json_products_count / (json_products_count + fallback_products_count)) * 100 if (json_products_count + fallback_products_count) > 0 else 0
print(f"JSON 데이터 활용률: {json_usage_rate:.1f}%")

if json_usage_rate >= 95:
    print("[SUCCESS] JSON 데이터 활용률 95% 이상 달성!")
elif json_usage_rate >= 80:
    print("[GOOD] JSON 데이터 활용률 양호")
else:
    print("[WARNING] JSON 데이터 활용률 개선 필요")
    
print("="*50)
