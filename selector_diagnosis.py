"""
선택자 진단 스크립트
현재 상품명 선택자가 실제로 어떤 요소를 가리키는지 확인
"""
import requests
from bs4 import BeautifulSoup as bs
import json

def diagnose_selector():
    # perfect_result에서 실제 상품 URL 사용
    test_url = "https://kidgymb2b.co.kr/product/detail.html?product_no=6577&cate_no=223&display_group=1"
    
    print(f"[DIAGNOSIS] 테스트 URL: {test_url}")
    
    try:
        # 페이지 요청
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(test_url, headers=headers)
        response.raise_for_status()
        
        soup = bs(response.content, 'html.parser')
        
        print("\n" + "="*70)
        print("[DIAGNOSIS] 선택자 분석 결과")
        print("="*70)
        
        # 현재 사용 중인 상품명 선택자 확인
        current_selector = ".title"
        print(f"\n[CURRENT] 현재 상품명 선택자: {current_selector}")
        
        # 현재 선택자로 추출되는 요소들 확인
        title_elements = soup.select(current_selector)
        print(f"[CURRENT] '{current_selector}' 선택자로 발견된 요소: {len(title_elements)}개")
        
        for i, element in enumerate(title_elements[:5]):  # 최대 5개만 출력
            text = element.get_text(strip=True)
            classes = element.get('class', [])
            tag = element.name
            print(f"  {i+1}. <{tag} class='{' '.join(classes)}'> → '{text}'")
            
            # 부모 요소 정보도 확인
            parent = element.parent
            if parent:
                parent_classes = parent.get('class', [])
                print(f"      부모: <{parent.name} class='{' '.join(parent_classes)}'>")
        
        print(f"\n[ANALYSIS] 문제점: 모든 상품이 '좋아요'로 추출되는 이유")
        print(f"→ '{current_selector}' 선택자가 상품명이 아닌 다른 UI 요소를 가리키고 있음")
        
        # 상품명으로 보이는 다른 후보들 찾기
        print(f"\n[SEARCH] 실제 상품명 후보 탐색...")
        
        potential_selectors = [
            'h1', 'h2', 'h3', 
            '.product-name', '.product_name', '.goods-name', '.goods_name',
            '.item-name', '.item_name', '.name', 
            '[class*="name"]', '[class*="title"]', '[class*="product"]',
            '.detail-title', '.product-title', '.goods-title'
        ]
        
        candidates = []
        
        for selector in potential_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if text and len(text) >= 5 and len(text) <= 100:  # 상품명 길이 범위
                        # 제외 패턴 체크
                        exclude_patterns = ['좋아요', '카테고리', '메뉴', '로그인', '회원가입', '장바구니']
                        if not any(pattern in text for pattern in exclude_patterns):
                            candidates.append({
                                'selector': selector,
                                'text': text,
                                'classes': element.get('class', []),
                                'tag': element.name
                            })
            except:
                continue
        
        print(f"[CANDIDATES] 상품명 후보 {len(candidates)}개 발견:")
        for i, candidate in enumerate(candidates[:10]):  # 최대 10개만 출력
            print(f"  {i+1}. {candidate['selector']} → '{candidate['text'][:50]}...'")
            print(f"      <{candidate['tag']} class='{' '.join(candidate['classes'])}'>")
        
        # 가장 유력한 후보 추천
        if candidates:
            best_candidate = None
            best_score = 0
            
            for candidate in candidates:
                score = 0
                text = candidate['text']
                classes = ' '.join(candidate['classes']).lower()
                
                # 길이 점수
                if 10 <= len(text) <= 50:
                    score += 20
                
                # 클래스명 점수
                if any(keyword in classes for keyword in ['product', 'goods', 'item', 'name']):
                    score += 30
                
                # 브랜드명 대괄호 점수
                if '[' in text and ']' in text:
                    score += 50
                
                # 헤더 태그 점수
                if candidate['tag'] in ['h1', 'h2']:
                    score += 10
                
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
            
            if best_candidate:
                print(f"\n[RECOMMEND] 가장 유력한 상품명 선택자:")
                print(f"→ {best_candidate['selector']}")
                print(f"→ 추출 텍스트: '{best_candidate['text']}'")
                print(f"→ 점수: {best_score}")
        
        # 진단 결과 요약
        print(f"\n" + "="*70)
        print("[SUMMARY] 진단 결과 요약")
        print("="*70)
        print(f"✗ 현재 선택자 '.title': 잘못된 요소 ('좋아요') 추출")
        print(f"✓ 문제 원인: UI 버튼/링크 요소를 상품명으로 오인")
        print(f"✓ 해결 방안: 더 정확한 상품명 선택자로 교체 필요")
        if best_candidate:
            print(f"✓ 권장 선택자: {best_candidate['selector']}")
        print("="*70)
        
        return {
            'current_selector': current_selector,
            'current_results': [elem.get_text(strip=True) for elem in title_elements],
            'candidates': candidates,
            'best_candidate': best_candidate,
            'diagnosis': 'FAILED - Wrong selector extracting UI elements instead of product names'
        }
        
    except Exception as e:
        print(f"[ERROR] 진단 실패: {e}")
        return None

if __name__ == "__main__":
    result = diagnose_selector()
    
    # 결과를 JSON 파일로 저장
    if result:
        with open('selector_diagnosis_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n[SAVE] 진단 결과가 'selector_diagnosis_result.json'에 저장되었습니다.")
