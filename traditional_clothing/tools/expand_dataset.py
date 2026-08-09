"""
数据扩充脚本 — 从多个来源批量下载传统服饰图像
目标：从 100 张扩充到 5000+ 张
"""
import sys, io, os, json, time, subprocess
from urllib.request import urlretrieve
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
IMG_DIR = os.path.join(DATA_DIR, "images")

def download_texmet_chinese(max_images=500):
    """从 TEXMET 筛选中国/东亚纺织品，下载更多图片"""
    print("=" * 60)
    print(f"[1/4] TEXMET: 下载中国/亚洲纺织品图片 (目标 {max_images} 张)")
    from datasets import load_dataset
    ds = load_dataset("hzafar/TEXMET", split="train")
    print(f"  数据集总量: {len(ds)} 条目")

    # 更精准的中国/东亚筛选
    china_kw = ['china', 'chinese', 'japan', 'japanese', 'korea', 'korean',
                'asia', 'asian', 'silk', 'brocade', 'embroidery', 'dragon',
                'phoenix', 'lotus', 'cloud pattern', 'ming', 'qing', 'tang',
                'song', 'yuan', 'han dynasty', 'textile', 'costume', 'robe',
                'kimono', 'sari', 'shawl', 'tapestry', 'damask', 'velvet']

    filtered = []
    for i, item in enumerate(ds):
        culture = (item.get('culture') or '').lower()
        classification = (item.get('classification') or '').lower()
        medium = (item.get('medium') or '').lower()
        department = (item.get('department') or '').lower()
        title = (item.get('title') or '').lower()
        object_name = (item.get('objectName') or '').lower()
        combined = f"{culture} {classification} {medium} {department} {title} {object_name}"

        is_target = any(kw in culture for kw in ['china', 'chinese', 'japan', 'japanese', 'korea', 'korean'])
        is_textile = any(kw in combined for kw in ['silk', 'textile', 'costume', 'embroidery',
                                                     'brocade', 'tapestry', 'woven', 'robe', 'dress'])
        has_img = bool(item.get('primaryImage'))

        if has_img and (is_target or is_textile):
            filtered.append({
                'objectID': item['objectID'],
                'culture': item.get('culture', ''),
                'title': item.get('title', ''),
                'classification': item.get('classification', ''),
                'medium': item.get('medium', ''),
                'primaryImage': item['primaryImage'],
                'is_chinese': is_target,
            })

    print(f"  筛选结果: {len(filtered)} 条目 ({sum(1 for f in filtered if f['is_chinese'])} 中国相关)")

    # 下载图片
    pattern_dir = os.path.join(IMG_DIR, "patterns", "texmet_expanded")
    relic_dir = os.path.join(IMG_DIR, "relics", "texmet_chinese")
    os.makedirs(pattern_dir, exist_ok=True)
    os.makedirs(relic_dir, exist_ok=True)

    downloaded, skipped = 0, 0
    for item in filtered:
        if downloaded >= max_images:
            break
        target_dir = relic_dir if item['is_chinese'] else pattern_dir
        filename = f"texmet_{item['objectID']}.jpg"
        filepath = os.path.join(target_dir, filename)
        if os.path.exists(filepath):
            downloaded += 1
            continue
        try:
            urlretrieve(item['primaryImage'], filepath)
            downloaded += 1
            if downloaded % 50 == 0:
                print(f"    已下载: {downloaded}/{max_images}")
            time.sleep(0.2)
        except:
            skipped += 1

    print(f"  完成: {downloaded} 下载, {skipped} 跳过")
    return downloaded


def try_roboflow_download():
    """尝试从 Roboflow 下载 Chinese Traditional Clothing 数据集"""
    print("\n" + "=" * 60)
    print("[2/4] Roboflow: Chinese Traditional Clothing 数据集")

    # Roboflow Chinese-Traditional-Clothing 项目
    print("  数据集: ctcdata/chinese-traditional-clothing-dataset")
    print("  标注: 6,305 文件, 863MB")
    print("  需要 Roboflow API key")
    print()
    print("  手动下载方法:")
    print("  1. 访问 https://universe.roboflow.com/ctcdata/chinese-traditional-clothing-dataset")
    print("  2. 注册免费账号 → Download Dataset → 选择 YOLOv8 格式")
    print("  3. 或使用 Python:")
    print("     from roboflow import Roboflow")
    print("     rf = Roboflow(api_key='YOUR_KEY')")
    print("     project = rf.workspace('ctcdata').project('chinese-traditional-clothing-dataset')")
    print("     dataset = project.version(1).download('yolov8')")
    return 0


def try_github_clone():
    """尝试从 GitHub 获取数据集"""
    print("\n" + "=" * 60)
    print("[3/4] GitHub 开源数据集")

    repos = [
        ("VisionMillionDataStudio/Chinese-Traditional-Clothing-Dataset439",
         "传统服饰识别 YOLOv8 标注数据集"),
        ("yyyjjy/CulTi", "丝绸纹样+敦煌壁画 5,726 图文对 (需申请密码)"),
    ]

    for repo, desc in repos:
        print(f"  {repo}")
        print(f"    {desc}")
        print(f"    git clone https://github.com/{repo}.git")

    # 尝试实际 clone
    downloads_dir = os.path.join(DATA_DIR, "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    try:
        import subprocess
        target = os.path.join(downloads_dir, "Chinese-Traditional-Clothing-Dataset439")
        if not os.path.exists(target):
            print(f"\n  正在 clone Chinese-Traditional-Clothing-Dataset439...")
            subprocess.run(["git", "clone", "--depth", "1",
                           "https://github.com/VisionMillionDataStudio/Chinese-Traditional-Clothing-Dataset439.git",
                           target], check=True, timeout=60)
            print(f"  Clone 成功!")
            # Count images
            imgs = sum(1 for _ in os.walk(target) for f in _[2] if f.endswith(('.jpg','.png','.jpeg')))
            print(f"  图片数量: {imgs}")
            return imgs
        else:
            imgs = sum(1 for _ in os.walk(target) for f in _[2] if f.endswith(('.jpg','.png','.jpeg')))
            print(f"  已存在: {imgs} 张图片")
            return imgs
    except Exception as e:
        print(f"  Clone 失败: {e}")
        return 0


def download_more_met(max_total=800):
    """补充下载 Met Museum 中国相关图片"""
    print("\n" + "=" * 60)
    print(f"[4/4] 补充下载: Met Museum 中国相关图片 (目标总计 {max_total} 张)")

    # 检查已有图片
    existing = 0
    for d in ['data/images/patterns/met_museum', 'data/images/relics/met_museum',
              'data/images/patterns/texmet_expanded', 'data/images/relics/texmet_chinese']:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), d)
        if os.path.exists(path):
            existing += len([f for f in os.listdir(path) if f.endswith('.jpg')])

    remaining = max(0, max_total - existing)
    if remaining > 0:
        print(f"  现有: {existing}, 还需: {remaining}")
        download_texmet_chinese(max_images=remaining)
    else:
        print(f"  已有 {existing} 张, 已达到目标!")

    return existing


def final_stats():
    """统计所有已下载数据"""
    print("\n" + "=" * 60)
    print("  数据集最终统计")
    print("=" * 60)

    base = os.path.dirname(os.path.dirname(__file__))
    total_imgs = 0
    breakdown = {}

    for root, dirs, files in os.walk(os.path.join(base, "data", "images")):
        imgs = [f for f in files if f.endswith(('.jpg', '.png', '.jpeg'))]
        if imgs:
            rel = os.path.relpath(root, base)
            breakdown[rel] = len(imgs)
            total_imgs += len(imgs)

    for path, count in sorted(breakdown.items()):
        print(f"  {path}: {count} 张")
    print(f"  ---")
    print(f"  总计: {total_imgs} 张图像")

    # 知识库
    idx_path = os.path.join(base, "data", "dataset_index.json")
    if os.path.exists(idx_path):
        with open(idx_path, 'r', encoding='utf-8') as f:
            ds = json.load(f)
        print(f"  知识条目: {ds['total_count']} 条")

    return total_imgs


if __name__ == "__main__":
    print("=" * 60)
    print("  传统服饰数据扩充工具 v2.0")
    print("  目标：从 100 张 → 5000+ 张训练级图像")
    print("=" * 60)

    n1 = download_texmet_chinese(max_images=300)  # +300 中国/东亚纺织品
    n2 = try_roboflow_download()                   # Roboflow 说明
    n3 = try_github_clone()                         # GitHub clone
    n4 = final_stats()

    print(f"\n本次新增: ~{n1 + n3} 张图像")
    print(f"总计: {n4} 张")
