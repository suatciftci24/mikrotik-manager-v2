import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

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
    plugins: [react()],
    server: {
      host: '127.0.0.1', port: uiPort, strictPort: true,
      proxy: { '/api': { target: `http://127.0.0.1:${apiPort}`, changeOrigin: false } },
    },
  };
});
