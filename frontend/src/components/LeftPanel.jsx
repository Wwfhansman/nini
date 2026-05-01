import React, { useEffect, useRef, useState } from 'react';

const WAVE_HEIGHTS = [3, 7, 12, 5, 10, 14, 6, 9, 4, 11, 7, 3];

function Waveform({ active }) {
  return (
    <div className="waveform" aria-hidden>
      {WAVE_HEIGHTS.map((h, i) => (
        <span
          key={i}
          style={{
            height: active ? h : 2,
            animationName: active ? 'waveAnim' : 'none',
            animationDuration: '0.7s',
            animationIterationCount: 'infinite',
            animationDirection: 'alternate',
            animationDelay: `${i * 60}ms`,
            animationTimingFunction: 'ease-in-out',
          }}
        />
      ))}
    </div>
  );
}

function VoiceBar({ voiceStatus, ttsVendor, onTtsVendorChange }) {
  const label =
    {
      idle: '待命',
      sleeping: '休眠',
      listening_for_wake: '说“妮妮”唤醒',
      active_listening: '我在听',
      transcribing: '听懂中…',
      listening: '正在听…',
      recording: '正在听…',
      requesting: '准备麦克风…',
      stopping: '收尾中…',
      recognizing: '听懂中…',
      thinking: '理解中…',
      speaking: '播报中',
      unsupported: '浏览器不支持录音',
      denied: '麦克风未授权',
      error: '需要处理',
    }[voiceStatus] || '待命';
  const active = [
    'listening',
    'recording',
    'listening_for_wake',
    'active_listening',
    'transcribing',
    'recognizing',
    'speaking',
  ].includes(voiceStatus);
  return (
    <div className="voicebar">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span
          style={{
            fontSize: 9,
            color: 'var(--c-mid)',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
          }}
        >
          语音状态
        </span>
        <span
          style={{
            fontSize: 13,
            fontWeight: 700,
            color: 'var(--c-ink)',
            fontFamily: 'var(--font-display)',
          }}
        >
          {label}
        </span>
      </div>
      <div className="sound-switch" aria-label="声音选择">
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
      <Waveform active={active} />
    </div>
  );
}

export default function LeftPanel({
  messages,
  voiceStatus,
  loading,
  onSend,
  onVoicePrimary,
  onPickImage,
  onPickAudio,
  onPlayTts,
  recordingState,
  recorderError,
  speechRecognitionHint,
  partialTranscript,
  finalTranscript,
  ttsVendor,
  onTtsVendorChange,
  onRunExperience,
  experienceRunning,
  experienceStep,
}) {
  const [input, setInput] = useState('');
  const listRef = useRef(null);
  const visible = messages.slice(-10);
  const voiceSecondaryDisabled =
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
  const voicePrimaryDisabled =
    ['unsupported', 'denied'].includes(recordingState) ||
    ['unsupported', 'denied', 'requesting'].includes(voiceStatus);
  const voiceActive = [
    'recording',
    'listening_for_wake',
    'active_listening',
    'transcribing',
    'recognizing',
    'thinking',
    'speaking',
  ].includes(voiceStatus);
  const voicePrimaryLabel = voiceActive ? '收起语音' : '开启语音会话';
  const transcriptHint = partialTranscript || finalTranscript || recorderError || speechRecognitionHint;

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [visible.length]);

  const submit = () => {
    if (!input.trim() || loading) return;
    onSend(input);
    setInput('');
  };

  return (
    <div className="leftpanel">
      <div className="section-head">
        <span className="section-label">对话记录</span>
        <div className="left-head-actions">
          <button
            type="button"
            className="quiet-link"
            onClick={onRunExperience}
            disabled={experienceRunning || loading}
            title="按今日推荐走一遍完整流程"
          >
            {experienceRunning ? '安排中' : '今日推荐'}
          </button>
          <span className="rp-aux">{messages.length} 轮</span>
        </div>
      </div>

      <div className="chat-list" ref={listRef}>
        {visible.length === 0 ? (
          <div className="chat-empty">
            说一句“妮妮，给我做个菜”，或直接告诉我家里有什么。
          </div>
        ) : (
          visible.map((msg) => (
            <div
              key={msg.id}
              className={`msg-wrap ${msg.role === 'user' ? 'user' : 'nini'}`}
            >
              <div
                className={`msg-tag ${msg.role === 'user' ? 'user' : 'nini'}`}
              >
                {msg.role === 'user' ? '你' : '妮妮'}
              </div>
              <div className={`bubble ${msg.role === 'user' ? 'user' : 'nini'}`}>
                {msg.text}
                <div className="msg-time">{msg.time}</div>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="left-console">
        <VoiceBar
          voiceStatus={voiceStatus}
          ttsVendor={ttsVendor}
          onTtsVendorChange={onTtsVendorChange}
        />
        {transcriptHint ? (
          <div className="voice-inline-note">{transcriptHint}</div>
        ) : null}
        {experienceRunning && experienceStep ? (
          <div className="voice-inline-note">正在安排：{experienceStep}</div>
        ) : null}

        <textarea
          className="input-textarea"
          rows={2}
          placeholder="说说今晚想吃什么，或者让我看看食材"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <div className="input-row">
          <button
            type="button"
            className={`voice-action ${voiceActive ? 'active' : ''}`}
            onClick={onVoicePrimary}
            title={voicePrimaryLabel}
            disabled={voicePrimaryDisabled}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <rect
                x="9"
                y="2"
                width="6"
                height="12"
                rx="3"
                fill="currentColor"
              />
              <path
                d="M5 10a7 7 0 0014 0M12 19v3M9 22h6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
            <span>{voicePrimaryLabel}</span>
          </button>
          <button
            type="button"
            className="icon-btn"
            onClick={onPickAudio}
            title="选择语音文件"
            aria-label="upload audio"
            disabled={voiceSecondaryDisabled}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <rect
                x="9"
                y="2"
                width="6"
                height="12"
                rx="3"
                fill="currentColor"
              />
              <path
                d="M5 10a7 7 0 0014 0M12 19v3M9 22h6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </button>
          <button
            type="button"
            className="icon-btn"
            onClick={onPickImage}
            title="看看食材"
            aria-label="upload image"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path
                d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <circle cx="12" cy="13" r="4" stroke="currentColor" strokeWidth="2" />
            </svg>
          </button>
          <button
            type="button"
            className="icon-btn"
            onClick={onPlayTts}
            title="再说一遍"
            aria-label="play tts"
            disabled={voiceSecondaryDisabled}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path
                d="M3 10v4h4l5 4V6L7 10H3z"
                fill="currentColor"
              />
              <path
                d="M16 8a5 5 0 010 8M19 5a8 8 0 010 14"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </button>
          <button
            type="button"
            className="send-btn"
            onClick={submit}
            disabled={loading || !input.trim()}
          >
            {loading ? '思考中…' : '发 送'}
          </button>
        </div>
      </div>
    </div>
  );
}
