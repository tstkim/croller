from config import *
from playwright.sync_api import sync_playwright
from PIL import ImageFont
import logging
import urllib.request
from PIL import Image, ImageDraw
import math
import time

# 로그 설정
logging.basicConfig(filename='app.log', level=logging.INFO)

# Playwright를 사용한 웹드라이버 설정 및 시작
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 이미지 파일명을 고유하게 만들기 위한 카운터
    image_counter = 1

    start_time = time.time()

    try:
        if use_login:
            try:
                # 로그인 페이지로 이동
                page.goto(login_url)
                page.fill('input[name="userid"]', login_credentials['userid'])
                page.fill('input[name="password"]', login_credentials['password'])
                page.press('input[name="password"]', 'Enter')
                page.wait_for_timeout(5000)
            except Exception as e:
                logging.error(f"로그인 중 오류 발생: {e}")

        # 페이지 반복 처리
        for page_number in range(start_page, end_page + 1):
            try:
                url = catalog_url_template.format(page=page_number)
                page.goto(url)
                page.wait_for_timeout(5000)
                soup = bs(page.content(), 'html.parser')
                base_url = product_base_url

                # 제품명
                product_names = soup.select("div.mList1 ul li")

                for product in product_names:
                    try:
                        product_name = product.select_one("span.ti").get_text(strip=True)
                    except AttributeError:
                        product_name = "상품명을 찾을 수 없습니다."
                    # print(f"상품명: {product_name}")  # 주석 처리

                    # 상품 페이지로 이동하기 위한 링크 추출
                    try:
                        product_link_element = product.select_one("a")
                        if product_link_element is not None and 'href' in product_link_element.attrs:
                            product_link = product_link_element['href']
                        else:
                            product_link = "링크를 찾을 수 없습니다."

                        if not product_link.startswith('http'):
                            product_link = base_url2 + product_link
                    except Exception as e:
                        logging.error(f"상품 링크 추출 중 오류 발생: {e}")
                        continue

                    # 상품페이지 이동
                    try:
                        page.goto(product_link)
                        page.wait_for_timeout(3000)
                        product_soup = bs(page.content(), 'html.parser')
                    except Exception as e:
                        logging.error(f"상품 페이지 이동 중 오류 발생: {e}")
                        continue

                    # 가격
                    try:
                        price = product_soup.select_one("#frm > div > div.info-con > table > tbody > tr:nth-child(1) > td > div > strong > b > span:nth-child(1)").get_text(strip=True)
                        price = price.replace(",", "").replace("원", "")
                        original_price = float(price)
                        adjusted_price = math.ceil((original_price * price_increase_rate) / 100) * 100
                        if adjusted_price < minimum_price:
                            adjusted_price = "가격 정보 없음"
                    except (AttributeError, ValueError):
                        adjusted_price = "가격 정보 없음"

                    # 썸네일 이미지 주소 추출
                    try:
                        thumbnail_element = product_soup.select_one("img#zoom_mw")
                        if thumbnail_element:
                            thumbnail_url = thumbnail_element.get('data-zoom-image')
                        else:
                            thumbnail_url = None
                    except Exception as e:
                        logging.error(f"썸네일 이미지 주소 추출 중 오류 발생: {e}")
                        thumbnail_url = None

                    # 썸네일 이미지 저장 및 새로운 캔버스에 편집
                    try:
                        if thumbnail_url:
                            urllib.request.urlretrieve(thumbnail_url, f'{thumbnail_path}/{image_counter}_cr.jpg')
                            im = Image.open(f'{thumbnail_path}/{image_counter}_cr.jpg')
                            im = im.resize((400, 400))

                            # 새로운 캔버스 생성
                            image = Image.new("RGB", (600, 600), "white")
                            gray_background = Image.new("RGB", (600, 100), (56, 56, 56))  # 아래 검정색 바탕띠
                            image.paste(gray_background, (0, 500))

                            red_background = Image.new("RGB", (150, 150), (255, 61, 70))  # 위 빨간색 바탕띠
                            image.paste(red_background, (440, 0))

                            name_font = ImageFont.truetype("C:/Windows/Fonts/NanumGothicExtraBold.ttf", 65)
                            label_font = ImageFont.truetype("C:/Windows/Fonts/NanumGothicExtraBold.ttf", 40)

                            # 상품명 길이 제한: 10자 초과 시 생략
                            max_length = 10
                            if len(product_name) > max_length:
                                text1 = product_name[:max_length] + "..."
                            else:
                                text1 = product_name

                            # 파일명에 "-" 혹은 특수문자가 있으면 오류가 나므로 제거
                            text1 = text1.replace("-", "")
                            ImageDraw.Draw(image).text((10, 510), text1, font=name_font, fill="white", stroke_fill="black", stroke_width=2)

                            
                            ImageDraw.Draw(image).text((460, 10), "S2B", font=name_font, fill="white", stroke_fill="red", stroke_width=2)
                            ImageDraw.Draw(image).text((505, 95), "공식", font=label_font, fill="white", stroke_fill="red", stroke_width=1)
                            image.paste(im, (100, 100))

                            image.save(f'{thumbnail_path}/{image_counter}_cr.jpg')
                            image.close()
                    except (ValueError, urllib.error.HTTPError, urllib.error.URLError, FileNotFoundError) as e:
                        logging.error(f"썸네일 이미지 처리 중 오류 발생: {e}")
                        continue

                    # 상세 페이지 이미지 저장 및 자르기
                    try:
                        detail_images = []
                        for p in range(1, 5):
                            try:
                                image_element = product_soup.select_one(f"div.tab-con img:nth-of-type({p})")
                                if image_element:
                                    image_url = image_element.get("src")
                                    if image_url and not image_url.endswith('.png') and "https://sysheen.speedgabia.com/internet_dept/b2b/01_common/ExchangeReturn_info.jpg" not in image_url:
                                        detail_images.append(image_url)
                                    else:
                                        logging.info(f"Invalid image URL skipped: {image_url}")
                                else:
                                    logging.info(f"No image element found for index {p}")
                            except AttributeError as e:
                                logging.error(f"AttributeError: {e}")
                                detail_images.append("")

                        # 상품 세부 정보 추출
                        try:
                            spec_table = product_soup.select_one("table.specTable")
                            if spec_table:
                                rows = spec_table.select("tr")
                                product_details = {}
                                for row in rows:
                                    th = row.select_one("th").get_text(strip=True)
                                    td = row.select_one("td").get_text(strip=True)
                                    product_details[th] = td
                        except Exception as e:
                            logging.error(f"상품 세부 정보 추출 중 오류 발생: {e}")
                            product_details = {}

                        # 상세 이미지 다운로드 및 결합
                        try:
                            combined_image = None
                            for img_url in detail_images:
                                img_path = f'{base_path}/detail_{image_counter}.jpg'
                                urllib.request.urlretrieve(img_url, img_path)
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

                            # 상품 세부 정보 이미지를 생성하여 결합
                            if product_details:
                                info_image = Image.new("RGB", (combined_image.width, 400), "white")
                                draw = ImageDraw.Draw(info_image)
                                font = ImageFont.truetype("C:/Windows/Fonts/NanumGothic.ttf", 18)
                                y_text = 10
                                max_width = 800  # 줄바꿈을 원하는 최대 너비

                                for key, value in product_details.items():
                                    text = f"{key}: {value}"
                                    lines = []
                                    words = text.split(' ')
                                    line = ''
                                    for word in words:
                                        test_line = f"{line} {word}".strip()
                                        width, _ = draw.textbbox((0, 0), test_line, font=font)[2:]
                                        if width <= max_width:
                                            line = test_line
                                        else:
                                            lines.append(line)
                                            line = word
                                    lines.append(line)  # 마지막 라인 추가

                                    for line in lines:
                                        draw.text((10, y_text), line, font=font, fill="black")
                                        y_text += 30

                                # 이미지 결합
                                combined_width = max(combined_image.width, info_image.width)
                                combined_height = combined_image.height + info_image.height
                                new_combined_image = Image.new("RGB", (combined_width, combined_height), "white")
                                new_combined_image.paste(combined_image, (0, 0))
                                new_combined_image.paste(info_image, (0, combined_image.height))
                                combined_image = new_combined_image

                            if combined_image is not None:
                                width, height = combined_image.size
                                current_image_num = image_counter  # 현재 상품 번호 계산
                                slice_height = height // 10  # 이미지 하나의 높이
                                for i in range(10):
                                    crop_area = (0, slice_height * i, width, slice_height * (i + 1))
                                    cropped_img = combined_image.crop(crop_area)
                                    cropped_img.save(f'{output_path}/{current_image_num:03}_{i + 1:03}.jpg')
                                combined_image.close()
                        except Exception as e:
                            logging.error(f"상세 이미지 처리 중 오류 발생: {e}")
                            continue

                    except (ValueError, urllib.error.HTTPError, urllib.error.URLError, FileNotFoundError) as e:
                        logging.error(f"상세 페이지 이미지 처리 중 오류 발생: {e}")
                        continue

                    # 옵션 추출
                    try:
                        options = []
                        for a in range(2, 20):
                            try:
                                option = product_soup.select_one(f"select[name='viewOptions[]'] option:nth-of-type({a})").get_text(strip=True)
                                option = option.replace("\n", "").replace("  ", "")
                            except AttributeError:
                                option = "없음"
                            options.append(option)
                    except Exception as e:
                        logging.error(f"옵션 추출 중 오류 발생: {e}")
                        options = []

                    # 옵션 처리
                    try:
                        option_string = []  # 옵션 리스트 초기화
                        for a in range(1, 10):
                            try:
                                option = product_soup.select_one(f"tbody tr:nth-of-type({a}) input[name='optionTxtL']")
                                option = option["value"] if option else "없음"
                            except (AttributeError, TypeError):
                                option = "없음"
                            option_string.append(option)

                        if not option_string:
                            option_string.append("없음")

                        formatted_options = "==0=10000=0=0=0=\n".join(option_string)
                        option_string = "[필수선택]\n" + formatted_options.split("없음")[0]
                        if option_string.count("10000") == 1:
                            option_string = ""
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

                        if len(detail_images) > 0 and adjusted_price != "가격 정보 없음":  # 상세페이지가 있고 가격이 비어있지 않은 경우만
                            sheet.append([product_code, empty_str, brand, manufacturer, origin, product_name, empty_str, empty_str, category, attributes, empty_str, empty_str, empty_str, empty_str, adjusted_price, payment_method, shipping_fee, purchase_quantity, tax_status, inventory, thumbnail_url_final, thumbnail_url_final, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, option_type, option_string, empty_str, empty_str, description, empty_str, empty_str, empty_str, empty_str, coupon, empty_str, category_code, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, empty_str, weight, detailed_description, detailed_description, detailed_description, detailed_description, detailed_description, detailed_description, free_gift, detailed_description, detailed_description, detailed_description, detailed_description, detailed_description, thumbnail_url])

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
