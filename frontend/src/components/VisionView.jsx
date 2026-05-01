import React from 'react';
import { UiPatchAttention, UiPatchCards, UiPatchPhrases } from './UiPatch.jsx';

export default function VisionView({
  state,
  visionPreview,
  lastObservation,
  onPickImage,
  onUploadVision,
  loading,
  recentEvents,
}) {
  const recipe = state?.recipe;
  const uiPatch = state?.ui_patch || {};
  const adjustments = state?.active_adjustments || [];
  const ingredients = lastObservation?.ingredients || [];
  const notes = lastObservation?.notes || [];
  const latestVisionEvent = (recentEvents || [])
    .filter((e) => e.name === 'vision_observe' || e.name === 'start_vision')
    .slice(-1)[0];
  const observation = ingredients.length
    ? lastObservation
    : latestVisionEvent?.name === 'vision_observe'
    ? latestVisionEvent?.output?.observation || null
    : null;
  const observationIngredients = observation?.ingredients || [];
  const observationNotes = observation?.notes || notes;
  const visibleIngredients = observationIngredients.slice(0, 4);
  const hiddenIngredientCount = Math.max(0, observationIngredients.length - visibleIngredients.length);
  const visibleNotes = (observationNotes || []).slice(0, 2);
  const patchCards = uiPatch.cards || [];
  const hasPatchCards = patchCards.length > 0;

  const beforeLines = recipe?.servings
    ? [`计划 ${recipe.servings}`, `计划用料 ${recipe?.ingredients?.length ?? 0} 项`]
    : ['标准方案'];
  const afterLines = adjustments.length
    ? adjustments.slice(0, 4)
    : ['等待食材画面'];

  return (
    <div className="view-wrap">
      <div className="view-header">
        <div className="view-eyebrow saffron">台面观察</div>
        <div className="view-title">{uiPatch.title || '我正在查看台面上的食材'}</div>
        {uiPatch.subtitle ? <div className="patch-subtitle">{uiPatch.subtitle}</div> : null}
      </div>

      <div className="vision-layout">
        <div className="cam-box">
          <div className="cam-bg">
            {visionPreview ? (
              <img src={visionPreview} alt="ingredient preview" />
            ) : (
              <div className="cam-empty">
                <div className="glyph">▣</div>
                等待食材画面
              </div>
            )}
          </div>
          <div className="cam-label">
            把食材放到镜头前，或选择一张台面照片。
          </div>
          <div className="vision-upload">
            <button
              type="button"
              className="btn-secondary"
              onClick={onPickImage}
              disabled={loading}
            >
              选择照片
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={onUploadVision}
              disabled={loading || !visionPreview}
            >
              {loading ? '正在看…' : '看看食材'}
            </button>
          </div>
        </div>

        <div className="vision-right">
          <UiPatchAttention text={uiPatch.attention} />
          <UiPatchCards cards={patchCards} />
          <UiPatchPhrases phrases={uiPatch.suggested_phrases} />

          {!hasPatchCards ? (
            <div className="info-block">
              <div className="info-title">看到的食材</div>
              {observationIngredients.length === 0 ? (
                <div className="mem-empty">请先选择食材画面，妮妮会根据看到的食材调整方案</div>
              ) : (
                visibleIngredients.map((it) => {
                  const warn =
                    String(it.amount || '').includes('半') ||
                    String(it.amount || '').includes('少');
                  return (
                    <div className="info-row" key={`${it.name}-${it.amount}`}>
                      <span className="info-key">{it.name}</span>
                      <span className={`info-val ${warn ? 'warn' : 'ok'}`}>
                        {it.amount}
                        {Number.isFinite(it.confidence)
                          ? ` · ${(it.confidence * 100).toFixed(0)}%`
                          : ''}
                      </span>
                    </div>
                  );
                })
              )}
              {hiddenIngredientCount ? (
                <div className="mem-empty">还有 {hiddenIngredientCount} 项已放入当前库存</div>
              ) : null}
            </div>
          ) : null}

          {visibleNotes.length ? (
            <div className="info-block compact">
              <div className="info-title">观察备注</div>
              {visibleNotes.map((n, i) => (
                <div className="mem-row" key={i}>
                  <span className="dash">—</span>
                  <span>{n}</span>
                </div>
              ))}
            </div>
          ) : null}

          <div className={`info-block ${hasPatchCards ? 'compact' : ''}`}>
            <div className="info-title">{hasPatchCards ? '菜谱调整' : '对菜谱的影响'}</div>
            {hasPatchCards ? (
              afterLines.slice(0, 2).map((t, i) => (
                <div className="mem-row" key={i}>
                  <span className="dash">✦</span>
                  <span>{t}</span>
                </div>
              ))
            ) : (
              <div className="ba-grid">
                <div>
                  <div className="ba-col-title">原计划</div>
                  {beforeLines.map((t, i) => (
                    <div className="ba-line before" key={i}>
                      {t}
                    </div>
                  ))}
                </div>
                <div className="ba-arrow">→</div>
                <div>
                  <div className="ba-col-title after">已根据食材调整</div>
                  {afterLines.slice(0, 3).map((t, i) => (
                    <div className="ba-line after" key={i}>
                      {t}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
