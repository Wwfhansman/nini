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

  const beforeLines = recipe?.servings
    ? [`计划 ${recipe.servings}`, `计划用料 ${recipe?.ingredients?.length ?? 0} 项`]
    : ['标准方案'];
  const afterLines = adjustments.length
    ? adjustments.slice(0, 4)
    : ['等待食材画面'];

  return (
    <div className="view-wrap">
      <div className="view-header">
        <div className="view-eyebrow saffron">终端视觉</div>
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
            Web 演示中使用图片模拟终端摄像头画面
          </div>
          <div className="vision-upload">
            <button
              type="button"
              className="btn-secondary"
              onClick={onPickImage}
              disabled={loading}
            >
              选择一张食材画面
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={onUploadVision}
              disabled={loading || !visionPreview}
            >
              {loading ? '识别中…' : '开始识别'}
            </button>
          </div>
        </div>

        <div className="vision-right">
          <UiPatchAttention text={uiPatch.attention} />
          <UiPatchCards cards={uiPatch.cards} />
          <UiPatchPhrases phrases={uiPatch.suggested_phrases} />

          <div className="info-block">
            <div className="info-title">看到的食材</div>
            {observationIngredients.length === 0 ? (
              <div className="mem-empty">请先选择食材画面，妮妮会根据看到的食材调整方案</div>
            ) : (
              observationIngredients.map((it) => {
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
          </div>

          {observationNotes?.length ? (
            <div className="info-block">
              <div className="info-title">观察备注</div>
              {observationNotes.map((n, i) => (
                <div className="mem-row" key={i}>
                  <span className="dash">—</span>
                  <span>{n}</span>
                </div>
              ))}
            </div>
          ) : null}

          <div className="info-block">
            <div className="info-title">对菜谱的影响</div>
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
                {afterLines.map((t, i) => (
                  <div className="ba-line after" key={i}>
                    {t}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
