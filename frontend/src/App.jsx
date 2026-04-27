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
import useVoiceRecorder from './hooks/useVoiceRecorder.js';

const DEMO_PLAN_TEXT =
  '我最近减脂，妈妈不吃辣，冰箱里有鸡胸肉、番茄、鸡蛋，今晚做什么？';
const DEMO_SOUR_TEXT = '记住我不喜欢太酸';

const nowTime = () =>
  new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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

function playAudioBase64({ audio_base64: audioBase64, mime_type: mimeType, fallback_used: fallbackUsed }) {
  if (!audioBase64 || fallbackUsed || !mimeType) {
    return Promise.resolve(false);
  }
  const src = `data:${mimeType};base64,${audioBase64}`;
  const audio = new Audio(src);
  return new Promise((resolve) => {
    let settled = false;
    const done = (played) => {
      if (settled) return;
      settled = true;
      resolve(played);
    };
    audio.onended = () => done(true);
    audio.onerror = () => done(false);
    audio.play().catch(() => done(false));
  });
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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
  const {
    recordingState,
    error: recorderError,
    durationMs,
    startRecording,
    stopRecording,
  } = useVoiceRecorder();

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
      if (!text) return false;
      const resp = await postSpeechTts(terminalId, text);
      appendEvents(resp, source);
      return playAudioBase64(resp?.data || {});
    },
    [appendEvents, terminalId],
  );

  const runRecordedVoiceTurn = useCallback(
    async (audio, source = 'recording') => {
      if (!audio) return;
      setError(null);
      setLoading(true);
      try {
        setVoiceStatus('recognizing');
        const audioFile = toAudioFile(audio);
        const asrResp = await postSpeechAsr(terminalId, audioFile);
        appendEvents(asrResp, `${source}-asr`);
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

        const speech = chatResp?.data?.speech;
        if (speech) {
          setVoiceStatus('speaking');
          await requestSpeechPlayback(speech, `${source}-tts`);
        }
        setVoiceStatus('idle');
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
      requestSpeechPlayback,
      syncFullState,
      terminalId,
    ],
  );

  const sendChat = useCallback(
    async (text, options = {}) => {
      const trimmed = (text || '').trim();
      if (!trimmed) return;
      setError(null);
      setLoading(true);
      setVoiceStatus('thinking');
      try {
        const resp = await postChat(terminalId, trimmed, 'text');
        applyResponse(resp, { fromUserText: trimmed, source: 'chat' });
        await syncFullState();
        setVoiceStatus('idle');
      } catch (e) {
        setError(`发送失败: ${e.message}`);
        setVoiceStatus('idle');
        if (options.throwOnError) throw e;
      } finally {
        setLoading(false);
      }
    },
    [terminalId, applyResponse, syncFullState],
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
    if (recordingState === 'unsupported') {
      setError('当前浏览器不支持录音，请使用上传录音兜底。');
      return;
    }
    if (recordingState === 'denied') {
      setError('麦克风权限被拒绝，请使用上传录音兜底。');
      return;
    }
    if (recordingState === 'recording' || voiceStatus === 'recording') {
      setError(null);
      setVoiceStatus('stopping');
      const blob = await stopRecording();
      if (!blob || blob.size === 0) {
        setError('没有录到有效语音，请再试一次。');
        setVoiceStatus('idle');
        return;
      }
      await runRecordedVoiceTurn(blob, 'recording');
      return;
    }
    if (['requesting', 'stopping', 'recognizing', 'thinking', 'speaking'].includes(voiceStatus)) {
      return;
    }

    setError(null);
    setVoiceStatus('requesting');
    const started = await startRecording();
    setVoiceStatus(started ? 'recording' : 'idle');
  }, [
    recordingState,
    runRecordedVoiceTurn,
    startRecording,
    stopRecording,
    voiceStatus,
  ]);

  useEffect(() => {
    if (recorderError) setError(recorderError);
  }, [recorderError]);

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
      const played = await requestSpeechPlayback(last.text, 'tts');
      if (!played) setError('暂无可播放音频，已保留文字回复。');
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
      await step('规划晚餐', () => sendChat(DEMO_PLAN_TEXT, { throwOnError: true }), 800);
      if (pendingImage) {
        await step('查看食材', () => sendVision(pendingImage, { throwOnError: true }), 800);
      } else {
        setDemoStep('跳过查看食材');
        await sleep(400);
      }
      await step('开始烹饪', () => sendControl('start', { throwOnError: true }));
      await step('记住口味', () => sendChat(DEMO_SOUR_TEXT, { throwOnError: true }), 800);
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

  const voiceDisplayStatus =
    voiceStatus === 'idle' && ['unsupported', 'denied'].includes(recordingState)
      ? recordingState
      : voiceStatus;

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
            recordingDurationMs={durationMs}
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
