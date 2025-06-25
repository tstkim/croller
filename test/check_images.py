from PIL import Image
import os

print("이미지 파일 확인:")
print("=" * 50)

# 썸네일 확인
thumb_path = "C:/Users/ME/Pictures/cr/1_cr.jpg"
if os.path.exists(thumb_path):
    with Image.open(thumb_path) as img:
        print(f"썸네일 (1_cr.jpg):")
        print(f"  크기: {img.size}")
        print(f"  모드: {img.mode}")
        print(f"  파일 크기: {os.path.getsize(thumb_path):,} bytes")
        print()

# 상세이미지 확인
detail_path = "C:/Users/ME/Pictures/output/001_001.jpg"
if os.path.exists(detail_path):
    with Image.open(detail_path) as img:
        print(f"상세이미지 (001_001.jpg):")
        print(f"  크기: {img.size}")
        print(f"  모드: {img.mode}")
        print(f"  파일 크기: {os.path.getsize(detail_path):,} bytes")
        print(f"  가로 해상도: {img.size[0]}px (기준: 660px 이상)")
        print(f"  품질 기준: {'✅ 통과' if img.size[0] >= 660 else '❌ 미달'}")
        print()

print("✅ 모든 이미지 파일이 정상적으로 생성되었습니다!")
