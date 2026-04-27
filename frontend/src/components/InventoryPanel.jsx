import React from 'react';

function modeLabel(mode) {
  const value = (mode || 'mock').toLowerCase();
  if (value === 'real') return '在线模式';
  if (value === 'hybrid') return '混合模式';
  if (value === 'auto') return '自动模式';
  return '演示模式';
}

function serviceStatus(ok, onlineText = '在线可用', fallbackText = '本地兜底') {
  return ok ? onlineText : fallbackText;
}

function logServiceName(provider) {
  const value = String(provider || '').toLowerCase();
  if (value.includes('vision')) return '视觉服务';
  if (value.includes('tts')) return '语音播报';
  if (value.includes('asr')) return '语音识别';
  if (value.includes('qiniu')) return '智能服务';
  return '服务';
}

function logStatusText(status) {
  if (status === 'success') return '正常';
  if (status === 'error') return '异常';
  if (status === 'fallback') return '本地兜底';
  return status || '—';
}

export default function InventoryPanel({ inventory, providerLogs, health }) {
  const items = inventory || [];
  const logs = (providerLogs || []).slice(-3);
  const providers = health?.providers || {};

  return (
    <div className="rp-section flex scroll">
      <div className="rp-head">
        <span className="section-label">当前库存</span>
        <span className="rp-aux">{items.length} 项</span>
      </div>
      {items.length === 0 ? (
        <div className="memory-empty">暂无库存条目</div>
      ) : (
        items.map((it) => {
          const changed =
            (it.source || '').includes('vision') ||
            (it.source || '').includes('review');
          return (
            <div className="inv-row" key={it.id || it.name}>
              <span className="inv-name">{it.name}</span>
              <span className={`inv-amount ${changed ? 'changed' : ''}`}>
                {it.amount || '—'}
                {changed ? ' ▲' : ''}
              </span>
            </div>
          );
        })
      )}

      <div className="provider-block">
        <div
          className="rp-head"
          style={{ marginBottom: 4, marginTop: 4 }}
        >
          <span className="section-label">服务状态</span>
        </div>
        <div className="provider-row">
          <span className="key">智能服务</span>
          <span className="val">{modeLabel(health?.demo_mode)}</span>
        </div>
        <div className="provider-row">
          <span className="key">任务理解</span>
          <span
            className={`val ${
              providers.qiniu_configured ? 'ok' : 'warn'
            }`}
          >
            {serviceStatus(providers.qiniu_configured)}
          </span>
        </div>
        <div className="provider-row">
          <span className="key">视觉服务</span>
          <span
            className={`val ${
              providers.vision_model_configured ? 'ok' : 'warn'
            }`}
          >
            {serviceStatus(providers.vision_model_configured)}
          </span>
        </div>
        <div className="provider-row">
          <span className="key">语音服务</span>
          <span
            className={`val ${
              providers.speech_provider_mode === 'mock' ? 'warn' : 'ok'
            }`}
          >
            {modeLabel(providers.speech_provider_mode)}
          </span>
        </div>
        {logs.map((log) => (
          <div className="provider-row" key={log.id}>
            <span className="key" title={log.provider}>
              {logServiceName(log.provider)}
            </span>
            <span
              className={`val ${
                log.status === 'success'
                  ? 'ok'
                  : log.status === 'error'
                  ? 'bad'
                  : 'warn'
              }`}
              title={log.status}
            >
              {logStatusText(log.status)}
              {Number.isFinite(log.latency_ms)
                ? ` · ${log.latency_ms}ms`
                : ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
