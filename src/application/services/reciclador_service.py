import traceback
import json
import logging
import os
import sys
from datetime import datetime
from flask import request, g, has_request_context

from src.infrastructure.database.db_manager import get_db, get_app
from src.infrastructure.database.models import SystemIncident
from src.application.events.event_bus import get_event_bus, SystemEvents

logger = logging.getLogger(__name__)

class RecicladorService:
    """
    Servicio Centinela (RECICLADOR) para captura proactiva de errores.
    """
    
    @staticmethod
    def capture(exception, category='system', severity='error', context=None):
        """
        Captura una excepción con todo el contexto posible y la guarda en la BD.
        """
        try:

            # 1. Extraer detalles básicos
            error_type = type(exception).__name__
            message = str(exception)
            stack = traceback.format_exc()
            
            # 2. Obtener contexto de request si existe
            url = None
            method = None
            params = None
            payload = None
            ip = None
            user_id = None
            username = None
            tenant_id = None
            
            if has_request_context():
                url = request.url
                method = request.method
                params = json.dumps(request.args.to_dict()) if request.args else None
                
                # Intentar obtener payload (ofuscando contraseñas)
                try:
                    if request.is_json:
                        data = request.get_json(silent=True) or {}
                        # Ofuscación simple
                        safe_data = {k: ('********' if 'password' in k.lower() or 'token' in k.lower() else v) 
                                   for k, v in data.items()}
                        payload = json.dumps(safe_data)
                except:
                    payload = "[Error retrieving payload]"
                
                ip = request.remote_addr
                user_id = getattr(g, 'user_id', None)
                username = getattr(g, 'user', None).username if hasattr(getattr(g, 'user', None), 'username') else None
                tenant_id = getattr(g, 'tenant_id', None)
            
            # 2.5 Priorizar context para tenant_id (útil en hilos de fondo)
            if context and 'tenant_id' in context:
                tenant_id = context['tenant_id']
            elif context and 'router_id' in context:
                # Fallback: intentar inferir tenant desde el router si estamos en monitoreo
                try:
                    from src.infrastructure.database.db_manager import get_db
                    from src.infrastructure.database.models import Router
                    router = get_db().session.query(Router).get(context['router_id'])
                    if router:
                        tenant_id = router.tenant_id
                except: pass
            
            # 3. Metadata del entorno
            env_meta = json.dumps({
                'os': sys.platform,
                'python_version': sys.version,
                'pid': os.getpid(),
                'timestamp': datetime.now().isoformat()
            })
            
            # 3.8 Generar Análisis de IA (Deducción Inteligente)
            ai_info = RecicladorService._generate_ai_analysis(error_type, message, RecicladorService._get_calling_module())
            
            # 4. Guardar en Base de Datos
            db = get_db()
            incident = SystemIncident(
                tenant_id=tenant_id,
                severity=severity,
                category=category,
                module=RecicladorService._get_calling_module(),
                error_type=error_type,
                message=message,
                stack_trace=stack,
                url=url,
                method=method,
                request_params=params,
                request_payload=payload,
                user_id=user_id,
                username=username,
                ip_address=ip,
                environment_meta=env_meta,
                ai_analysis=json.dumps(ai_info),
                status='new'
            )
            
            db.session.add(incident)
            db.session.commit()
            
            # 5. Notificar en tiempo real (PROACTIVIDAD)
            RecicladorService._broadcast(incident)
            
            logger.error(f"🚨 RECICLADOR: Incidente capturado [{error_type}]: {message}")
            return incident
            
        except Exception as e:
            # Fail silently to avoid recursion or blocking the app
            logger.error(f"❌ Error crítico en el RECICLADOR: {e}")
            return None

    @staticmethod
    def _generate_ai_analysis(error_type, message, module):
        """
        Simula un motor de IA que analiza el error y sugiere reparaciones.
        En una fase avanzada, esto podría llamar a una LLM real.
        """
        analysis = {
            'diagnosis': "Error desconocido. Requiere inspección manual del stack trace.",
            'solution_steps': ["Revisar logs del servidor", "Verificar integridad de la base de datos"],
            'risk_level': 'medium'
        }
        
        msg_lower = message.lower()
        
        # Patrones comunes de MikroTik
        if '10038' in msg_lower or 'socket' in msg_lower:
            analysis['diagnosis'] = "Corrupción de socket detectada. Probable colisión de hilos en Windows."
            analysis['solution_steps'] = [
                "El sistema ya activó el auto-reconnect", 
                "Verificar si hay múltiples procesos accediendo al mismo router",
                "Asegurar que MikroTikAdapter no sea compartido entre hilos"
            ]
            analysis['risk_level'] = 'high'
            
        elif 'connection refused' in msg_lower or '10061' in msg_lower:
            analysis['diagnosis'] = "El router MikroTik rechazó la conexión. API deshabilitada o puerto incorrecto."
            analysis['solution_steps'] = [
                "Verificar IP y Puerto del router",
                "Asegurar que /ip service set api disabled=no",
                "Comprobar Firewall en el router (/ip firewall filter)"
            ]
            analysis['risk_level'] = 'high'
            
        # Patrones de Base de Datos
        elif 'operationalerror' in error_type.lower() and 'locked' in msg_lower:
            analysis['diagnosis'] = "Base de datos SQLite bloqueada por proceso largo."
            analysis['solution_steps'] = [
                "Reducir el tiempo de las transacciones",
                "Aumentar el bus_timeout en la conexión SQLite",
                "Verificar si hay backups corriendo en paralelo"
            ]
            analysis['risk_level'] = 'medium'
            
        # Patrones de Jinja2 / Templates
        elif 'templatenotfound' in error_type.lower() or 'jinja2' in module.lower():
            analysis['diagnosis'] = "Error de renderizado de interfaz. Archivo HTML faltante o sintaxis corrupta."
            analysis['solution_steps'] = [
                "Verificar ruta en src/presentation/web/templates",
                "Revisar etiquetas {{ }} o {% %} mal cerradas",
                "Limpiar caché de Jinja2"
            ]
            analysis['risk_level'] = 'low'
            
        # Patrones de Auth / RBAC
        elif 'permission' in msg_lower or 'authorized' in msg_lower:
            analysis['diagnosis'] = "Intento de acceso denegado o fallo en la lógica de permisos."
            analysis['solution_steps'] = [
                "Verificar permisos del rol en la matriz",
                "Asegurar que el token de sesión no haya expirado",
                "Revisar decorador @permission_required en el controller"
            ]
            analysis['risk_level'] = 'medium'

        return analysis

    @staticmethod
    def _get_calling_module():
        """Intenta identificar el módulo que falló mediante el stack"""
        try:
            # El frame -3 suele ser el origen del error antes de entrar al servicio
            stack = traceback.extract_stack()
            if len(stack) > 3:
                return f"{os.path.basename(stack[-3].filename)}:{stack[-3].lineno}"
        except:
            pass
        return "unknown"

    @staticmethod
    def _broadcast(incident):
        """Envía el incidente al EventBus para que sea replicado vía WebSockets"""
        try:
            from src.application.events.event_bus import get_event_bus, SystemEvents
            # Envolver en una estructura que el frontend espera
            payload = {
                'event_type': SystemEvents.INCIDENT_REPORTED,
                'incident': incident.to_dict()
            }
            get_event_bus().publish(SystemEvents.INCIDENT_REPORTED, payload, source='reciclador')
            logger.info(f"📡 Centinela: Incidente publicado en el EventBus")
        except Exception as e:
            logger.error(f"⚠️ Centinela: Error publicando incidente en EventBus: {e}")
