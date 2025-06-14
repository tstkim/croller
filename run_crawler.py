#!/usr/bin/env python3
"""
통합 크롤링 실행기
1단계: final_analyzer_clean.py로 선택자 자동 분석
2단계: main.py로 대량 크롤링 실행
"""

import subprocess
import sys
import os
from datetime import datetime

def run_final_analyzer():
    """선택자 분석 실행"""
    print("\n" + "="*50)
    print("1단계: 선택자 자동 분석")
    print("="*50)
    
    # 실행 전 기존 JSON 파일 개수 확인
    import glob
    before_files = glob.glob("perfect_result_*.json")
    before_count = len(before_files)
    
    # 가상환경의 Python 실행 파일 경로
    python_exe = "./venv/Scripts/python.exe"
    
    # 루트 디렉토리의 final_analyzer_clean.py 실행
    result = subprocess.run([python_exe, "final_analyzer_clean.py"])
    
    # 실행 후 새로운 JSON 파일이 생성되었는지 확인
    after_files = glob.glob("perfect_result_*.json")
    after_count = len(after_files)
    
    if after_count > before_count:
        latest_file = max(after_files, key=os.path.getmtime)
        print(f"[SUCCESS] 선택자 분석 완료: {latest_file}")
        return True
    else:
        print("[ERROR] 선택자 파일이 생성되지 않았습니다.")
        return False

def run_main_crawler():
    """메인 크롤링 실행"""
    print("\n" + "="*50)
    print("2단계: 대량 크롤링 실행")
    print("="*50)
    
    # 가상환경의 Python 실행 파일 경로
    python_exe = "./venv/Scripts/python.exe"
    
    # main.py 실행
    result = subprocess.run([python_exe, "main.py"])
    
    return result.returncode == 0

def main():
    """메인 실행 함수"""
    start_time = datetime.now()
    
    print("택수님! 전체 크롤링 프로세스를 시작합니다!")
    print(f"시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 1단계: 선택자 분석
        if not run_final_analyzer():
            print("\n[ERROR] 선택자 분석에 실패했습니다.")
            return False
        
        # 2단계: 메인 크롤링
        if not run_main_crawler():
            print("\n[ERROR] 크롤링에 실패했습니다.")
            return False
        
        # 완료
        end_time = datetime.now()
        duration = end_time - start_time
        
        print("\n" + "="*50)
        print("전체 프로세스 완료!")
        print(f"총 소요시간: {duration}")
        print("="*50)
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n[INFO] 사용자에 의해 중단되었습니다.")
        return False
    except Exception as e:
        print(f"\n[ERROR] 예상치 못한 오류: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n[SUCCESS] 크롤링이 성공적으로 완료되었습니다!")
    else:
        print("\n[FAIL] 크롤링 중 문제가 발생했습니다.")
    
    # Windows에서 창이 바로 닫히지 않도록
    input("\n아무 키나 누르면 종료됩니다...")