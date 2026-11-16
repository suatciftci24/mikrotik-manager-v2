"""Read-only Nginx/Vite identity tests; no real sockets, SSH or service actions."""
import importlib.util
import json
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('webroot',ROOT/'tools/v26_webroot_preflight.py')
web=importlib.util.module_from_spec(spec);spec.loader.exec_module(web)
CONFIG='''server { listen 443 ssl; server_name v26.mikmanager.com.tr;
 location / { proxy_pass http://127.0.0.1:15173; proxy_set_header Host $host; }
 location /api/ { proxy_pass http://127.0.0.1:18996; }
}'''


class WebrootPreflight(TestCase):
    def test_only_exact_tls_domain_and_loopback_routes_accepted(self):
        self.assertEqual(web.nginx_routes(CONFIG),dict(domain=web.DOMAIN,web_port=15173,api_port=18996))
        upstream='upstream frontend_v26 { server 127.0.0.1:15173; }\n'+CONFIG.replace('http://127.0.0.1:15173','http://frontend_v26')
        self.assertEqual(web.nginx_routes(upstream)['web_port'],15173)
        invalid=[CONFIG.replace(web.DOMAIN,'other.example'),CONFIG.replace('443 ssl','80'),
                 CONFIG.replace('15173','5173'),CONFIG.replace('18996','8000'),
                 CONFIG.replace('127.0.0.1:15173','other.example:15173'),
                 CONFIG.replace('http://127.0.0.1:15173','http://$target'),CONFIG+CONFIG,
                 CONFIG.replace('location /api/','location ~ /api/'),
                 CONFIG.replace('location /api/','location /src/'),
                 CONFIG.replace('http://127.0.0.1:18996;','http://127.0.0.1:18996/;'),
                 CONFIG.replace('proxy_pass http://127.0.0.1:15173;','root /srv/other/dist;')]
        for value in invalid:
            with self.subTest(value=value),self.assertRaises(RuntimeError):web.nginx_routes(value)

    def test_ssl_include_content_verified_and_override_rejected(self):
        config='# configuration file /etc/nginx/sites-enabled/v26:\n'+CONFIG.replace('listen 443 ssl;','listen 443 ssl; include /etc/letsencrypt/options-ssl-nginx.conf;')
        fragment='\n# configuration file /etc/letsencrypt/options-ssl-nginx.conf:\nssl_protocols TLSv1.2 TLSv1.3;\n'
        self.assertEqual(web.nginx_routes(config+fragment)['api_port'],18996)
        with self.assertRaises(RuntimeError):web.nginx_routes(config)
        with self.assertRaises(RuntimeError):web.nginx_routes(config+fragment+'rewrite ^ /other;')

    def test_raw_module_is_literal_only_and_preserves_utf8_source(self):
        raw='const mesaj="Türkçe";\r\n'
        self.assertEqual(web.raw_module(('export default '+json.dumps(raw)+';\n//# sourceMappingURL=data:fixture').encode()),raw.encode())
        for body in [b'<html>wrong project</html>',b'export default "value"; alert(1)',b'export default {};']:
            with self.assertRaises(RuntimeError):web.raw_module(body)

    def test_listener_requires_exact_port_project_and_unit_ancestry(self):
        def run(args,**kw):
            stage=kw['stage']
            if stage=='WEBROOT_UNIT_PID':return '100'
            if stage=='WEBROOT_LISTENER':return 'LISTEN 0 511 127.0.0.1:15173 0.0.0.0:* users:(("node",pid=101,fd=1))'
            if stage=='WEBROOT_LISTENER_CWD':return str(web.APP/'frontend')
            return 'Name:\tnode\nPPid:\t100\n'
        web.listener_identity(run,'fixture-v26.service',15173,web.APP/'frontend')
        for wrongstage,value in [('WEBROOT_LISTENER_CWD','/srv/v25/frontend'),
                                 ('WEBROOT_LISTENER','LISTEN 0 511 0.0.0.0:15173 0.0.0.0:* users:(("node",pid=101,fd=1))'),
                                 ('WEBROOT_LISTENER_PARENT','PPid:\t1\n')]:
            with self.subTest(stage=wrongstage),self.assertRaises(RuntimeError):
                web.listener_identity(lambda args,**kw:value if kw['stage']==wrongstage else run(args,**kw),
                                      'fixture-v26.service',15173,web.APP/'frontend')

    def test_vite_identity_uses_live_source_not_dist_and_rejects_wrong_project(self):
        with tempfile.TemporaryDirectory() as temp:
            app=Path(temp)
            (app/'frontend/src/lib').mkdir(parents=True)
            for name in ['api.ts','presentation.ts']:(app/'frontend/src/lib'/name).write_text('export const marker="'+name+'";')
            page=b'<script type="module" src="/@vite/client"></script><div id="root"></div><script type="module" src="/src/main.tsx"></script>'
            response={'/':page,'/@vite/client':b'export function createHotContext() {}',
                      '/api/ready':json.dumps(dict(service='mikrotik-manager-v2',runtime_profile='v26-isolated-acceptance',api_version='v1',api_port=18996)).encode()}
            for name in ['api.ts','presentation.ts']:
                response['/src/lib/'+name+'?raw']=('export default '+json.dumps((app/'frontend/src/lib'/name).read_text())).encode()
            units=[('v26-api.service',True),('v26-web.service',False)]
            with patch.object(web,'APP',app),patch.object(web,'listener_identity'), \
                 patch.object(web,'https',side_effect=lambda path:response[path]), \
                 patch.object(web,'loopback',side_effect=lambda port,path:response[path]):
                result=web.verify(lambda *a,**kw:CONFIG,units)
                self.assertEqual(result['mode'],'vite-dev')
                self.assertEqual(result['project'],str(app/'frontend'))
                response['/src/lib/api.ts?raw']=b'export default "different project source"'
                with self.assertRaisesRegex(RuntimeError,'VITE_PROJECT_SOURCE_MISMATCH'):web.verify(lambda *a,**kw:CONFIG,units)
                response['/']=b'<script src="/assets/compiled.js"></script><div id="root"></div>'
                with self.assertRaisesRegex(RuntimeError,'VITE_DEV_HTML_IDENTITY_REJECTED'):web.verify(lambda *a,**kw:CONFIG,units)
