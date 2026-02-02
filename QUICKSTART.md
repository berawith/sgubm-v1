# 🚀 Inicio Rápido - SGUBM-V1

## ✅ Arquitectura Verificada

La arquitectura modular hexagonal ha sido verificada exitosamente:

```
✨ All tests passed! Modular architecture is working correctly.

🎯 Key Achievements:
   • Modules are decoupled
   • Interfaces enable dependency injection
   • Event Bus allows communication without coupling
   • Configuration is centralized
   • Domain logic has no external dependencies
```

---

## 📋 Instalación

### 1. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar Entorno

El archivo `config/.env` ya está creado con valores por defecto. Edítalo según tus necesidades:

```bash
# Editar configuración
notepad config/.env
```

Configuraciones clave:
- `DB_DRIVER`: Tipo de base de datos (sqlite, postgresql)
- `SECRET_KEY`: Cambiar en producción
- `MT_AUTO_SYNC`: Habilitar sincronización automática con MikroTik

### 3. Ejecutar Aplicación

```bash
python run.py
```

La aplicación se ejecutará en: `http://localhost:5000`

---

## 📚 Documentación

| Documento | Descripción |
|-----------|-------------|
| `README.md` | Información general del proyecto |
| `ARCHITECTURE.md` | Arquitectura hexagonal detallada |
| `PROJECT_STRUCTURE.md` | Estructura de carpetas y módulos |

---

## 🧪 Ejecutar Tests

```bash
python tests/test_architecture.py
```

---

## 🎯 Siguiente Paso: Implementar Módulos

La estructura modular está lista. Ahora puedes agregar:

### 1. Database Repositories

Crear: `src/infrastructure/database/repositories/`

```python
from src.core.interfaces.contracts import IRepository

class ClientRepository(IRepository):
    def create(self, entity):
        # Implementación con SQLAlchemy
        pass
```

### 2. API Controllers

Crear: `src/presentation/api/clients.py`

```python
from flask import Blueprint

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/clients', methods=['GET'])
def get_clients():
    # Usar servicios inyectados
    pass
```

### 3. Frontend

Crear: `src/presentation/web/static/` y `templates/`

---

## 💡 Cómo Usar la Arquitectura Modular

### Ejemplo 1: Crear un Nuevo Servicio

```python
# 1. Definir interfaz en core/interfaces/contracts.py
class IEmailService(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> bool:
        pass

# 2. Implementar en infrastructure/email/
class GmailAdapter(IEmailService):
    def send(self, to, subject, body):
        # Implementación con Gmail API
        pass

# 3. Usar en application/services/
class NotificationService:
    def __init__(self, email: IEmailService):
        self.email = email  # Inyección
    
    def notify_client(self, client_id):
        self.email.send(...)
```

### Ejemplo 2: Comunicación Entre Módulos

```python
# Módulo A: Facturación
from src.application.events import get_event_bus, SystemEvents

event_bus = get_event_bus()
event_bus.publish(SystemEvents.PAYMENT_OVERDUE, {
    "client_id": "123"
})

# Módulo B: Aprovisionamiento (se ejecuta automáticamente)
def handle_overdue(data):
    suspend_service(data["client_id"])

event_bus.subscribe(SystemEvents.PAYMENT_OVERDUE, handle_overdue)
```

---

## 🔧 Configuración Avanzada

### Cambiar Base de Datos a PostgreSQL

En `config/.env`:

```env
DB_DRIVER=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=sgubm_isp
DB_USER=postgres
DB_PASSWORD=tu_password
```

### Habilitar Sincronización Automática MikroTik

```env
MT_AUTO_SYNC=true
MT_SYNC_INTERVAL=5
```

### Habilitar Notificaciones

```env
SMTP_HOST=smtp.gmail.com
SMTP_USER=tu_email@gmail.com
SMTP_PASSWORD=tu_password
```

---

## 📊 Estructura Actual

```
✅ Core Domain (Entidades de negocio)
✅ Interfaces (Contratos)
✅ Event Bus (Comunicación desacoplada)
✅ MikroTik Adapter (Integración RouterOS)
✅ Configuration System (Centralizado)
✅ Test Suite (Verificación de arquitectura)

⬜ Database Repositories (Próximo)
⬜ API REST Controllers (Próximo)
⬜ Authentication (Próximo)
⬜ Frontend UI (Próximo)
```

---

## 🎓 Principios a Seguir

1. **Nunca importar implementaciones directamente**
   - ❌ `from infrastructure.mikrotik import MikroTikAdapter`
   - ✅ `service = MyService(network: INetworkService)`

2. **Usar Event Bus para comunicación cross-module**
   - Los módulos no deben conocerse entre sí
   - Publicar eventos en lugar de llamar directamente

3. **Configuración centralizada**
   - Nunca hardcodear valores
   - Usar `get_config()` para acceder a configuración

4. **Cada módulo debe ser testeable independientemente**
   - Usar mocks para dependencias
   - Tests sin base de datos ni servicios externos

---

## ⚡ Comandos Útiles

```bash
# Ejecutar aplicación
python run.py

# Ejecutar tests
python tests/test_architecture.py

# Ver configuración actual
python -c "from src.infrastructure.config import get_config; print(get_config().to_dict())"

# Verificar estructura de módulos
python -c "import src; print('✅ Estructura correcta')"
```

---

## 🐛 Troubleshooting

### Error: "No module named 'src'"

Ejecuta desde el directorio raíz `SGUBM-V1/`:

```bash
cd c:\SGUBM-V1
python run.py
```

### Error: "Configuration errors"

Verifica que `config/.env` existe y tiene valores válidos:

```bash
# Verificar
type config\.env
```

---

## 📞 Soporte

La arquitectura modular está diseñada para ser autoexplicativa:

- Revisa `ARCHITECTURE.md` para entender los principios
- Revisa `PROJECT_STRUCTURE.md` para entender la organización
- Ejecuta `tests/test_architecture.py` para verificar integridad

¡La aplicación está lista para empezar a desarrollar módulos! 🚀
