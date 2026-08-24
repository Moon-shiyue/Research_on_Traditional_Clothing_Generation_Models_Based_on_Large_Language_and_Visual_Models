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
    ├── data/                        # 传统服饰数据集（28 条标注 + 训练语料）
    ├── tools/                       # 数据采集 / 扩充 / 合成工具
    ├── tests/                       # 单元测试（91 项）
    ├── requirements.txt
    └── README.md                    # 模块详细文档
```

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
| 数据集 | 28 条四级结构化标注 + 518 条训练文本 + 660 条 DSL 数据 | ✅ 完成 |
| 单元测试 | 91 项（组件构建/规则命中/数据完整性） | ✅ 完成 |

## 📚 参考

- GarmentCode / Design2GarmentCode / GarmentCodeData（ETH Zurich）
- ChatHuman（3D 人体生成）
- 沈从文《中国古代服饰研究》等形制文献

## 📄 许可

数据来源：MET Open Access（CC0）、Wikimedia Commons、洛阳民俗博物馆（免费开放）、
学术文献知识编码。外部数据集使用请遵守各自许可。
