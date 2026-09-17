# 传统服饰数据集

> ⚠️ **本仓库（GitHub）未包含任何图片数据文件**
>
> 图像数据总体积约 820MB（6,300 张），git 不适合托管二进制大文件，
> 因此 **GitHub 上仅上传了标注数据与下载脚本，未上传图片文件**。
> 图片可通过脚本从原始来源重新下载（见下方）。

## 数据集清单

| 数据集 | 规模 | 标注 | 来源 | 状态 |
|--------|------|------|------|------|
| **Chinese-Traditional-Clothing Dataset** ⭐ | **6,300 张** | COCO 目标检测（8 类形制） | [Roboflow Universe](https://universe.roboflow.com/ctcdata/chinese-traditional-clothing-dataset) | ✅ **当前使用** |
| 内置知识库 | 28 条 | 四级结构化标注 | 学术文献编码 | ✅ 已上传 GitHub |
| 训练文本数据 | 18 条 | 文本配对 | 知识库编码 | ✅ 已上传 GitHub |
| DSL 训练数据 | 660 条 | 文本-GarmentCode 配对 | 脚本合成 | ✅ 已上传 GitHub |

## ⭐ 主力数据集详情

**Chinese-Traditional-Clothing Dataset**

| 项目 | 详情 |
|------|------|
| 来源 | [Roboflow Universe — ctcdata/chinese-traditional-clothing-dataset](https://universe.roboflow.com/ctcdata/chinese-traditional-clothing-dataset) |
| 分发 | Kaggle: `xiaomeigou/chinesetraditionalclothing`（v4） |
| 版本 | Roboflow **v12**（2023-05-02 导出） |
| 图片数 | 6,300 张（train 5,820 / valid 310 / test 170） |
| 标注 | COCO 格式，**24,562 个边界框** |
| 类别（8 类形制） | AoQun 袄裙、DaoPao 道袍、Pao 袍、QuJu 曲裾、RuQun 襦裙、ZhiDuo 直裰、ZhiJu 直裾、ZhuZiShenYi 朱子深衣 |
| 许可 | ⚠️ Roboflow 标注 `License: undefined`（未明确）——学术使用请注明来源，商用/再分发需联系作者 |

### ⚠️ 使用时注意事项

1. **增强数据**：6,300 张中含 Roboflow 自动增强（约 4.1 倍），
   **独立原图约 1,561 张**（文件名去掉 `.rf.<hash>` 后缀即为原图名）。
2. **数据泄露**：约 40 张原图（2.6%）的增强版本跨越了 train/valid/test，
   直接训练会导致验证指标虚高。**建议按原图名重新划分 split**：

```python
import os, re
from collections import defaultdict

orig2splits = defaultdict(set)
for split in ("train", "valid", "test"):
    for f in os.listdir(f"data/downloads/kaggle_chinese_clothing/{split}"):
        if f.lower().endswith((".jpg", ".jpeg", ".png")):
            orig = re.sub(r"\.rf\.[0-9a-f]+", "", f)   # 还原原图名
            orig2splits[orig].add(split)
# 同一原图的所有增强版本必须归入同一个 split
```

## 图片重新下载方式

```bash
# 主力数据集（Kaggle，约 820MB；首次需配置 Kaggle API 凭据）
pip install kagglehub
python tools/download_main_dataset.py

# 也可直接使用 kagglehub：
#   python -c "import kagglehub; print(kagglehub.dataset_download('xiaomeigou/chinesetraditionalclothing'))"
# 或从 Roboflow 页面手动导出：
#   https://universe.roboflow.com/ctcdata/chinese-traditional-clothing-dataset

# 可选：其他公开数据集（当前未使用，脚本保留）
python tools/download_public_data.py    # TEXMET（CC0）、中国传统女鞋
python tools/crawl_images.py            # Wikimedia Commons / Met Museum
python tools/download_images.py         # 批量图像下载
```

下载后图片存放于 `data/downloads/kaggle_chinese_clothing/`
（已被 `.gitignore` 排除，不会进入 git 仓库）。

## 目录说明

- `data/downloads/kaggle_chinese_clothing/` — 主力数据集图片，**未上传 GitHub**
- `data/downloads/kaggle_chinese_clothing/README.roboflow.txt` — 数据集官方说明（含来源、版本、许可）
- `kaggle_annotations/` — COCO 格式标注文件（**已上传 GitHub**）
- `data/annotations/` — 训练用 JSONL 数据（**已上传 GitHub**）
- `data/dataset_index.json` — 28 条知识库（**已上传 GitHub**）

## 附注

- 数据集官方 README（`README.roboflow.txt` / `README.dataset.txt`）保留在
  `data/downloads/kaggle_chinese_clothing/`，可核对来源与许可。
- 其他调研发现的公开数据集（民族服饰检测 2,474 张、少数民族服饰分类 10,320 张、
  TEXMET 18,644 张等）已登记在 `../data/README.md` 的"可选外部资源"章节。
