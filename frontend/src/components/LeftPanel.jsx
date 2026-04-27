import React, { useEffect, useRef, useState } from 'react';
import SpeechControls from './SpeechControls.jsx';

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

function VoiceBar({ voiceStatus }) {
  const label =
    {
      idle: '待机中',
      listening: '正在听…',
      thinking: '思考中…',
      speaking: '播报中',
    }[voiceStatus] || '待机中';
  const active = voiceStatus === 'listening' || voiceStatus === 'speaking';
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
      <Waveform active={active} />
    </div>
  );
}

export default function LeftPanel({
  messages,
  voiceStatus,
  loading,
  onSend,
  onPickImage,
  onPickAudio,
  onPlayTts,
  onQuickAction,
  speechMode,
}) {
  const [input, setInput] = useState('');
  const listRef = useRef(null);
  const visible = messages.slice(-10);

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
        <span className="rp-aux">{messages.length} msgs</span>
      </div>

      <div className="chat-list" ref={listRef}>
        {visible.length === 0 ? (
          <div className="chat-empty">
            说说今晚想吃什么，或者点击右上「一键运行 Demo」。
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

      <VoiceBar voiceStatus={voiceStatus} />

      <SpeechControls
        voiceStatus={voiceStatus}
        speechMode={speechMode}
        onPickAudio={onPickAudio}
        onPlayTts={onPlayTts}
        loading={loading}
      />

      <div className="input-wrap">
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
            className="icon-btn"
            onClick={onPickAudio}
            title="上传录音 → ASR"
            aria-label="upload audio"
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
            title="上传食材图 → Vision"
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
            title="播放最新语音 → TTS"
            aria-label="play tts"
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

      <div className="quick-nav">
        <button
          type="button"
          className="quick-btn"
          onClick={() => onQuickAction('planning')}
          title="reset 状态"
        >
          规划晚餐
        </button>
        <button
          type="button"
          className="quick-btn primary"
          onClick={() => onQuickAction('cooking')}
        >
          开始烹饪
        </button>
        <button
          type="button"
          className="quick-btn"
          onClick={() => onQuickAction('review')}
        >
          烹饪复盘
        </button>
      </div>
    </div>
  );
}
