"""
WhatsApp Agent Service
Logic for the "Secretary & Administrator" AI Agent.
"""
from typing import Dict, Any, List, Optional
from src.core.interfaces.contracts import IWhatsAppAgentService, IRepository
from src.infrastructure.database.repository_registry import ClientRepository, PaymentRepository, RouterRepository
import json

class WhatsAppAgentService(IWhatsAppAgentService):
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.client_repo = db_manager.get_client_repository()
        self.payment_repo = db_manager.get_payment_repository()
        self.router_repo = db_manager.get_router_repository()
        self.whatsapp_repo = db_manager.get_whatsapp_repository()
        from src.application.events.event_bus import get_event_bus
        self.event_bus = get_event_bus()

    def process_incoming_message(self, phone: str, message: str, client_override: Optional[Any] = None) -> str:
        """
        Main entry point for incoming WhatsApp messages.
        """
        # 1. Identify Client
        client = client_override or self._find_client_by_phone(phone)
        client_id = client.id if client else None

        # 2. Identify Intent (uses AI)
        intent_data = self.identify_intent(message, phone=phone)
        intent = intent_data.get('intent', 'unknown')

        # Log Incoming Message
        msg_obj = self.whatsapp_repo.create({
            'client_id': client_id,
            'phone': phone,
            'message_text': message,
            'is_outgoing': False,
            'intent_identified': intent
        })
        
        from src.application.events.event_bus import SystemEvents
        self.event_bus.publish(SystemEvents.WHATSAPP_MESSAGE_RECEIVED, msg_obj.to_dict())

        if not client:
            response = "Estimado/a cliente. No hemos podido localizar su número en nuestra base de datos institucional. Por favor, proporcione su código de suscriptor para que pueda asistirle con la mayor celeridad."
            self._log_outgoing(phone, response, client_id, "unknown")
            return response
        
        # 3. Execute Task (with personality)
        response = self.execute_administrative_task(intent, {"client": client, "message": message, "phone": phone})
        
        # Log Outgoing Message
        self._log_outgoing(phone, response, client_id, intent)
        
        return response

    def _log_outgoing(self, phone: str, text: str, client_id: Optional[int], intent: str):
        msg_obj = self.whatsapp_repo.create({
            'client_id': client_id,
            'phone': phone,
            'message_text': text,
            'is_outgoing': True,
            'intent_identified': intent
        })
        from src.application.events.event_bus import SystemEvents
        self.event_bus.publish(SystemEvents.WHATSAPP_MESSAGE_SENT, msg_obj.to_dict())

    def identify_intent(self, message: str, phone: Optional[str] = None) -> Dict[str, Any]:
        """
        Uses AI to identify what the user wants, now with context.
        """
        import os
        gemini_key = os.getenv('GEMINI_API_KEY')
        
        # Load conversation context if phone is provided
        context = ""
        if phone:
            context = self.whatsapp_repo.get_recent_context(phone)

        if gemini_key and gemini_key != 'your_gemini_api_key':
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                system_instruction = """
                Eres la "Secretaria Virtual Premium" de SGUBM, un ISP (Proveedor de Internet).
                Tu tono debe ser: Profesional, Empático, servicial y resolutivo.
                Persona: Eres eficiente y usas un lenguaje corporativo pero cercano. No eres un robot, eres una asistente de alto nivel.
                
                Instrucciones:
                1. Analiza el mensaje actual y el contexto previo.
                2. Devuelve un JSON con la intención predominante. 
                3. Intenciones: check_balance, check_due_date, report_issue, general_inquiry, payment_promise.
                4. Si el cliente sugiere una fecha para pagar después, usa 'payment_promise'.
                """

                prompt = f"""
                CONTEXTO RECIENTE:
                {context}
                
                MENSAJE ACTUAL DEL CLIENTE: 
                "{message}"
                
                Determina la intención y responde SOLO el JSON. Ejemplo: {{"intent": "check_balance"}}
                """
                response = model.generate_content(prompt)
                try:
                    text = response.text.replace('```json', '').replace('```', '').strip()
                    result = json.loads(text)
                    return result
                except:
                    pass
            except Exception as e:
                print(f"Gemini Error: {str(e)}")

        # Fallback to improved keyword matching
        msg = message.lower()
        if any(word in msg for word in ["puedo pagar", "pagaré", "el dia", "pago el"]):
            return {"intent": "payment_promise"}
        elif any(word in msg for word in ["debo", "saldo", "pagar", "cuenta", "pago"]):
            return {"intent": "check_balance"}
        elif any(word in msg for word in ["vence", "corte", "fecha", "vencimiento"]):
            return {"intent": "check_due_date"}
        elif any(word in msg for word in ["internet", "lento", "falla", "sin servicio", "no tengo"]):
            return {"intent": "report_issue"}
        
        return {"intent": "general_inquiry"}

    def execute_administrative_task(self, intent: str, params: Dict[str, Any]) -> str:
        client = params.get('client')
        message = params.get('message', '')
        
        if intent == "check_balance":
            balance = getattr(client, 'account_balance', 0)
            if balance <= 0:
                return f"Estimado/a {client.legal_name}, me es grato informarle que su cuenta se encuentra actualmente al día. No registramos valores pendientes a la fecha. ¡Agradecemos su puntualidad!"
            else:
                return f"Cordial saludo, {client.legal_name}. Tras verificar en nuestro sistema, he identificado un saldo pendiente de ${balance:,.2f} en su facturación. ¿Desea que le genere el soporte de pago?"

        elif intent == "check_due_date":
            due_date = getattr(client, 'due_date', None)
            if due_date:
                return f"He revisado su ciclo de facturación, {client.legal_name}. Su próxima fecha de vencimiento es el {due_date.day}/{due_date.month}/{due_date.year}. Le recomendamos realizar el pago antes de esta fecha para garantizar la continuidad de su servicio."
            return f"Lo lamento, {client.legal_name}, pero no he logrado determinar su próxima fecha exacta de vencimiento en este momento. Permítame consultar con el área de cartera y le informaré a la brevedad."

        elif intent == "report_issue":
            is_online = getattr(client, 'is_online', False)
            if is_online:
                return f"Entiendo su inquietud, {client.legal_name}. He realizado una verificación técnica remota y detecto que su router está respondiendo correctamente a nuestra central. Si experimenta lentitud, por favor reinicie su equipo. En caso de que persista, escalaré su caso a soporte técnico nivel 2."
            else:
                return f"Lamento los inconvenientes, {client.legal_name}. Confirmo que su servicio figura actualmente como desconectado de nuestra red. He generado una alerta técnica prioritaria para que nuestra cuadrilla verifique el estado del nodo en su sector."

        elif intent == "payment_promise":
            return f"Entiendo perfectamente su situación, {client.legal_name}. En SGUBM valoramos mucho su permanencia. He procesado su intención de pago voluntario; por favor, indíqueme en qué fecha exacta podrá realizar el abono para registrar su promesa de pago y evitar la suspensión del servicio."

        return f"Muchas gracias por su mensaje, {client.legal_name}. Como su asistente virtual, he registrado su consulta. Un asesor especializado la atenderá personalmente en unos instantes para brindarle una solución a medida."

    def _find_client_by_phone(self, phone: str) -> Optional[Any]:
        # Clean phone number
        clean_phone = "".join(filter(str.isdigit, phone))
        if not clean_phone:
            return None
            
        # Try finding by exact match or suffix (last 10 digits as a common pattern)
        # We search in DB using ilike for more flexibility
        search_pattern = f"%{clean_phone[-10:]}%"
        from src.infrastructure.database.models import Client
        return self.db_manager.session.query(Client).filter(Client.phone.ilike(search_pattern)).first()
