# SGUBM-V1 - Sistema de Gestión Unificado para ISP

## Arquitectura Modular Hexagonal

```
┌─────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                       │
│  (API REST, WebSockets, Static Files)                       │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                   APPLICATION LAYER                          │
│  (Use Cases, Business Logic, Orchestration)                 │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                     DOMAIN LAYER                             │
│  (Entities, Value Objects, Business Rules)                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                 INFRASTRUCTURE LAYER                         │
│  (Database, MikroTik API, External Services)                │
└─────────────────────────────────────────────────────────────┘
```

## Principios de Diseño

1. **Separation of Concerns**: Cada módulo tiene una sola responsabilidad
2. **Dependency Inversion**: Las capas superiores NO dependen de las inferiores
3. **Open/Closed**: Abierto a extensión, cerrado a modificación
4. **Interface Segregation**: Interfaces pequeñas y específicas
5. **DRY**: Sin repetición de código

## Estructura de Directorios

```
SGUBM-V1/
├── src/
│   ├── core/                      # Núcleo del sistema
│   │   ├── domain/               # Entidades y reglas de negocio
│   │   ├── interfaces/           # Contratos (abstracciones)
│   │   └── exceptions/           # Excepciones del dominio
│   ├── application/              # Casos de uso
│   │   ├── services/            # Servicios de aplicación
│   │   ├── dto/                 # Data Transfer Objects
│   │   └── events/              # Event Bus
│   ├── infrastructure/           # Implementaciones concretas
│   │   ├── database/            # Repositorios SQL
│   │   ├── mikrotik/            # Adaptador MikroTik
│   │   ├── security/            # Autenticación/Autorización
│   │   └── config/              # Configuración
│   └── presentation/             # Capa de presentación
│       ├── api/                 # Controladores REST
│       └── web/                 # Archivos estáticos
├── tests/                        # Tests unitarios e integración
├── migrations/                   # Migraciones de BD
└── config/                       # Configuración por ambiente
```

## Instalación

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp config/.env.example config/.env

# Ejecutar migraciones
python manage.py db upgrade

# Iniciar aplicación
python run.py
```

## Módulos Independientes

Cada módulo puede funcionar de forma autónoma. Ejemplo:

```python
# El módulo de facturación NO conoce la implementación de MikroTik
# Solo conoce la interfaz INetworkService

from core.interfaces import INetworkService

class BillingService:
    def __init__(self, network_service: INetworkService):
        self.network = network_service
    
    def suspend_client(self, client_id):
        # La implementación real puede ser MikroTik, Cisco, etc.
        self.network.disable_service(client_id)
```

## Tecnologías

- **Backend**: Python 3.11+ / Flask
- **ORM**: SQLAlchemy 2.0
- **Database**: PostgreSQL / SQLite
- **API**: RESTful + WebSockets
- **Frontend**: Vanilla JS (ES6+) con componentes modulares
- **MikroTik**: RouterOS API
- **Testing**: pytest
