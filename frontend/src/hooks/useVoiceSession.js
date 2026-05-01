import { useCallback, useEffect, useRef, useState } from 'react';
import { getVoiceWebSocketUrl } from '../api.js';

const TARGET_SAMPLE_RATE = 16000;
const CHUNK_MS = 160;
const CHUNK_SAMPLES = Math.round((TARGET_SAMPLE_RATE * CHUNK_MS) / 1000);
const VAD_THRESHOLD = 0.012;
const SPEECH_END_SILENCE_MS = 900;
const QUIET_PACKET_INTERVAL_MS = 900;

function isSupported() {
  return Boolean(
    typeof window !== 'undefined' &&
      typeof navigator !== 'undefined' &&
      navigator.mediaDevices?.getUserMedia &&
      (window.AudioContext || window.webkitAudioContext) &&
      typeof window.WebSocket !== 'undefined',
  );
}

function stopStream(stream) {
  stream?.getTracks?.().forEach((track) => track.stop());
}

function rms(buffer) {
  if (!buffer.length) return 0;
  let sum = 0;
  for (let i = 0; i < buffer.length; i += 1) {
    sum += buffer[i] * buffer[i];
  }
  return Math.sqrt(sum / buffer.length);
}

function downsample(buffer, sourceRate, targetRate) {
  if (sourceRate === targetRate) return buffer;
  if (sourceRate < targetRate) return buffer;

  const ratio = sourceRate / targetRate;
  const length = Math.floor(buffer.length / ratio);
  const result = new Float32Array(length);
  let offset = 0;
  for (let i = 0; i < length; i += 1) {
    const nextOffset = Math.round((i + 1) * ratio);
    let sum = 0;
    let count = 0;
    for (let j = offset; j < nextOffset && j < buffer.length; j += 1) {
      sum += buffer[j];
      count += 1;
    }
    result[i] = count ? sum / count : 0;
    offset = nextOffset;
  }
  return result;
}

function floatToPcm16(floatBuffer) {
  const pcm = new Int16Array(floatBuffer.length);
  for (let i = 0; i < floatBuffer.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, floatBuffer[i]));
    pcm[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return pcm;
}

function concatSamples(current, next) {
  if (!current.length) return Array.from(next);
  const merged = current.slice();
  for (let i = 0; i < next.length; i += 1) merged.push(next[i]);
  return merged;
}

function voiceNotice(message) {
  if (!message) return '语音会话暂时不可用。';
  if (message.includes('已切换')) {
    return '语音连接不稳定，已切换为备用识别。';
  }
  if (message.includes('上传') || message.includes('录音')) {
    return '语音暂时不可用，请选择语音文件。';
  }
  return message;
}

export default function useVoiceSession({ terminalId, onAgentEvent, onAgentResponse, onError }) {
  const supportedRef = useRef(isSupported());
  const wsRef = useRef(null);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const sourceRef = useRef(null);
  const processorRef = useRef(null);
  const gainRef = useRef(null);
  const pendingSamplesRef = useRef([]);
  const capturePausedRef = useRef(false);
  const lastQuietPacketAtRef = useRef(0);
  const speechStartedRef = useRef(false);
  const audioEndSentRef = useRef(false);
  const lastVoiceAtRef = useRef(0);
  const startedAtRef = useRef(0);
  const durationTimerRef = useRef(null);
  const pendingFinalRef = useRef('');
  const responseSerialRef = useRef(Promise.resolve());

  const [sessionState, setSessionState] = useState(
    supportedRef.current ? 'sleeping' : 'unsupported',
  );
  const [partialTranscript, setPartialTranscript] = useState('');
  const [finalTranscript, setFinalTranscript] = useState('');
  const [provider, setProvider] = useState(null);
  const [fallbackUsed, setFallbackUsed] = useState(false);
  const [error, setError] = useState(null);
  const [durationMs, setDurationMs] = useState(0);

  const cleanupAudio = useCallback(async () => {
    if (durationTimerRef.current) {
      window.clearInterval(durationTimerRef.current);
      durationTimerRef.current = null;
    }
    try {
      processorRef.current?.disconnect();
    } catch {
      // Audio node may already be detached.
    }
    try {
      sourceRef.current?.disconnect();
    } catch {
      // Audio node may already be detached.
    }
    try {
      gainRef.current?.disconnect();
    } catch {
      // Audio node may already be detached.
    }
    processorRef.current = null;
    sourceRef.current = null;
    gainRef.current = null;
    stopStream(streamRef.current);
    streamRef.current = null;
    pendingSamplesRef.current = [];
    capturePausedRef.current = false;
    speechStartedRef.current = false;
    audioEndSentRef.current = false;
    lastVoiceAtRef.current = 0;
    const ctx = audioContextRef.current;
    audioContextRef.current = null;
    if (ctx && ctx.state !== 'closed') {
      try {
        await ctx.close();
      } catch {
        // Closing can fail if the browser already disposed the context.
      }
    }
  }, []);

  const closeSocket = useCallback(() => {
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws && ws.readyState <= WebSocket.OPEN) {
      try {
        ws.close();
      } catch {
        // Socket may already be closed by the server.
      }
    }
  }, []);

  const stopSession = useCallback(async () => {
    closeSocket();
    await cleanupAudio();
    setSessionState(supportedRef.current ? 'sleeping' : 'unsupported');
    setDurationMs(0);
  }, [cleanupAudio, closeSocket]);

  useEffect(() => () => {
    closeSocket();
    cleanupAudio();
  }, [cleanupAudio, closeSocket]);

  const sendChunk = useCallback((samples) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN || !samples.length) return;
    const pcm = Int16Array.from(samples);
    ws.send(pcm.buffer);
  }, []);

  const sendJson = useCallback((payload) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(payload));
    return true;
  }, []);

  const flushSamples = useCallback((force = false) => {
    const pending = pendingSamplesRef.current;
    while (pending.length >= CHUNK_SAMPLES || (force && pending.length)) {
      const take = force ? Math.min(pending.length, CHUNK_SAMPLES) : CHUNK_SAMPLES;
      const chunk = pending.splice(0, take);
      sendChunk(chunk);
    }
  }, [sendChunk]);

  const finishUtterance = useCallback(() => {
    if (audioEndSentRef.current) return;
    flushSamples(true);
    if (!sendJson({ type: 'audio.end' })) return;
    audioEndSentRef.current = true;
    speechStartedRef.current = false;
  }, [flushSamples, sendJson]);

  const startAudio = useCallback(async () => {
    const AudioCtor = window.AudioContext || window.webkitAudioContext;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    const ctx = new AudioCtor();
    const source = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    const zeroGain = ctx.createGain();
    zeroGain.gain.value = 0;

    processor.onaudioprocess = (event) => {
      if (capturePausedRef.current) return;
      const input = event.inputBuffer.getChannelData(0);
      const level = rms(input);
      const now = Date.now();
      const quiet = level < VAD_THRESHOLD;
      if (!quiet) {
        speechStartedRef.current = true;
        audioEndSentRef.current = false;
        lastVoiceAtRef.current = now;
      }
      if (
        quiet &&
        speechStartedRef.current &&
        !audioEndSentRef.current &&
        lastVoiceAtRef.current &&
        now - lastVoiceAtRef.current >= SPEECH_END_SILENCE_MS
      ) {
        finishUtterance();
        return;
      }
      if (quiet && !speechStartedRef.current) {
        return;
      }
      if (quiet && now - lastQuietPacketAtRef.current < QUIET_PACKET_INTERVAL_MS) {
        return;
      }
      if (quiet) lastQuietPacketAtRef.current = now;
      const resampled = downsample(input, ctx.sampleRate, TARGET_SAMPLE_RATE);
      const pcm = floatToPcm16(resampled);
      pendingSamplesRef.current = concatSamples(pendingSamplesRef.current, pcm);
      flushSamples(false);
    };

    source.connect(processor);
    processor.connect(zeroGain);
    zeroGain.connect(ctx.destination);

    streamRef.current = stream;
    audioContextRef.current = ctx;
    sourceRef.current = source;
    processorRef.current = processor;
    gainRef.current = zeroGain;
  }, [finishUtterance, flushSamples]);

  const handleMessage = useCallback(
    async (event) => {
      let payload = null;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }
      if (payload.type === 'session.state') {
        setSessionState(payload.state || 'sleeping');
        return;
      }
      if (payload.type === 'asr.provider') {
        setProvider(payload.provider || null);
        setFallbackUsed(Boolean(payload.fallback_used));
        return;
      }
      if (payload.type === 'asr.partial') {
        setPartialTranscript(payload.text || '');
        setSessionState((current) =>
          current === 'listening_for_wake' || current === 'active_listening'
            ? 'transcribing'
            : current,
        );
        return;
      }
      if (payload.type === 'asr.final') {
        const text = payload.text || '';
        pendingFinalRef.current = text;
        setFinalTranscript(text);
        setPartialTranscript('');
        speechStartedRef.current = false;
        audioEndSentRef.current = false;
        return;
      }
      if (payload.type === 'wake.detected') {
        setSessionState('active_listening');
        return;
      }
      if (payload.type === 'agent.event') {
        onAgentEvent?.(payload.event);
        return;
      }
      if (payload.type === 'agent.response') {
        const transcript = pendingFinalRef.current;
        pendingFinalRef.current = '';
        const response = {
          ok: true,
          data: payload.data || { speech: payload.speech || '' },
          state: payload.state || {},
          events: payload.events || [],
          error: null,
        };
        responseSerialRef.current = responseSerialRef.current.then(async () => {
          setSessionState('speaking');
          capturePausedRef.current = true;
          try {
            await onAgentResponse?.(response, transcript);
          } finally {
            capturePausedRef.current = false;
            if (wsRef.current?.readyState === WebSocket.OPEN) {
              setSessionState('active_listening');
            }
          }
        });
        return;
      }
      if (payload.type === 'error') {
        const message = voiceNotice(payload.message);
        if (payload.message?.includes('已切换')) {
          setError(null);
          setFallbackUsed(true);
        } else {
          setError(message);
        }
        onError?.(message);
      }
    },
    [onAgentEvent, onAgentResponse, onError],
  );

  const startSession = useCallback(async () => {
    if (!supportedRef.current) {
      const message = '当前浏览器不支持实时语音，请选择语音文件。';
      setError(message);
      setSessionState('unsupported');
      onError?.(message);
      return false;
    }

    setError(null);
    setPartialTranscript('');
    setFinalTranscript('');
    setSessionState('requesting');
    try {
      await cleanupAudio();
      await startAudio();
      const ws = new WebSocket(getVoiceWebSocketUrl());
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;
      await new Promise((resolve, reject) => {
        ws.onopen = resolve;
        ws.onerror = () => reject(new Error('无法建立语音会话连接。'));
      });
      ws.onmessage = (message) => {
        handleMessage(message);
      };
      ws.onclose = () => {
        wsRef.current = null;
        cleanupAudio();
        setSessionState((current) =>
          current === 'sleeping' || current === 'unsupported' ? current : 'sleeping',
        );
      };
      ws.send(
        JSON.stringify({
          type: 'session.start',
          terminal_id: terminalId,
          sample_rate: TARGET_SAMPLE_RATE,
        }),
      );
      startedAtRef.current = Date.now();
      durationTimerRef.current = window.setInterval(() => {
        setDurationMs(Date.now() - startedAtRef.current);
      }, 250);
      return true;
    } catch (err) {
      await cleanupAudio();
      closeSocket();
      const denied =
        err?.name === 'NotAllowedError' ||
        err?.name === 'PermissionDeniedError' ||
        err?.name === 'SecurityError';
      const message = denied
        ? '麦克风权限被拒绝，请选择语音文件。'
        : err.message || '语音会话启动失败。';
      setError(message);
      setSessionState(denied ? 'denied' : 'error');
      onError?.(message);
      return false;
    }
  }, [cleanupAudio, closeSocket, handleMessage, onError, startAudio, terminalId]);

  const sleepSession = useCallback(async () => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      sendJson({ type: 'session.sleep' });
    }
    await stopSession();
  }, [sendJson, stopSession]);

  const isActive = !['sleeping', 'unsupported', 'denied', 'error'].includes(sessionState);
  const recognitionMode =
    provider === 'mock_streaming_asr' || fallbackUsed ? '语音已准备好' : '';

  return {
    sessionState,
    partialTranscript,
    finalTranscript,
    provider,
    fallbackUsed,
    error,
    durationMs,
    isActive,
    recognitionMode,
    startSession,
    sleepSession,
  };
}
