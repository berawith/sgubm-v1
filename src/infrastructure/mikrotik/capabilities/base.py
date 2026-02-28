import logging
from typing import Optional, List, Dict, Any
from routeros_api.exceptions import RouterOsApiConnectionError, RouterOsApiCommunicationError

logger = logging.getLogger(__name__)

class CapabilityBase:
    """
    Clase base para capacidades de MikroTik (Centinela).
    Provee acceso seguro a la API y aislamiento de errores local.
    """
    def __init__(self, api_connection):
        self._api = api_connection
        self._host = "unknown" # Se inyecta desde el Adapter principal

    def _get_resource(self, path: str):
        """Acceso centralizado a recursos con captura proactiva de fallos."""
        try:
            return self._api.get_resource(path)
        except (RouterOsApiConnectionError, RouterOsApiCommunicationError) as e:
            logger.error(f"🚨 [Centinela] Fallo de comunicación en {path}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"🚨 [Centinela] Error inesperado accediendo a {path}: {str(e)}")
            raise

    def set_host(self, host: str):
        self._host = host
