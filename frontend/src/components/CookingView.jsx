import React, { useEffect, useRef, useState } from 'react';
import { UiPatchAttention, UiPatchPhrases } from './UiPatch.jsx';

function formatTimer(seconds) {
  const safe = Math.max(0, Math.floor(Number(seconds) || 0));
  const mm = String(Math.floor(safe / 60)).padStart(2, '0');
  const ss = String(safe % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

function timerStatusLabel(status) {
  if (status === 'running') return '正在计时';
  if (status === 'paused') return '已暂停';
  if (status === 'finished') return '已完成';
  return '准备中';
}

/* Display-only countdown. The backend stays the source of truth: every
   server response resets `displayRemaining`, and the local interval just
   ticks the visual; it never POSTs. */
function useDisplayCountdown(state) {
  const remaining = Number(state?.timer_remaining_seconds || 0);
  const status = state?.timer_status || 'idle';
  const stepIdx = state?.current_step_index ?? 0;
  const [displayRemaining, setDisplayRemaining] = useState(remaining);
  const tickRef = useRef(null);

  useEffect(() => {
    setDisplayRemaining(remaining);
  }, [remaining, stepIdx]);

  useEffect(() => {
    if (tickRef.current) clearInterval(tickRef.current);
    if (status !== 'running') return undefined;
    tickRef.current = setInterval(() => {
      setDisplayRemaining((cur) => (cur > 0 ? cur - 1 : 0));
    }, 1000);
    return () => clearInterval(tickRef.current);
  }, [status, stepIdx]);

  return displayRemaining;
}

export default function CookingView({ state, onControl, loading }) {
  const recipe = state?.recipe || null;
  const steps = recipe?.steps || [];
  const idx = Number.isFinite(state?.current_step_index)
    ? state.current_step_index
    : 0;
  const step = steps[idx] || null;
  const next = steps[idx + 1] || null;
  const adjustments = state?.active_adjustments || [];
  const uiPatch = state?.ui_patch || {};
  const status = state?.timer_status || 'idle';

  const displayRemaining = useDisplayCountdown(state);
  const totalDuration = Math.max(1, Number(step?.duration_seconds || 0));
  const pct =
    status === 'idle'
      ? 0
      : Math.min(
          100,
          ((totalDuration - displayRemaining) / totalDuration) * 100,
        );

  const isLastStep = idx >= steps.length - 1;

  return (
    <div className="kds-wrap">
      <div className="kds-rail">
        {steps.map((s, i) => (
          <div
            key={i}
            className={`rail-pip ${i < idx ? 'done' : i === idx ? 'cur' : ''}`}
          >
            {i < idx ? '✓' : i + 1}
          </div>
        ))}
        <div className="rail-title">
          {recipe?.dish_name || '当前菜品'}
        </div>
      </div>

      <div className="kds-main">
        {step ? (
          <>
            <div className="kds-num-block">
              <span className="kds-num">{idx + 1}</span>
              <div className="kds-num-meta">
                <span className="kds-total">/ {steps.length || 1}</span>
                {step.heat ? <span className="kds-fire">{step.heat}</span> : null}
              </div>
            </div>
            <div className="kds-divider" />
            <div className="kds-action">{step.title}</div>
            <div
              style={{
                fontSize: 14,
                color: 'var(--c-mid)',
                lineHeight: 1.6,
              }}
            >
              {step.instruction}
            </div>

            <div className="kds-timer-row">
              <div
                className={`kds-timer ${status === 'idle' ? 'idle' : ''}`}
              >
                {formatTimer(displayRemaining)}
              </div>
              <div className="kds-timer-right">
                <div className="timer-track">
                  <div
                    className="timer-fill"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="timer-status">
                  {timerStatusLabel(status)} · 预计 {step.duration_seconds || 0} 秒
                </div>
              </div>
            </div>

            {step.ingredients?.length ? (
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--c-mid)',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                用料：{step.ingredients.join('、')}
              </div>
            ) : null}

            {adjustments.length ? (
              <div className="kds-notes">
                {adjustments.slice(0, 3).map((a, i) => (
                  <span key={i} className="note-item">
                    ✦ {a}
                  </span>
                ))}
              </div>
            ) : null}

            <UiPatchAttention text={uiPatch.attention} />
            <UiPatchPhrases phrases={uiPatch.suggested_phrases} />
          </>
        ) : (
          <div style={{ textAlign: 'center', color: 'var(--c-mid)' }}>
            尚未规划菜谱步骤，先在左侧输入约束让妮妮规划。
          </div>
        )}
      </div>

      {next ? (
        <div className="kds-next-bar">
          <span className="next-label">下一步 →</span>
          <span className="next-text">{next.title}</span>
        </div>
      ) : null}

      <div className="kds-controls">
        <button
          type="button"
          className="kds-ctrl"
          disabled={loading || idx === 0}
          onClick={() => onControl('previous_step')}
        >
          ← 上一步
        </button>
        {status === 'paused' ? (
          <button
            type="button"
            className="kds-ctrl primary"
            disabled={loading}
            onClick={() => onControl('resume')}
          >
            ▶ 继续
          </button>
        ) : status === 'running' ? (
          <button
            type="button"
            className="kds-ctrl"
            disabled={loading}
            onClick={() => onControl('pause')}
          >
            ⏸ 暂停一下
          </button>
        ) : (
          <button
            type="button"
            className="kds-ctrl primary"
            disabled={loading}
            onClick={() => onControl('start')}
          >
            ▶ 开始做
          </button>
        )}
        {isLastStep ? (
          <button
            type="button"
            className="kds-ctrl danger"
            disabled={loading}
            onClick={() => onControl('finish')}
          >
            做完了 ✓
          </button>
        ) : (
          <button
            type="button"
            className="kds-ctrl primary"
            disabled={loading}
            onClick={() => onControl('next_step')}
          >
            下一步 →
          </button>
        )}
      </div>
    </div>
  );
}
