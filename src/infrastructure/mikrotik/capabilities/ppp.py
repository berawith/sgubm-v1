import logging
from typing import Dict, Any, List, Optional
from .base import CapabilityBase

logger = logging.getLogger(__name__)

class PPPCapability(CapabilityBase):
    """
    Gestiona todas las operaciones de PPP (Secrets, Profiles, Active Sessions).
    """
    
    def detect(self) -> Dict[str, Any]:
        """Detecta configuración de PPPoE"""
        try:
            profiles = self._get_resource('/ppp/profile')
            secrets = self._get_resource('/ppp/secret')
            pools = self._get_resource('/ip/pool')
            
            profile_list = profiles.get()
            secret_list = secrets.get()
            pool_list = pools.get()
            
            detected_profiles = []
            detected_pools = []
            
            for profile in profile_list:
                detected_profiles.append({
                    "name": profile.get("name", ""),
                    "local_address": profile.get("local-address", ""),
                    "remote_address": profile.get("remote-address", ""),
                    "rate_limit": profile.get("rate-limit", "")
                })
            
            for pool in pool_list:
                detected_pools.append({
                    "name": pool.get("name", ""),
                    "ranges": pool.get("ranges", "")
                })
            
            return {
                "enabled": len(secret_list) > 0,
                "profiles": detected_profiles,
                "pools": detected_pools,
                "client_count": len(secret_list)
            }
        except Exception as e:
            logger.error(f"Error detectando PPPoE en {self._host}: {str(e)}")
            return {"enabled": False, "profiles": [], "pools": []}

    def create_profile(self, name: str, rate_limit: str, local_address: str = None, remote_address: str = None) -> bool:
        """Crea o actualiza un perfil PPPoE"""
        try:
            profiles = self._get_resource('/ppp/profile')
            existing = profiles.get(name=name)
            
            params = {
                "name": name,
                "rate-limit": rate_limit,
                "only-one": "default"
            }
            if local_address: params["local-address"] = local_address
            if remote_address: params["remote-address"] = remote_address
            
            if existing:
                profiles.set(id=existing[0]['id'], **params)
            else:
                profiles.add(**params)
            return True
        except Exception as e:
            logger.error(f"Error gestionando perfil PPP {name}: {e}")
            return False

    def create_client(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Crea cliente PPPoE"""
        try:
            secrets = self._get_resource('/ppp/secret')
            secret_params = {
                "name": client_data["username"],
                "password": client_data["password"],
                "service": "pppoe",
                "profile": client_data.get("profile", "default"),
                "comment": ""
            }
            if "local_address" in client_data: secret_params["local-address"] = client_data["local_address"]
            if "remote_address" in client_data: secret_params["remote-address"] = client_data["remote_address"]
            
            result = secrets.add(**secret_params)
            return {
                "success": True,
                "mikrotik_id": result.get("ret", ""),
                "method": "pppoe"
            }
        except Exception as e:
            logger.error(f"Error creando cliente PPP {client_data.get('username')}: {e}")
            raise

    def get_active_sessions(self) -> Dict[str, Any]:
        """Obtiene lista de sesiones PPPoE activas"""
        try:
            ppp_active = self._get_resource('/ppp/active')
            sessions = {}
            for s in ppp_active.get():
                user = s.get('name')
                if user:
                    sessions[user] = {
                        'ip': s.get('address'),
                        'uptime': s.get('uptime'),
                        'id': s.get('id') or s.get('.id')
                    }
            return sessions
        except Exception as e:
            logger.error(f"Error obteniendo sesiones activas: {e}")
            return {}

    def remove_secret(self, username: str) -> bool:
        """Elimina un Secret PPPoE por nombre"""
        try:
            secrets = self._get_resource('/ppp/secret')
            existing = secrets.get(name=username)
            if existing:
                secrets.remove(id=existing[0]['id'])
                return True
            return False
        except Exception as e:
            logger.error(f"Error eliminando Secret {username}: {e}")
            return False
