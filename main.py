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
import re

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
    
    # 2. '선택'으로 끝나는 모든 문자열 제외 (공백 포함)
    if re.search(r'선택\s*$', text):
        return True
    
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
        'logo', 'icon', 'btn', 'menu', 'nav', 
        'design', 'ui', 'arrow', 'quick', 'zzim'
    ]
    
    for pattern in exclude_patterns:
        if pattern in url_lower:
            return False
    
    # 포함되어야 할 패턴들
    include_patterns = ['editor', 'goods', 'product', 'data']
    for pattern in include_patterns:
        if pattern in url_lower:
            return True
    
    return False

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
    
    # 데스크탑 모드로 설정
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.set_extra_http_headers({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    })

    # 이미지 파일명을 고유하게 만들기 위한 카운터
    image_counter = 1

    start_time = time.time()

    try:
        # 최신 perfect_result_*.json 파일에서 선택자 읽기
        json_files = glob.glob("perfect_result_*.json")
        if not json_files:
            raise FileNotFoundError("perfect_result_*.json 파일이 없습니다.")
        latest_json = max(json_files, key=os.path.getmtime)
        with open(latest_json, "r", encoding="utf-8") as f:
            selectors = json.load(f)["선택자"]

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
        product_infos = []  # (image_counter, product_name, adjusted_price, product_link, ...) 저장용

        # 페이지 반복 처리
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

                # 제품 리스트 선택자 적용 (범용 선택자 사용)
                product_list_selector = selectors.get("상품리스트", ".goods-list li, .item-list li, [class*='item'], li[class*='goods'], .product-list li, .catalog li")
                print(f"[DEBUG] 사용할 상품리스트 선택자: {product_list_selector}")
                
                # 여러 선택자를 시도해서 상품 찾기
                product_list = []
                for selector in product_list_selector.split(', '):
                    try:
                        found_products = soup.select(selector.strip())
                        if found_products:
                            product_list.extend(found_products)
                            print(f"[DEBUG] '{selector.strip()}' 선택자로 {len(found_products)}개 상품 발견")
                    except:
                        continue
                
                # 중복 제거
                seen_elements = set()
                unique_product_list = []
                for product in product_list:
                    element_id = id(product)
                    if element_id not in seen_elements:
                        seen_elements.add(element_id)
                        unique_product_list.append(product)
                
                product_list = unique_product_list
                
                # 고유한 상품 링크만 추출하여 중복 제거
                unique_products = {}
                for product in product_list:
                    try:
                        link_element = product.select_one(selectors["상품링크"])
                        if link_element and 'href' in link_element.attrs:
                            link = link_element['href']
                            if link not in unique_products:
                                unique_products[link] = product
                    except:
                        continue
                
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

                    # 상품명 추출 (개별 상품 페이지에서)
                    product_name = "상품명을 찾을 수 없습니다."
                    try:
                        # 여러 상품명 선택자 시도
                        name_selectors = [
                            selectors["상품명"], ".name", "h1", "h2", ".title", ".product-name", ".goods-name",
                            ".item-name", "[itemprop='name']"
                        ]
                        for name_selector in name_selectors:
                            try:
                                name_element = product_soup.select_one(name_selector)
                                if name_element:
                                    full_text = name_element.get_text(strip=True)
                                    if full_text and len(full_text) > 3:  # 의미있는 텍스트인지 확인
                                        product_name = full_text.split(":", 1)[-1].strip()
                                        print(f"[PRODUCT] {product_name[:50]}...")
                                        break
                            except Exception as e:
                                print(f"[ERROR] 상품명 선택자 오류: {e}")
                                continue
                        if product_name == "상품명을 찾을 수 없습니다.":
                            print("[WARNING] 상품명 추출 실패")
                    except Exception as e:
                        logging.error(f"상품명 추출 중 오류 발생: {e}")
                        print(f"[ERROR] 상품명 추출 중 오류: {e}")
                        product_name = "상품명을 찾을 수 없습니다."

                    # 가격
                    try:
                        price_selectors = [
                            selectors["가격"], ".price", ".org_price", ".sale_price", "[class*='price']", ".cost", ".amount"
                        ]
                        price_element = None
                        for price_sel in price_selectors:
                            price_element = product_soup.select_one(price_sel)
                            if price_element:
                                print(f"[DEBUG] 가격 선택자 '{price_sel}' 성공")
                                break
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
                                    adjusted_price = "가격 정보 없음"
                                else:
                                    adjusted_price = int(adjusted_price)
                                    logging.info(f"가격 추출 성공: {adjusted_price}")
                                    print(f"[DEBUG] 가격 추출 성공: {adjusted_price}")
                            else:
                                adjusted_price = "가격 정보 없음"
                                print(f"[DEBUG] 유효한 가격을 찾을 수 없음: {price_display}")
                        else:
                            adjusted_price = "가격 정보 없음"
                            print("[DEBUG] 가격 요소를 찾을 수 없음")
                    except (AttributeError, ValueError) as e:
                        adjusted_price = "가격 정보 없음"
                        logging.error("가격 추출 실패")
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
                            logging.error("썸네일 추출 실패")
                            print("[DEBUG] 썸네일 추출 실패")
                    except Exception as e:
                        logging.error(f"썸네일 이미지 주소 추출 중 오류 발생: {e}")
                        thumbnail_url = None
                        print(f"[DEBUG] 썸네일 추출 실패: {e}")

                    # 썸네일 이미지 저장 및 새로운 캔버스에 편집
                    try:
                        if thumbnail_url:
                            print(f"[DEBUG] 썸네일 이미지 다운로드 시도: {thumbnail_url}")
                            urllib.request.urlretrieve(thumbnail_url, f'{thumbnail_path}/{image_counter}_cr.jpg')
                            im = Image.open(f'{thumbnail_path}/{image_counter}_cr.jpg')
                            im = im.resize((400, 400))
                            image = Image.new("RGB", (600, 600), "white")
                            gray_background = Image.new("RGB", (600, 100), (56, 56, 56))
                            image.paste(gray_background, (0, 500))
                            
                            # 먼저 상품 이미지를 붙임
                            image.paste(im, (100, 100))
                            
                            # 그 다음에 S2B REGISTERED 배지를 그림 (상품 이미지 위에 오도록)
                            # 파란색 배경 (더 크게)
                            blue_background = Image.new("RGB", (120, 80), (0, 82, 204))  # S2B 파란색
                            image.paste(blue_background, (480, 0))
                            
                            # 빨간색 하단 부분 (더 크게)
                            red_badge = Image.new("RGB", (120, 40), (255, 61, 70))
                            image.paste(red_badge, (480, 80))
                            draw = ImageDraw.Draw(image)
                            font_path = "C:/Windows/Fonts/NanumGothicExtraBold.ttf"
                            max_text_width = 520  # 600px - 좌우 40px 여백
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
                                # 텍스트 폭/높이 계산 및 중앙 정렬
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
                            
                            # S2B REGISTERED 텍스트 추가
                            badge_font_path = "C:/Windows/Fonts/arialbd.ttf"  # Arial Bold 폰트 사용
                            try:
                                s2b_font = ImageFont.truetype(badge_font_path, 60)  # S2B 폰트 크기 (더 크게 해서 공백 줄이기)
                                registered_font = ImageFont.truetype(badge_font_path, 16)  # REGISTERED 폰트 크기 (더 크게)
                            except:
                                try:
                                    badge_font_path = "C:/Windows/Fonts/Arial.ttf"  # 일반 Arial로 대체
                                    s2b_font = ImageFont.truetype(badge_font_path, 60)
                                    registered_font = ImageFont.truetype(badge_font_path, 16)
                                except:
                                    s2b_font = ImageFont.load_default()
                                    registered_font = ImageFont.load_default()
                            
                            # S2B 텍스트 그리기 (파란색 배경 위에)
                            s2b_text = "S2B"
                            try:
                                bbox = draw.textbbox((0, 0), s2b_text, font=s2b_font)
                                s2b_width = bbox[2] - bbox[0]
                                s2b_height = bbox[3] - bbox[1]
                            except AttributeError:
                                s2b_width, s2b_height = draw.textsize(s2b_text, font=s2b_font)
                            s2b_x = 480 + (120 - s2b_width) // 2  # 크게 한 배지에 맞춰 조정
                            s2b_y = 5  # 더 위로 올려서 공백 줄이기
                            draw.text((s2b_x, s2b_y), s2b_text, font=s2b_font, fill="white")
                            
                            # REGISTERED 텍스트 그리기 (빨간색 배경 위에)
                            reg_text = "REGISTERED"
                            try:
                                bbox = draw.textbbox((0, 0), reg_text, font=registered_font)
                                reg_width = bbox[2] - bbox[0]
                                reg_height = bbox[3] - bbox[1]
                            except AttributeError:
                                reg_width, reg_height = draw.textsize(reg_text, font=registered_font)
                            reg_x = 480 + (120 - reg_width) // 2  # 크게 한 배지에 맞춰 조정
                            reg_y = 88  # 빨간색 배경 위에
                            draw.text((reg_x, reg_y), reg_text, font=registered_font, fill="white")
                            try:
                                image.save(f'{thumbnail_path}/{image_counter}_cr.jpg', quality=95, optimize=False)
                                print(f"[DEBUG] 썸네일 저장 성공: {thumbnail_path}/{image_counter}_cr.jpg")
                            except Exception as e:
                                print(f"[ERROR] 썸네일 저장 오류: {e}")
                            image.close()
                        else:
                            print("[WARNING] 썸네일 URL이 없어 이미지 생성 생략")
                    except Exception as e:
                        print(f"[ERROR] 썸네일 이미지 처리 중 오류: {e}")
                        continue
                    print(f"[DEBUG] 상품 처리 종료: {product_link_partial}")

                    # 상세 페이지 이미지 저장 및 자르기
                    try:
                        detail_images = product_soup.select(selectors["상세페이지"])
                        if detail_images:
                            logging.info(f"상세페이지 추출 성공: {len(detail_images)}개")
                            print(f"[DEBUG] 상세페이지 추출 성공: {len(detail_images)}개")
                        else:
                            logging.error("상세페이지 추출 실패")
                            print("[DEBUG] 상세페이지 추출 실패")
                        combined_image = None

                        for img_tag in detail_images:
                            # 여러 속성에서 이미지 URL 찾기
                            img_url = img_tag.get('data-original') or img_tag.get('data-src') or img_tag.get('src')
                            
                            if not img_url:
                                continue  # src 속성이 없는 경우 제외
                            
                            # 유효한 상세 이미지인지 검사
                            if not is_valid_detail_image(img_url):
                                continue

                            # 절대 URL로 변환
                            if img_url.startswith('//'):
                                img_url = 'https:' + img_url
                            elif img_url.startswith('/'):
                                img_url = product_base_url + img_url
                            elif not img_url.startswith('http'):
                                img_url = product_base_url + '/' + img_url
                            
                            # 이미지 다운로드 및 로컬 저장 경로 설정
                            img_path = f'{base_path}/detail_{image_counter}.jpg'  # 고유한 파일명 생성
                            urllib.request.urlretrieve(img_url, img_path)
                            jm = Image.open(img_path).convert("RGB")

                            # 이미지를 하나로 합치기
                            if combined_image is None:
                                combined_image = jm
                            else:
                                combined_width = max(combined_image.width, jm.width)
                                combined_height = combined_image.height + jm.height
                                new_combined_image = Image.new("RGB", (combined_width, combined_height), "white")
                                new_combined_image.paste(combined_image, (0, 0))
                                new_combined_image.paste(jm, (0, combined_image.height))
                                combined_image = new_combined_image

                        # 이미지 자르기 및 저장
                        if combined_image is not None:
                            width, height = combined_image.size
                            current_image_num = image_counter  # 현재 상품 번호 계산
                            slice_height = height // 10  # 이미지 하나의 높이
                            for i in range(10):
                                crop_area = (0, slice_height * i, width, slice_height * (i + 1))  # 이미지 자르는 영역 설정
                                cropped_img = combined_image.crop(crop_area)  # 이미지 자르기
                                cropped_img.save(f'{output_path}/{current_image_num:03}_{i + 1:03}.jpg')  # 잘린 이미지 저장
                            combined_image.close()

                    except Exception as e:
                        print(f"오류 발생: {e}")
                        logging.error(f"상세페이지 추출 중 오류 발생: {e}")
                        print(f"[DEBUG] 상세페이지 추출 실패: {e}")


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
                        logging.error(f"옵션 추출 중 오류 발생: {e}")
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
                        logging.error(f"옵션 처리 중 오류 발생: {e}")
                        option_string = ""

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
                            description += f"<img src='http://ai.esmplus.com/tstkimtt/{tdate}{code}/output/{current_image_num:03}_{i:03}.jpg' /><br />"
                        description += "<img src='http://gi.esmplus.com/tstkimtt/deliver.jpg' /></center>"

                        coupon = "쿠폰"
                        category_code = "c"
                        weight = "25"
                        detailed_description = "상세설명일괄참조"
                        free_gift = "N"

                        # 엑셀 헤더 순서에 맞춰 데이터 리스트를 정확히 매핑
                        if adjusted_price == "가격 정보 없음":
                            continue  # 최소가격 미만 상품은 엑셀에 추가하지 않음
                        sheet.append([
                            product_code,           # 업체상품코드
                            "",                     # 모델명 (빈 값)
                            brand,                  # 브랜드
                            manufacturer,           # 제조사
                            origin,                 # 원산지
                            product_name,           # 상품명
                            "",                     # 홍보문구 (빈 값)
                            "",                     # 요약상품명 (빈 값)
                            category,               # 카테고리코드
                            attributes,             # 사용자분류명 (또는 적절한 값)
                            "",                     # 한줄메모 (빈 값)
                            "",                     # 시중가 (빈 값)
                            "",                     # 원가 (빈 값)
                            "",                     # 표준공급가 (빈 값)
                            adjusted_price,         # 판매가
                            payment_method,         # 배송방법
                            shipping_fee,           # 배송비
                            purchase_quantity,      # 구매수량
                            tax_status,             # 과세여부
                            inventory,              # 판매수량
                            thumbnail_url_final,    # 이미지1URL
                            thumbnail_url_final,    # 이미지2URL
                            "",                     # 이미지3URL (빈 값)
                            "",                     # 이미지4URL (빈 값)
                            "",                     # GIF생성 (빈 값)
                            "",                     # 이미지6URL (빈 값)
                            "",                     # 이미지7URL (빈 값)
                            "",                     # 이미지8URL (빈 값)
                            "",                     # 이미지9URL (빈 값)
                            "",                     # 이미지10URL (빈 값)
                            "",                     # 추가정보입력사항 (빈 값)
                            option_type,            # 옵션타입
                            option_string,          # 옵션구분 (또는 옵션 문자열)
                            "",                     # 선택옵션 (빈 값)
                            "",                     # 입력형옵션 (빈 값)
                            "",                     # 추가구매옵션 (빈 값)
                            description,            # 상세설명
                            "",                     # 추가상세설명 (빈 값)
                            "",                     # 광고/홍보 (빈 값)
                            "",                     # 제조일자 (빈 값)
                            "",                     # 유효일자 (빈 값)
                            "",                     # 사은품내용 (빈 값)
                            coupon,                 # 키워드 (쿠폰)
                            "",                     # 인증구분 (빈 값)
                            category_code,          # 인증정보 (카테고리코드)
                            "",                     # 거래처 (빈 값)
                            "",                     # 영어상품명 (빈 값)
                            "",                     # 중국어상품명 (빈 값)
                            "",                     # 일본어상품명 (빈 값)
                            "",                     # 영어상세설명 (빈 값)
                            "",                     # 중국어상세설명 (빈 값)
                            "",                     # 일본어상세설명 (빈 값)
                            weight,                 # 상품무게
                            "",                     # 영어키워드 (빈 값)
                            "",                     # 중국어키워드 (빈 값)
                            "",                     # 일본어키워드 (빈 값)
                            "",                     # 생산지국가 (빈 값)
                            "",                     # 전세계배송코드 (빈 값)
                            "",                     # 사이즈 (빈 값)
                            "",                     # 포장방법 (빈 값)
                            "",                     # 상품상세코드 (빈 값)
                            detailed_description,   # 상품상세1
                            detailed_description,   # 상품상세2
                            detailed_description,   # 상품상세3
                            detailed_description,   # 상품상세4
                            detailed_description,   # 상품상세5
                            detailed_description,   # 상품상세6
                            free_gift,              # 상품상세7 (사은품여부)
                            detailed_description,   # 상품상세8
                            detailed_description,   # 상품상세9
                            detailed_description,   # 상품상세10
                            detailed_description,   # 상품상세11
                            detailed_description,   # 상품상세12
                            thumbnail_url           # 상품상세13 (마지막에 이미지 URL)
                        ])

                        product_infos.append({
                            'image_counter': image_counter,
                            'product_name': product_name,
                            'adjusted_price': adjusted_price,
                            'product_link': product_link,
                            'thumbnail_url': thumbnail_url
                        })
                        print(f"[INFO] 저장: {image_counter}_cr.jpg | {product_name} | {adjusted_price} | {product_link}")
                        image_counter += 1  # 다음 상품을 위해 카운터 증가
                    except Exception as e:
                        logging.error(f"상품 데이터 추가 중 오류 발생: {e}")
                        continue

  
            except Exception as e:
                logging.error(f"페이지 처리 중 오류 발생: {e}")
                continue

    except Exception as e:
        logging.error(f"오류 발생: {e}")

    finally:
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
print("The Job Took " + str(end_time - start_time) + " seconds.")
