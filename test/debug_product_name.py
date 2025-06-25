#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
키드짐 상품페이지 DOM 구조 분석 스크립트
상품명 추출 문제 해결을 위한 디버깅 도구
"""

import requests
from bs4 import BeautifulSoup
import json
import sys
from urllib.parse import urljoin

def analyze_product_page(url):
    """상품 페이지의 DOM 구조를 분석합니다."""
    
    print(f"[INFO] 분석 대상 URL: {url}")
    
    try:
        # 헤더 설정으로 접근 차단 방지
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # 페이지 요청
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        print(f"[SUCCESS] 페이지 로드 완료 (상태코드: {response.status_code})")
        
        # BeautifulSoup으로 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 상품명 후보들 찾기
        print("\n" + "="*80)
        print("상품명 후보 요소들 분석")
        print("="*80)
        
        # 1. h1, h2, h3 태그들 확인
        print("\n[1] 제목 태그 (h1, h2, h3) 분석:")
        for i, tag in enumerate(['h1', 'h2', 'h3'], 1):
            elements = soup.find_all(tag)
            print(f"\n  {tag.upper()} 태그 ({len(elements)}개):")
            for j, elem in enumerate(elements[:5], 1):  # 최대 5개만 표시
                text = elem.get_text(strip=True)
                classes = elem.get('class', [])
                print(f"    {j}. 텍스트: '{text}' | 클래스: {classes}")
        
        # 2. .title 클래스 요소들 확인
        print("\n[2] .title 클래스 요소들:")
        title_elements = soup.find_all(class_='title')
        print(f"  총 {len(title_elements)}개 발견:")
        for i, elem in enumerate(title_elements, 1):
            text = elem.get_text(strip=True)
            tag_name = elem.name
            all_classes = elem.get('class', [])
            print(f"    {i}. <{tag_name}> '{text}' | 전체클래스: {all_classes}")
        
        # 3. 상품명 가능성이 높은 패턴들 확인
        print("\n[3] 상품명 가능 패턴 분석:")
        
        # 패턴 1: product, name, goods 포함 클래스
        patterns = [
            {'class': 'product'},
            {'class': 'name'},
            {'class': 'goods'},
            {'id': 'product'},
            {'id': 'name'},
        ]
        
        for pattern in patterns:
            if 'class' in pattern:
                elements = soup.find_all(class_=lambda x: x and pattern['class'] in ' '.join(x))
                pattern_type = f"클래스에 '{pattern['class']}' 포함"
            else:
                elements = soup.find_all(id=lambda x: x and pattern['id'] in x)
                pattern_type = f"ID에 '{pattern['id']}' 포함"
            
            if elements:
                print(f"\n  {pattern_type} ({len(elements)}개):")
                for i, elem in enumerate(elements[:3], 1):
                    text = elem.get_text(strip=True)
                    tag_name = elem.name
                    classes = elem.get('class', [])
                    id_attr = elem.get('id', '')
                    print(f"    {i}. <{tag_name}> '{text}' | 클래스:{classes} | ID:{id_attr}")
        
        # 4. 메타 태그에서 상품명 찾기
        print("\n[4] 메타 태그 분석:")
        meta_patterns = [
            ('og:title', 'property'),
            ('twitter:title', 'name'), 
            ('title', 'name'),
            ('product:name', 'property'),
            ('keywords', 'name'),
            ('description', 'name')
        ]
        
        for pattern, attr_type in meta_patterns:
            try:
                if attr_type == 'property':
                    meta = soup.find('meta', property=pattern)
                else:
                    meta = soup.find('meta', attrs={'name': pattern})
                
                if meta:
                    content = meta.get('content', '')
                    print(f"  {pattern}: '{content}'")
            except Exception as e:
                print(f"  {pattern}: 오류 - {e}")
        
        # 페이지 타이틀도 확인
        if soup.title:
            title_text = soup.title.get_text(strip=True)
            print(f"  페이지 타이틀: '{title_text}'")
        
        # 5. 실제 상품명으로 보이는 요소들 추가 분석
        print("\n[5] 상품명 가능 요소들 추가 분석:")
        
        # 상품 정보 영역에서 상품명 찾기
        product_info_selectors = [
            '.goods_name',
            '.product_name', 
            '.item_name',
            '.prd_name',
            '.goods_info h1',
            '.product_info h1',
            '.detail_info h1',
            'h1.name',
            'h2.name',
            '.name:not(.title)',  # title 클래스가 아닌 name 클래스
            '#product_name',
            '[itemprop="name"]'  # 구조화 데이터의 name
        ]
        
        for selector in product_info_selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    print(f"\n  선택자 '{selector}' ({len(elements)}개):")
                    for i, elem in enumerate(elements[:3], 1):
                        text = elem.get_text(strip=True)
                        tag_name = elem.name
                        classes = elem.get('class', [])
                        print(f"    {i}. <{tag_name}> '{text}' | 클래스: {classes}")
            except Exception as e:
                print(f"  선택자 '{selector}' 오류: {e}")
        
        # 6. DOM 트리에서 상품명 패턴 분석
        print("\n[6] DOM 구조 기반 상품명 후보 분석:")
        
        # 텍스트 길이와 위치 기반으로 상품명 후보 찾기
        text_elements = soup.find_all(text=True)
        candidates = []
        
        for text in text_elements:
            text_content = text.strip()
            if (len(text_content) > 2 and len(text_content) < 100 and  # 적절한 길이
                not text_content.isdigit() and  # 숫자만 있는 것 제외
                '원' not in text_content and  # 가격 제외
                ',' not in text_content and   # 가격 구분자 제외
                '%' not in text_content and   # 할인율 제외
                text_content not in ['좋아요', '장바구니', '바로구매', '찜하기', '관심상품']):  # UI 텍스트 제외
                
                parent = text.parent
                if parent and parent.name not in ['script', 'style', 'meta', 'title']:
                    candidates.append({
                        'text': text_content,
                        'parent_tag': parent.name,
                        'parent_classes': parent.get('class', [])
                    })
        
        # 중복 제거 및 정렬
        unique_candidates = []
        seen_texts = set()
        for candidate in candidates:
            if candidate['text'] not in seen_texts:
                unique_candidates.append(candidate)
                seen_texts.add(candidate['text'])
        
        # 길이 순으로 정렬 (적절한 길이의 텍스트가 상품명일 가능성 높음)
        unique_candidates.sort(key=lambda x: abs(len(x['text']) - 15))  # 15자 내외가 적절
        
        print(f"  상품명 후보 텍스트들 (상위 10개):")
        for i, candidate in enumerate(unique_candidates[:10], 1):
            print(f"    {i}. '{candidate['text']}' (부모: <{candidate['parent_tag']}>, 클래스: {candidate['parent_classes']})")
        
        # 5. JSON-LD 구조화 데이터 확인
        print("\n[5] JSON-LD 구조화 데이터:")
        json_scripts = soup.find_all('script', type='application/ld+json')
        for i, script in enumerate(json_scripts, 1):
            try:
                data = json.loads(script.string)
                if 'name' in data:
                    print(f"  스크립트 {i} - name: '{data['name']}'")
                elif '@type' in data and data['@type'] == 'Product':
                    print(f"  스크립트 {i} - Product 타입 발견")
            except:
                pass
        
        # 6. 현재 perfect_result에서 사용 중인 선택자 테스트
        print("\n[6] 현재 선택자 '.title' 테스트:")
        current_selector = soup.select('.title')
        for i, elem in enumerate(current_selector, 1):
            text = elem.get_text(strip=True)
            tag_name = elem.name
            parent = elem.parent.name if elem.parent else 'None'
            print(f"  {i}. <{tag_name}> '{text}' (부모: <{parent}>)")
        
        print("\n" + "="*80)
        print("분석 완료")
        print("="*80)
        
    except requests.RequestException as e:
        print(f"[ERROR] 페이지 요청 실패: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] 분석 중 오류 발생: {e}")
        return False
    
    return True

def find_actual_product_urls(catalog_url):
    """카탈로그에서 실제 개별 상품 상세페이지 URL들을 찾습니다."""
    
    print(f"[INFO] 카탈로그 페이지 분석: {catalog_url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        }
        
        response = requests.get(catalog_url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        print(f"[DEBUG] 페이지 타이틀: {soup.title.string if soup.title else 'None'}")
        
        # 상품 링크 패턴 찾기
        product_links = []
        
        # 키드짐 B2B 사이트의 상품 링크 패턴 분석
        all_links = soup.find_all('a', href=True)
        
        print(f"[DEBUG] 전체 링크 개수: {len(all_links)}")
        
        # 링크 패턴 분석
        link_patterns = {}
        for link in all_links[:20]:  # 처음 20개만 분석
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # 패턴별로 분류
            if '/product/' in href and '/detail' in href:
                if 'product_detail' not in link_patterns:
                    link_patterns['product_detail'] = []
                link_patterns['product_detail'].append((href, text))
            elif '/product/' in href and href.count('/') > 2:
                if 'product_path' not in link_patterns:
                    link_patterns['product_path'] = []
                link_patterns['product_path'].append((href, text))
            elif '/goods/' in href:
                if 'goods' not in link_patterns:
                    link_patterns['goods'] = []
                link_patterns['goods'].append((href, text))
        
        print("\n[DEBUG] 발견된 링크 패턴들:")
        for pattern, links in link_patterns.items():
            print(f"  {pattern}: {len(links)}개")
            for i, (href, text) in enumerate(links[:3], 1):
                print(f"    {i}. {href} -> '{text}'")
        
        # CSS 선택자로 상품 링크 찾기
        selectors = [
            '.prdList .item a',  # 상품 목록의 아이템 링크
            '.productList li a',  # 상품 리스트 링크
            '.goods_list a',     # 상품 목록 링크
            '.product_item a',   # 상품 아이템 링크
            'a[href*="/detail"]',  # detail 포함 링크
            'a[href*="/product/"][href*="/"]'  # product 폴더 하위 링크
        ]
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    print(f"\n[DEBUG] 선택자 '{selector}': {len(elements)}개 발견")
                    for i, elem in enumerate(elements[:3], 1):
                        href = elem.get('href', '')
                        text = elem.get_text(strip=True)
                        print(f"    {i}. {href} -> '{text}'")
                        
                        if href and not href.startswith('javascript:'):
                            if href.startswith('/'):
                                full_url = urljoin(catalog_url, href)
                            else:
                                full_url = href
                            
                            # 개별 상품 페이지 패턴 확인
                            if ('/detail' in href or 
                                (href.count('/') >= 3 and '/product/' in href) or
                                '/goods/' in href):
                                if full_url not in product_links:
                                    product_links.append(full_url)
            except Exception as e:
                print(f"[DEBUG] 선택자 '{selector}' 오류: {e}")
        
        print(f"\n[SUCCESS] {len(product_links)}개의 개별 상품 링크 발견")
        
        # 처음 5개 링크 출력
        for i, link in enumerate(product_links[:5], 1):
            print(f"  {i}. {link}")
        
        return product_links[:3] if product_links else []
        
    except Exception as e:
        print(f"[ERROR] 카탈로그 분석 실패: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    print("키드짐 상품페이지 DOM 구조 분석 시작")
    print("="*80)
    
    # 1. 먼저 카탈로그에서 실제 상품 URL들을 찾기
    catalog_url = "https://kidgymb2b.co.kr/product/list.html?cate_no=223&page=1"
    product_urls = find_actual_product_urls(catalog_url)
    
    if not product_urls:
        print("[ERROR] 실제 상품 URL을 찾을 수 없습니다.")
        sys.exit(1)
    
    # 2. 찾은 상품 URL들을 분석
    for i, url in enumerate(product_urls, 1):
        print(f"\n{'='*80}")
        print(f"상품 {i} 분석")
        print(f"{'='*80}")
        
        success = analyze_product_page(url)
        
        if success:
            print(f"\n[SUCCESS] 상품 {i} 분석 완료")
        else:
            print(f"\n[FAILED] 상품 {i} 분석 실패")
            
        if i < len(product_urls):
            print("\n" + "-"*40 + " 다음 상품 " + "-"*40)
    
    print(f"\n{'='*80}")
    print("전체 분석 완료")
    print(f"{'='*80}")
