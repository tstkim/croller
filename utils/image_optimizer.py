#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import os
import time
from PIL import Image, ImageDraw, ImageFont


class ImageDownloadOptimizer:
    def __init__(self, max_workers=5):
        self.max_workers = max_workers
        self.session = requests.Session()
        
        # config.py 표준 경로 설정 (절대 변경 금지)
        from datetime import datetime
        from config import code, tdate, base_path, thumbnail_path, output_path
        
        # config.py에서 정의된 경로 사용
        self.base_path = base_path
        self.cr_path = thumbnail_path  # config.py의 thumbnail_path
        self.output_path = output_path  # config.py의 output_path
        
        print(f"[INIT] config.py 표준 경로 사용: {self.base_path}")
        
        # 키드짐 사이트에 특화된 헤더 설정
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        })

    def get_fitting_font(self, draw, text, max_width, font_path, max_font_size=80, min_font_size=32):
        """상품명 길이에 따라 글자 크기를 동적으로 조정"""
        font_size = max_font_size
        while font_size >= min_font_size:
            try:
                font = ImageFont.truetype(font_path, font_size)
                try:
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                except AttributeError:
                    text_width, _ = draw.textsize(text, font=font)
                if text_width <= max_width:
                    return font
            except Exception as e:
                print(f"[WARNING] 폰트 사이즈 {font_size}에서 오류: {e}")
            font_size -= 2
        return ImageFont.truetype(font_path, min_font_size)

    def download_and_process_thumbnail(self, thumbnail_url, image_counter, product_name):
        """썸네일 다운로드 및 처리"""
        try:
            if not thumbnail_url:
                return False
            
            print(f"[THUMB] 썸네일 다운로드 시작: {thumbnail_url}")
            
            # 이미지 다운로드
            headers = {
                'Referer': 'https://kidgymb2b.co.kr/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = self.session.get(thumbnail_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 썸네일 파일명 및 경로 설정
            thumbnail_filename = f"{image_counter}_cr.jpg"
            thumbnail_path = f"{self.cr_path}/{thumbnail_filename}"
            
            # 이미지 저장
            with open(thumbnail_path, 'wb') as f:
                f.write(response.content)
            
            print(f"[THUMB] 썸네일 저장 성공: {thumbnail_path}")
            
            # 650x650 캔버스에 상품명 텍스트와 S2B 배지 포함한 썸네일 생성
            try:
                # PIL 라이브러리 로드됨
                
                # 원본 이미지 열기
                with Image.open(thumbnail_path) as original_img:
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
                    
                    # S2B REGISTERED 배지 (우측 상단 모서리에 딱 붙이기)
                    blue_background = Image.new('RGB', (120, 80), (0, 82, 204))  # 파란색 박스
                    canvas.paste(blue_background, (530, 0))  # 650-120=530, Y=0 (모서리)
                    red_badge = Image.new('RGB', (120, 40), (255, 61, 70))  # 빨간색 박스
                    canvas.paste(red_badge, (530, 80))  # 파란색 박스 바로 아래
                    
                    draw = ImageDraw.Draw(canvas)
                    
                    # 상품명 텍스트 처리
                    display_name = product_name[:13] + "..." if len(product_name) > 13 else product_name
                    display_name = display_name.replace("-", "")
                    
                    # 동적 폰트 크기 조정
                    max_text_width = 600  # 650px 캔버스에서 좌우 25px 여백
                    font_path = "C:/Windows/Fonts/NanumGothicExtraBold.ttf"
                    
                    try:
                        name_font = self.get_fitting_font(draw, display_name, max_text_width, font_path, 80, 32)
                        print(f"[FONT] 적용된 폰트 크기: {name_font.size}pt for '{display_name}'")
                    except:
                        try:
                            font_path = "C:/Windows/Fonts/malgun.ttf"
                            name_font = self.get_fitting_font(draw, display_name, max_text_width, font_path, 80, 32)
                            print(f"[FONT] 말굼 폰트 적용: {name_font.size}pt")
                        except:
                            name_font = ImageFont.load_default()
                            print(f"[FONT] 기본 폰트 사용")
                    
                    # 상품명 텍스트 그리기 (하단 회색 영역 중앙)
                    try:
                        bbox = draw.textbbox((0, 0), display_name, font=name_font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                    except AttributeError:
                        text_width, text_height = draw.textsize(display_name, font=name_font)
                    
                    text_x = (650 - text_width) // 2
                    text_y = 560  # 회색 영역(550~650) 상단에서 10px 아래
                    draw.text((text_x, text_y), display_name, font=name_font, fill="white", stroke_fill="black", stroke_width=2)
                    
                    # S2B 배지 텍스트
                    try:
                        s2b_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 60)
                        reg_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 16)
                    except:
                        try:
                            s2b_font = ImageFont.truetype("C:/Windows/Fonts/Arial.ttf", 60)
                            reg_font = ImageFont.truetype("C:/Windows/Fonts/Arial.ttf", 16)
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
                    
                    s2b_x = 530 + (120 - s2b_width) // 2  # 새로운 배지 위치(530)에 맞춰 조정
                    s2b_y = 20  # 파란색 박스(80px) 중앙에 맞춤
                    draw.text((s2b_x, s2b_y), s2b_text, font=s2b_font, fill="white")
                    
                    # "REGISTERED" 텍스트 (빨간색 영역) - 새로운 배지 위치에 맞춤
                    reg_text = "REGISTERED"
                    try:
                        bbox = draw.textbbox((0, 0), reg_text, font=reg_font)
                        reg_width = bbox[2] - bbox[0]
                    except AttributeError:
                        reg_width, _ = draw.textsize(reg_text, font=reg_font)
                    
                    reg_x = 530 + (120 - reg_width) // 2  # 새로운 배지 위치(530)에 맞춰 조정
                    reg_y = 95  # 빨간색 배경 위에 (80+15=95)
                    draw.text((reg_x, reg_y), reg_text, font=reg_font, fill="white")
                    
                    # 최종 이미지 저장
                    canvas.save(thumbnail_path, 'JPEG', quality=95)
                    
                print(f"[THUMB] 썸네일 생성 완료: 650x650 (상품명 + S2B 배지)")
                
            except Exception as resize_error:
                print(f"[WARNING] 썸네일 처리 실패: {resize_error}")
                # 실패 시 기본 방식으로 폴백
                try:
                    with Image.open(thumbnail_path) as original_img:
                        canvas = Image.new('RGB', (650, 650), 'white')
                        original_img.thumbnail((600, 600), Image.Resampling.LANCZOS)
                        x = (650 - original_img.width) // 2
                        y = (650 - original_img.height) // 2
                        canvas.paste(original_img, (x, y))
                        canvas.save(thumbnail_path, 'JPEG', quality=90)
                        print(f"[THUMB] 기본 썸네일 생성 완료: 650x650")
                except Exception as fallback_error:
                    print(f"[ERROR] 썸네일 폴백 처리도 실패: {fallback_error}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] 썸네일 처리 실패: {e}")
            return False

    def download_and_process_detail_images(self, detail_img_urls, image_counter, product_name):
        """상세이미지 다운로드 및 처리 (기존 main.py 방식: 결합 후 10등분)"""
        try:
            if not detail_img_urls:
                return False
            
            print(f"[DETAIL] 상세이미지 다운로드 시작: {len(detail_img_urls)}개")
            
            headers = {
                'Referer': 'https://kidgymb2b.co.kr/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 1. 모든 상세이미지를 다운로드하고 하나로 결합
            combined_image = None
            valid_images = []
            
            for idx, img_url in enumerate(detail_img_urls):
                try:
                    print(f"[DETAIL] 이미지 {idx+1} 다운로드: {img_url}")
                    
                    # 이미지 다운로드
                    response = self.session.get(img_url, headers=headers, timeout=30)
                    response.raise_for_status()
                    
                    # 임시 파일로 저장
                    temp_filename = f"temp_detail_{image_counter}_{idx}.jpg"
                    temp_path = f"{self.output_path}/{temp_filename}"
                    
                    with open(temp_path, 'wb') as f:
                        f.write(response.content)
                    
                    # 이미지 열기 및 크기 확인
                    with Image.open(temp_path) as img:
                        img = img.convert("RGB")
                        width, height = img.size
                        print(f"[DETAIL] 이미지 크기: {width}x{height}")
                        
                        if width >= 660:  # 유효한 해상도만 사용
                            valid_images.append(img.copy())
                            print(f"[DETAIL] 유효한 이미지: {width}px >= 660px")
                        else:
                            print(f"[WARNING] 이미지 너비 부족: {width}px < 660px")
                    
                    # 임시 파일 삭제
                    os.remove(temp_path)
                    
                except Exception as img_error:
                    print(f"[ERROR] 이미지 {idx+1} 처리 실패: {img_error}")
                    continue
            
            if not valid_images:
                print(f"[ERROR] 유효한 상세이미지가 없음")
                return False
            
            print(f"[DETAIL] 유효한 이미지 {len(valid_images)}개 결합 시작")
            
            # 2. 이미지를 세로로 결합 (기존 main.py 방식)
            combined_image = None
            for img in valid_images:
                if combined_image is None:
                    combined_image = img
                else:
                    # 너비를 맞춤 (큰 쪽으로)
                    combined_width = max(combined_image.width, img.width)
                    combined_height = combined_image.height + img.height
                    
                    # 새로운 결합 이미지 생성
                    new_combined_image = Image.new("RGB", (combined_width, combined_height), "white")
                    new_combined_image.paste(combined_image, (0, 0))
                    new_combined_image.paste(img, (0, combined_image.height))
                    
                    combined_image.close()
                    combined_image = new_combined_image
            
            # 3. 결합된 이미지를 10등분해서 저장 (기존 main.py 방식)
            if combined_image is not None:
                width, height = combined_image.size
                slice_height = height // 10  # 이미지 하나의 높이
                
                print(f"[DETAIL] 결합 이미지 크기: {width}x{height}, 조각 높이: {slice_height}")
                
                for i in range(10):
                    crop_area = (0, slice_height * i, width, slice_height * (i + 1))  # 이미지 자르는 영역 설정
                    cropped_img = combined_image.crop(crop_area)  # 이미지 자르기
                    
                    # 파일명: 기존 main.py 방식과 동일 (001_001.jpg, 001_002.jpg ...)
                    detail_filename = f"{image_counter:03}_{i + 1:03}.jpg"
                    detail_path = f"{self.output_path}/{detail_filename}"
                    
                    cropped_img.save(detail_path, 'JPEG', quality=90)  # 잘린 이미지 저장
                    print(f"[DETAIL] 조각 {i+1} 저장: {detail_path}")
                    
                    cropped_img.close()
                
                combined_image.close()
                print(f"[DETAIL] 상세이미지 처리 완료: 10개 조각 생성")
                return True
            
            else:
                print(f"[ERROR] 이미지 결합 실패")
                return False
            
        except Exception as e:
            print(f"[ERROR] 상세이미지 처리 실패: {e}")
            return False

    def close(self):
        """리소스 정리"""
        self.session.close()
