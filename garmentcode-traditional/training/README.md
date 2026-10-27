# 传统服饰模型训练工具 v1

当前目标：完整中文单组件要求 → GarmentCode 传统参数 JSON。使用本地 Qwen2-VL-2B-Instruct 基座和新的语言 LoRA。旧回归权重、原始数据和前后端代码均保留。

本目录已经完成本地数据和训练机制验证，**尚未对完整基座微调，也没有图像训练结果**。

## 数据与验证结果

- 原始 2,140 条配置，418 个不同几何组合；所有朝代、场合和句式按几何组合一起划分。
- 清理后 train/val/test 为 3,416 / 432 / 432 条文本任务，对应 334 / 42 / 42 个几何组合。
- 排除 2,140 条缺少明确场合的句式；原文件未改。原因见 `data/training_v1/cleaning_report.json`。
- 跨集合几何、输入文本、源 ID 无重叠；验证与测试中的参数值都在训练中出现，因此主要测试未见组合。
- 本地 tokenizer 测得完整样本最长 223 token，答案最长 69 token。输入和 padding 的标签为 -100，不参与答案损失；超长样本直接报错，禁止截断答案。
- 初始本地 11 项测试通过；2026-10-01 增补 CUDA 生成精度与适配器张量审计测试（共 13 项）。极小的原生 Qwen2-VL 验证语言 LoRA 获得梯度、基座冻结及保存重载一致性；极小模型不代表正式模型效果或显存需求。
- **规则基线在现有验证集配置匹配率为 100%**。模板任务很容易，不能用它单独证明模型理解真实描述或图像。需要追加经人工核验的自然表达和图像评测。

本地详细记录：`docs/training-preflight-v1.json`、`runs/baselines-v1/rule-val.metrics.json`。该验证使用 `d2g` 环境：Python 3.9.19 / torch 2.4.0+cu121 / transformers 4.46.2 / peft 0.13.2。服务器依赖及 CUDA 环境尚待实测。

## 本地命令

从项目主目录运行。PowerShell 使用已有环境，例如：

```powershell
& 'C:\Users\huang\miniconda3\envs\d2g\python.exe' -m training.prepare_data
& 'C:\Users\huang\miniconda3\envs\d2g\python.exe' -m training.train --preflight --report docs/training-preflight-v1.json
& 'C:\Users\huang\miniconda3\envs\d2g\python.exe' -m unittest training.test_pipeline -v
```

首次部署需要同步 `training/`、`data/training_v1/` 和相关文档到服务器已有主项目，核对源数据、传统模板、组件源码和本地基座文件。**不要重传或覆盖旧权重，不要用删除式目录同步。** `prepare_data` 可确定性重建 v1 文件；训练前会验证数据及 schema 校验和。

本次已打包到 `artifacts/training_bundle_v1.zip`，包含训练工具、新数据和文档，不包含基座、旧权重、API 配置或缓存。包中的 `training/reference_files.json` 用于核对服务器上的参考代码和参数文件，不自动覆盖这些文件。

2026-10-01 修复：`write_json` 显式使用 CRLF，以保持最初在 Windows 创建的 v1 JSON 文件字节和校验和。JSONL 继续使用 LF。原保存函数依赖操作系统默认换行，导致服务器重新生成 `schema.json` 时与冻结文件的哈希不同；本次修复保留全部冻结数据，不重新划分。

同日修复：训练设置 `tf32=True` 会修改 CUDA 全局精度开关，原独立推理没有设为一致状态。生成函数现在显式统一 TF32，并在结束后恢复调用方状态；预测元数据记录这一设置。现有 30 步试训的 24 条预测中有 8 条在原独立推理下变化，服务器须运行下述审计才能确认具体原因，不能仅凭变化断言权重损坏。

```bash
python -m training.audit_reload
```

审计逐张量比较最终适配器与选中 checkpoint，再用同一适配器分别关闭、开启 TF32，在原 24 个 ID 上生成并对比。结果写入新的 `runs/reload-audit-v1/`。若该目录已存在，用 `--output-dir` 指定新目录。不会覆盖原始预测或权重。必须查看 `adapter_weights.tensor_values_identical` 及 `tf32_on.identical_predictions`，只有权重一致且 TF32 开启时恢复全部原始输出，才支持精度开关是本轮差异原因的判断。

## 服务器运行顺序

确认服务器已经开启并选用交接文档中的 Python 环境。从 `/root/autodl-tmp/garmentcode-traditional` 运行：

```bash
python -m training.train --preflight --report docs/server-training-preflight-v1.json
python -m unittest training.test_pipeline -v
python -m training.train --smoke
```

默认 smoke 在 `runs/traditional-json-lora-v1-smoke`，使用均衡抽取的 24 条训练记录与 24 条验证记录，30 次优化更新。查看 `gradient_check.json`、损失日志、验证原始预测以及 `run_manifest.json`。这次短程试跑用于检查完整基座的训练/生成/保存链路；若要验证小样本过拟合，可在训练集合内增加步数，不能把 smoke 当作泛化结果。

试跑后的适配器重载检查：

```bash
python -m training.infer --adapter runs/traditional-json-lora-v1-smoke --split val --ids-from runs/traditional-json-lora-v1-smoke/val-step-30.jsonl --output runs/traditional-json-lora-v1-smoke/reload-val.jsonl
python -m training.verify_reload --before runs/traditional-json-lora-v1-smoke/val-step-30.jsonl --after runs/traditional-json-lora-v1-smoke/reload-val.jsonl
```

`--limit` 仅用于试跑。完整评测会把未预测的记录计为缺失，不能把局部预测的分数当作完整验证成绩。

完整试跑验证通过后，先跑未微调基座验证集，再正式训练：

```bash
python -m training.infer --split val --output runs/baselines-v1/base-val.jsonl
python -m training.evaluate --split val --predictions runs/baselines-v1/base-val.jsonl --report runs/baselines-v1/base-val.metrics.json --execute
python -m training.train
python -m training.infer --adapter runs/traditional-json-lora-v1 --split val --output runs/traditional-json-lora-v1/val.jsonl
python -m training.evaluate --split val --predictions runs/traditional-json-lora-v1/val.jsonl --report runs/traditional-json-lora-v1/val.metrics.json --execute
```

默认 BF16、语言 q/k/v/o LoRA rank 16、学习率 5e-5、batch 1、梯度累积 16、3 epoch。每轮对完整验证集生成 JSON，按**各组件宏平均的完整配置匹配率**选择最佳 checkpoint，并在训练结束导出该适配器。测试集不进入训练、早停或选模。

不覆盖非空输出目录。新实验用 `--output-dir runs/你的实验名`；中断恢复用 `--resume runs/实验名/checkpoint-步数`，须沿用相同配置与数据。checkpoint 和最终适配器均保存安全张量；恢复文件包含优化器状态，只恢复自己生成的可信 checkpoint。

方案和提示词锁定后再运行独立测试。基座、规则与微调模型使用同一冻结测试集和评分器，例如：

```bash
python -m training.baseline --split test --output runs/baselines-v1/rule-test.jsonl
python -m training.infer --split test --output runs/baselines-v1/base-test.jsonl
python -m training.infer --adapter runs/traditional-json-lora-v1 --split test --output runs/traditional-json-lora-v1/test.jsonl
python -m training.evaluate --split test --predictions runs/traditional-json-lora-v1/test.jsonl --report runs/traditional-json-lora-v1/test.metrics.json --execute
```

另外两种基线也分别用 `training.evaluate --split test` 评分。推理使用贪心生成，固定提示词，默认最大生成长度 256；记录是否触及上限。预测文件已存在时会拒绝覆盖。

## 评测含义与边界

- 原始输出先严格解析和校验，拒绝重复 JSON 键、非有限数值、未知组件/字段、缺少字段和错误类型。仅容忍完整 Markdown JSON 代码块，不自动修答案。
- 完整匹配必须原始字段全部正确且 schema 合法。字段/数值/文化上下文分别报告；MAE 按字段报告并附实际预测覆盖数，漏字段不会按零误差处理。
- 数据清理和评测复用同一套形制规则，包括清代低立领反例。规则来自项目约定，文化真实性仍需有来源的资料及专家核验。
- 组件执行仅调用白名单类。分别报告非空裁片、几何数值有限性、运行时警告。能够组装不代表缝合完整、无自交、可制造或三维合体。已记录的马面裙和襦裙缝合问题仍待修复。
- 现有主要是离散参数组合，不能据此承诺任意尺寸、任意传统服饰或整套服装。

## 全面训练路线

1. **文本配置**：跑通上述基线、试跑、正式训练、冻结测试；补充人工核验的自然表达、信息缺失和超出支持范围的请求。缺少尺寸/场合时应澄清或明确标记默认来源。
2. **图像识别**：先用原生基座建立视觉基线，再收集真实图像与可见组件/领袖特征标注。记录来源、使用权限、衣服实体 ID、视角及遮挡，按衣服实体而非照片随机划分。先测试识别已标注的组件和可见属性；只凭照片无法确定的朝代、场合或尺寸应允许“未知”。
3. **图文配置生成**：引入有依据的图像—纸样配置配对数据，用图片识别结果和用户明确尺寸共同生成配置。只增加识别标注时，不能声称已经学会图片到精确纸样参数。原生 processor 处理图像、视觉输入必须真正参与训练；为文本与图像任务分别报告指标及混合训练是否损害文本效果。
4. **完整服装与接入**：领、袖、衣身和裙装组合需整套配置及正确缝合关系监督，先修复纸样结构，再评估三维拟合。前后端接入独立的 JSON 配置入口；本工具暂未修改现有 API。

图像标注草稿结构见 `training/image_annotation.example.json`，其中示例为待填模板，不是可用于训练的实际标注。当前没有确认可用的配对图像数据，因此第二阶段尚不能直接启动图像微调。
