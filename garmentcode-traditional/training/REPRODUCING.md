# 已完成的 v1 训练与复现

仓库提供**实际训练好的LoRA权重**、冻结数据、原始预测、评分结果、训练清单和复现工具。训练任务是「完整中文单组件描述 → 传统服饰参数JSON」，涉及12类组件；不是图像微调结果，也不是演示软件22类/209搭配的识图准确率。

## 结果与材料

| 432条冻结测试集 | 完整配置匹配率 | 字段准确率 |
| --- | --- | --- |
| 未微调 Qwen2-VL-2B-Instruct | 0% | 0% |
| 规则基线 | 100% | 100% |
| 本项目LoRA | 99.5370%（430/432） | 99.8344% |

LoRA组件宏平均配置匹配率为97.9167%，运行无警告率为90.2778%。模板任务中规则基线更好，不能据此宣称模型优于规则或能处理任意图片。训练/验证/测试3416/432/432条，对应334/42/42个几何组；组、文本及源ID不跨集合重叠，测试参数值在训练中出现过。

训练639步，按验证集宏平均配置匹配率选择 **checkpoint-213**（验证集100%）。发布的最终适配器即该最佳checkpoint，原服务器重载后432条验证预测全部一致。权重SHA256：

```text
4f9956463a1209ec485ae4cf96fb49eebef93128e49fe7d53d49620767e80209
```

发布材料在[`../models/traditional-json-lora-v1/`](../models/traditional-json-lora-v1/)。原manifest及adapter_config保留服务器历史路径供审计，命令显式加载本地基座与适配器，不依赖那些私人路径。

## 1. 创建独立实验目录

克隆整个仓库，从仓库根目录运行；此步只需Python标准库：

```bash
cd garmentcode-traditional
python -m training.reproduce verify-release
python -m training.reproduce prepare
cd ../reproduction-v1
```

默认新建仓库根目录下`reproduction-v1/`，拒绝覆盖已有目录；重跑可用`prepare --output 另一个新目录`。准备过程恢复训练时三份几何源码快照，并校验13份参考文件、冻结数据和权重。**当前演示软件的几何改进不会被替换**。后续预检、训练和评估均在这个独立目录运行，避免新旧几何代码混用。

## 2. 环境和基座

建议使用与原服务器一致的Linux、Python3.12.3、RTX4090（24GB）及独立虚拟环境。完整模型推理/训练需要支持BF16的CUDA GPU。文件核验或重评存档预测不需要GPU。原服务器记录了核心依赖，传递依赖和完整系统环境未全部冻结，因此不承诺任意硬件上重训逐位相同。

```bash
python -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r training/requirements-training.txt
python -m training.reproduce download-base
python -m training.reproduce verify-base
```

CairoSVG还需要系统Cairo库；Ubuntu可安装`libcairo2`。训练和CPU演示应使用不同环境，避免PyYAML版本约束冲突。

下载约4.42GB两个官方分片，固定来源为[Qwen/Qwen2-VL-2B-Instruct指定版本](https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct/tree/895c3a49bc3fa70a340399125c650a463535e71c)。两个分片的SHA256已与本机训练基座核对一致。分词器及模型/生成配置使用仓库附带的训练时原文件，避免上游新配置影响结果。下载失败可重跑，未完成分片重新下载，已完成且正确的分片保留。如果已有同一基座，可复制并校验，跳过网络：

```bash
python -m training.reproduce download-base --source /path/to/Qwen2-VL-2B-Instruct
```

无需API密钥或作者登录资料。请预留基座与训练checkpoint的存储空间。

## 3. 重新运行已训练模型

这些命令实际执行GPU推理，保存新预测；文件已存在时拒绝覆盖，重复实验请更改输出目录：

```bash
python -m training.train --preflight --report runs/reproduce/preflight.json
python -m unittest training.test_pipeline -v
python -m training.infer --adapter models/traditional-json-lora-v1 --split val --output runs/reproduce/val.jsonl
python -m training.verify_reload --before models/traditional-json-lora-v1/val-step-213.jsonl --after runs/reproduce/val.jsonl
python -m training.infer --adapter models/traditional-json-lora-v1 --split test --output runs/reproduce/test.jsonl
python -m training.evaluate --split test --predictions runs/reproduce/test.jsonl --report runs/reproduce/test.metrics.json --execute
```

参考目标：验证集432/432预测一致，测试集430/432完整配置匹配。生成固定贪心、batch1、BF16、SDPA与TF32开启；此前未统一TF32时确实发生过重载差异。硬件或依赖变化可能影响输出，应记录差异排查，不应修改测试答案或评分规则凑分。

## 4. CPU重评存档预测

安装几何依赖后可不下载基座，重算已有预测的指标。**这只是评估代码和存档审计，不是重新推理**：

```bash
python -m training.evaluate --split test --predictions models/traditional-json-lora-v1/test.jsonl --report runs/reproduce/archived-test.metrics.json --execute
python -m training.verify_reload --before models/traditional-json-lora-v1/val-step-213.jsonl --after models/traditional-json-lora-v1/val-best-reload.jsonl
```

两条基线的原始测试预测和指标也在`models/traditional-json-lora-v1/baselines/`。运行警告与裁片执行成功分开统计；成功输出且几何有限不等于工业生产或完全合身。

## 5. 从官方基座重新训练

完成第1、2节后，在独立实验目录执行：

```bash
python -m training.train --preflight --report runs/retrain-preflight.json
python -m unittest training.test_pipeline -v
python -m training.train --output-dir runs/retrained-v1
python -m training.infer --adapter runs/retrained-v1 --split test --output runs/retrained-v1/test.jsonl
python -m training.evaluate --split test --predictions runs/retrained-v1/test.jsonl --report runs/retrained-v1/test.metrics.json --execute
```

配置为seed42、rank16、alpha32、dropout0.05、学习率5e-5、3epoch、microbatch1、累积16步；只训练语言attention q/k/v/o LoRA，视觉部分冻结。提示词、配置及数据均提供；测试集不参与选模。发布的是完成训练的适配器，不含优化器状态，支持重新训练但不能从原第213步精确续训。

重训用于验证方法及指标，不承诺新权重SHA与原权重一致；要重现原训练模型输出，优先按第3节加载发布权重。

## 接入演示软件

启用本地语言模型时，设置`GARMENT_MODEL_PATH`为独立实验目录中`lmm_utils/Qwen/Qwen2-VL-2B-Instruct`的绝对路径，`GARMENT_ADAPTER_PATH`为`models/traditional-json-lora-v1`的绝对路径，再启动后端。图片识别仍需自行配置视觉来源；本LoRA未经过图像微调。

## 本次发布验证（2026-10-27）

上传副本通过干净Git检出校验、35份发布文件与13份训练参考文件校验、训练预检及13项训练流程测试。对432条存档测试预测重评，总体/宏平均/各组件指标和数值误差均与原报告相同。另在RTX4070 Laptop上实际加载发布适配器，对覆盖12类的24条验证样本重新推理，24/24与原服务器输出一致。详见[发布验证证据](release-validation/checks.json)及同目录的新预测。

本次没有重新训练，也没有重跑全部432条GPU测试或新建空白Python环境安装验证；原完整实验与本次发布检查分开记录。基座分片来源经官方元数据与本地文件哈希核对，本次测试使用本地分片复制路径，未重复从网络下载4.42GB。
