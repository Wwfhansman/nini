import React from 'react';

export default function SpeechControls({
  voiceStatus,
  speechMode,
  onPickAudio,
  onPlayTts,
  loading,
}) {
  const statusText =
    {
      idle: '待机',
      listening: '识别中',
      thinking: '思考中',
      speaking: '播报中',
    }[voiceStatus] || voiceStatus;

  return (
    <div className="speech-controls">
      <span className="speech-status">
        SPEECH · mode={speechMode || 'mock'} · status={statusText}
      </span>
      <button
        type="button"
        onClick={onPickAudio}
        disabled={loading}
        title="上传音频文件 → /api/speech/asr"
      >
        ASR 上传
      </button>
      <button
        type="button"
        onClick={onPlayTts}
        disabled={loading}
        title="对最新一条妮妮播报调用 /api/speech/tts"
      >
        TTS 播放
      </button>
    </div>
  );
}
