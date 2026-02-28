import logging
from src.application.services.monitoring_manager import MonitoringManager
from src.application.events.event_bus import get_event_bus, SystemEvents

logger = logging.getLogger(__name__)

def register_socket_events(sio):
    monitor_manager = MonitoringManager.get_instance()
    # Inyectar el AsyncServer en el manager
    monitor_manager.init_socketio(sio)
    
    # Iniciar monitoreo global
    monitor_manager.start_dashboard_monitoring()

    event_bus = get_event_bus()

    # Bridge WhatsApp events to SocketIO
    async def on_whatsapp_event(data):
        await sio.emit('whatsapp_message', data)
        logger.debug(f"WhatsApp event broadcasted to sockets: {data.get('id')}")

    event_bus.subscribe(SystemEvents.WHATSAPP_MESSAGE_RECEIVED, lambda d: on_whatsapp_event(d))
    event_bus.subscribe(SystemEvents.WHATSAPP_MESSAGE_SENT, lambda d: on_whatsapp_event(d))

    # ---------------------------------------------------------
    # BRIDGE BUSINESS EVENTS TO SOCKETIO (REAL-TIME SYNC)
    # ---------------------------------------------------------
    async def on_business_event(data):
        """Generic handler for business events (CRUD)"""
        tenant_id = data.get('tenant_id')
        event_type = data.get('event_type')
        
        if tenant_id and event_type:
            room = f"tenant_{tenant_id}"
            await sio.emit('data_refresh', data, room=room)
            logger.debug(f"📢 Business event {event_type} broadcasted to room {room}")

    # Suscribirse a eventos de negocio comunes
    business_events = [
        SystemEvents.CLIENT_CREATED, SystemEvents.CLIENT_UPDATED, SystemEvents.CLIENT_DELETED,
        SystemEvents.CLIENT_SUSPENDED, SystemEvents.CLIENT_RESTORED,
        SystemEvents.PAYMENT_RECEIVED,
        SystemEvents.INCIDENT_REPORTED
    ]
    
    for event_name in business_events:
        event_bus.subscribe(event_name, lambda d: on_business_event(d))

    # --- Async Handlers for Socket.io ---

    @sio.on('connect')
    async def connect(sid, environ):
        monitor_manager.init_socketio(sio)
        logger.info(f"Client connected: {sid}")

    @sio.on('disconnect')
    async def disconnect(sid):
        logger.info(f"Client disconnected: {sid}")

    @sio.on('join_tenant')
    async def join_tenant(sid, data):
        tenant_id = data.get('tenant_id')
        if tenant_id:
            room = f"tenant_{tenant_id}"
            sio.enter_room(sid, room)
            logger.info(f"Client {sid} joined tenant room {room}")
            await sio.emit('joined_tenant', {'tenant_id': tenant_id, 'status': 'sync_active'}, room=sid)

    @sio.on('join_router')
    async def join_router(sid, data):
        router_id = data.get('router_id')
        if router_id:
            room = f"router_{router_id}"
            sio.enter_room(sid, room)
            logger.info(f"Client {sid} joined room {room}")
            
            # Asegurar que el hilo de monitoreo esté corriendo
            monitor_manager.start_router_monitoring(int(router_id))
            await sio.emit('joined_router', {'router_id': router_id, 'status': 'monitoring'}, room=sid)

    @sio.on('leave_router')
    async def leave_router(sid, data):
        router_id = data.get('router_id')
        if router_id:
            room = f"router_{router_id}"
            sio.leave_room(sid, room)
            logger.info(f"Client {sid} left room {room}")

    @sio.on('subscribe_interfaces')
    async def subscribe_interfaces(sid, data):
        router_id = data.get('router_id')
        interfaces = data.get('interfaces', [])
        if router_id:
            monitor_manager.start_router_monitoring(int(router_id))
            for iface in interfaces:
                monitor_manager.add_monitored_interface(int(router_id), iface)
            logger.info(f"Client {sid} subscribed to interfaces {interfaces} on router {router_id}")

    @sio.on('subscribe_clients')
    async def subscribe_clients(sid, data):
        router_id = data.get('router_id')
        client_ids = data.get('client_ids', [])
        if client_ids:
            monitor_manager.add_monitored_clients(router_id, client_ids)
            logger.info(f"Client {sid} subscribed to traffic of clients: {client_ids}")

    @sio.on('unsubscribe_clients')
    async def unsubscribe_clients(sid, data):
        client_ids = data.get('client_ids', [])
        if client_ids:
            monitor_manager.remove_monitored_clients(client_ids)
