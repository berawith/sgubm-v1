# Estructura del Proyecto SGUBM-V1

```
SGUBM-V1/
│
├── 📄 README.md                    # Documentación principal
├── 📄 ARCHITECTURE.md              # Arquitectura modular hexagonal
├── 📄 requirements.txt             # Dependencias
├── 📄 run.py                       # Punto de entrada
│
├── 📁 config/                      # Configuración
│   └── .env.example                # Variables de entorno
│
├── 📁 scripts/                     # Scripts de utilidad
│   └── 📁 maintenance/             # Scripts de mantenimiento, auditoría y diagnóstico
│
└── 📁 src/                         # Código fuente
    │
    ├── 📁 core/                    # NÚCLEO DEL SISTEMA (Sin dependencias)
    │   ├── domain/                 # Entidades y lógica de negocio
    │   │   └── entities.py         # Node, Client, Plan, Subscription...
    │   ├── interfaces/             # Contratos (abstracciones)
    │   │   └── contracts.py        # INetworkService, IRepository...
    │   └── exceptions/             # Excepciones del dominio
    │
    ├── 📁 application/             # CASOS DE USO
    │   ├── services/               # Servicios de aplicación
    │   │   ├── client_service.py
    │   │   ├── billing_service.py
    │   │   └── provisioning_service.py
    │   ├── dto/                    # Data Transfer Objects
    │   └── events/                 # Sistema de eventos
    │       └── event_bus.py        # Pub/Sub desacoplado
    │
    ├── 📁 infrastructure/          # IMPLEMENTACIONES CONCRETAS
    │   ├── database/               # Persistencia
    │   │   ├── repositories/
    │   │   └── models.py
    │   ├── mikrotik/               # Adaptador MikroTik
    │   │   └── adapter.py          # Implementa INetworkService
    │   ├── security/               # Autenticación
    │   └── config/                 # Configuración
    │       └── settings.py         # Configuración centralizada
    │
    └── 📁 presentation/            # CAPA DE PRESENTACIÓN
        ├── api/                    # Controladores REST
        └── web/                    # Frontend
            ├── static/             # CSS, JS, imágenes
            └── templates/          # HTML

```

## 🔑 Conceptos Clave

### 1. Flujo de Dependencias
```
Presentation  ──uses──>  Application  ──uses──>  Core
                                                    ▲
Infrastructure  ──implements──────────────────────┘
```

### 2. Comunicación Entre Módulos
```
Módulo A ──publish──> Event Bus ──notify──> Módulo B
                                          └──> Módulo C
```

### 3. Inyección de Dependencias
```
Service(interface: INetworkService)
           ▲
           │ (inyección)
           │
    MikroTikAdapter (implementación)
```

## 🎯 Puntos de Extensión

| Componente | Archivo | Acción |
|------------|---------|--------|
| Nuevo adaptador de router | `infrastructure/[vendor]/adapter.py` | Implementa `INetworkService` |
| Nueva regla de negocio | `core/domain/entities.py` | Añadir método a entidad |
| Nuevo caso de uso | `application/services/` | Crear servicio con DI |
| Nuevo endpoint API | `presentation/api/` | Crear blueprint Flask |
| Nuevo evento del sistema | `application/events/event_bus.py` | Añadir a `SystemEvents` |

## 🚀 Inicio Rápido

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar entorno
cp config/.env.example config/.env
# Editar config/.env con tus valores

# 3. Ejecutar aplicación
python run.py
```

## 📦 Módulos Actuales

- ✅ **Core Domain**: Entidades de negocio
- ✅ **Interfaces**: Contratos entre capas
- ✅ **Event Bus**: Sistema de eventos
- ✅ **MikroTik Adapter**: Integración con RouterOS
- ✅ **Config System**: Configuración centralizada

## 🔜 Próximos Módulos

- ✅ **Database Repositories**: Persistencia SQL
- ✅ **API Controllers**: Endpoints REST
- ✅ **Authentication**: JWT + RBAC
- ✅ **Frontend**: UI moderna
- ✅ **Billing Engine**: Motor de facturación
- ✅ **Report Generator**: Reportes PDF/Excel
- ✅ **Notification Service**: Email/SMS/WhatsApp

## 📈 Escalabilidad

La arquitectura permite:
- Desplegar módulos en contenedores independientes
- Escalar horizontalmente por servicio
- Cambiar implementaciones sin tocar el core
- Agregar nuevos vendors (Cisco, Ubiquiti) sin modificar código existente
