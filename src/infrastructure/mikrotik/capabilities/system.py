import logging
from typing import Dict, Any, List, Optional
from .base import CapabilityBase

logger = logging.getLogger(__name__)

class SystemCapability(CapabilityBase):
    """
    Gestiona recursos del sistema, DHCP, ARP, Firewall y monitoreo de hardware.
    """

    def get_resource_usage(self) -> Dict[str, Any]:
        """Obtiene uso de CPU, Memoria y Uptime"""
        try:
            res = self._get_resource('/system/resource').get()
            if res:
                data = res[0]
                total_mem = int(data.get("total-memory", 0))
                free_mem = int(data.get("free-memory", 0))
                return {
                    "platform": data.get("platform", ""),
                    "board_name": data.get("board-name", ""),
                    "version": data.get("version", ""),
                    "uptime": data.get("uptime", ""),
                    "cpu_load": data.get("cpu-load", "0"),
                    "memory_usage": int(((total_mem - free_mem) / total_mem) * 100) if total_mem > 0 else 0
                }
            return {"uptime": "N/A", "cpu_load": 0, "memory_usage": 0}
        except Exception as e:
            logger.error(f"Error obteniendo recursos del sistema: {e}")
            return {"uptime": "N/A", "cpu_load": 0, "memory_usage": 0}

    def get_interfaces(self) -> List[Dict[str, Any]]:
        """Obtiene lista de interfaces"""
        try:
            return self._get_resource('/interface').get()
        except Exception as e:
            logger.error(f"Error obteniendo interfaces: {e}")
            return []

    def get_dhcp_leases(self) -> List[Dict[str, Any]]:
        """Obtiene leases de DHCP activos"""
        try:
            return self._get_resource('/ip/dhcp-server/lease').get(status='bound')
        except Exception as e:
            logger.error(f"Error obteniendo DHCP leases: {e}")
            return []

    def get_arp_table(self) -> List[Dict[str, Any]]:
        """Obtiene tabla ARP"""
        try:
            return self._get_resource('/ip/arp').get()
        except Exception as e:
            logger.error(f"Error obteniendo tabla ARP: {e}")
            return []

    def ensure_firewall_rules(self) -> bool:
        """Configura reglas de firewall para cortes (Centinela)"""
        try:
            filter_rules = self._get_resource('/ip/firewall/filter')
            rules = [
                {'chain': 'forward', 'src-address-list': 'IPS_BLOQUEADAS', 'action': 'drop', 'comment': 'SGUBM: Bloquear Forward'},
                {'chain': 'input', 'src-address-list': 'IPS_BLOQUEADAS', 'action': 'drop', 'comment': 'SGUBM: Bloquear Input'}
            ]
            all_filters = filter_rules.get()
            for r_def in rules:
                exists = any(f.get('comment') == r_def['comment'] for f in all_filters)
                if not exists:
                    filter_rules.add(**r_def, **{'place-before': '0'})
            return True
        except Exception as e:
            logger.error(f"Error configurando firewall: {e}")
            return False

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Obtiene logs recientes"""
        try:
            return self._get_resource('/log').get()[-limit:]
        except Exception as e:
            logger.error(f"Error obteniendo logs: {e}")
            return []

    def ping(self, targets: List[str], count: int = 2) -> Dict[str, Any]:
        """Ejecuta pings desde el router"""
        results = {}
        try:
            ping_resource = self._get_resource('/tool')
            for target in targets:
                try:
                    res = ping_resource.call('ping', {'address': target, 'count': str(count)})
                    avg_lat = 0
                    received = sum(int(p.get('received', '0')) for p in res)
                    latencies = [int(p.get('time', '0').replace('ms', '')) for p in res if p.get('received') != '0']
                    avg_lat = sum(latencies) / len(latencies) if latencies else 0
                    loss = ((count - received) / count) * 100
                    results[target] = {'latency': avg_lat, 'loss': loss}
                except:
                    results[target] = {'latency': 0, 'loss': 100}
            return results
        except Exception as e:
            logger.error(f"Error ejecutando ping masivo: {e}")
            return {}

    def get_all_last_seen(self) -> Dict[str, str]:
        """
        Obtiene 'Last Seen' combinando DHCP y PPPoE.
        """
        results = {}
        try:
            leases = self._get_resource('/ip/dhcp-server/lease').get()
            for l in leases:
                addr = l.get('address')
                last_seen = l.get('last-seen')
                if addr and last_seen:
                    results[addr] = last_seen
            return results
        except Exception as e:
            logger.error(f"Error en get_all_last_seen: {e}")
            return {}
