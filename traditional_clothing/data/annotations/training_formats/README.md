# 微调格式数据（Training Formats）

把 `traditional_design_dataset.jsonl`（2,140 条）转换为**主流训练框架可直接使用**的格式。

## 📁 文件清单

| 文件 | 格式 | 样本数 | 大小 | 适用框架 |
|------|------|--------|------|----------|
| `sharegpt_train.json` / `_val.json` | ShareGPT | 15,448 / 1,672 | 18.1 / 2.0 MB | **LLaMA-Factory**、FastChat、Axolotl |
| `openai_train.jsonl` / `_val.jsonl` | OpenAI messages | 15,448 / 1,672 | 15.8 / 1.7 MB | OpenAI 微调 API、兼容接口（vLLM 等） |
| `alpaca_train.json` / `_val.json` | Alpaca | 15,448 / 1,672 | 9.3 / 1.0 MB | LLaMA-Factory、Axolotl、text-generation-webui |
| `d2gc_caption2design_train.json` / `_val.json` | D2GC 对齐 | 1,931 / 209 | 1.5 / 0.2 MB | Design2GarmentCode 的 caption2yaml 链路 |
| `stats.json` | 统计 | — | — | — |

## 🔢 数据规模

```
源数据（参数组合）    2,140 条 × 12 组件 × 6 朝代
    ↓ 划分（按参数组合 id，防泄露）
train 1,931 组合   val 209 组合
    ↓ 展开（4 种任务形式 × 最多 3 种句式）
train 15,448 条   val 1,672 条
```

## 🎯 四种任务形式

| 任务 | 输入 | 输出 | 数量(train) | 用途 |
|------|------|------|------------|------|
| **text2design** | 中文制版说明 | 设计配置 JSON | 5,793 | ⭐ **主任务**：自然语言 → GarmentCode 配置 |
| **text2code** | 中文制版说明 | 完整可执行代码 | 5,793 | 生成含配置+调用的代码 |
| **caption2design** | 参数路径标签 | 设计配置 JSON | 1,931 | 与 D2GC 的 `caption2yaml` 严格对齐 |
| **design2text** | 设计配置 JSON | 中文制版说明 | 1,931 | 反向任务，增强形制理解 |

## 📖 格式示例

### ShareGPT（推荐 LLaMA-Factory 使用）
```json
{
  "conversations": [
    {"from": "human", "value": "明代马面裙，裙长及膝，马面宽约20cm，褶裥稀疏（褶量比1.4），中腰位，常服。"},
    {"from": "gpt", "value": "{\n  \"mamian-skirt\": {\n    \"length\": {\"v\": 0.55}, ..."}
  ],
  "system": "你是中国传统服饰制版助手，精通历代服饰形制...",
  "meta": {"id": "...", "task": "text2design", "component": "mamian-skirt", "dynasty": "Ming"}
}
```

### Alpaca
```json
{
  "instruction": "明代马面裙，裙长及膝，马面宽约20cm，...",
  "input": "",
  "output": "{\n  \"mamian-skirt\": {...}"
}
```

### OpenAI（JSONL）
```jsonl
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}], "meta": {...}}
```

### D2GC 对齐
```json
{
  "caption": ["traditional__dynasty__Ming", "mamian-skirt__mamian_width__narrow", ...],
  "design": {"mamian-skirt": {"length": {"v": 0.55}, ...}},
  "text": "明代马面裙，裙长及膝，马面宽约20cm，...",
  "id": "mamian-skirt_ming_0001"
}
```

## ⚠️ 划分防泄露（重要）

**同一参数组合的 3 种句式必须落在同一个 split**——否则验证集"见过"对应配置，指标虚高。

本脚本以**样本 id（= 一个参数组合）**为单位、**按组件分层**划分（`VAL_RATIO=0.10`, `SEED=42`），
并断言 train/val 的 id 集合无交集：

```
train: 1931 组合  |  val: 209 组合
校验无重叠: True
```

> 注意：这解决的是**数据划分泄露**。你原来的图像数据集（Chinese-Traditional-Clothing）
> 还有另一类泄露（Roboflow 增强版本跨 split，约 40 张原图），训练视觉模型时需另外处理。

## 🚀 使用示例

### LLaMA-Factory（推荐）
```yaml
# data/dataset_info.json 中注册
traditional_clothing:
  file_name: sharegpt_train.json
  format: sharegpt
  columns:
    messages: conversations
    system: system

# 训练
llamafactory-cli train \
  --model_name_or_path Qwen/Qwen2-VL-2B-Instruct \
  --dataset traditional_clothing \
  --template qwen2_vl \
  --finetuning_type lora \
  --lora_target all \
  --output_dir outputs/traditional_lora
```

### OpenAI 兼容接口
```bash
openai api fine_tuning.jobs.create -t openai_train.jsonl -m gpt-4o-mini
```

### 自定义训练（torch）
```python
import json
rows = json.load(open('sharegpt_train.json', encoding='utf-8'))
for r in rows:
    prompt = r['conversations'][0]['value']
    answer = r['conversations'][1]['value']
    # 按你的模板拼接：<|system|>...<|user|>{prompt}<|assistant|>{answer}
```

## 🔗 与 Design2GarmentCode 的关系

D2GC 的微调数据是「自然语言制版说明 ↔ GarmentCode 程序」（论文 §3.2.1 的 `D = {(Γ_cmt(f_i), f_i)}`）。
本目录的 **`d2gc_caption2design_*.json`** 可直接对应其 `caption2yaml` 链路；
其余格式则是**通用的指令微调格式**，可迁移到任意 LLaMA 系模型。

## 📊 统计（stats.json）

```json
{
  "source_samples": 2140,
  "train_combos": 1931, "val_combos": 209,
  "train_rows": 15448, "val_rows": 1672,
  "tasks": {"text2design": 5793, "text2code": 5793,
            "caption2design": 1931, "design2text": 1931},
  "by_component_train": {"cross-collar": 4860, "narrow-sleeve": 2250, ...},
  "by_dynasty_train": {"Ming": 4404, "Song": 3150, "Tang": 2826, ...},
  "val_ratio": 0.1, "seed": 42
}
```

## 🔄 重新生成

```bash
cd GarmentCode
python traditional_ext/build_dataset.py          # ① 重新生成 2140 条源数据
python traditional_ext/export_training_formats.py # ② 导出本目录的格式
```

## ⚠️ 使用前须知

1. **输出为 JSON 字符串**：模型需学会输出合法 JSON（建议训练时加入 JSON 校验奖励或约束解码）。
2. **配置为片段**：`design` 只含该组件的参数节点，完整成衣需合并 `traditional.yaml` 的其余节点。
3. **未清洗的真实运行风险**：模型输出的参数可能超出形制范围，**请接形制校验引擎**
   （`validation/` 的 23 条规则）做后置过滤。
4. **说明文本为模板生成**：语言多样性有限，如需更自然可先用 LLM 润色（见主数据卡"局限"节）。
