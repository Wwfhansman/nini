import React from 'react';

export default function InventoryPanel({ inventory, providerLogs, health }) {
  const items = inventory || [];
  const providers = health?.providers || {};
  const hasLiveConnection = Boolean(
    providers.qiniu_configured ||
      providers.vision_model_configured ||
      providers.volc_tts_configured ||
      providers.volc_asr_configured ||
      providerLogs?.some((log) => log.status === 'success'),
  );

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

      <div className="provider-block compact">
        <div className="provider-row">
          <span className="key">终端连接</span>
          <span className={`val ${hasLiveConnection ? 'ok' : 'warn'}`}>
            {hasLiveConnection ? '已连接' : '本机可用'}
          </span>
        </div>
      </div>
    </div>
  );
}
