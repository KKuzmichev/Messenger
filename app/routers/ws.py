import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.dependencies import get_current_user_id
from app.services.auth import decode_token
from app.services.ws_manager import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id or payload.get("type") != "access":
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(user_id, ws)

    await manager.send_to_user(user_id, {"type": "presence", "user_id": user_id, "status": "online"})

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "typing":
                conv_id = msg.get("conversation_id")
                if conv_id:
                    await manager.broadcast_to_conversation(
                        [user_id],
                        {"type": "typing", "user_id": user_id, "conversation_id": conv_id},
                        exclude=user_id,
                    )
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        manager.disconnect(user_id, ws)
        await manager.send_to_user(user_id, {"type": "presence", "user_id": user_id, "status": "offline"})
