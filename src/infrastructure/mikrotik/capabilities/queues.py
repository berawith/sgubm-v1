import logging
from typing import Dict, Any, List, Optional
from .base import CapabilityBase

logger = logging.getLogger(__name__)

class QueueCapability(CapabilityBase):
    """
    Gestiona Simple Queues, PCQ y recolección masiva de tráfico.
    """

    def detect(self) -> Dict[str, Any]:
        """Detecta configuración de Simple Queues"""
        try:
            queues = self._get_resource('/queue/simple')
            queue_list = queues.get()
            queue_types = {}
            for queue in queue_list:
                max_limit = queue.get("max-limit", "")
                if max_limit not in queue_types:
                    queue_types[max_limit] = {"max_limit": max_limit, "count": 0}
                queue_types[max_limit]["count"] += 1
            return {
                "enabled": len(queue_list) > 0,
                "queue_types": list(queue_types.values()),
                "total_queues": len(queue_list)
            }
        except Exception as e:
            logger.error(f"Error detectando Queues en {self._host}: {e}")
            return {"enabled": False, "queue_types": []}

    def detect_pcq(self) -> Dict[str, Any]:
        """Detecta configuración de PCQ"""
        try:
            queue_types = self._get_resource('/queue/type')
            pcq_types = [qt for qt in queue_types.get() if qt.get("kind", "") == "pcq"]
            return {"enabled": len(pcq_types) > 0, "pcq_count": len(pcq_types)}
        except Exception as e:
            logger.error(f"Error detectando PCQ: {e}")
            return {"enabled": False}

    def create_simple_queue(self, name: str, target: str, max_limit: str, 
                           burst_limit: str = None, burst_threshold: str = None, burst_time: str = None) -> bool:
        """Crea o actualiza una Simple Queue de forma directa."""
        try:
            queues = self._get_resource('/queue/simple')
            queue_params = {
                "name": name,
                "target": target,
                "max-limit": max_limit,
                "comment": ""
            }
            if burst_limit:
                queue_params["burst-limit"] = burst_limit
                queue_params["burst-threshold"] = burst_threshold or ""
                queue_params["burst-time"] = burst_time or "8s/8s"
            
            existing = queues.get(name=name)
            if existing:
                queues.set(id=existing[0]['id'], **queue_params)
            else:
                queues.add(**queue_params)
            return True
        except Exception as e:
            logger.error(f"Error gestionando Simple Queue {name}: {e}")
            return False

    def get_bulk_traffic(self, targets: List[str], all_ifaces: List[Dict] = None, all_queues: List[Dict] = None) -> Dict[str, Any]:
        """Obtiene tráfico en tiempo real procesando en ráfagas (chunks)."""
        results = {}
        try:
            # Si no se proveen colas, las obtenemos
            active_queues = all_queues if all_queues is not None else self._get_resource('/queue/simple').get()
            queue_map = {q.get('name'): q.get('rate', '0/0') for q in active_queues if q.get('name')}
            
            for target in targets:
                rate_str = queue_map.get(target, '0/0')
                parts = rate_str.split('/')
                if len(parts) == 2:
                    # En MikroTik Simple Queues, rate es upload/download
                    # Para el frontend: tx=download, rx=upload
                    results[target] = {'tx': int(parts[1]), 'rx': int(parts[0])}
                else:
                    results[target] = {'tx': 0, 'rx': 0}
            return results
        except Exception as e:
            logger.error(f"Error obteniendo tráfico masivo: {e}")
            return {}

    def remove_queue(self, name_or_ip: str) -> bool:
        """Elimina una Simple Queue"""
        try:
            queues = self._get_resource('/queue/simple')
            existing = queues.get(name=name_or_ip)
            if not existing:
                # Buscar por target
                all_q = queues.get()
                for q in all_q:
                    if q.get('target', '').split('/')[0] == name_or_ip:
                        existing = [q]
                        break
            if existing:
                queues.remove(id=existing[0]['id'])
                return True
            return False
        except Exception as e:
            logger.error(f"Error eliminando Simple Queue {name_or_ip}: {e}")
            return False
