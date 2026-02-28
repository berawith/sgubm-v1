import threading
import time
import logging
from datetime import datetime, timedelta
from src.application.services.billing_service import BillingService

logger = logging.getLogger(__name__)

class AutomationManager:
    """
    Manager para tareas automáticas en segundo plano.
    Maneja el ciclo de facturacion y cortes.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None
        self.last_check_date = None
        self.last_traffic_snapshot = 0 # Timestamp
        self.last_integrity_check = 0 # Timestamp


    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = AutomationManager()
            return cls._instance

    def start(self):
        """Inicia el hilo de automatización"""
        if self.thread and self.thread.is_alive():
            return
            
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="AutomationThread")
        self.thread.start()
        logger.info("🚀 AutomationManager: Thread de tareas automáticas iniciado.")

    def stop(self):
        """Detiene el hilo"""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)

    def _run_loop(self):
        """Bucle principal de ejecución"""
        # Esperar un poco a que el sistema esté totalmente arriba
        time.sleep(10)
        
        while not self.stop_event.is_set():
            try:
                self._check_and_run_tasks()
                
                # Snapshot de tráfico cada 20 minutos (1200 seg) PARA HISTOGRAMAS REALES
                now_ts = time.time()
                if now_ts - self.last_traffic_snapshot > 1200:
                    logger.info("📊 AutomationManager: Iniciando captura de snapshots de tráfico (Lectura de Bytes)...")
                    self._record_traffic_snapshots()
                    self.last_traffic_snapshot = now_ts
                
                # Integridad cada 6 horas (21600 seg)
                if now_ts - self.last_integrity_check > 21600:
                    logger.info("🛡️ AutomationManager: Ejecutando auditoría de integridad de datos...")
                    self._run_integrity_checks()
                    self.last_integrity_check = now_ts
                    
            except Exception as e:
                logger.error(f"❌ AutomationManager: Error en bucle: {e}")
            
            # Dormir 1 minuto entre iteraciones
            # Las tareas internas controlan su propia frecuencia con timestamps
            for _ in range(6): 
                if self.stop_event.is_set(): break
                time.sleep(10) # 6 x 10s = 60s

    def _check_and_run_tasks(self):
        """Verifica qué tareas tocan ahora para CADA TENANT"""
        from src.infrastructure.database.db_manager import get_db
        from src.infrastructure.database.models import Tenant
        
        db = get_db()
        try:
            # Obtener todos los tenants activos
            tenants = db.session.query(Tenant).filter(Tenant.is_active == 1).all()
            
            now = datetime.now()
            today = now.date()
            
            for tenant in tenants:
                # REPLACED: Contexto manual por tenant_id
                # En FastAPI manejamos el tenant_id explícitamente en el servicio si es necesario
                service = BillingService()
                
                # 1. Ciclo de Facturación (Aprobación Requerida el Día 1)
                if today.day == 1 and self.last_check_date != today:
                    logger.info(f"📅 AutomationManager [{tenant.name}]: Día 1 detectado. Solicitando aprobación de ciclo...")
                    service.request_cycle_approval(tenant.id, today.year, today.month)

                # 2. Verificar Notificaciones Pendientes (Recordatorios Horarios)
                self._process_notification_reminders(db, tenant.id)

                # 3. Ciclo de Suspensiones (Horario)
                try:
                    if now.minute == 0: 
                        logger.info(f"⚡ AutomationManager [{tenant.name}]: Verificación horaria de suspensiones...")
                        # Aseguramos que el servicio sepa para qué tenant es
                        service.process_suspensions(tenant_id=tenant.id)
                except Exception as e:
                    logger.error(f"Error suspendiendo tenant {tenant.name}: {e}")
            
            # Tareas Globales
            if self.last_check_date != today:
                try:
                    logger.info("🧹 AutomationManager: Ejecutando limpieza global de historial...")
                    self._clean_traffic_history()
                    self.last_check_date = today
                except Exception as e:
                    logger.error(f"Error limpieza global: {e}")

        except Exception as e:
            logger.error(f"Error crítico en _check_and_run_tasks: {e}")
        finally:
            if 'db' in locals():
                db.remove_session()

    def _process_notification_reminders(self, db, tenant_id):
        """Busca notificaciones de aprobación pendientes y maneja recordatorios"""
        from src.infrastructure.database.models import SystemNotification
        
        now = datetime.now()
        pending = db.session.query(SystemNotification).filter(
            SystemNotification.tenant_id == tenant_id,
            SystemNotification.status == 'pending',
            SystemNotification.type == 'approval_required',
            SystemNotification.remind_at <= now
        ).all()
        
        for notif in pending:
            # En un sistema real aquí enviaríamos un WebSocket push o Telegram/WhatsApp
            # Por ahora, registramos en log y actualizamos remind_at para la siguiente hora
            logger.info(f"🔔 RECORDATORIO: {notif.title} para tenant {tenant_id}. Mensaje: {notif.message}")
            
            # Programar siguiente recordatorio en 1 hora
            notif.remind_at = now + timedelta(hours=1)
            
        db.session.commit()

    def _record_traffic_snapshots(self):
        """Captura snapshots de tráfico de todos los clientes para el historial"""
        from src.infrastructure.database.db_manager import get_db
        from src.infrastructure.mikrotik.adapter import MikroTikAdapter
        from src.application.services.monitoring_manager import MonitoringManager
        
        from concurrent.futures import ThreadPoolExecutor
        
        try:
            db = get_db()
            router_repo = db.get_router_repository()
            routers = router_repo.get_all()
            online_routers = [r for r in routers if r.status == 'online']
            
            if not online_routers:
                return

            def process_router(router):
                from src.infrastructure.database.db_manager import get_db as get_local_db
                local_db = get_local_db()
                
                try:
                    # tenant_id = router.tenant_id
                    client_repo = local_db.get_client_repository()
                    traffic_repo = local_db.get_traffic_repository()
                    manager = MonitoringManager.get_instance()
                    
                    adapter = MikroTikAdapter()
                    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=5):
                        clients = client_repo.get_by_router(router.id)
                        client_ids = [c.id for c in clients]
                        
                        if not client_ids:
                            adapter.disconnect()
                            return
                        
                        # 1. Obtener velocidades actuales (bps)
                        traffic_bps = manager.get_router_clients_traffic(router.id, client_ids, adapter)
                        
                        # 2. Obtener contadores de bytes totales (resiliente)
                        client_map = {c.id: c.username for c in clients}
                        traffic_bytes = {}
                        try:
                            traffic_bytes = adapter.get_bulk_interface_stats(list(client_map.values()))
                        except Exception as e_stats:
                            logger.warning(f"get_bulk_interface_stats failed for {router.alias}: {e_stats}")
                        
                        # 3. Quality Pulse (Ping Test - resiliente)
                        pulse_targets = []
                        for client in clients:
                            info_bps = traffic_bps.get(str(client.id), {})
                            target_ip = info_bps.get('ip') or client.ip_address
                            if target_ip and '/' not in target_ip:
                                pulse_targets.append(target_ip)

                        pulse_results = {}
                        if pulse_targets:
                            try:
                                pulse_results = adapter.ping_bulk(pulse_targets, count=5) # 5 muestras para jitter real
                            except Exception as e_ping:
                                logger.warning(f"ping_bulk failed for {router.alias}: {e_ping}")

                        for client in clients:
                            cid = client.id
                            user = client.username
                            # TrafficSurgicalEngine usa enteros como llaves, no strings.
                            info_bps = traffic_bps.get(cid, {})
                            info_bytes = traffic_bytes.get(user, {})
                            target_ip = info_bps.get('ip') or client.ip_address
                            
                            # Datos base del ping (Default: Marcar como no medido/error)
                            # Si no está en pulse_results, es que se saltó o falló.
                            quality_data = pulse_results.get(target_ip, {
                                'latency': -1, # Indicador de N/A en DB
                                'loss': 100, 
                                'status': 'skipped', 
                                'jitter': 0
                            })
                            
                            is_online_traffic = (info_bps.get('status') == 'online')
                            
                            # --- ANALYTICAL LINK HEALTH INDEX (LHI) ---
                            lhi = 100.0
                            lat = quality_data['latency']
                            loss = quality_data['loss']
                            jitter = quality_data.get('jitter', 0)
                            
                            if lat == -1:
                                # No se pudo medir. Si está por tráfico, le damos un lhi base de 50 (Incierto)
                                lhi = 50.0 if is_online_traffic else 0
                            else:
                                # 1. Penalización No-Lineal por Pérdida de Paquetes (Crítico)
                                lhi -= (loss * 10)
                                
                                # 2. Penalización Progresiva por Latencia
                                if lat > 30:
                                    if lat <= 100:
                                        lhi -= (lat - 30) / 4
                                    else:
                                        lhi -= 17.5 + ((lat - 100) / 2)
                                
                                # 3. Penalización por Inestabilidad (Jitter)
                                if jitter > 5:
                                    lhi -= (jitter - 5) * 1.5
                            
                            # 4. Verificación de Estado
                            if not is_online_traffic and quality_data['status'] not in ['online', 'skipped']:
                                lhi = 0
                                
                            lhi = max(0, min(100, lhi))

                            traffic_repo.add_snapshot({
                                'client_id': cid,
                                'download_bps': float(info_bps.get('download', 0)),
                                'upload_bps': float(info_bps.get('upload', 0)),
                                'download_bytes': float(info_bytes.get('tx_bytes', 0)), 
                                'upload_bytes': float(info_bytes.get('rx_bytes', 0)),
                                'is_online': is_online_traffic,
                                'latency_ms': lat,
                                'packet_loss_pct': loss,
                                'jitter_ms': jitter,
                                'quality_score': round(lhi, 1),
                                'timestamp': datetime.now()
                            })

                            # Actualizar estado is_online en el objeto cliente para el Dashboard
                            if client.is_online != is_online_traffic:
                                client.is_online = is_online_traffic
                                client.last_seen = datetime.now() if is_online_traffic else client.last_seen
                        
                        local_db.session.commit()
                        adapter.disconnect()
                except Exception as e_proc:
                    logger.error(f"Error processing router {router.alias}: {e_proc}")
                finally:
                    local_db.remove_session()

            # Execute in parallel
            with ThreadPoolExecutor(max_workers=5) as executor:
                executor.map(process_router, online_routers)
                
        except Exception as e:
            logger.error(f"Critical error in _record_traffic_snapshots: {e}")
        finally:
             if 'db' in locals():
                 db.remove_session()

    def _clean_traffic_history(self):
        """Limpia el historial de tráfico antiguo para mantener la BD ligera"""
        from src.infrastructure.database.db_manager import get_db
        try:
            db = get_db()
            traffic_repo = db.get_traffic_repository()
            # Mantener 30 días con intervalo de 20 min es razonable (~50MB con 1000 clientes)
            traffic_repo.delete_old_history(days=30)
            logger.info("✅ Historial de tráfico antiguo eliminado correctamente")
        except Exception as e:
            logger.error(f"Error al limpiar historial: {e}")
        finally:
            if 'db' in locals():
                db.remove_session()

    def _run_integrity_checks(self):
        """Ejecuta auditorías de consistencia y registro de anomalías"""
        from src.infrastructure.database.db_manager import get_db
        from src.infrastructure.database.models import Payment, Client
        from sqlalchemy import func
        
        try:
            db = get_db()
            session = db.session
            
            # 1. Detectar Pagos Duplicados (Referencias)
            dup_refs = session.query(Payment.reference).filter(
                Payment.reference != '', Payment.reference != None
            ).group_by(Payment.reference).having(func.count(Payment.id) > 1).all()
            
            if dup_refs:
                logger.warning(f"⚠️ Auditoría: Detectadas {len(dup_refs)} referencias de pago duplicadas.")
                
            # 2. Detectar Inconsistencias Balance vs Status
            # Clientes ACTIVOS con balance POSITIVO (>0 significa deuda en este sistema)
            # Nota: En SGUBM, balance > 0 es deuda, balance <= 0 es al día.
            mismatched = session.query(Client).filter(
                Client.account_balance > 0,
                Client.status == 'active'
            ).count()
            
            if mismatched > 0:
                logger.warning(f"⚠️ Auditoría: Detectados {mismatched} clientes activos con deuda pendiente.")
                
            # 3. Detectar IPs duplicadas activas
            dup_ips = session.query(Client.ip_address).filter(
                Client.status == 'active'
            ).group_by(Client.ip_address).having(func.count(Client.id) > 1).all()
            
            if dup_ips:
                logger.warning(f"⚠️ Auditoría: Detectadas {len(dup_ips)} IPs duplicadas en clientes activos.")

        except Exception as e:
            logger.error(f"Error en _run_integrity_checks: {e}")
        finally:
            if 'db' in locals():
                db.remove_session()
