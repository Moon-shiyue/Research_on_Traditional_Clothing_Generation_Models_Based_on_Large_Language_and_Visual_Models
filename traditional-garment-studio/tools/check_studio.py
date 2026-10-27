"""Read-only local setup checks; no login, inference, installation or file writes."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler


ROOT = Path(__file__).resolve().parents[1]

# A newer server may add types; require the supported public capabilities,
# rather than rejecting it because its catalog is larger than an old release.
REQUIRED_COMPONENTS = {'mamian-skirt', 'ruqun-skirt', 'beizi', 'banbi', 'cloud-shoulder',
    'cross-collar', 'duijin-collar', 'round-collar', 'stand-collar',
    'narrow-sleeve', 'wide-sleeve', 'pipa-sleeve',
    'cross-upper', 'round-upper', 'stand-upper', 'cross-robe', 'round-robe', 'stand-robe','bijia','pibo','duijin-upper','chest-wrap'}
REQUIRED_PAIRS = {frozenset((upper, lower)) for upper in
    ['beizi', 'banbi', 'cross-upper', 'round-upper', 'stand-upper','bijia','duijin-upper','chest-wrap']
    for lower in ['mamian-skirt', 'ruqun-skirt']}
REQUIRED_ENSEMBLES = REQUIRED_PAIRS | {p | {'cloud-shoulder'} for p in REQUIRED_PAIRS} | {
    frozenset((robe, 'cloud-shoulder')) for robe in ['cross-robe', 'round-robe', 'stand-robe']}
for inner in ['cross-upper','round-upper','stand-upper','chest-wrap']:
    for outer in ['beizi','banbi','bijia','duijin-upper']:
        for lower in ['mamian-skirt','ruqun-skirt']:
            group=frozenset((inner,outer,lower))
            REQUIRED_ENSEMBLES.update([group,group|{'cloud-shoulder'}])


REQUIRED_ENSEMBLES.update([group|{'pibo'} for group in list(REQUIRED_ENSEMBLES)])
REQUIRED_ENSEMBLES.update(frozenset((c,'pibo')) for c in
    ['beizi','banbi','bijia','duijin-upper','chest-wrap','cross-upper','round-upper','stand-upper','cross-robe','round-robe','stand-robe'])


def health_capabilities(health):
    components = health.get('components', {})
    if not isinstance(components, dict):
        return False, '组件目录格式不正确'
    def groups(key):
        rows = health.get(key, [])
        if not isinstance(rows, list):
            raise ValueError('组合目录格式不正确')
        result = set()
        for row in rows:
            values = row.get('components') if isinstance(row, dict) else None
            if not isinstance(values, list) or not all(isinstance(c, str) for c in values):
                raise ValueError('组合目录格式不正确')
            result.add(frozenset(values))
        return result
    try:
        pairs, ensembles = groups('outfits'), groups('ensembles')
    except ValueError as error:
        return False, str(error)
    ready = (health.get('status') == 'ok' and REQUIRED_COMPONENTS <= set(components)
        and REQUIRED_PAIRS <= pairs and REQUIRED_ENSEMBLES <= ensembles)
    detail = f'可访问，{len(components)}类组件、{len(pairs)}种上下装组合、{len(ensembles)}种完整组合。'
    if not ready:
        detail += '完整服饰能力不齐全；若代码已更新，请关闭旧后端窗口后重新运行run-backend.cmd。'
    return ready, detail


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def read_local(path, port=8000, as_json=True):
    # Only this fixed loopback reader bypasses environment proxies. Remote
    # vision requests keep their separately configured transport.
    with build_opener(ProxyHandler({}), NoRedirect).open('http://127.0.0.1:'+str(port)+path, timeout=4) as response:
        raw = response.read(512_001)
        if len(raw) > 512_000:
            raise ValueError('本机服务返回内容过大')
        if not as_json:
            return raw.decode('utf-8')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError('本机接口返回了其它应用的数据')
        return value


def check(offline=False):
    garment = Path(os.environ.get('GARMENT_ROOT', ROOT.parent/'garmentcode-traditional')).resolve()
    model = Path(os.environ.get('GARMENT_MODEL_PATH', garment/'lmm_utils/Qwen/Qwen2-VL-2B-Instruct'))
    adapter = Path(os.environ.get('GARMENT_ADAPTER_PATH', garment/'artifacts/server-results-20261006/runs/traditional-json-lora-v1'))
    sys.path.insert(0, str(garment))
    rows = []

    def add(name, ok, detail, optional=False):
        rows.append(dict(name=name, status='ok' if ok else 'warning' if optional else 'error', detail=detail))

    add('Python', sys.version_info >= (3, 9), sys.executable+' / '+sys.version.split()[0])
    for module in ['fastapi', 'uvicorn', 'multipart', 'httpx', 'PIL', 'yaml', 'numpy',
                   'pygarment', 'svgpathtools', 'cairosvg', 'reportlab', 'pypdf']:
        try:
            found = importlib.util.find_spec(module) is not None
        except (ModuleNotFoundError, ValueError):
            found = False
        add('依赖 '+module, found, '可找到模块（未加载模型）' if found else '当前Python中缺少模块；请核对d2g环境及backend/requirements.txt')
    required = ['data/training_v1/schema.json', 'assets/design_params/traditional.yaml',
                'assets/bodies/mean_female.yaml', 'traditional_ext']
    missing = [name for name in required if not (garment/name).exists()]
    add('主项目资源', not missing, str(garment) if not missing else '缺少：'+', '.join(missing))
    add('本地文字模型', (model/'config.json').is_file() and (adapter/'adapter_model.safetensors').is_file(),
        '只核对配置与适配器存在；未读取权重。明确组件和参数可直接制版，未解析文字才可能加载模型。', optional=True)
    add('Node.js / npm', bool(shutil.which('node') and shutil.which('npm.cmd' if os.name=='nt' else 'npm')),
        '需在PATH中可用；本检查不安装或更新软件。')
    add('前端依赖', (ROOT/'frontend/node_modules/vite/bin/vite.js').is_file(), '核对frontend/node_modules中的Vite入口。')
    if not offline:
        try:
            health = read_local('/api/v1/health')
            healthy, detail = health_capabilities(health)
            add('后端8000', healthy, detail+'本地模型是否已加载不代表识图服务状态。')
        except (HTTPError, URLError, OSError, ValueError, TypeError):
            add('后端8000', False, '无法确认制版服务；先运行run-backend.cmd，并查看该窗口错误。')
        try:
            html = read_local('/', 5173, False)
            proxy = read_local('/api/v1/health', 5173)
            add('前端5173及代理', 'id="app"' in html and health_capabilities(proxy)[0],
                '已读页面与后端代理健康接口；不是浏览器交互或模型质量测试。')
        except (HTTPError, URLError, OSError, ValueError, TypeError):
            add('前端5173及代理', False, '先运行run-frontend.cmd；若8000正常而代理失败，重启前端。')
        try:
            config = read_local('/api/v1/vision/config')
            source = config.get('source')
            label = 'ChatGPT套餐' if source=='chatgpt_plan' else '独立API' if source=='api_key' else '未知来源'
            add('图片识别配置', bool(config.get('configured')), label+' / '+str(config.get('model', ''))+
                '；仅本机配置状态，未发送图片、未验证远端权限或剩余额度。', optional=True)
        except (HTTPError, URLError, OSError, ValueError, TypeError):
            add('图片识别配置', False, '本机配置未能读取；明确文字制版可单独使用。', optional=True)
    return dict(version='studio-check-v2', offline=offline,
        ready=not any(row['status']=='error' for row in rows), checks=rows,
        scope='只读本机检查；不读取或输出凭据，不启动服务，不推理，不安装，不修改数据。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='只查环境和文件，不连接本机服务')
    parser.add_argument('--json', action='store_true', help='输出可保存的检查结果')
    args = parser.parse_args()
    report = check(args.offline)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for row in report['checks']:
            print('['+row['status'].upper()+'] '+row['name']+'：'+row['detail'])
        print('\n'+report['scope'])
        print('基础检查通过。' if report['ready'] else '请先处理ERROR项；已有纸样和训练文件未改动。')
    return 0 if report['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
