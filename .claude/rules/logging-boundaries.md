# Logging at API and WebSocket Boundaries

## Globs
<!-- - server/api/**/*.py
- server/routers/**/*.py
- server/websocket/**/*.py
- server/**/ws*.py -->
- server/**/*.py

## Rule

在 API 入口和 WebSocket 通信处必须记录结构化日志，便于链路追踪和问题排查。

### API 入口

每个 route handler 必须记录：

- 请求进入：method、path、request_id、调用方 IP（脱敏）
- 请求结束：status_code、耗时
- 异常：exception type、message、stack trace

```python
# 标准写法
import logging
import time

logger = logging.getLogger(__name__)

@router.post("/your-endpoint")
async def handler(request: YourRequest):
    start = time.time()
    logger.info("request.start", extra={
        "path": "/your-endpoint",
        "method": "POST",
        "request_id": request.state.request_id,
    })
    try:
        result = await do_something(request)
        logger.info("request.end", extra={
            "status": 200,
            "duration_ms": int((time.time() - start) * 1000),
        })
        return result
    except Exception as e:
        logger.exception("request.error", extra={
            "error": str(e),
            "duration_ms": int((time.time() - start) * 1000),
        })
        raise
```

### WebSocket

每个 WebSocket handler 必须记录：

- 连接建立：client_id、连接时间
- 消息收发：message type、payload 大小（不记录原始内容）
- 连接关闭：原因、持续时长
- 异常断开：error type

```python
# 标准写法
@router.websocket("/ws/{client_id}")
async def websocket_handler(websocket: WebSocket, client_id: str):
    await websocket.accept()
    connected_at = time.time()
    logger.info("ws.connected", extra={"client_id": client_id})
    try:
        while True:
            data = await websocket.receive_text()
            logger.info("ws.message.received", extra={
                "client_id": client_id,
                "size_bytes": len(data),
            })
    except WebSocketDisconnect as e:
        logger.info("ws.disconnected", extra={
            "client_id": client_id,
            "duration_s": int(time.time() - connected_at),
            "code": e.code,
        })
    except Exception as e:
        logger.exception("ws.error", extra={
            "client_id": client_id,
            "error": str(e),
        })
```

### 禁止

- 不能在日志里记录密码、token、完整的请求 body
- 不能用 print 替代 logger
- 不能只在异常时记录，正常链路也必须有日志