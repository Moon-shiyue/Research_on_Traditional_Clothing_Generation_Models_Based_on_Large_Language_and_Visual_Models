# 传统服饰数据集

> ⚠️ **重要说明：本仓库（GitHub）未包含任何图片数据文件**
>
> 由于图片数据总体积约 2GB，且 git 不适合托管二进制大文件，
> **本仓库仅上传了下载脚本（`tools/` 目录），未上传任何图片文件**。
> 所有图片均可通过下方脚本从原始来源重新下载获取，数据来源可溯、版权合规。

## 数据集清单

| 数据集 | 图片数 | 大小 | 来源 | 获取方式 |
|--------|--------|------|------|----------|
| Kaggle Chinese Traditional Clothing | 6,300 | 840MB | Roboflow/Kaggle | `tools/download_datasets.py` |
| Met Museum TEXMET Expanded | 2,500+ | 478MB | Metropolitan Museum (CC0) | `tools/download_public_data.py` |
| Wikimedia/Crawled | 334 | 480MB | Wikimedia Commons | `tools/crawl_images.py` |
| Met Museum Original | 100 | 118MB | Metropolitan Museum (CC0) | `tools/download_images.py` |
| **总计** | **~7,000** | **~2GB** | | |

## 图片数据获取方式（脚本重新下载）

```bash
# 1. 公开数据集（TEXMET 纺织品 + 中国传统女鞋，HuggingFace 源）
python tools/download_public_data.py

# 2. Kaggle 汉服检测数据集（需 kagglehub，首次运行需 Kaggle API 凭据）
python tools/download_datasets.py

# 3. Wikimedia Commons / MET 博物馆公开图像爬取
python tools/crawl_images.py

# 4. 批量下载指定图像列表
python tools/download_images.py
```

下载完成后图片存放于 `data/images/` 与 `data/downloads/`（已被 `.gitignore` 排除，
不会进入 git 仓库）。

## 数据目录说明

- `data/images/` — 下载的图片（文物照片、汉服参考图、纹样素材），**未上传 GitHub**
- `data/downloads/` — 外部数据集原始下载，**未上传 GitHub**
- `data/annotations/` — 标注数据（JSONL 文本，已上传）
- `data/dataset_index.json` — 28 条内置知识库索引（已上传，无需下载）

## 附注

- 之前文档提到的 HuggingFace 托管地址（`shenx/traditional-chinese-clothing`）
  尚未创建，当前以脚本重新下载为主。
- 数据来源与许可详见 `../data/README.md`。
