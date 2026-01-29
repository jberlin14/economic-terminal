"""
WebSocket Handler for Real-Time Updates

Provides real-time data push to connected clients.
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Set
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from modules.utils.timezone import get_current_time


class ConnectionManager:
    """
    Manages WebSocket connections and broadcasting.
    """
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def send_personal(self, message: dict, websocket: WebSocket):
        """Send message to a specific client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending to WebSocket: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        if not self.active_connections:
            return
        
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


# Global connection manager
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint handler.
    
    Clients can subscribe to different data channels:
    - 'all': All updates
    - 'fx': FX rate updates only
    - 'yields': Yield curve updates only
    - 'alerts': Risk alerts only
    """
    await manager.connect(websocket)
    
    # Send welcome message
    await manager.send_personal({
        'type': 'connected',
        'timestamp': get_current_time().isoformat(),
        'message': 'Connected to Economic Terminal'
    }, websocket)
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                await handle_client_message(websocket, message)
            except json.JSONDecodeError:
                await manager.send_personal({
                    'type': 'error',
                    'message': 'Invalid JSON'
                }, websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def handle_client_message(websocket: WebSocket, message: dict):
    """Handle incoming client messages."""
    msg_type = message.get('type', '')
    
    if msg_type == 'ping':
        await manager.send_personal({
            'type': 'pong',
            'timestamp': get_current_time().isoformat()
        }, websocket)
    
    elif msg_type == 'subscribe':
        channel = message.get('channel', 'all')
        await manager.send_personal({
            'type': 'subscribed',
            'channel': channel,
            'timestamp': get_current_time().isoformat()
        }, websocket)
    
    elif msg_type == 'get_status':
        await manager.send_personal({
            'type': 'status',
            'connections': manager.connection_count,
            'timestamp': get_current_time().isoformat()
        }, websocket)


async def broadcast_fx_update(fx_data: Dict[str, Any]):
    """Broadcast FX rate update to all clients."""
    await manager.broadcast({
        'type': 'fx_update',
        'data': fx_data,
        'timestamp': get_current_time().isoformat()
    })


async def broadcast_yield_update(yield_data: Dict[str, Any]):
    """Broadcast yield curve update to all clients."""
    await manager.broadcast({
        'type': 'yield_update',
        'data': yield_data,
        'timestamp': get_current_time().isoformat()
    })


async def broadcast_alert(alert_data: Dict[str, Any]):
    """Broadcast risk alert to all clients."""
    await manager.broadcast({
        'type': 'alert',
        'severity': alert_data.get('severity', 'HIGH'),
        'data': alert_data,
        'timestamp': get_current_time().isoformat()
    })


async def broadcast_news(news_data: Dict[str, Any]):
    """Broadcast news update to all clients."""
    await manager.broadcast({
        'type': 'news',
        'data': news_data,
        'timestamp': get_current_time().isoformat()
    })
