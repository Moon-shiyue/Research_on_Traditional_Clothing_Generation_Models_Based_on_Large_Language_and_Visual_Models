# 传统服饰智能二维制版演示

当前代码快照支持22类组件/整件款式及209种完整搭配，最多五件衣物。图片先核对衣物清单再确认；文字可直接指定款式和尺寸。输出左侧人体定位、右侧全部二维净样及厘米标注，可编辑尺寸、下载ZIP、查看A4分幅打印并恢复历史。几何检查不代表实体试缝或任意照片精确还原。

## 安装与启动

同一仓库内保持`traditional-garment-studio/`和`garmentcode-traditional/`为同级目录。Python3.9环境为已验证环境，前端使用Node.js及npm。

```sh
# 在仓库根目录安装CPU演示依赖；CairoSVG还需要系统Cairo动态库。
python -m pip install -r requirements-demo.txt
cd traditional-garment-studio/frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

另开终端，在仓库根目录运行：

```sh
cd traditional-garment-studio
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:5173/ 。Windows也可设置`GARMENT_PYTHON`为自己的Python路径后使用cmd启动脚本。服务仅监听本机。

文字样例：`立领对襟上衣；马面裙，裙长95cm；云肩`，或`圆领长袍，衣长130cm，袖长55cm`。

图片识别需在页面“云端视觉设置”中自行配置可用的视觉来源、账号或API；仓库不附带登录资料，也不保证他人账号具备相同服务权限。运行产生的凭据、图片与结果均不提交Git。

## 模型与训练

明确款式/参数的文字和云端识图后的参数制版不需下载本地大模型。本地自由文字LoRA推理及重新训练需要另行安装PyTorch、transformers==4.46.2、peft==0.13.2等训练依赖，下载基座并取得本项目适配器；见`../garmentcode-traditional/training/README.md`。权重不在Git仓库。

可设置`GARMENT_ROOT`、`GARMENT_MODEL_PATH`、`GARMENT_ADAPTER_PATH`和`GARMENT_RUNTIME_DIR`。默认代码资源指向同级`garmentcode-traditional/`；模型/适配器不存在时，不能把自由文字推理当作可用功能。

## 检查

```sh
cd traditional-garment-studio
python -m unittest discover -s backend -t . -p "test*.py"
cd frontend
npm test
npm run build
```

本机当前版本曾通过225项后端与36项前端检查；本次上传副本也已通过225项后端、36项前端测试及前端生产构建。209组合为基础制版完整性检查，不是209张图片的识别准确率。

文档：[软件使用指南](docs/软件使用指南.md)、[支持范围](docs/完整服饰支持范围.md)、[接口](docs/api-complete-garments-2026-10-27.md)。仓库不附带本机历史纸样或测试照片，启动后需自行生成。
