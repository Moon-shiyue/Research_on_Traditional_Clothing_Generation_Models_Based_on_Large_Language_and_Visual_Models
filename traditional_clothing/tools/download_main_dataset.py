"""
下载主力数据集：Chinese-Traditional-Clothing Dataset

来源: https://universe.roboflow.com/ctcdata/chinese-traditional-clothing-dataset
分发: Kaggle - xiaomeigou/chinesetraditionalclothing (v4, 对应 Roboflow v12)

数据内容:
  - 6,300 张传统服饰图像 (train 5,820 / valid 310 / test 170)
  - COCO 格式标注，24,562 个边界框
  - 8 类形制: AoQun 袄裙 / DaoPao 道袍 / Pao 袍 / QuJu 曲裾 /
              RuQun 襦裙 / ZhiDuo 直裰 / ZhiJu 直裾 / ZhuZiShenYi 朱子深衣

用法:
    pip install kagglehub
    python tools/download_main_dataset.py

注意:
  - Kaggle 首次使用需配置 API 凭据 (~/.kaggle/kaggle.json)
    或设置环境变量 KAGGLE_USERNAME / KAGGLE_KEY
  - 数据集约 820MB，下载后存放于 data/downloads/kaggle_chinese_clothing/
  - 图片不纳入 git（.gitignore 已排除），标注文件已单独保存在 datasets/
  - 许可: Roboflow 标注为 undefined，学术使用请注明来源
"""
import os
import shutil
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST_DIR = os.path.join(PROJECT_ROOT, "data", "downloads", "kaggle_chinese_clothing")

KAGGLE_DATASET = "xiaomeigou/chinesetraditionalclothing"


def download():
    print("=" * 62)
    print("  下载主力数据集: Chinese-Traditional-Clothing Dataset")
    print("=" * 62)
    print(f"  Kaggle: {KAGGLE_DATASET}")
    print("  Roboflow: ctcdata/chinese-traditional-clothing-dataset (v12)")
    print("  规模: 6,300 张 / 24,562 标注框 / 8 类形制")
    print()

    try:
        import kagglehub
    except ImportError:
        print("  ✗ 缺少依赖 kagglehub，请先安装：")
        print("      pip install kagglehub")
        return 1

    try:
        print("[1/3] 从 Kaggle 下载（约 820MB，首次较慢）...")
        cache_path = kagglehub.dataset_download(KAGGLE_DATASET)
        print(f"  ✓ 下载完成: {cache_path}")
    except Exception as exc:
        print(f"  ✗ 下载失败: {type(exc).__name__}: {str(exc)[:200]}")
        print()
        print("  可能原因与解决方式：")
        print("    1) 未配置 Kaggle 凭据 → 到 kaggle.com 账号设置页创建 API Token，")
        print("       保存为 ~/.kaggle/kaggle.json")
        print("    2) 网络问题 → 可改用浏览器从 Roboflow 页面直接导出：")
        print("       https://universe.roboflow.com/ctcdata/chinese-traditional-clothing-dataset")
        return 1

    # 定位实际包含 train/valid/test 的目录
    src_dir = None
    for root, dirs, _files in os.walk(cache_path):
        if {"train", "valid", "test"} <= set(dirs):
            src_dir = root
            break
    if src_dir is None:
        print("  ✗ 未在下载内容中找到 train/valid/test 目录")
        return 1

    print(f"\n[2/3] 复制到项目目录: {DEST_DIR}")
    os.makedirs(os.path.dirname(DEST_DIR), exist_ok=True)
    if os.path.exists(DEST_DIR):
        shutil.rmtree(DEST_DIR)
    shutil.copytree(src_dir, DEST_DIR)
    print("  ✓ 复制完成")

    print("\n[3/3] 校验数据完整性...")
    total = 0
    for split in ("train", "valid", "test"):
        split_dir = os.path.join(DEST_DIR, split)
        if not os.path.isdir(split_dir):
            continue
        n = len([f for f in os.listdir(split_dir)
                 if f.lower().endswith((".jpg", ".jpeg", ".png"))])
        total += n
        ann = os.path.join(split_dir, "_annotations.coco.json")
        print(f"  {split:<6} {n:>5} 张" + ("  ✓ COCO 标注" if os.path.exists(ann) else "  ⚠ 缺标注"))
    print(f"  合计   {total:>5} 张")

    print()
    print("=" * 62)
    print("  完成！图片位于 data/downloads/kaggle_chinese_clothing/")
    print("  提示：")
    print("   - 数据集含 Roboflow 自动增强（约 4.1 倍），独立原图约 1,561 张")
    print("   - 训练前建议按原图名重新划分 split（见 datasets/README.md）")
    print("   - 许可为 undefined，学术使用请注明来源")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(download())
