import { createHash } from 'node:crypto';
import { realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { defineConfig, loadEnv, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

const devCheckoutIdentity: Plugin = {
  name: 'mikrotik-dev-checkout',
  apply: 'serve',
  transformIndexHtml() {
    const repo = realpathSync(fileURLToPath(new URL('..', import.meta.url)));
    const id = createHash('sha256').update(repo).digest('hex');
    return [{tag: 'meta', attrs: {name: 'mikrotik-dev-checkout', content: id}, injectTo: 'head'}];
  },
};

export default defineConfig(({mode}) => {
  const env = loadEnv(mode, '.', 'V2_');
  const port = (name: string, fallback: number) => {
    const raw = env[name] ?? String(fallback);
    if (!/^[0-9]+$/.test(raw) || Number(raw) < 1024 || Number(raw) > 65535)
      throw new Error(`${name}: 1024–65535 arasında bir port gerekli.`);
    return Number(raw);
  };
  const apiPort = port('V2_API_PORT', 8000), uiPort = port('V2_UI_PORT', 5173);
  if (apiPort === uiPort) throw new Error('V2_API_PORT ve V2_UI_PORT farklı olmalı.');
  return {
    plugins: [react(), devCheckoutIdentity],
    server: {
      host: '127.0.0.1', port: uiPort, strictPort: true,
      proxy: { '/api': { target: `http://127.0.0.1:${apiPort}`, changeOrigin: false } },
    },
  };
});
