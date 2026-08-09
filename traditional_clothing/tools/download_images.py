"""
从 TEXMET 数据集中筛选中国传统纺织品并下载图片
Metropolitan Museum of Art 开放数据，CC0 公共领域
"""
import os, sys, io, json, time
from urllib.request import urlretrieve
from urllib.error import URLError

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
IMG_DIR = os.path.join(DATA_DIR, "images")

def main():
    print("=" * 60)
    print("  传统服饰图像下载 (Met Museum TEXMET)")
    print("=" * 60)

    from datasets import load_dataset
    ds = load_dataset("hzafar/TEXMET", split="train")

    # 筛选条件
    china_keywords = ['china', 'chinese']
    textile_keywords = ['silk', 'textile', 'costume', 'dress', 'robe',
                        'embroidery', 'brocade', 'tapestry', 'velvet', 'damask',
                        'embroidered', 'woven', 'cotton', 'linen', 'wool']

    # 筛选中国相关纺织品
    filtered = []
    for i, item in enumerate(ds):
        culture = (item.get('culture') or '').lower()
        classification = (item.get('classification') or '').lower()
        medium = (item.get('medium') or '').lower()
        department = (item.get('department') or '').lower()
        object_name = (item.get('objectName') or '').lower()

        combined = f"{culture} {classification} {medium} {department} {object_name}"

        # 筛选: 中国相关 OR 纺织品相关
        is_china = any(kw in culture for kw in china_keywords)
        is_textile = any(kw in combined for kw in textile_keywords)

        if is_china or (is_textile and item.get('primaryImage')):
            filtered.append({
                'index': i,
                'objectID': item['objectID'],
                'title': item.get('title', ''),
                'culture': item.get('culture', ''),
                'dynasty': item.get('dynasty', ''),
                'period': item.get('period', ''),
                'objectDate': item.get('objectDate', ''),
                'medium': item.get('medium', ''),
                'classification': item.get('classification', ''),
                'department': item.get('department', ''),
                'dimensions': item.get('dimensions', ''),
                'creditLine': item.get('creditLine', ''),
                'objectURL': item.get('objectURL', ''),
                'primaryImage': item.get('primaryImage', ''),
                'primaryImageSmall': item.get('primaryImageSmall', ''),
                'is_china': is_china,
            })

    print(f"\n  总条目: {len(ds)}")
    print(f"  筛选结果: {len(filtered)} 条")
    print(f"  其中中国相关: {sum(1 for f in filtered if f['is_china'])} 条")
    print(f"  其中纺织品: {len(filtered) - sum(1 for f in filtered if f['is_china'])} 条")

    # 保存筛选索引
    idx_path = os.path.join(DATA_DIR, "downloads", "texmet_filtered.json")
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_in_dataset": len(ds),
            "filtered_count": len(filtered),
            "china_count": sum(1 for x in filtered if x['is_china']),
            "items": filtered[:500],  # 保存前500条元数据
        }, f, ensure_ascii=False, indent=2)
    print(f"  已保存筛选索引: texmet_filtered.json")

    # 下载图片 (限制数量避免过大)
    max_download = 100
    relic_dir = os.path.join(IMG_DIR, "relics", "met_museum")
    pattern_dir = os.path.join(IMG_DIR, "patterns", "met_museum")
    os.makedirs(relic_dir, exist_ok=True)
    os.makedirs(pattern_dir, exist_ok=True)

    downloaded = 0
    skipped = 0
    print(f"\n  开始下载图片 (最多 {max_download} 张)...")
    for item in filtered:
        if downloaded >= max_download:
            break
        url = item.get('primaryImage') or item.get('primaryImageSmall')
        if not url:
            skipped += 1
            continue

        # 选择目录: 中国条目放 relics, 其他纺织品放 patterns
        target_dir = relic_dir if item['is_china'] else pattern_dir
        obj_id = item['objectID']
        ext = url.rsplit('.', 1)[-1].split('?')[0] or 'jpg'
        filename = f"met_{obj_id}.{ext}"
        filepath = os.path.join(target_dir, filename)

        if os.path.exists(filepath):
            downloaded += 1
            continue

        try:
            urlretrieve(url, filepath)
            downloaded += 1
            if downloaded % 10 == 0:
                print(f"    已下载: {downloaded}/{max_download}")
            time.sleep(0.3)  # 礼貌限速
        except Exception as e:
            skipped += 1

    print(f"\n  下载完成: {downloaded} 张图片")
    print(f"  中国文物: {relic_dir}")
    print(f"  纺织品纹样: {pattern_dir}")
    print(f"  跳过: {skipped}")

    # 统计概览
    print(f"\n  按文化来源分布 (前20):")
    from collections import Counter
    culture_cnt = Counter(f['culture'] for f in filtered if f['culture'])
    for c, n in culture_cnt.most_common(20):
        print(f"    {c}: {n}")


if __name__ == "__main__":
    main()
