#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import ssl
import time
import re
import logging
from datetime import datetime
from openpyxl import Workbook
from config import *
from utils.image_optimizer import ImageDownloadOptimizer
from final_analyzer_universal import FinalAnalyzer


# SSL 인증서 검증 비활성화
ssl._create_default_https_context = ssl._create_unverified_context

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 테스트할 상품 개수 추가 확인
TEST_PRODUCTS = getattr(sys.modules[__name__], 'TEST_PRODUCTS', 3) if 'sys' in locals() else 3


class ProductCrawler(FinalAnalyzer):
    """FinalAnalyzer를 상속받아 대량 크롤링을 수행하는 클래스"""
    
    def __init__(self):
        super().__init__()  # FinalAnalyzer 초기화
        # 성능 측정 변수들
        self.image_counter = 1
        self.start_time = time.time()
        self.json_products_count = 0
        self.fallback_products_count = 0
        self.json_processing_time = 0
        self.fallback_processing_time = 0
        self.network_requests_saved = 0
        
        # 엑셀 설정
        import openpyxl
        self.wb = openpyxl.Workbook()
        self.sheet = self.wb.active
        
        # 엑셀 헤더 (절대 변경 금지)
        self.headers = [
            "상품번호", "상품명", "판매가", "시중가", "옵션", "모델명", "브랜드", 
            "제조사", "원산지", "성인인증", "상품요약설명", "상품상세설명",
            "상품태그", "검색키워드", "상품무게", "상품코드", "상품분류번호",
            "진열순서", "진열상태", "판매상태", "품절상태", "메인진열",
            "신상품", "추천상품", "할인상품", "이미지URL"
        ]
        self.sheet.append(self.headers)
        
        # 방문한 링크 추적
        self.visited_links = set()
        self.product_infos = []
        
        # 이미지 다운로드 최적화 객체
        self.download_optimizer = ImageDownloadOptimizer()
        # 이미지 폴더 경로 저장 (엑셀 저장 시 같은 경로 사용)
        self.image_base_path = self.download_optimizer.base_path
    
    async def run_full_crawling(self):
        """메인 크롤링 실행 (JSON 의존성 제거됨)"""
        print("[JSON_REMOVED] ProductCrawler 시작 - JSON 파일 의존성 제거됨")
        
        # Playwright 브라우저 초기화 (FinalAnalyzer 패턴 활용)
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
            page = await context.new_page()
            
            try:
                print("[JSON_REMOVED] 실시간 선택자 탐지 모드로 전환")
                
                # 1. 로그인 처리 (부모 클래스 login_manager 활용)
                if LOGIN_REQUIRED:
                    login_selectors = await self.login_manager.auto_login(page, MAIN_URL, USERNAME, PASSWORD)
                    await asyncio.sleep(1)
                    print(f"[LOG] 로그인 후 쿠키: {await context.cookies()}")
                    await page.reload()
                    if login_selectors:
                        self.selectors['로그인_아이디_선택자'] = login_selectors.get('id')
                        self.selectors['로그인_비밀번호_선택자'] = login_selectors.get('pw')
                        self.selectors['로그인_버튼_선택자'] = login_selectors.get('btn')
                
                print(f"[LOG] 로그인 후 현재 URL: {page.url}")
                
                # 2. 갤러리 페이지로 이동
                await page.goto(GALLERY_URL, wait_until="domcontentloaded", timeout=30000, referer=MAIN_URL)
                await page.wait_for_load_state("networkidle", timeout=15000)
                print(f"[LOG] 갤러리 이동 후 현재 URL: {page.url}")
                
                # 3. 상품 링크 선택자 동적 탐지
                product_link_selector = await self._detect_product_link_selector(page)
                self.selectors['상품링크'] = product_link_selector
                
                # 4. 테스트 링크 수집
                test_links = await self._get_test_links(page, product_link_selector)
                print(f"[OK] 수집된 테스트 링크: {len(test_links)}개")
                
                if test_links:
                    # 5. 실시간 선택자 탐지 (부모 클래스 메서드 활용)
                    print(f"[JSON_REMOVED] 실시간 선택자 탐지 시작...")
                    await self._analyze_selectors(page, test_links[0])
                    
                    print(f"[SUCCESS] 선택자 탐지 완료: {len(self.selectors)}개")
                    for key, value in self.selectors.items():
                        print(f"   [SELECTOR] {key}: {value}")
                    
                    # 6. 실제 상품 크롤링 시작 (TEST_PRODUCT_COUNT만큼)
                    print(f"[CRAWLING] {TEST_PRODUCT_COUNT}개 상품 크롤링 시작...")
                    await self._crawl_products(page, test_links)
                    
                    # 7. 엑셀 파일 저장
                    self._save_excel_file()
                    
                    print(f"[SUCCESS] 크롤링 완료: {self.image_counter-1}개 상품 처리")
                    
                else:
                    print("[ERROR] 테스트 링크 수집 실패 - Fallback 로직 필요")
                    return False
                
            except Exception as e:
                print(f"[ERROR] 크롤링 실행 실패: {e}")
                import traceback
                traceback.print_exc()
                return False
            finally:
                await browser.close()
        
        print("[JSON_REMOVED] ProductCrawler 실행 완료")
        return True
    
    async def _crawl_products(self, page, test_links):
        """상품 크롤링 실행 (TEST_PRODUCT_COUNT만큼)"""
        successful_count = 0
        seen_names = set()  # 중복 상품명 방지
        
        for i in range(min(len(test_links), 20)):  # 최대 20개 링크에서 시도
            if successful_count >= TEST_PRODUCT_COUNT:
                print(f"[COMPLETE] 목표 달성! {TEST_PRODUCT_COUNT}개 상품 추출 완료")
                break
                
            link = test_links[i]
            print(f"\n{'='*50}")
            print(f"[PRODUCT] 상품 {i+1} 처리 중... (성공: {successful_count}/{TEST_PRODUCT_COUNT})")
            print(f"[LINK] {link}")
            
            try:
                success = await self._extract_and_save_product(page, link, seen_names)
                if success:
                    successful_count += 1
                    print(f"[SUCCESS] 상품 {i+1} 성공! ({successful_count}/{TEST_PRODUCT_COUNT})")
                else:
                    print(f"[SKIP] 상품 {i+1} 건너뜀")
                    
            except Exception as e:
                print(f"[ERROR] 상품 {i+1} 오류: {str(e)[:100]}")
            
            # 서버 부하 방지
            if i < len(test_links) - 1:
                await asyncio.sleep(1)
        
        print(f"[RESULT] 크롤링 완료: {successful_count}개 성공")
    
    async def _extract_and_save_product(self, page, url, seen_names):
        """단일 상품 추출 및 저장 (부모 클래스 메서드 활용 + 이미지/엑셀 처리)"""
        try:
            # 1. 부모 클래스의 _extract_single_product 메서드 활용
            product_data = await self._extract_single_product(page, url)
            
            if not product_data or not product_data.get('상품명'):
                print(f"[SKIP] 상품 데이터 추출 실패: {url}")
                return False
            
            # 2. 상품명 중복 체크
            product_name = product_data.get('상품명', '').strip()
            if product_name.lower() in seen_names:
                print(f"[SKIP] 중복 상품명: {product_name}")
                return False
            seen_names.add(product_name.lower())
            
            # 3. 상품 상세설명 HTML 추출 (키드짐 특수 요구사항)
            detail_description_html = ""
            try:
                # 상세설명 영역 선택자들 (키드짐 사이트 기준)
                description_selectors = [
                    '.goods_intro_detail',
                    '.detail_content', 
                    '.product_detail',
                    '.goods_detail_content',
                    '.item_detail_area',
                    '[class*="detail"]',
                    '[class*="intro"]'
                ]
                
                for selector in description_selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            for element in elements:
                                html_content = await element.inner_html()
                                if html_content and len(html_content.strip()) > 50:  # 의미있는 내용만
                                    detail_description_html = html_content.strip()
                                    print(f"[DETAIL_DESC] 상세설명 추출 성공: {len(detail_description_html)}글자")
                                    break
                            if detail_description_html:
                                break
                    except Exception as e:
                        continue
                
                if not detail_description_html:
                    print(f"[WARNING] 상세설명 추출 실패: {url}")
                    
            except Exception as e:
                print(f"[ERROR] 상세설명 추출 중 오류: {e}")
            
            # 4. 가격 필터링 (10000원 미만 제외)
            price_text = product_data.get('가격', '0')
            clean_price = self._parse_price(price_text)
            if clean_price < 10000:
                print(f"[SKIP] 가격 기준 미달: {clean_price}원 < 10000원")
                return False
            
            # 4. 이미지 다운로드 및 처리
            thumbnail_url = product_data.get('썸네일', '')
            detail_img_urls = product_data.get('상세페이지', [])
            
            # 썸네일 처리
            thumbnail_success = False
            if thumbnail_url:
                thumbnail_success = self.download_optimizer.download_and_process_thumbnail(
                    thumbnail_url, self.image_counter, product_name
                )
            
            # 상세이미지 처리  
            detail_success = False
            if detail_img_urls:
                detail_success = self.download_optimizer.download_and_process_detail_images(
                    detail_img_urls, self.image_counter, product_name
                )
            
            # 5. 엑셀 데이터 생성 (기존 헤더 순서 완전 준수)
            options = product_data.get('선택옵션', [])
            options_text = " / ".join([str(opt) for opt in options[:5]]) if options else ""
            
            row_data = [
                self.image_counter,  # 상품번호
                product_name,        # 상품명
                clean_price,         # 판매가
                clean_price,         # 시중가
                options_text,        # 옵션
                "",                  # 모델명
                "키드짐",            # 브랜드
                "",                  # 제조사
                "",                  # 원산지
                "N",                 # 성인인증
                "",                  # 상품요약설명
                detail_description_html,  # 상품상세설명 (HTML 형식)
                "",                  # 상품태그
                "",                  # 검색키워드
                "",                  # 상품무게
                f"KG{self.image_counter:03}",  # 상품코드
                "",                  # 상품분류번호
                self.image_counter,  # 진열순서
                "Y",                 # 진열상태
                "Y",                 # 판매상태
                "N",                 # 품절상태
                "Y" if self.image_counter <= 5 else "N",  # 메인진열
                "Y",                 # 신상품
                "Y",                 # 추천상품
                "N",                 # 할인상품
                f"{self.image_counter}_cr.jpg"  # 이미지URL
            ]
            
            # 6. 엑셀에 데이터 추가
            self.sheet.append(row_data)
            
            print(f"[SAVE] 상품 저장 완료: {product_name} | {clean_price}원")
            print(f"   [IMAGES] 썸네일: {'OK' if thumbnail_success else 'FAIL'}, 상세: {'OK' if detail_success else 'FAIL'}")
            
            self.image_counter += 1
            return True
            
        except Exception as e:
            print(f"[ERROR] 상품 추출 실패: {e}")
            return False
    
    def _parse_price(self, price_text):
        """가격 텍스트에서 숫자 추출"""
        try:
            if not price_text:
                return 0
            # 숫자만 추출
            numbers = re.findall(r'\d+', str(price_text).replace(',', ''))
            return int(numbers[0]) if numbers else 0
        except:
            return 0
    
    def _save_excel_file(self):
        """엑셀 파일 저장 (이미지 폴더와 같은 위치)"""
        try:
            tdate = datetime.now().strftime("%Y%m%d%H%M")
            # 이미지 폴더와 같은 위치에 저장 (미리 저장된 경로 사용)
            filename = f"{self.image_base_path}/{tdate}kr.xlsx"
            self.wb.save(filename)
            print(f"[EXCEL] 엑셀 파일 저장 완료: {filename}")
            
            # 성능 리포트
            end_time = time.time()
            total_time = end_time - self.start_time
            print(f"[PERF] 총 처리 시간: {total_time:.2f}초")
            print(f"[PERF] 처리된 상품: {self.image_counter-1}개")
            
        except Exception as e:
            print(f"[ERROR] 엑셀 저장 실패: {e}")


if __name__ == "__main__":
    """
    범용 쇼핑몰 크롤러 - JSON 의존성 제거 버전
    
    주요 특징:
    - FinalAnalyzer 상속으로 실시간 선택자 탐지
    - JSON 파일 없이 선택자 자동 탐지 및 크롤링
    - 기존 결과물 형식 100% 보존 (엑셀 헤더, 이미지 규격)
    """
    print("키드짐 B2B 크롤러 시작! 작업을 시작할게요.. 잠깐만 기다려주세요*^.^*")
    
    try:
        # 비동기 크롤링 실행
        asyncio.run(ProductCrawler().run_full_crawling())
        print("[SUCCESS] 크롤링 작업이 성공적으로 완료되었습니다!")
        
    except KeyboardInterrupt:
        print("\n[STOP] 사용자에 의해 작업이 중단되었습니다.")
    except Exception as e:
        print(f"[ERROR] 크롤링 중 오류 발생: {e}")
        print("[INFO] 자세한 오류 내용은 로그를 확인해주세요.")
