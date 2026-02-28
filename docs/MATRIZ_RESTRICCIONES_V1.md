# Matriz de Restricciones - Rol: Cobrador (V1)

Este documento detalla los permisos restringidos para el rol de **Cobrador** en el sistema SGUBM-V1, con el fin de garantizar la integridad de los datos de los clientes y la seguridad de la infraestructura.

## Resumen de Restricciones

El rol de Cobrador está diseñado exclusivamente para la gestión de pagos y visualización de datos. Por política de seguridad, tiene prohibido realizar cambios estructurales o administrativos en el listado de clientes.

| Acción | Estado | Motivo |
| :--- | :--- | :--- |
| **Ver Clientes** | ✅ Permitido | Necesario para identificar al suscriptor. |
| **Editar Datos de Cliente** | ❌ Restringido | Evita cambios no autorizados en planes o información sensible. |
| **Activar / Suspender Cliente** | ❌ Restringido | Acción administrativa reservada para Admin/Socio. |
| **Eliminar Cliente** | ❌ Restringido | Riesgo de pérdida de histórico y desincronización MikroTik. |
| **Crear Nuevo Cliente** | ❌ Restringido | Los ingresos deben ser validados por administración/técnicos. |

## Detalles Técnicos (RBAC)

Las restricciones se aplican mediante el sistema de **Control de Acceso Basado en Roles (RBAC)** tanto en el Backend como en el Frontend.

- **Módulo:** `clients:list`
- **Permisos Específicos:**
    - `can_view`: `True`
    - `can_edit`: `False`
    - `can_delete`: `False`
    - `can_create`: `False`

## Histórico de Cambios

- **2026-02-27:** Implementación de restricciones estrictas y corrección de la lógica de verificación en la interfaz (`clients.js`).
