"""
WebSocket Manager for Real-time Traffic Data Streaming
Handles WebSocket connections, message broadcasting, and real-time updates
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Any, Optional, Callable
from datetime import datetime, timedelta
from uuid import uuid4
import traceback

from fastapi import WebSocket, WebSocketDisconnect
from .config import get_settings
from .logging_config import websocket_logger

settings = get_settings()


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # subscription_type -> set of connection_ids
        self.message_queue: Dict[str, List[Dict[str, Any]]] = {}
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
    async def connect(self, websocket: WebSocket, connection_id: Optional[str] = None) -> str:
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        if not connection_id:
            connection_id = str(uuid4())
        
        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            'connected_at': datetime.utcnow(),
            'last_ping': datetime.utcnow(),
            'subscriptions': set(),
            'message_count': 0,
            'client_info': {}
        }
        self.message_queue[connection_id] = []
        
        websocket_logger.info(f"WebSocket connection established: {connection_id}")
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """Handle WebSocket disconnection"""
        if connection_id in self.active_connections:
            # Remove from all subscriptions
            for subscription_type in self.subscriptions:
                self.subscriptions[subscription_type].discard(connection_id)
            
            # Clean up connection data
            del self.active_connections[connection_id]
            del self.connection_metadata[connection_id]
            del self.message_queue[connection_id]
            
            websocket_logger.info(f"WebSocket connection closed: {connection_id}")
    
    async def subscribe(self, connection_id: str, subscription_type: str):
        """Subscribe connection to a specific data type"""
        if connection_id in self.active_connections:
            if subscription_type not in self.subscriptions:
                self.subscriptions[subscription_type] = set()
            
            self.subscriptions[subscription_type].add(connection_id)
            self.connection_metadata[connection_id]['subscriptions'].add(subscription_type)
            
            websocket_logger.info(f"Connection {connection_id} subscribed to {subscription_type}")
    
    async def unsubscribe(self, connection_id: str, subscription_type: str):
        """Unsubscribe connection from a specific data type"""
        if subscription_type in self.subscriptions:
            self.subscriptions[subscription_type].discard(connection_id)
        
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]['subscriptions'].discard(subscription_type)
            
        websocket_logger.info(f"Connection {connection_id} unsubscribed from {subscription_type}")
    
    async def send_personal_message(self, connection_id: str, message: Dict[str, Any]):
        """Send message to a specific connection"""
        if connection_id in self.active_connections:
            try:
                websocket = self.active_connections[connection_id]
                await websocket.send_text(json.dumps(message))
                
                self.connection_metadata[connection_id]['message_count'] += 1
                self.connection_metadata[connection_id]['last_ping'] = datetime.utcnow()
                
            except Exception as e:
                websocket_logger.error(f"Error sending message to {connection_id}: {str(e)}")
                await self.disconnect(connection_id)
    
    async def broadcast_to_subscription(self, subscription_type: str, message: Dict[str, Any]):
        """Broadcast message to all connections subscribed to a type"""
        if subscription_type not in self.subscriptions:
            return
        
        disconnected_connections = []
        
        for connection_id in self.subscriptions[subscription_type].copy():
            try:
                await self.send_personal_message(connection_id, message)
            except:
                disconnected_connections.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected_connections:
            await self.disconnect(connection_id)
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast message to all active connections"""
        disconnected_connections = []
        
        for connection_id in list(self.active_connections.keys()):
            try:
                await self.send_personal_message(connection_id, message)
            except:
                disconnected_connections.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected_connections:
            await self.disconnect(connection_id)
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)
    
    def get_subscription_stats(self) -> Dict[str, int]:
        """Get subscription statistics"""
        return {
            subscription_type: len(connections)
            for subscription_type, connections in self.subscriptions.items()
        }
    
    async def start_heartbeat(self):
        """Start heartbeat monitoring"""
        async def heartbeat_loop():
            while True:
                try:
                    await asyncio.sleep(settings.ws_heartbeat_interval)
                    
                    current_time = datetime.utcnow()
                    stale_connections = []
                    
                    for connection_id, metadata in self.connection_metadata.items():
                        last_ping = metadata['last_ping']
                        if (current_time - last_ping).total_seconds() > settings.ws_heartbeat_interval * 2:
                            stale_connections.append(connection_id)
                    
                    # Send ping to all connections
                    ping_message = {
                        'type': 'ping',
                        'timestamp': current_time.isoformat()
                    }
                    
                    await self.broadcast_to_all(ping_message)
                    
                    # Clean up stale connections
                    for connection_id in stale_connections:
                        websocket_logger.warning(f"Cleaning up stale connection: {connection_id}")
                        await self.disconnect(connection_id)
                        
                except Exception as e:
                    websocket_logger.error(f"Heartbeat error: {str(e)}")
        
        self.heartbeat_task = asyncio.create_task(heartbeat_loop())
    
    async def stop_heartbeat(self):
        """Stop heartbeat monitoring"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass


class TrafficDataBroadcaster:
    """Handles broadcasting of traffic data updates"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.last_broadcast: Dict[str, datetime] = {}
        
    async def broadcast_traffic_update(self, sensor_id: str, data: Dict[str, Any], timestamp: datetime):
        """Broadcast traffic data update"""
        message = {
            'type': 'traffic_update',
            'sensor_id': sensor_id,
            'data': data,
            'timestamp': timestamp.isoformat()
        }
        
        await self.connection_manager.broadcast_to_subscription('traffic_data', message)
        self.last_broadcast['traffic_data'] = timestamp
        
        websocket_logger.debug(f"Broadcasted traffic update for sensor {sensor_id}")
    
    async def broadcast_prediction_update(self, sensor_id: str, prediction: Dict[str, Any], timestamp: datetime):
        """Broadcast prediction update"""
        message = {
            'type': 'prediction_update',
            'sensor_id': sensor_id,
            'prediction': prediction,
            'timestamp': timestamp.isoformat()
        }
        
        await self.connection_manager.broadcast_to_subscription('predictions', message)
        self.last_broadcast['predictions'] = timestamp
        
        websocket_logger.debug(f"Broadcasted prediction update for sensor {sensor_id}")
    
    async def broadcast_alert(self, alert_id: str, alert: Dict[str, Any], timestamp: datetime):
        """Broadcast traffic alert"""
        message = {
            'type': 'alert',
            'alert_id': alert_id,
            'alert': alert,
            'timestamp': timestamp.isoformat()
        }
        
        await self.connection_manager.broadcast_to_subscription('alerts', message)
        self.last_broadcast['alerts'] = timestamp
        
        websocket_logger.debug(f"Broadcasted alert {alert_id}")
    
    async def broadcast_system_status(self, status: Dict[str, Any]):
        """Broadcast system status update"""
        message = {
            'type': 'system_status',
            'status': status,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await self.connection_manager.broadcast_to_all(message)


class WebSocketManager:
    """Main WebSocket management class"""
    
    def __init__(self):
        self.connection_manager = ConnectionManager()
        self.broadcaster = TrafficDataBroadcaster(self.connection_manager)
        self.initialized = False
        
    def initialize(self):
        """Initialize WebSocket manager"""
        if not self.initialized:
            asyncio.create_task(self.connection_manager.start_heartbeat())
            self.initialized = True
            websocket_logger.info("WebSocket manager initialized")
    
    async def handle_connection(self, websocket: WebSocket):
        """Handle new WebSocket connection"""
        connection_id = None
        try:
            connection_id = await self.connection_manager.connect(websocket)
            
            # Send welcome message
            welcome_message = {
                'type': 'welcome',
                'connection_id': connection_id,
                'timestamp': datetime.utcnow().isoformat(),
                'available_subscriptions': [
                    'traffic_data',
                    'predictions', 
                    'alerts',
                    'system_status'
                ]
            }
            
            await self.connection_manager.send_personal_message(connection_id, welcome_message)
            
            # Listen for client messages
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    await self._handle_client_message(connection_id, message)
                    
                except WebSocketDisconnect:
                    break
                except json.JSONDecodeError:
                    error_message = {
                        'type': 'error',
                        'message': 'Invalid JSON format',
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    await self.connection_manager.send_personal_message(connection_id, error_message)
                except Exception as e:
                    websocket_logger.error(f"Error handling WebSocket message: {str(e)}")
                    
        except WebSocketDisconnect:
            websocket_logger.info(f"WebSocket disconnected: {connection_id}")
        except Exception as e:
            websocket_logger.error(f"WebSocket connection error: {str(e)}")
        finally:
            if connection_id:
                await self.connection_manager.disconnect(connection_id)
    
    async def _handle_client_message(self, connection_id: str, message: Dict[str, Any]):
        """Handle message from client"""
        message_type = message.get('type')
        
        if message_type == 'subscribe':
            subscription_type = message.get('subscription')
            if subscription_type:
                await self.connection_manager.subscribe(connection_id, subscription_type)
                
                response = {
                    'type': 'subscription_confirmed',
                    'subscription': subscription_type,
                    'timestamp': datetime.utcnow().isoformat()
                }
                await self.connection_manager.send_personal_message(connection_id, response)
        
        elif message_type == 'unsubscribe':
            subscription_type = message.get('subscription')
            if subscription_type:
                await self.connection_manager.unsubscribe(connection_id, subscription_type)
                
                response = {
                    'type': 'unsubscription_confirmed',
                    'subscription': subscription_type,
                    'timestamp': datetime.utcnow().isoformat()
                }
                await self.connection_manager.send_personal_message(connection_id, response)
        
        elif message_type == 'pong':
            # Update last ping time
            if connection_id in self.connection_manager.connection_metadata:
                self.connection_manager.connection_metadata[connection_id]['last_ping'] = datetime.utcnow()
        
        elif message_type == 'get_status':
            status = self.get_health_status()
            response = {
                'type': 'status_response',
                'status': status,
                'timestamp': datetime.utcnow().isoformat()
            }
            await self.connection_manager.send_personal_message(connection_id, response)
        
        else:
            error_response = {
                'type': 'error',
                'message': f'Unknown message type: {message_type}',
                'timestamp': datetime.utcnow().isoformat()
            }
            await self.connection_manager.send_personal_message(connection_id, error_response)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get WebSocket health status"""
        return {
            'status': 'healthy' if self.initialized else 'not_initialized',
            'active_connections': self.connection_manager.get_connection_count(),
            'subscriptions': self.connection_manager.get_subscription_stats(),
            'last_broadcasts': self.broadcaster.last_broadcast
        }
    
    async def setup_kafka_integration(self, traffic_streamer, prediction_streamer, alert_streamer):
        """Setup integration with Kafka streamers (simplified stub version)"""
        # For now, just store references - actual integration would set up callbacks
        self.traffic_streamer = traffic_streamer
        self.prediction_streamer = prediction_streamer
        self.alert_streamer = alert_streamer
        
        websocket_logger.info("Kafka integration setup completed (stub version)")
    
    async def close(self):
        """Close WebSocket manager"""
        await self.connection_manager.stop_heartbeat()
        
        # Disconnect all connections
        for connection_id in list(self.connection_manager.active_connections.keys()):
            await self.connection_manager.disconnect(connection_id)
        
        websocket_logger.info("WebSocket manager closed")


# Global WebSocket manager instance
websocket_manager = WebSocketManager()