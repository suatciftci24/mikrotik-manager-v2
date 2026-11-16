"""Read-only identity proof for the one confirmed Nginx/Vite V26 topology."""
import hashlib
from html.parser import HTMLParser
import http.client
import json
from pathlib import Path
import re
import shlex
import urllib.request

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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def https(path):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(ORIGIN+path,timeout=10) as response:
        require(response.status==200,'WEBROOT_HTTPS_STATUS_REJECTED')
        return response.read()


def loopback(port,path):
    require(port in (15173,18996) and path.startswith('/') and not path.startswith('//'),'WEBROOT_TARGET_REJECTED')
    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=10)
    try:
        connection.request('GET',path)
        response=connection.getresponse()
        require(response.status==200,'WEBROOT_LOOPBACK_STATUS_REJECTED')
        return response.read()
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
    def __init__(self):super().__init__();self.scripts=[];self.root=False
    def handle_starttag(self,tag,attributes):
        values=dict(attributes)
        if tag=='script' and 'src' in values:self.scripts.append(values['src'])
        if tag=='div' and values.get('id')=='root':self.root=True


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
    require(page==loopback(15173,'/'),'VITE_HTTPS_UPSTREAM_MISMATCH')
    document=EntryHTML();document.feed(page.decode('utf-8'))
    require(document.root and '/@vite/client' in document.scripts and '/src/main.tsx' in document.scripts and
            not any(path.startswith('/assets/') for path in document.scripts),'VITE_DEV_HTML_IDENTITY_REJECTED')
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
                nginx_sha256=hashlib.sha256(config.encode()).hexdigest(),https='PASS',api='PASS')
