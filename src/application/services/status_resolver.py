"""
Status Resolver
Aisla la lógica de decisión de estado de red y políticas de gracia.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from src.application.services.monitoring_utils import MikroTikTimeParser

logger = logging.getLogger(__name__)

class StatusResolver:
    """
    Motor de decisión para determinar el estado Online/Offline de un cliente.
    Aplica heurísticas basadas en PPPoE, ARP y DHCP.
    """

    @staticmethod
    def resolve_online_status(info: Dict[str, Any]) -> bool:
        """
        Determina si un cliente está online basado en el snapshot del TrafficEngine.
        """
        return info.get('status') == 'online'

    @staticmethod
    def resolve_last_seen(client: Any, offline_metadata: Dict[str, str]) -> Optional[datetime]:
        """
        Determina el último momento visto para un cliente offline usando metadata de MikroTik.
        """
        if not offline_metadata:
            return None

        # Prioridad 1: IP Address
        if client.ip_address and client.ip_address in offline_metadata:
            dt = MikroTikTimeParser.parse(offline_metadata[client.ip_address])
            if dt: return dt

        # Prioridad 2: Username (PPPoE/DHCP name)
        if client.username and client.username in offline_metadata:
            dt = MikroTikTimeParser.parse(offline_metadata[client.username])
            if dt: return dt

        # Prioridad 3: MAC Address
        if hasattr(client, 'mac_address') and client.mac_address and client.mac_address in offline_metadata:
            dt = MikroTikTimeParser.parse(offline_metadata[client.mac_address])
            if dt: return dt

        return None
