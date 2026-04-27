import React from 'react';

const TYPE_COLORS = {
  health_goal: 'var(--c-herb)',
  allergy_or_restriction: 'var(--c-danger)',
  preference: 'var(--c-terra)',
  cooking_note: 'var(--c-saffron)',
  profile: 'var(--c-mid)',
};
const TYPE_LABELS = {
  health_goal: 'HEALTH',
  allergy_or_restriction: 'RESTRICT',
  preference: 'PREF',
  cooking_note: 'NOTE',
  profile: 'PROFILE',
};

function memoryText(m) {
  const v = m?.value_json;
  if (!v) return '';
  if (typeof v === 'string') return v;
  return v.text || v.value || JSON.stringify(v);
}

export default function MemoryPanel({ memories, highlight }) {
  const list = memories || [];
  const latestId = list[list.length - 1]?.id;
  return (
    <div
      className="rp-section scroll"
      style={{ flex: '0 0 auto', maxHeight: 220 }}
    >
      <div className="rp-head">
        <span className="section-label">张家厨房记忆</span>
        <span className="rp-aux">{list.length} entries</span>
      </div>
      {list.length === 0 ? (
        <div className="memory-empty">
          暂无记忆。规划晚餐时妮妮会写入 health_goal / restriction / preference。
        </div>
      ) : (
        list.map((m) => {
          const color = TYPE_COLORS[m.type] || 'var(--c-terra)';
          const isLatest = highlight && m.id === latestId;
          return (
            <div
              key={m.id}
              className={`memory-row ${isLatest ? 'highlight' : ''}`}
            >
              <span
                className="memory-tag"
                style={{ color, border: `1px solid ${color}` }}
              >
                {TYPE_LABELS[m.type] || m.type}
              </span>
              <span className="memory-text">{memoryText(m)}</span>
            </div>
          );
        })
      )}
    </div>
  );
}
