#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from utils.image_optimizer import ImageDownloadOptimizer
from PIL import Image, ImageDraw, ImageFont

def test_improved_thumbnail():
    """개선된 썸네일 테스트 (더 큰 상품명 + 더 큰 S2B 배지)"""
    
    # 테스트할 상품명들
    test_products = [
        "스윙호스(6개입)",
        "키드짐 프리미엄 운동기구 세트",
        "플레이볼",
        "스타트걷기(추가구성요소포함)",
    ]
    
    optimizer = ImageDownloadOptimizer()
    
    for i, product_name in enumerate(test_products, 1):
        print(f"\n=== 개선된 테스트 {i}: '{product_name}' ===")
        
        # 650x650 캔버스 생성
        canvas = Image.new('RGB', (650, 650), 'white')
        
        # 회색 배경 (하단 상품명 영역)
        gray_background = Image.new('RGB', (650, 100), (56, 56, 56))
        canvas.paste(gray_background, (0, 550))
        
        # 가상 상품 이미지 (테스트용)
        product_img = Image.new('RGB', (400, 400), (200, 200, 200))
        img_x = (650 - 400) // 2
        img_y = (550 - 400) // 2
        canvas.paste(product_img, (img_x, img_y))
        
        # S2B REGISTERED 배지 (더 크게!)
        blue_background = Image.new('RGB', (150, 100), (0, 82, 204))
        canvas.paste(blue_background, (500, 0))
        red_badge = Image.new('RGB', (150, 50), (255, 61, 70))
        canvas.paste(red_badge, (500, 100))
        
        draw = ImageDraw.Draw(canvas)
        
        # 상품명 처리
        display_name = product_name[:13] + "..." if len(product_name) > 13 else product_name
        display_name = display_name.replace("-", "")
        
        # 동적 폰트 크기 조정 (더 큰 범위)
        max_text_width = 600
        font_path = "C:/Windows/Fonts/NanumGothicExtraBold.ttf"
        
        try:
            name_font = optimizer.get_fitting_font(draw, display_name, max_text_width, font_path, 80, 32)
            print(f"   적용된 상품명 폰트: {name_font.size}pt")
            
            # 텍스트 크기 계산
            try:
                bbox = draw.textbbox((0, 0), display_name, font=name_font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            except AttributeError:
                text_width, text_height = draw.textsize(display_name, font=name_font)
            
            # 상품명 텍스트 그리기
            text_x = (650 - text_width) // 2
            text_y = 550 + (100 - text_height) // 2
            draw.text((text_x, text_y), display_name, font=name_font, fill="white", stroke_fill="black", stroke_width=1)
            
            # S2B 배지 텍스트 (2배 크기!)
            try:
                s2b_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 60)
                reg_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 28)
                print(f"   S2B 폰트: 60pt, REGISTERED 폰트: 28pt")
            except:
                s2b_font = ImageFont.load_default()
                reg_font = ImageFont.load_default()
            
            # "S2B" 텍스트
            s2b_text = "S2B"
            try:
                bbox = draw.textbbox((0, 0), s2b_text, font=s2b_font)
                s2b_width = bbox[2] - bbox[0]
            except AttributeError:
                s2b_width, _ = draw.textsize(s2b_text, font=s2b_font)
            
            s2b_x = 500 + (150 - s2b_width) // 2
            s2b_y = 20
            draw.text((s2b_x, s2b_y), s2b_text, font=s2b_font, fill="white")
            
            # "REGISTERED" 텍스트
            reg_text = "REGISTERED"
            try:
                bbox = draw.textbbox((0, 0), reg_text, font=reg_font)
                reg_width = bbox[2] - bbox[0]
            except AttributeError:
                reg_width, _ = draw.textsize(reg_text, font=reg_font)
            
            reg_x = 500 + (150 - reg_width) // 2
            reg_y = 115
            draw.text((reg_x, reg_y), reg_text, font=reg_font, fill="white")
            
            # 테스트 이미지 저장
            test_filename = f"improved_thumb_{i}_{name_font.size}pt.jpg"
            canvas.save(test_filename, 'JPEG', quality=95)
            print(f"   테스트 이미지 저장: {test_filename}")
            
        except Exception as e:
            print(f"   오류: {e}")

if __name__ == "__main__":
    test_improved_thumbnail()
    print("\n🎉 개선된 썸네일 테스트 완료!")
    print("📊 개선사항:")
    print("   • 상품명: 32~80pt (기존 24~60pt 대비 33% 증가)")
    print("   • S2B 글자: 60pt (기존 30pt 대비 100% 증가)")
    print("   • REGISTERED: 28pt (기존 14pt 대비 100% 증가)")
    print("   • 배지 크기: 150x150px (기존 120x120px 대비 25% 확장)")
