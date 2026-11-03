"""Live call endpoints: real-time emergency reporting over WebSocket."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.live_call import LiveCall, ACTIVE, active_summaries, MAX_CONCURRENT_CALLS

router = APIRouter(prefix="/api/live", tags=["live"])
log = logging.getLogger("aapda.live")


@router.get("/calls")
def live_calls():
    """Active live calls for the Situation Room's LiveCallsPanel."""
    return {"items": active_summaries()}


@router.websocket("/call")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time voice turn loop powered by Sarvam AI."""
    await websocket.accept()

    if len(ACTIVE) >= MAX_CONCURRENT_CALLS:
        await websocket.send_json({
            "type": "error",
            "message": "All live call channels are busy. Please try again in a moment.",
        })
        await websocket.close(code=1008)
        return

    call_id = uuid.uuid4().hex[:8]
    call = LiveCall(
        send_json=websocket.send_json,
        send_bytes=websocket.send_bytes,
        call_id=call_id,
    )
    ACTIVE[call_id] = call

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                except ValueError:
                    continue

                msg_type = data.get("type")
                if msg_type == "start":
                    lang = data.get("language")
                    asyncio.create_task(call.start(lang))
                elif msg_type == "commit":
                    pcm = call.buffer.take()
                    if pcm:
                        asyncio.create_task(call.handle_turn(pcm))
                elif msg_type == "end":
                    await call.finish()
                    break
                elif msg_type == "playback_done":
                    call.speaking.set()
                    await call.listen()

            elif "bytes" in message and message["bytes"]:
                raw = message["bytes"]
                if call.speaking.is_set():
                    turn_ready = call.buffer.add(raw)
                    if turn_ready:
                        pcm = call.buffer.take()
                        asyncio.create_task(call.handle_turn(pcm))

    except (WebSocketDisconnect, asyncio.CancelledError, RuntimeError):
        pass
    except Exception as exc:
        log.warning("Live call %s error: %s", call_id, exc)
    finally:
        ACTIVE.pop(call_id, None)
        if not call.finished:
            try:
                await call.finish()
            except Exception:
                pass
