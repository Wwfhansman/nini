import { useCallback, useEffect, useRef, useState } from 'react';

const MIME_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/mp4',
  'audio/wav',
  '',
];

function isRecorderSupported() {
  return Boolean(
    typeof window !== 'undefined' &&
      typeof navigator !== 'undefined' &&
      navigator.mediaDevices?.getUserMedia &&
      typeof window.MediaRecorder !== 'undefined',
  );
}

function pickMimeType() {
  if (typeof window === 'undefined' || typeof window.MediaRecorder === 'undefined') {
    return '';
  }
  return (
    MIME_CANDIDATES.find(
      (candidate) => !candidate || window.MediaRecorder.isTypeSupported(candidate),
    ) || ''
  );
}

function stopStream(stream) {
  stream?.getTracks?.().forEach((track) => track.stop());
}

export default function useVoiceRecorder() {
  const supportedRef = useRef(isRecorderSupported());
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const startedAtRef = useRef(0);
  const durationTimerRef = useRef(null);
  const stopPromiseRef = useRef(null);

  const [recordingState, setRecordingState] = useState(
    supportedRef.current ? 'idle' : 'unsupported',
  );
  const [audioBlob, setAudioBlob] = useState(null);
  const [error, setError] = useState(null);
  const [durationMs, setDurationMs] = useState(0);

  const clearDurationTimer = useCallback(() => {
    if (durationTimerRef.current) {
      window.clearInterval(durationTimerRef.current);
      durationTimerRef.current = null;
    }
  }, []);

  const resetRecorder = useCallback(() => {
    clearDurationTimer();
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      try {
        recorderRef.current.stop();
      } catch {
        // Recorder is already stopping; stream cleanup below is still safe.
      }
    }
    stopStream(streamRef.current);
    recorderRef.current = null;
    streamRef.current = null;
    chunksRef.current = [];
    stopPromiseRef.current = null;
  }, [clearDurationTimer]);

  useEffect(() => () => resetRecorder(), [resetRecorder]);

  const startRecording = useCallback(async () => {
    if (!supportedRef.current) {
      setRecordingState('unsupported');
      setError('当前浏览器不支持录音，请选择语音文件。');
      return false;
    }
    if (recordingState === 'recording' || recordingState === 'requesting') {
      return false;
    }

    setRecordingState('requesting');
    setAudioBlob(null);
    setError(null);
    setDurationMs(0);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = pickMimeType();
      const recorder = new window.MediaRecorder(
        stream,
        mimeType ? { mimeType } : undefined,
      );

      recorderRef.current = recorder;
      chunksRef.current = [];
      startedAtRef.current = Date.now();

      recorder.ondataavailable = (event) => {
        if (event.data?.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        setError('录音过程中出现错误，请重试或选择语音文件。');
      };
      recorder.onstop = () => {
        clearDurationTimer();
        const type = recorder.mimeType || mimeType || 'audio/webm';
        const blob = chunksRef.current.length
          ? new Blob(chunksRef.current, { type })
          : null;
        stopStream(streamRef.current);
        streamRef.current = null;
        recorderRef.current = null;
        chunksRef.current = [];
        setAudioBlob(blob);
        setDurationMs(startedAtRef.current ? Date.now() - startedAtRef.current : 0);
        setRecordingState('idle');
        if (stopPromiseRef.current) {
          stopPromiseRef.current.resolve(blob);
          stopPromiseRef.current = null;
        }
      };

      recorder.start();
      durationTimerRef.current = window.setInterval(() => {
        setDurationMs(Date.now() - startedAtRef.current);
      }, 200);
      setRecordingState('recording');
      return true;
    } catch (err) {
      stopStream(streamRef.current);
      streamRef.current = null;
      const denied =
        err?.name === 'NotAllowedError' ||
        err?.name === 'PermissionDeniedError' ||
        err?.name === 'SecurityError';
      setRecordingState(denied ? 'denied' : 'idle');
      setError(denied ? '麦克风权限被拒绝，请选择语音文件。' : err.message);
      return false;
    }
  }, [clearDurationTimer, recordingState]);

  const stopRecording = useCallback(() => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state !== 'recording') {
      return Promise.resolve(audioBlob);
    }
    setRecordingState('stopping');
    const promise = new Promise((resolve, reject) => {
      stopPromiseRef.current = { resolve, reject };
    });
    try {
      recorder.requestData?.();
      recorder.stop();
    } catch (err) {
      setRecordingState('idle');
      setError(err.message);
      stopPromiseRef.current?.reject(err);
      stopPromiseRef.current = null;
    }
    return promise;
  }, [audioBlob]);

  const cancelRecording = useCallback(() => {
    resetRecorder();
    setAudioBlob(null);
    setDurationMs(0);
    setRecordingState(supportedRef.current ? 'idle' : 'unsupported');
  }, [resetRecorder]);

  return {
    recordingState,
    audioBlob,
    error,
    durationMs,
    startRecording,
    stopRecording,
    cancelRecording,
  };
}
