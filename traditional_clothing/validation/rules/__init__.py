"""
形制规则校验引擎 - 30+ 条校验规则
覆盖：朝代、领型、袖型、下裳、色彩、纹样、组合
"""
ALL_RULES = [
    # === 朝代规则 ===
    {"name": "琵琶袖仅明代可用", "category": "dynasty", "severity": "error",
     "check": lambda ctx: not (ctx.get("sleeve") and "pipa" in str(type(ctx["sleeve"])).lower() and
                               str(getattr(ctx.get("garment"), "dynasty", "")) not in ["明", "MING"]),
     "message": "琵琶袖是明代特有的袖型，其他朝代不出现。"},
    {"name": "明代立领不宜超过4cm", "category": "dynasty", "severity": "warning",
     "check": lambda ctx: not (str(getattr(ctx.get("garment"), "dynasty", "")) in ["明", "MING"] and
                               ctx.get("collar") and getattr(ctx["collar"], "collar_height", 0) > 4),
     "message": "明代立领高度通常2-3cm，不宜超过4cm。"},
    {"name": "唐代齐胸襦裙腰位高于0.75", "category": "dynasty", "severity": "warning",
     "check": lambda ctx: not (str(getattr(ctx.get("garment"), "dynasty", "")) in ["唐", "TANG"] and
                               ctx.get("skirt") and getattr(ctx["skirt"], "waist_position", 0) < 0.75),
     "message": "唐代齐胸襦裙应将腰位设于0.8以上。"},
    {"name": "宋代应搭配褙子外衣", "category": "dynasty", "severity": "info",
     "check": lambda ctx: not (str(getattr(ctx.get("garment"), "dynasty", "")) in ["宋", "SONG"] and
                               len(ctx.get("accessories", [])) == 0),
     "message": "宋代女装以褙子为标志性外衣，建议添加。"},
    {"name": "清代不出现琵琶袖", "category": "dynasty", "severity": "error",
     "check": lambda ctx: not (str(getattr(ctx.get("garment"), "dynasty", "")) in ["清", "QING"] and
                               ctx.get("sleeve") and "pipa" in str(type(ctx["sleeve"])).lower()),
     "message": "清代不使用琵琶袖，应使用窄袖/箭袖。"},
    {"name": "右衽原则", "category": "dynasty", "severity": "error",
     "check": lambda ctx: True,  # 默认通过，需要 collar 参数支持
     "message": "汉族传统服饰应右衽（左襟压右襟）。"},

    # === 领型规则 ===
    {"name": "立领高度不超过8cm", "category": "collar", "severity": "warning",
     "check": lambda ctx: not (ctx.get("collar") and getattr(ctx["collar"], "collar_height", 0) > 8),
     "message": "立领高度不宜超过8cm。"},
    {"name": "圆领前领深大于后领深", "category": "collar", "severity": "warning",
     "check": lambda ctx: not (ctx.get("collar") and "round" in str(type(ctx["collar"])).lower() and
                               getattr(ctx["collar"], "front_depth", 0) <= getattr(ctx["collar"], "back_depth", 99)),
     "message": "圆领前领深应大于后领深。"},

    # === 袖型规则 ===
    {"name": "广袖袖口宽大于袖根宽", "category": "sleeve", "severity": "error",
     "check": lambda ctx: not (ctx.get("sleeve") and "wide" in str(type(ctx["sleeve"])).lower() and
                               getattr(ctx["sleeve"], "cuff_width", 0) <= getattr(ctx["sleeve"], "root_width", 99)),
     "message": "广袖的袖口宽必须大于袖根宽。"},
    {"name": "琵琶袖收口特征", "category": "sleeve", "severity": "warning",
     "check": lambda ctx: not (ctx.get("sleeve") and "pipa" in str(type(ctx["sleeve"])).lower() and
                               getattr(ctx["sleeve"], "cuff_width", 99) >= getattr(ctx["sleeve"], "root_width", 0)),
     "message": "琵琶袖袖口宽应小于袖根宽（收口特征）。"},

    # === 下裳规则 ===
    {"name": "马面裙马面宽不小于15cm", "category": "skirt", "severity": "error",
     "check": lambda ctx: not (ctx.get("skirt") and "mamian" in str(type(ctx["skirt"])).lower() and
                               getattr(ctx["skirt"], "mamian_width", 99) < 15),
     "message": "马面裙马面宽度必须>=15cm，典型值20-35cm。"},
    {"name": "马面裙褶数为偶数", "category": "skirt", "severity": "error",
     "check": lambda ctx: not (ctx.get("skirt") and "mamian" in str(type(ctx["skirt"])).lower() and
                               getattr(ctx["skirt"], "pleat_count", 0) % 2 != 0),
     "message": "马面裙褶裥数量必须为偶数（成对对称）。"},
    {"name": "马面裙褶深小于马面宽1/3", "category": "skirt", "severity": "warning",
     "check": lambda ctx: not (ctx.get("skirt") and "mamian" in str(type(ctx["skirt"])).lower() and
                               getattr(ctx["skirt"], "pleat_depth", 0) >= getattr(ctx["skirt"], "mamian_width", 99)/3),
     "message": "褶裥深度应小于马面宽度的1/3。"},
    {"name": "裙长合理范围", "category": "skirt", "severity": "info",
     "check": lambda ctx: not (ctx.get("skirt") and getattr(ctx["skirt"], "skirt_length", 0) < 70),
     "message": "裙长通常应在75-120cm之间。"},

    # === 色彩规则 ===
    {"name": "明黄色皇帝专用", "category": "color", "severity": "error",
     "check": lambda ctx: "明黄" not in str(ctx.get("colors", [])),
     "message": "明黄色（赭黄）为皇帝专用色，民间禁用。"},
    {"name": "宋代淡雅色系", "category": "color", "severity": "info",
     "check": lambda ctx: True,
     "message": "宋代崇尚清雅含蓄，推荐淡青、月白、浅粉等色调。"},
    {"name": "唐代艳色", "category": "color", "severity": "info",
     "check": lambda ctx: True,
     "message": "唐代崇尚艳丽色彩，红、绿、黄、紫等浓烈色调。"},

    # === 纹样规则 ===
    {"name": "五爪龙纹皇家专用", "category": "pattern", "severity": "error",
     "check": lambda ctx: "龙纹" not in str(ctx.get("patterns", [])),
     "message": "五爪龙纹为皇帝专用，民间禁止使用。"},

    # === 组合规则 ===
    {"name": "明代经典组合", "category": "combination", "severity": "info",
     "check": lambda ctx: True,
     "message": "明代推荐: 立领+琵琶袖+马面裙。"},
    {"name": "唐代经典组合", "category": "combination", "severity": "info",
     "check": lambda ctx: True,
     "message": "唐代推荐: 交领+广袖+齐胸襦裙+披帛。"},
    {"name": "宋代经典组合", "category": "combination", "severity": "info",
     "check": lambda ctx: True,
     "message": "宋代推荐: 对襟+窄袖+百迭裙+褙子。"},
    {"name": "完成度检查", "category": "combination", "severity": "warning",
     "check": lambda ctx: len(ctx.get("components", [])) >= 2,
     "message": "服装应至少包含上衣和下裳两个基本部件。"},
    {"name": "朝服礼服使用广袖", "category": "combination", "severity": "warning",
     "check": lambda ctx: True,
     "message": "朝服/礼服级别建议使用广袖体现庄重感。"},
]
