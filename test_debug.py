#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task 1 디버깅 테스트: 단계별 검증
"""

import sys
sys.path.append('.')

import urllib.request
import urllib.error
from PIL import Image
import io

def test_url_pattern_filtering():
    """URL 패턴 필터링 테스트"""
    print("=== URL 패턴 필터링 테스트 ===")
    
    test_urls = [
        "https://kidgymb2b.co.kr/web/product/big/202311/804a48eb43897e87a52cd051a9cb46b9.jpg",
        "https://kidgymb2b.co.kr/web/upload/watermark3.png",
    ]
    
    for url in test_urls:
        url_lower = url.lower()
        
        # 제외 패턴 확인
        exclude_patterns = [
            'logo', 'icon', 'btn', 'button', 'menu', 'nav', 
            'arrow', 'quick', 'zzim', 'wishlist',
            'banner', 'common', 'header', 'footer',
            'popup', 'close', 'search', 'cart',
            'sns', 'facebook', 'twitter', 'kakao',
            'top_btn', 'scroll', 'floating',
            '_wg/', 'detail_img_info', 'delivery_info',
            'exchange_info', 'return_info', 'notice_info'
        ]
        
        excluded = False
        for pattern in exclude_patterns:
            if pattern in url_lower:
                print(f"제외됨: {url} (패턴: {pattern})")
                excluded = True
                break
        
        if not excluded:
            # 포함 패턴 확인
            include_patterns = [
                'detail', 'content', 'description', 'product',
                'item', 'goods', 'view', 'main', 'sub'
            ]
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
            
            has_include = any(pattern in url_lower for pattern in include_patterns)
            has_image_ext = any(ext in url_lower for ext in image_extensions)
            
            if has_include or has_image_ext:
                print(f"패턴 통과: {url} (include: {has_include}, ext: {has_image_ext})")
            else:
                print(f"패턴 실패: {url}")

def test_image_download():
    """이미지 다운로드 및 크기 확인 테스트"""
    print("\n=== 이미지 다운로드 테스트 ===")
    
    url = "https://kidgymb2b.co.kr/web/product/big/202311/804a48eb43897e87a52cd051a9cb46b9.jpg"
    
    try:
        print(f"테스트 URL: {url}")
        
        # HEAD 요청
        print("HEAD 요청 시도...")
        head_req = urllib.request.Request(url, method='HEAD')
        head_req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        try:
            with urllib.request.urlopen(head_req, timeout=10) as response:
                content_length = response.headers.get('Content-Length')
                if content_length:
                    file_size = int(content_length)
                    print(f"HEAD 요청 성공: {file_size} bytes")
                else:
                    print("HEAD 요청 성공하지만 Content-Length 없음")
        except Exception as e:
            print(f"HEAD 요청 실패: {e}")
        
        # 실제 다운로드
        print("실제 다운로드 시도...")
        img_req = urllib.request.Request(url)
        img_req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        with urllib.request.urlopen(img_req, timeout=15) as response:
            img_data = response.read()
            print(f"다운로드 성공: {len(img_data)} bytes")
            
            # PIL로 이미지 크기 확인
            img = Image.open(io.BytesIO(img_data))
            width, height = img.size
            print(f"이미지 크기: {width}x{height}")
            
            if width >= 660:
                print(f"크기 검증 통과: {width}px >= 660px")
            else:
                print(f"크기 검증 실패: {width}px < 660px")
                
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    test_url_pattern_filtering()
    test_image_download()
