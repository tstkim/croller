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


class FinalAnalyzer:
    def __init__(self):
        self.login_manager = LoginManager()
        self.smart_detector = SmartDetector()
        self.selectors = {}
        self.test_data = []
    
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
            
            # 상품명 (브랜드명 우선 선택)
            if self.selectors.get('상품명'):
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
                                
                                # 제외 패턴 체크
                                exclude_patterns = [
                                    '카테고리', '전체보기', '메뉴', '네비게이션', '로그인', '회원가입',
                                    '장바구니', '주문', '배송', '고객센터', '공지사항', '이벤트',
                                    '커뮤니티', '게시판', '문의', '리뷰', '소개', '브랜드',
                                    '옵션', '후기', '상세정보', '문의사항', '상품 옵션', '상품 후기'
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
                    
                    data['상품명'] = best_name
                    
                except Exception as e:
                    data['상품명'] = None
            else:
                data['상품명'] = None
            
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
        """유효한 상세 이미지인지 판단"""
        if not url:
            return False
        
        url_lower = url.lower()
        
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
            'exchange_info', 'return_info', 'notice_info'
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
        
        return has_include or has_image_ext
    
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


if __name__ == "__main__":
    analyzer = FinalAnalyzer()
    asyncio.run(analyzer.run())
    print("[COMPLETE] 추출 완료! 자동 종료됩니다.")
