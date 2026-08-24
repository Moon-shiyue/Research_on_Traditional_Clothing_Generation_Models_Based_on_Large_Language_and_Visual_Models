# 传统服饰数据集

> ⚠️ **重要说明：本仓库（GitHub）未包含任何图片数据文件**
>
> 图片数据总体积约 2GB（`images/` 约 1GB + `downloads/` 约 800MB），
> 由于 git 不适合托管二进制大文件，**GitHub 上仅上传了下载/爬取脚本，
> 未上传任何图片文件**。所有图片均可通过下方脚本从原始来源重新下载。

## 📊 数据集总览

| 数据类别 | 条目数 | 标注方式 | 来源 |
|----------|--------|----------|------|
| **内置知识库（服装）** | 18 条 | 四级结构化标注 | 学术文献编码 |
| **内置知识库（纹样）** | 10 条 | 纹样特征标注 | 学术文献编码 |
| **洛阳刺绣数据集** | 260 件 | 原始标注 | 洛阳民俗博物馆 |
| **GarmentCodeData** | 115,000 条 | 3D+纸样 | ETH Zurich |
| **Hanfu-Bench** | 1,192 张 | 多模态 | 学术基准 |
| **CulTi** | 5,726 对 | 图文多模态 | ICDAR 2025 |
| **故宫数字文物库** | 10万+ 件 | 在线浏览 | 故宫博物院 |
| **苏州丝绸纹样库** | 10,000 个 | 纹样数据 | 苏州丝绸博物馆 |

## 📁 目录结构

```
data/
├── dataset_index.json          # 主数据集索引（28条已标注）
├── annotation_spec.md          # 标注规范文档
├── README.md                   # 本文档
├── images/                     # 图像数据
│   ├── relics/                 #  文物照片
│   │   └── wikimedia/          #    Wikimedia Commons 公开图像
│   ├── hanfu/                  #  汉服参考图
│   │   └── wikimedia/          #    Wikimedia Commons 公开图像
│   └── patterns/               #  纹样素材
├── texts/                      # 文本数据
│   ├── literature/             #  形制文献目录
│   ├── craft/                  #  工艺规范
│   └── culture/                #  文化背景
├── annotations/                # 标注数据
│   ├── images/
│   └── texts/
└── downloads/                  # 外部数据集下载
```

## 🔌 外部数据集获取方式

### 1. GarmentCodeData (ETH Zurich) — 强烈推荐！

**内容**: 115,000 个 3D 定制服装 + 缝纫纸样 (JSON/PLY/OBJ)
**用途**: 本项目核心参考数据集，提供标准化的纸样生成范例
**获取**: https://doi.org/10.3929/ethz-b-000673889
**许可**: 学术研究
**大小**: 约 50GB+（分批下载）

```bash
# 访问 ETH Research Collection 下载（约 50GB，分批）
# 或使用公开数据集工具脚本（TEXMET / 中国女鞋，见 tools/ 目录）:
pip install datasets huggingface_hub
python tools/download_public_data.py
```

### 2. Hanfu-Bench — 汉服多模态基准

**内容**: 1,192 张汉服图像 + 专家标注
**获取**: https://huggingface.co/datasets/lizhou21/hanfu-bench
**许可**: CC BY-NC-SA 4.0（仅学术，不可训练模型）
**安装**:
```bash
pip install datasets
python -c "from datasets import load_dataset; load_dataset('lizhou21/hanfu-bench')"
```

### 3. 洛阳民俗博物馆刺绣文物数据集 — 免费下载！

**内容**: 260 件（套）清中晚期至民国刺绣服饰高清图片
**获取**: https://geodoi.ac.cn/WebCn/doi.aspx?ID=1836
**DOI**: 10.3974/geodb.2021.07.03.V1
**大小**: 1.45 GB（4个压缩包）
**许可**: 免费开放（需标注来源）
**说明**: 含云肩(31件)、荷包(46件)、绣裙(24件)、肚兜(12件)等 17 个品类

### 4. CulTi — 丝绸纹样+敦煌壁画

**内容**: 5,726 组图像-文本对
**获取**: https://github.com/yyyjjy/CulTi
**许可**: 需签署数据使用协议
**步骤**: 1. 填写 Data Usage Agreement → 2. 邮件发送 → 3. 获取解密密码

### 5. 故宫博物院数字文物库

**内容**: 10万+ 件珍贵文物高清影像（含大量宫廷服饰）
**获取**: https://www.dpm.org.cn/explore/collections.html
**许可**: 在线浏览免费，商用需授权
**说明**: 支持颜色/纹饰/器型智能检索，支持超高清细节放大

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
