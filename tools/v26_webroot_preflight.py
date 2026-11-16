"""Read-only identity proof for the one confirmed Nginx/Vite V26 topology."""
import hashlib
from html.parser import HTMLParser
import http.client
import json
from pathlib import Path
import re
import shlex
import urllib.request
from urllib.parse import urlsplit

DOMAIN='v26.mikmanager.com.tr'
ORIGIN='https://'+DOMAIN
APP=Path('/srv/mikrotik-v26-next')


def require(value,code):
    if not value:raise RuntimeError(code)


def nginx_tree(text):
    lexer=shlex.shlex(text,posix=True,punctuation_chars='{};')
    lexer.whitespace_split=True
    lexer.commenters='#'
    tokens=[]
    try:
        for value in lexer:
            tokens.extend(list(value) if value and all(c in '{};' for c in value) else [value])
    except ValueError:raise RuntimeError('NGINX_CONFIG_PARSE_REJECTED') from None
    offset=0
    def parse(nested=False):
        nonlocal offset
        nodes=[]
        while offset<len(tokens):
            if tokens[offset]=='}':
                require(nested,'NGINX_CONFIG_PARSE_REJECTED');offset+=1;return nodes
            head=[]
            while offset<len(tokens) and tokens[offset] not in '{};':
                head.append(tokens[offset]);offset+=1
            require(head and offset<len(tokens),'NGINX_CONFIG_PARSE_REJECTED')
            end=tokens[offset];offset+=1
            require(end in (';','{'),'NGINX_CONFIG_PARSE_REJECTED')
            nodes.append((head,parse(True) if end=='{' else None))
        require(not nested,'NGINX_CONFIG_PARSE_REJECTED')
        return nodes
    return parse()


def walk(nodes):
    for head,children in nodes:
        yield head,children
        if children is not None:yield from walk(children)


def nginx_routes(config):
    nodes=nginx_tree(config)
    parts=re.split(r'^# configuration file ([^\r\n]+):\s*$',config,flags=re.MULTILINE)
    files={parts[i]:parts[i+1] for i in range(1,len(parts)-1,2)}
    servers=[]
    upstreams={}
    for head,children in walk(nodes):
        if head[0]=='upstream':
            require(len(head)==2 and head[1] not in upstreams,'NGINX_UPSTREAM_REJECTED')
            upstreams[head[1]]=children
        if head==['server'] and children is not None:
            names=[h[1:] for h,c in children if h[0]=='server_name']
            tls=any(h[0]=='listen' and 'ssl' in h[1:] and
                    any(v=='443' or v.endswith(':443') for v in h[1:]) for h,c in children)
            if names==[[DOMAIN]] and tls:servers.append(children)
    require(len(servers)==1,'NGINX_V26_TLS_SERVER_REJECTED')
    server=servers[0]
    for head,children in server:
        if head[0]=='include':
            require(len(head)==2 and head[1]=='/etc/letsencrypt/options-ssl-nginx.conf' and head[1] in files,
                    'NGINX_INCLUDE_UNVERIFIED')
            fragment=nginx_tree(files[head[1]])
            require(all(c is None and (h[0].startswith('ssl_') or h[0] in ('resolver','resolver_timeout'))
                        for h,c in fragment),'NGINX_INCLUDE_OVERRIDE_REJECTED')
    require(not any(h[0] in ('rewrite','return','if','try_files','error_page') for h,c in server),
            'NGINX_SERVER_OVERRIDE_REJECTED')
    def peer(value,port,api):
        require('$' not in value,'NGINX_DYNAMIC_UPSTREAM_REJECTED')
        target=value
        match=re.fullmatch(r'http://([A-Za-z0-9_-]+)(/?)',value)
        if match and match[1] in upstreams:
            entries=upstreams[match[1]]
            require(entries is not None and len(entries)==1 and entries[0][0][0]=='server' and
                    entries[0][1] is None and len(entries[0][0])==2,'NGINX_UPSTREAM_REJECTED')
            target='http://'+entries[0][0][1]+match[2]
        allowed={'http://127.0.0.1:'+str(port)}
        if not api:allowed.add('http://127.0.0.1:'+str(port)+'/')
        require(target in allowed,'NGINX_PROXY_TARGET_REJECTED')
    routes={}
    for head,children in server:
        if head[0]!='location':continue
        require(children is not None,'NGINX_LOCATION_REJECTED')
        args=head[1:]
        if args and args[0]=='^~':args=args[1:]
        require(len(args)==1 and args[0] in ('/','/api','/api/'),'NGINX_LOCATION_OVERRIDE_REJECTED')
        path=args[0];role='web' if path=='/' else 'api'
        require(role not in routes,'NGINX_AMBIGUOUS_ROUTE_REJECTED')
        passes=[h[1:] for h,c in children if h[0]=='proxy_pass']
        require(len(passes)==1 and len(passes[0])==1,'NGINX_PROXY_REQUIRED')
        require(not any(c is not None or h[0] in ('rewrite','return','try_files','root','alias','error_page','include')
                        for h,c in children),'NGINX_LOCATION_OVERRIDE_REJECTED')
        peer(passes[0][0],15173 if role=='web' else 18996,role=='api')
        routes[role]=path
    require(set(routes)=={'api','web'},'NGINX_V26_ROUTES_REQUIRED')
    return dict(domain=DOMAIN,web_port=15173,api_port=18996)


class ResponseBody(bytes):
    def __new__(cls,body,status=200,content_type=''):
        value=super().__new__(cls,body)
        value.status=status
        mime=content_type.split(';',1)[0].strip().lower()
        value.mime=mime if mime in ('text/html','application/xhtml+xml','text/javascript',
                                   'application/javascript','application/json','text/plain') else 'OTHER'
        return value


class WebrootFailure(RuntimeError):
    def __init__(self,code,diagnostics):
        self.diagnostics=diagnostics
        super().__init__(code)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def https(path):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(ORIGIN+path,timeout=10) as response:
        require(response.status==200,'WEBROOT_HTTPS_STATUS_REJECTED')
        return ResponseBody(response.read(),response.status,response.headers.get('Content-Type',''))


def loopback(port,path):
    require(port in (15173,18996) and path.startswith('/') and not path.startswith('//'),'WEBROOT_TARGET_REJECTED')
    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=10)
    try:
        connection.request('GET',path)
        response=connection.getresponse()
        require(response.status==200,'WEBROOT_LOOPBACK_STATUS_REJECTED')
        return ResponseBody(response.read(),response.status,response.getheader('Content-Type',''))
    finally:connection.close()


def listener_identity(run,unit,port,cwd):
    pid=run(['systemctl','show',unit,'--value','--property=MainPID'],stage='WEBROOT_UNIT_PID')
    require(pid.isdigit() and int(pid)>1,'WEBROOT_UNIT_PID_REJECTED')
    output=run(['sudo','-n','ss','-H','-ltnp','sport = :'+str(port)],stage='WEBROOT_LISTENER')
    rows=output.splitlines()
    require(len(rows)==1 and len(rows[0].split())>=4 and
            rows[0].split()[3]=='127.0.0.1:'+str(port),'WEBROOT_LISTENER_ADDRESS_REJECTED')
    owners=set(re.findall(r'pid=(\d+)',output))
    require(len(owners)==1,'WEBROOT_LISTENER_OWNER_REJECTED')
    owner=owners.pop()
    actual=run(['sudo','-n','readlink','-e','/proc/'+owner+'/cwd'],stage='WEBROOT_LISTENER_CWD')
    require(actual==str(cwd),'WEBROOT_LISTENER_CWD_REJECTED')
    current=owner;seen=set()
    for _ in range(32):
        if current==pid:return
        require(current not in seen and int(current)>1,'WEBROOT_LISTENER_ANCESTRY_REJECTED')
        seen.add(current)
        status=run(['sudo','-n','cat','/proc/'+current+'/status'],stage='WEBROOT_LISTENER_PARENT')
        match=re.search(r'^PPid:\s+(\d+)\s*$',status,re.MULTILINE)
        require(match is not None,'WEBROOT_LISTENER_ANCESTRY_REJECTED')
        current=match[1]
    raise RuntimeError('WEBROOT_LISTENER_ANCESTRY_REJECTED')


class EntryHTML(HTMLParser):
    def __init__(self):super().__init__();self.scripts=[];self.entries=[];self.root=False;self.root_count=0
    def handle_starttag(self,tag,attributes):
        values=dict(attributes)
        if tag=='script' and 'src' in values:
            self.scripts.append(values['src'])
            self.entries.append((values['src'],values.get('type','')))
        if tag=='div' and values.get('id')=='root':self.root=True;self.root_count+=1


def script_identity(src):
    # Only Vite's documented decimal HMR timestamp may vary. No host/path decoding,
    # arbitrary query removal, fragments, import/url/raw modes or redirect aliases.
    try:value=urlsplit(src)
    except ValueError:return dict(kind='other',valid=False)
    kinds={'/@vite/client':'vite_client','/src/main.tsx':'source_entry','/theme.js':'theme'}
    kind=kinds.get(value.path,'built_asset' if value.path.startswith('/assets/') else 'other')
    valid=(not value.scheme and not value.netloc and not value.fragment and
           (not value.query or re.fullmatch(r't=[0-9]{1,20}',value.query) is not None))
    return dict(kind=kind,valid=bool(valid),hmr_timestamp=bool(value.query and valid))


def html_identity(page,direct):
    def body(value):
        return dict(status=getattr(value,'status',200),content_type=getattr(value,'mime','NOT_CAPTURED'),
                    bytes=len(value),sha256=hashlib.sha256(value).hexdigest())
    document=EntryHTML()
    try:document.feed(page.decode('utf-8'))
    except UnicodeError:raise WebrootFailure('VITE_HTML_ENCODING_REJECTED',dict(https=body(page),loopback=body(direct))) from None
    scripts=[]
    for src,kind in document.entries:
        info=script_identity(src)
        info.update(module=kind=='module',url_sha256=hashlib.sha256(src.encode()).hexdigest())
        scripts.append(info)
    checks=dict(upstream_bytes_equal=page==direct,
                html_content_type=all(getattr(value,'mime','NOT_CAPTURED') in ('text/html','NOT_CAPTURED') for value in (page,direct)),
                unique_root_mount=document.root_count==1,
                vite_client_module=sum(v['kind']=='vite_client' and v['valid'] and v['module'] for v in scripts)==1,
                source_entry_module=sum(v['kind']=='source_entry' and v['valid'] and v['module'] for v in scripts)==1,
                no_built_assets=not any(v['kind']=='built_asset' for v in scripts),
                valid_identity_urls=all(v['valid'] for v in scripts if v['kind'] in ('vite_client','source_entry')))
    diagnostics=dict(expected=dict(client='/@vite/client',entry='/src/main.tsx',mount='div#root',type='module',
                                   allowed_query='optional_single_decimal_t'),
                     https=body(page),loopback=body(direct),root_count=document.root_count,
                     script_count=len(scripts),scripts=scripts[:32],scripts_truncated=len(scripts)>32,checks=checks)
    index=APP/'frontend/index.html'
    if index.is_file() and index.resolve()==index:
        local=index.read_bytes()
        parsed=EntryHTML()
        try:parsed.feed(local.decode('utf-8'))
        except UnicodeError:raise WebrootFailure('VITE_LOCAL_INDEX_ENCODING_REJECTED',diagnostics) from None
        diagnostics['project_index']=dict(sha256=hashlib.sha256(local).hexdigest(),bytes=len(local),
            root_count=parsed.root_count,source_entries=sum(script_identity(src)['kind']=='source_entry' for src in parsed.scripts),
            built_assets=sum(script_identity(src)['kind']=='built_asset' for src in parsed.scripts))
    if not checks['upstream_bytes_equal']:raise WebrootFailure('VITE_HTTPS_UPSTREAM_MISMATCH',diagnostics)
    if not all(checks.values()):raise WebrootFailure('VITE_DEV_HTML_IDENTITY_REJECTED',diagnostics)
    return diagnostics


def raw_module(body):
    text=body.decode('utf-8').strip()
    require(text.startswith('export default '),'VITE_RAW_MODULE_REJECTED')
    remainder=text[len('export default '):]
    try:value,end=json.JSONDecoder().raw_decode(remainder)
    except ValueError:raise RuntimeError('VITE_RAW_MODULE_REJECTED') from None
    tail=remainder[end:]
    require(isinstance(value,str) and re.fullmatch(r'\s*;?\s*(?://[^\r\n]*(?:\r?\n|$)\s*)*',tail),
            'VITE_RAW_MODULE_REJECTED')
    return value.encode('utf-8')


def verify(run,units):
    require(APP.resolve()==APP and (APP/'frontend').resolve()==APP/'frontend','WEBROOT_PROJECT_PATH_REJECTED')
    require(len(units)==2 and sum(api for _,api in units)==1,'WEBROOT_UNIT_SCOPE_REJECTED')
    config=run(['sudo','-n','nginx','-T'],stage='NGINX_READONLY_CONFIG')
    routes=nginx_routes(config)
    for unit,api in units:
        listener_identity(run,unit,18996 if api else 15173,APP if api else APP/'frontend')
    page=https('/')
    html=html_identity(page,loopback(15173,'/'))
    vite_client=https('/@vite/client')
    require(vite_client==loopback(15173,'/@vite/client') and b'createHotContext' in vite_client,
            'VITE_CLIENT_IDENTITY_REJECTED')
    for relative in ('src/lib/api.ts','src/lib/presentation.ts'):
        file=APP/'frontend'/relative
        require(file.is_file() and file.resolve()==file,'VITE_SOURCE_PATH_REJECTED')
        path='/'+relative+'?raw'
        served=https(path)
        require(served==loopback(15173,path) and raw_module(served)==file.read_bytes(),
                'VITE_PROJECT_SOURCE_MISMATCH')
    api=https('/api/ready')
    require(json.loads(api)==json.loads(loopback(18996,'/api/ready')),'NGINX_API_UPSTREAM_MISMATCH')
    value=json.loads(api)
    require(value.get('service')=='mikrotik-manager-v2' and value.get('runtime_profile')=='v26-isolated-acceptance'
            and value.get('api_version')=='v1' and value.get('api_port')==18996,'WEBROOT_API_IDENTITY_REJECTED')
    return dict(mode='vite-dev',project=str(APP/'frontend'),**routes,
                nginx_sha256=hashlib.sha256(config.encode()).hexdigest(),html_identity=html,
                https='PASS',api='PASS',production_ready=False)
