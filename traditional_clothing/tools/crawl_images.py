"""
图片爬虫 — 从公开源下载传统服饰图片
P3: Wikimedia Commons + Museum Open Access APIs
"""
import sys, io, os, json, time, urllib.request, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
IMG_DIR = os.path.join(DATA_DIR, "images", "crawled")
os.makedirs(IMG_DIR, exist_ok=True)

def download_wikimedia():
    """从 Wikimedia Commons 搜索并下载传统服饰图片"""
    print("=" * 60)
    print("  Wikimedia Commons 图片搜索")
    print("=" * 60)

    # 使用 Wikimedia Commons API 搜索
    search_terms = [
        "Hanfu", "Chinese traditional clothing", "Ming dynasty clothing",
        "Tang dynasty clothing", "Song dynasty clothing", "Qing dynasty clothing",
        "Chinese embroidery", "Chinese silk robe", "Chinese dragon robe",
        "mamian skirt", "horse face skirt", "Chinese cloud collar",
        "Chinese textile pattern", "Chinese brocade",
    ]

    headers = {'User-Agent': 'TraditionalClothingResearch/1.0 (Research Project)'}
    total_downloaded = 0

    for term in search_terms:
        if total_downloaded >= 200:
            break

        print(f"\n  搜索: {term}")
        # Wikimedia Commons API
        api_url = "https://commons.wikimedia.org/w/api.php"
        params = {
            'action': 'query',
            'format': 'json',
            'generator': 'search',
            'gsrsearch': term,
            'gsrlimit': 20,
            'gsrnamespace': 6,  # File namespace
            'prop': 'imageinfo',
            'iiprop': 'url|size|extmetadata',
            'iiurlwidth': 800,
        }

        try:
            url = api_url + '?' + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())

            if 'query' not in data or 'pages' not in data['query']:
                print(f"    无结果")
                continue

            term_dir = os.path.join(IMG_DIR, term.replace(' ', '_').lower()[:40])
            os.makedirs(term_dir, exist_ok=True)

            for page_id, page in data['query']['pages'].items():
                if total_downloaded >= 200:
                    break
                if 'imageinfo' not in page:
                    continue

                for info in page['imageinfo']:
                    img_url = info.get('thumburl') or info.get('url')
                    if not img_url:
                        continue

                    # 跳过太小的图
                    if info.get('thumbwidth', 0) < 200:
                        continue

                    filename = urllib.parse.quote(page['title'].replace('File:', '')[:60], safe='')
                    filepath = os.path.join(term_dir, filename)
                    if os.path.exists(filepath):
                        total_downloaded += 1
                        continue

                    try:
                        img_req = urllib.request.Request(img_url, headers=headers)
                        with urllib.request.urlopen(img_req, timeout=15) as img_resp:
                            with open(filepath, 'wb') as f:
                                f.write(img_resp.read())
                        total_downloaded += 1
                        time.sleep(0.3)
                    except Exception as e:
                        pass

            print(f"    已下载: {total_downloaded}/200")

        except Exception as e:
            print(f"    错误: {type(e).__name__}")

    return total_downloaded


def download_met_open_access():
    """下载 Met Museum Open Access 图片 (已有 TEXMET 索引)"""
    print("\n" + "=" * 60)
    print("  Met Museum Open Access (从TEXMET索引直接下载)")
    print("=" * 60)

    # 加载已有的 TEXMET 筛选索引
    idx_path = os.path.join(DATA_DIR, "downloads", "texmet_filtered.json")
    if not os.path.exists(idx_path):
        print("  TEXMET 索引不存在, 跳过")
        return 0

    with open(idx_path, 'r', encoding='utf-8') as f:
        idx = json.load(f)

    items = idx.get('items', [])
    print(f"  索引: {len(items)} 条")

    met_dir = os.path.join(IMG_DIR, "met_museum_open")
    os.makedirs(met_dir, exist_ok=True)

    downloaded = 0
    for item in items:
        if downloaded >= 300:
            break
        url = item.get('primaryImage') or item.get('primaryImageSmall')
        if not url:
            continue
        filename = f"met_{item['objectID']}.jpg"
        filepath = os.path.join(met_dir, filename)
        if os.path.exists(filepath):
            downloaded += 1
            continue

        try:
            urllib.request.urlretrieve(url, filepath)
            downloaded += 1
            if downloaded % 50 == 0:
                print(f"    已下载: {downloaded}/300")
            time.sleep(0.2)
        except:
            pass

    print(f"  完成: {downloaded} 张")
    return downloaded


def final_summary():
    """最终统计"""
    print("\n" + "=" * 60)
    print("  数据总览")
    print("=" * 60)

    total = 0
    for root, dirs, files in os.walk(os.path.join(DATA_DIR, "images")):
        imgs = [f for f in files if f.endswith(('.jpg', '.png', '.jpeg'))]
        if imgs:
            rel = os.path.relpath(root, DATA_DIR)
            count = len(imgs)
            total += count
            print(f"  {rel}: {count} 张")

    # Kaggle 数据
    kaggle_path = os.path.join(DATA_DIR, "downloads", "kaggle_chinese_clothing")
    if os.path.exists(kaggle_path):
        kaggle_imgs = sum(1 for _ in os.walk(kaggle_path) for f in _[2] if f.endswith(('.jpg','.png','.jpeg')))
        total += kaggle_imgs
        print(f"  downloads/kaggle_chinese_clothing: {kaggle_imgs} 张")

    # 训练数据
    training_path = os.path.join(DATA_DIR, "annotations", "training_data.jsonl")
    if os.path.exists(training_path):
        with open(training_path, 'r', encoding='utf-8') as f:
            training_lines = sum(1 for _ in f)
        print(f"  training_data.jsonl: {training_lines} 条")

    print(f"\n  === 总计: {total} 张图像 ===")
    return total


if __name__ == "__main__":
    print("=" * 60)
    print("  传统服饰图片爬虫")
    print("=" * 60)

    n1 = download_wikimedia()
    n2 = download_met_open_access()
    total = final_summary()

    print(f"\n本次新增: {n1 + n2} 张")
    print(f"总计: {total} 张")
