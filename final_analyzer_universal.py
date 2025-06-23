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
                    self.test_data.append(data)
                    successful_count += 1
                    
                    print(f"[SUCCESS] 상품 {i+1} 성공! ({successful_count}/{TEST_PRODUCTS})")
                    print(f"   [NAME] 상품명: {data.get('상품명', '')[:50]}...")
                    print(f"   [PRICE] 가격: {data.get('가격', 'N/A')}")
                    print(f"   [OPTIONS] 옵션: {len(data.get('선택옵션', []))}개")
                    print(f"   [THUMB] 썸네일: {'OK' if data.get('썸네일') else 'FAIL'}")
                    print(f"   [DETAIL] 상세이미지: {len(data.get('상세페이지', []))}개")
                else:
                    print(f"[FAIL] 상품 {i+1} 실패: 데이터 부족")
                    
            except Exception as e:
                print(f"[ERROR] 상품 {i+1} 오류: {str(e)[:100]}")
            
            # 서버 부하 방지
            if i < max_attempts - 1:
                await asyncio.sleep(1)
        
        print(f"[RESULT] 추출 완료: {successful_count}개 성공")
    
    async def _extract_single_product(self, page, url):
        """단일 상품 데이터 추출"""
        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            data = {'url': url}
            
            # 상품명 (다중 선택자 시도 + 강화된 필터링)
            product_name = None
            
            # 다양한 상품명 선택자 후보들 (우선순위 순)
            product_name_selectors = [
                # 1순위: 상품명 전용 클래스
                '.product-name', '.product_name', '.goods-name', '.goods_name',
                '.item-name', '.item_name', '.detail-title', '.product-title',
                
                # 2순위: 포괄적 상품명 패턴
                '[class*="product"][class*="name"]', '[class*="goods"][class*="name"]',
                '[class*="product"][class*="title"]', '[class*="goods"][class*="title"]',
                
                # 3순위: 일반적인 제목 요소 (단, 키드짐에서 문제가 된 .title 제외)
                'h1', 'h2', 'h3', '.name', 
                
                # 4순위: 포괄적 패턴
                '[class*="name"]:not(.title)', '[class*="title"]:not(.title)',
                '[class*="product"]', '[class*="goods"]', '[class*="item"]',
                
                # 5순위: 기존 perfect_result 선택자 (문제가 있었지만 fallback으로)
                self.selectors.get('상품명', '.title')
            ]
            
            for selector in product_name_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if not elements:
                        continue
                    
                    best_name = None
                    best_score = 0
                    
                    for element in elements:
                        if element:
                            text = await element.text_content()
                            if text:
                                text = text.strip()
                                
                                # 강화된 제외 패턴 체크
                                # 강화된 제외 패턴 체크
                                exclude_patterns = [
                                    # 키드짐 특화 UI 요소 패턴
                                    '좋아요', '싫어요', '추천', '찜하기', '관심상품', '북마크', '즐겨찾기',
                                    '리뷰', '후기', '평가', '별점', '댓글', '문의', '신고',
                                    
                                    # 키드짐 특화 카테고리/메뉴 패턴 (강화)
                                    '볼&골대', '체육용품', '운동기구', '스포츠용품', '놀이기구',
                                    '네트리더', '타겟게임', '라켓게임', '멀티시스템', 
                                    '캐치게임', '점프&밸런스', '레크리에이션', '놀이교구',
                                    '유아체육', '어린이체육', '유아놀이', '어린이놀이',
                                    
                                    # 범용 제외 패턴 (강화)
                                    '카테고리', '전체보기', '메뉴', '네비게이션', '로그인', '회원가입',
                                    '장바구니', '주문', '배송', '고객센터', '공지사항', '이벤트',
                                    '검색', '정렬', '필터', '브랜드', '제조사', 'FAQ', 'Q&A',
                                    '이용약관', '개인정보', '정책', '가이드', '도움말'
                                    '신상품', '인기상품', '할인', '세일', '모델명', '제조사', '원산지',
                                    'quick', 'menu', 'nav', 'header', 'footer', 'banner',
                                    
                                    # 짧은 UI 텍스트
                                    '더보기', '닫기', '열기', '이전', '다음', '목록', '검색',
                                    'more', 'close', 'open', 'prev', 'next', 'list', 'search'
                                ]
                                
                                # 제외 패턴 정확 매칭 및 포함 매칭
                                should_exclude = False
                                text_lower = text.lower()
                                
                                # 정확 매칭 (완전히 같은 경우)
                                if text in exclude_patterns or text_lower in [p.lower() for p in exclude_patterns]:
                                    should_exclude = True
                                
                                # 포함 매칭 (하지만 너무 짧은 텍스트만)
                                elif len(text) <= 10 and any(pattern.lower() in text_lower for pattern in exclude_patterns):
                                    should_exclude = True
                                
                                if should_exclude:
                                    continue
                                
                                # 길이 기반 1차 필터링 (상품명 합리적 범위)
                                if not (5 <= len(text) <= 150):
                                    continue
                                
                                # 점수 계산 (개선된 로직)
                                score = 0
                                
                                # 길이 점수 (적당한 길이 선호)
                                if 10 <= len(text) <= 80:
                                    score += 20
                                elif 5 <= len(text) <= 150:
                                    score += 10
                                
                                # 클래스명 기반 점수 (상품명 전용 클래스 최우선)
                                class_name = await element.get_attribute('class') or ''
                                class_lower = class_name.lower()
                                
                                # 상품명 전용 클래스 초고점
                                if any(pattern in class_lower for pattern in ['product-name', 'goods-name', 'item-name']):
                                    score += 100
                                elif any(pattern in class_lower for pattern in ['product-title', 'goods-title', 'detail-title']):
                                    score += 80
                                elif any(keyword in class_lower for keyword in ['product', 'goods', 'item']):
                                    score += 40
                                
                                # 태그별 점수
                                try:
                                    tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
                                except:
                                    tag_name = ''
                                if tag_name == 'h1':
                                    score += 30
                                elif tag_name == 'h2':
                                    score += 20
                                elif tag_name == 'h3':
                                    score += 10
                                
                                # 브랜드명 대괄호 점수 (키드짐 특화 및 범용성 강화)
                                if '[키드짐]' in text or '[kidgym]' in text.lower():
                                    score += 100  # 키드짐 브랜드명 최고점
                                elif '[브랜드]' in text.lower() or '[제조사]' in text.lower():
                                    score += 90   # 일반 브랜드명 고점
                                elif '[' in text and ']' in text:
                                    # 대괄호 내용이 일반적인 브랜드명인지 검증
                                    bracket_content = text[text.find('[')+1:text.find(']')]
                                    if len(bracket_content) >= 2 and bracket_content.replace(' ', '').isalnum():
                                        score += 70  # 유효한 브랜드명으로 보이는 대괄호
                                    else:
                                        score += 20  # 브랜드명이 아닌 대괄호
                                
                                # UI 요소 및 카테고리 감점 강화
                                if 'title' in class_lower:
                                    if len(text) <= 10:  # "좋아요" 같은 짧은 title 요소
                                        score -= 80
                                    elif any(ui_word in text.lower() for ui_word in ['좋아요', '싫어요', '찜하기', '버튼']):
                                        score -= 100  # UI 요소 확실
                                
                                # 카테고리명 강력 감점
                                category_indicators = ['볼&골대', '체육용품', '운동기구', '카테고리']
                                if any(cat in text for cat in category_indicators):
                                    score -= 200  # 카테고리명 강력 배제
                                
                                # 버튼, 링크 요소 감점
                                parent_tag = ''
                                try:
                                    parent = await element.evaluate('el => el.parentElement')
                                    if parent:
                                        parent_tag = await parent.evaluate('el => el.tagName.toLowerCase()')
                                except:
                                    pass
                                
                                if parent_tag in ['button', 'a']:
                                    score -= 30
                                if score > best_score:
                                    best_score = score
                                    best_name = text
                    
                    # 유효한 상품명을 찾았으면 더 이상 다른 선택자 시도하지 않음
                    if best_name and best_score >= 20:  # 최소 점수 기준
                        product_name = best_name
                        print(f"[SUCCESS] 상품명 추출 성공 (선택자: {selector}, 점수: {best_score}): {product_name[:50]}...")
                        break
                        
                except Exception as e:
                    print(f"[DEBUG] 선택자 {selector} 시도 실패: {e}")
                    continue
            
            data['상품명'] = product_name
            
            # 가격
            if self.selectors.get('가격'):
                try:
                    element = await page.query_selector(self.selectors['가격'])
                    if element:
                        price_text = (await element.text_content()).strip()
                        price_match = re.search(r'(\d{1,3}(?:,\d{3})*)', price_text)
                        if price_match:
                            data['가격'] = price_match.group(1) + '원'
                        else:
                            numbers = re.findall(r'\d+', price_text.replace(',', ''))
                            if numbers:
                                longest_num = max(numbers, key=len)
                                if len(longest_num) >= 3:
                                    formatted_price = '{:,}'.format(int(longest_num))
                                    data['가격'] = formatted_price + '원'
                                else:
                                    data['가격'] = price_text
                            else:
                                data['가격'] = price_text
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
                        await page.wait_for_timeout(500)
                    
                    # 다양한 선택자 시도
                    selectors_to_try = [
                        self.selectors['상세페이지'],  # SmartDetector가 찾은 선택자
                        '#prdDetail img',
                        '.goods_description img',
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
                                    
                                    # 유효성 검사 및 중복 체크
                                    if (normalized_url and 
                                        self._is_valid_detail_image(normalized_url) and 
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
                            continue
                    
                    data['상세페이지'] = detail_images[:10]
                    print(f"[DEBUG] 최종 상세페이지 이미지: {len(data['상세페이지'])}개")
                    
                    # 상세설명 텍스트 추출 (범용 로직)
                    try:
                        print("[DEBUG] 상세설명 텍스트 추출 시작")
                        detail_text_content = []
                        
                        # 범용 텍스트 선택자들 (p, div, article 태그 우선)
                        text_selectors_to_try = [
                            self.selectors.get('상세설명텍스트', ''),
                            '.goods_description p, .goods_description div',
                            '.product-description p, .product-description div', 
                            '.detail p, .detail div',
                            '.content p, .content div',
                            '.description p, .description div',
                            '.product-detail p, .product-detail div',
                            'article p, article div',
                            '[class*="description"] p, [class*="description"] div',
                            '[class*="detail"] p, [class*="detail"] div'
                        ]
                        
                        for selector in text_selectors_to_try:
                            if not selector.strip():
                                continue
                                
                            try:
                                print(f"[DEBUG] 텍스트 선택자 시도: {selector}")
                                text_elements = await page.query_selector_all(selector)
                                print(f"[DEBUG] 찾은 텍스트 요소 수: {len(text_elements)}")
                                
                                for element in text_elements:
                                    # innerHTML 또는 textContent 추출
                                    html_content = await element.inner_html()
                                    text_content = await element.inner_text()
                                    
                                    # HTML 서식이 있는 경우 HTML 우선, 없으면 텍스트
                                    if html_content and html_content.strip():
                                        # 기본적인 HTML 태그 정제 (스크립트, 스타일 제거)
                                        cleaned_html = re.sub(r'<script.*?</script>', '', html_content, flags=re.DOTALL)
                                        cleaned_html = re.sub(r'<style.*?</style>', '', cleaned_html, flags=re.DOTALL)
                                        
                                        if len(cleaned_html.strip()) > 10:  # 의미있는 내용만
                                            detail_text_content.append(cleaned_html.strip())
                                            print(f"[DEBUG] 유효한 HTML 텍스트 추가: {len(cleaned_html)}자")
                                    elif text_content and text_content.strip() and len(text_content.strip()) > 10:
                                        detail_text_content.append(text_content.strip())
                                        print(f"[DEBUG] 유효한 플레인 텍스트 추가: {len(text_content)}자")
                                
                                # 유효한 텍스트를 찾았으면 다음 선택자는 시도하지 않음
                                if detail_text_content:
                                    print(f"[DEBUG] {selector} 선택자로 {len(detail_text_content)}개 텍스트 블록 찾음")
                                    break
                                    
                            except Exception as e:
                                print(f"[DEBUG] {selector} 텍스트 선택자 오류: {e}")
                                continue
                        
                        # 텍스트 통합 및 정제
                        if detail_text_content:
                            combined_text = '\n\n'.join(detail_text_content)
                            # 최대 길이 제한 (5000자)
                            if len(combined_text) > 5000:
                                combined_text = combined_text[:5000] + '...'
                            data['상세설명텍스트'] = combined_text
                            print(f"[DEBUG] 최종 상세설명 텍스트: {len(combined_text)}자")
                        else:
                            data['상세설명텍스트'] = ""
                            print("[DEBUG] 상세설명 텍스트를 찾을 수 없음")
                            
                    except Exception as e:
                        print(f"[ERROR] 상세설명 텍스트 추출 실패: {e}")
                        data['상세설명텍스트'] = ""
                    
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
        
    def _is_valid_detail_image(self, url):
        """유효한 상세 이미지인지 판단 (URL 패턴 + 실제 이미지 크기 검증)"""
        if not url:
            return False
        
        url_lower = url.lower()
        
        # 1단계: URL 패턴 기반 필터링
        # 확실히 제외할 UI 요소들만 필터링
        exclude_patterns = [
            'logo', 'icon', 'btn', 'button', 'menu', 'nav', 
            'arrow', 'quick', 'zzim', 'wishlist',
            'banner', 'common', 'header', 'footer',
            'popup', 'close', 'search', 'cart',
            'sns', 'facebook', 'twitter', 'kakao',
            'top_btn', 'scroll', 'floating',
            # 공통 정보 이미지 필터링 추가
            '_wg/', 'detail_img_info', 'delivery_info',
            'exchange_info', 'return_info', 'notice_info',
            # 키드짐 특화 워터마크 및 UI 요소 필터링
            'watermark', 'watermark3', 'sold_out', 'stamp',
            '0516100/', 'overlay', 'badge', 'mark',
            'thumbnail_', '_thumb', 'list_', '_list'
        ]
        
        # 특정 패턴이 포함된 경우 무조건 제외
        for pattern in exclude_patterns:
            if pattern in url_lower:
                # print(f"[DEBUG] '{pattern}' 패턴 발견, 이미지 제외: {url}")  # 디버깅 메시지 주석처리
                return False
        
        # 포함되어야 하는 패턴들 (상세 이미지 가능성 높음)
        include_patterns = [
            'detail', 'content', 'description', 'product',
            'item', 'goods', 'view', 'main', 'sub'
        ]
        
        # 상세 패턴이 포함되어 있으면 대부분 허용
        has_include = any(pattern in url_lower for pattern in include_patterns)
        
        # 이미지 확장자가 있으면 대부분 허용
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        has_image_ext = any(ext in url_lower for ext in image_extensions)
        
        # URL 패턴 필터링을 통과하지 못하면 바로 거부
        if not (has_include or has_image_ext):
            return False
        
        # 2단계: 실제 이미지 크기 검증
        return self._check_image_dimensions(url)
    
    def _check_image_dimensions(self, url):
        """실제 이미지 크기를 확인하여 660px 이상인지 검증 (캐시 활용)"""
        # 캐시 확인
        with self.cache_lock:
            if url in self.verified_images_cache:
                return self.verified_images_cache[url][0]
        
        result = self._verify_single_image_optimized(url)
        
        # 캐시에 저장
        with self.cache_lock:
            self.verified_images_cache[url] = (result, 0)
        
        return result
    
    def _verify_single_image_optimized(self, url):
        """단일 이미지 최적화된 검증"""
        try:
            # requests.Session을 사용한 HEAD 요청
            head_response = self.session.head(url, timeout=10, allow_redirects=True)
            
            if head_response.status_code == 200:
                content_length = head_response.headers.get('content-length')
                if content_length:
                    file_size = int(content_length)
                    # 50KB 미만이면 제외
                    if file_size < 50000:
                        return False
            
            # 실제 이미지 다운로드하여 크기 확인
            img_response = self.session.get(url, timeout=15)
            img_response.raise_for_status()
            img_data = img_response.content
            
            # 파일 크기 재확인
            if len(img_data) < 50000:
                return False
            
            # PIL로 이미지 크기 확인
            img = Image.open(io.BytesIO(img_data))
            width, height = img.size
            
            # 660px 이상 조건 확인
            if width >= 660:
                # 추가 품질 검증: 가로세로 비율 확인
                aspect_ratio = width / height
                
                # 너무 긴 이미지 (10:1 비율 이상) 제외
                if aspect_ratio > 10 or aspect_ratio < 0.1:
                    return False
                
                # 너무 작은 정사각형 이미지 제외 (100x100 미만)
                if width == height and width < 100:
                    return False
                
                # 중복 이미지 검사 (해시값 기반)
                img_hash = hashlib.md5(img_data).hexdigest()
                if img_hash in self.image_hashes:
                    return False
                
                # 모든 검증 통과 시 해시 저장 및 승인
                self.image_hashes.add(img_hash)
                return True
            else:
                return False
                
        except Exception as e:
            return False
    
    def verify_images_parallel(self, urls):
        """병렬로 여러 이미지 검증"""
        if not urls:
            return {}
            
        print(f"[PERF] FinalAnalyzer 병렬 이미지 검증 시작: {len(urls)}개")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {executor.submit(self._check_image_dimensions, url): url for url in urls}
            results = {}
            
            for future in future_to_url:
                url = future_to_url[future]
                try:
                    results[url] = future.result()
                except Exception as e:
                    print(f"[ERROR] 병렬 이미지 검증 실패 {url}: {e}")
                    results[url] = False
        
        valid_count = sum(1 for is_valid in results.values() if is_valid)
        print(f"[PERF] FinalAnalyzer 병렬 검증 완료: {valid_count}개 유효")
        return results
    
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
    
    def close(self):
        """세션 정리"""
        self.session.close()
        print("[PERF] FinalAnalyzer 세션 정리 완료")


if __name__ == "__main__":
    analyzer = FinalAnalyzer()
    asyncio.run(analyzer.run())
    print("[COMPLETE] 추출 완료! 자동 종료됩니다.")
