import {test} from 'node:test';
import assert from 'node:assert/strict';
import {api, ApiError} from '../src/lib/api.ts';

test('missing workspace routes provide diagnostic guidance and record errors preserve server detail', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({ok: false, status: 404, json: async () => ({detail: 'Not Found'})});
    await assert.rejects(() => api('/router-workspace/routers'), {
      constructor: ApiError,
      status: 404,
      message: 'Sentetik router API ucu bulunamadı. Bağlı API adresi ve sürümü doğrulanmalı; bu yanıt tek başına eski backend kanıtı değildir. İşlem tamamlanmadı.',
    });

    const detail = 'Kayıt bu çalışma alanında bulunamadı.';
    globalThis.fetch = async () => ({ok: false, status: 404, json: async () => ({detail})});
    await assert.rejects(() => api('/router-workspace/routers/missing'), {
      constructor: ApiError,
      status: 404,
      message: detail,
    });
  } finally {
    globalThis.fetch = original;
  }
});
