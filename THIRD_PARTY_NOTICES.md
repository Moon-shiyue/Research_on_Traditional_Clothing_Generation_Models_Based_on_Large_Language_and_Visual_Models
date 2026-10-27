# 来源与许可说明

`traditional_clothing/`为仓库原有模块，本次保留。

`garmentcode-traditional/pygarment/`、`assets/garment_programs/`及部分基础人体/参数支持来自本机可用的Design2GarmentCode参考代码；该参考项目的Style3D MIT许可原文保留在`garmentcode-traditional/LICENSE.upstream`。上游：https://github.com/Style3D/design2garmentcode-impl 。其中GarmentCode/PyGarment的参考来源：https://github.com/maria-korosteleva/GarmentCode 。原文件中的作者及来源说明保留。

传统服饰扩展、训练流程和演示应用为本项目工作代码。此说明不为仓库原有或新增原创代码另选开源许可证，也不更改任何第三方许可。

本次新增代码包不包含第三方服饰照片、SMPL人体网格、Qwen基座权重或私人登录资料。`garmentcode-traditional/data/`中的新增文字样本是参数化生成的项目训练输入，重建方法在`traditional_ext/build_dataset.py`及`training/prepare_data.py`，并非服饰图片数据集。源库已有数据的来源与限制仍按其原说明。

GarmentCode原始MIT许可原文另保留于`garmentcode-traditional/LICENSE.GarmentCode`，版权归Maria Korosteleva。

发布的LoRA适配器基于Qwen2-VL-2B-Instruct训练。Qwen的Apache-2.0许可及原模型说明随精确运行配置保存在`garmentcode-traditional/models/traditional-json-lora-v1/base_runtime/`。基座权重从官方固定版本下载；项目训练适配器、数据、预测和训练记录随仓库发布。
