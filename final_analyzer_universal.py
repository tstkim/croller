"""
상품 페이지 직접 분석 및 정확한 선택자 탐지 (범용 버전)
"""
import asyncio
import traceback
from playwright.async_api import async_playwright
from config import *
from login_manager import LoginManager
import json
import re
from datetime import datetime
from smart_detector_final import SmartDetector
import urllib.request
import urllib.error
from PIL import Image
import io
import requests
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import hashlib


class FinalAnalyzer:
    def __init__(self):
        self.login_manager = LoginManager()
        self.smart_detector = SmartDetector()
        self.selectors = {}
        self.test_data = []
        # 중복 이미지 추적을 위한 해시 집합
        self.image_hashes = set()
        # 성능 최적화 관련 속성
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.verified_images_cache = {}  # URL -> (valid, file_size) 캐시
        self.cache_lock = Lock()
        self.max_workers = 4
    
    async def _detect_product_link_selector(self, page):
        """상품 갤러리에서 상품 링크 a 태그의 선택자를 동적으로 탐지"""
        handles = await page.query_selector_all('a')
        selector_count = {}
        for handle in handles:
            href = await handle.get_attribute('href')
            if href and PRODUCT_LINK_PATTERN in href:
                id_attr = await handle.get_attribute('id')
                class_attr = await handle.get_attribute('class')
                if id_attr:
                    sel = f"a#{id_attr}"
                elif class_attr:
                    sel = f"a.{'.'.join(class_attr.split())}"
                else:
                    sel = f'a[href*="{PRODUCT_LINK_PATTERN}"]'
                selector_count[sel] = selector_count.get(sel, 0) + 1
        if selector_count:
            return max(selector_count, key=selector_count.get)
        return f'a[href*="{PRODUCT_LINK_PATTERN}"]'

    async def run(self):
        """메인 실행"""
        print("[ANALYZER] 최종 상품 분석기 시작...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
            page = await context.new_page()
            try:
                # 로그인
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
                
                # 갤러리 페이지로 이동
                await page.goto(GALLERY_URL, wait_until="domcontentloaded", timeout=30000, referer=MAIN_URL)
                await page.wait_for_load_state("networkidle", timeout=15000)
                print(f"[LOG] 갤러리 이동 후 현재 URL: {page.url}")
                
                if not page.url.startswith(GALLERY_URL.split('?')[0]):
                    print(f"[WARNING] 갤러리 페이지로 정상 이동하지 못했습니다. 현재 URL: {page.url}")
                
                # 상품 링크 선택자 동적 탐지
                product_link_selector = await self._detect_product_link_selector(page)
                self.selectors['상품링크'] = product_link_selector
                
                # 테스트 링크 수집
                test_links = await self._get_test_links(page, product_link_selector)
                print(f"[OK] 수집된 테스트 링크: {len(test_links)}개")
                
                if test_links:
                    # 선택자 탐지
                    print(f"[DETECT] 선택자 탐지...")
                    await self._analyze_selectors(page, test_links[0])
                    # 3개 상품 강제 처리
                    await self._extract_three_products(page, test_links)
                
                # 결과 저장
                self._save_result()
            finally:
                await browser.close()
    
    async def _get_test_links(self, page, product_link_selector=None):
        """테스트 링크 수집"""
        try:
            await page.goto(GALLERY_URL, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            selector = product_link_selector or f'a[href*="{PRODUCT_LINK_PATTERN}"]'
            links = await page.evaluate(f'''
                () => {{
                    const links = Array.from(document.querySelectorAll('{selector}'));
                    return links.map(link => link.href).filter(href => href);
                }}
            ''')
            unique_links = list(set(links))[:10]
            return unique_links
            
        except Exception as e:
            print(f"[ERROR] 링크 수집 실패: {e}")
            return [SAMPLE_PRODUCT_URL]
    
    async def _analyze_selectors(self, page, sample_product_url):
        """선택자 지능형 분석 (SmartDetector + 기본 선택자 보완)"""
        print(f"[SMART] SmartDetector 4단계 지능형 탐지 시작...")
        
        # 먼저 기본 선택자들을 설정 (보장된 선택자)
        base_selectors = {
            '상품리스트': '.goods-list li, .item-list li, [class*="item"], li[class*="goods"]',
            '상품명': '.name',
            '가격': '.org_price', 
            '선택옵션': 'select:nth-of-type(2)',
            '썸네일': '.viewImgWrap img',
            '상세페이지': '.goods_description img'
        }
        
        print(f"[BASE] 기본 선택자 {len(base_selectors)}개 설정")
        self.selectors.update(base_selectors)
        
        try:
            # 개별 상품 페이지로 이동
            print(f"[SMART] 개별 상품 페이지로 이동: {sample_product_url}")
            await page.goto(sample_product_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # SmartDetector로 추가 선택자 탐지 시도 (개별 상품 페이지에서)
            detected_selectors = await self.smart_detector.detect_selectors(page, sample_product_url)
            
            if detected_selectors and len(detected_selectors) > 0:
                print(f"[SMART] SmartDetector 성공! 탐지 단계: {self.smart_detector.detected_stage}")
                print(f"[SMART] 탐지된 선택자: {list(detected_selectors.keys())}")
                
                # SmartDetector 선택자로 기본 선택자 개선 시도
                for key, value in detected_selectors.items():
                    if key in self.selectors:
                        print(f"[UPDATE] {key}: {self.selectors[key]} -> {value}")
                        self.selectors[key] = value
                    else:
                        print(f"[ADD] {key}: {value}")
                        self.selectors[key] = value
            else:
                print(f"[SMART] SmartDetector 탐지 실패 또는 결과 없음, 기본 선택자만 사용")
            
            print(f"[FINAL] 최종 선택자 설정 완료 ({len(self.selectors)}개):")
            for key, value in self.selectors.items():
                print(f"   {key}: {value}")
            # HTML 구조 분석 디버깅 실행 (DEBUG 모드)
            debug_mode = True  # 필요시 config.py에서 DEBUG_MODE 변수로 제어 가능
            await self._debug_html_structure(page, debug_mode)
                
        except Exception as e:
            print(f"[ERROR] 선택자 분석 실패: {e}")
            print(f"[TRACE] 트레이스백:")
            import traceback
            traceback.print_exc()
    
    async def _extract_three_products(self, page, test_links):
        """설정된 개수만큼 상품 강제 추출"""
        print(f"[EXTRACT] {TEST_PRODUCTS}개 상품 강제 추출 시작...")
        
        successful_count = 0
        max_attempts = min(len(test_links), 10)
        
        # 중복 상품명 방지를 위한 집합 추가
        seen_names = set()
        
        for i in range(max_attempts):
            if successful_count >= TEST_PRODUCTS:
                print(f"[COMPLETE] 목표 달성! {TEST_PRODUCTS}개 상품 추출 완료")
                break
                
            link = test_links[i]
            print(f"\n{'='*50}")
            print(f"[PRODUCT] 상품 {i+1} 처리 중... (성공: {successful_count}/{TEST_PRODUCTS})")
            print(f"[LINK] {link}")
            
            try:
                data = await self._extract_single_product(page, link)
                
                if data and data.get('상품명', '').strip():
                    # 상품명 정제 및 유효성 검증
                    product_name = data.get('상품명', '').strip().lower()
                    
                    # 키드짐 특화 카테고리명 및 무효한 상품명 제외
                    invalid_names = {
                        '볼&골대', '댄스&창', '댄스&소셜', '네트게임', '타겟게임',
                        '흔바테감', '네트리더', '게임도구', '음향기기', '무대배경',
                        '교구', '체육용품', '놀이기구', '무대도구', '카테고리',
                        '상품명을 찾을 수 없습니다.', '상품명 정보 없음', '좋아요',
                        '찜하기', '장바구니', '바로구매', '관심상품'
                    }
                    
                    # 정제된 상품명이 무효한 이름인지 확인
                    is_invalid = any(invalid.lower() == product_name for invalid in invalid_names)
                    
                    # 중복 및 유효성 검사
                    if not is_invalid and product_name not in seen_names:
                        seen_names.add(product_name)
                        self.test_data.append(data)
                        successful_count += 1
                        
                        print(f"[SUCCESS] 상품 {i+1} 성공! ({successful_count}/{TEST_PRODUCTS})")
                        print(f"   [NAME] 상품명: {data.get('상품명', '')[:50]}...")
                        print(f"   [PRICE] 가격: {data.get('가격', 'N/A')}")
                        print(f"   [OPTIONS] 옵션: {len(data.get('선택옵션', []))}개")
                        print(f"   [THUMB] 썸네일: {'OK' if data.get('썸네일') else 'FAIL'}")
                        print(f"   [DETAIL] 상세이미지: {len(data.get('상세페이지', []))}개")
                    else:
                        if is_invalid:
                            print(f"[SKIP] 상품 {i+1} 무효한 상품명: {data.get('상품명', '')[:50]}...")
                        else:
                            print(f"[SKIP] 상품 {i+1} 중복된 상품명: {data.get('상품명', '')[:50]}...")
                else:
                    print(f"[FAIL] 상품 {i+1} 실패: 데이터 부족")
                    
            except Exception as e:
                print(f"[ERROR] 상품 {i+1} 오류: {str(e)[:100]}")
            
            # 서버 부하 방지
            if i < max_attempts - 1:
                await asyncio.sleep(1)
        
        print(f"[RESULT] 추출 완료: {successful_count}개 성공, 중복 제외: {len(seen_names)}개 고유 상품명")
    
    async def _extract_single_product(self, page, url):
        """단일 상품 데이터 추출"""
        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            data = {'url': url}
            
            # 상품명 (메타태그 우선 + Fallback 적용)
            product_name = None
            extraction_method = "추출 실패"
            
            # 1차 시도: 메타 태그에서 상품명 추출 (키드짐 분석 결과 반영)
            try:
                # og:title 메타 태그 확인
                og_title = await page.query_selector('meta[property="og:title"]')
                if og_title:
                    meta_title = await og_title.get_attribute('content')
                    if meta_title and meta_title.strip():
                        # 브랜드명 제거 (예: "크리스마스무대 - 키드짐-스마타임" -> "크리스마스무대")
                        clean_title = meta_title.strip().split(' - ')[0].strip()
                        
                        # 키드짐 카테고리명 제외 확인
                        kidgym_categories = [
                            '볼&골대', '댄스&창', '댄스&소셜', '네트게임', '타겟게임',
                            '흔바테감', '네트리더', '게임도구', '음향기기', '무대배경',
                            '교구', '체육용품', '놀이기구', '무대도구'
                        ]
                        
                        is_category = any(cat.lower() == clean_title.lower() for cat in kidgym_categories)
                        
                        if not is_category and len(clean_title) > 2:
                            product_name = clean_title
                            extraction_method = "og:title 메타태그"
                            print(f"[META] og:title에서 상품명 추출 성공: {product_name}")
                        else:
                            print(f"[META] og:title 카테고리명 제외: {clean_title}")
                
                # 페이지 title 태그 확인 (og:title이 없을 경우)
                if not product_name:
                    title_elem = await page.query_selector('title')
                    if title_elem:
                        title_text = await title_elem.text_content()
                        if title_text and title_text.strip():
                            clean_title = title_text.strip().split(' - ')[0].strip()
                            is_category = any(cat.lower() == clean_title.lower() for cat in kidgym_categories)
                            
                            if not is_category and len(clean_title) > 2:
                                product_name = clean_title
                                extraction_method = "페이지 title 태그"
                                print(f"[META] title에서 상품명 추출 성공: {product_name}")
                                
            except Exception as e:
                print(f"[META] 메타태그 추출 오류: {e}")
            
            # 2차 시도: 기존 선택자 방식 (Fallback)
            if not product_name and self.selectors.get('상품명'):
                try:
                    # 모든 후보 요소 가져오기
                    elements = await page.query_selector_all(self.selectors['상품명'])
                    
                    # 브랜드명 대괄호가 있는 상품명 우선 선택
                    best_name = None
                    best_score = 0
                    
                    for element in elements:
                        if element:
                            text = await element.text_content()
                            if text:
                                text = text.strip()
                                
                                # 제외 패턴 체크 (키드짐 특화 강화)
                                exclude_patterns = [
                                    '카테고리', '전체보기', '메뉴', '네비게이션', '로그인', '회원가입',
                                    '장바구니', '주문', '배송', '고객센터', '공지사항', '이벤트',
                                    '커뮤니티', '게시판', '문의', '리뷰', '소개', '브랜드',
                                    '옵션', '후기', '상세정보', '문의사항', '상품 옵션', '상품 후기',
                                    # 키드짐 카테고리명 추가
                                    '볼&골대', '댄스&창', '댄스&소셜', '네트게임', '타겟게임',
                                    '흔바테감', '네트리더', '게임도구', '음향기기', '무대배경',
                                    '교구', '체육용품', '놀이기구', '무대도구',
                                    # UI 요소
                                    '좋아요', '찜하기', '장바구니에 넣기', '바로구매'
                                ]
                                
                                should_exclude = any(pattern in text for pattern in exclude_patterns)
                                if should_exclude:
                                    continue
                                    
                                # 점수 계산
                                score = 0
                                if 3 <= len(text) <= 100:
                                    score += 10
                                
                                # 브랜드명 대괄호 초고점!
                                if '[' in text and ']' in text:
                                    score += 50
                                    
                                if score > best_score:
                                    best_score = score
                                    best_name = text
                    
                    if best_name:
                        product_name = best_name
                        extraction_method = "perfect_result 선택자"
                        print(f"[FALLBACK] 선택자에서 상품명 추출: {product_name}")
                        
                except Exception as e:
                    print(f"[FALLBACK] 선택자 추출 오류: {e}")
            
            # 최종 상품명 설정
            data['상품명'] = product_name
            
            if product_name:
                print(f"[SUCCESS] 상품명 추출 성공 ({extraction_method}): {product_name[:30]}...")
            else:
                print(f"[FAIL] 상품명 추출 실패")
            
            # 가격 (원본 텍스트 그대로 저장)
            if self.selectors.get('가격'):
                try:
                    element = await page.query_selector(self.selectors['가격'])
                    if element:
                        price_text = (await element.text_content()).strip()
                        # 원본 텍스트 그대로 저장 (나중에 main.py에서 정리)
                        data['가격'] = price_text if price_text else None
                    else:
                        data['가격'] = None
                except:
                    data['가격'] = None
            else:
                data['가격'] = None
            
            # 선택옵션
            if self.selectors.get('선택옵션'):
                try:
                    options = await page.query_selector_all(f"{self.selectors['선택옵션']} option")
                    option_list = []
                    for option in options:
                        text = (await option.text_content()).strip()
                        if text:
                            # 먼저 화폐 기호 제거
                            cleaned_text = text.replace('₩', '').replace('원', '').strip()
                            # 그 다음 유효성 검사
                            if self._is_valid_option(text):
                                # 중복 체크 후 추가
                                if cleaned_text not in option_list:
                                    option_list.append(cleaned_text)
                    data['선택옵션'] = option_list
                except:
                    data['선택옵션'] = []
            else:
                data['선택옵션'] = []
            
            # 썸네일
            if self.selectors.get('썸네일'):
                try:
                    element = await page.query_selector(self.selectors['썸네일'])
                    if element:
                        src = await element.get_attribute('src')
                        data_src = await element.get_attribute('data-src')
                        data_original = await element.get_attribute('data-original')
                        
                        # 최선의 URL 선택 후 정규화
                        raw_url = data_original or data_src or src
                        if raw_url:
                            normalized_url = self._normalize_url(raw_url, page.url)
                            data['썸네일'] = normalized_url
                        else:
                            data['썸네일'] = None
                    else:
                        data['썸네일'] = None
                except:
                    data['썸네일'] = None
            else:
                data['썸네일'] = None
            
            # 상세페이지 이미지
            if self.selectors.get('상세페이지'):
                try:
                    print(f"[DEBUG] 상세페이지 이미지 추출 시작...")
                    print(f"[DEBUG] 사용할 선택자: {self.selectors['상세페이지']}")
                    
                    # lazy loading을 위한 단계적 스크롤
                    print("[DEBUG] 페이지 스크롤 시작...")
                    scroll_steps = [0, 0.25, 0.5, 0.75, 1.0]
                    for step in scroll_steps:
                        await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {step})")
                        await page.wait_for_timeout(800)  # 키드짐 특화: 대기시간 증가 (lazy loading 대응)
                    
                    # 이미지 로드 완료 대기 추가
                    await page.wait_for_timeout(1000)
                    
                    # 키드짐 특화 선택자를 우선순위로 배치
                    selectors_to_try = [
                        '.goods_description img',  # 키드짐 상세 설명 영역
                        '.product_detail img',     # 상품 상세 영역  
                        'div[class*="prd"] img',   # prd 관련 클래스
                        '.goods_info img',         # 상품 정보 영역
                        self.selectors['상세페이지'],  # SmartDetector가 찾은 선택자
                        '#prdDetail img',
                        '.detail img',
                        '.detail-content img',
                        '.product-detail img',
                        '.product-content img',
                        '.content img',
                        '.contents img',
                        'div[class*="detail"] img',
                        'div[class*="content"] img',
                        'div[id*="detail"] img',
                        'img[src*="detail"]',
                        'img[src*="content"]',
                        'img'  # 최후의 수단
                    ]
                    
                    detail_images = []
                    for selector in selectors_to_try:
                        try:
                            print(f"[DEBUG] 선택자 시도: {selector}")
                            images = await page.query_selector_all(selector)
                            print(f"[DEBUG] 찾은 이미지 수: {len(images)}")
                            
                            for img in images:
                                src = await img.get_attribute('src')
                                data_src = await img.get_attribute('data-src')
                                data_original = await img.get_attribute('data-original')
                                best_url = data_original or data_src or src
                                
                                if best_url:
                                    # URL 정규화
                                    normalized_url = self._normalize_url(best_url, page.url)
                                    # 썸네일 URL과 동일한지 확인
                                    thumbnail_url = data.get('썸네일', '')
                                    
                                    # 유효성 검사 및 중복 체크 (Playwright fallback 지원)
                                    if (normalized_url and 
                                        await self._is_valid_detail_image(normalized_url, page) and 
                                        normalized_url not in detail_images and
                                        normalized_url != thumbnail_url):
                                        detail_images.append(normalized_url)
                                        print(f"[DEBUG] 유효한 상세 이미지 추가: {normalized_url}")
                            
                            # 유효한 이미지를 찾았으면 다음 선택자는 시도하지 않음
                            if detail_images:
                                print(f"[DEBUG] {selector} 선택자로 {len(detail_images)}개 이미지 찾음")
                                break
                                
                        except Exception as e:
                            print(f"[DEBUG] {selector} 선택자 오류: {e}")
                        
                        # 키드짐 특화: 각 선택자 시도 간격 증가 (DOM 로딩 대기)
                        await page.wait_for_timeout(300)
                    
                    data['상세페이지'] = detail_images[:10]
                    print(f"[DEBUG] 최종 상세페이지 이미지: {len(data['상세페이지'])}개")
                    
                except Exception as e:
                    print(f"[ERROR] 상세페이지 추출 실패: {e}")
                    import traceback
                    traceback.print_exc()
                    data['상세페이지'] = []
            else:
                data['상세페이지'] = []
            
            return data
            
        except Exception as e:
            print(f"[ERROR] 상품 추출 실패: {e}")
            return None
    
    def _is_valid_option(self, text):
        """유효한 선택옵션인지 판단 (너무 강하지 않게, 안전하게)"""
        if not text:
            return False

        text_lower = text.lower().strip()

        # 명확히 제외할 패턴들 (은행/결제/배송/안내문구)
        exact_exclude = [
            '선택', '-- 선택 --', '옵션선택', '옵션을 선택해주세요',
            '- [필수] 옵션을 선택해 주세요 -', '-------------------',
            '인터넷뱅킹 바로가기', '선택해주세요', '선택하세요'
        ]
        partial_exclude = [
            '은행', '계좌', '결제', '카드', '배송', '수령', 'pay', 'bank', 'delivery', 'shipping', 'account', 'method'
        ]

        # 정확히 일치하는 제외 패턴
        for pattern in exact_exclude:
            if text.strip() == pattern or text_lower == pattern.lower():
                return False

        # 부분 일치(단어 단위)만 제외 (너무 긴 옵션은 제외하지 않음)
        for pattern in partial_exclude:
            if pattern in text_lower and len(text_lower) <= 10:
                return False

        return True
        
    def _normalize_url(self, url, base_url):
        """상대 URL을 절대 URL로 변환하고 유효성 검사"""
        if not url:
            return None
            
        url = url.strip()
        
        # 이미 절대 URL인 경우
        if url.startswith(('http://', 'https://')):
            return url
            
        # 상대 URL인 경우 절대 URL로 변환
        if url.startswith('//'):
            return f"https:{url}"
        elif url.startswith('/'):
            from urllib.parse import urljoin
            return urljoin(base_url, url)
        else:
            # 상대 경로
            from urllib.parse import urljoin
            return urljoin(base_url, url)
        
    async def _get_image_info_via_playwright(self, page, url):
        """Playwright를 통한 이미지 정보 추출 (403 오류 대응)"""
        try:
            # 브라우저에서 이미지 정보 추출
            result = await page.evaluate(f"""
                async () => {{
                    try {{
                        const img = new Image();
                        return new Promise((resolve, reject) => {{
                            img.onload = () => {{
                                resolve({{
                                    width: img.naturalWidth,
                                    height: img.naturalHeight,
                                    src: img.src
                                }});
                            }};
                            img.onerror = () => reject(new Error('Image load failed'));
                            img.src = '{url}';
                            
                            // 5초 타임아웃
                            setTimeout(() => reject(new Error('Timeout')), 5000);
                        }});
                    }} catch (e) {{
                        return null;
                    }}
                }}
            """)
            return result
        except Exception as e:
            print(f"[FALLBACK] Playwright 이미지 정보 추출 실패: {e}")
            return None

    async def _is_valid_detail_image(self, url, page=None):
        """키드짐 특화: 유효한 상세 이미지 검증 (가로 300px 이상, 파일 크기 5KB 이상, 의미 필터링 완화, Playwright fallback 지원)"""
        if not url:
            return False
        
        url_lower = url.lower()
        
        # 1단계: URL 패턴 기반 필터링 (확실히 제외할 UI 요소들)
        exclude_patterns = [
            'logo', 'icon', 'btn', 'button', 'menu', 'nav', 
            'arrow', 'quick', 'zzim', 'wishlist',
            'banner', 'header', 'footer',  # 'common' 제거 (키드짐 특화 완화)
            'popup', 'close', 'search', 'cart',
            'sns', 'facebook', 'twitter', 'kakao',
            'top_btn', 'scroll', 'floating',
            # 공통 정보 이미지 필터링 추가
            '_wg/', 'detail_img_info', 'delivery_info',
            'exchange_info', 'return_info', 'notice_info',
            # 키드짐 특화 워터마크 및 UI 요소 필터링
            'watermark', 'watermark3', 'sold_out', 'stamp',
            '0516100/', 'overlay', 'badge', 'mark',
            'thumbnail_', '_thumb', 'list_', '_list',
            # 기준서 추가: 무의미한 이미지 패턴
            'guide_', 'info_', 'notice_', 'help_',
            'event_', 'promotion_', 'ad_', 'banner_'
        ]
        
        # 키드짐 특화: 상품 이미지 경로 우대 (필터링 우선 통과)
        is_product_image = '/web/product/' in url_lower or '/product/' in url_lower
        
        # 특정 패턴이 포함된 경우 제외 (단, 상품 이미지 경로는 예외)
        if not is_product_image:
            for pattern in exclude_patterns:
                if pattern in url_lower:
                    print(f"[FILTER] 패턴 '{pattern}' 발견으로 이미지 제외: {url}")
                    return False
        else:
            print(f"[PRIORITY] 키드짐 상품 이미지 경로 감지, 우선 검증: {url}")
        
        # 2단계: 이미지 파일 형식 확인
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        has_image_ext = any(ext in url_lower for ext in image_extensions)
        if not has_image_ext:
            print(f"[FILTER] 이미지 확장자 없음으로 제외: {url}")
            return False
        
        # 3단계: 실제 이미지 다운로드 및 해상도/크기 검증 (기준서 요구사항)
        try:
            import requests
            from PIL import Image
            from io import BytesIO
            
            # 키드짐 사이트에 맞는 헤더 설정 (main.py ImageDownloadOptimizer와 동일)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://kidgymb2b.co.kr/',
                'Accept': 'image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'image',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'same-origin'
            }
            
            # 이미지 헤더만 다운로드하여 크기 확인 (성능 최적화)
            response = requests.head(url, headers=headers, timeout=10)
            if response.status_code != 200:
                # HTTP 403 등의 오류 발생 시 Playwright fallback 시도
                if response.status_code == 403 and page:
                    print(f"[FALLBACK] HTTP 403 오류, Playwright로 재시도: {url}")
                    try:
                        # Playwright를 통한 이미지 정보 추출
                        image_info = await self._get_image_info_via_playwright(page, url)
                        if image_info and image_info.get('width', 0) >= 300:
                            print(f"[FALLBACK] Playwright로 성공 ({image_info['width']}x{image_info['height']}): {url}")
                            return True
                    except Exception as e:
                        print(f"[FALLBACK] Playwright 실패: {url} - {e}")
                
                print(f"[FILTER] HTTP 응답 오류 ({response.status_code})으로 이미지 제외: {url}")
                return False
            
            # 파일 크기 검증 (기준서: 파일 크기 필터링)
            content_length = response.headers.get('content-length')
            if content_length:
                file_size = int(content_length)
                # 키드짐 특화: 너무 작은 파일 (5KB 미만) 제외 (기존 10KB에서 완화)
                if file_size < 5120:  # 5KB
                    print(f"[FILTER] 파일 크기 너무 작음 ({file_size} bytes)으로 이미지 제외: {url}")
                    return False
                # 너무 큰 파일 (10MB 초과) 제외
                if file_size > 10485760:  # 10MB
                    print(f"[FILTER] 파일 크기 너무 큼 ({file_size} bytes)으로 이미지 제외: {url}")
                    return False
            
            # 해상도 검증을 위해 실제 이미지 일부 다운로드 (기준서: 가로 660px 이상)
            # 키드짐 사이트에 맞는 헤더 설정 (main.py ImageDownloadOptimizer와 동일)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://kidgymb2b.co.kr/',
                'Accept': 'image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'image',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'same-origin'
            }
            response = requests.get(url, headers=headers, timeout=15, stream=True)
            if response.status_code != 200:
                # HTTP 403 등의 오류 발생 시 Playwright fallback 시도 (GET 요청)
                if response.status_code == 403 and page:
                    print(f"[FALLBACK] HTTP 403 오류 (GET), Playwright로 재시도: {url}")
                    try:
                        # Playwright를 통한 이미지 정보 추출
                        image_info = await self._get_image_info_via_playwright(page, url)
                        if image_info and image_info.get('width', 0) >= 300:
                            print(f"[FALLBACK] Playwright로 성공 ({image_info['width']}x{image_info['height']}): {url}")
                            return True
                    except Exception as e:
                        print(f"[FALLBACK] Playwright 실패: {url} - {e}")
                
                print(f"[FILTER] 이미지 다운로드 실패로 제외: {url}")
                return False
            
            # 이미지 해상도 확인
            try:
                image_data = BytesIO()
                downloaded = 0
                # 최대 100KB만 다운로드해서 해상도 확인 (성능 최적화)
                for chunk in response.iter_content(chunk_size=8192):
                    if downloaded > 102400:  # 100KB 제한
                        break
                    image_data.write(chunk)
                    downloaded += len(chunk)
                
                image_data.seek(0)
                with Image.open(image_data) as img:
                    width, height = img.size
                    
                    # 키드짐 특화: 가로 해상도 300px 이상 (기존 660px에서 완화)
                    if width < 300:
                        print(f"[FILTER] 해상도 기준 미달 ({width}x{height})으로 이미지 제외: {url}")
                        return False
                    
                    print(f"[VALID] 해상도 검증 통과 ({width}x{height}): {url}")
                    return True
                    
            except Exception as e:
                print(f"[FILTER] 이미지 해상도 확인 실패로 제외: {url} - {e}")
                return False
                
        except Exception as e:
            print(f"[FILTER] 이미지 검증 중 오류로 제외: {url} - {e}")
            return False
    
    def _save_result(self):
        """결과 저장 (SmartDetector 정보 포함)"""
        result = {
            '선택자': self.selectors,
            '추출데이터': self.test_data,
            'SmartDetector정보': self.smart_detector.get_detection_info(),
            '생성일시': datetime.now().isoformat()
        }
        
        filename = f"perfect_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"[SAVE] 결과 저장: {filename}")
        print("=" * 70)
        print("[FINAL] 최종 결과:")
        
        # SmartDetector 정보 출력
        detection_info = self.smart_detector.get_detection_info()
        if detection_info['detected_stage']:
            print(f"   [AI] 탐지방식: {detection_info['detected_stage']}")
        else:
            print(f"   [AI] 탐지방식: 기본 선택자 사용")
            
        print(f"   [COUNT] 선택자 개수: {len(self.selectors)}개")
        print(f"   [NAME] 상품명: {self.selectors.get('상품명', 'FAIL')}")
        print(f"   [PRICE] 가격: {self.selectors.get('가격', 'FAIL')}")
        print(f"   [OPTIONS] 선택옵션: {self.selectors.get('선택옵션', 'FAIL')}")
        print(f"   [THUMB] 썸네일: {self.selectors.get('썸네일', 'FAIL')}")
        print(f"   [DETAIL] 상세페이지: {self.selectors.get('상세페이지', 'FAIL')}")
        print(f"   [DATA] 추출된 상품: {len(self.test_data)}개")
    
    async def _debug_html_structure(self, page, debug_mode=False):
        """실시간 HTML 구조 분석 디버깅 기능"""
        if not debug_mode:
            return
            
        print("\n" + "="*70)
        print("[DEBUG] HTML 구조 분석 시작...")
        print("="*70)
        
        try:
            # 현재 페이지 URL 확인
            current_url = page.url
            print(f"[DEBUG] 분석 대상 URL: {current_url}")
            
            # 모든 텍스트 요소 수집
            text_elements = await self._collect_text_elements(page)
            
            # 상품명 후보 분석
            await self._analyze_product_name_candidates(text_elements)
            
            # 가격 후보 분석
            await self._analyze_price_candidates(text_elements)
            
            # 옵션 후보 분석
            await self._analyze_option_candidates(text_elements)
            
            # 이미지 후보 분석
            await self._analyze_image_candidates(page)
            
            print("="*70)
            print("[DEBUG] HTML 구조 분석 완료")
            print("="*70 + "\n")
            
        except Exception as e:
            print(f"[DEBUG ERROR] HTML 구조 분석 실패: {e}")
            
    async def _collect_text_elements(self, page):
        """모든 텍스트 요소와 선택자 수집"""
        text_elements = []
        
        # 다양한 태그에서 텍스트 수집
        tags_to_check = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'div', 'strong', 'b', 'em', 'i', 'td', 'th', 'li', 'a']
        
        for tag in tags_to_check:
            try:
                elements = await page.query_selector_all(tag)
                for i, element in enumerate(elements):
                    text = await element.text_content()
                    if text and text.strip():
                        # 클래스와 ID 속성 수집
                        class_attr = await element.get_attribute('class')
                        id_attr = await element.get_attribute('id')
                        
                        # 선택자 생성
                        selectors = []
                        if id_attr:
                            selectors.append(f"#{id_attr}")
                        if class_attr:
                            for cls in class_attr.split():
                                selectors.append(f".{cls}")
                        selectors.append(tag)
                        
                        text_elements.append({
                            'text': text.strip(),
                            'tag': tag,
                            'selectors': selectors,
                            'class': class_attr,
                            'id': id_attr
                        })
            except:
                continue
                
        print(f"[DEBUG] 수집된 텍스트 요소: {len(text_elements)}개")
        return text_elements
    
    async def _analyze_product_name_candidates(self, text_elements):
        """상품명 후보 분석"""
        print("\n[DEBUG] === 상품명 후보 분석 ===")
        
        product_name_keywords = ['product', 'goods', 'item', 'name', 'title']
        candidates = []
        
        for element in text_elements:
            text = element['text']
            selectors = element['selectors']
            
            # 길이 기반 필터링 (상품명은 보통 10~100자)
            if 10 <= len(text) <= 100:
                score = 0
                
                # 클래스명에 상품명 관련 키워드 포함시 가점
                for selector in selectors:
                    for keyword in product_name_keywords:
                        if keyword in selector.lower():
                            score += 20
                            
                # 헤더 태그 가점
                if element['tag'] in ['h1', 'h2', 'h3']:
                    score += 10
                    
                # 카테고리명으로 보이는 텍스트 감점
                # 카테고리명으로 보이는 텍스트 감점 (강화)
                exclude_words = [
                    # 키드짐 특화 카테고리
                    '카테고리', '분류', '볼&골대', '체육용품', '운동기구', '놀이기구',
                    '네트리더', '타겟게임', '라켓게임', '멀티시스템', '캐치게임',
                    '점프&밸런스', '레크리에이션', '놀이교구', '유아체육', '어린이체육',
                    # 범용 UI 요소
                    '메뉴', '네비게이션', '검색', '정렬', '필터', '브랜드', '제조사'
                ]
                if any(word in text for word in exclude_words):
                    score -= 50  # 강화된 감점
                    
                if score > 0:
                    candidates.append({
                        'text': text,
                        'selectors': selectors,
                        'score': score
                    })
        
        # 점수순 정렬
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"[DEBUG] 상품명 후보 {min(5, len(candidates))}개:")
        for i, candidate in enumerate(candidates[:5]):
            print(f"  {i+1}. '{candidate['text'][:50]}...' (점수: {candidate['score']})")
            print(f"     선택자: {', '.join(candidate['selectors'][:3])}")
            
    async def _analyze_price_candidates(self, text_elements):
        """가격 후보 분석"""
        print("\n[DEBUG] === 가격 후보 분석 ===")
        
        price_patterns = [
            r'[\d,]+원',
            r'₩[\d,]+',
            r'\$[\d,]+\.?\d*',
            r'[\d,]+\s*won',
            r'[\d]{1,3}(?:,\d{3})*'
        ]
        
        candidates = []
        
        for element in text_elements:
            text = element['text']
            selectors = element['selectors']
            
            # 가격 패턴 매칭
            for pattern in price_patterns:
                if re.search(pattern, text):
                    score = 10
                    
                    # 가격 관련 클래스명 가점
                    price_keywords = ['price', 'cost', 'amount', 'money', 'won']
                    for selector in selectors:
                        for keyword in price_keywords:
                            if keyword in selector.lower():
                                score += 25
                                
                    # 짧은 텍스트 가점 (가격은 보통 간결함)
                    if len(text) <= 20:
                        score += 15
                        
                    candidates.append({
                        'text': text,
                        'selectors': selectors,
                        'score': score
                    })
                    break
        
        # 점수순 정렬
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"[DEBUG] 가격 후보 {min(5, len(candidates))}개:")
        for i, candidate in enumerate(candidates[:5]):
            print(f"  {i+1}. '{candidate['text']}' (점수: {candidate['score']})")
            print(f"     선택자: {', '.join(candidate['selectors'][:3])}")
            
    async def _analyze_option_candidates(self, text_elements):
        """선택 옵션 후보 분석"""
        print("\n[DEBUG] === 선택 옵션 후보 분석 ===")
        
        option_keywords = ['option', 'select', 'choice', 'variant', 'size', 'color']
        candidates = []
        
        for element in text_elements:
            selectors = element['selectors']
            
            # 옵션 관련 클래스명 검사
            for selector in selectors:
                for keyword in option_keywords:
                    if keyword in selector.lower():
                        candidates.append({
                            'selector': selector,
                            'text': element['text'][:30] + '...'
                        })
                        break
        
        print(f"[DEBUG] 옵션 관련 선택자 {min(5, len(candidates))}개:")
        for i, candidate in enumerate(candidates[:5]):
            print(f"  {i+1}. {candidate['selector']} -> '{candidate['text']}'")
            
    async def _analyze_image_candidates(self, page):
        """이미지 후보 분석"""
        print("\n[DEBUG] === 이미지 후보 분석 ===")
        
        try:
            # 모든 이미지 요소 수집
            images = await page.query_selector_all('img')
            
            thumbnail_candidates = []
            detail_candidates = []
            
            for i, img in enumerate(images):
                src = await img.get_attribute('src')
                alt = await img.get_attribute('alt') or ''
                class_attr = await img.get_attribute('class') or ''
                id_attr = await img.get_attribute('id') or ''
                
                if src:
                    # 썸네일 후보 분석
                    if any(keyword in class_attr.lower() for keyword in ['thumb', 'thumbnail', 'main', 'primary']):
                        thumbnail_candidates.append(f"img.{class_attr.split()[0] if class_attr else ''}")
                    elif any(keyword in id_attr.lower() for keyword in ['thumb', 'thumbnail', 'main']):
                        thumbnail_candidates.append(f"#{id_attr}")
                        
                    # 상세 이미지 후보 분석  
                    if any(keyword in class_attr.lower() for keyword in ['detail', 'content', 'description']):
                        detail_candidates.append(f"img.{class_attr.split()[0] if class_attr else ''}")
                        
            print(f"[DEBUG] 썸네일 후보 {min(3, len(thumbnail_candidates))}개:")
            for i, candidate in enumerate(thumbnail_candidates[:3]):
                print(f"  {i+1}. {candidate}")
                
            print(f"[DEBUG] 상세이미지 후보 {min(3, len(detail_candidates))}개:")
            for i, candidate in enumerate(detail_candidates[:3]):
                print(f"  {i+1}. {candidate}")
                
        except Exception as e:
            print(f"[DEBUG ERROR] 이미지 분석 실패: {e}")


if __name__ == "__main__":
    analyzer = FinalAnalyzer()
    asyncio.run(analyzer.run())
    print("[COMPLETE] 추출 완료! 자동 종료됩니다.")
