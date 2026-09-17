# 基于大语言模型与视觉模型的传统服饰生成模型研究

河海大学大学生创新训练计划项目 —— 融合大语言模型（LLM）与视觉模型（VLM），
实现传统服饰的参数化生成与形制合规校验。

## 📂 仓库结构

```
├── README.md                        # 本文档（项目总览）
└── traditional_clothing/            # 核心交付模块
    ├── garment_components/          # ⭐ 传统服饰参数化组件库（GarmentCode 思想）
    │   ├── collars/                 #   领型：交领、圆领、立领、对襟
    │   ├── sleeves/                 #   袖型：广袖、窄袖、琵琶袖（明代独有）
    │   ├── skirts/                  #   下裳：马面裙 ⭐、襦裙
    │   ├── accessories/             #   配饰：云肩、褙子、半臂
    │   └── garments/                #   GarmentComposer 服装组合器
    ├── validation/                  # 形制规则校验引擎（23 条文化合规规则）
    ├── data/                        # 知识库（28 条）+ 训练语料（18/660 条）
    ├── datasets/                    # 主力数据集文档 + COCO 形制标注（24,562 框）
    ├── tools/                       # 数据采集 / 扩充 / 合成工具
    ├── tests/                       # 单元测试（91 项）
    ├── requirements.txt
    └── README.md                    # 模块详细文档
```

## 🎯 技术路线

本项目参考 **GarmentCode**（ETH Zurich, SIGGRAPH Asia 2023）与
**Design2GarmentCode**（CVPR 2025）的思路：

```
设计输入（文字/图片）→ 多模态大模型 → GarmentCode 程序代码 → 参数化纸样/3D 服装
                          ↑ 微调                     ↑ 形制规则校验（本项目）
```

1. **参数化纸样表示**：服装以"程序代码"而非像素表示，可直接生成结构正确的纸样
   （参考 GarmentCode 的 DSL 与 PyGarment 引擎）
2. **大模型生成代码**：微调多模态大模型，把"明代立领琵琶袖马面裙"这类设计概念
   转换为可执行的服装程序（参考 Design2GarmentCode 的双 Agent 架构）
3. **传统服饰领域适配**：构建传统服饰的部件库、配对数据集与形制校验规则，
   让通用方法能正确生成传统服饰

## 🎯 项目目标

1. **知识数字化**：将传统服饰的形制知识（朝代、部件、纹样、礼制）编码为
   结构化数据与参数化几何模型
2. **组件化生成**：基于 GarmentCode 思想构建传统服饰部件库，
   支持"组合 → 裁片 → DSL"全流程
3. **文化合规校验**：将礼制规范、形制禁忌编码为自动校验规则，
   保证生成结果的形制准确性

## 🚀 快速开始

```bash
cd traditional_clothing
pip install -r requirements.txt
python -m pytest tests/ -v          # 运行 91 项单元测试
```

```python
from garment_components.base import Dynasty
from garment_components.garments import GarmentComposer
from validation.engine import ValidationEngine

# 生成明代袄裙：立领 + 琵琶袖 + 马面裙
composer = (GarmentComposer("明代袄裙", Dynasty.MING)
            .add_collar("stand_collar")
            .add_sleeve("pipa_sleeve")
            .add_skirt("mamian_skirt"))

# 文化合规校验
report = ValidationEngine().validate(composer)
print("通过:", report.passed)
```

详细用法见 [`traditional_clothing/README.md`](traditional_clothing/README.md)。

## ⭐ 核心交付件

| 模块 | 内容 | 状态 |
|------|------|------|
| 参数化组件库 | 12 个传统服饰部件（领/袖/裙/配饰） | ✅ 完成 |
| 形制校验引擎 | 23 条文化合规规则（朝代/部件/色彩/纹样/组合） | ✅ 完成 |
| 数据集 | **6,300 张图像 + 24,562 个形制标注框** + 28 条知识库 + 18 条训练文本 + 660 条 DSL 数据 | ✅ 完成 |
| 单元测试 | 91 项（组件构建/规则命中/数据完整性） | ✅ 完成 |

> ⚠️ **关于图片数据**：图像数据集为 **Chinese-Traditional-Clothing Dataset**（6,300 张，
> 约 820MB，Roboflow v12，含 8 类形制 COCO 标注），**未上传到 GitHub**——
> 仅上传了标注数据与 `traditional_clothing/tools/` 下的下载脚本。
> 需要图片时运行以下命令从原始来源重新获取：
>
> ```bash
> pip install kagglehub
> python tools/download_main_dataset.py
> ```
>
> 详见 [`traditional_clothing/datasets/README.md`](traditional_clothing/datasets/README.md)。

## 📚 参考

- [GarmentCode](https://github.com/maria-korosteleva/GarmentCode)：参数化纸样编程框架
  （ETH Zurich, SIGGRAPH Asia 2023）
- [Design2GarmentCode](https://style3d.github.io/design2garmentcode/)：多模态大模型驱动的
  服装程序生成（CVPR 2025）
- GarmentCodeData：115,000 组 3D 服装 + 纸样数据集（ECCV 2024）
- ChatHuman（3D 人体生成）
- 沈从文《中国古代服饰研究》等形制文献

## 📄 许可

**图像数据**：[Chinese-Traditional-Clothing Dataset](https://universe.roboflow.com/ctcdata/chinese-traditional-clothing-dataset)
（Roboflow Universe / CTCDATA，v12）——Roboflow 标注许可为 `undefined`，
学术使用请注明来源，商用/再分发前请联系作者确认。

**文本与知识数据**：基于学术文献与博物馆公开信息编码，详见 `traditional_clothing/data/`。
