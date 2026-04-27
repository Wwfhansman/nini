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

const DEMO_PLAN_TEXT =
  '我最近减脂，妈妈不吃辣，冰箱里有鸡胸肉、番茄、鸡蛋，今晚做什么？';
const DEMO_SOUR_TEXT = '记住我不喜欢太酸';

const nowTime = () =>
  new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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
        if (!cancelled) setError(`无法连接后端 /health: ${e.message}`);
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
        setError('请先选择一张食材照片');
        if (options.throwOnError) throw new Error('请先选择一张食材照片');
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

  const handleAudioInputChange = useCallback(
    async (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      setError(null);
      setVoiceStatus('listening');
      setLoading(true);
      try {
        const resp = await postSpeechAsr(terminalId, file);
        const text = resp?.data?.text;
        const events = Array.isArray(resp.events) ? resp.events : [];
        if (events.length) {
          setRecentEvents((prev) => [
            ...prev,
            ...events.map((e) => ({ ...e, _source: 'asr' })),
          ]);
        }
        setVoiceStatus('idle');
        if (text) {
          await sendChat(text);
        }
      } catch (e) {
        setError(`ASR 失败: ${e.message}`);
        setVoiceStatus('idle');
      } finally {
        setLoading(false);
        if (audioInputRef.current) audioInputRef.current.value = '';
      }
    },
    [terminalId, sendChat],
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
      const resp = await postSpeechTts(terminalId, last.text);
      const data = resp?.data || {};
      const events = Array.isArray(resp.events) ? resp.events : [];
      if (events.length) {
        setRecentEvents((prev) => [
          ...prev,
          ...events.map((e) => ({ ...e, _source: 'tts' })),
        ]);
      }
      if (data.audio_base64 && !data.fallback_used && data.mime_type) {
        const src = `data:${data.mime_type};base64,${data.audio_base64}`;
        const audio = new Audio(src);
        audio.onended = () => setVoiceStatus('idle');
        audio.onerror = () => setVoiceStatus('idle');
        await audio.play().catch(() => setVoiceStatus('idle'));
      } else {
        setVoiceStatus('idle');
      }
    } catch (e) {
      setError(`TTS 失败: ${e.message}`);
      setVoiceStatus('idle');
    }
  }, [chatLog, terminalId]);

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
        setError(`Demo 步骤「${label}」失败: ${e.message}`);
        throw e;
      }
      await sleep(gap);
    };
    try {
      await step('reset', () => sendControl('reset', { throwOnError: true }));
      await step('chat: 家庭约束', () => sendChat(DEMO_PLAN_TEXT, { throwOnError: true }), 800);
      if (pendingImage) {
        await step('vision', () => sendVision(pendingImage, { throwOnError: true }), 800);
      } else {
        setDemoStep('skip vision (no image)');
        await sleep(400);
      }
      await step('control: start', () => sendControl('start', { throwOnError: true }));
      await step('chat: 不喜欢太酸', () => sendChat(DEMO_SOUR_TEXT, { throwOnError: true }), 800);
      await step('control: next_step', () => sendControl('next_step', { throwOnError: true }));
      await step('control: pause', () => sendControl('pause', { throwOnError: true }));
      await step('control: resume', () => sendControl('resume', { throwOnError: true }));
      await step('control: finish', () => sendControl('finish', { throwOnError: true }));
      await step('export memory', () => exportMemory({ throwOnError: true }));
      setDemoStep('done');
    } catch {
      setDemoStep('error');
    } finally {
      setDemoRunning(false);
    }
  }, [demoRunning, sendControl, sendChat, sendVision, exportMemory, pendingImage]);

  const mode = useMemo(() => {
    const dm = (health?.demo_mode || 'mock').toLowerCase();
    return dm.charAt(0).toUpperCase() + dm.slice(1);
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

  return (
    <div className="app-root">
      <TopBar
        appState={state.ui_mode || 'planning'}
        currentStepIndex={state.current_step_index}
        totalSteps={state.recipe?.steps?.length}
        voiceStatus={voiceStatus}
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
          {demoRunning ? '运行中…' : '一键运行 Demo'}
        </button>
        <button
          type="button"
          className="demo-btn secondary"
          disabled={demoRunning || loading}
          onClick={triggerImagePicker}
        >
          {pendingImage ? '已选择食材图' : '选择食材图（可选）'}
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
          <span className="demo-step">step: {demoStep}</span>
        ) : null}
      </div>

      <div className="app-body">
        <div className="app-col left">
          <LeftPanel
            messages={chatLog}
            voiceStatus={voiceStatus}
            loading={loading}
            onSend={sendChat}
            onPickImage={triggerImagePicker}
            onPickAudio={triggerAudioPicker}
            onPlayTts={playLatestSpeech}
            speechMode={health?.providers?.speech_provider_mode}
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
