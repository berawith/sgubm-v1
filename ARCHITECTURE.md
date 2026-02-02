# ARQUITECTURA MODULAR HEXAGONAL - SGUBM-V1

## 📐 Principios Fundamentales

### 1. Separation of Concerns Absoluta
Cada módulo es **completamente independiente** y se comunica mediante **contratos (interfaces)**.

### 2. Dependency Inversion
```
┌────────────────────────────────────┐
│     HIGH LEVEL (Business Logic)    │
│   NO depende de implementaciones    │
└──────────────┬─────────────────────┘
               │ (Interfaces)
┌──────────────▼─────────────────────┐
│   LOW LEVEL (Infrastructure)        │
│   Implementaciones intercambiables   │
└────────────────────────────────────┘
```

### 3. Open/Closed Principle
- **Abierto** para extensión (añadir nuevos adaptadores, servicios)
- **Cerrado** para modificación (el núcleo NO cambia)

---

## 🏗️ Capas de la Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│  (API Controllers, WebSockets, Static Files)                │
│  • No contiene lógica de negocio                            │
│  • Solo traduce requests a DTOs                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                          │
│  (Use Cases, Services, Orchestration)                       │
│  • Coordina flujos de negocio                               │
│  • Usa interfaces, NO implementaciones                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      DOMAIN LAYER                            │
│  (Entities, Value Objects, Business Rules)                  │
│  • Núcleo puro SIN dependencias externas                    │
│  • Solo lógica de negocio                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  INFRASTRUCTURE LAYER                        │
│  (Database, MikroTik, APIs Externas)                        │
│  • Implementaciones concretas de interfaces                 │
│  • Intercambiables sin afectar el núcleo                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Estructura de Módulos

### Core (Núcleo del Sistema)
```
src/core/
├── domain/              # Entidades y reglas de negocio
│   └── entities.py      # Node, Client, Plan, Subscription, etc.
├── interfaces/          # Contratos entre capas
│   └── contracts.py     # INetworkService, IRepository, etc.
└── exceptions/          # Excepciones del dominio
    └── errors.py
```

**Regla de Oro:** El Core NO IMPORTA nada de otras capas.

---

### Application (Casos de Uso)
```
src/application/
├── services/            # Servicios de aplicación
│   ├── client_service.py       # Gestión de clientes
│   ├── billing_service.py      # Facturación
│   └── provisioning_service.py # Aprovisionamiento
├── dto/                 # Data Transfer Objects
│   └── schemas.py
└── events/              # Event Bus
    └── event_bus.py     # Pub/Sub para módulos
```

**Ejemplo de Servicio Desacoplado:**
```python
from core.interfaces.contracts import INetworkService, IRepository

class ProvisioningService:
    def __init__(self, 
                 network_service: INetworkService,  # Interface, NO implementación
                 client_repo: IRepository):
        self.network = network_service
        self.clients = client_repo
    
    def provision_new_client(self, client_data):
        # Lógica que funciona con CUALQUIER implementación
        client = self.clients.create(client_data)
        self.network.create_client_service(client)
```

---

### Infrastructure (Implementaciones)
```
src/infrastructure/
├── database/            # Repositorios SQL
│   ├── repositories/
│   │   ├── client_repository.py
│   │   └── node_repository.py
│   └── models.py        # SQLAlchemy models
├── mikrotik/            # Adaptador MikroTik
│   ├── adapter.py       # Implementa INetworkService
│   └── commands.py
├── cisco/               # Adaptador Cisco (futuro)
│   └── adapter.py       # También implementa INetworkService
├── security/
│   └── auth_service.py  # Implementa IAuthService
└── config/
    └── settings.py      # Configuración centralizada
```

**Clave:** Puedes cambiar de MikroTik a Cisco solo cambiando qué adaptador se inyecta.

---

## ⚡ Event Bus (Comunicación Desacoplada)

### ¿Por qué Event Bus?
Los módulos NO se conocen entre sí. Se comunican mediante eventos.

### Ejemplo Práctico:

**Módulo de Facturación** (publica evento):
```python
from application.events.event_bus import get_event_bus, SystemEvents

event_bus = get_event_bus()
event_bus.publish(SystemEvents.PAYMENT_OVERDUE, {
    "client_id": "123",
    "days_overdue": 15
})
```

**Módulo de Aprovisionamiento** (escucha evento):
```python
def suspend_overdue_client(data):
    client_id = data["client_id"]
    # Suspender servicio automáticamente
    network_service.suspend_client_service(client_id)

event_bus.subscribe(SystemEvents.PAYMENT_OVERDUE, suspend_overdue_client)
```

**Módulo de Notificaciones** (también escucha):
```python
def notify_overdue(data):
    send_sms(client_id, "Su servicio será suspendido en 24 horas")

event_bus.subscribe(SystemEvents.PAYMENT_OVERDUE, notify_overdue)
```

✅ Los 3 módulos NO se conocen entre sí  
✅ Puedes agregar/quitar módulos sin romper nada  
✅ Testeable independientemente  

---

## 🎯 Inyección de Dependencias

### Problema del Código Espagueti:
```python
# ❌ MAL: Dependencia directa
class BillingService:
    def __init__(self):
        self.network = MikroTikAdapter()  # Acoplamiento fuerte
```

Si quieres cambiar Router, debes modificar BillingService.

### Solución con DI:
```python
# ✅ BIEN: Inyección de interfaz
class BillingService:
    def __init__(self, network_service: INetworkService):
        self.network = network_service  # Cualquier implementación
```

Ahora puedes inyectar MikroTik, Cisco, o un Mock para tests.

### Contenedor de DI (Service Locator Pattern):
```python
# infrastructure/di/container.py
class ServiceContainer:
    def __init__(self):
        self._services = {}
    
    def register(self, interface, implementation):
        self._services[interface] = implementation
    
    def resolve(self, interface):
        return self._services[interface]

# Configuración
container = ServiceContainer()
container.register(INetworkService, MikroTikAdapter())
container.register(IRepository, SQLAlchemyRepository())

# Uso
billing = BillingService(
    network_service=container.resolve(INetworkService),
    client_repo=container.resolve(IRepository)
)
```

---

## 📐 Ejemplo Completo: Agregar un Cliente

### 1. Controller (Presentation)
```python
# presentation/api/clients_controller.py
from flask import Blueprint, request

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/clients', methods=['POST'])
def create_client():
    client_data = request.json
    # Delega al servicio (no tiene lógica)
    result = client_service.create_client(client_data)
    return {"success": True, "client_id": result.id}
```

### 2. Service (Application)
```python
# application/services/client_service.py
class ClientService:
    def __init__(self, client_repo: IRepository, event_bus: IEventBus):
        self.clients = client_repo
        self.events = event_bus
    
    def create_client(self, data):
        # Lógica de negocio
        client = Client(**data)
        saved_client = self.clients.create(client)
        
        # Publica evento (otros módulos reaccionan)
        self.events.publish(SystemEvents.CLIENT_CREATED, {
            "client_id": saved_client.id
        })
        
        return saved_client
```

### 3. Domain (Core)
```python
# core/domain/entities.py
@dataclass
class Client:
    id: str
    name: str
    
    def is_overdue(self) -> bool:
        # Lógica de negocio pura
        return self.account_balance < 0
```

### 4. Repository (Infrastructure)
```python
# infrastructure/database/repositories/client_repository.py
class ClientRepository(IRepository):
    def create(self, entity):
        # Lógica de persistencia
        session.add(entity)
        session.commit()
        return entity
```

---

## 🔧 Configuración Centralizada

Un solo archivo define TODA la configuración:

```python
from infrastructure.config.settings import get_config

config = get_config()

# Acceso tipado y seguro
db_string = config.database.connection_string
timeout = config.mikrotik.connection_timeout
enable_billing = config.billing.enable_auto_billing
```

✅ Un solo punto de cambio  
✅ Validación automática  
✅ Sin valores hardcoded  

---

## 🧪 Testing Modular

### Test de Dominio (sin dependencias):
```python
def test_client_overdue_status():
    client = Client(name="Test", account_balance=-100)
    assert client.is_overdue() == True
```

### Test de Servicio (con mocks):
```python
def test_create_client_service():
    # Mock repository
    mock_repo = Mock(IRepository)
    mock_repo.create.return_value = Client(id="123")
    
    # Mock event bus
    mock_events = Mock(IEventBus)
    
    # Servicio con dependencias mockeadas
    service = ClientService(mock_repo, mock_events)
    result = service.create_client({"name": "Test"})
    
    assert result.id == "123"
    mock_events.publish.assert_called_once()
```

✅ Tests rápidos (sin base de datos)  
✅ Independientes entre sí  

---

## 🚀 Añadir un Nuevo Módulo (Sin Romper Nada)

### Paso 1: Crear la interfaz
```python
# core/interfaces/contracts.py
class ISMSService(ABC):
    @abstractmethod
    def send_sms(self, phone: str, message: str) -> bool:
        pass
```

### Paso 2: Crear la implementación
```python
# infrastructure/sms/twilio_adapter.py
class TwilioAdapter(ISMSService):
    def send_sms(self, phone, message):
        # Lógica de Twilio
        pass
```

### Paso 3: Registrar en el contenedor
```python
container.register(ISMSService, TwilioAdapter())
```

### Paso 4: Usar en cualquier servicio
```python
class NotificationService:
    def __init__(self, sms_service: ISMSService):
        self.sms = sms_service
```

✅ Ningún código existente fue modificado  
✅ Totalmente intercambiable  

---

## ✨ Beneficios de Esta Arquitectura

| Característica | Beneficio |
|----------------|-----------|
| **Modularidad** | Cada módulo vive solo |
| **Testeable** | Tests sin infraestructura |
| **Mantenible** | Cambios localizados |
| **Extensible** | Nuevas features sin romper |
| **Reutilizable** | Módulos en otros proyectos |
| **Escalable** | Despliegue de módulos independiente |

---

## 🎓 Reglas de Oro

1. **El Core NO importa nada de Infrastructure**
2. **Siempre inyecta interfaces, NUNCA implementaciones**
3. **Un cambio en un módulo NO debe romper otros**
4. **Usa Event Bus para comunicación cross-module**
5. **Un archivo de configuración, NO valores hardcoded**
6. **Cada clase tiene UNA sola responsabilidad**

---

## 📚 Próximos Pasos

1. Implementar repositorios SQL
2. Crear controllers REST para API
3. Desarrollar frontend modular
4. Añadir autenticación JWT
5. Sistema de reportes
6. Tests automatizados

**Recuerda:** Si modificas algo y rompes otro módulo, la arquitectura está mal implementada.
