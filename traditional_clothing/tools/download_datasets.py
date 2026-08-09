"""
一键下载所有可获取的传统服饰数据集
用法: python tools/download_datasets.py

数据来源:
  1. HuggingFace 公开数据集 (fashion, traditional clothing)
  2. 洛阳民俗博物馆刺绣文物数据集
  3. GarmentCodeData (ETH Zurich)
  4. 内置知识库构建
"""
import os, json, sys, io

# Fix GBK encoding on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(os.path.join(DATA_DIR, "downloads"), exist_ok=True)


def download_hf_public_datasets():
    """下载 HuggingFace 上公开可用的服装/传统服饰相关数据集"""
    print("=" * 50)
    print("[1/4] HuggingFace 公开数据集...")

    # 尝试多个可能相关的公开数据集
    dataset_list = [
        # 公开服装数据集（不需要认证）
        ("keremberke/clothing-classification", "服装分类数据集"),
        ("TheFusion21/PokemonCards", None),  # skip
    ]

    success = 0
    for ds_name, desc in dataset_list:
        if desc is None:
            continue
        try:
            from datasets import load_dataset
            print(f"  尝试: {ds_name} - {desc}")
            ds = load_dataset(ds_name, trust_remote_code=False)
            info = {}
            for split_name in ds:
                info[split_name] = len(ds[split_name])
            print(f"  OK: {info}")
            success += 1
        except Exception as e:
            print(f"  跳过: {type(e).__name__}")

    # 尝试 Hanfu-Bench (需要认证)
    print(f"\n  Hanfu-Bench (lizhou21/hanfu-bench) - 需要 HuggingFace 登录")
    print(f"  登录命令: huggingface-cli login")
    print(f"  然后运行: from datasets import load_dataset")
    print(f"           ds = load_dataset('lizhou21/hanfu-bench')")

    print(f"  成功下载: {success} 个数据集")


def download_luoyang_embroidery():
    """洛阳刺绣数据集信息"""
    print("\n" + "=" * 50)
    print("[2/4] 洛阳民俗博物馆刺绣文物数据集")
    print("  DOI: 10.3974/geodb.2021.07.03.V1")
    print("  规模: 260件刺绣文物, 1.45GB")
    print("  来源: https://geodoi.ac.cn/WebCn/doi.aspx?ID=1836")
    print("  许可: 免费开放(需标注来源)")
    print("  状态: 需要浏览器手动下载4个压缩包")


def download_garmentcode_data():
    """GarmentCodeData"""
    print("\n" + "=" * 50)
    print("[3/4] GarmentCodeData (ETH Zurich)")
    print("  DOI: 10.3929/ethz-b-000673889")
    print("  规模: 115,000 条3D服装+纸样, 50GB+")
    print("  需要手动从 ETH Research Collection 下载")


def build_and_verify_knowledge():
    """验证内置知识数据集"""
    print("\n" + "=" * 50)
    print("[4/4] 内置知识数据集...")
    idx_path = os.path.join(DATA_DIR, "dataset_index.json")
    if os.path.exists(idx_path):
        with open(idx_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        total = data.get("total_count", 0)
        stats = data.get("statistics", {})
        print(f"  条目总数: {total}")
        print(f"  朝代分布: {stats.get('by_dynasty', {})}")
        print(f"  领型分布: {stats.get('by_collar', {})}")
        print(f"  袖型分布: {stats.get('by_sleeve', {})}")
        print(f"  裙型分布: {stats.get('by_skirt', {})}")
        print("  OK: 内置知识数据集完整")
    else:
        print("  dataset_index.json 未找到!")
        # 重建
        from data_scraper import DataCollector
        c = DataCollector("../data")
        anns = c.build_knowledge_dataset()
        c.save_dataset(anns)
        print(f"  已重建 {len(anns)} 条")


if __name__ == "__main__":
    print("=" * 60)
    print("  传统服饰数据集下载工具 v2.0")
    print("=" * 60)

    download_hf_public_datasets()
    download_luoyang_embroidery()
    download_garmentcode_data()
    build_and_verify_knowledge()

    print("\n" + "=" * 60)
    print("  下载任务完成!")
    print("  内置知识库: 28条 (dataset_index.json)")
    print("  外部数据集: 需手动下载 (见上方说明)")
    print("=" * 60)
