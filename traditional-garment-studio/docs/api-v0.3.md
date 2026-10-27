# 本机制版 API v0.3：单件与两件组合

本页是旧两件版本说明。2026-10-25完整单衣、三/四件叠穿、比甲、开襟确认及默认完整识图见[最新接口补充](api-complete-garments-2026-10-25.md)。

2026-10-22。实现对应 `backend/app.py`，FastAPI 版本 0.3.0。基址 `/api/v1`，原有 `X-Session-Id` UUID 会话头、图片上传、任务轮询及错误格式保持不变。单件字段细节见 [v0.2](api-v0.2.md)，本页覆盖其中“仅单组件、无整套、失败清空旧纸样”的旧说明。

2026-10-23文字兼容修复：明确排除的袖型、云肩层数或朝代不计作正向选择；组合分句保留否定词。“衣长改为110cm”“腰围调整为80cm”等可直接填写，支持正号和前置小数点后再按范围验证。被排除的数值、无法明确归属的“100cm改110cm”请求澄清并保留旧纸样，不会将排除条件删除后生成默认款。

## 支持范围

2026-10-23晚间：厘米衣长在应用层允许褙子0.75–2.0、半臂0.4–0.9倍腿长；原训练schema与模型预测校验契约保持原样。`GET /design/params`的立领`collar_height.range`按当前朝代收窄，另有可选`constraint_note`用于说明模板约束。字段`range`不再直接引用并修改schema列表。参数校验HTTP状态与错误码不变，面向用户的`message`使用中文支持选项或厘米范围，例如“当前立领基础模板的场合可选：常服、朝服。”。

保留12类单组件，新增 `beizi + mamian-skirt`（11片）与 `banbi + ruqun-skirt`（17片）。每组为两件分别缝制的基础款，共用一个人体尺寸集合，没有上下装之间的配缝。共同朝代/场合取两件 schema 的交集，参数面板只提供交集值。当前不是任意完整服饰的复原器，不支持连体上下装、整件交领袍、交叉闭合前襟或整件连接琵琶袖。

`GET /health` 增加 `outfits:[{components:[...],names:[...]}]`；不加载模型。

## 文字组合

`POST /parse` 接受 `{text,image?,scope?,image_proposal_id?}`，返回202及任务ID。`scope` 为 `component`（默认）或 `outfit`，主要控制图片识别范围；明确写出支持的两件组合时，文字路由自动生成整套。

示例：

```json
{"text":"明代褙子，衣长110cm，袖长48cm；马面裙，裙长95cm，常服"}
```

也支持 `唐代半臂，衣长50cm；襦裙，裙长95cm，常服`。人体身高/围度全套共享；衣长和袖长属于上装，裙长、褶量和裙摆属于下裙。共同结尾的明确角色尺寸仍按此分配，不依赖衣物出现顺序。明确要求额外单做领袖片会请求拆分提交，避免漏掉第三件。

袖口文字可明确写“袖口平铺半围24cm”或“袖口整围48cm”。半臂 `sleeve_width` 存平铺半围，褙子 `sleeve_cuff_width` 存整围，两种写法按二倍关系换算；矛盾值请求澄清。原有“袖口宽”写法保持其组件字段的旧语义，优先使用带整围/半围的明确写法。

成功任务的 `result` 保留 `status,reply,pattern,design_params,body_params,design_list`，其中 `design_list` 为两件名称。`design_params` 仍为两层：`[上装组件,字段]`、`[下裙组件,字段]` 以及共用 `[traditional,字段]`。

## 图片整套识别

1. `POST /upload/image` 上传图片，得到会话内 `image_id`。
2. `POST /parse` 传 `{"image":"img_...","text":"可选尺寸","scope":"outfit"}`。
3. 视觉模型分别描述两件衣物。须同时确认支持的一对，并确认上装前襟为 `open`；不完整、不确定或不支持的结构返回澄清，不补造缺失衣物。
4. 成功建议仍为 `status:needs_input`，包含 `suggested_outfit:true`、`suggested_name`、`suggested_text`、`outfit_observations`、`image_proposal_id`。此阶段尚未生成新纸样。
5. 确认时原样回传 `suggested_text` 和 `image_proposal_id`，不再附图片，避免重复识图。令牌会话内单次使用，文本必须与建议一致。换款或修改意图应新发请求。

袖型、裙摆等可见特征贯通到支持的基础款参数，明确文字尺寸优先。全长裙缺少裙长时披露95cm默认值，来源记为 `image_style_default`；它不是照片测量。无精确尺寸时沿用当前人体。图片失败不转付费来源，仍按已有视觉配置工作。

## 元数据、调参及显示

组合 `pattern.component` 为 `outfit`，新增 `outfit_version` 和 `garments`。每件含 `id:upper/lower`、`component,name,panel_count,geometry_validation` 及自身资源URL。总 `panel_count` 为两件之和；`panel_measurements` 的 `panel_id` 加 `upper__/lower__` 前缀，同时增加 `garment_id,garment_name`。

`parameter_sources,default_fields,absolute_lengths_cm,body_parameter_sources` 汇总到根元数据。`PUT /design/params` 仍使用 `[component,field]` 与 `unit:"cm"/"native"`，只修改对应衣物；共用朝代场合同时更新两件。`PUT /body/params` 重新生成两件，保持所有已指定的厘米长度。恢复默认和随机设计同时作用于两件。

`body_layout_svg_url/body_layout_dimension_svg_url` 左侧只有一个人体，按同一解剖坐标叠放两件，右侧放全部无人体净样，保持厘米比例。左侧是二维定位，不能作裁剪轮廓；右侧及独立净样包含真实尺寸。组合 SVG 为子件平移排布，未缩放裁片。

所有成员验证与生成完成才提交会话。输入澄清、非法参数或几何失败保留上次有效纸样，并说明本次尚未生成；前端处理中显示遮罩并禁用下载，避免把旧结果误当成本次输出。失败生成的临时目录清除，不删除既有结果。

## 下载

`GET /download` 和 `POST /download/link` 根据当前结果导出单件或组合。组合根目录包含总览 `pattern*.svg`、带命名空间的 `pattern.json`、组合 `design.json`、共享 `body.json`、`metadata.json`、人体定位文件、中文说明及校验清单。`upper/` 与 `lower/` 包含原样的分件导出、结构说明、尺寸和分件校验清单。

褙子＋马面裙为44文件；半臂＋襦裙下裳为37文件。根 `export-manifest.json` 校验解压后的其它全部文件；它自身不计入哈希范围。全部净样以cm为物理尺寸。马面裙 `lower/cutting*.svg` 含明确声明的裁剪余量，其它净样不含缝份，不可重复加量。没有布料仿真或实体试缝结论。

## A4分幅PDF（2026-10-23）

- `GET /print/plan`：返回当前纸样的A4页数、裁布片数、纸样套数、各裁片的行列与页码范围，以及 `pattern_url`。此请求不生成PDF。
- `POST /print/link`：可传 `{"pattern_url":"预览返回的URL"}`，返回 `url,filename,plan,pattern_url`。预览对应纸样已变化时返回409 `print_changed`；同一会话有任务时返回409 `task_conflict`。旧客户端可不传请求体，表示导出当前设计。
- PDF为1:1厘米净样，不含缝份；首页有10cm校准框，每页有效范围18×25.2cm，邻页重叠0.5cm。页框不是裁剪线，按同一裁片的行列号及十字拼接。
- 仅几何与原有标记都一致的襦裙裙幅共用纸样并标明裁布份数；马面裙两幅保留各自标记。不同比例或镜像裁片不合并。仅当减少页数时旋转90°，不缩放原裁片。
- PDF在同一结果目录缓存；输入或输出校验不符时重建。生成阶段在全局会话锁之外，同一会话不接受改尺寸，其它会话仍可响应。原ZIP内容与接口保持不变。

## 重启恢复（2026-10-23）

会话首次建立时，从 `runtime/patterns/<会话UUID>/` 查找最后一份完整应用设计。校验当前参数schema、人体尺寸、裁片清单、JSON几何及必要SVG；组合还校验两件的身体文件、共同朝代场合和总几何一致。恢复原SVG链接、款式、尺寸来源及固定厘米长度，不重新推理或生成。无法读取或不满足要求的目录跳过，尝试上一份；没有可恢复设计时保持初始状态。

图片确认令牌、上传引用、任务及busy状态不恢复；它们仍按原有会话规则失效。浏览器清除或更换会话UUID后，不会自动读取其它会话的设计。本地文件保留不等于生产身份认证。
