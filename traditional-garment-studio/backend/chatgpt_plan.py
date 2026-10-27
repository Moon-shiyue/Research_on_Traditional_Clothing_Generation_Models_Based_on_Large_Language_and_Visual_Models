"""Official Sign in with ChatGPT for this loopback-only application.

Separate app-owned credentials; never reads Codex/ChatGPT login files.
Windows credentials use current-user DPAPI; Unix files are owner-only.
"""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit
import uuid

import httpx
import jwt

from .cloud_errors import VisionError
from .settings import STUDIO_ROOT

ISSUER = 'https://auth.openai.com'
RESOURCE = 'https://api.openai.com/v1'
SCOPE = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'
DIRECT = 'chatgpt.tokens.use.direct'


def _protect(data, decrypt=False):
    if os.name != 'nt':
        return data
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        fn = crypt.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        args = (ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output))
    else:
        fn = crypt.CryptProtectData
        fn.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        args = (ctypes.byref(source), 'Traditional Garment Studio', None, None, None, 1, ctypes.byref(output))
    fn.restype = wintypes.BOOL
    if not fn(*args):
        raise VisionError('无法访问本机加密的登录凭据，请使用原 Windows 用户启动。')
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(output.data)


class PlanSession:
    def __init__(self, directory=None, transport=None):
        self.directory = Path(directory or STUDIO_ROOT / '.private' / 'chatgpt')
        self.transport = transport
        self.lock = threading.RLock()
        self.pending = None
        self.last_message = ''
        self.catalogs = {}
        self.retry_client_id = None
        self.data = {'host_id': 'urn:uuid:' + str(uuid.uuid4()), 'accounts': {}, 'active': None}
        self.file = self.directory / ('credentials.dpapi' if os.name == 'nt' else 'credentials.json')
        if self.file.is_file():
            try:
                self.data = json.loads(_protect(self.file.read_bytes(), decrypt=True))
            except Exception:
                # Do not overwrite a record we could not decrypt/read.
                raise VisionError('本应用登录记录无法读取；请检查 Windows 用户和本机凭据文件。') from None

    def _save(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        content = _protect(json.dumps(self.data, ensure_ascii=False).encode())
        temp = self.directory / ('.credentials-' + secrets.token_hex(8))
        fd = os.open(str(temp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(content)
            os.replace(temp, self.file)
        finally:
            temp.unlink(missing_ok=True)

    def _json(self, method, url, **kwargs):
        # Connect failures occur before request delivery. A read/write/stream
        # failure may follow acceptance of a one-time token or refresh request,
        # so those failures must never trigger automatic re-submission.
        for attempt in range(2):
            try:
                with httpx.Client(timeout=25, follow_redirects=False, transport=self.transport) as client:
                    response = client.request(method, url, **kwargs)
                break
            except (httpx.ConnectError,httpx.ConnectTimeout):
                if attempt:
                    raise VisionError('无法连接 OpenAI 登录服务，已重试一次连接，请检查网络后重试。') from None
            except httpx.HTTPError:
                raise VisionError('OpenAI 登录连接中断或读取超时，未重复提交登录请求，请稍后重试。') from None
        if response.status_code != 200:
            if response.status_code in (401, 403):
                raise VisionError('ChatGPT 登录或套餐权限已失效，请重新登录并授权使用套餐。')
            if response.status_code == 429:
                raise VisionError('ChatGPT 套餐额度或本应用限额已达到，请在 ChatGPT 用量设置中查看。')
            raise VisionError('OpenAI 登录服务返回 HTTP ' + str(response.status_code) + '，请稍后重试。')
        try:return response.json()
        except ValueError:
            raise VisionError('OpenAI 登录服务返回了无法读取的数据，未重复提交登录请求。') from None

    def _discovery(self):
        config = self._json('GET', ISSUER + '/.well-known/openid-configuration')
        if config.get('issuer') != ISSUER:
            raise VisionError('OpenAI 身份服务的签发者校验失败。')
        for field in ['authorization_endpoint', 'token_endpoint', 'jwks_uri', 'revocation_endpoint']:
            parsed = urlsplit(config.get(field, ''))
            if parsed.scheme != 'https' or parsed.netloc != 'auth.openai.com' or parsed.fragment or parsed.query:
                raise VisionError('OpenAI 身份服务地址校验失败。')
        return config

    def status(self):
        with self.lock:
            active = self.data['accounts'].get(self.data['active'], {})
            return {'connected': bool(active.get('access_token')),
                    'active_account': self.data['active'],
                    'accounts': [{'id': key, 'label': value['label'], 'signed_in': bool(value.get('access_token'))}
                                 for key, value in self.data['accounts'].items()],
                    'pending': bool(self.pending), 'message': self.last_message,
                    'model': active.get('model', '')}

    def start(self, account_id=None):
        with self.lock:
            if self.pending:
                raise VisionError('已有登录窗口正在等待授权，请完成或取消后再试。')
            account = self.data['accounts'].get(account_id) if account_id else None
            if account_id and not account:
                raise VisionError('请选择已有账号，或使用新账号登录。')
            config = self._discovery()
            self._save()  # Persist the host ID BEFORE registration.
            pending = {'state': secrets.token_urlsafe(32), 'nonce': secrets.token_urlsafe(32),
                       'verifier': secrets.token_urlsafe(64), 'account_id': account_id,
                       'client_id': account['client_id'] if account else (self.retry_client_id or 'dynamic_agent_client'),
                       'config': config, 'deadline': time.time() + 600}
            owner = self
            class Callback(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass  # OAuth callback query strings must never enter logs.

                def do_GET(self):
                    if urlsplit(self.path).path != '/auth/callback':
                        self.send_error(404)
                        return
                    try:
                        owner.complete(parse_qs(urlsplit(self.path).query), pending)
                        body = '登录授权已完成，可以关闭此窗口并返回传统服饰制版软件。'
                        code = 200
                    except VisionError as error:
                        body, code = str(error), 400
                    except Exception:
                        owner.fail(pending, '登录验证未完成，请返回软件重新登录。')
                        body, code = '登录验证未完成，请返回软件重新登录。', 400
                    content = ('<!doctype html><meta charset="utf-8"><title>传统服饰制版登录</title><p>' + body + '</p>').encode()
                    self.send_response(code)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(content)))
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Referrer-Policy', 'no-referrer')
                    self.send_header('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")
                    self.end_headers()
                    self.wfile.write(content)
            server = ThreadingHTTPServer(('127.0.0.1', 0), Callback)
            pending['server'] = server
            pending['redirect_uri'] = f'http://127.0.0.1:{server.server_port}/auth/callback'
            pending['timer'] = threading.Timer(600, lambda: self.fail(pending, '登录已超时，请重新打开登录。'))
            pending['timer'].daemon = True
            self.pending = pending
            self.last_message = '正在等待官方登录授权。'
            threading.Thread(target=server.serve_forever, daemon=True).start()
            pending['timer'].start()
            query = {'client_id': pending['client_id'], 'ext_agent_host_id': self.data['host_id'],
                     'response_type': 'code', 'redirect_uri': pending['redirect_uri'], 'scope': SCOPE,
                     'resource': RESOURCE, 'state': pending['state'], 'nonce': pending['nonce'],
                     'code_challenge_method': 'S256',
                     'code_challenge': base64.urlsafe_b64encode(hashlib.sha256(pending['verifier'].encode()).digest()).rstrip(b'=').decode()}
            if account:
                if account.get('id_token'):
                    query['id_token_hint'] = account['id_token']
                if account.get('email'):
                    query['login_hint'] = account['email']
            elif pending['client_id'] == 'dynamic_agent_client':
                query['agent_name_hint'] = 'Traditional Garment Studio'
            return {'authorization_url': config['authorization_endpoint'] + '?' + urlencode(query)}

    def _stop(self, pending):
        pending['timer'].cancel()
        # Shutdown waits for serve_forever; never do that on its own thread.
        def close():
            pending['server'].shutdown()
            pending['server'].server_close()
        threading.Thread(target=close, daemon=True).start()

    def fail(self, pending, message):
        with self.lock:
            if self.pending is pending:
                self.pending = None
                self.last_message = message
                self._stop(pending)

    def cancel(self):
        with self.lock:
            if self.pending:
                self.fail(self.pending, '已取消登录。')
        return self.status()

    def complete(self, query, pending):
        with self.lock:
            if (self.pending is not pending or pending['deadline'] < time.time()
                    or len(query.get('state', [])) != 1
                    or not secrets.compare_digest(query['state'][0], pending['state'])):
                # An unrelated callback must not consume the legitimate pending login.
                raise VisionError('登录回调校验失败，请使用本次打开的官方登录窗口。')
            try:
                if query.get('error'):
                    raise VisionError('未获得 ChatGPT 套餐使用授权；可返回软件重试。')
                client_id = pending['client_id']
                if client_id == 'dynamic_agent_client':
                    values = query.get('client_id', [])
                    if len(values) != 1 or not values[0].startswith('oaiapp_'):
                        raise VisionError('官方登录未返回注册客户端编号，请重新登录。')
                    client_id = values[0]
                    self.retry_client_id = client_id
                elif query.get('client_id') and query['client_id'] != [client_id]:
                    raise VisionError('返回的客户端编号与本次登录不一致。')
                if len(query.get('code', [])) != 1:
                    raise VisionError('官方登录未返回有效授权码。')
                tokens = self._json('POST', pending['config']['token_endpoint'], data={
                    'grant_type': 'authorization_code', 'client_id': client_id, 'code': query['code'][0],
                    'code_verifier': pending['verifier'], 'redirect_uri': pending['redirect_uri'], 'resource': RESOURCE})
                identity = self._validate(tokens, client_id, pending)
                previous = self.data['accounts'].get(pending['account_id'])
                if previous and identity['sub'] != previous['subject']:
                    raise VisionError('登录账号与所选账号不一致，原登录记录已保留。')
                key = pending['account_id'] or hashlib.sha256((client_id + ':' + identity['sub']).encode()).hexdigest()[:24]
                record = {'client_id': client_id, 'subject': identity['sub'], 'email': identity.get('email', ''),
                          'label': (identity.get('email') or 'ChatGPT') + ' · ' + key[-6:],
                          'model': previous.get('model', '') if previous else ''}
                record.update(self._token_record(tokens))
                self.data['accounts'][key] = record
                self.data['active'] = key
                self._save()
                self.retry_client_id = None
                self.last_message = '已使用 ChatGPT 套餐；请读取可用模型并选择识图模型。'
            except (jwt.PyJWTError, KeyError, TypeError, ValueError):
                self.last_message = '官方身份签名、有效期或套餐权限验证失败，请重新登录。'
                raise VisionError(self.last_message) from None
            except VisionError as error:
                self.last_message = str(error)
                raise
            finally:
                self.pending = None
                self._stop(pending)

    def _validate(self, tokens, client_id, pending):
        header = jwt.get_unverified_header(tokens['id_token'])
        jwks = self._json('GET', pending['config']['jwks_uri'])
        algorithm = header.get('alg')
        if algorithm not in {'RS256', 'ES256'}:
            raise VisionError('OpenAI 身份签名算法不受支持。')
        candidates = [k for k in jwks['keys'] if k.get('kid') == header.get('kid')
                      and k.get('use', 'sig') == 'sig' and k.get('alg', algorithm) == algorithm]
        if len(candidates) != 1:
            raise VisionError('OpenAI 身份签名密钥校验失败。')
        key = jwt.PyJWK.from_dict(candidates[0], algorithm=algorithm).key
        claims = jwt.decode(tokens['id_token'], key, algorithms=[algorithm], audience=client_id,
                            issuer=ISSUER, leeway=5, options={'require': ['sub', 'exp', 'iat', 'nonce']})
        if (not isinstance(claims['sub'], str) or not claims['sub']
                or not secrets.compare_digest(claims['nonce'], pending['nonce'])):
            raise VisionError('OpenAI 登录随机数校验失败。')
        self._token_record(tokens)
        return claims

    @staticmethod
    def _token_record(tokens, old=None):
        scopes = tokens.get('scope', '').split()
        if DIRECT not in scopes or not tokens.get('access_token') or tokens.get('token_type', '').lower() != 'bearer':
            raise VisionError('登录成功但未授权使用 ChatGPT 套餐，请重新登录并允许套餐使用。')
        expires = float(tokens['expires_in'])
        if expires <= 0:
            raise VisionError('OpenAI 返回的登录有效期无效。')
        return {'access_token': tokens['access_token'], 'refresh_token': tokens.get('refresh_token', (old or {}).get('refresh_token', '')),
                'id_token': tokens.get('id_token', (old or {}).get('id_token', '')),
                'scopes': scopes, 'expires_at': time.time() + expires}

    def bearer(self):
        with self.lock:
            record = self.data['accounts'].get(self.data['active'])
            if not record or not record.get('access_token'):
                raise VisionError('请先在“云端视觉设置”中使用 ChatGPT 登录并授权套餐额度。')
            if record['expires_at'] <= time.time() + 60:
                if not record.get('refresh_token'):
                    raise VisionError('ChatGPT 登录已过期，请重新登录。')
                config = self._discovery()
                tokens = self._json('POST', config['token_endpoint'], data={'grant_type': 'refresh_token',
                    'client_id': record['client_id'], 'refresh_token': record['refresh_token'], 'resource': RESOURCE})
                # A refresh may omit scope to retain the previously granted scopes.
                tokens.setdefault('scope', ' '.join(record['scopes']))
                record.update(self._token_record(tokens, record))
                self._save()
            return record['access_token']

    def models(self):
        with self.lock:
            data = self._json('GET', RESOURCE + '/models', headers={'Authorization': 'Bearer ' + self.bearer()})
            models = [{'slug': m['slug'], 'display_name': m.get('display_name', m['slug'])}
                      for m in data.get('models', []) if m.get('visibility') == 'list' and isinstance(m.get('slug'), str)]
            self.catalogs[self.data['active']] = models
            return models

    def select_model(self, model):
        with self.lock:
            choices = self.models()
            if model not in [m['slug'] for m in choices]:
                raise VisionError('此模型不在当前 ChatGPT 账号的可用列表中。')
            self.data['accounts'][self.data['active']]['model'] = model
            self._save()
            return self.status()

    def credentials(self):
        with self.lock:
            token = self.bearer()
            model = self.data['accounts'][self.data['active']].get('model')
            if not model:
                raise VisionError('请先读取 ChatGPT 可用模型，选择支持图片的模型并保存。')
            return token, model

    def sign_out(self):
        with self.lock:
            self.cancel()
            record = self.data['accounts'].get(self.data['active'])
            revoked = True
            if record and record.get('refresh_token'):
                try:
                    config = self._discovery()
                    with httpx.Client(timeout=25, follow_redirects=False, transport=self.transport) as client:
                        response = client.post(config['revocation_endpoint'], data={'token': record['refresh_token'],
                            'token_type_hint': 'refresh_token', 'client_id': record['client_id']})
                    revoked = response.status_code == 200
                except (VisionError, httpx.HTTPError):
                    revoked = False
            if record:
                for field in ['access_token', 'refresh_token', 'id_token']:
                    record.pop(field, None)
            self.data['active'] = None
            self._save()
            self.last_message = '已退出本应用的 ChatGPT 登录。' if revoked else '已清除本机登录；未确认远端撤销，请在 ChatGPT 设置中断开本应用。'
            return self.status()
