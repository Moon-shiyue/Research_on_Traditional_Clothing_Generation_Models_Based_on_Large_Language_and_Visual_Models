# 数据交付说明（Data Delivery）

> **交付方**：数据工程 + 传统服饰组件库 负责人（申新卓）
> **接收方**：模型微调 负责人
> **交付日期**：2026-09-17
> **数据集**：传统服饰设计数据集 v1.0

---

## 一、交付物清单

| # | 文件/目录 | 大小 | 说明 |
|---|-----------|------|------|
| 1 | `data/annotations/traditional_design_dataset.jsonl` | 2.4 MB | **源数据集**（2,140 条，含全部字段：说明/caption/配置/代码/纸样统计） |
| 2 | `data/annotations/README_traditional_design_dataset.md` | — | **数据卡**（构造方法、字段说明、使用方法、局限） |
| 3 | `data/annotations/training_formats/` | 49.7 MB | **微调格式数据**（4 种格式，train/val 已划分） |
| 4 | `data/annotations/training_formats/README.md` | — | 格式说明 + 训练示例（LLaMA-Factory / OpenAI） |
| 5 | `garmentcode_ext/` | ~120 KB | **组件代码 + 参数树**（用于验证/执行模型输出） |
| 6 | `garmentcode_ext/validate_dataset.py` | — | **数据自查脚本**（25 项检查） |
| 7 | `garmentcode_ext/evaluate.py` | — | **效果评测脚本**（5 维指标） |

---

## 二、数据概览

```
源数据:      2,140 条（参数组合）
组件覆盖:    12 个（领型4 / 袖型3 / 下裳2 / 配饰3）
朝代覆盖:    6 代（汉/魏晋/唐/宋/明/清）
展开样本:    train 15,448 条 | val 1,672 条
任务形式:    text2design / text2code / caption2design / design2text
划分:        按参数组合 id 分层（防泄露，train/val 无交集）
可执行性:    100%（每条都真实调用 GarmentCode assembly 验证过）
```

**数据来源**：程序化生成（不是人工标注、也不是从图像转换）——
用 pygarment 原生实现的 12 个传统服饰组件，枚举合法参数组合，
**真实生成纸样**后产出监督信号；非法组合由形制规则剔除（722 条）。

---

## 三、快速开始（3 步）

### 第 1 步：自查数据（1 分钟）

```bash
# 需要先准备 GarmentCode 环境（见第五节）
cd GarmentCode
python traditional_ext/validate_dataset.py --sample 30
# 期望输出：✅ 全部通过（25 项检查）— 数据集可交付
```

### 第 2 步：选格式开训

| 你的训练框架 | 用这个文件 | 格式名 |
|-------------|-----------|--------|
| LLaMA-Factory / Axolotl / FastChat | `sharegpt_train.json` | `sharegpt` |
| OpenAI 微调 API / vLLM | `openai_train.jsonl` | messages |
| text-generation-webui | `alpaca_train.json` | alpaca |
| 复现 Design2GarmentCode | `d2gc_caption2design_train.json` | 自定义 |

LLaMA-Factory 示例（`data/dataset_info.json`）：
```json
{
  "traditional_clothing": {
    "file_name": "sharegpt_train.json",
    "format": "sharegpt",
    "columns": {"messages": "conversations", "system": "system"}
  }
}
```

### 第 3 步：训练后评测（必做）

```bash
# ① 用 val 集推理，输出 JSONL：{"id": "...", "prediction": "模型输出文本"}
python your_inference.py --dataset d2gc_caption2design_val.json --out preds.jsonl

# ② 评测
python traditional_ext/evaluate.py \
    --predictions preds.jsonl \
    --gt data/traditional_instruct/training_formats/d2gc_caption2design_val.json \
    --report eval_report.json
```

---

## 四、评测指标（`evaluate.py` 输出）

| 指标 | 含义 | 说明 |
|------|------|------|
| ① JSON 合法率 | 输出能否解析为 JSON | 反映格式遵循能力 |
| ② 组件节点命中率 | 输出是否含正确的组件节点 | 反映任务理解 |
| ③ **可执行率** | 配置能否真实生成纸样 | ⭐ 核心指标（调用 GarmentCode 验证） |
| ④ **形制合规率** | 是否通过 23 条形制规则 | ⭐ 本项目的差异化指标 |
| ⑤ 完全匹配率 / 参数准确率 | 与标注答案的匹配度 | 反映数值精确性 |

**自测基线**（用标注答案当预测跑出来的上限）：
```
① 100%  ② 100%  ③ 100%  ④ 100%  ⑤ 100%
```
即：**如果模型输出完全正确，5 项都应 100%**。实测"故意破坏 20% JSON + 参数改错"时：
`① 79.9% / ③ 79.9% / ④ 71.8% / ⑤ 20.1%` — 指标能正确反映质量下降。

---

## 五、环境依赖（重要）

评测与验证需要 **GarmentCode 环境**（因为要真实执行纸样生成）：

```bash
# 1. 获取 GarmentCode
git clone https://github.com/maria-korosteleva/GarmentCode.git
cd GarmentCode
pip install -e .

# 2. 放入本项目的扩展模块
cp -r <项目>/traditional_clothing/garmentcode_ext ./traditional_ext
cp <项目>/traditional_clothing/garmentcode_ext/traditional.yaml ./assets/design_params/

# 3. 额外依赖
pip install svgpathtools svgwrite scipy psutil CairoSVG

# 4. 验证环境
python test_garmentcode.py          # 应输出 Success!
python traditional_ext/demo_aoqun.py  # 生成明代袄裙三件套纸样
```

> ⚠️ **cairo DLL 问题**：pygarment 自带 Windows 版 cairo 运行时，但只在特定时机写入 PATH。
> `traditional_ext/exporter.py` 已处理此问题；若 `import cairosvg` 报
> `no library called "cairo-2"`，请确认扩展模块已放入 GarmentCode 目录内。

**若无法搭建环境**：验证脚本可加 `--sample 0`，评测脚本可加 `--no-exec` 跳过执行类检查
（但会失去 ③④ 两个核心指标）。

---

## 六、必读注意事项

### 1. 输出为 JSON 字符串
模型需要学会输出合法 JSON。建议：
- 训练时加 JSON 校验（或格式奖励）
- 推理时用约束解码（outlines / lm-format-enforcer / vLLM guided decoding）

### 2. 配置是「片段」，不是完整成衣
`design` 字段只含该组件的参数节点（如 `mamian-skirt` + `traditional`）。
完整成衣需与 `traditional.yaml` 的其余节点合并：
```python
full = yaml.safe_load(open('traditional.yaml'))['design']
full.update(predicted_design)      # 覆盖预测的节点
```

### 3. ⚠️ 模型输出必须过形制校验
模型可能生成越界参数（如"明代立领 6cm"、"不存在的褶数"）。
**请务必接形制校验做后置过滤**：
```python
from validation.engine import ValidationEngine     # 项目的 23 条规则引擎
report = ValidationEngine().validate(garment)
if not report.passed:
    # 拒绝或让模型重生成
```
这也是本项目的核心差异化能力（Design2GarmentCode 通用方法没有形制约束）。

### 4. 数据划分已防泄露，勿自行重划
`train/val` 按**参数组合 id** 分层划分，确保同一组合的 3 种句式不跨 split。
若自行随机重划，会导致验证集"见过"对应配置、指标虚高。

### 5. 样本分布不均
交领 648 vs 褙子 40（配饰组件的形制约束更严，过滤掉大量组合）。
若某类组件效果差，可考虑：调 class weight、或对少样本组件做数据增广。

### 6. 语言多样性有限
说明文本由模板生成（3 种句式），不如 LLM 生成的多样。
若模型泛化差，可先做一轮**说明文本润色**（用 LLM 重写后再训）。

---

## 七、已知局限（诚实声明）

| # | 局限 | 影响 |
|---|------|------|
| 1 | 说明文本为模板生成 | 语言泛化能力可能受限 |
| 2 | 配饰组件有几何简化（云肩无独立领座、褙子单片前身、半臂连袖） | 纸样与真实制版有差异 |
| 3 | 未建模唐宋细节形制（钿钗礼衣、圆领袍襕等） | 覆盖不全 |
| 4 | 体型固定（`mean_female.yaml`） | 其他体型需重新归一化 |
| 5 | 形制约束来自项目规则（23 条），非文献原文 | 建议领域专家复核 |
| 6 | 未接图像输入（纯文本任务） | 图像引导生成需另做图-配置配对 |

---

## 八、支持与反馈

- **数据问题**（字段、格式、划分）：找数据负责人
- **环境问题**（GarmentCode 跑不通、cairo 报错）：见第五节，或参考
  `garmentcode_ext/README.md`
- **评测口径问题**（指标定义、如何解读）：见第四节

相关文档：
- 数据卡：`data/annotations/README_traditional_design_dataset.md`
- 格式说明：`data/annotations/training_formats/README.md`
- 组件与迁移指南：`garmentcode_ext/README.md`
