# 传统服饰设计数据集（Traditional Design Instruction Dataset）

> 按 **Design2GarmentCode**（CVPR 2025, arXiv:2412.08603）§3.2.1 **Program Learning** 方法构建的
> 传统服饰领域微调数据集。

## 📐 构造方法（对应论文）

论文原文的做法：

> We start by providing the DSL-GA with **existing GarmentCode programs ℱ**, and instructing it to
> **comment on the functions with detailed pattern-drafting instructions**. After **manually
> validating the comments**, we get a dataset D pairing natural language instructions with
> GarmentCode implementations: **D = {( Γ_cmt(f_i), f_i ) | f_i ∈ ℱ }**

即：**已有程序代码 + 配套自然语言制版说明** 构成配对数据，教模型 DSL 语法。

本数据集的对应实现：

```
① 用 pygarment 原生 API 实现传统服饰组件（马面裙/琵琶袖/立领）
        ↓
② 枚举合法参数组合（形制约束过滤）
        ↓
③ 每组参数【真实调用组件生成纸样】—— 保证可执行性
        ↓
④ 生成监督目标：(自然语言制版说明, caption, 设计配置, 目标代码)
        ↓
⑤ 形制规则二次过滤（明代立领超高、琵琶袖尺寸倒置等一律剔除）
```

**关键差异**：论文用 LLM 给代码写注释（Γ_cmt）后人工校验；本数据集用
**形制短语模板 + 真实几何参数**生成说明，并通过**实际执行 GarmentCode** 验证每条样本可运行。

## 📊 数据统计

| 项目 | 数值 |
|------|------|
| **有效样本** | **414 条** |
| 被形制规则过滤 | 72 条（如"袖口宽 = 袖根宽"违反 袖口 < 袖根 < 膨起） |
| 组件分布 | 马面裙 216 / 琵琶袖 144 / 立领 54 |
| 朝代分布 | 明 288 / 清 126 |
| 每条样本句式 | 3 种（正式 / 指令式 / 口语式） |
| 可执行性 | **100%**（每条都真实执行过 `assembly()` 生成纸样） |

## 📁 文件

```
traditional_instruct/
├── traditional_design_dataset.jsonl   # 主数据（414 条）
├── stats.json                          # 统计报告
└── README.md                           # 本文档（数据卡）
```

## 🔖 字段说明

```jsonc
{
  "id": "mamian-skirt_ming_0001",
  "component": "mamian-skirt",              // 组件标识
  "component_class": "MamianSkirt",         // pygarment 类名
  "dynasty": "Ming",                        // 朝代
  "occasion": "Changfu",                    // 场合

  // ① 自然语言制版说明（模拟 Γ_cmt，3 种句式）
  "instructions_cn": [
    "明代马面裙，裙长及膝，马面宽约20cm，褶裥稀疏（褶量比1.4），中腰位，常服。",
    "请设计一条明代常服马面裙，要求：裙长及膝，马面宽约20cm，...",
    "我想要一条明代风格的马面裙，裙长及膝，马面宽约20cm，..."
  ],

  // ② D2GC 兼容 caption（参数路径标签，可被 caption2design 解析）
  "caption": [
    "traditional__dynasty__Ming",
    "mamian-skirt__mamian_width__narrow",
    "mamian-skirt__pleat_ruffle__light", "..."
  ],

  // ③ 设计配置（可执行，喂给组件即得纸样）
  "design": {
    "mamian-skirt": {"length": {"v": 0.55}, "mamian_width": {"v": 20.0}, ...},
    "traditional": {"dynasty": {"v": "Ming"}, "occasion": {"v": "Changfu"}}
  },

  // ④ 目标代码
  "target_code": "MamianSkirt(body, design).assembly()",

  // ⑤ 可验证的纸样统计
  "pattern": {"panels": 5, "panel_names": ["..."], "area_cm2": 5249.7},

  "meta": {
    "source": "procedural_generation",
    "verified": true,                        // 已真实执行 GarmentCode
    "generator": "traditional_ext/build_dataset.py",
    "created_at": "2026-09-17"
  }
}
```

## 🔧 使用方法

### 方式 1：指令微调（instruction → 配置/代码）

```python
# 输入：instructions_cn[i]
# 输出：design 配置 或 target_code
{"instruction": row["instructions_cn"][0],
 "output": json.dumps(row["design"], ensure_ascii=False)}
```

### 方式 2：DSL 语法对齐（论文方法）

```python
# 输入：制版说明
# 输出：GarmentCode 程序/配置
# 直接使用 instructions_cn → design 配对
```

### 方式 3：caption 校验（复用 D2GC 的 caption2yaml）

```python
from traditional_ext.params import caption2design
design = load_design()
design, applied = caption2design(row["caption"], design)
# 与 row["design"] 一致 → 说明 caption 与配置严格对应
```

### 方式 4：纸样生成（验证/可视化）

```python
from traditional_ext.mamian_skirt import MamianSkirt
skirt = MamianSkirt(body, row["design"])
pattern = skirt.assembly()          # 直接得到 specification.json
```

## ⚠️ 局限与注意事项

1. **说明文本为模板生成**，不如 LLM 生成的多样（论文用 LLM 写注释 + 人工校验）。
   如需更自然的表述，可用 `enrich_with_llm` 思路：把 `target_code`/`design` 交给 LLM 重写说明再人工校对。
2. **仅覆盖 3 个组件**（马面裙/琵琶袖/立领），补齐 12 个组件后可扩至约 1,500 条。
3. **体型固定**：全部基于 `mean_female.yaml`（与论文一致："we use a standard body model throughout"）。
4. **朝代覆盖偏窄**：目前只有明/清（因这 3 个组件的形制归属），汉/唐/宋需补组件后扩展。
5. **形制约束来自项目规则**（23 条校验规则），非历史文献原文，建议领域专家复核。

## 📚 引用

- Design2GarmentCode, CVPR 2025 — `arXiv:2412.08603`（数据构造方法来源）
- GarmentCode, SIGGRAPH Asia 2023 — 参数化纸样 DSL 与 pygarment 引擎
