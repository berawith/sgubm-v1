"""
Unit Tests for Monitoring Utilities
Verifica el correcto funcionamiento del parseo de tiempo de MikroTik.
"""
import pytest
from datetime import datetime, timedelta
from src.application.services.monitoring_utils import MikroTikTimeParser

def test_parse_absolute_time():
    # Formato completo
    time_str = "sep/02/2023 14:00:00"
    dt = MikroTikTimeParser.parse(time_str)
    assert dt is not None
    assert dt.year == 2023
    assert dt.month == 9
    assert dt.day == 2
    assert dt.hour == 14

def test_parse_relative_time_simple():
    # 10 minutos atrás
    time_str = "10m"
    dt = MikroTikTimeParser.parse(time_str)
    assert dt is not None
    # Permitir margen de error de 2 segundos por ejecución
    now = datetime.now()
    expected = now - timedelta(minutes=10)
    assert abs((now - dt).total_seconds() - 600) < 2

def test_parse_relative_time_complex():
    # 1 día, 5 horas, 20 minutos
    time_str = "1d05:20:00"
    dt = MikroTikTimeParser.parse(time_str)
    assert dt is not None
    
    now = datetime.now()
    total_expected_seconds = 86400 + (5 * 3600) + (20 * 60)
    assert abs((now - dt).total_seconds() - total_expected_seconds) < 2

def test_parse_never():
    assert MikroTikTimeParser.parse("never") is None
    assert MikroTikTimeParser.parse("") is None

if __name__ == "__main__":
    pytest.main([__file__])
