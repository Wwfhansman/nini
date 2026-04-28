import React from 'react';

const TYPE_COLORS = {
  health_goal: 'var(--c-herb)',
  allergy_or_restriction: 'var(--c-danger)',
  preference: 'var(--c-terra)',
  cooking_note: 'var(--c-saffron)',
  profile: 'var(--c-mid)',
};
const TYPE_LABELS = {
  health_goal: '健康目标',
  allergy_or_restriction: '饮食限制',
  preference: '口味偏好',
  cooking_note: '烹饪记录',
  profile: '家庭成员',
};
const SOURCE_LABELS = {
  user_explicit: '用户告诉我',
  inferred: '妮妮推断',
  vision: '视觉识别',
  review: '烹饪复盘',
};

function memoryText(m) {
  const v = m?.value_json;
  if (!v) return '';
  if (typeof v === 'string') return v;
  return v.text || v.value || JSON.stringify(v);
}

function shortTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function MemoryPanel({ memories, highlight, pendingAction }) {
  const list = memories || [];
  const latestId = list[list.length - 1]?.id;
  const pendingDelete =
    pendingAction?.type === 'delete_memory' ? pendingAction : null;
  return (
    <div
      className="rp-section scroll"
      style={{ flex: '0 0 auto', maxHeight: 220 }}
    >
      <div className="rp-head">
        <span className="section-label">张家厨房记忆</span>
        <span className="rp-aux">{list.length} 条</span>
      </div>
      {pendingDelete ? (
        <div className="memory-pending">
          等待确认删除：{pendingDelete.summary || '这条记忆'}
        </div>
      ) : null}
      {list.length === 0 ? (
        <div className="memory-empty">
          暂无家庭记忆。你告诉妮妮的口味和饮食习惯会出现在这里。
        </div>
      ) : (
        list.map((m) => {
          const color = TYPE_COLORS[m.type] || 'var(--c-terra)';
          const isLatest = highlight && m.id === latestId;
          const updatedAt = shortTime(m.updated_at);
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
              <div className="memory-main">
                <span className="memory-text">{memoryText(m)}</span>
                <span className="memory-meta">
                  {SOURCE_LABELS[m.source] || '家庭记忆'}
                  {updatedAt ? ` · ${updatedAt}` : ''}
                </span>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
