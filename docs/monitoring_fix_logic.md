# Explicación Técnica: Reparación del Sistema de Monitoreo

Este documento detalla los cambios realizados en el código para resolver el problema de los clientes que aparecían como "Offline" y con 0 de tráfico.

## 1. Cambios en `src/infrastructure/mikrotik/adapter.py`

Se modificó el método `get_bulk_traffic` para ser más flexible en la búsqueda de estadísticas.

```python
# NUEVO: Tabla de búsqueda por IP para Colas Simples
queue_by_ip = {}
for q in all_queues:
    target = q.get('target', '')
    if target:
        # Extraemos la IP del target (ej: "177.77.73.50/32" -> "177.77.73.50")
        q_ip = target.split('/')[0].strip()
        if q_ip:
            queue_by_ip[q_ip] = q
```
*   **¿Qué hace?**: Crea un diccionario que permite encontrar una cola de MikroTik usando solo la dirección IP del cliente.
*   **¿Por qué?**: Si la cola se llama "Zulay Ruiz" pero el sistema la busca como "zulay_ruiz" (username), fallaría. Con este cambio, si el nombre no coincide, el sistema usa la IP como "llave maestra".

```python
elif target in queue_by_ip:
    # Fallback por IP si el nombre no coincide
    q_data = queue_by_ip[target]
```
*   **¿Qué hace?**: Si los patrones de nombre fallan, intenta buscar el `target` (que puede ser una IP) en el nuevo mapa de IPs.

---

## 2. Cambios en `src/application/services/monitoring_manager.py`

Se mejoró la lógica central que decide si un cliente está online y recolecta su tráfico.

### Caché de Metadatos
```python
self.client_metadata_cache[c.id] = {
    'username': c.username,
    'legal_name': c.legal_name, # <-- Se agregó este campo
    'ip': c.ip_address,
    ...
}
```
*   **¿Qué hace?**: Ahora el sistema recuerda el "Nombre Legal" del cliente además de su "Username".
*   **¿Por qué?**: Permite buscar colas en MikroTik que usen el nombre real de la persona.

### Lógica de Detección (Online/Offline)
```python
# Probar Username, Legal Name o IP
q = queue_map.get(user_lower) or queue_map.get(legal_lower) or queue_by_ip.get(c_ip)
```
*   **¿Qué hace?**: Intenta encontrar la cola del cliente usando tres métodos en orden:
    1.  Username (minúsculas)
    2.  Nombre Legal (minúsculas)
    3.  Dirección IP
*   **¿Por qué?**: Garantiza que, sin importar cómo se haya nombrado la cola en Winbox, el sistema pueda asociarla al cliente correcto.

### Telemetría y Robustez
```python
c_ip = meta['ip'].strip() if meta['ip'] else None
```
*   **¿Qué hace?**: Limpia cualquier espacio en blanco accidental en la IP de la base de datos antes de comparar.

```python
logger.info(f"Monitor {router_id}: {online_count}/{len(client_ids)} clients online...")
```
*   **¿Qué hace?**: Imprime en la consola del servidor un resumen cada ciclo de monitoreo.
*   **¿Por qué?**: Permite al administrador verificar de un vistazo que el sistema está funcionando ("207/225 online").

---

## Resumen del Flujo Corregido

1.  El sistema consulta la tabla ARP del router (ve quién tiene "pulso" eléctrico en la red).
2.  Cruza esa información con la base de datos limpiando las IPs.
3.  Si hay coincidencia de IP, busca la "Simple Queue" usando el Nombre Legal como fallback.
4.  Si encuentra la cola, extrae el campo `rate` (bps actuales) y lo envía al Dashboard vía WebSockets.
