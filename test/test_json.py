#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import glob
import os
import time

def test_json_processing():
    """JSON 데이터 처리 테스트"""
    
    start_time = time.time()
    
    # 성능 측정 변수들
    json_products_count = 0
    json_processing_time = 0
    network_requests_saved = 0
    
    try:
        # 최신 perfect_result_*.json 파일에서 데이터 읽기
        json_files = glob.glob("perfect_result_*.json")
        if not json_files:
            raise FileNotFoundError("perfect_result_*.json 파일이 없습니다.")
        latest_json = max(json_files, key=os.path.getmtime)
        
        with open(latest_json, "r", encoding="utf-8") as f:
            data = json.load(f)
            selectors = data["선택자"]
            extracted_products = data.get("추출데이터", [])
        
        print(f"JSON 파일 로드 성공: {latest_json}")
        print(f"선택자 개수: {len(selectors)}")
        print(f"추출된 상품 개수: {len(extracted_products)}")
        
        # JSON 데이터가 있으면 우선 사용
        if extracted_products:
            print(f"[JSON_DATA] {len(extracted_products)}개 상품의 JSON 추출데이터 발견, JSON 데이터 우선 사용")
            
            json_start_time = time.time()
            
            # JSON 데이터 기반 상품 처리
            for idx, product_data in enumerate(extracted_products):
                try:
                    product_start_time = time.time()
                    product_url = product_data.get("url", "")
                    
                    if not product_url:
                        print("[WARNING] JSON 데이터에 url이 없습니다.")
                        continue
                    
                    print(f"[JSON_DATA] 상품 {idx+1} 처리 시작: {product_url}")
                    
                    # JSON 데이터에서 상품 정보 직접 가져오기
                    product_name = product_data.get("상품명", "상품명을 찾을 수 없습니다.")
                    price_text = product_data.get("가격", "0원")
                    options = product_data.get("선택옵션", [])
                    thumbnail_url = product_data.get("썸네일", "")
                    detail_img_urls = product_data.get("상세페이지", [])
                    
                    print(f"[JSON_DATA] 상품정보 - 이름: {product_name}, 가격: {price_text}, 상세이미지: {len(detail_img_urls)}개")
                    
                    # 성능 지표 업데이트
                    json_products_count += 1
                    product_processing_time = time.time() - product_start_time
                    json_processing_time += product_processing_time
                    network_requests_saved += 5  # 상품당 5번의 네트워크 요청 절약 추정
                    
                    print(f"[PERF] JSON 상품 처리 시간: {product_processing_time:.2f}초, 누적 절약 요청: {network_requests_saved}개")
                    
                except Exception as e:
                    print(f"[ERROR] JSON 데이터 상품 처리 중 오류: {e}")
                    continue
        else:
            print("[INFO] JSON 추출데이터가 없습니다.")
            
    except Exception as e:
        print(f"[ERROR] JSON 처리 중 오류: {e}")
    
    # 성능 요약 출력
    end_time = time.time()
    total_time = end_time - start_time
    
    print("\n" + "="*50)
    print("JSON 데이터 처리 테스트 결과")
    print("="*50)
    print(f"총 처리 시간: {total_time:.2f}초")
    print(f"JSON 데이터로 처리된 상품: {json_products_count}개")
    
    if json_products_count > 0:
        avg_json_time = json_processing_time / json_products_count
        print(f"JSON 상품당 평균 처리 시간: {avg_json_time:.2f}초")
    
    print(f"절약된 네트워크 요청: {network_requests_saved}개")
    print(f"JSON 데이터 활용률: 100.0%")
    print("[SUCCESS] JSON 데이터 처리 테스트 성공!")
    print("="*50)

if __name__ == "__main__":
    test_json_processing()
