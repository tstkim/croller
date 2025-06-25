#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from utils.image_optimizer import ImageDownloadOptimizer
from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime

# 기존 이미지를 복사해서 새로운 방식으로 처리하는 테스트
def test_thumbnail_processing():
    # 새로운 경로에 테스트 폴더 생성
    tdate = datetime.now().strftime("%Y%m%d%H%M")
    base_path = f"C:/Users/ME/Documents/project/croller/images/{tdate}test"
    cr_path = f"{base_path}/cr"
    os.makedirs(cr_path, exist_ok=True)
    
    # 기존 이미지 복사
    source_img = "C:/Users/ME/Pictures/cr/1_cr.jpg"
    test_img = f"{cr_path}/test_cr.jpg"
    
    if os.path.exists(source_img):
        # 기존 이미지를 복사
        import shutil
        shutil.copy2(source_img, test_img)
        print(f"기존 이미지 복사: {source_img} -> {test_img}")
        
        # 새로운 방식으로 썸네일 처리
        try:
            # 원본 이미지 열기
            with Image.open(test_img) as original_img:
                # 650x650 흰색 캔버스 생성
                canvas = Image.new('RGB', (650, 650), 'white')
                
                # 회색 배경 (하단 상품명 영역)
                gray_background = Image.new('RGB', (650, 100), (56, 56, 56))
                canvas.paste(gray_background, (0, 550))
                
                # 원본 이미지 크기 조정 (최대 400x400, 비율 유지)
                original_img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                
                # 상품 이미지를 중앙 상단에 배치
                img_x = (650 - original_img.width) // 2
                img_y = (550 - original_img.height) // 2
                canvas.paste(original_img, (img_x, img_y))
                
                # S2B REGISTERED 배지 (우측 상단)
                blue_background = Image.new('RGB', (120, 80), (0, 82, 204))  # S2B 파란색
                canvas.paste(blue_background, (530, 0))
                red_badge = Image.new('RGB', (120, 40), (255, 61, 70))  # 빨간색
                canvas.paste(red_badge, (530, 80))
                
                draw = ImageDraw.Draw(canvas)
                
                # 상품명 텍스트 처리
                product_name = "테스트 상품명입니다"
                display_name = product_name[:13] + "..." if len(product_name) > 13 else product_name
                display_name = display_name.replace("-", "")
                
                # 폰트 로드
                try:
                    name_font = ImageFont.truetype("C:/Windows/Fonts/NanumGothicExtraBold.ttf", 32)
                except:
                    try:
                        name_font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 32)
                    except:
                        name_font = ImageFont.load_default()
                
                # 상품명 텍스트 그리기
                try:
                    bbox = draw.textbbox((0, 0), display_name, font=name_font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                except AttributeError:
                    text_width, text_height = draw.textsize(display_name, font=name_font)
                
                text_x = (650 - text_width) // 2
                text_y = 550 + (100 - text_height) // 2
                draw.text((text_x, text_y), display_name, font=name_font, fill="white", stroke_fill="black", stroke_width=1)
                
                # S2B 배지 텍스트
                try:
                    s2b_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 24)
                    reg_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 12)
                except:
                    try:
                        s2b_font = ImageFont.truetype("C:/Windows/Fonts/Arial.ttf", 24)
                        reg_font = ImageFont.truetype("C:/Windows/Fonts/Arial.ttf", 12)
                    except:
                        s2b_font = ImageFont.load_default()
                        reg_font = ImageFont.load_default()
                
                # "S2B" 텍스트 (파란색 영역)
                s2b_text = "S2B"
                try:
                    bbox = draw.textbbox((0, 0), s2b_text, font=s2b_font)
                    s2b_width = bbox[2] - bbox[0]
                except AttributeError:
                    s2b_width, _ = draw.textsize(s2b_text, font=s2b_font)
                
                s2b_x = 530 + (120 - s2b_width) // 2
                draw.text((s2b_x, 25), s2b_text, font=s2b_font, fill="white")
                
                # "REGISTERED" 텍스트 (빨간색 영역)
                reg_text = "REGISTERED"
                try:
                    bbox = draw.textbbox((0, 0), reg_text, font=reg_font)
                    reg_width = bbox[2] - bbox[0]
                except AttributeError:
                    reg_width, _ = draw.textsize(reg_text, font=reg_font)
                
                reg_x = 530 + (120 - reg_width) // 2
                draw.text((reg_x, 95), reg_text, font=reg_font, fill="white")
                
                # 최종 이미지 저장
                new_thumbnail = f"{cr_path}/new_style_cr.jpg"
                canvas.save(new_thumbnail, 'JPEG', quality=95)
                
                print(f"SUCCESS: 새로운 스타일 썸네일 생성 성공: {new_thumbnail}")
                print(f"저장 위치: {base_path}")
                print(f"특징: 650x650, 상품명 텍스트, S2B 배지 포함")
                
                return True
                
        except Exception as e:
            print(f"ERROR: 썸네일 처리 실패: {e}")
            return False
    else:
        print(f"ERROR: 기존 이미지 파일이 없습니다: {source_img}")
        return False

if __name__ == "__main__":
    print("새로운 썸네일 처리 방식 테스트...")
    success = test_thumbnail_processing()
    print(f"테스트 결과: {'성공' if success else '실패'}")
