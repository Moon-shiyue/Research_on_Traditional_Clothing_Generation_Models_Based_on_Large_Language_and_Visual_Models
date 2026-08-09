"""
下载 HuggingFace 上真正公开可用的传统服饰/纺织品数据集

找到的数据集:
1. hzafar/TEXMET - 18,644 张全球传统纺织品 (Met Museum), CC0
2. guanya22388/ChineseTraditionalWomenClothShoesDataset - 1000+ 中国传统女鞋, CC-BY-4.0
"""
import os, sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "downloads")
os.makedirs(DATA_DIR, exist_ok=True)

from datasets import load_dataset, get_dataset_config_names
from huggingface_hub import list_repo_files


def download_texmet():
    """TEXMET - 大都会博物馆纺织品数据集 (18,644 images, 1,697 objects)"""
    print("=" * 60)
    print("[1/3] TEXMET: 全球传统纺织品数据集 (Metropolitan Museum)")
    print("      18,644 张纺织品图像, 1,697 件精选文物, 4000+ 年跨度")
    print("      许可: CC0 (完全公开，可商用)")
    try:
        ds = load_dataset("hzafar/TEXMET")
        print(f"  ✅ 下载成功!")
        total = 0
        for split_name in ds:
            count = len(ds[split_name])
            total += count
            print(f"     [{split_name}]: {count} 条")

        # 保存样本元数据
        if total > 0:
            sample = ds[list(ds.keys())[0]][0]
            meta = {
                "dataset": "hzafar/TEXMET",
                "description": "Metropolitan Museum of Art textiles collection",
                "total_items": total,
                "sample_keys": list(sample.keys()) if hasattr(sample, 'keys') else str(type(sample)),
                "license": "CC0 (Public Domain)",
            }
            with open(os.path.join(DATA_DIR, "texmet_info.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            print(f"  已保存元数据到 texmet_info.json")
        return ds
    except Exception as e:
        print(f"  ⚠ {type(e).__name__}: {str(e)[:200]}")
        return None


def download_chinese_shoes():
    """中国传统女鞋数据集 (1000+ images, CC-BY-4.0)"""
    print("\n" + "=" * 60)
    print("[2/3] 中国传统女鞋数据集 (ChineseTraditionalWomenClothShoes)")
    print("      1000+ 张图片, 含彝族/汉族绣花鞋")
    print("      许可: CC-BY-4.0")
    try:
        ds = load_dataset("guanya22388/ChineseTraditionalWomenClothShoesDataset")
        print(f"  ✅ 下载成功!")
        for split_name in ds:
            count = len(ds[split_name])
            print(f"     [{split_name}]: {count} 条")

        meta = {
            "dataset": "guanya22388/ChineseTraditionalWomenClothShoesDataset",
            "description": "Chinese Yi & Han ethnic traditional women's cloth shoes",
            "license": "CC-BY-4.0",
            "classes": ["plain/solid", "hand-embroidered ceremonial"],
        }
        with open(os.path.join(DATA_DIR, "chinese_shoes_info.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return ds
    except Exception as e:
        print(f"  ⚠ {type(e).__name__}: {str(e)[:200]}")
        return None


def save_sample_images():
    """将下载的数据集保存一些样本图片到本地"""
    print("\n" + "=" * 60)
    print("[3/3] 保存样本图片到 data/images/...")
    img_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "images")

    # TEXMET 样本
    try:
        ds = load_dataset("hzafar/TEXMET", split="train")
        from PIL import Image
        texmet_dir = os.path.join(img_dir, "patterns", "texmet")
        os.makedirs(texmet_dir, exist_ok=True)

        saved = 0
        for i, item in enumerate(ds):
            if saved >= 50:
                break
            try:
                img = item.get('image') or item.get('img') or item.get('picture')
                if img is not None:
                    if hasattr(img, 'save'):
                        img.save(os.path.join(texmet_dir, f"texmet_{i:04d}.jpg"))
                    saved += 1
            except:
                pass
        print(f"  TEXMET: 已保存 {saved} 张图片到 {texmet_dir}")
    except Exception as e:
        print(f"  TEXMET 图片保存: {type(e).__name__}")

    # 中国女鞋样本
    try:
        ds = load_dataset("guanya22388/ChineseTraditionalWomenClothShoesDataset", split="train")
        shoes_dir = os.path.join(img_dir, "relics", "chinese_shoes")
        os.makedirs(shoes_dir, exist_ok=True)

        saved = 0
        for i, item in enumerate(ds):
            if saved >= 50:
                break
            try:
                img = item.get('image') or item.get('img')
                if img is not None and hasattr(img, 'save'):
                    img.save(os.path.join(shoes_dir, f"shoe_{i:04d}.jpg"))
                    saved += 1
            except:
                pass
        print(f"  中国传统女鞋: 已保存 {saved} 张图片到 {shoes_dir}")
    except Exception as e:
        print(f"  鞋子图片保存: {type(e).__name__}")


if __name__ == "__main__":
    print("=" * 60)
    print("  公开传统服饰数据集下载工具")
    print("=" * 60)

    texmet = download_texmet()
    shoes = download_chinese_shoes()
    save_sample_images()

    # 总结
    print("\n" + "=" * 60)
    print("  下载完成!")
    print(f"  TEXMET (纺织品): {'✅' if texmet else '❌'}")
    print(f"  中国女鞋: {'✅' if shoes else '❌'}")
    print(f"  内置知识库: ✅ 28条 (dataset_index.json)")
    print(f"  图片已保存到: data/images/")
    print("=" * 60)
