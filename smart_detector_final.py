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
            '상품명': '.product-name, .goods-name, .item-name, [class*="product"] h1, [class*="goods"] h1, [class*="item"] h1, .name, .title, h2, h1',
            '가격': '.org_price, .price, .sale_price, .cost, .amount, .product-price',
            '선택옵션': 'select:nth-of-type(2), select[name*="option"], .option select',
            '썸네일': '.viewImgWrap img, .product-image img, .main-image img, .thumb img',
            '상세페이지': '.goods_description img, .product-description img, .detail img, .content img',
            '상세설명텍스트': '.goods_description p, .product-description p, .detail p, .content p, .description div, .description-content, .product-detail-text'
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
        # 기본 선택자 후보들 (클래스명 기반 선택자 우선 배치)
        candidates = [
            # 1순위: 상품명 전용 클래스들 (가장 높은 우선순위)
            '.product-name', '.product-title', '.goods-name', '.item-name', 
            '.product_name', '.goods_name', '.item_title', '.product_title', 
            '.goods_title', '.detail-name', '.detail-title', '.prd-name', 
            '.prd-title', '.pro_name', '.prod-name', '.main-title',
            '.product-main-title', '.goods-main-title', '[itemprop="name"]',
            
            # 2순위: 일반적인 이름/제목 클래스
            '.name', '.title',
            
            # 3순위: 제네릭 헤더 태그들 (fallback용)
            'h1', 'h2', 'h3', 'h4', 'h5'
        ]
        
        # 제외할 텍스트 패턴들 (카테고리명, 네비게이션, UI 요소 등)
        exclude_patterns = [
            # 기본 UI 요소 및 네비게이션
            '카테고리', '전체보기', '메뉴', '네비게이션', '로그인', '회원가입',
            '장바구니', '주문', '배송', '고객센터', '공지사항', '이벤트',
            '커뮤니티', '게시판', '문의', '리뷰', '소개', '브랜드',
            '옵션 선택', '선택하세요', '추가', '전체상품목록',
            '상품 옵션', '상품 후기', '상품정보제공고시', '교환 및 반품안내',
            'CUSTOMER CENTER', 'BANK INFO', 'ORDER TRACKING', 'RETURN & EXCHANGE',
            '후기', '옵션', '정보제공', '반품안내', 'SHOP', 'MENU', 'INFO',
            
            # 키드짐 특화 UI 요소 패턴 (강화)
            '좋아요', '싫어요', '추천', '찜하기', '관심상품', '북마크', '즐겨찾기',
            '리뷰', '후기', '평가', '별점', '댓글', '문의', '신고', '신고하기',
            '버튼', '클릭', '더보기', '선택', '닫기', '열기', '확인', '취소',
            
            # 키드짐 특화 카테고리/메뉴 패턴 (대폭 강화)
            '볼&골대', '공&골대', '체육용품', '운동기구', '스포츠용품', 
            '놀이기구', '체육활동', '실내체육', '야외체육', '게임활동',
            '볼놀이', '공놀이', '골대', '체육관', '운동장', '놀이터',
            '네트리더', '타겟게임', '라켓게임', '멀티시스템', '캐치게임',
            '점프&밸런스', '레크리에이션', '놀이교구', '유아체육', '어린이체육',
            '유아놀이', '어린이놀이', '체육교구', '스포츠교구', '운동교구',
            
            # 일반적인 카테고리 패턴
            '신상품', '베스트', '추천', 'NEW', 'BEST', 'HOT', 'SALE',
            '전체상품', '모든상품', '상품리스트', '제품목록',
            '검색', '정렬', '필터', '브랜드', '제조사', 'FAQ', 'Q&A',
            '이용약관', '개인정보', '정책', '가이드', '도움말', 'WORLD SHIPPING'
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
                                
                                # 제외 패턴 체크 (강화된 로직)
                                should_exclude = False
                                text_lower = text.lower()
                                
                                # 1. 정확 매칭 (완전히 같은 경우)
                                if text in exclude_patterns or text_lower in [p.lower() for p in exclude_patterns]:
                                    should_exclude = True
                                    print(f"[DEBUG] -> 정확 매칭 제외됨: '{text[:30]}...'")
                                
                                # 2. 부분 매칭 (주요 키워드 포함)
                                elif any(pattern.lower() in text_lower for pattern in exclude_patterns):
                                    should_exclude = True
                                    print(f"[DEBUG] -> 부분 매칭 제외됨: '{text[:30]}...'")
                                
                                if should_exclude:
                                    continue
                                    
                                # 상품명 스코어링
                                score = 0
                                
                                # 클래스명 기반 선택자 초고점 보너스! (카테고리명 vs 상품명 구분의 핵심)
                                product_class_selectors = [
                                    '.product-name', '.product-title', '.goods-name', '.item-name',
                                    '.product_name', '.goods_name', '.item_title', '.product_title',
                                    '.goods_title', '.detail-name', '.detail-title', '.prd-name',
                                    '.prd-title', '.pro_name', '.prod-name', '.main-title',
                                    '.product-main-title', '.goods-main-title', '[itemprop="name"]'
                                ]
                                if selector in product_class_selectors:
                                    score += 100  # 클래스명 기반 선택자에 최고 우선순위
                                    print(f"[DEBUG] -> 상품명 클래스 선택자 보너스! +100점")
                                
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
                                    
                                    # UI 요소 및 카테고리명 추가 감점 (제외 패턴을 빠져나간 경우)
                                    ui_indicators = ['좋아요', '싫어요', '찜하기', '버튼', '클릭', '선택']
                                    if any(ui_word in text_lower for ui_word in ui_indicators):
                                        score -= 100  # UI 요소 강력 배제
                                        print(f"[DEBUG] -> UI 요소 감점 -100점")
                                    
                                    category_indicators = ['볼&골대', '네트리더', '타겟게임', '체육용품', '운동기구']
                                    if any(cat in text for cat in category_indicators):
                                        score -= 200  # 카테고리명 강력 배제
                                        print(f"[DEBUG] -> 카테고리명 감점 -200점")
                                    
                                # 상품 관련 키워드 보너스
                                product_keywords = ['가방', '신발', '의류', '장난감', '어린이', '아이', '배낭', '유모차']
                                if any(word in text for word in product_keywords):
                                    score += 10
                                
                                # 제네릭 헤더 태그 페널티 (카테고리명을 잘못 선택하는 것을 방지)
                                generic_header_selectors = ['h1', 'h2', 'h3', 'h4', 'h5']
                                if selector in generic_header_selectors:
                                    score -= 30  # 제네릭 헤더는 낮은 우선순위로 (fallback용)
                                    print(f"[DEBUG] -> 제네릭 헤더 태그 페널티 -30점")
                                    
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
        
        # 최고 점수 후보 선택 (강화된 검증)
        if all_candidates:
            # 중복 상품명 감지 및 제거
            unique_texts = set()
            filtered_candidates = []
            
            for candidate in all_candidates:
                text_key = candidate['text'].lower().strip()
                if text_key not in unique_texts:
                    unique_texts.add(text_key)
                    filtered_candidates.append(candidate)
                else:
                    print(f"[DEBUG] 중복 상품명 제거: '{candidate['text'][:30]}...'")
            
            # 최소 점수 기준 강화 (UI 요소와 카테고리명 배제)
            valid_candidates = [c for c in filtered_candidates if c['score'] >= 30]  # 기존 5에서 30으로 상향
            
            if valid_candidates:
                best = valid_candidates[0]
                print(f"\n[DEBUG] 최종 선택: {best['element_selector']} -> '{best['text']}' (점수: {best['score']})")
                return best['element_selector']
            else:
                print(f"[DEBUG] 적절한 상품명 후보를 찾을 수 없음 (최고점: {all_candidates[0]['score'] if all_candidates else 0})")
                return None
        else:
            print("[DEBUG] 상품명 후보가 전혀 없음")
            return None
    
    async def _find_price(self, page):
        """가격 선택자 탐지 (확장된 패턴 지원)"""
        # 우선순위별 가격 선택자 후보들
        candidates = [
            # 1순위: 전용 가격 클래스들
            '.price', '.org_price', '.sale_price', '.product-price', '.goods-price',
            '.item-price', '.cost', '.amount', '.price-current', '.price-now',
            '.final-price', '.selling-price', '.retail-price',
            
            # 2순위: 가격 관련 속성들
            '[itemprop="price"]', '[data-price]', '[data-cost]',
            
            # 3순위: 클래스명 포함 패턴들
            '[class*="price"]', '[class*="cost"]', '[class*="amount"]',
            
            # 4순위: ID 기반 패턴들  
            '#price', '#cost', '#amount', '#product-price',
            
            # 5순위: 범용 가격 패턴들
            '.money', '.currency', '.won', '.dollar', '.value',
            'span[title*="가격"]', 'span[title*="price"]', 'div[title*="가격"]',
            
            # 6순위: 텍스트 포함 패턴들 (키드짐 등 특수 케이스)
            'span:contains("원")', 'div:contains("원")', 'td:contains("원")',
            'span:contains("₩")', 'div:contains("₩")', 'strong:contains("원")'
        ]
        
        # 개선된 가격 정규표현식 (다양한 형식 지원)
        price_patterns = [
            r'[\d,]+원',  # 10,000원 형식
            r'₩[\d,]+',   # ₩10,000 형식
            r'\$[\d,]+\.?\d*',  # $99.99 형식
            r'[\d,]+\s*won',  # 10000 won 형식
            r'[\d,]+\s*₩',  # 10000 ₩ 형식
            r'[\d]{1,3}(?:,\d{3})*',  # 숫자만 (콤마 포함)
            r'[\d]+\.[\d]{2}',  # 소수점 형식
        ]
        
        all_price_candidates = []
        
        # 모든 선택자 후보 테스트
        for selector in candidates:
            try:
                elements = await page.query_selector_all(selector)
                for i, element in enumerate(elements):
                    if element:
                        text = await element.text_content()
                        if text:
                            text = text.strip()
                            
                            # 가격 패턴 매칭 검사
                            matched_price = None
                            for pattern in price_patterns:
                                match = re.search(pattern, text)
                                if match:
                                    matched_price = match.group()
                                    break
                            
                            if matched_price:
                                # 가격 검증 및 스코어링
                                score = self._validate_and_score_price(text, matched_price, selector)
                                if score > 0:
                                    all_price_candidates.append({
                                        'selector': selector,
                                        'text': text,
                                        'price': matched_price,
                                        'score': score
                                    })
                                    
            except Exception as e:
                continue
        
        # 점수로 정렬하여 최고점 선택자 반환
        if all_price_candidates:
            all_price_candidates.sort(key=lambda x: x['score'], reverse=True)
            best_candidate = all_price_candidates[0]
            print(f"[DEBUG] 최고 가격 후보: {best_candidate['selector']} -> '{best_candidate['price']}' (점수: {best_candidate['score']})")
            return best_candidate['selector']
        
        return None
    
    def _validate_and_score_price(self, text, price_text, selector):
        """가격 텍스트 검증 및 스코어링"""
        score = 0
        
        # 기본 가격 패턴 점수
        if price_text:
            score += 10
            
        # 숫자 추출 및 범위 검증
        try:
            # 숫자만 추출
            numeric_price = re.sub(r'[^\d]', '', price_text)
            if numeric_price:
                price_value = int(numeric_price)
                
                # 의미있는 가격 범위 확인 (100원 ~ 10,000,000원)
                if 100 <= price_value <= 10000000:
                    score += 20
                    
                    # 일반적인 상품 가격 범위 보너스 (1,000원 ~ 1,000,000원)
                    if 1000 <= price_value <= 1000000:
                        score += 30
                else:
                    return 0  # 비현실적인 가격은 제외
                    
        except:
            return 0
            
        # 전용 가격 클래스 보너스
        price_class_keywords = ['price', 'cost', 'amount', 'money', 'won']
        if any(keyword in selector.lower() for keyword in price_class_keywords):
            score += 25
            
        # 가격 관련 속성 보너스  
        if 'itemprop="price"' in selector or 'data-price' in selector:
            score += 35
            
        # 텍스트 품질 검증
        if len(text) <= 20:  # 짧고 간결한 텍스트 선호
            score += 10
            
        # 불필요한 텍스트 포함시 감점
        exclude_words = ['배송', '무료', '적립', '할인', '쿠폰', '혜택', '이벤트']
        if any(word in text for word in exclude_words):
            score -= 15
            
        return max(score, 0)
    
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
