#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task 1 검증: FinalAnalyzer 이미지 크기 검증 로직 테스트
"""

import sys
sys.path.append('.')

from final_analyzer_universal import FinalAnalyzer

# 테스트용 키드짐 이미지 URL들
test_urls = [
    # 큰 이미지 (예상: True)
    "https://kidgymb2b.co.kr/web/product/big/202311/804a48eb43897e87a52cd051a9cb46b9.jpg",
    "https://kidgymb2b.co.kr/web/product/big/201903/96cfdc7347c8d4509113266b3f7cbc97.jpg",
    
    # 작은 이미지 (예상: False)
    "https://kidgymb2b.co.kr/web/product/small/201903/8da1df580945eba6226f4360401094c4.jpg",
    
    # 워터마크 이미지 (예상: False)
    "https://kidgymb2b.co.kr/web/upload/watermark3.png",
]

def test_image_validation():
    print("=== Task 1 검증: 이미지 크기 검증 로직 테스트 ===")
    print()
    
    analyzer = FinalAnalyzer()
    
    for i, url in enumerate(test_urls, 1):
        print(f"테스트 {i}: {url}")
        try:
            result = analyzer._is_valid_detail_image(url)
            if result:
                print("결과: PASS (660px+ 이미지)")
            else:
                print("결과: REJECT (크기 부족 또는 불필요 이미지)")
            print()
        except Exception as e:
            print(f"오류: {e}")
            print()

if __name__ == "__main__":
    test_image_validation()
