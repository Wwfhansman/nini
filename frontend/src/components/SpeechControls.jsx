import React from 'react';

export default function SpeechControls({
  voiceStatus,
  recordingState,
  recorderError,
  durationMs,
  speechRecognitionHint,
  partialTranscript,
  finalTranscript,
  ttsVendor,
  onTtsVendorChange,
  onVoicePrimary,
  onPickAudio,
  onPlayTts,
  loading,
}) {
  const statusText = {
    idle: '待命',
    sleeping: '休眠',
    listening_for_wake: '等你唤醒',
    active_listening: '我在听',
    transcribing: '听懂中',
    requesting: '准备麦克风',
    recording: '正在听',
    stopping: '收尾中',
    recognizing: '听懂中',
    thinking: '理解中',
    speaking: '播报中',
    unsupported: '语音不可用',
    denied: '麦克风未授权',
    error: '需要处理',
  }[voiceStatus] || '待命';

  const primaryLabel = {
    idle: '开启语音会话',
    sleeping: '开启语音会话',
    listening_for_wake: '收起语音',
    active_listening: '收起语音',
    transcribing: '收起语音',
    requesting: '准备中…',
    recording: '说完了',
    stopping: '处理中…',
    recognizing: '听懂中…',
    thinking: '收起语音',
    speaking: '收起语音',
    unsupported: '语音不可用',
    denied: '麦克风未授权',
    error: '重新开始',
  }[voiceStatus] || '开启语音';

  const durationText =
    recordingState === 'recording' ||
    ['recording', 'listening_for_wake', 'active_listening', 'transcribing'].includes(
      voiceStatus,
    )
      ? `${Math.max(1, Math.round(durationMs / 1000))}s`
      : null;
  const primaryDisabled =
    ['unsupported', 'denied'].includes(recordingState) ||
    ['unsupported', 'denied'].includes(voiceStatus) ||
    voiceStatus === 'requesting';
  const secondaryDisabled =
    loading ||
    [
      'requesting',
      'recording',
      'listening_for_wake',
      'active_listening',
      'transcribing',
      'stopping',
      'recognizing',
      'thinking',
      'speaking',
    ].includes(voiceStatus) ||
    ['requesting', 'recording', 'stopping'].includes(recordingState);
  const transcriptHint = partialTranscript
    ? `正在识别：${partialTranscript}`
    : finalTranscript
      ? `刚才听到：${finalTranscript}`
      : '';

  return (
    <div className="speech-controls">
      <div className="speech-copy">
        <span className="speech-status">{statusText}</span>
        <span className="speech-help">
          {recorderError ||
            transcriptHint ||
            speechRecognitionHint ||
            "开启后说“妮妮”唤醒，连续说话即可。"}
        </span>
      </div>
      <div className="tts-vendor-switch" aria-label="声音选择">
        <span>声音：</span>
        <button
          type="button"
          className={ttsVendor === 'bytedance' ? 'active' : ''}
          onClick={() => onTtsVendorChange?.('bytedance')}
        >
          清亮
        </button>
        <button
          type="button"
          className={ttsVendor === 'xiaomi' ? 'active' : ''}
          onClick={() => onTtsVendorChange?.('xiaomi')}
        >
          温柔
        </button>
      </div>
      <button
        type="button"
        className={`speech-main ${
          ['recording', 'listening_for_wake', 'active_listening', 'transcribing'].includes(
            voiceStatus,
          )
            ? 'recording'
            : ''
        }`}
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
        title="选择语音文件"
      >
        语音文件
      </button>
      <button
        type="button"
        onClick={onPlayTts}
        disabled={secondaryDisabled}
        title="再说一遍"
      >
        再说一遍
      </button>
    </div>
  );
}
