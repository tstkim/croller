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
        
        # 공통 경로 설정 (한 번만 설정)
        from datetime import datetime
        tdate = datetime.now().strftime("%Y%m%d%H%M")
        self.base_path = f"C:/Users/ME/Documents/project/croller/images/{tdate}kidgym"
        self.cr_path = f"{self.base_path}/cr"
        self.output_path = f"{self.base_path}/output"
        
        # 폴더 미리 생성
        os.makedirs(self.cr_path, exist_ok=True)
        os.makedirs(self.output_path, exist_ok=True)
        print(f"[INIT] 이미지 저장 경로 설정: {self.base_path}")
        
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
                    
                    # S2B REGISTERED 배지 (우측 상단) - 파란색 박스 세로 20% 축소!
                    blue_background = Image.new('RGB', (150, 80), (0, 82, 204))  # S2B 파란색 (100→80으로 20% 축소)
                    canvas.paste(blue_background, (500, 0))  # (530, 0) → (500, 0)으로 이동
                    red_badge = Image.new('RGB', (150, 50), (255, 61, 70))  # 빨간색 (120→150, 40→50으로 확장)
                    canvas.paste(red_badge, (500, 80))  # (530, 80) → (500, 80)으로 이동 (파란색 박스 크기에 맞춤)
                    
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
                    text_y = 540 + (100 - text_height) // 2  # 550→540으로 10px 위로 이동
                    draw.text((text_x, text_y), display_name, font=name_font, fill="white", stroke_fill="black", stroke_width=1)
                    
                    # S2B 배지 텍스트 - S2B는 크게, REGISTERED는 30% 줄임
                    try:
                        s2b_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 60)  # 30→60으로 2배 증가
                        reg_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 20)  # 28→20으로 30% 감소
                    except:
                        try:
                            s2b_font = ImageFont.truetype("C:/Windows/Fonts/Arial.ttf", 60)
                            reg_font = ImageFont.truetype("C:/Windows/Fonts/Arial.ttf", 20)  # 28→20으로 30% 감소
                        except:
                            s2b_font = ImageFont.load_default()
                            reg_font = ImageFont.load_default()
                    
                    # "S2B" 텍스트 (파란색 영역) - 새로운 배지 크기에 맞춤
                    s2b_text = "S2B"
                    try:
                        bbox = draw.textbbox((0, 0), s2b_text, font=s2b_font)
                        s2b_width = bbox[2] - bbox[0]
                    except AttributeError:
                        s2b_width, _ = draw.textsize(s2b_text, font=s2b_font)
                    
                    s2b_x = 500 + (150 - s2b_width) // 2  # 새로운 배지 크기에 맞춰 조정 (150px 폭)
                    s2b_y = 15  # 축소된 파란색 박스(80px)의 중앙에 맞춤 (20→15로 조정)
                    draw.text((s2b_x, s2b_y), s2b_text, font=s2b_font, fill="white")
                    
                    # "REGISTERED" 텍스트 (빨간색 영역) - 새로운 배지 크기에 맞춤
                    reg_text = "REGISTERED"
                    try:
                        bbox = draw.textbbox((0, 0), reg_text, font=reg_font)
                        reg_width = bbox[2] - bbox[0]
                    except AttributeError:
                        reg_width, _ = draw.textsize(reg_text, font=reg_font)
                    
                    reg_x = 500 + (150 - reg_width) // 2  # 새로운 배지 크기에 맞춰 조정 (150px 폭)
                    reg_y = 95  # 빨간색 배경 위에 (115→95로 20px 위로 이동)
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
        """상세이미지 다운로드 및 처리"""
        try:
            if not detail_img_urls:
                return False
            
            print(f"[DETAIL] 상세이미지 다운로드 시작: {len(detail_img_urls)}개")
            
            headers = {
                'Referer': 'https://kidgymb2b.co.kr/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            processed_count = 0
            
            for idx, img_url in enumerate(detail_img_urls[:10]):  # 최대 10개
                try:
                    print(f"[DETAIL] 이미지 {idx+1} 다운로드: {img_url}")
                    
                    # 이미지 다운로드
                    response = self.session.get(img_url, headers=headers, timeout=30)
                    response.raise_for_status()
                    
                    # 상세이미지 파일명 (예: 001_001.jpg, 001_002.jpg)
                    detail_filename = f"{image_counter:03}_{idx+1:03}.jpg"
                    detail_path = f"{self.output_path}/{detail_filename}"
                    
                    # 이미지 저장
                    with open(detail_path, 'wb') as f:
                        f.write(response.content)
                    
                    print(f"[DETAIL] 상세이미지 저장 성공: {detail_path}")
                    
                    # 간단한 크기 확인 (660px 이상만)
                    try:
                        with Image.open(detail_path) as img:
                            width, height = img.size
                            print(f"[DETAIL] 이미지 크기: {width}x{height}")
                            
                            if width >= 660:
                                processed_count += 1
                                print(f"[DETAIL] 유효한 이미지: {width}px >= 660px")
                            else:
                                print(f"[WARNING] 이미지 너비 부족: {width}px < 660px")
                                # 작은 이미지도 일단 유지
                                processed_count += 1
                                
                    except Exception as check_error:
                        print(f"[WARNING] 이미지 크기 확인 실패: {check_error}")
                        processed_count += 1
                    
                except Exception as img_error:
                    print(f"[ERROR] 이미지 {idx+1} 처리 실패: {img_error}")
                    continue
            
            print(f"[DETAIL] 상세이미지 처리 완료: {processed_count}개 성공")
            return processed_count > 0
            
        except Exception as e:
            print(f"[ERROR] 상세이미지 처리 실패: {e}")
            return False

    def close(self):
        """리소스 정리"""
        self.session.close()
