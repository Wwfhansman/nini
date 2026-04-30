import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  DEFAULT_TERMINAL_ID,
  getHealth,
  getMemoryMarkdown,
  getState,
  postChat,
  postControl,
  postSpeechAsr,
  postSpeechTts,
  postVision,
} from './api.js';
import TopBar from './components/TopBar.jsx';
import LeftPanel from './components/LeftPanel.jsx';
import CenterPanel from './components/CenterPanel.jsx';
import RightPanel from './components/RightPanel.jsx';
import useVoiceSession from './hooks/useVoiceSession.js';

const DEMO_PLAN_TEXT =
  '我最近减脂，妈妈不吃辣，冰箱里有鸡胸肉、番茄、鸡蛋，今晚做什么？';
const DEMO_SOUR_TEXT = '记住我不喜欢太酸';
const AUTO_PLAYBACK_TIMEOUT_MS = 16000;

const nowTime = () =>
  new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function initialTtsVendor() {
  if (typeof window === 'undefined') return 'bytedance';
  const value = window.localStorage.getItem('nini_tts_vendor');
  return value === 'xiaomi' || value === 'bytedance' ? value : 'bytedance';
}

function audioExtension(mimeType) {
  if (mimeType?.includes('mp4')) return 'm4a';
  if (mimeType?.includes('wav')) return 'wav';
  if (mimeType?.includes('webm')) return 'webm';
  return 'webm';
}

function toAudioFile(blob) {
  if (blob instanceof File) return blob;
  const type = blob?.type || 'audio/webm';
  return new File([blob], `voice-turn-${Date.now()}.${audioExtension(type)}`, {
    type,
  });
}

function createDemoIngredientsFile() {
  return new File(
    [new Blob(['nini demo ingredients'], { type: 'image/jpeg' })],
    'demo-ingredients.jpg',
    { type: 'image/jpeg' },
  );
}

function playAudioBase64({
  audio_base64: audioBase64,
  mime_type: mimeType,
  fallback_used: fallbackUsed,
}) {
  if (!audioBase64 || fallbackUsed || !mimeType) {
    return Promise.resolve({ played: false, reason: 'no_audio' });
  }
  const src = `data:${mimeType};base64,${audioBase64}`;
  const audio = new Audio(src);
  return new Promise((resolve) => {
    let settled = false;
    const timer = window.setTimeout(() => {
      try {
        audio.pause();
      } catch {
        // Browser may have already disposed the audio element.
      }
      done({ played: false, reason: 'timeout' });
    }, AUTO_PLAYBACK_TIMEOUT_MS);
    const done = (result) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      resolve(result);
    };
    audio.onended = () => done({ played: true, reason: 'played' });
    audio.onerror = () => done({ played: false, reason: 'playback_error' });
    audio.onabort = () => done({ played: false, reason: 'playback_error' });
    audio.play().catch(() => done({ played: false, reason: 'blocked' }));
  });
}

function playbackNotice(result, manual = false) {
  if (result?.reason === 'blocked') {
    return manual
      ? '浏览器未能播放音频，请稍后再试。'
      : '浏览器未自动播放，可点击重播。';
  }
  if (result?.reason === 'playback_error') {
    return '语音音频暂时无法播放，已保留文字回复。';
  }
  if (result?.reason === 'timeout') {
    return '语音播放时间过长，已先恢复识别。';
  }
  return '当前暂无可播放语音，已保留文字回复。';
}

function serviceModeLabel(mode) {
  const normalized = (mode || 'mock').toLowerCase();
  if (normalized === 'real') return '在线模式';
  if (normalized === 'hybrid') return '混合模式';
  return '演示模式';
}

export default function App() {
  const [terminalId, setTerminalId] = useState(DEFAULT_TERMINAL_ID);
  const [health, setHealth] = useState(null);

  const [apiData, setApiData] = useState(null);
  const [state, setState] = useState({ ui_mode: 'planning' });

  const [chatLog, setChatLog] = useState([]);

  const [voiceStatus, setVoiceStatus] = useState('idle');
  const [ttsVendor, setTtsVendor] = useState(initialTtsVendor);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const [highlightTrigger, setHighlightTrigger] = useState(0);
  const [recentEvents, setRecentEvents] = useState([]);

  const [memoryMarkdown, setMemoryMarkdown] = useState('');
  const [demoRunning, setDemoRunning] = useState(false);
  const [demoStep, setDemoStep] = useState('');

  const [pendingImage, setPendingImage] = useState(null);
  const [lastVisionPreview, setLastVisionPreview] = useState(null);
  const [lastObservation, setLastObservation] = useState(null);

  const [currentTime, setCurrentTime] = useState(nowTime());

  const visionInputRef = useRef(null);
  const audioInputRef = useRef(null);

  // wall clock
  useEffect(() => {
    const iv = setInterval(() => setCurrentTime(nowTime()), 1000);
    return () => clearInterval(iv);
  }, []);

  // health & initial state
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const h = await getHealth();
        if (!cancelled) setHealth(h);
      } catch (e) {
        if (!cancelled) setError(`暂时无法连接厨房服务: ${e.message}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshState = useCallback(
    async (tid) => {
      const id = tid || terminalId;
      try {
        const resp = await getState(id);
        const data = resp?.data || {};
        setApiData(data);
        if (data.state) setState(data.state);
        if (Array.isArray(data.tool_events)) setRecentEvents([]);
      } catch (e) {
        setError(`获取状态失败: ${e.message}`);
      }
    },
    [terminalId],
  );

  useEffect(() => {
    refreshState(terminalId);
  }, [terminalId, refreshState]);

  // Apply a chat/vision/control response
  const applyResponse = useCallback(
    (resp, { fromUserText, source = 'ui' } = {}) => {
      if (!resp) return;
      if (resp.state) setState(resp.state);
      const events = Array.isArray(resp.events) ? resp.events : [];
      const startsVision =
        resp?.data?.voice_route?.intent === 'start_vision' ||
        events.some((event) => event.name === 'start_vision');
      if (startsVision) {
        setLastObservation(null);
        setLastVisionPreview(null);
        setPendingImage(null);
        if (visionInputRef.current) visionInputRef.current.value = '';
      }
      if (events.length) {
        setRecentEvents((prev) => [
          ...prev,
          ...events.map((e) => ({ ...e, _source: source })),
        ]);
        setHighlightTrigger((n) => n + 1);
      }
      const speech = resp?.data?.speech;
      const time = nowTime();
      if (fromUserText) {
        setChatLog((prev) => [
          ...prev,
          { id: `u-${Date.now()}`, role: 'user', text: fromUserText, time },
        ]);
      }
      if (speech) {
        setChatLog((prev) => [
          ...prev,
          {
            id: `n-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`,
            role: 'nini',
            text: speech,
            time,
          },
        ]);
      }
    },
    [],
  );

  // After any mutation we re-pull /api/state so memory/inventory/tool_events stay fresh.
  const syncFullState = useCallback(async () => {
    try {
      const resp = await getState(terminalId);
      const data = resp?.data || {};
      setApiData(data);
      if (data.state) setState(data.state);
    } catch (e) {
      setError(`刷新状态失败: ${e.message}`);
    }
  }, [terminalId]);

  const appendEvents = useCallback((resp, source) => {
    const events = Array.isArray(resp?.events) ? resp.events : [];
    if (!events.length) return;
    setRecentEvents((prev) => [
      ...prev,
      ...events.map((e) => ({ ...e, _source: source })),
    ]);
    setHighlightTrigger((n) => n + 1);
  }, []);

  const appendUserMessage = useCallback((text) => {
    setChatLog((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: 'user', text, time: nowTime() },
    ]);
  }, []);

  const requestSpeechPlayback = useCallback(
    async (text, source = 'tts') => {
      if (!text) return { played: false, reason: 'no_speech' };
      const resp = await postSpeechTts(terminalId, text, ttsVendor);
      appendEvents(resp, source);
      return playAudioBase64(resp?.data || {});
    },
    [appendEvents, terminalId, ttsVendor],
  );

  const handleTtsVendorChange = useCallback((vendor) => {
    const next = vendor === 'xiaomi' ? 'xiaomi' : 'bytedance';
    setTtsVendor(next);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('nini_tts_vendor', next);
    }
  }, []);

  const speakResponseSpeech = useCallback(
    async (resp, source = 'auto-tts') => {
      const speech = resp?.data?.speech;
      if (!speech) return false;
      setVoiceStatus('speaking');
      try {
        const playback = await requestSpeechPlayback(speech, source);
        if (!playback.played) setNotice(playbackNotice(playback));
        return playback.played;
      } catch {
        setNotice('语音播报暂不可用，已保留文字回复。');
        return false;
      } finally {
        setVoiceStatus('idle');
      }
    },
    [requestSpeechPlayback],
  );

  const handleVoiceAgentEvent = useCallback((event) => {
    if (!event) return;
    setRecentEvents((prev) => [...prev, { ...event, _source: 'voice-session' }]);
    setHighlightTrigger((n) => n + 1);
  }, []);

  const handleVoiceAgentResponse = useCallback(
    async (resp, transcript) => {
      setLoading(true);
      try {
        applyResponse(resp, {
          fromUserText: transcript,
          source: 'voice-session',
        });
        await syncFullState();
        await speakResponseSpeech(resp, 'voice-session-tts');
      } finally {
        setLoading(false);
      }
    },
    [applyResponse, speakResponseSpeech, syncFullState],
  );

  const voiceSession = useVoiceSession({
    terminalId,
    onAgentEvent: handleVoiceAgentEvent,
    onAgentResponse: handleVoiceAgentResponse,
    onError: setNotice,
  });

  const runRecordedVoiceTurn = useCallback(
    async (audio, source = 'recording') => {
      if (!audio) return;
      setError(null);
      setNotice(null);
      setLoading(true);
      try {
        setVoiceStatus('recognizing');
        const audioFile = toAudioFile(audio);
        const asrResp = await postSpeechAsr(terminalId, audioFile);
        appendEvents(asrResp, `${source}-asr`);
        if (
          asrResp?.data?.provider === 'mock_asr' ||
          asrResp?.data?.fallback_used
        ) {
          setNotice('当前为演示识别，系统会使用固定指令：下一步。');
        }
        const text = (asrResp?.data?.text || '').trim();
        if (!text) {
          setError('没有识别到有效语音，请再说一次或上传录音。');
          setVoiceStatus('idle');
          return;
        }

        appendUserMessage(text);
        setVoiceStatus('thinking');
        const chatResp = await postChat(terminalId, text, 'voice');
        applyResponse(chatResp, { source: `${source}-chat` });
        await syncFullState();
        await speakResponseSpeech(chatResp, `${source}-tts`);
      } catch (e) {
        setError(`语音会话失败: ${e.message}`);
        setVoiceStatus('idle');
      } finally {
        setLoading(false);
      }
    },
    [
      appendEvents,
      appendUserMessage,
      applyResponse,
      speakResponseSpeech,
      syncFullState,
      terminalId,
    ],
  );

  const sendChat = useCallback(
    async (text, options = {}) => {
      const trimmed = (text || '').trim();
      if (!trimmed) return;
      setError(null);
      setNotice(null);
      setLoading(true);
      setVoiceStatus('thinking');
      try {
        const source = options.source || 'text';
        const autoSpeak = options.autoSpeak !== false;
        const resp = await postChat(terminalId, trimmed, source);
        applyResponse(resp, { fromUserText: trimmed, source: 'chat' });
        await syncFullState();
        if (autoSpeak) {
          await speakResponseSpeech(resp, 'chat-tts');
        } else {
          setVoiceStatus('idle');
        }
      } catch (e) {
        setError(`发送失败: ${e.message}`);
        setVoiceStatus('idle');
        if (options.throwOnError) throw e;
      } finally {
        setLoading(false);
      }
    },
    [terminalId, applyResponse, speakResponseSpeech, syncFullState],
  );

  const sendControl = useCallback(
    async (command, options = {}) => {
      setError(null);
      setLoading(true);
      try {
        const resp = await postControl(terminalId, command);
        applyResponse(resp, { source: 'control' });
        await syncFullState();
      } catch (e) {
        setError(`控制 ${command} 失败: ${e.message}`);
        if (options.throwOnError) throw e;
      } finally {
        setLoading(false);
      }
    },
    [terminalId, applyResponse, syncFullState],
  );

  const sendVision = useCallback(
    async (file, options = {}) => {
      const f = file || pendingImage;
      if (!f) {
        setError('请先选择一张食材画面');
        if (options.throwOnError) throw new Error('请先选择一张食材画面');
        return;
      }
      setError(null);
      setLoading(true);
      try {
        const resp = await postVision(terminalId, f, 'ingredients');
        const obs = resp?.data?.observation;
        if (obs) setLastObservation(obs);
        applyResponse(resp, { source: 'vision' });
        await syncFullState();
      } catch (e) {
        setError(`视觉识别失败: ${e.message}`);
        if (options.throwOnError) throw e;
      } finally {
        setLoading(false);
      }
    },
    [terminalId, pendingImage, applyResponse, syncFullState],
  );

  const handleSelectImage = useCallback((file) => {
    setPendingImage(file);
    if (file) {
      const reader = new FileReader();
      reader.onload = () => setLastVisionPreview(reader.result);
      reader.readAsDataURL(file);
    } else {
      setLastVisionPreview(null);
    }
  }, []);

  const triggerImagePicker = useCallback(() => {
    if (visionInputRef.current) visionInputRef.current.click();
  }, []);

  const handleImageInputChange = useCallback(
    (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      handleSelectImage(file);
      setState((prev) => ({ ...prev, ui_mode: 'vision' }));
    },
    [handleSelectImage],
  );

  const triggerAudioPicker = useCallback(() => {
    if (audioInputRef.current) audioInputRef.current.click();
  }, []);

  const handleVoicePrimary = useCallback(async () => {
    setError(null);
    setNotice(null);
    if (voiceSession.isActive) {
      await voiceSession.sleepSession();
      return;
    }
    await voiceSession.startSession();
  }, [voiceSession]);

  useEffect(() => {
    if (voiceSession.error) setError(voiceSession.error);
  }, [voiceSession.error]);

  const handleAudioInputChange = useCallback(
    async (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      try {
        await runRecordedVoiceTurn(file, 'upload');
      } finally {
        if (audioInputRef.current) audioInputRef.current.value = '';
      }
    },
    [runRecordedVoiceTurn],
  );

  const playLatestSpeech = useCallback(async () => {
    const last = [...chatLog].reverse().find((m) => m.role === 'nini');
    if (!last) {
      setError('暂无可播放的播报内容');
      return;
    }
    setError(null);
    setVoiceStatus('speaking');
    try {
      const playback = await requestSpeechPlayback(last.text, 'tts');
      if (!playback.played) setNotice(playbackNotice(playback, true));
    } catch (e) {
      setError(`语音播报失败: ${e.message}`);
    } finally {
      setVoiceStatus('idle');
    }
  }, [chatLog, requestSpeechPlayback]);

  const exportMemory = useCallback(async (options = {}) => {
    setError(null);
    try {
      const md = await getMemoryMarkdown(terminalId);
      setMemoryMarkdown(md);
    } catch (e) {
      setError(`导出记忆失败: ${e.message}`);
      if (options.throwOnError) throw e;
    }
  }, [terminalId]);

  const runDemoFlow = useCallback(async () => {
    if (demoRunning) return;
    setDemoRunning(true);
    setError(null);
    setMemoryMarkdown('');
    setChatLog([]);
    setRecentEvents([]);
    const step = async (label, fn, gap = 600) => {
      setDemoStep(label);
      try {
        await fn();
      } catch (e) {
        setError(`演示步骤「${label}」失败: ${e.message}`);
        throw e;
      }
      await sleep(gap);
    };
    try {
      await step('重置终端', () => sendControl('reset', { throwOnError: true }));
      await step(
        '规划晚餐',
        () => sendChat(DEMO_PLAN_TEXT, { throwOnError: true, autoSpeak: false }),
        800,
      );
      await step(
        '查看食材',
        () =>
          sendVision(pendingImage || createDemoIngredientsFile(), {
            throwOnError: true,
          }),
        800,
      );
      await step('开始烹饪', () => sendControl('start', { throwOnError: true }));
      await step(
        '记住口味',
        () => sendChat(DEMO_SOUR_TEXT, { throwOnError: true, autoSpeak: false }),
        800,
      );
      await step('进入下一步', () => sendControl('next_step', { throwOnError: true }));
      await step('暂停', () => sendControl('pause', { throwOnError: true }));
      await step('继续', () => sendControl('resume', { throwOnError: true }));
      await step('完成复盘', () => sendControl('finish', { throwOnError: true }));
      await step('导出家庭记忆', () => exportMemory({ throwOnError: true }));
      setDemoStep('完成');
    } catch {
      setDemoStep('需要处理');
    } finally {
      setDemoRunning(false);
    }
  }, [demoRunning, sendControl, sendChat, sendVision, exportMemory, pendingImage]);

  const mode = useMemo(() => {
    return serviceModeLabel(health?.demo_mode);
  }, [health]);

  const speechRecognitionHint = useMemo(() => {
    const providers = health?.providers || {};
    const modeValue = providers.speech_provider_mode;
    if (modeValue === 'mock') return '语音识别：演示模式，会返回固定指令';
    if (['real', 'auto'].includes(modeValue)) {
      return '语音识别：当前暂用演示兜底';
    }
    return '';
  }, [health]);

  const memories = apiData?.memories || [];
  const inventory = apiData?.inventory || [];
  const toolEventsServer = apiData?.tool_events || [];
  const providerLogs = apiData?.provider_logs || [];

  const combinedEvents = useMemo(() => {
    const seen = new Set();
    const all = [...toolEventsServer, ...recentEvents];
    const dedup = [];
    for (const ev of all) {
      const key = ev.id || `${ev.name}-${ev.created_at || ''}-${ev.event_type || ''}`;
      if (seen.has(key)) continue;
      seen.add(key);
      dedup.push(ev);
    }
    return dedup;
  }, [toolEventsServer, recentEvents]);

  const recorderError = voiceSession.error;
  const recordingDurationMs = voiceSession.durationMs;
  const recordingState = ['unsupported', 'denied'].includes(voiceSession.sessionState)
    ? voiceSession.sessionState
    : voiceSession.isActive
      ? 'recording'
      : 'idle';
  const voiceDisplayStatus =
    voiceSession.sessionState !== 'sleeping' ? voiceSession.sessionState : voiceStatus;

  return (
    <div className="app-root">
      <TopBar
        appState={state.ui_mode || 'planning'}
        currentStepIndex={state.current_step_index}
        totalSteps={state.recipe?.steps?.length}
        voiceStatus={voiceDisplayStatus}
        currentTime={currentTime}
        mode={mode}
        terminalId={terminalId}
        onTerminalIdChange={setTerminalId}
      />

      {error ? (
        <div className="app-banner">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)}>
            关闭
          </button>
        </div>
      ) : null}
      {!error && notice ? (
        <div className="app-banner notice">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice(null)}>
            关闭
          </button>
        </div>
      ) : null}

      <div className="demo-bar">
        <span className="label">演示</span>
        <button
          type="button"
          className="demo-btn"
          disabled={demoRunning}
          onClick={runDemoFlow}
        >
          {demoRunning ? '运行中…' : '一键演示'}
        </button>
        <button
          type="button"
          className="demo-btn secondary"
          disabled={demoRunning || loading}
          onClick={triggerImagePicker}
        >
          {pendingImage ? '已选择食材画面' : '选择食材画面（可选）'}
        </button>
        <button
          type="button"
          className="demo-btn secondary"
          disabled={demoRunning || loading}
          onClick={() => sendControl('reset')}
        >
          重置
        </button>
        {demoStep ? (
          <span className="demo-step">进度：{demoStep}</span>
        ) : null}
      </div>

      <div className="app-body">
        <div className="app-col left">
          <LeftPanel
            messages={chatLog}
            voiceStatus={voiceDisplayStatus}
            uiMode={state.ui_mode || 'planning'}
            loading={loading}
            onSend={sendChat}
            onVoicePrimary={handleVoicePrimary}
            onPickImage={triggerImagePicker}
            onPickAudio={triggerAudioPicker}
            onPlayTts={playLatestSpeech}
            recordingState={recordingState}
            recorderError={recorderError}
            recordingDurationMs={recordingDurationMs}
            speechRecognitionHint={voiceSession.recognitionMode || speechRecognitionHint}
            partialTranscript={voiceSession.partialTranscript}
            finalTranscript={voiceSession.finalTranscript}
            ttsVendor={ttsVendor}
            onTtsVendorChange={handleTtsVendorChange}
            onQuickAction={(action) => {
              if (action === 'planning') sendControl('reset');
              else if (action === 'cooking') sendControl('start');
              else if (action === 'review') sendControl('finish');
            }}
          />
        </div>
        <div className="app-col center">
          <CenterPanel
            uiMode={state.ui_mode || 'planning'}
            state={state}
            memories={memories}
            inventory={inventory}
            providerLogs={providerLogs}
            recipeDocuments={apiData?.recipe_documents || []}
            visionPreview={lastVisionPreview}
            lastObservation={lastObservation}
            recentEvents={combinedEvents}
            memoryMarkdown={memoryMarkdown}
            onControl={sendControl}
            onPickImage={triggerImagePicker}
            onUploadVision={() => sendVision()}
            onExportMemory={exportMemory}
            loading={loading}
          />
        </div>
        <div className="app-col right">
          <RightPanel
            uiMode={state.ui_mode || 'planning'}
            events={combinedEvents}
            memories={memories}
            state={state}
            inventory={inventory}
            providerLogs={providerLogs}
            health={health}
            highlightTrigger={highlightTrigger}
          />
        </div>
      </div>

      <input
        ref={visionInputRef}
        type="file"
        accept="image/*"
        style={{ display: 'none' }}
        onChange={handleImageInputChange}
      />
      <input
        ref={audioInputRef}
        type="file"
        accept="audio/*"
        style={{ display: 'none' }}
        onChange={handleAudioInputChange}
      />
    </div>
  );
}
