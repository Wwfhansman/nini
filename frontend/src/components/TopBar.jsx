import React from 'react';

const VOICE_LABELS = {
  idle: { text: '待命', tone: 'mid' },
  listening: { text: '正在听', tone: 'terra' },
  recording: { text: '正在听', tone: 'terra' },
  requesting: { text: '请求中', tone: 'terra' },
  stopping: { text: '识别中', tone: 'saffron' },
  recognizing: { text: '识别中', tone: 'saffron' },
  thinking: { text: '理解中', tone: 'saffron' },
  speaking: { text: '播报中', tone: 'herb' },
  unsupported: { text: '需要处理', tone: 'danger' },
  denied: { text: '需要处理', tone: 'danger' },
  error: { text: '需要处理', tone: 'danger' },
};

const VOICE_COLORS = {
  mid: 'var(--c-mid)',
  terra: 'var(--c-terra)',
  saffron: 'var(--c-saffron)',
  herb: 'var(--c-herb)',
  danger: 'var(--c-danger)',
};

function statusForUiMode(uiMode, currentStepIndex, totalSteps) {
  if (uiMode === 'planning')
    return { text: '正在规划晚餐', color: 'var(--c-terra)' };
  if (uiMode === 'vision')
    return { text: '视觉识别中', color: 'var(--c-saffron)' };
  if (uiMode === 'cooking') {
    const idx = Number.isFinite(currentStepIndex) ? currentStepIndex + 1 : 1;
    const total = Number.isFinite(totalSteps) && totalSteps > 0 ? totalSteps : 6;
    return { text: `烹饪中 · 第 ${idx} / ${total} 步`, color: 'var(--c-terra)' };
  }
  if (uiMode === 'review')
    return { text: '本次烹饪复盘', color: 'var(--c-herb)' };
  return { text: '待命中', color: 'var(--c-mid)' };
}

export default function TopBar({
  appState,
  currentStepIndex,
  totalSteps,
  voiceStatus,
  currentTime,
  mode,
  terminalId,
  onTerminalIdChange,
}) {
  const status = statusForUiMode(appState, currentStepIndex, totalSteps);
  const voice = VOICE_LABELS[voiceStatus] || VOICE_LABELS.idle;
  const voiceColor = VOICE_COLORS[voice.tone];

  const modeColor =
    mode === '在线模式'
      ? 'var(--c-herb)'
      : mode === '混合模式'
      ? 'var(--c-saffron)'
      : 'var(--c-mid)';

  return (
    <header className="topbar">
      <div className="topbar-brand">
        <div className="topbar-mark">妮</div>
        <div className="topbar-text">
          <span className="topbar-name">妮妮 Kitchen Agent</span>
          <span className="topbar-sub">家庭厨房 AI 终端</span>
        </div>
        <div className="topbar-divider" />
        <div className="topbar-status" style={{ color: status.color }}>
          <span
            className="topbar-status-line"
            style={{ background: status.color }}
          />
          {status.text}
        </div>
      </div>

      <div className="topbar-right">
        <div className="topbar-chip topbar-tid">
          <span className="topbar-chip-label">终端</span>
          <input
            value={terminalId}
            onChange={(e) => onTerminalIdChange(e.target.value)}
            spellCheck={false}
            aria-label="terminal id"
          />
        </div>
        <div className="topbar-chip">
          <span className="topbar-chip-label">智能服务</span>
          <span className="topbar-chip-val" style={{ color: modeColor }}>
            {mode}
          </span>
        </div>
        <div className="topbar-chip">
          <span className="topbar-chip-label">语音</span>
          <span className="topbar-chip-val" style={{ color: voiceColor }}>
            {voice.text}
          </span>
        </div>
        <div className="topbar-clock">{currentTime}</div>
      </div>
    </header>
  );
}
