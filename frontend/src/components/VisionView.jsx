import React from 'react';

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
  const adjustments = state?.active_adjustments || [];
  const ingredients = lastObservation?.ingredients || [];
  const notes = lastObservation?.notes || [];
  const visionEvent = (recentEvents || [])
    .filter((e) => e.name === 'vision_observe')
    .slice(-1)[0];
  const observation = ingredients.length
    ? lastObservation
    : visionEvent?.output?.observation || null;
  const observationIngredients = observation?.ingredients || [];
  const observationNotes = observation?.notes || notes;

  const beforeLines = recipe?.servings
    ? [`计划 ${recipe.servings}`, `计划用料 ${recipe?.ingredients?.length ?? 0} 项`]
    : ['标准方案'];
  const afterLines = adjustments.length
    ? adjustments.slice(0, 4)
    : ['等待识别结果'];

  return (
    <div className="view-wrap">
      <div className="view-header">
        <div className="view-eyebrow saffron">视觉识别</div>
        <div className="view-title">我正在查看台面上的食材</div>
      </div>

      <div className="vision-layout">
        <div className="cam-box">
          <div className="cam-bg">
            {visionPreview ? (
              <img src={visionPreview} alt="ingredient preview" />
            ) : (
              <div className="cam-empty">
                <div className="glyph">▣</div>
                请选择一张食材照片
              </div>
            )}
          </div>
          <div className="cam-label">
            VISION · {state?.last_speech ? 'capture ready' : 'awaiting frame'}
          </div>
          <div className="vision-upload">
            <button
              type="button"
              className="btn-secondary"
              onClick={onPickImage}
              disabled={loading}
            >
              选择图片
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={onUploadVision}
              disabled={loading || !visionPreview}
            >
              {loading ? '识别中…' : '上传识别'}
            </button>
          </div>
        </div>

        <div className="vision-right">
          <div className="info-block">
            <div className="info-title">识别结果</div>
            {observationIngredients.length === 0 ? (
              <div className="mem-empty">暂无识别结果，先上传一张图</div>
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
              <div className="info-title">识别备注</div>
              {observationNotes.map((n, i) => (
                <div className="mem-row" key={i}>
                  <span className="dash">—</span>
                  <span>{n}</span>
                </div>
              ))}
            </div>
          ) : null}

          <div className="info-block">
            <div className="info-title">菜谱已自动修正</div>
            <div className="ba-grid">
              <div>
                <div className="ba-col-title">Before</div>
                {beforeLines.map((t, i) => (
                  <div className="ba-line before" key={i}>
                    {t}
                  </div>
                ))}
              </div>
              <div className="ba-arrow">→</div>
              <div>
                <div className="ba-col-title after">After</div>
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
