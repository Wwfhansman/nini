// All backend HTTP calls live here. Components must not call fetch directly.

// By default, hit relative URLs so the Vite dev/preview proxy (or any same-origin
// deployment) routes /api, /health, /static to the backend without CORS.
// Set VITE_API_BASE_URL to a full origin only when you need to bypass the proxy.
const RAW_BASE = (import.meta.env.VITE_API_BASE_URL || '').trim();
const RAW_WS_BASE = (import.meta.env.VITE_WS_BASE_URL || '').trim();
const RAW_PROXY_TARGET = (import.meta.env.VITE_API_PROXY_TARGET || '').trim();
export const API_BASE_URL = RAW_BASE.replace(/\/+$/, '');
export const DEFAULT_TERMINAL_ID =
  (import.meta.env.VITE_DEFAULT_TERMINAL_ID || 'demo-kitchen-001').trim();

class ApiError extends Error {
  constructor(message, { status, payload } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

async function parseJsonOrThrow(response) {
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { raw: text };
    }
  }
  if (!response.ok) {
    const message =
      payload?.error?.message ||
      payload?.detail ||
      `HTTP ${response.status} ${response.statusText}`;
    throw new ApiError(message, { status: response.status, payload });
  }
  return payload;
}

function buildUrl(path, params) {
  // Use a fake base only to leverage URLSearchParams; we strip it back to a
  // relative URL so the dev/preview proxy (and same-origin prod) handles it.
  const base = API_BASE_URL || 'http://_relative_';
  const url = new URL(base + path);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
    }
  }
  if (!API_BASE_URL) {
    return url.pathname + (url.search || '');
  }
  return url.toString();
}

async function getJson(path, params) {
  const res = await fetch(buildUrl(path, params), { method: 'GET' });
  return parseJsonOrThrow(res);
}

async function postJson(path, body) {
  const res = await fetch(API_BASE_URL + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  return parseJsonOrThrow(res);
}

async function postForm(path, formData) {
  const res = await fetch(API_BASE_URL + path, {
    method: 'POST',
    body: formData,
  });
  return parseJsonOrThrow(res);
}

export async function getHealth() {
  const res = await fetch(buildUrl('/health'));
  return parseJsonOrThrow(res);
}

export async function getState(terminalId) {
  return getJson('/api/state', { terminal_id: terminalId });
}

export async function postChat(terminalId, text, source = 'text') {
  return postJson('/api/chat', { terminal_id: terminalId, text, source });
}

export async function postControl(terminalId, command) {
  return postJson('/api/control', { terminal_id: terminalId, command });
}

export async function postVision(terminalId, file, purpose = 'ingredients') {
  const fd = new FormData();
  fd.append('terminal_id', terminalId);
  fd.append('purpose', purpose);
  if (file) fd.append('image', file);
  return postForm('/api/vision', fd);
}

export async function postSpeechTts(terminalId, text, ttsVendor) {
  return postJson('/api/speech/tts', {
    terminal_id: terminalId,
    text,
    tts_vendor: ttsVendor,
  });
}

export async function postSpeechAsr(terminalId, audioFile) {
  const fd = new FormData();
  fd.append('terminal_id', terminalId);
  if (audioFile) fd.append('audio', audioFile);
  return postForm('/api/speech/asr', fd);
}

export function getVoiceWebSocketUrl() {
  const explicitBase =
    RAW_WS_BASE ||
    API_BASE_URL ||
    (import.meta.env.DEV
      ? RAW_PROXY_TARGET || 'http://127.0.0.1:8000'
      : '');
  const base =
    explicitBase ||
    (typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
  const url = new URL('/ws/voice', base);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url.toString();
}

export async function getMemoryMarkdown(terminalId) {
  const res = await fetch(buildUrl('/api/export/memory', { terminal_id: terminalId }));
  if (!res.ok) {
    throw new ApiError(`HTTP ${res.status}`, { status: res.status });
  }
  return res.text();
}

export { ApiError };
