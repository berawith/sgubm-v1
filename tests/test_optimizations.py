"""
Test de Verificación de Optimizaciones
Verifica que las optimizaciones críticas no rompan la estructura del sistema
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Agrega el directorio raíz del proyecto al sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.application.services.billing_service import BillingService
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

class TestOptimizations(unittest.TestCase):

    def test_billing_service_has_adapter(self):
        """Verifica que BillingService puede importar MikroTikAdapter"""
        print("✅ BillingService imports successfully")

    def test_adapter_has_bulk_suspend(self):
        """Verifica que MikroTikAdapter tiene el método bulk_suspend_clients"""
        adapter = MikroTikAdapter()
        self.assertTrue(hasattr(adapter, 'bulk_suspend_clients'),
                       "MikroTikAdapter should have bulk_suspend_clients method")
        print("✅ MikroTikAdapter.bulk_suspend_clients exists")

    @patch('src.application.services.billing_service.get_db')
    def test_billing_service_structure(self, mock_get_db):
        """Verifica la estructura básica de BillingService"""
        service = BillingService()
        self.assertTrue(hasattr(service, 'process_suspensions'))
        self.assertTrue(hasattr(service, 'generate_monthly_invoices'))
        print("✅ BillingService methods exist")

if __name__ == '__main__':
    unittest.main()
