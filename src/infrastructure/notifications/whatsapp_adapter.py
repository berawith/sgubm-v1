"""
WhatsApp Infrastructure Adapter
Implementation of INotificationService for WhatsApp.
"""
from typing import Dict, Any, Optional
from src.core.interfaces.contracts import INotificationService
import requests
import logging

class WhatsAppAdapter(INotificationService):
    def __init__(self, bridge_url: str, api_key: str):
        self.bridge_url = bridge_url
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

    def send_email(self, to: str, subject: str, body: str) -> bool:
        # Not implemented here
        return False

    def send_sms(self, phone: str, message: str) -> bool:
        # Not implemented here
        return False

    def send_whatsapp(self, phone: str, message: str) -> bool:
        """
        Sends a WhatsApp message via the local bridge API (port 5001).
        """
        try:
            # El bridge corre en el mismo servidor generalmente
            url = "http://localhost:5001/send"
            payload = {
                "phone": phone,
                "text": message
            }
            
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200 and response.json().get('success')
            
        except Exception as e:
            self.logger.error(f"Error sending WhatsApp via Bridge API: {str(e)}")
            return False

    def handle_webhook(self, data: Dict[str, Any], agent_service: Any):
        """
        Handles incoming events from the WhatsApp bridge.
        """
        # Example structure for incoming message
        message_data = data.get('data', {})
        phone = message_data.get('remoteJid', '').split('@')[0]
        text = message_data.get('message', {}).get('conversation', '')
        
        if phone and text:
            response = agent_service.process_incoming_message(phone, text)
            self.send_whatsapp(phone, response)
