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
        """상품명 선택자 탐지"""
        candidates = [
            'h1', 'h2', '.name', '.title', '.product-name', '.product-title',
            '.goods-name', '.item-name', '[itemprop="name"]', '.product_name'
        ]
        
        for selector in candidates:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text and 5 <= len(text.strip()) <= 200:
                        return selector
            except:
                continue
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
            '.goods_description img', '.product-description img',
            '.detail img', '.content img', '.description img',
            '[class*="detail"] img', '.editor img'
        ]
        
        for selector in candidates:
            try:
                elements = await page.query_selector_all(selector)
                if elements and len(elements) >= 2:
                    return selector
            except:
                continue
        return None
    
    async def _find_options(self, page):
        """선택옵션 선택자 탐지"""
        candidates = [
            'select:nth-of-type(2)', 'select[name*="option"]',
            '.option select', '.options select',
            'select:not([name*="quantity"])'
        ]
        
        for selector in candidates:
            try:
                element = await page.query_selector(selector)
                if element:
                    options = await page.query_selector_all(f'{selector} option')
                    if options and len(options) > 1:
                        return selector
            except:
                continue
        return None
    
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
