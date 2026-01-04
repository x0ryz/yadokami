import asyncio
import json

from fastapi import WebSocket
from loguru import logger
from src.core.config import settings
from src.core.redis import get_redis


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"WebSocket client connected. Total: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket client disconnected")

    async def broadcast(self, message: dict):
        data = json.dumps(message, default=str)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(data)
            except Exception as e:
                logger.error(f"Error sending to WS: {e}")
                self.disconnect(connection)


manager = ConnectionManager()


async def redis_listener():
    """Listen to the Redis channel and sends messages via WebSocket Manager"""
    logger.info("Starting Redis Listener...")

    while True:
        pubsub = None
        try:
            redis = get_redis()
            pubsub = redis.pubsub()
            await pubsub.subscribe("ws_updates")

            logger.info("Redis Pub/Sub connected.")

            async for message in pubsub.listen():
                if message["type"] == "message":
                    raw_data = message["data"]

                    try:
                        payload = json.loads(raw_data)

                        event_name = (
                            payload.get("event") or payload.get("type") or "unknown"
                        )

                        logger.info(f"WS sending: {event_name}")
                        await manager.broadcast(payload)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to decode Redis message: {raw_data}")
                    except Exception as e:
                        logger.error(f"Error broadcasting message: {e}")

        except asyncio.CancelledError:
            logger.info("Redis listener cancelled.")
            break
        except Exception as e:
            logger.error(f"Redis connection lost: {e}. Reconnecting...")
            await asyncio.sleep(5)
        finally:
            if pubsub:
                await pubsub.close()
