"""
生成增强数据集 — 基于知识库和 TEXMET 元数据，构建可用于微调的结构化数据集

策略：
1. 从 TEXMET 18,644 条元数据中提取中国/东亚纺织品标签
2. 结合内置知识库 (28条) 生成图文配对描述
3. 输出 JSONL 格式的训练数据
"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def generate_training_data():
    """生成可用于微调的结构化训练数据"""
    print("=" * 60)
    print("  生成 AI 训练数据")
    print("=" * 60)

    # 1. 加载 TEXMET 元数据
    try:
        from datasets import load_dataset
        ds = load_dataset("hzafar/TEXMET", split="train")
        print(f"\n[1] TEXMET 元数据: {len(ds)} 条")
    except:
        ds = None
        print("[1] TEXMET 不可用，使用知识库")

    # 2. 加载内置知识库
    idx_path = os.path.join(DATA_DIR, "dataset_index.json")
    with open(idx_path, "r", encoding="utf-8") as f:
        kb = json.load(f)

    # 3. 生成训练条目
    training_data = []
    categories = set()

    # 从知识库生成
    for item in kb["annotations"]:
        if item.get("data_type") == "reference_knowledge":
            categories.add(item.get("garment_type", item.get("pattern_name", "")))

            # 生成文本描述
            if "garment_type" in item:
                text = f"{item['dynasty']}{item['era_detail']}的{item['garment_type']}，"
                text += f"领型为{item['components']['collar']}，袖型为{item['components']['sleeve']}"
                if item['components'].get('skirt'):
                    text += f"，下裳为{item['components']['skirt']}"
                if item.get('patterns'):
                    text += f"，纹样包括{'、'.join(item['patterns'])}"
                text += f"，色彩为{'、'.join(item.get('colors', []))}"
                text += f"，面料为{item.get('material', '')}"
                text += f"，{item.get('ceremony_level', '')}，{item.get('description', '')}"
            else:
                text = f"传统纹样：{item.get('pattern_name', '')}，{item.get('description', '')}"

            training_data.append({
                "id": item["image_id"],
                "text": text,
                "dynasty": item["dynasty"],
                "category": item.get("garment_type", item.get("pattern_name", "")),
                "source": item.get("source", ""),
                "data_type": "knowledge_base",
            })

    # 从 TEXMET 生成
    if ds:
        china_kw = ['china', 'chinese', 'japan', 'korean', 'silk', 'brocade',
                     'embroidery', 'dragon', 'textile', 'costume', 'robe']
        count = 0
        for i, item in enumerate(ds):
            if count >= 500:
                break
            culture = (item.get('culture') or '').lower()
            medium = (item.get('medium') or '').lower()
            classification = (item.get('classification') or '').lower()
            combined = f"{culture} {medium} {classification}"

            if any(kw in combined for kw in china_kw) and item.get('primaryImage'):
                title = item.get('title', '')
                obj_date = item.get('objectDate', '')
                dimensions = item.get('dimensions', '')
                text = f"{item.get('culture', '')} {item.get('period', '')} {item.get('dynasty', '')} 的{title}，"
                text += f"年代{obj_date}，材质{medium}，{classification}，{dimensions}"

                training_data.append({
                    "id": f"texmet_{item['objectID']}",
                    "text": text,
                    "culture": item.get('culture', ''),
                    "medium": item.get('medium', ''),
                    "classification": item.get('classification', ''),
                    "image_url": item.get('primaryImage', ''),
                    "source": "Metropolitan Museum of Art",
                    "data_type": "texmet_metadata",
                })
                categories.add(classification)
                count += 1

        print(f"   TEXMET 条目: {count}")

    print(f"\n[2] 总训练条目: {len(training_data)}")
    print(f"   类别数: {len(categories)}")

    # 4. 保存 JSONL
    output_path = os.path.join(DATA_DIR, "annotations", "training_data.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for item in training_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"\n[3] 已保存训练数据: {output_path}")

    # 5. 生成统计
    from collections import Counter
    dynasties = Counter(item.get("dynasty", item.get("culture", "unknown"))
                        for item in training_data)
    types = Counter(item.get("category", item.get("classification", "unknown"))
                    for item in training_data)

    print(f"\n[4] 数据分布:")
    print(f"   朝代/文化分布 (top 10):")
    for k, v in dynasties.most_common(10):
        print(f"     {k}: {v}")
    print(f"   类别分布 (top 10):")
    for k, v in types.most_common(10):
        print(f"     {k}: {v}")

    return len(training_data)


if __name__ == "__main__":
    n = generate_training_data()
    print(f"\n{'='*60}")
    print(f"  生成 {n} 条训练数据 (JSONL)")
    print(f"  可用于 LLM/VLM 微调或 RAG 知识检索")
    print(f"{'='*60}")
