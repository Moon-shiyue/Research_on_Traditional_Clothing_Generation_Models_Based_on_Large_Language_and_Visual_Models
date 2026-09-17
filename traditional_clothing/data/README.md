# 传统服饰数据集

> ⚠️ **重要说明：本仓库（GitHub）未包含任何图片数据文件**
>
> 图像数据总体积约 820MB（6,300 张），由于 git 不适合托管二进制大文件，
> **GitHub 上仅上传了标注数据（JSON/JSONL）与下载脚本，未上传任何图片文件**。
> 图片可通过下方脚本从原始来源重新下载。

## 📊 当前实际使用的数据集

| 数据类别 | 规模 | 标注方式 | 来源 | 位置 |
|----------|------|----------|------|------|
| **Chinese-Traditional-Clothing Dataset** ⭐ | **6,300 张** / 24,562 标注框 | COCO 目标检测（8 类形制） | [Roboflow Universe](https://universe.roboflow.com/ctcdata/chinese-traditional-clothing-dataset)（v12, 2023） | `downloads/kaggle_chinese_clothing/` |
| **内置知识库（服装）** | 18 条 | 四级结构化标注 | 学术文献编码 | `dataset_index.json` |
| **内置知识库（纹样）** | 10 条 | 纹样特征标注 | 学术文献编码 | `dataset_index.json` |
| **训练文本数据** | 18 条 | 文本-标签配对 | 知识库编码 | `annotations/training_data.jsonl` |
| **DSL 训练数据** | 660 条 | 文本-GarmentCode 配对 | 脚本合成 | `annotations/dsl_training.jsonl` |

### 主力数据集详情

- **来源**：[Roboflow Universe — ctcdata/chinese-traditional-clothing-dataset](https://universe.roboflow.com/ctcdata/chinese-traditional-clothing-dataset)
- **版本**：v12（2023-05-02 导出），官方声明 6,300 张
- **8 类形制标注**：AoQun（袄裙）、DaoPao（道袍）、Pao（袍）、QuJu（曲裾）、
  RuQun（襦裙）、ZhiDuo（直裰）、ZhiJu（直裾）、ZhuZiShenYi（朱子深衣）
- **许可**：⚠️ Roboflow 标注为 `License: undefined`（许可未明确），
  学术研究使用需注明来源，商用/再分发请先联系数据集作者确认
- **注意**：6,300 张中包含 Roboflow 自动数据增强（约 4.1 倍），
  独立原图约 1,561 张；训练时建议按原图名重新划分 split 以避免数据泄露

## 📁 目录结构

```
data/
├── dataset_index.json          # 知识库索引（28 条四级结构化标注）
├── annotation_spec.md          # 标注规范文档
├── README.md                   # 本文档
├── texts/                      # 文本数据
│   ├── literature/             #   形制文献目录
│   ├── craft/                  #   工艺规范
│   └── culture/                #   文化背景
├── annotations/                # 标注与训练数据
│   ├── training_data.jsonl     #   18 条知识库训练文本
│   └── dsl_training.jsonl      #   660 条 DSL 配对数据
└── downloads/                  # 外部数据集下载（git 忽略）
    └── kaggle_chinese_clothing/  #   ⭐ 主力数据集（6,300 张 + COCO 标注）
```

## 🔌 可选外部资源（当前**未**使用）

> 以下数据集在项目调研阶段登记备选，当前**未下载、未使用**，
> 仅作为后续扩展时的候选来源。若需使用请自行确认许可条款。

### 1. GarmentCodeData (ETH Zurich)

**内容**: 115,000 个 3D 定制服装 + 缝纫纸样 (JSON/PLY/OBJ)
**用途**: 本项目核心参考数据集，提供标准化的纸样生成范例
**获取**: https://doi.org/10.3929/ethz-b-000673889
**许可**: 学术研究
**大小**: 约 50GB+（分批下载）

### 2. Hanfu-Bench — 汉服多模态基准

**内容**: 1,192 张汉服图像 + 专家标注
**获取**: https://huggingface.co/datasets/lizhou21/hanfu-bench
**许可**: CC BY-NC-SA 4.0（仅学术，不可训练模型）

### 3. 洛阳民俗博物馆刺绣文物数据集

**内容**: 260 件（套）清中晚期至民国刺绣服饰高清图片
**获取**: https://geodoi.ac.cn/WebCn/doi.aspx?ID=1836
**DOI**: 10.3974/geodb.2021.07.03.V1
**许可**: 免费开放（需标注来源）

### 4. CulTi — 丝绸纹样+敦煌壁画

**内容**: 5,726 组图像-文本对
**获取**: https://github.com/yyyjjy/CulTi
**许可**: 需签署数据使用协议

### 5. 故宫博物院数字文物库 / 苏州丝绸纹样库

**内容**: 10万+ 件文物影像 / 10,000+ 个丝绸纹样
**获取**: https://www.dpm.org.cn/explore/collections.html ｜ 苏州大数据交易所
**许可**: 在线浏览免费，商用需授权

### 6. 其他可参考公开数据集（调研发现）

| 数据集 | 规模 | 任务 | 备注 |
|--------|------|------|------|
| 中国民族服饰检测数据集 | 2,474 张 | YOLO/VOC 检测 | 涵盖 55 个少数民族 + 汉族 |
| 中国少数民族服饰分类数据集 | 10,320 张 / 56 类 | 图像分类 | 含 miaozu(230)、hanzu(240) |
| TEXMET | 18,644 张 | 纺织品图像 | CC0，Met Museum，最宽松 |
| Met Museum Open Access | 10万+ 件 | 文物图像 | CC0 |

> 备注：`tools/download_public_data.py`、`tools/crawl_images.py` 等脚本
> 仍保留，可随时用于获取上述任一数据集。

### 6. 苏州丝绸纹样数据库

**内容**: 10,000+ 个高质量丝绸原生纹样
**获取**: 苏州大数据交易所
**说明**: 江苏省首款上架交易的丝绸纹样数据产品

## 📝 内置知识库说明

由于部分外部数据集需要申请授权或网络条件限制，
本模块内置了基于学术文献编码的 **28 条传统服饰知识条目**：

- **18 条服装条目**: 覆盖汉/魏晋/唐/宋/明/清六代
- **10 条纹样条目**: 缠枝莲/海水江崖/宝相花/团凤/落花流水/如意云/四合如意/团花/联珠/折枝花

每条包含：朝代、形制类型、部件标注（领/袖/裙）、纹样、色彩、面料、
礼仪等级、身份等级、来源出处、详细描述。

## 🚀 快速开始

```python
# 查看当前数据集
import json
with open('data/dataset_index.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(f"总条目: {data['total_count']}")
print(f"朝代分布: {data['statistics']['by_dynasty']}")

# 使用标注规范添加新数据（见 annotation_spec.md）
# 标注写入 data/annotations/ 下的 JSONL 文件：
#   - training_data.jsonl  文本训练数据（知识库 + 图文条目）
#   - dsl_training.jsonl   GarmentCode DSL 训练数据
# 扩充数据的自动化脚本：
python tools/generate_synthetic_data.py     # 合成文本训练数据
python tools/synthesize_dsl_data.py         # 合成 DSL 训练数据
python tools/expand_dataset.py              # 基于知识条目扩充数据集
```

## 📮 数据贡献

如需贡献数据，请确保：
1. 图像/文本来源明确，版权合规
2. 按照 `annotation_spec.md` 中的四级标注规范进行标注
3. 提交到对应的数据子目录
