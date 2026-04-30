"""Volcengine bigmodel streaming ASR provider.

The provider keeps Volcengine's binary frame handling isolated from the voice
session. It follows the official bigmodel SAUC WebSocket shape: an initial JSON
request frame followed by PCM audio frames and a final negative-sequence frame.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from backend.config import Settings
from backend.speech.schemas import SpeechProviderError
from backend.speech.streaming_asr import StreamingASREvent


PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001

CLIENT_FULL_REQUEST = 0b0001
CLIENT_AUDIO_ONLY_REQUEST = 0b0010
SERVER_FULL_RESPONSE = 0b1001
SERVER_ACK = 0b1011
SERVER_ERROR_RESPONSE = 0b1111

NO_SEQUENCE = 0b0000
POS_SEQUENCE = 0b0001
NEG_SEQUENCE = 0b0010
NEG_WITH_SEQUENCE = 0b0011

NO_SERIALIZATION = 0b0000
JSON_SERIALIZATION = 0b0001

NO_COMPRESSION = 0b0000
GZIP_COMPRESSION = 0b0001


@dataclass(frozen=True)
class ParsedVolcFrame:
    message_type: int
    flags: int
    sequence: Optional[int]
    payload: Any
    log_id: Optional[str] = None


def _int32(value: int) -> bytes:
    return int(value).to_bytes(4, byteorder="big", signed=True)


def _read_int32(frame: bytes, offset: int) -> tuple[int, int]:
    return int.from_bytes(frame[offset : offset + 4], byteorder="big", signed=True), offset + 4


def _header(
    message_type: int,
    flags: int,
    serialization: int = JSON_SERIALIZATION,
    compression: int = GZIP_COMPRESSION,
) -> bytes:
    return bytes(
        [
            (PROTOCOL_VERSION << 4) | DEFAULT_HEADER_SIZE,
            (message_type << 4) | flags,
            (serialization << 4) | compression,
            0,
        ]
    )


def _encode_payload(payload: bytes | Dict[str, Any], compression: int = GZIP_COMPRESSION) -> bytes:
    if isinstance(payload, bytes):
        raw = payload
    else:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if compression == GZIP_COMPRESSION:
        return gzip.compress(raw)
    return raw


def build_full_request_frame(payload: Dict[str, Any], sequence: int = 1) -> bytes:
    body = _encode_payload(payload)
    return _header(CLIENT_FULL_REQUEST, POS_SEQUENCE) + _int32(sequence) + _int32(len(body)) + body


def build_audio_frame(chunk: bytes, sequence: int, final: bool = False) -> bytes:
    body = _encode_payload(chunk)
    flags = NEG_WITH_SEQUENCE if final else POS_SEQUENCE
    seq = -abs(sequence) if final else abs(sequence)
    return _header(CLIENT_AUDIO_ONLY_REQUEST, flags, NO_SERIALIZATION, GZIP_COMPRESSION) + _int32(seq) + _int32(len(body)) + body


def _decode_payload(payload: bytes, serialization: int, compression: int) -> Any:
    if compression == GZIP_COMPRESSION and payload:
        payload = gzip.decompress(payload)
    if serialization == JSON_SERIALIZATION and payload:
        return json.loads(payload.decode("utf-8"))
    if payload:
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError:
            return payload
    return None


def parse_volc_frame(frame: bytes) -> ParsedVolcFrame:
    if len(frame) < 4:
        raise SpeechProviderError("invalid Volcengine ASR frame", "volc_streaming_asr", "volc-bigmodel-streaming-asr")

    header_size = (frame[0] & 0x0F) * 4
    message_type = frame[1] >> 4
    flags = frame[1] & 0x0F
    serialization = frame[2] >> 4
    compression = frame[2] & 0x0F
    offset = header_size
    sequence: Optional[int] = None

    if flags in {POS_SEQUENCE, NEG_SEQUENCE, NEG_WITH_SEQUENCE} and len(frame) >= offset + 4:
        sequence, offset = _read_int32(frame, offset)

    if message_type == SERVER_ERROR_RESPONSE:
        error_code = None
        if len(frame) >= offset + 4:
            error_code, offset = _read_int32(frame, offset)
        payload_size = 0
        if len(frame) >= offset + 4:
            payload_size, offset = _read_int32(frame, offset)
        payload = frame[offset : offset + max(payload_size, 0)] if payload_size else frame[offset:]
        decoded = _decode_payload(payload, serialization, compression)
        message = decoded if isinstance(decoded, str) else json.dumps(decoded, ensure_ascii=False)
        raise SpeechProviderError(
            f"Volcengine ASR error {error_code}: {message}",
            "volc_streaming_asr",
            "volc-bigmodel-streaming-asr",
            status_code=error_code,
        )

    payload_size = 0
    if len(frame) >= offset + 4:
        payload_size, offset = _read_int32(frame, offset)
    payload = frame[offset : offset + max(payload_size, 0)] if payload_size else frame[offset:]
    return ParsedVolcFrame(
        message_type=message_type,
        flags=flags,
        sequence=sequence,
        payload=_decode_payload(payload, serialization, compression),
    )


def _first_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_first_text(item) for item in value]
        return "".join(part for part in parts if part)
    if not isinstance(value, dict):
        return ""

    for key in ("text", "utterance", "sentence"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    for key in ("result", "payload", "data"):
        nested = _first_text(value.get(key))
        if nested:
            return nested
    for key in ("utterances", "results"):
        nested = _first_text(value.get(key))
        if nested:
            return nested
    return ""


def _is_final_payload(value: Any, sequence: Optional[int]) -> bool:
    if sequence is not None and sequence < 0:
        return True
    if isinstance(value, dict):
        truthy = {True, 1, "true", "final", "definite", "completed"}
        for key in ("final", "is_final", "definite", "completed"):
            if value.get(key) in truthy:
                return True
        result = value.get("result")
        if isinstance(result, dict):
            for key in ("final", "is_final", "definite", "completed"):
                if result.get(key) in truthy:
                    return True
            utterances = result.get("utterances")
            if isinstance(utterances, list) and utterances:
                return any(isinstance(item, dict) and item.get("definite") is True for item in utterances)
    return False


def _extract_log_id(websocket: Any) -> Optional[str]:
    response = getattr(websocket, "response", None)
    headers = getattr(response, "headers", None) or getattr(websocket, "response_headers", None)
    if not headers:
        return None
    try:
        return headers.get("X-Tt-Logid") or headers.get("x-tt-logid")
    except AttributeError:
        return None


class VolcStreamingASRSession:
    provider = "volc_streaming_asr"
    model = "volc-bigmodel-streaming-asr"
    fallback_used = False

    def __init__(
        self,
        websocket: Any,
        reader_task: Optional["asyncio.Task[None]"] = None,
        log_id: Optional[str] = None,
    ) -> None:
        self.websocket = websocket
        self.reader_task = reader_task
        self.log_id = log_id
        self._queue: asyncio.Queue[StreamingASREvent] = asyncio.Queue()
        self._sequence = 2
        self._closed = False

    async def _read_loop(self) -> None:
        try:
            async for message in self.websocket:
                if isinstance(message, str):
                    try:
                        payload = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    text = _first_text(payload)
                    if text:
                        final = _is_final_payload(payload, None)
                        await self._queue.put(
                            StreamingASREvent(
                                type="final" if final else "partial",
                                text=text,
                                provider=self.provider,
                                final=final,
                            )
                        )
                    continue

                frame = parse_volc_frame(message)
                if frame.message_type not in {SERVER_FULL_RESPONSE, SERVER_ACK}:
                    continue
                text = _first_text(frame.payload)
                if not text:
                    continue
                final = _is_final_payload(frame.payload, frame.sequence)
                await self._queue.put(
                    StreamingASREvent(
                        type="final" if final else "partial",
                        text=text,
                        provider=self.provider,
                        final=final,
                    )
                )
        except asyncio.CancelledError:
            raise
        except SpeechProviderError as exc:
            await self._queue.put(StreamingASREvent(type="error", text=str(exc), provider=self.provider))
        except Exception as exc:
            await self._queue.put(
                StreamingASREvent(
                    type="error",
                    text=f"Volcengine streaming ASR read failed: {exc}",
                    provider=self.provider,
                )
            )

    async def send_audio(self, chunk: bytes) -> None:
        if self._closed or not chunk:
            return
        frame = build_audio_frame(chunk, self._sequence, final=False)
        self._sequence += 1
        await self.websocket.send(frame)

    async def finish(self) -> None:
        if self._closed:
            return
        frame = build_audio_frame(b"", self._sequence, final=True)
        self._sequence += 1
        await self.websocket.send(frame)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.reader_task:
            self.reader_task.cancel()
        try:
            await self.websocket.close()
        except Exception:
            pass

    async def receive_event(self, timeout: Optional[float] = None) -> Optional[StreamingASREvent]:
        if timeout is None:
            return await self._queue.get()
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


class VolcStreamingASRProvider:
    name = "volc_streaming_asr"
    model = "volc-bigmodel-streaming-asr"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _validate_config(self) -> None:
        missing = []
        if not self.settings.volc_asr_app_key:
            missing.append("VOLC_ASR_APP_KEY")
        if not self.settings.volc_asr_access_key:
            missing.append("VOLC_ASR_ACCESS_KEY")
        if not self.settings.volc_asr_resource_id:
            missing.append("VOLC_ASR_RESOURCE_ID")
        if missing:
            raise SpeechProviderError(
                f"{', '.join(missing)} required for Volcengine streaming ASR provider",
                self.name,
                self.model,
            )

    async def start_session(self, terminal_id: str, sample_rate: int = 16000) -> VolcStreamingASRSession:
        self._validate_config()
        try:
            import websockets
        except ImportError as exc:
            raise SpeechProviderError("websockets package is required for Volcengine streaming ASR", self.name, self.model) from exc

        connect_id = uuid.uuid4().hex
        headers = {
            "X-Api-App-Key": self.settings.volc_asr_app_key,
            "X-Api-Access-Key": self.settings.volc_asr_access_key,
            "X-Api-Resource-Id": self.settings.volc_asr_resource_id,
            "X-Api-Connect-Id": connect_id,
        }
        request_payload = {
            "user": {"uid": terminal_id},
            "audio": {
                "format": "pcm",
                "codec": "raw",
                "rate": int(sample_rate or 16000),
                "bits": 16,
                "channel": 1,
            },
            "request": {
                "model_name": "bigmodel",
                "enable_punc": True,
                "enable_itn": True,
            },
        }
        try:
            connect_kwargs = {
                "ping_interval": 20,
                "close_timeout": 5,
                "max_size": 8 * 1024 * 1024,
            }
            try:
                websocket = await websockets.connect(
                    self.settings.volc_asr_ws_url,
                    additional_headers=headers,
                    **connect_kwargs,
                )
            except TypeError:
                websocket = await websockets.connect(
                    self.settings.volc_asr_ws_url,
                    extra_headers=headers,
                    **connect_kwargs,
                )
            await websocket.send(build_full_request_frame(request_payload, sequence=1))
        except Exception as exc:
            raise SpeechProviderError(
                f"Volcengine streaming ASR connection failed: {exc}",
                self.name,
                self.model,
            ) from exc

        session = VolcStreamingASRSession(websocket, log_id=_extract_log_id(websocket))
        session.reader_task = asyncio.create_task(session._read_loop())
        return session
