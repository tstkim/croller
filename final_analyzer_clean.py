"""
상품 페이지 직접 분석 및 정확한 선택자 탐지 (이모지 제거 버전)
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
            if href and '/goods/view' in href:
                id_attr = await handle.get_attribute('id')
                class_attr = await handle.get_attribute('class')
                if id_attr:
                    sel = f"a#{id_attr}"
                elif class_attr:
                    sel = f"a.{'.'.join(class_attr.split())}"
                else:
                    sel = 'a[href*="/goods/view"]'
                selector_count[sel] = selector_count.get(sel, 0) + 1
        if selector_count:
            return max(selector_count, key=selector_count.get)
        return 'a[href*="/goods/view"]'

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
            selector = product_link_selector or 'a[href*="/goods/view"]'
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
            print(f"[SMART] 개별 상품 페쒰지로 이동: {sample_product_url}")
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
            
            # 상품명
            if self.selectors.get('상품명'):
                try:
                    element = await page.query_selector(self.selectors['상품명'])
                    if element:
                        data['상품명'] = (await element.text_content()).strip()
                    else:
                        data['상품명'] = None
                except:
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
                        data['썸네일'] = data_original or data_src or src
                    else:
                        data['썸네일'] = None
                except:
                    data['썸네일'] = None
            else:
                data['썸네일'] = None
            
            # 상세페이지 이미지
            if self.selectors.get('상세페이지'):
                try:
                    images = await page.query_selector_all(self.selectors['상세페이지'])
                    detail_images = []
                    for img in images:
                        src = await img.get_attribute('src')
                        data_src = await img.get_attribute('data-src')
                        data_original = await img.get_attribute('data-original')
                        best_url = data_original or data_src or src
                        
                        if best_url and self._is_valid_detail_image(best_url) and best_url not in detail_images:
                            detail_images.append(best_url)
                    
                    data['상세페이지'] = detail_images[:10]
                except:
                    data['상세페이지'] = []
            else:
                data['상세페이지'] = []
            
            return data
            
        except Exception as e:
            print(f"[ERROR] 상품 추출 실패: {e}")
            return None
    
    def _is_valid_option(self, text):
        """유효한 선택옵션인지 판단"""
        if not text:
            return False
        
        text_lower = text.lower().strip()
        
        # 완전히 제외할 패턴들 (정확히 일치하는 경우만)
        exact_exclude = [
            '선택', '-- 선택 --', '옵션선택', '옵션을 선택해주세요',
            '- 무게 선택 -', '- 색상 선택 -', '- 사이즈 선택 -'
        ]
        
        # 포함된 경우 제외할 패턴들
        partial_exclude = [
            '택배(주문 시 결제)', '배송비', '주문 시 결제'
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
    
    def _is_valid_detail_image(self, url):
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
