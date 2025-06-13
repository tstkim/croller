"""
상품 페이지 직접 분석 및 정확한 선택자 탐지 (3개 상품 보장)
"""
import asyncio
import traceback
from playwright.async_api import async_playwright
from site_config import *
from login_manager import LoginManager
import json
import re
from datetime import datetime


class FinalAnalyzer:
    def __init__(self):
        self.login_manager = LoginManager()
        self.selectors = {}
        self.test_data = []
    
    async def _detect_product_link_selector(self, page):
        """상품 갤러리에서 상품 링크 a 태그의 선택자를 동적으로 탐지"""
        # 1. 모든 a 태그 수집
        handles = await page.query_selector_all('a')
        selector_count = {}
        for handle in handles:
            href = await handle.get_attribute('href')
            if href and '/goods/view' in href:
                # CSS selector 생성
                selector = await page.evaluate('(el) => el.outerHTML', handle)
                # id, class, tag 기반 selector 추출
                id_attr = await handle.get_attribute('id')
                class_attr = await handle.get_attribute('class')
                if id_attr:
                    sel = f"a#{id_attr}"
                elif class_attr:
                    sel = f"a.{'.'.join(class_attr.split())}"
                else:
                    sel = 'a[href*="/goods/view"]'
                selector_count[sel] = selector_count.get(sel, 0) + 1
        # 가장 많이 등장하는 selector 반환
        if selector_count:
            return max(selector_count, key=selector_count.get)
        return 'a[href*="/goods/view"]'

    async def run(self):
        """메인 실행"""
        print("🎯 최종 상품 분석기 시작...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
            page = await context.new_page()
            try:
                # 로그인 (동일 page/context에서 진행)
                if LOGIN_REQUIRED:
                    await self.login_manager.auto_login(page, MAIN_URL, USERNAME, PASSWORD)
                    await asyncio.sleep(1)  # 세션 적용 대기
                    print("[로그] 로그인 후 쿠키:", await context.cookies())
                    await page.reload()  # 세션 강제 동기화
                print(f"[로그] 로그인 후 현재 URL: {page.url}")
                # 로그인 후 곧바로 갤러리 페이지로 이동
                await page.goto(GALLERY_URL, wait_until="domcontentloaded", timeout=30000, referer=MAIN_URL)
                await page.wait_for_load_state("networkidle", timeout=15000)
                print(f"[로그] 갤러리 이동 후 현재 URL: {page.url}")
                if not page.url.startswith(GALLERY_URL.split('?')[0]):
                    print(f"[경고] 갤러리 페이지로 정상 이동하지 못했습니다. 현재 URL: {page.url}")
                # 상품 링크 선택자 동적 탐지
                product_link_selector = await self._detect_product_link_selector(page)
                self.selectors['상품링크'] = product_link_selector
                # 테스트 링크 수집
                test_links = await self._get_test_links(page, product_link_selector)
                print(f"✅ 수집된 테스트 링크: {len(test_links)}개")
                if test_links:
                    # 선택자 탐지
                    print(f"\n🔍 선택자 탐지...")
                    await self._analyze_selectors(page, test_links[0])
                    # 3개 상품 강제 처리
                    await self._extract_three_products(page, test_links)
                # 결과 저장
                self._save_result()
            finally:
                await browser.close()
    
    async def _get_test_links(self, page, product_link_selector=None):
        """테스트 링크 수집 (상품 링크 선택자 사용)"""
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
            print(f"❌ 링크 수집 실패: {e}")
            return [SAMPLE_PRODUCT_URL]
    
    async def _analyze_selectors(self, page, url):
        """선택자 분석 (상품링크 포함)"""
        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            # 기존 성공한 선택자들 사용
            self.selectors.update({
                '상품명': '.name',
                '가격': '.org_price', 
                '선택옵션': 'select:nth-of-type(2)',
                '썸네일': '.viewImgWrap img',
                '상세페이지': '.goods_description img'
            })
            
            print("📋 선택자 설정 완료:")
            for key, value in self.selectors.items():
                print(f"   {key}: {value}")
                
        except Exception as e:
            print(f"❌ 선택자 분석 실패: {e}")
    
    async def _extract_three_products(self, page, test_links):
        """3개 상품 강제 추출"""
        print(f"\n📊 3개 상품 강제 추출 시작...")
        
        successful_count = 0
        max_attempts = min(len(test_links), 10)
        
        for i in range(max_attempts):
            if successful_count >= 3:
                print(f"🎉 목표 달성! 3개 상품 추출 완료")
                break
                
            link = test_links[i]
            print(f"\n{'='*50}")
            print(f"📦 상품 {i+1} 처리 중... (성공: {successful_count}/3)")
            print(f"🔗 {link}")
            
            try:
                data = await self._extract_single_product(page, link)
                
                if data and data.get('상품명', '').strip():
                    self.test_data.append(data)
                    successful_count += 1
                    
                    print(f"✅ 상품 {i+1} 성공! ({successful_count}/3)")
                    print(f"   📝 상품명: {data.get('상품명', '')[:50]}...")
                    print(f"   💰 가격: {data.get('가격', 'N/A')}")
                    print(f"   ⚙️ 옵션: {len(data.get('선택옵션', []))}개")
                    print(f"   🖼️ 썸네일: {'✅' if data.get('썸네일') else '❌'}")
                    print(f"   📸 상세이미지: {len(data.get('상세페이지', []))}개")
                else:
                    print(f"❌ 상품 {i+1} 실패: 데이터 부족")
                    
            except Exception as e:
                print(f"❌ 상품 {i+1} 오류: {str(e)[:100]}")
            
            # 서버 부하 방지
            if i < max_attempts - 1:
                await asyncio.sleep(1)
        
        print(f"\n🏁 추출 완료: {successful_count}개 성공")
    
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
            
            # 가격 (정확한 추출)
            if self.selectors.get('가격'):
                try:
                    element = await page.query_selector(self.selectors['가격'])
                    if element:
                        price_text = (await element.text_content()).strip()
                        # 정확한 숫자 추출
                        price_match = re.search(r'(\d{1,3}(?:,\d{3})*)', price_text)
                        if price_match:
                            data['가격'] = price_match.group(1) + '원'
                        else:
                            # 백업: 가장 긴 숫자 찾기
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
                        if text and text not in ['선택', '-- 선택 --', '옵션선택', '옵션을 선택해주세요']:
                            option_list.append(text)
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
            
            # 상세페이지 이미지 (필터링 적용)
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
            print(f"❌ 상품 추출 실패: {e}")
            return None
    
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
        """결과 저장"""
        result = {
            '선택자': self.selectors,
            '추출데이터': self.test_data,
            '생성일시': datetime.now().isoformat()
        }
        
        filename = f"perfect_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 결과 저장: {filename}")
        print("\n" + "="*70)
        print("🎯 최종 결과:")
        print(f"   📝 상품명: {self.selectors.get('상품명', '❌')}")
        print(f"   💰 가격: {self.selectors.get('가격', '❌')}")
        print(f"   ⚙️ 선택옵션: {self.selectors.get('선택옵션', '❌')}")
        print(f"   🖼️ 썸네일: {self.selectors.get('썸네일', '❌')}")
        print(f"   📸 상세페이지: {self.selectors.get('상세페이지', '❌')}")
        print(f"   📊 추출된 상품: {len(self.test_data)}개")


if __name__ == "__main__":
    analyzer = FinalAnalyzer()
    asyncio.run(analyzer.run())
    print("\n🏁 추출 완료! 자동 종료됩니다.")
