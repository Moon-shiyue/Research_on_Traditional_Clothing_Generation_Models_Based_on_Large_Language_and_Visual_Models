# 传统服饰参数化生成组件库

> 基于大语言模型与视觉模型的传统服饰生成模型研究 —— 数据工程 + 传统服饰组件库模块

本仓库实现了 **传统服饰领域知识的数字化**，是项目差异化的关键部分：

1. **传统服饰参数化组件库**（基于 GarmentCode 思想）：领型、袖型、下裳、配饰的
   参数化几何建模与 GarmentCode DSL 导出
2. **形制规则校验引擎**：将传统服饰的礼制规范、形制禁忌编码为可自动执行的
   校验规则，对生成结果进行文化合规性检查
3. **传统服饰数据集**：标注数据（28 条知识条目 + 518 条训练文本 + 660 条 DSL 数据）、
   图像收集与外部数据集获取工具

---

## 📦 目录结构

```
traditional_clothing/
├── garment_components/        # ⭐ 参数化组件库（核心交付件）
│   ├── base.py                #   基础类型：Point2D / Panel / SewingEdge / 部件基类
│   ├── curves.py              #   曲线原语：直线 / 贝塞尔 / 圆弧 / 云纹边
│   ├── collars/               #   领型：交领、圆领、立领、对襟
│   ├── sleeves/               #   袖型：广袖、窄袖、琵琶袖
│   ├── skirts/                #   下裳：马面裙 ⭐、襦裙
│   ├── accessories/           #   配饰：云肩、褙子、半臂
│   └── garments/              #   GarmentComposer 服装组合器
├── validation/                # 形制规则校验引擎（23 条规则）
│   ├── engine.py              #   ValidationEngine 校验引擎
│   └── rules/                 #   规则库：朝代/领/袖/裙/色彩/纹样/组合
├── data/                      # 数据集
│   ├── dataset_index.json     #   主数据集索引（28 条四级结构化标注）
│   ├── annotation_spec.md     #   标注规范文档
│   ├── annotations/           #   training_data.jsonl / dsl_training.jsonl
│   ├── texts/                 #   形制文献 / 工艺规范 / 文化背景目录
│   ├── images/                #   图像数据（文物/汉服/纹样，git 忽略，脚本可重下）
│   └── downloads/             #   外部数据集下载（git 忽略）
├── tools/                     # 数据工具脚本
│   ├── generate_synthetic_data.py   #   合成文本训练数据
│   ├── synthesize_dsl_data.py       #   合成 GarmentCode DSL 训练数据
│   ├── expand_dataset.py            #   基于知识条目扩充数据集
│   ├── crawl_images.py              #   爬取公开图像（Wikimedia/MET）
│   ├── download_images.py           #   批量下载图像
│   ├── download_datasets.py         #   下载外部数据集（Kaggle/Roboflow）
│   ├── download_public_data.py      #   下载公开数据集（HuggingFace）
│   └── data_scraper.py              #   多源数据抓取器
├── tests/                     # 单元测试（pytest，91 项）
│   ├── test_components.py     #   组件库测试
│   ├── test_validation.py     #   校验引擎测试
│   └── test_data.py           #   数据集完整性测试
├── requirements.txt           # 依赖清单
└── README.md                  # 本文档
```

---

## 🚀 快速开始

```bash
pip install -r requirements.txt
python -m pytest tests/ -v        # 运行全部测试（91 项）
```

### 1. 组合一套传统服饰

```python
from garment_components.base import Dynasty
from garment_components.garments import GarmentComposer

# 明代袄裙：立领 + 琵琶袖 + 马面裙
composer = (GarmentComposer("明代袄裙", Dynasty.MING)
            .add_collar("stand_collar")
            .add_sleeve("pipa_sleeve")
            .add_skirt("mamian_skirt"))

panels = composer.all_panels          # 全部裁片（含轮廓/缝边/褶线）
for p in panels:
    print(p.name, len(p.outline), "点", f"面积 {p.area:.0f} cm²")
```

### 2. 生成单个部件

```python
from garment_components.skirts import MamianSkirt, build_mamian_skirt

skirt = build_mamian_skirt(mamian_width=28, pleat_count=6, pleat_depth=4.5)
print(skirt.summary)                  # 参数摘要
print(skirt.to_garment_code())        # 导出 GarmentCode DSL
```

### 3. 文化合规性校验

```python
from garment_components.base import Dynasty
from garment_components.garments import GarmentComposer
from validation.engine import ValidationEngine

composer = (GarmentComposer("清代袍", Dynasty.QING)
            .add_collar("stand_collar")
            .add_sleeve("pipa_sleeve")     # ❌ 清代不应使用琵琶袖
            .add_skirt("mamian_skirt"))

report = ValidationEngine().validate(composer)
print("通过:", report.passed, "| 错误:", report.error_count,
      "| 警告:", report.warning_count)
for r in report.results:
    if not r.passed:
        print(f"  [{r.severity}] {r.rule_name}: {r.message}")
```

---

## ⭐ 核心交付件

### 1. 传统服饰参数化组件库

| 类别 | 组件 | 关键参数 |
|------|------|----------|
| 领型 | 交领（右衽） | 领宽、领深、交叉角、重叠量 |
| 领型 | 圆领 | 领围、前/后领深 |
| 领型 | 立领 | 领高（明 2-3cm / 清 4-6cm）、颈围 |
| 领型 | 对襟 | 襟宽、领深 |
| 袖型 | 广袖 | 袖长、袖口宽 > 袖根宽（汉唐） |
| 袖型 | 窄袖 | 肘部微弧贴合（历代通用） |
| 袖型 | 琵琶袖 ⭐ | 收口 < 根宽 < 膨起宽（**明代独有**） |
| 下裳 | 马面裙 ⭐ | 马面宽 ≥15cm、褶数偶数、褶深 < 马面宽/3 |
| 下裳 | 襦裙 | 裙长、腰围、腰位 |
| 配饰 | 云肩 | 层数、花瓣数、垂须 |
| 配饰 | 褙子 | 衣长、肩宽、开衩 |
| 配饰 | 半臂 | 袖长、衣长 |

每个部件均实现：
- `build_panels()` — 生成参数化裁片（轮廓 + 缝边 + 内部结构线）
- `to_garment_code()` — 导出 GarmentCode DSL
- `validate()` — 参数合理性自检
- `compatible_dynasties` — 形制溯源（朝代兼容性声明）

### 2. 形制规则校验引擎（23 条）

按类别覆盖：
- **朝代规则**（6 条）：琵琶袖仅明代可用、清代不出现琵琶袖、明代立领高度、
  唐代齐胸襦裙腰位、宋代褙子搭配、右衽原则
- **领型规则**（2 条）：立领高度上限、圆领前深 > 后深
- **袖型规则**（2 条）：广袖袖口 > 袖根、琵琶袖收口特征
- **下裳规则**（4 条）：马面宽 ≥15cm、褶数偶数、褶深比例、裙长范围
- **色彩规则**（3 条）：明黄皇帝专用、宋代淡雅、唐代艳色
- **纹样规则**（1 条）：五爪龙纹皇家专用
- **组合规则**（5 条）：明/唐/宋经典组合、完成度检查、礼服广袖

支持 `validate()` / `validate_component()` / `validate_combination()` 三种粒度，
规则执行异常自动降级为 error 报告，不中断整体校验。

### 3. 数据集

> ⚠️ **GitHub 仓库未包含图片文件，仅含标注数据与下载脚本。**

- **dataset_index.json**：28 条四级结构化标注（朝代-形制-部件-纹样），
  覆盖汉/魏晋/唐/宋/明/清六代，18 条服装条目 + 10 条纹样条目
- **training_data.jsonl**：518 条训练文本（知识库 + 图文多模态）
- **dsl_training.jsonl**：660 条 GarmentCode DSL 训练数据（含体型参数）
- 图像收集：MET 博物馆（CC0）、Wikimedia Commons、洛阳刺绣、Kaggle 汉服数据集
  约 2GB 图片**未上传 GitHub**，仅提供 `tools/` 下载脚本按需重新获取
  （详见 `data/README.md` 与 `datasets/README.md`）

---

## 🧪 测试

```bash
python -m pytest tests/ -v
```

覆盖：
- 全部 12 个组件：面板构建、DSL 导出、参数自检、朝代声明
- 组合器：明/唐/宋经典装束组合
- 校验引擎：朝代禁忌命中、部件规则、类别过滤、异常容错
- 数据集：索引一致性、标注字段完整性、DSL 数据标记覆盖

---

## 📚 参考

- GarmentCode：服装设计编程语言（ETH Zurich）
- Design2GarmentCode：服装设计大模型
- GarmentCodeData：115,000 组 3D 服装 + 纸样数据集
- ChatHuman：3D 人体生成模型
- 沈从文《中国古代服饰研究》等形制文献（见 `data/texts/literature/`）

## 📄 许可与致谢

数据来源：MET Open Access（CC0）、Wikimedia Commons、洛阳民俗博物馆（免费开放）、
学术文献知识编码。外部数据集使用请遵守各自许可（详见 `data/README.md`）。
