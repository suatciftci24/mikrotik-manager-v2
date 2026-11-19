import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { defineConfig, loadEnv, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import release from '../release.json';

const devCheckoutIdentity: Plugin = {
  name: 'mikrotik-dev-checkout',
  apply: 'serve',
  transformIndexHtml() {
    const repo = realpathSync(fileURLToPath(new URL('..', import.meta.url)));
    const id = createHash('sha256').update(repo).digest('hex');
    return [{tag: 'meta', attrs: {name: 'mikrotik-dev-checkout', content: id}, injectTo: 'head'}];
  },
};

function buildCommit(): string | null {
  const root = realpathSync(fileURLToPath(new URL('..', import.meta.url)));
  const git = (...args: string[]) => spawnSync('git', args, {cwd: root, encoding: 'utf8'}).stdout?.trim();
  // A source archive may be extracted inside a different Git checkout.
  const head = git('rev-parse', '--show-toplevel') === root ? git('rev-parse', '--verify', 'HEAD') : undefined;
  const supplied = process.env.V2_BUILD_COMMIT;
  const commit = supplied ?? head;
  if (commit !== undefined && (!/^[0-9a-f]{40}$/.test(commit) || (head && commit !== head))) {
    throw new Error('V2_BUILD_COMMIT geçerli kaynak commit SHA değeri olmalı ve varsa checkout HEAD ile eşleşmeli.');
  }
  return commit ?? null;
}

export default defineConfig(({command, mode}) => {
  const commit = command === 'build' ? buildCommit() : null;
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
    define: {__BUILD_COMMIT__: JSON.stringify(commit)},
    plugins: [
      react(),
      devCheckoutIdentity,
      {
        name: 'mikrotik-build-identity',
        apply: 'build',
        transformIndexHtml() {
          return [
            {tag: 'meta', attrs: {name: 'mikrotik-app-version', content: release.version}},
            ...(commit ? [{tag: 'meta', attrs: {name: 'mikrotik-build-commit', content: commit}}] : []),
          ];
        },
      },
    ],
    server: {
      host: '127.0.0.1', port: uiPort, strictPort: true,
      proxy: { '/api': { target: `http://127.0.0.1:${apiPort}`, changeOrigin: false } },
    },
  };
});
