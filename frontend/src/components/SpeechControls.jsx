import React from 'react';

export default function SpeechControls({
  voiceStatus,
  recordingState,
  recorderError,
  durationMs,
  onVoicePrimary,
  onPickAudio,
  onPlayTts,
  loading,
}) {
  const statusText = {
    idle: '待命',
    requesting: '请求麦克风',
    recording: '正在听',
    stopping: '收尾中',
    recognizing: '识别中',
    thinking: '理解中',
    speaking: '播报中',
    unsupported: '不支持录音',
    denied: '麦克风未授权',
    error: '需要处理',
  }[voiceStatus] || '待命';

  const primaryLabel = {
    idle: '开始说话',
    requesting: '请求麦克风…',
    recording: '停止并识别',
    stopping: '处理中…',
    recognizing: '识别中…',
    thinking: '理解中…',
    speaking: '播报中…',
    unsupported: '无法录音',
    denied: '麦克风未授权',
    error: '重新开始',
  }[voiceStatus] || '开始说话';

  const durationText =
    recordingState === 'recording' || voiceStatus === 'recording'
      ? `${Math.max(1, Math.round(durationMs / 1000))}s`
      : null;
  const primaryDisabled =
    ['unsupported', 'denied'].includes(recordingState) ||
    ['unsupported', 'denied'].includes(voiceStatus) ||
    (loading && voiceStatus !== 'recording') ||
    ['requesting', 'stopping', 'recognizing', 'thinking', 'speaking'].includes(voiceStatus);
  const secondaryDisabled =
    loading ||
    ['requesting', 'recording', 'stopping', 'recognizing', 'thinking', 'speaking'].includes(
      voiceStatus,
    ) ||
    ['requesting', 'recording', 'stopping'].includes(recordingState);

  return (
    <div className="speech-controls">
      <div className="speech-copy">
        <span className="speech-status">{statusText}</span>
        <span className="speech-help">
          {recorderError || '点击开始说话，妮妮会听完、理解并回复。'}
        </span>
      </div>
      <button
        type="button"
        className={`speech-main ${voiceStatus === 'recording' ? 'recording' : ''}`}
        onClick={onVoicePrimary}
        disabled={primaryDisabled}
      >
        {primaryLabel}
        {durationText ? <span>{durationText}</span> : null}
      </button>
      <button
        type="button"
        onClick={onPickAudio}
        disabled={secondaryDisabled}
        title="上传录音文件"
      >
        上传录音
      </button>
      <button
        type="button"
        onClick={onPlayTts}
        disabled={secondaryDisabled}
        title="重播最近一次妮妮回复"
      >
        重播回复
      </button>
    </div>
  );
}
