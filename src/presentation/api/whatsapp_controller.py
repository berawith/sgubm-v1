"""
WhatsApp API Controller
Webhook receiver for WhatsApp messages.
"""
from flask import Blueprint, request, jsonify
from src.infrastructure.database.db_manager import get_db
from src.application.services.whatsapp_agent_service import WhatsAppAgentService
from src.infrastructure.notifications.whatsapp_adapter import WhatsAppAdapter
import logging
from datetime import datetime

whatsapp_bp = Blueprint('whatsapp', __name__, url_prefix='/api/whatsapp')

# Setup logger
logger = logging.getLogger(__name__)

@whatsapp_bp.route('/webhook', methods=['POST'])
def webhook():
    """
    Receives events from the WhatsApp bridge.
    """
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No data received"}), 400

    logger.debug(f"Received WhatsApp webhook: {data}")

    try:
        db_manager = get_db()
        agent_service = WhatsAppAgentService(db_manager)
        settings_repo = db_manager.get_system_setting_repository()
        
        # Check if auto-reply is enabled
        is_auto = settings_repo.get_value('whatsapp_auto_reply')
        is_auto_enabled = str(is_auto).lower() != 'false' if is_auto is not None else True

        message_data = data.get('data', {})
        if not message_data:
            message_data = data
            
        # Detectamos el JID completo para identificar grupos (@g.us)
        raw_jid = message_data.get('key', {}).get('remoteJid', '') or data.get('sender', '')
        is_group = '@g.us' in raw_jid
        
        phone = raw_jid.split('@')[0]
        text = message_data.get('message', {}).get('conversation', '')
        if not text:
            text = message_data.get('text', '')

        if phone and text:
            # REGLAS DE ORO PARA EL HISTORIAL:
            # Solo guardamos si es un chat individual comprobable (evitamos ruidos de grupos o técnicos)
            if is_group or '@s.whatsapp.net' not in raw_jid:
                logger.info(f"Historial Omitido: Chat no individual ({raw_jid})")
                return jsonify({"success": True, "message": "Evento ignorado (No es chat individual)"}), 200

            # Siempre procesamos para guardar en el historial (solo individuales ahora)
            response = agent_service.process_incoming_message(phone, text)
            
            # REGLAS PARA RESPUESTA AUTOMÁTICA
            if not is_auto_enabled:
                return jsonify({
                    "success": True, 
                    "message": "Mensaje guardado. Modo manual activo.",
                    "manual": True
                })

            return jsonify({
                "success": True, 
                "response": {
                    "to": phone,
                    "message": response
                }
            })

        return jsonify({"success": True, "message": "Event processed, no action taken"}), 200

    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@whatsapp_bp.route('/history/<phone>', methods=['GET'])
def get_history(phone):
    """Obtiene el historial de mensajes de un número específico"""
    try:
        db = get_db()
        whatsapp_repo = db.get_whatsapp_repository()
        history = whatsapp_repo.get_history_by_phone(phone)
        return jsonify([m.to_dict() for m in history])
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@whatsapp_bp.route('/config', methods=['GET'])
def get_config():
    """Obtiene la configuración actual del agente"""
    try:
        db = get_db()
        settings_repo = db.get_system_setting_repository()
        
        import os
        gemini_key = settings_repo.get_value('whatsapp_gemini_key') or os.getenv('GEMINI_API_KEY', '')
        agent_name = settings_repo.get_value('whatsapp_agent_name') or "Secretaria Virtual Premium"
        agent_phone = settings_repo.get_value('whatsapp_agent_phone') or "Desconocido"
        auto_reply = settings_repo.get_value('whatsapp_auto_reply') == 'true'
        pairing_phone = settings_repo.get_value('whatsapp_pairing_phone')
        
        webhook_url = f"{request.url_root}api/whatsapp/webhook"
        
        return jsonify({
            "gemini_key": gemini_key,
            "agent_name": agent_name,
            "agent_phone": agent_phone,
            "pairing_phone": pairing_phone,
            "pairing_code": _whatsapp_status.get('pairing_code'),
            "auto_reply": auto_reply,
            "webhook_url": webhook_url
        })
    except Exception as e:
        logger.error(f"Error fetching WhatsApp config: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@whatsapp_bp.route('/config', methods=['POST'])
def save_config():
    """Guarda la configuración del agente en la base de datos"""
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
            
        db = get_db()
        settings_repo = db.get_system_setting_repository()
        
        if 'gemini_key' in data:
            settings_repo.set_value('whatsapp_gemini_key', data['gemini_key'], category='whatsapp', description='Gemini API Key')
            import os
            os.environ['GEMINI_API_KEY'] = data['gemini_key']
            
        if 'agent_name' in data:
            settings_repo.set_value('whatsapp_agent_name', data['agent_name'], category='whatsapp')
            
        if 'agent_phone' in data:
            settings_repo.set_value('whatsapp_agent_phone', data['agent_phone'], category='whatsapp')

        if 'auto_reply' in data:
            settings_repo.set_value('whatsapp_auto_reply', 'true' if data['auto_reply'] else 'false', category='whatsapp')

        return jsonify({"success": True, "message": "Configuración actualizada"})
        
    except Exception as e:
        logger.error(f"Error saving WhatsApp config: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# Almacén efímero para el QR y estado (en producción podría ir a Redis o DB)
_whatsapp_status = {
    "connected": False,
    "qr": None,
    "last_update": None
}

@whatsapp_bp.route('/status', methods=['GET'])
def get_status():
    """Retorna el estado actual de la conexión y el QR si existe"""
    return jsonify(_whatsapp_status)

@whatsapp_bp.route('/status', methods=['POST'])
def update_status():
    """Actualiza el estado desde el Bridge"""
    data = request.json
    _whatsapp_status["connected"] = data.get("connected", False)
    _whatsapp_status["qr"] = data.get("qr")
    _whatsapp_status["pairing_code"] = data.get("pairing_code")
    _whatsapp_status["last_update"] = datetime.now().isoformat()
    return jsonify({"success": True})

# Almacén volátil para chats del teléfono (no clientes necesariamente)
_external_chats = []

@whatsapp_bp.route('/sync-chats', methods=['POST'])
def sync_chats():
    """Recibe la lista completa de chats desde el Bridge"""
    global _external_chats
    data = request.json
    _external_chats = data.get('chats', [])
    logger.info(f"Sincronizados {_external_chats.__len__()} chats externos")
    return jsonify({"success": True})

@whatsapp_bp.route('/conversations', methods=['GET'])
def get_conversations():
    """Retorna hilos de conversación de la DB mezclados con chats externos"""
    try:
        db = get_db()
        # 1. Obtener hilos de la DB
        from src.infrastructure.database.repositories import WhatsAppRepository
        repo = WhatsAppRepository(db.session)
        db_conversations = repo.get_latest_conversations()
        
        # Formatear conversaciones de DB
        results = []
        for msg in db_conversations:
            try:
                results.append(msg.to_dict())
            except Exception as e:
                logger.error(f"Error serializing message {msg.id}: {str(e)}")
        
        # 2. Mezclar con chats externos
        existing_phones = {c['phone'] for c in results if 'phone' in c}
        
        for ext in _external_chats:
            try:
                if not ext.get('id'): continue
                
                phone = ext['id'].split('@')[0]
                # Solo añadir si no es un grupo y no está ya en los resultados
                if '@s.whatsapp.net' in ext['id'] and phone not in existing_phones:
                    ts_val = ext.get('lastMessageTimestamp', 0)
                    if ts_val:
                        try:
                            # Handle potential millisecond vs second difference
                            if ts_val > 10**12: # Milliseconds
                                ts_val = ts_val / 1000
                            ts_iso = datetime.fromtimestamp(ts_val).isoformat()
                        except Exception:
                            ts_iso = datetime.now().isoformat()
                    else:
                        ts_iso = datetime.now().isoformat()
                        
                    results.append({
                        'id': None,
                        'phone': phone,
                        'client_name': ext.get('name') or phone,
                        'message_text': '[Chat del teléfono]',
                        'is_outgoing': False,
                        'timestamp': ts_iso,
                        'is_external': True
                    })
            except Exception as e:
                logger.error(f"Error processing external chat {ext.get('id')}: {str(e)}")
        
        # Ordenar por timestamp descendente
        results.sort(key=lambda x: x.get('timestamp') or "", reverse=True)
        
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error fetching aggregated conversations: {str(e)}")
        return jsonify({"error": str(e)}), 500

@whatsapp_bp.route('/send', methods=['POST'])
def send_message():
    """Envía un mensaje manual a un número específico"""
    try:
        data = request.json
        phone = data.get('phone')
        message = data.get('message')
        
        if not phone or not message:
            return jsonify({"success": False, "error": "Teléfono y mensaje requeridos"}), 400
            
        # Limpiar número
        clean_phone = "".join(filter(str.isdigit, phone))
        
        db = get_db()
        agent_service = WhatsAppAgentService(db)
        settings_repo = db.get_system_setting_repository()
        
        # Enviamos a través del adaptador
        # El adaptador ahora usa localhost:5001 por defecto
        adapter = WhatsAppAdapter(
            bridge_url="", # No se usa en la implementación local actual pero mantenemos firma
            api_key=settings_repo.get_value('whatsapp_gemini_key', '')
        )
        success = adapter.send_whatsapp(clean_phone, message)
        
        if success:
            # Registrar en el historial como mensaje saliente
            # Buscamos el cliente para el log si existe
            client = agent_service._find_client_by_phone(clean_phone)
            client_id = client.id if client else None
            
            agent_service._log_outgoing(clean_phone, message, client_id, "manual_outbound")
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "No se pudo enviar el mensaje (¿Bridge desconectado?)"}), 503
            
    except Exception as e:
        logger.error(f"Error sending manual WhatsApp: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@whatsapp_bp.route('/pair', methods=['POST'])
def request_pairing():
    """Registra una solicitud de vinculación por código"""
    try:
        data = request.json
        phone = data.get('phone')
        if not phone:
            return jsonify({"success": False, "error": "Número de teléfono requerido"}), 400
            
        # Limpiar número
        clean_phone = "".join(filter(str.isdigit, phone))
        
        db = get_db()
        settings_repo = db.get_system_setting_repository()
        settings_repo.set_value('whatsapp_pairing_phone', clean_phone, category='whatsapp')
        
        return jsonify({"success": True, "message": "Solicitud de vinculación enviada al Bridge"})
    except Exception as e:
        logger.error(f"Error requesting pairing: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
