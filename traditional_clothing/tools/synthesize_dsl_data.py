"""
DSL 代码合成器 — 生成 500+ 条 text→GarmentCode DSL 训练配对

策略：
1. 每个部件参数随机采样 → 生成描述+DSL
2. 多部件组合 → 完整服装描述+DSL
3. 朝代特定组合 → 历史准确性约束
4. 输出 JSONL 用于 LLM 微调
"""
import sys, io, os, json, random, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
random.seed(42)

OUTPUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "annotations", "dsl_training.jsonl")

# ==================== DSL 模板 ====================

COLLAR_DSL = """COLLAR {name} {{
    TYPE {class_name}
    DYNASTY {dynasty}
    COLLAR_WIDTH {collar_width:.1f}
    COLLAR_DEPTH {collar_depth:.1f}
    CROSS_ANGLE {cross_angle:.1f}
    BORDER_WIDTH {border_width:.1f}
    OVERLAP_AMOUNT {overlap_amount:.1f}
    CURVE_RADIUS {curve_radius:.1f}
    FRONT_NECK_DEPTH {front_neck_depth:.1f}
    BACK_NECK_DEPTH {back_neck_depth:.1f}
    SEAM_ALLOWANCE {seam_allowance:.1f}
}}"""

STAND_COLLAR_DSL = """COLLAR {name} {{
    TYPE StandCollar
    DYNASTY {dynasty}
    COLLAR_HEIGHT {collar_height:.1f}
    NECK_CIRCUMFERENCE {neck_circumference:.1f}
    STIFFNESS {stiffness:.2f}
    BUTTON_POSITION {button_position:.1f}
    COLLAR_FLARE {collar_flare:.1f}
    SEAM_ALLOWANCE {seam_allowance:.1f}
}}"""

WIDE_SLEEVE_DSL = """SLEEVE {name} {{
    TYPE WideSleeve
    DYNASTY {dynasty}
    SLEEVE_LENGTH {sleeve_length:.1f}
    CUFF_WIDTH {cuff_width:.1f}
    ROOT_WIDTH {root_width:.1f}
    FLARE_START_RATIO {flare_start_ratio:.2f}
    SLEEVE_CAP_HEIGHT {sleeve_cap_height:.1f}
    SEAM_ALLOWANCE {seam_allowance:.1f}
}}"""

PIPA_SLEEVE_DSL = """SLEEVE {name} {{
    TYPE PipaSleeve
    DYNASTY {dynasty}
    SLEEVE_LENGTH {sleeve_length:.1f}
    CUFF_WIDTH {cuff_width:.1f}
    ROOT_WIDTH {root_width:.1f}
    BULGE_WIDTH {bulge_width:.1f}
    BULGE_POSITION {bulge_position:.2f}
    SLEEVE_CAP_HEIGHT {sleeve_cap_height:.1f}
    SEAM_ALLOWANCE {seam_allowance:.1f}
}}"""

NARROW_SLEEVE_DSL = """SLEEVE {name} {{
    TYPE NarrowSleeve
    DYNASTY {dynasty}
    SLEEVE_LENGTH {sleeve_length:.1f}
    CUFF_WIDTH {cuff_width:.1f}
    ROOT_WIDTH {root_width:.1f}
    ELBOW_WIDTH {elbow_width:.1f}
    ELBOW_POSITION {elbow_position:.2f}
    SLEEVE_CAP_HEIGHT {sleeve_cap_height:.1f}
    SEAM_ALLOWANCE {seam_allowance:.1f}
}}"""

MAMIAN_SKIRT_DSL = """SKIRT {name} {{
    TYPE MamianSkirt
    DYNASTY {dynasty}
    SKIRT_LENGTH {skirt_length:.1f}
    WAIST_CIRCUMFERENCE {waist_circumference:.1f}
    MAMIAN_WIDTH {mamian_width:.1f}
    PLEAT_COUNT {pleat_count}
    PLEAT_DEPTH {pleat_depth:.1f}
    PLEAT_DIRECTION {pleat_direction}
    WAISTBAND_HEIGHT {waistband_height:.1f}
    TIE_LENGTH {tie_length:.1f}
    BORDER_WIDTH {border_width:.1f}
    NUM_MAMIAN {num_mamian}
    SEAM_ALLOWANCE {seam_allowance:.1f}
}}"""

RUQUN_SKIRT_DSL = """SKIRT {name} {{
    TYPE RuqunSkirt
    DYNASTY {dynasty}
    SKIRT_LENGTH {skirt_length:.1f}
    WAIST_CIRCUMFERENCE {waist_circumference:.1f}
    HEM_WIDTH {hem_width:.1f}
    WAISTBAND_HEIGHT {waistband_height:.1f}
    PLEAT_COUNT {pleat_count}
    TIE_LENGTH {tie_length:.1f}
    WAIST_POSITION {waist_position:.2f}
    SEAM_ALLOWANCE {seam_allowance:.1f}
}}"""

CLOUD_SHOULDER_DSL = """ACCESSORY {name} {{
    TYPE CloudShoulder
    DYNASTY {dynasty}
    NECK_CIRCUMFERENCE {neck_circumference:.1f}
    NUM_PETALS {num_petals}
    PETAL_RADIUS {petal_radius:.1f}
    COLLAR_STAND_HEIGHT {collar_stand_height:.1f}
    OVERLAP_RATIO {overlap_ratio:.2f}
    SEAM_ALLOWANCE {seam_allowance:.1f}
}}"""

BEIZI_DSL = """ACCESSORY {name} {{
    TYPE Beizi
    DYNASTY {dynasty}
    GARMENT_LENGTH {garment_length:.1f}
    SHOULDER_WIDTH {shoulder_width:.1f}
    CHEST_WIDTH {chest_width:.1f}
    SLIT_HEIGHT {slit_height:.1f}
    SLEEVE_LENGTH {sleeve_length:.1f}
    COLLAR_TYPE {collar_type}
    SEAM_ALLOWANCE {seam_allowance:.1f}
}}"""

BANBI_DSL = """ACCESSORY {name} {{
    TYPE Banbi
    DYNASTY {dynasty}
    GARMENT_LENGTH {garment_length:.1f}
    HALF_SLEEVE_LENGTH {half_sleeve_length:.1f}
    CHEST_WIDTH {chest_width:.1f}
    COLLAR_TYPE {collar_type}
    SEAM_ALLOWANCE {seam_allowance:.1f}
}}"""

FULL_GARMENT_DSL = """GARMENT {name} {{
    DYNASTY {dynasty}
    GENDER {gender}
    OCCASION {occasion}
    COMPONENTS [{component_list}]
    STITCHES [{stitch_list}]
    BODY_MEASUREMENTS {{
        HEIGHT {height:.1f}
        CHEST {chest:.1f}
        WAIST {waist:.1f}
        HIP {hip:.1f}
        SHOULDER {shoulder:.1f}
        NECK {neck:.1f}
        ARM_LENGTH {arm_length:.1f}
    }}
}}"""

# ==================== 参数空间 ====================

DYNASTY_INFO = {
    "汉": {"collars": ["cross"], "sleeves": ["wide"], "skirts": ["ruqun"], "accessories": [], "gender": "通用", "occasion_weight": {"礼服": 3, "常服": 2}},
    "唐": {"collars": ["cross", "round"], "sleeves": ["wide", "narrow"], "skirts": ["ruqun"], "accessories": ["banbi"], "gender": "女", "occasion_weight": {"礼服": 2, "常服": 2, "朝服": 1}},
    "宋": {"collars": ["duijin", "cross", "round"], "sleeves": ["narrow", "wide"], "skirts": ["ruqun"], "accessories": ["beizi", "banbi"], "gender": "女", "occasion_weight": {"常服": 3, "礼服": 1}},
    "明": {"collars": ["stand", "cross", "round", "duijin"], "sleeves": ["pipa", "narrow", "wide"], "skirts": ["mamian", "ruqun"], "accessories": ["cloud_shoulder", "beizi"], "gender": "女", "occasion_weight": {"常服": 2, "礼服": 2, "朝服": 1}},
    "清": {"collars": ["stand", "round"], "sleeves": ["narrow", "wide"], "skirts": ["mamian"], "accessories": ["cloud_shoulder"], "gender": "女", "occasion_weight": {"常服": 2, "礼服": 2, "朝服": 1}},
}

OCCASIONS = ["朝服", "礼服", "常服", "便服"]
GENDERS = ["男", "女", "通用"]

# ==================== 描述生成器 ====================

def gen_cross_collar_desc(params):
    return (f"{params['dynasty']}代交领，领宽{params['collar_width']:.0f}cm，"
            f"领深{params['collar_depth']:.0f}cm，交叉角度{params['cross_angle']:.0f}度，"
            f"缘边宽{params['border_width']:.1f}cm，右衽交领结构。")

def gen_stand_collar_desc(params):
    return (f"{params['dynasty']}代立领，领高{params['collar_height']:.1f}cm，"
            f"领围{params['neck_circumference']:.0f}cm，"
            f"{'明代风格矮领' if params['collar_height'] < 3.5 else '清代风格高领'}，挺拔直立。")

def gen_wide_sleeve_desc(params):
    return (f"广袖，袖长{params['sleeve_length']:.0f}cm，袖口宽{params['cuff_width']:.0f}cm，"
            f"袖口宽大飘逸，{'唐代大袖风格' if params['cuff_width'] > 50 else '日常广袖'}。")

def gen_pipa_sleeve_desc(params):
    return (f"琵琶袖，袖长{params['sleeve_length']:.0f}cm，袖口宽{params['cuff_width']:.0f}cm，"
            f"膨胀宽{params['bulge_width']:.0f}cm，形似琵琶，明代标志性袖型。")

def gen_narrow_sleeve_desc(params):
    return (f"窄袖，袖长{params['sleeve_length']:.0f}cm，袖口宽{params['cuff_width']:.0f}cm，"
            f"袖肘宽{params['elbow_width']:.0f}cm，日常实用款式。")

def gen_mamian_skirt_desc(params):
    direction_text = "向中心" if params['pleat_direction'] == 0 else "向两侧"
    return (f"马面裙，裙长{params['skirt_length']:.0f}cm，腰围{params['waist_circumference']:.0f}cm，"
            f"马面宽{params['mamian_width']:.0f}cm，{params['pleat_count']}对褶裥（{direction_text}），"
            f"褶深{params['pleat_depth']:.1f}cm，腰头高{params['waistband_height']:.0f}cm，"
            f"{'有裙襕装饰' if params['border_width'] > 0 else '无裙襕'}。")

def gen_ruqun_skirt_desc(params):
    waist_desc = "齐胸高腰" if params['waist_position'] > 0.75 else ("高腰" if params['waist_position'] > 0.65 else "自然腰位")
    return (f"襦裙，裙长{params['skirt_length']:.0f}cm，腰围{params['waist_circumference']:.0f}cm，"
            f"裙摆宽{params['hem_width']:.0f}cm，{params['pleat_count']}道褶，{waist_desc}。")

def gen_cloud_shoulder_desc(params):
    return (f"云肩，{params['num_petals']}片云形裁片，径向长{params['petal_radius']:.0f}cm，"
            f"内领高{params['collar_stand_height']:.1f}cm，明清装饰性肩部配件。")

def gen_beizi_desc(params):
    collar_names = ["交领", "对襟", "圆领"]
    return (f"褙子，衣长{params['garment_length']:.0f}cm，肩宽{params['shoulder_width']:.0f}cm，"
            f"侧开衩{params['slit_height']:.0f}cm，{collar_names[params['collar_type']]}，宋代标志性外衣。")

def gen_banbi_desc(params):
    collar_names = ["交领", "对襟", "圆领"]
    return (f"半臂，衣长{params['garment_length']:.0f}cm，半袖长{params['half_sleeve_length']:.0f}cm，"
            f"{collar_names[params['collar_type']]}，唐宋短袖外衣。")

# ==================== 参数采样 ====================

def sample_params(param_space, n=1):
    """从参数空间采样"""
    results = []
    for _ in range(n):
        params = {}
        for key, (lo, hi, step) in param_space.items():
            if isinstance(step, int):
                params[key] = random.randint(lo, hi)
            else:
                val = random.uniform(lo, hi)
                params[key] = round(val / step) * step if step else round(val, 1)
        results.append(params)
    return results

# ==================== 数据生成 ====================

def generate_collar_samples():
    """生成领型样本"""
    samples = []
    # 交领
    params_space = {
        "collar_width": (12, 28, 1), "collar_depth": (15, 35, 1),
        "cross_angle": (35, 65, 5), "border_width": (1.5, 7, 0.5),
        "overlap_amount": (5, 14, 1), "curve_radius": (1.5, 9, 0.5),
        "front_neck_depth": (6, 14, 1), "back_neck_depth": (2, 5, 0.5),
        "seam_allowance": (0.5, 2, 0.5),
    }
    for dynasty in ["汉", "唐", "宋", "明"]:
        for params in sample_params(params_space, 20):
            params["dynasty"] = dynasty
            params["name"] = "交领"
            params["class_name"] = "CrossCollar"
            desc = gen_cross_collar_desc(params)
            dsl = COLLAR_DSL.format(**params)
            samples.append({"text": desc, "dsl": dsl, "component": "cross_collar", "dynasty": dynasty})

    # 立领
    stand_space = {
        "collar_height": (2, 5.5, 0.5), "neck_circumference": (32, 45, 1),
        "stiffness": (0.3, 0.9, 0.1), "button_position": (1, 4, 0.5),
        "collar_flare": (1, 12, 1), "seam_allowance": (0.5, 2, 0.5),
    }
    for dynasty in ["明", "清"]:
        lo, hi = (2, 3.5) if dynasty == "明" else (3.5, 5.5)
        stand_space["collar_height"] = (lo, hi, 0.5)
        for params in sample_params(stand_space, 25):
            params["dynasty"] = dynasty
            params["name"] = "立领"
            desc = gen_stand_collar_desc(params)
            dsl = STAND_COLLAR_DSL.format(**params)
            samples.append({"text": desc, "dsl": dsl, "component": "stand_collar", "dynasty": dynasty})

    return samples


def generate_sleeve_samples():
    """生成袖型样本"""
    samples = []
    # 广袖
    wide_space = {"sleeve_length": (60, 130, 5), "cuff_width": (35, 110, 5),
                  "root_width": (14, 28, 2), "flare_start_ratio": (0.15, 0.5, 0.05),
                  "sleeve_cap_height": (8, 18, 1), "seam_allowance": (0.5, 2, 0.5)}
    for dynasty in ["汉", "唐"]:
        for params in sample_params(wide_space, 25):
            params["dynasty"] = dynasty; params["name"] = "广袖"
            desc = gen_wide_sleeve_desc(params)
            dsl = WIDE_SLEEVE_DSL.format(**params)
            samples.append({"text": desc, "dsl": dsl, "component": "wide_sleeve", "dynasty": dynasty})

    # 琵琶袖
    pipa_space = {"sleeve_length": (65, 95, 5), "cuff_width": (10, 18, 1),
                  "root_width": (18, 26, 2), "bulge_width": (28, 42, 2),
                  "bulge_position": (0.35, 0.55, 0.05), "sleeve_cap_height": (8, 16, 1),
                  "seam_allowance": (0.5, 2, 0.5)}
    for params in sample_params(pipa_space, 40):
        params["dynasty"] = "明"; params["name"] = "琵琶袖"
        desc = gen_pipa_sleeve_desc(params)
        dsl = PIPA_SLEEVE_DSL.format(**params)
        samples.append({"text": desc, "dsl": dsl, "component": "pipa_sleeve", "dynasty": "明"})

    # 窄袖
    narrow_space = {"sleeve_length": (55, 90, 5), "cuff_width": (14, 20, 1),
                    "root_width": (16, 24, 2), "elbow_width": (18, 26, 1),
                    "elbow_position": (0.35, 0.5, 0.05), "sleeve_cap_height": (7, 14, 1),
                    "seam_allowance": (0.5, 2, 0.5)}
    for dynasty in ["唐", "宋", "明", "清"]:
        for params in sample_params(narrow_space, 15):
            params["dynasty"] = dynasty; params["name"] = "窄袖"
            desc = gen_narrow_sleeve_desc(params)
            dsl = NARROW_SLEEVE_DSL.format(**params)
            samples.append({"text": desc, "dsl": dsl, "component": "narrow_sleeve", "dynasty": dynasty})

    return samples


def generate_skirt_samples():
    """生成下裳样本"""
    samples = []
    # 马面裙 ⭐
    mamian_space = {"skirt_length": (80, 115, 5), "waist_circumference": (60, 95, 5),
                    "mamian_width": (18, 35, 2), "pleat_count": (4, 10, 2),
                    "pleat_depth": (2, 7, 0.5), "pleat_direction": (0, 1, 1),
                    "waistband_height": (4, 9, 1), "tie_length": (60, 140, 10),
                    "border_width": (0, 20, 2), "num_mamian": (2, 2, 2),
                    "seam_allowance": (0.5, 2, 0.5)}
    for dynasty in ["明", "清"]:
        for params in sample_params(mamian_space, 50):
            params["dynasty"] = dynasty; params["name"] = "马面裙"
            # 明制马面更宽
            if dynasty == "明" and params["mamian_width"] < 20:
                params["mamian_width"] = random.uniform(20, 35)
            desc = gen_mamian_skirt_desc(params)
            dsl = MAMIAN_SKIRT_DSL.format(**params)
            samples.append({"text": desc, "dsl": dsl, "component": "mamian_skirt", "dynasty": dynasty})

    # 襦裙
    ruqun_space = {"skirt_length": (75, 125, 5), "waist_circumference": (60, 95, 5),
                   "hem_width": (120, 280, 10), "waistband_height": (3, 7, 1),
                   "pleat_count": (4, 22, 2), "tie_length": (60, 140, 10),
                   "waist_position": (0.55, 0.9, 0.05), "seam_allowance": (0.5, 2, 0.5)}
    for dynasty in ["汉", "唐", "宋"]:
        wp_lo = 0.75 if dynasty == "唐" else 0.55
        ruqun_space["waist_position"] = (wp_lo, 0.9, 0.05)
        for params in sample_params(ruqun_space, 30):
            params["dynasty"] = dynasty; params["name"] = "襦裙"
            desc = gen_ruqun_skirt_desc(params)
            dsl = RUQUN_SKIRT_DSL.format(**params)
            samples.append({"text": desc, "dsl": dsl, "component": "ruqun_skirt", "dynasty": dynasty})

    return samples


def generate_accessory_samples():
    """生成配件样本"""
    samples = []
    # 云肩
    cloud_space = {"neck_circumference": (33, 45, 2), "num_petals": (4, 8, 2),
                   "petal_radius": (14, 28, 2), "collar_stand_height": (1, 3.5, 0.5),
                   "overlap_ratio": (0.05, 0.25, 0.05), "seam_allowance": (0.5, 1.5, 0.5)}
    for params in sample_params(cloud_space, 30):
        params["dynasty"] = random.choice(["明", "清"]); params["name"] = "云肩"
        desc = gen_cloud_shoulder_desc(params)
        dsl = CLOUD_SHOULDER_DSL.format(**params)
        samples.append({"text": desc, "dsl": dsl, "component": "cloud_shoulder", "dynasty": params["dynasty"]})

    # 褙子
    beizi_space = {"garment_length": (80, 135, 5), "shoulder_width": (33, 43, 2),
                   "chest_width": (48, 68, 3), "slit_height": (30, 75, 5),
                   "sleeve_length": (50, 75, 5), "collar_type": (0, 2, 1),
                   "seam_allowance": (0.5, 2, 0.5)}
    for params in sample_params(beizi_space, 35):
        params["dynasty"] = "宋" if random.random() < 0.7 else "明"; params["name"] = "褙子"
        desc = gen_beizi_desc(params)
        dsl = BEIZI_DSL.format(**params)
        samples.append({"text": desc, "dsl": dsl, "component": "beizi", "dynasty": params["dynasty"]})

    # 半臂
    banbi_space = {"garment_length": (42, 70, 3), "half_sleeve_length": (16, 35, 2),
                   "chest_width": (45, 62, 3), "collar_type": (0, 2, 1),
                   "seam_allowance": (0.5, 2, 0.5)}
    for params in sample_params(banbi_space, 25):
        params["dynasty"] = random.choice(["唐", "宋"]); params["name"] = "半臂"
        desc = gen_banbi_desc(params)
        dsl = BANBI_DSL.format(**params)
        samples.append({"text": desc, "dsl": dsl, "component": "banbi", "dynasty": params["dynasty"]})

    return samples


def generate_garment_combinations():
    """生成完整服装组合"""
    samples = []
    combos = {
        "明制袄裙": {"dynasty": "明", "collars": ["stand", "cross"], "sleeves": ["pipa", "narrow"],
                     "skirts": ["mamian"], "accessories": ["cloud_shoulder"],
                     "occasion": ["常服", "礼服"]},
        "唐制齐胸襦裙": {"dynasty": "唐", "collars": ["cross"], "sleeves": ["wide"],
                        "skirts": ["ruqun"], "accessories": ["banbi"],
                        "occasion": ["礼服", "常服"]},
        "宋制褙子裙": {"dynasty": "宋", "collars": ["duijin", "cross"], "sleeves": ["narrow"],
                       "skirts": ["ruqun"], "accessories": ["beizi"],
                       "occasion": ["常服"]},
        "汉制深衣": {"dynasty": "汉", "collars": ["cross"], "sleeves": ["wide"],
                     "skirts": ["ruqun"], "accessories": [],
                     "occasion": ["礼服", "朝服"]},
    }

    for style_name, config in combos.items():
        for _ in range(25):
            dynasty = config["dynasty"]
            occasion = random.choice(config["occasion"])
            gender = random.choice(["女", "男"])

            # 随机选部件
            collar_type = random.choice(config["collars"])
            sleeve_type = random.choice(config["sleeves"])
            skirt_type = random.choice(config["skirts"])
            components = [collar_type, sleeve_type, skirt_type]
            if config["accessories"] and random.random() < 0.6:
                acc = random.choice(config["accessories"])
                components.append(acc)

            # 身体尺寸
            body = {
                "height": random.uniform(150, 180),
                "chest": random.uniform(78, 100),
                "waist": random.uniform(60, 90),
                "hip": random.uniform(82, 102),
                "shoulder": random.uniform(34, 42),
                "neck": random.uniform(32, 42),
                "arm_length": random.uniform(48, 62),
            }

            # 描述
            desc_parts = [f"{dynasty}代{style_name}，{occasion}，{gender}性"]
            desc_parts.append(f"身高{body['height']:.0f}cm，胸围{body['chest']:.0f}cm，腰围{body['waist']:.0f}cm")
            if "stand" in components:
                desc_parts.append("立领")
            if "cross" in components:
                desc_parts.append("交领右衽")
            if "pipa" in components:
                desc_parts.append("琵琶袖")
            if "wide" in components:
                desc_parts.append("广袖")
            if "narrow" in components:
                desc_parts.append("窄袖")
            if "mamian" in components:
                desc_parts.append("马面裙")
            if "ruqun" in components:
                desc_parts.append("襦裙")
            if "cloud_shoulder" in components:
                desc_parts.append("云肩")
            if "beizi" in components:
                desc_parts.append("褙子")
            if "banbi" in components:
                desc_parts.append("半臂")

            desc = "，".join(desc_parts) + "。"

            # DSL
            dsl = FULL_GARMENT_DSL.format(
                name=style_name,
                dynasty=dynasty,
                gender=gender,
                occasion=occasion,
                component_list=", ".join(components),
                stitch_list="collar_to_body, sleeve_to_body, skirt_to_waistband",
                **body,
            )
            samples.append({"text": desc, "dsl": dsl, "component": "full_garment", "dynasty": dynasty,
                           "style": style_name, "occasion": occasion})
    return samples


# ==================== 主程序 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("  DSL 代码合成器")
    print("=" * 60)

    all_samples = []
    generators = [
        ("领型", generate_collar_samples),
        ("袖型", generate_sleeve_samples),
        ("下裳", generate_skirt_samples),
        ("配件", generate_accessory_samples),
        ("完整服装", generate_garment_combinations),
    ]

    for name, gen_func in generators:
        samples = gen_func()
        all_samples.extend(samples)
        print(f"  {name}: {len(samples)} 条")

    print(f"\n  总计: {len(all_samples)} 条 DSL 训练数据")

    # 保存
    random.shuffle(all_samples)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        for item in all_samples:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\n  已保存到: {OUTPUT}")
    print(f"  格式: text (中文描述) + dsl (GarmentCode DSL)")
    print(f"  可用于 LLM 微调 (text→DSL code generation)")

    # 统计
    from collections import Counter
    comps = Counter(s["component"] for s in all_samples)
    dyns = Counter(s["dynasty"] for s in all_samples)
    print(f"\n  按部件统计:")
    for k, v in comps.most_common():
        print(f"    {k}: {v}")
    print(f"\n  按朝代统计:")
    for k, v in dyns.most_common():
        print(f"    {k}: {v}")

    print(f"\n{'='*60}")
    print(f"  DSL 数据合成完成! {len(all_samples)} 条可用")
    print(f"{'='*60}")
