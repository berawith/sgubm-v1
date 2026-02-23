import logging
from flask import request
from flask_socketio import emit, join_room, leave_room
from src.application.services.monitoring_manager import MonitoringManager

logger = logging.getLogger(__name__)

def register_socket_events(socketio):
    monitor_manager = MonitoringManager.get_instance()
    monitor_manager.init_socketio(socketio)
    
    # Iniciar monitoreo del dashboard (global)
    monitor_manager.start_dashboard_monitoring()

    # Bridge WhatsApp events to SocketIO
    from src.application.events.event_bus import get_event_bus, SystemEvents
    event_bus = get_event_bus()

    def on_whatsapp_event(data):
        socketio.emit('whatsapp_message', data)
        logger.debug(f"WhatsApp event broadcasted to sockets: {data.get('id')}")

    event_bus.subscribe(SystemEvents.WHATSAPP_MESSAGE_RECEIVED, on_whatsapp_event)
    event_bus.subscribe(SystemEvents.WHATSAPP_MESSAGE_SENT, on_whatsapp_event)

    @socketio.on('connect')
    def on_connect():
        logger.info(f"Client connected: {request.sid}")

    @socketio.on('disconnect')
    def on_disconnect():
        logger.info(f"Client disconnected: {request.sid}")

    @socketio.on('join_router')
    def handle_join_router(data):
        router_id = data.get('router_id')
        if router_id:
            room = f"router_{router_id}"
            join_room(room)
            logger.info(f"Client {request.sid} joined room {room}")
            
            # Asegurar que el hilo de monitoreo esté corriendo para este router
            monitor_manager.start_router_monitoring(int(router_id))
            
            emit('joined_router', {'router_id': router_id, 'status': 'monitoring'})

    @socketio.on('leave_router')
    def handle_leave_router(data):
        router_id = data.get('router_id')
        if router_id:
            room = f"router_{router_id}"
            leave_room(room)
            logger.info(f"Client {request.sid} left room {room}")
            # we don't stop the thread immediately here as other clients might be watching
            # The MonitoringManager could implement a reference count if needed.

    @socketio.on('subscribe_interfaces')
    def handle_subscribe_interfaces(data):
        router_id = data.get('router_id')
        interfaces = data.get('interfaces', [])
        
        if not router_id:
            return

        # Ensure monitor is running
        monitor_manager.start_router_monitoring(int(router_id))
        
        # Add interfaces to monitor
        for iface in interfaces:
            monitor_manager.add_monitored_interface(int(router_id), iface)
            
        logger.info(f"Client {request.sid} subscribed to interfaces {interfaces} on router {router_id}")

    @socketio.on('unsubscribe_interfaces')
    def handle_unsubscribe_interfaces(data):
        router_id = data.get('router_id')
        interfaces = data.get('interfaces', [])
        
        if not router_id:
            return
            
        for iface in interfaces:
            monitor_manager.remove_monitored_interface(int(router_id), iface)

    @socketio.on('subscribe_clients')
    def handle_subscribe_clients(data):
        router_id = data.get('router_id')
        client_ids = data.get('client_ids', [])
        if not client_ids:
            return
            
        monitor_manager.add_monitored_clients(router_id, client_ids)
        logger.info(f"Client {request.sid} subscribed to traffic of clients: {client_ids}")

    @socketio.on('unsubscribe_clients')
    def handle_unsubscribe_clients(data):
        client_ids = data.get('client_ids', [])
        if client_ids:
            monitor_manager.remove_monitored_clients(client_ids)
