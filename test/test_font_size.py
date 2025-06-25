#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from utils.image_optimizer import ImageDownloadOptimizer
from PIL import Image, ImageDraw, ImageFont

def test_font_sizes():
    """다양한 길이의 상품명으로 폰트 크기 테스트"""
    
    # 테스트할 상품명들 (다양한 길이)
    test_products = [
        "스윙호스(6개입)",  # 짧은 이름
        "키드짐 스윙 호스 6개입 세트",  # 중간 길이
        "키드짐 프리미엄 스윙 호스 6개입 세트 최고급",  # 긴 이름
        "A",  # 매우 짧은 이름
        "키드짐프리미엄스윙호스6개입세트최고급품질보장제품",  # 매우 긴 이름
    ]
    
    optimizer = ImageDownloadOptimizer()
    
    for i, product_name in enumerate(test_products, 1):
        print(f"\n=== 테스트 {i}: '{product_name}' ===")
        
        # 650x650 캔버스 생성
        canvas = Image.new('RGB', (650, 650), 'white')
        
        # 회색 배경 (하단 상품명 영역)
        gray_background = Image.new('RGB', (650, 100), (56, 56, 56))
        canvas.paste(gray_background, (0, 550))
        
        draw = ImageDraw.Draw(canvas)
        
        # 상품명 처리
        display_name = product_name[:13] + "..." if len(product_name) > 13 else product_name
        display_name = display_name.replace("-", "")
        
        # 동적 폰트 크기 조정
        max_text_width = 600
        font_path = "C:/Windows/Fonts/NanumGothicExtraBold.ttf"
        
        try:
            name_font = optimizer.get_fitting_font(draw, display_name, max_text_width, font_path, 60, 24)
            print(f"   적용된 폰트 크기: {name_font.size}pt")
            print(f"   표시될 텍스트: '{display_name}'")
            
            # 텍스트 크기 계산
            try:
                bbox = draw.textbbox((0, 0), display_name, font=name_font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            except AttributeError:
                text_width, text_height = draw.textsize(display_name, font=name_font)
            
            print(f"   텍스트 크기: {text_width}x{text_height}px")
            
            # 텍스트 그리기
            text_x = (650 - text_width) // 2
            text_y = 550 + (100 - text_height) // 2
            draw.text((text_x, text_y), display_name, font=name_font, fill="white", stroke_fill="black", stroke_width=1)
            
            # 테스트 이미지 저장
            test_filename = f"test_font_{i}_{name_font.size}pt.jpg"
            canvas.save(test_filename, 'JPEG', quality=95)
            print(f"   테스트 이미지 저장: {test_filename}")
            
        except Exception as e:
            print(f"   오류: {e}")

if __name__ == "__main__":
    test_font_sizes()
    print("\n✅ 폰트 크기 테스트 완료!")
