"""
범용 SmartDetector - 이모지 완전 제거 버전
"""
import json
import asyncio
import re
from datetime import datetime


class SmartDetector:
    """범용 쇼핑몰 선택자 자동 탐지 엔진"""
    
    def __init__(self):
        self.detected_stage = None
        self.detection_log = []
        
    async def detect_selectors(self, page, url):
        """메인 탐지 함수 - 범용 휴리스틱 탐지 + 기본 선택자 보완"""
        print("[SMART] 범용 선택자 탐지 시작...")
        
        # 기본 선택자 설정 (보장된 선택자)
        base_selectors = {
            '상품리스트': '.goods-list li, .item-list li, [class*="item"], li[class*="goods"], .product-list li, .catalog li',
            '상품명': '.name, h1, h2, .title, .product-name, .goods-name',
            '가격': '.org_price, .price, .sale_price, .cost, .amount, .product-price',
            '선택옵션': 'select:nth-of-type(2), select[name*="option"], .option select',
            '썸네일': '.viewImgWrap img, .product-image img, .main-image img, .thumb img',
            '상세페이지': '.goods_description img, .product-description img, .detail img, .content img'
        }
        
        # 탐지 시도
        result = await self._heuristic_dom_search(page)
        
        if result and len(result) > 0:
            self.detected_stage = "4단계: 휴리스틱 DOM 탐색"
            print(f"[SUCCESS] 휴리스틱 탐지 성공: {len(result)}개 선택자")
            
            # 기본 선택자와 대체 또는 추가
            final_selectors = base_selectors.copy()
            for key, value in result.items():
                if key in final_selectors:
                    print(f"[UPDATE] {key}: {value}")
                    final_selectors[key] = value
                else:
                    print(f"[ADD] {key}: {value}")
                    final_selectors[key] = value
            
            return final_selectors
        else:
            print("[FALLBACK] 휴리스틱 탐지 실패, 기본 선택자 반환")
            self.detected_stage = "기본 선택자 사용"
            return base_selectors
    
    async def _heuristic_dom_search(self, page):
        """범용 휴리스틱 DOM 탐색"""
        selectors = {}
        
        # 상품명 탐지
        name_selector = await self._find_product_name(page)
        if name_selector:
            selectors['상품명'] = name_selector
            print(f"[DETECT] 상품명: {name_selector}")
        
        # 가격 탐지
        price_selector = await self._find_price(page)
        if price_selector:
            selectors['가격'] = price_selector
            print(f"[DETECT] 가격: {price_selector}")
        
        # 썸네일 탐지
        thumbnail_selector = await self._find_thumbnail(page)
        if thumbnail_selector:
            selectors['썸네일'] = thumbnail_selector
            print(f"[DETECT] 썸네일: {thumbnail_selector}")
        
        # 상세페이지 이미지 탐지
        detail_selector = await self._find_detail_images(page)
        if detail_selector:
            selectors['상세페이지'] = detail_selector
            print(f"[DETECT] 상세페이지: {detail_selector}")
        
        # 선택옵션 탐지
        option_selector = await self._find_options(page)
        if option_selector:
            selectors['선택옵션'] = option_selector
            print(f"[DETECT] 선택옵션: {option_selector}")
        
        return selectors if len(selectors) >= 1 else None
    
    async def _find_product_name(self, page):
        """상품명 선택자 탐지 (전체 요소 스캔 버전)"""
        # 기본 선택자 후보들
        candidates = [
            'h1', 'h2', 'h3', 'h4', 'h5', '.name', '.title', '.product-name', 
            '.product-title', '.goods-name', '.item-name', '[itemprop="name"]', 
            '.product_name', '.goods_name', '.item_title', '.product_title', 
            '.goods_title', '.detail-name', '.detail-title', '.prd-name', 
            '.prd-title', '.pro_name', '.prod-name', '.main-title',
            '.product-main-title', '.goods-main-title'
        ]
        
        # 제외할 텍스트 패턴들
        exclude_patterns = [
            '카테고리', '전체보기', '메뉴', '네비게이션', '로그인', '회원가입',
            '장바구니', '주문', '배송', '고객센터', '공지사항', '이벤트',
            '커뮤니티', '게시판', '문의', '리뷰', '소개', '브랜드',
            '옵션 선택', '선택하세요', '추가', '전체상품목록',
            '상품 옵션', '상품 후기', '상품정보제공고시', '교환 및 반품안내',
            'CUSTOMER CENTER', 'BANK INFO', 'ORDER TRACKING', 'RETURN & EXCHANGE',
            '후기', '옵션', '정보제공', '반품안내', 'SHOP', 'MENU', 'INFO'
        ]
        
        all_candidates = []
        print("[DEBUG] 상품명 전체 후보 스캔:")
        
        # 모든 후보 테스트
        for selector in candidates:
            try:
                elements = await page.query_selector_all(selector)
                for i, element in enumerate(elements):
                    if element:
                        text = await element.text_content()
                        if text:
                            text = text.strip()
                            if 3 <= len(text) <= 100:  # 적절한 길이
                                print(f"[DEBUG] {selector}[{i}]: '{text}'")
                                
                                # 제외 패턴 체크
                                should_exclude = any(pattern in text for pattern in exclude_patterns)
                                if should_exclude:
                                    print(f"[DEBUG] -> 제외됨: '{text[:30]}...'")
                                    continue
                                    
                                # 상품명 스코어링
                                score = 0
                                
                                # 길이 점수
                                if 5 <= len(text) <= 50:
                                    score += 15
                                elif 3 <= len(text) <= 100:
                                    score += 10
                                    
                                # 상품명다운 보너스
                                if any(char.isalnum() for char in text):
                                    score += 5
                                if not any(word in text.lower() for word in ['select', 'click', 'button']):
                                    score += 5
                                    
                                # 브랜드명 대괄호 초고점 보너스!
                                if '[' in text and ']' in text:
                                    score += 50  # 다른 모든 후보를 압도
                                    print(f"[DEBUG] -> 브랜드명 대괄호 발견! +50점")
                                    
                                # 상품 관련 키워드 보너스
                                product_keywords = ['가방', '신발', '의류', '장난감', '어린이', '아이', '배낭', '유모차']
                                if any(word in text for word in product_keywords):
                                    score += 10
                                    
                                all_candidates.append({
                                    'selector': f"{selector}[{i}]",
                                    'text': text,
                                    'score': score,
                                    'element_selector': selector
                                })
                                print(f"[DEBUG] -> 점수: {score}")
                                
            except Exception as e:
                print(f"[DEBUG] {selector}: 오류 - {e}")
                continue
        
        # 점수로 정렬
        all_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        print("\n[DEBUG] 상위 5개 후보:")
        for i, candidate in enumerate(all_candidates[:5]):
            print(f"[DEBUG] {i+1}. {candidate['selector']}: '{candidate['text']}' (점수: {candidate['score']})")
        
        # 최고 점수 후보 선택
        if all_candidates and all_candidates[0]['score'] > 5:
            best = all_candidates[0]
            print(f"\n[DEBUG] 최종 선택: {best['element_selector']} -> '{best['text']}'")
            return best['element_selector']
        else:
            print("[DEBUG] 적절한 상품명 후보를 찾을 수 없음")
            return None
    
    async def _find_price(self, page):
        """가격 선택자 탐지"""
        candidates = [
            '.price', '.org_price', '.sale_price', '.cost', '.amount',
            '.product-price', '[itemprop="price"]', '[class*="price"]'
        ]
        
        price_pattern = r'\d{1,3}(?:,\d{3})*(?:원|won|₩|\$)?'
        
        for selector in candidates:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text and re.search(price_pattern, text):
                        return selector
            except:
                continue
        return None
    
    async def _find_thumbnail(self, page):
        """썸네일 이미지 선택자 탐지"""
        candidates = [
            '.viewImgWrap img', '.product-image img', '.main-image img',
            '.thumb img', '.thumbnail img', '[itemprop="image"]',
            '.goods-image img', '.item-image img'
        ]
        
        for selector in candidates:
            try:
                element = await page.query_selector(selector)
                if element:
                    src = await element.get_attribute('src')
                    data_src = await element.get_attribute('data-src')
                    if src or data_src:
                        return selector
            except:
                continue
        return None
    
    async def _find_detail_images(self, page):
        """상세페이지 이미지 선택자 탐지"""
        candidates = [
            '#prdDetailContentLazy img', '#prdDetailContent img',
            '.goods_description img', '.product-description img',
            '#prdDetail img', '#productDetail img', 
            '.prd_detail img', '.product_detail img',
            '.detail_content img', '.description_content img',
            '.editor img', '[id*="detail"] img'
        ]
        
        for selector in candidates:
            try:
                elements = await page.query_selector_all(selector)
                if elements and len(elements) >= 1:  # 1개 이상만 있으면 허용
                    # 실제 이미지 src가 있는지 확인
                    valid_images = 0
                    for element in elements[:5]:  # 최대 5개만 확인
                        src = await element.get_attribute('src')
                        data_src = await element.get_attribute('data-src')
                        data_original = await element.get_attribute('data-original')
                        if src or data_src or data_original:
                            valid_images += 1
                    if valid_images >= 1:
                        return selector
            except:
                continue
        return None
    
    async def _find_options(self, page):
        """선택옵션 선택자 탐지 (정교화 버전)"""
        # 모든 select 태그를 대상으로 name/id/class 속성 분석
        select_elements = await page.query_selector_all('select')
        option_keywords = ['option', 'product', 'item', 'select', 'goods', 'size', 'color', 'type', 'style']
        exclude_keywords = ['bank', 'pay', 'delivery', 'shipping', 'address', 'method', 'account', '결제', '은행', '배송', '수령', '카드', '계좌']
        best_selector = None
        best_valid_count = 0
        for sel in select_elements:
            try:
                name = (await sel.get_attribute('name') or '').lower()
                id_ = (await sel.get_attribute('id') or '').lower()
                class_ = (await sel.get_attribute('class') or '').lower()
                attr_str = name + ' ' + id_ + ' ' + class_
                # 상품 옵션 관련 키워드가 포함되어 있고, 결제/배송/은행 관련 키워드는 없어야 함
                if any(k in attr_str for k in option_keywords) and not any(k in attr_str for k in exclude_keywords):
                    # selector 생성
                    selector = ''
                    if id_:
                        selector = f'select#{id_}'
                    elif class_:
                        selector = f'select.{".".join(class_.split())}'
                    elif name:
                        selector = f'select[name="{name}"]'
                    else:
                        continue
                    # option 텍스트 샘플링
                    options = await sel.query_selector_all('option')
                    valid_count = 0
                    total_count = 0
                    for option in options:
                        text = (await option.text_content() or '').strip()
                        total_count += 1
                        # 은행/결제/배송 관련 값이 포함된 option은 제외
                        if not any(k in text for k in exclude_keywords) and len(text) > 1:
                            valid_count += 1
                    # 유효 옵션 비율이 50% 이상이고, 2개 이상이면 후보로 삼음
                    if total_count > 1 and valid_count / total_count >= 0.5 and valid_count > best_valid_count:
                        best_valid_count = valid_count
                        best_selector = selector
            except Exception as e:
                continue
        return best_selector if best_selector else None
    
    def get_detection_info(self):
        """탐지 정보 반환"""
        return {
            'detected_stage': self.detected_stage,
            'detection_log': self.detection_log,
            'timestamp': datetime.now().isoformat()
        }


if __name__ == "__main__":
    print("[INFO] 범용 SmartDetector 로드됨")
    print("[INFO] 4단계 휴리스틱 DOM 탐색 지원")
