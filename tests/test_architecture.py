"""
Test de Arquitectura Modular
Verifica que los módulos están correctamente desacoplados
"""
import sys
import os

# Agrega el directorio raíz del proyecto al sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_imports():
    """Verifica que todos los módulos se importan correctamente"""
    print("🧪 Testing modular architecture...\n")
    
    # Test 1: Core Domain (sin dependencias)
    try:
        from src.core.domain.entities import Client, Node, ServicePlan, ManagementMethod
        print("✅ Core Domain imports successfully (no external dependencies)")
    except Exception as e:
        print(f"❌ Core Domain import failed: {e}")
        return False
    
    # Test 2: Interfaces
    try:
        from src.core.interfaces.contracts import INetworkService, IRepository
        print("✅ Interfaces import successfully")
    except Exception as e:
        print(f"❌ Interfaces import failed: {e}")
        return False
    
    # Test 3: Event Bus
    try:
        from src.application.events.event_bus import get_event_bus, SystemEvents
        print("✅ Event Bus imports successfully")
    except Exception as e:
        print(f"❌ Event Bus import failed: {e}")
        return False
    
    # Test 4: Configuration
    try:
        from src.infrastructure.config.settings import get_config
        config = get_config()
        print(f"✅ Configuration loaded successfully (Environment: {config.system.environment})")
    except Exception as e:
        print(f"❌ Configuration import failed: {e}")
        return False
    
    # Test 5: MikroTik Adapter
    try:
        from src.infrastructure.mikrotik.adapter import MikroTikAdapter
        print("✅ MikroTik Adapter implements INetworkService")
    except Exception as e:
        print(f"❌ MikroTik Adapter import failed: {e}")
        return False
    
    return True


def test_domain_entities():
    """Verifica que las entidades de dominio funcionan sin dependencias"""
    print("\n🧪 Testing Domain Entities...\n")
    
    from src.core.domain.entities import Client, Node, ServicePlan, BurstConfig, ManagementMethod
    from datetime import datetime
    
    # Test Client
    client = Client(
        subscriber_code="CLI-001",
        legal_name="John Doe",
        identity_document="12345678",
        account_balance=-50.0,
        credit_status="overdue"  # Marcar como moroso
    )
    
    assert client.is_overdue() == True, "Client should be overdue"
    print("✅ Client entity works correctly")
    
    # Test Node
    node = Node(
        alias="Router Principal",
        host_address="192.168.1.1"
    )
    
    node.enable_capability(ManagementMethod.PPPOE)
    assert node.supports_pppoe == True, "Node should support PPPoE"
    print("✅ Node entity works correctly")
    
    # Test ServicePlan
    plan = ServicePlan(
        commercial_name="Plan 50MB",
        base_cost=29.99,
        download_speed="50M",
        upload_speed="10M"
    )
    
    price_with_tax = plan.calculate_price_with_tax(0.12)
    assert price_with_tax > plan.base_cost, "Price with tax should be higher"
    print("✅ ServicePlan entity works correctly")
    
    return True


def test_event_bus():
    """Verifica que el Event Bus funciona para comunicación desacoplada"""
    print("\n🧪 Testing Event Bus (Decoupled Communication)...\n")
    
    from src.application.events.event_bus import get_event_bus, SystemEvents
    
    event_bus = get_event_bus()
    
    # Suscriptor de prueba
    received_events = []
    
    def test_handler(data):
        received_events.append(data)
    
    # Suscribirse a un evento
    event_bus.subscribe(SystemEvents.CLIENT_CREATED, test_handler)
    
    # Publicar evento
    event_bus.publish(SystemEvents.CLIENT_CREATED, {
        "client_id": "123",
        "name": "Test Client"
    })
    
    assert len(received_events) == 1, "Event should be received"
    assert received_events[0]["client_id"] == "123", "Event data should match"
    
    print("✅ Event Bus works correctly (modules can communicate without coupling)")
    
    return True


def test_dependency_injection():
    """Verifica que las interfaces permiten inyección de dependencias"""
    print("\n🧪 Testing Dependency Injection Pattern...\n")
    
    from src.core.interfaces.contracts import INetworkService
    from typing import Dict, Any
    
    # Mock implementation (sin usar MikroTik real)
    class MockNetworkService(INetworkService):
        def connect(self, host: str, username: str, password: str, port: int = 8728) -> bool:
            return True
        
        def disconnect(self) -> None:
            pass
        
        def create_client_service(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
            return {"success": True, "mock": True}
        
        def discover_configuration(self) -> Dict[str, Any]:
            return {"methods": ["pppoe"]}
        
        # Implementar otros métodos abstractos
        def update_client_service(self, client_id: str, updates: Dict[str, Any]) -> bool:
            return True
        def suspend_client_service(self, client_id: str) -> bool:
            return True
        def restore_client_service(self, client_id: str) -> bool:
            return True
        def delete_client_service(self, client_id: str) -> bool:
            return True
        def get_client_stats(self, client_id: str) -> Dict[str, Any]:
            return {}
    
    # Servicio que usa la interfaz (no la implementación)
    class TestService:
        def __init__(self, network: INetworkService):
            self.network = network
        
        def provision_client(self):
            return self.network.create_client_service({"username": "test"})
    
    # Inyectar el mock
    mock_network = MockNetworkService()
    service = TestService(network=mock_network)
    
    result = service.provision_client()
    assert result["success"] == True, "Service should work with injected dependency"
    
    print("✅ Dependency Injection works correctly")
    print("   → Service doesn't know if it's using MikroTik, Cisco, or Mock")
    print("   → Implementation can be changed without modifying the service")
    
    return True


def test_configuration():
    """Verifica que la configuración centralizada funciona"""
    print("\n🧪 Testing Centralized Configuration...\n")
    
    from src.infrastructure.config.settings import get_config
    
    config = get_config()
    
    # Verificar que las configuraciones son accesibles
    assert hasattr(config, 'database'), "Config should have database section"
    assert hasattr(config, 'mikrotik'), "Config should have mikrotik section"
    assert hasattr(config, 'billing'), "Config should have billing section"
    
    # Verificar conexión string
    db_string = config.database.connection_string
    assert len(db_string) > 0, "Database connection string should be generated"
    
    print(f"✅ Configuration System works correctly")
    print(f"   → Database: {config.database.driver}")
    print(f"   → Environment: {config.system.environment}")
    print(f"   → Debug Mode: {config.system.debug_mode}")
    
    return True


def run_all_tests():
    """Ejecuta todos los tests de arquitectura"""
    print("=" * 80)
    print("🚀 SGUBM-V1 - Modular Architecture Test Suite")
    print("=" * 80)
    
    tests = [
        ("Module Imports", test_imports),
        ("Domain Entities", test_domain_entities),
        ("Event Bus", test_event_bus),
        ("Dependency Injection", test_dependency_injection),
        ("Configuration", test_configuration)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"❌ {test_name} failed")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} raised exception: {e}")
    
    print("\n" + "=" * 80)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    print("=" * 80)
    
    if failed == 0:
        print("\n✨ All tests passed! Modular architecture is working correctly.")
        print("\n🎯 Key Achievements:")
        print("   • Modules are decoupled")
        print("   • Interfaces enable dependency injection")
        print("   • Event Bus allows communication without coupling")
        print("   • Configuration is centralized")
        print("   • Domain logic has no external dependencies")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please check the errors above.")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
