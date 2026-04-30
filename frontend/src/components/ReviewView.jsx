import React from 'react';
import { UiPatchAttention, UiPatchCards, UiPatchPhrases } from './UiPatch.jsx';

function memoryText(m) {
  const v = m?.value_json;
  if (!v) return '';
  if (typeof v === 'string') return v;
  return v.text || v.value || JSON.stringify(v);
}

export default function ReviewView({
  state,
  memories,
  inventory,
  memoryMarkdown,
  onExportMemory,
  onControl,
  loading,
}) {
  const recipe = state?.recipe || null;
  const uiPatch = state?.ui_patch || {};
  const minutes = recipe?.estimated_minutes;
  const stepCount = recipe?.steps?.length || 0;
  const adjustments = state?.active_adjustments || [];
  const review = state?.review || {};
  const inventoryChanges = review.inventory_changes || [];
  const nextTime = review.next_time || [
    '番茄类菜品默认降低酸度',
    '继续保持不辣',
    '优先少油做法',
  ];

  return (
    <div className="view-wrap">
      <div className="view-header">
        <div className="view-eyebrow herb">烹饪完成</div>
        <div className="view-title">{uiPatch.title || '本次烹饪复盘'}</div>
        {uiPatch.subtitle ? <div className="patch-subtitle">{uiPatch.subtitle}</div> : null}
      </div>

      <div className="review-layout">
        <UiPatchAttention text={uiPatch.attention} />
        <UiPatchCards cards={uiPatch.cards} />

        <div className="stats-row">
          <div className="stat-box">
            <div className="stat-val">
              {Number.isFinite(minutes) ? minutes : '—'}
              <span className="stat-unit">min</span>
            </div>
            <div className="stat-label">预计用时</div>
          </div>
          <div className="stat-box">
            <div className="stat-val">
              {stepCount}
              <span className="stat-unit">步</span>
            </div>
            <div className="stat-label">烹饪步骤</div>
          </div>
          <div className="stat-box">
            <div className="stat-val">
              {adjustments.length || 0}
              <span className="stat-unit">项</span>
            </div>
            <div className="stat-label">已应用调整</div>
          </div>
        </div>

        <div className="review-cols">
          <div className="info-block">
            <div className="info-title">本次食材消耗</div>
            {inventoryChanges.length === 0 ? (
              <div className="mem-empty">暂无消耗记录</div>
            ) : (
              inventoryChanges.map((it) => (
                <div className="info-row" key={it.item_id || it.name}>
                  <span className="info-key">已使用 {it.name}</span>
                  <span className="info-val warn">{it.before || '部分'}</span>
                </div>
              ))
            )}
          </div>

          <div className="info-block">
            <div className="info-title">写入家庭记忆</div>
            {memories.length === 0 ? (
              <div className="mem-empty">暂无家庭记忆</div>
            ) : (
              memories.map((m) => (
                <div className="review-line" key={m.id}>
                  — {memoryText(m)}
                </div>
              ))
            )}
          </div>

          <div className="info-block">
            <div className="info-title">下次建议</div>
            {nextTime.map((t) => (
              <div className="review-line muted" key={t}>
                <span className="arrow">→</span>
                {t}
              </div>
            ))}
          </div>
        </div>

        <div className="review-actions">
          <button
            type="button"
            className="btn-primary"
            disabled={loading}
            onClick={onExportMemory}
          >
            导出家庭记忆卡
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={loading}
            onClick={() => onControl('reset')}
          >
            再做一道
          </button>
        </div>
        <UiPatchPhrases phrases={uiPatch.suggested_phrases} />

        {memoryMarkdown ? (
          <div className="export-md">{memoryMarkdown}</div>
        ) : null}
      </div>
    </div>
  );
}
