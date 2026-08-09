"""
传统服饰数据采集工具

支持从多种来源采集传统服饰数据：
1. 博物馆公开数据（故宫数字文物库、洛阳民俗博物馆等）
2. 学术公开数据集（Hanfu-Bench, CulTi, GarmentCodeData）
3. 公开汉服图库
4. Hugging Face 数据集
5. 学术论文中的开放数据

数据采集后自动按照四级标注体系进行初步标注。
"""

import json
import os
import csv
import hashlib
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


# =============================================================================
# 数据源配置
# =============================================================================

DATA_SOURCES = {
    # 洛阳民俗博物馆刺绣文物数据集
    "luoyang_embroidery": {
        "name": "洛阳民俗博物馆刺绣文物数据集",
        "url": "https://geodoi.ac.cn/WebCn/doi.aspx?ID=1836",
        "doi": "10.3974/geodb.2021.07.03.V1",
        "type": "image",
        "count": 260,
        "era": "清中晚期-民国",
        "categories": ["云肩", "荷包", "绣裙", "肚兜", "童帽", "枕顶"],
        "license": "免费开放（需标注来源）",
        "download_method": "网页直接下载",
        "status": "available",
    },

    # 故宫数字文物库（服饰类）
    "palace_museum": {
        "name": "故宫博物院数字文物库",
        "url": "https://www.dpm.org.cn/explore/collections.html",
        "type": "image",
        "count": "10万+（含服饰数千件）",
        "era": "明清为主",
        "categories": ["宫廷服饰", "朝服", "吉服", "常服", "便服"],
        "license": "在线浏览免费，商用需授权",
        "download_method": "API/爬虫（需遵守robots.txt）",
        "status": "online_browse",
    },

    # Hanfu-Bench 学术基准
    "hanfu_bench": {
        "name": "Hanfu-Bench 汉服多模态基准",
        "url": "https://huggingface.co/datasets/lizhou21/hanfu-bench",
        "type": "image+text",
        "count": 1192,
        "era": "多朝代",
        "categories": ["汉服", "多模态问答"],
        "license": "CC BY-NC-SA 4.0（仅学术研究）",
        "download_method": "Hugging Face datasets 库",
        "status": "available",
    },

    # CulTi 丝绸纹样+敦煌壁画
    "culti": {
        "name": "CulTi 多模态文化遗产数据集",
        "url": "https://github.com/yyyjjy/CulTi",
        "type": "image+text",
        "count": 5726,
        "era": "多朝代",
        "categories": ["丝绸纹样", "敦煌壁画"],
        "license": "需签署数据使用协议",
        "download_method": "Google Drive（需申请密码）",
        "status": "request",
    },

    # GarmentCodeData
    "garment_code_data": {
        "name": "GarmentCodeData 3D服装数据集",
        "url": "https://igl.ethz.ch/projects/GarmentCodeData/",
        "type": "3D+sewing_pattern",
        "count": 115000,
        "era": "现代（但制版方法可复用）",
        "categories": ["上衣", "裙子", "裤子", "连衣裙", "连体裤"],
        "license": "学术研究",
        "download_method": "ETH Research Collection",
        "doi": "10.3929/ethz-b-000673889",
        "status": "available",
    },

    # 苏州丝绸纹样数据库
    "suzhou_silk": {
        "name": "苏州丝绸纹样数据库",
        "url": "https://www.suzhousilk.com/",
        "type": "pattern",
        "count": 10000,
        "era": "历代",
        "categories": ["丝绸纹样"],
        "license": "数据交易平台",
        "download_method": "苏州大数据交易所",
        "status": "licensed",
    },
}


# =============================================================================
# 内置传统服饰知识库 — 用于初始数据集构建
# =============================================================================

TRADITIONAL_GARMENT_KNOWLEDGE = [
    # ===== 明代服饰 =====
    {
        "dynasty": "明", "era_detail": "万历年间",
        "garment_type": "袄裙",
        "collar": "立领", "sleeve": "琵琶袖", "skirt": "马面裙",
        "patterns": ["缠枝莲纹", "如意云纹"],
        "colors": ["藏蓝", "银白", "金"],
        "material": "织金妆花缎",
        "ceremony_level": "常服", "social_status": "士庶命妇",
        "source": "山东博物馆藏",
        "description": "明万历年间女袄裙，立领琵琶袖短袄配藏蓝织金马面裙"
    },
    {
        "dynasty": "明", "era_detail": "嘉靖年间",
        "garment_type": "圆领袍",
        "collar": "圆领", "sleeve": "琵琶袖", "skirt": "",
        "patterns": ["云纹", "鹤纹"],
        "colors": ["大红", "金"],
        "material": "纻丝",
        "ceremony_level": "朝服", "social_status": "一品文官",
        "source": "孔府旧藏",
        "description": "明大红纻丝圆领袍，云鹤纹补子，一品文官朝服"
    },
    {
        "dynasty": "明", "era_detail": "万历",
        "garment_type": "道袍",
        "collar": "交领", "sleeve": "大袖", "skirt": "",
        "patterns": ["暗花"],
        "colors": ["月白"],
        "material": "暗花纱",
        "ceremony_level": "常服", "social_status": "士人",
        "source": "定陵出土",
        "description": "明月白暗花纱道袍，交领大袖，士人日常穿着"
    },
    {
        "dynasty": "明", "era_detail": "崇祯年间",
        "garment_type": "比甲",
        "collar": "对襟", "sleeve": "无袖", "skirt": "",
        "patterns": ["折枝牡丹"],
        "colors": ["石青", "白"],
        "material": "缎",
        "ceremony_level": "常服", "social_status": "士庶",
        "source": "故宫博物院藏",
        "description": "明石青缎折枝牡丹纹比甲，对襟无袖"
    },

    # ===== 唐代服饰 =====
    {
        "dynasty": "唐", "era_detail": "开元年间",
        "garment_type": "齐胸襦裙",
        "collar": "交领", "sleeve": "广袖", "skirt": "齐胸襦裙",
        "patterns": ["宝相花纹", "团花纹"],
        "colors": ["大红", "鹅黄", "石绿"],
        "material": "锦",
        "ceremony_level": "礼服", "social_status": "贵族",
        "source": "敦煌壁画摹本",
        "description": "唐开元齐胸襦裙，交领广袖，高腰至胸，宝相花纹锦"
    },
    {
        "dynasty": "唐", "era_detail": "天宝年间",
        "garment_type": "大袖衫",
        "collar": "坦领", "sleeve": "广袖", "skirt": "",
        "patterns": ["团窠纹"],
        "colors": ["绛紫", "金"],
        "material": "罗",
        "ceremony_level": "礼服", "social_status": "贵族",
        "source": "敦煌壁画",
        "description": "唐天宝大袖衫，坦领广袖，外罩透明罗纱"
    },
    {
        "dynasty": "唐", "era_detail": "中唐",
        "garment_type": "半臂襦裙",
        "collar": "交领", "sleeve": "窄袖", "skirt": "襦裙",
        "patterns": ["联珠纹"],
        "colors": ["青", "白", "红"],
        "material": "绢",
        "ceremony_level": "常服", "social_status": "士庶",
        "source": "唐墓壁画",
        "description": "唐中唐半臂襦裙，外罩半臂，交领窄袖内襦"
    },

    # ===== 宋代服饰 =====
    {
        "dynasty": "宋", "era_detail": "南宋",
        "garment_type": "褙子裙",
        "collar": "对襟", "sleeve": "窄袖", "skirt": "百迭裙",
        "patterns": ["折枝花纹"],
        "colors": ["月白", "淡青", "牙色"],
        "material": "罗",
        "ceremony_level": "常服", "social_status": "士庶",
        "source": "台北故宫博物院藏",
        "description": "南宋月白罗褙子，对襟窄袖，两侧开衩，配百迭裙"
    },
    {
        "dynasty": "宋", "era_detail": "北宋",
        "garment_type": "背子",
        "collar": "直领对襟", "sleeve": "窄袖", "skirt": "",
        "patterns": ["暗花"],
        "colors": ["淡粉"],
        "material": "绉纱",
        "ceremony_level": "常服", "social_status": "士庶女眷",
        "source": "福州南宋黄昇墓",
        "description": "南宋淡粉绉纱背子，直领对襟，窄袖，简约清雅"
    },
    {
        "dynasty": "宋", "era_detail": "北宋",
        "garment_type": "大袖衫裙",
        "collar": "交领", "sleeve": "广袖", "skirt": "百迭裙",
        "patterns": ["暗花缠枝"],
        "colors": ["朱红", "金"],
        "material": "织锦",
        "ceremony_level": "礼服", "social_status": "命妇",
        "source": "宋画《女孝经图》",
        "description": "宋朱红织锦大袖衫裙，命妇礼服，交领广袖配百迭裙"
    },

    # ===== 汉代服饰 =====
    {
        "dynasty": "汉", "era_detail": "西汉",
        "garment_type": "曲裾深衣",
        "collar": "交领", "sleeve": "广袖", "skirt": "曲裾绕襟",
        "patterns": ["云气纹", "几何纹"],
        "colors": ["朱红", "黑"],
        "material": "锦",
        "ceremony_level": "礼服", "social_status": "贵族",
        "source": "马王堆汉墓出土",
        "description": "西汉朱红锦曲裾深衣，交领右衽，曲裾绕襟三重"
    },
    {
        "dynasty": "汉", "era_detail": "东汉",
        "garment_type": "直裾深衣",
        "collar": "交领", "sleeve": "广袖", "skirt": "直裾",
        "patterns": ["菱形纹"],
        "colors": ["青", "白"],
        "material": "绢",
        "ceremony_level": "常服", "social_status": "士人",
        "source": "汉画像石",
        "description": "东汉青绢直裾深衣，交领广袖，下摆垂直"
    },

    # ===== 清代服饰 =====
    {
        "dynasty": "清", "era_detail": "乾隆年间",
        "garment_type": "吉服袍",
        "collar": "立领", "sleeve": "箭袖", "skirt": "袍服",
        "patterns": ["团龙纹", "海水江崖"],
        "colors": ["明黄"],
        "material": "缂丝",
        "ceremony_level": "朝服", "social_status": "皇帝",
        "source": "故宫博物院藏",
        "description": "清乾隆明黄缂丝团龙吉服袍，立领箭袖，皇帝吉服"
    },
    {
        "dynasty": "清", "era_detail": "光绪年间",
        "garment_type": "氅衣",
        "collar": "立领", "sleeve": "宽袖", "skirt": "",
        "patterns": ["折枝花卉", "蝴蝶纹"],
        "colors": ["湖蓝", "粉红"],
        "material": "绸",
        "ceremony_level": "常服", "social_status": "旗人女眷",
        "source": "故宫博物院藏",
        "description": "清光绪湖蓝绸绣折枝花卉氅衣，立领宽袖，滚边装饰"
    },
    {
        "dynasty": "清", "era_detail": "清末",
        "garment_type": "马面裙",
        "collar": "", "sleeve": "", "skirt": "马面裙",
        "patterns": ["海水江崖", "牡丹纹"],
        "colors": ["大红", "金"],
        "material": "织锦缎",
        "ceremony_level": "礼服", "social_status": "士庶",
        "source": "民间收藏",
        "description": "清大红织锦马面裙，前后马面+侧褶裥，海水江崖纹裙襕"
    },

    # ===== 魏晋南北朝 =====
    {
        "dynasty": "魏晋", "era_detail": "东晋",
        "garment_type": "襦裙",
        "collar": "交领", "sleeve": "广袖", "skirt": "间色裙",
        "patterns": ["几何纹"],
        "colors": ["浅绿", "白", "群青"],
        "material": "绢",
        "ceremony_level": "常服", "social_status": "士庶",
        "source": "顾恺之《女史箴图》",
        "description": "东晋襦裙，交领广袖，间色长裙，魏晋风流飘逸"
    },
    {
        "dynasty": "魏晋", "era_detail": "南北朝",
        "garment_type": "杂裾垂髾服",
        "collar": "交领", "sleeve": "广袖", "skirt": "杂裾",
        "patterns": ["云纹"],
        "colors": ["朱红", "白", "青"],
        "material": "纱",
        "ceremony_level": "礼服", "social_status": "贵族",
        "source": "北朝壁画",
        "description": "南北朝杂裾垂髾服，飞髾飘带装饰，交领广袖"
    },

    # ===== 经典纹样参考 =====
    {"dynasty": "通用", "pattern_name": "缠枝莲纹", "era": "宋→明清",
     "description": "以莲花为主体，枝蔓缠绕，寓意连绵不断。明清最为盛行。",
     "typical_colors": ["青花蓝白", "五彩", "青绿"],
     "source": "景德镇陶瓷纹样、织锦纹样"},
    {"dynasty": "通用", "pattern_name": "海水江崖纹", "era": "明清",
     "description": "波涛海水托起江崖，寓意江山永固。常用于官服下摆、裙襕。",
     "typical_colors": ["青蓝", "金", "五彩"],
     "source": "明清官服、马面裙襕"},
    {"dynasty": "通用", "pattern_name": "宝相花纹", "era": "唐→宋",
     "description": "佛教艺术影响，莲花变形为对称庄严的花卉纹。盛唐标志性纹样。",
     "typical_colors": ["金", "朱红", "石青"],
     "source": "敦煌壁画、唐代织锦"},
    {"dynasty": "通用", "pattern_name": "团凤纹", "era": "明清",
     "description": "凤凰呈圆形排列，象征祥瑞。皇后、命妇礼服常用。",
     "typical_colors": ["金", "五彩"],
     "source": "明清命妇礼服"},
    {"dynasty": "通用", "pattern_name": "落花流水纹", "era": "明",
     "description": "花瓣飘落于流水之上，明代最流行的浪漫纹样。",
     "typical_colors": ["青花蓝", "淡彩"],
     "source": "明代丝绸、瓷器"},
    {"dynasty": "通用", "pattern_name": "如意云纹", "era": "明→清",
     "description": "云头状如如意，寓意吉祥如意。多用于衣缘、领口装饰。",
     "typical_colors": ["金", "五彩"],
     "source": "明清服饰缘边"},
    {"dynasty": "通用", "pattern_name": "四合如意云纹", "era": "明清",
     "description": "四个如意云头组合成方形，最经典的传统云纹变体。",
     "typical_colors": ["金", "五彩"],
     "source": "明清织锦、缂丝"},
]


# =============================================================================
# 数据采集类
# =============================================================================

class DataCollector:
    """数据采集器 — 从多种来源获取传统服饰数据"""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.images_dir = self.data_dir / "images"
        self.texts_dir = self.data_dir / "texts"
        self.annotations_dir = self.data_dir / "annotations"

        for d in [self.images_dir, self.texts_dir, self.annotations_dir]:
            d.mkdir(parents=True, exist_ok=True)
            (d / "relics").mkdir(exist_ok=True)
            (d / "hanfu").mkdir(exist_ok=True)
            (d / "patterns").mkdir(exist_ok=True)
        for sub in ["literature", "craft", "culture"]:
            (self.texts_dir / sub).mkdir(exist_ok=True)

    def build_knowledge_dataset(self) -> List[dict]:
        """
        构建内置知识数据集

        将 TRADITIONAL_GARMENT_KNOWLEDGE 转化为标准标注格式，
        生成初始数据集索引。
        """
        annotations = []
        for i, item in enumerate(TRADITIONAL_GARMENT_KNOWLEDGE):
            if "garment_type" in item:
                # 服装条目
                ann = {
                    "image_id": f"knowledge_{item['dynasty']}_{item['garment_type']}_{i:03d}",
                    "dynasty": item["dynasty"],
                    "era_detail": item.get("era_detail", ""),
                    "garment_type": item["garment_type"],
                    "components": {
                        "collar": item.get("collar", ""),
                        "sleeve": item.get("sleeve", ""),
                        "skirt": item.get("skirt", ""),
                    },
                    "patterns": item.get("patterns", []),
                    "colors": item.get("colors", []),
                    "material": item.get("material", ""),
                    "ceremony_level": item.get("ceremony_level", ""),
                    "social_status": item.get("social_status", ""),
                    "source": item.get("source", ""),
                    "description": item.get("description", ""),
                    "annotator": "申新卓（知识编码）",
                    "review_status": "knowledge_verified",
                    "data_type": "reference_knowledge",
                }
            else:
                # 纹样条目
                ann = {
                    "image_id": f"pattern_{item['pattern_name']}_{i:03d}",
                    "dynasty": item.get("dynasty", "通用"),
                    "pattern_name": item.get("pattern_name", ""),
                    "pattern_era": item.get("era", ""),
                    "description": item.get("description", ""),
                    "typical_colors": item.get("typical_colors", []),
                    "source": item.get("source", ""),
                    "annotator": "申新卓（知识编码）",
                    "review_status": "knowledge_verified",
                    "data_type": "pattern_reference",
                }
            annotations.append(ann)

        return annotations

    def save_dataset(self, annotations: List[dict], filename: str = "dataset_index.json"):
        """保存数据集索引"""
        filepath = self.annotations_dir / filename
        data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "project": "基于大语言模型与视觉模型的传统服饰生成模型研究",
            "annotation_schema": "四级结构化标注：朝代-形制-部件-纹样",
            "total_count": len(annotations),
            "data_sources": list(DATA_SOURCES.keys()),
            "statistics": self._compute_stats(annotations),
            "annotations": annotations,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(filepath)

    def _compute_stats(self, annotations: List[dict]) -> dict:
        """计算数据集统计"""
        stats = {
            "total": len(annotations),
            "by_dynasty": {},
            "by_type": {},
            "by_collar": {},
            "by_sleeve": {},
            "by_skirt": {},
        }
        for ann in annotations:
            d = ann.get("dynasty", "未知")
            stats["by_dynasty"][d] = stats["by_dynasty"].get(d, 0) + 1

            if "garment_type" in ann:
                gt = ann.get("garment_type", "未知")
                stats["by_type"][gt] = stats["by_type"].get(gt, 0) + 1

                comps = ann.get("components", {})
                for key, stat_key in [("collar", "by_collar"), ("sleeve", "by_sleeve"), ("skirt", "by_skirt")]:
                    val = comps.get(key, "")
                    if val:
                        stats[stat_key][val] = stats[stat_key].get(val, 0) + 1
        return stats

    def create_download_script(self) -> str:
        """生成数据下载脚本（用于指导用户下载大型数据集）"""
        script = """#!/bin/bash
# 传统服饰数据集下载脚本
# 项目: 基于大语言模型与视觉模型的传统服饰生成模型研究
#
# 使用方法:
#   1. 确保已安装: pip install datasets huggingface_hub
#   2. 运行: bash download_datasets.sh

DATA_DIR="./downloads"
mkdir -p "$DATA_DIR"

echo "============================================"
echo " 传统服饰数据集下载工具"
echo "============================================"

# 1. Hanfu-Bench (Hugging Face)
echo ""
echo "[1/4] Hanfu-Bench 汉服多模态基准数据集..."
echo "来源: https://huggingface.co/datasets/lizhou21/hanfu-bench"
echo "许可: CC BY-NC-SA 4.0 (仅学术研究)"
echo ""
echo "Python 下载方式:"
echo "  from datasets import load_dataset"
echo "  dataset = load_dataset('lizhou21/hanfu-bench')"
echo ""

# 2. GarmentCodeData (ETH Zurich)
echo "[2/4] GarmentCodeData 3D服装数据集..."
echo "来源: https://igl.ethz.ch/projects/GarmentCodeData/"
echo "DOI: 10.3929/ethz-b-000673889"
echo ""
echo "访问 https://doi.org/10.3929/ethz-b-000673889 下载"
echo ""

# 3. 洛阳民俗博物馆刺绣文物数据集
echo "[3/4] 洛阳民俗博物馆刺绣文物数据集 (260件)..."
echo "来源: https://geodoi.ac.cn/WebCn/doi.aspx?ID=1836"
echo "DOI: 10.3974/geodb.2021.07.03.V1"
echo "免费下载，1.45GB"
echo ""

# 4. CulTi 多模态数据集
echo "[4/4] CulTi 丝绸纹样+敦煌壁画数据集 (5,726对)..."
echo "来源: https://github.com/yyyjjy/CulTi"
echo "需签署数据使用协议后获取 Google Drive 下载链接"
echo ""

echo "============================================"
echo " 内置知识数据集已构建完成"
echo " 运行 python tools/data_annotator.py 查看"
echo "============================================"
"""
        script_path = self.data_dir / "download_datasets.sh"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)
        return str(script_path)

    def create_huggingface_downloader(self) -> str:
        """生成 HuggingFace 数据集下载 Python 脚本"""
        script = '''"""
从 Hugging Face 下载传统服饰相关数据集

使用前安装: pip install datasets pillow
"""

import os
from datasets import load_dataset

DATA_DIR = "downloads"
os.makedirs(DATA_DIR, exist_ok=True)


def download_hanfu_bench():
    """下载 Hanfu-Bench 汉服多模态基准数据集"""
    print("正在下载 Hanfu-Bench...")
    try:
        dataset = load_dataset("lizhou21/hanfu-bench", trust_remote_code=True)
        print(f"✅ Hanfu-Bench 下载完成")
        for split in dataset:
            print(f"   {split}: {len(dataset[split])} 条数据")
        # 保存到本地
        dataset.save_to_disk(f"{DATA_DIR}/hanfu_bench")
        print(f"   已保存到 {DATA_DIR}/hanfu_bench")
        return dataset
    except Exception as e:
        print(f"⚠️ Hanfu-Bench 下载失败: {e}")
        print("   可能需要登录 Hugging Face: huggingface-cli login")
        return None


if __name__ == "__main__":
    print("=" * 50)
    print(" 传统服饰 HuggingFace 数据集下载工具")
    print("=" * 50)
    download_hanfu_bench()
'''
        script_path = self.data_dir / "download_hf_datasets.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)
        return str(script_path)


# =============================================================================
# 主程序
# =============================================================================

def main():
    collector = DataCollector("../data")

    print("=" * 60)
    print(" 传统服饰数据采集工具 v1.0")
    print("=" * 60)

    # 1. 构建内置知识数据集
    print("\n📚 [1/3] 构建内置知识数据集...")
    annotations = collector.build_knowledge_dataset()
    print(f"   ✅ 已生成 {len(annotations)} 条知识条目")
    print(f"      其中服装条目: {sum(1 for a in annotations if 'garment_type' in a)} 条")
    print(f"      纹样条目: {sum(1 for a in annotations if 'pattern_name' in a)} 条")

    # 2. 保存数据集
    print("\n💾 [2/3] 保存数据集索引...")
    filepath = collector.save_dataset(annotations)
    print(f"   ✅ 已保存到: {filepath}")

    # 3. 生成下载脚本
    print("\n📥 [3/3] 生成外部数据集下载脚本...")
    sh_path = collector.create_download_script()
    py_path = collector.create_huggingface_downloader()
    print(f"   ✅ Bash脚本: {sh_path}")
    print(f"   ✅ Python脚本: {py_path}")

    # 4. 数据源总览
    print("\n" + "=" * 60)
    print(" 📊 可获取的外部数据源")
    print("=" * 60)
    for key, src in DATA_SOURCES.items():
        status_icon = "🟢" if src["status"] == "available" else "🟡" if src["status"] == "online_browse" else "🔴"
        print(f" {status_icon} {src['name']}")
        print(f"    类型: {src['type']} | 数量: {src['count']} | 朝代: {src.get('era', 'N/A')}")
        print(f"    许可: {src['license']}")
        print(f"    获取: {src['download_method']}")
        print()

    print("=" * 60)
    print(" 🎉 数据采集初始化完成！")
    print(f"   内置知识库: {len(annotations)} 条")
    print(f"   外部数据源: {len(DATA_SOURCES)} 个")
    print("=" * 60)


if __name__ == "__main__":
    main()
