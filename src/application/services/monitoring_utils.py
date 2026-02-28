"""
Monitoring Utilities
Utilidades puras para el procesamiento de datos de MikroTik.
"""
import re
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

class MikroTikTimeParser:
    """
    Analizador estático de formatos de tiempo de RouterOS.
    Soporta formatos relativos (uptime) y absolutos (timestamps).
    """

    @staticmethod
    def parse(time_str: str) -> Optional[datetime]:
        """
        Punto de entrada principal para el parseo de tiempo.
        """
        if not time_str or time_str.lower() == 'never':
            return None
        
        # 1. Intentar como fecha absoluta (Formato oct/11/2023...)
        dt = MikroTikTimeParser._parse_absolute(time_str)
        if dt:
            return dt
        
        # 2. Intentar como duración relativa (Formato 24d 06:36:28...)
        return MikroTikTimeParser._parse_relative(time_str)

    @staticmethod
    def _parse_absolute(time_str: str) -> Optional[datetime]:
        """Parses Mikrotik absolute time string (e.g. 'sep/02/2023 14:00:00')"""
        try:
            months = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            
            parts = time_str.split(' ')
            if len(parts) != 2:
                return None
            
            date_part, time_part = parts
            date_subparts = date_part.split('/')
            
            if len(date_subparts) == 3:
                m_str, d_str, y_str = date_subparts
            elif len(date_subparts) == 2:
                m_str, d_str = date_subparts
                y_str = str(datetime.now().year)
            else:
                return None
            
            month = months.get(m_str.lower())
            if not month:
                return None
            
            dt_str = f"{y_str}-{month:02d}-{int(d_str):02d} {time_part}"
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    @staticmethod
    def _parse_relative(time_str: str) -> Optional[datetime]:
        """Parses Mikrotik relative time (uptime) into a reference datetime."""
        try:
            s = time_str.strip().lower()
            total_seconds = 0
            
            # Semanas y Días
            w_match = re.search(r'(\d+)\s*w', s)
            d_match = re.search(r'(\d+)\s*d', s)
            if w_match: total_seconds += int(w_match.group(1)) * 604800
            if d_match: total_seconds += int(d_match.group(1)) * 86400
            
            # Quitar parte de dias/semanas para procesar H:M:S o h/m/s
            remaining = re.sub(r'\d+\s*[wd]', '', s).strip()
            
            if ':' in remaining:
                parts = [int(x) for x in remaining.split(':')]
                if len(parts) == 3: 
                    total_seconds += parts[0] * 3600 + parts[1] * 60 + parts[2]
                elif len(parts) == 2: 
                    total_seconds += parts[1] * 60 + parts[2] if len(parts) > 2 else parts[0] * 60 + parts[1]
            else:
                for unit, mult in [('h', 3600), ('m', 60), ('s', 1)]:
                    match = re.search(fr'(\d+)\s*{unit}', remaining)
                    if match: total_seconds += int(match.group(1)) * mult
            
            if total_seconds > 0:
                return datetime.now() - timedelta(seconds=total_seconds)
        except Exception as e:
            logger.debug(f"Error parseando tiempo relativo '{time_str}': {e}")
            
        return None
