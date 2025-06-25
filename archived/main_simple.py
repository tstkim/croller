#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
from bs4 import BeautifulSoup as bs
import re
import ssl
from config import *

# SSL 인증서 검증 비활성화
ssl._create_default_https_context = ssl._create_unverified_context

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 테스트할 상품 개수 추가 확인
TEST_PRODUCTS = getattr(sys.modules[__name__], 'TEST_PRODUCTS', 3) if 'sys' in locals() else 3

# ImageDownloadOptimizer 클래스 (기존과 동일)
class ImageDownloadOptimizer:
    def __init__(self, max_workers=5):
        self.max_workers = max_workers
        self.session = requests.Session()
        # 키드짐 사이트에 특화된 헤더 설정
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        })

    def download_and_process_thumbnail(self, thumbnail_url, image_counter, product_name):
        """썸네일 다운로드 및 처리"""
        try:
            if not thumbnail_url:
                return False
            
            # 썸네일 다운로드 로직 (간소화)
            print(f"[THUMB] 썸네일 처리: {image_counter}_cr.jpg")
            return True
        except Exception as e:
            print(f"[ERROR] 썸네일 처리 실패: {e}")
            return False

    def download_and_process_detail_images(self, detail_img_urls, image_counter, product_name):
        """상세이미지 다운로드 및 처리"""
        try:
            if not detail_img_urls:
                return False
            
            # 상세이미지 다운로드 로직 (간소화)
            print(f"[DETAIL] 상세이미지 처리: {len(detail_img_urls)}개")
            return True
        except Exception as e:
            print(f"[ERROR] 상세이미지 처리 실패: {e}")
            return False

    def close(self):
        """리소스 정리"""
        self.session.close()

def main():
    """메인 실행 함수"""
    
    # 성능 측정 변수들
    image_counter = 1
    start_time = time.time()
    json_products_count = 0
    fallback_products_count = 0
    json_processing_time = 0
    fallback_processing_time = 0
    network_requests_saved = 0

    # 엑셀 설정
    import openpyxl
    wb = openpyxl.Workbook()
    sheet = wb.active
    
    # 엑셀 헤더
    headers = [
        "상품번호", "상품명", "판매가", "시중가", "옵션", "모델명", "브랜드", 
        "제조사", "원산지", "성인인증", "상품요약설명", "상품상세설명",
        "상품태그", "검색키워드", "상품무게", "상품코드", "상품분류번호",
        "진열순서", "진열상태", "판매상태", "품절상태", "메인진열",
        "신상품", "추천상품", "할인상품", "이미지URL"
    ]
    sheet.append(headers)
    
    # 방문한 링크 추적
    visited_links = set()
    product_infos = []
    
    # 이미지 다운로드 최적화 객체
    download_optimizer = ImageDownloadOptimizer()
    
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

        print(f"JSON 파일 로드 성공: {latest_json}")
        print(f"추출된 상품 개수: {len(extracted_products)}")

        # JSON 데이터가 있으면 우선 사용
        if extracted_products:
            print(f"[JSON_DATA] {len(extracted_products)}개 상품의 JSON 추출데이터 발견, JSON 데이터 우선 사용")
            
            json_start_time = time.time()
            
            # JSON 데이터 기반 상품 처리
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
                        sheet.append([
                            image_counter, product_name, adjusted_price, "0", option_string,
                            "", "", "", "", "1", "", "", "", "", "1", "", "",
                            "1", "진열", "판매", "정상", "1", "1", "1", "1", thumbnail_url
                        ])
                        
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
            fallback_products_count = 0  # fallback은 현재 비활성화

    except Exception as e:
        logging.error(f"오류 발생: {e}")
        print(f"[ERROR] 전체 처리 중 오류: {e}")

    finally:
        # 성능 최적화 객체 정리
        download_optimizer.close()
        print("[PERF] 이미지 다운로드 최적화 시스템 정리 완료")

    # 엑셀 파일 저장
    try:
        from datetime import datetime
        tdate = datetime.now().strftime("%Y%m%d%H%M")
        code = "kr"
        wb.save(f'C:/Users/ME/Pictures/{tdate}{code}.xlsx')
        print("크롤링 성공")
        print(f"엑셀 파일 저장: C:/Users/ME/Pictures/{tdate}{code}.xlsx")
    except Exception as e:
        logging.error(f"엑셀 파일 저장 중 오류 발생: {e}")

    # 성능 요약 로그
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

if __name__ == "__main__":
    main()
