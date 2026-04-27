import React from 'react';

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
          <span className="section-label">Provider 状态</span>
        </div>
        <div className="provider-row">
          <span className="key">DEMO_MODE</span>
          <span className="val">{health?.demo_mode || '—'}</span>
        </div>
        <div className="provider-row">
          <span className="key">QINIU</span>
          <span
            className={`val ${
              providers.qiniu_configured ? 'ok' : 'warn'
            }`}
          >
            {providers.qiniu_configured ? 'configured' : 'mock only'}
          </span>
        </div>
        <div className="provider-row">
          <span className="key">VISION</span>
          <span
            className={`val ${
              providers.vision_model_configured ? 'ok' : 'warn'
            }`}
          >
            {providers.vision_model_configured ? 'configured' : 'mock'}
          </span>
        </div>
        <div className="provider-row">
          <span className="key">SPEECH</span>
          <span
            className={`val ${
              providers.speech_provider_mode === 'mock' ? 'warn' : 'ok'
            }`}
          >
            {providers.speech_provider_mode || '—'}
          </span>
        </div>
        {logs.map((log) => (
          <div className="provider-row" key={log.id}>
            <span className="key">{log.provider}</span>
            <span
              className={`val ${
                log.status === 'success'
                  ? 'ok'
                  : log.status === 'error'
                  ? 'bad'
                  : 'warn'
              }`}
            >
              {log.status}
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
