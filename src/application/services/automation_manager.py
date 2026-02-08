import threading
import time
import logging
from datetime import datetime
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
                
                # Snapshot de tráfico cada 10 minutos (600 seg) PARA HISTOGRAMAS REALES
                now_ts = time.time()
                if now_ts - self.last_traffic_snapshot > 600:
                    logger.info("📊 AutomationManager: Iniciando captura de snapshots de tráfico (Lectura de Bytes)...")
                    self._record_traffic_snapshots()
                    self.last_traffic_snapshot = now_ts
                    
            except Exception as e:
                logger.error(f"❌ AutomationManager: Error en bucle: {e}")
            
            # Dormir 1 minuto entre iteraciones
            # Las tareas internas controlan su propia frecuencia con timestamps
            for _ in range(6): 
                if self.stop_event.is_set(): break
                time.sleep(10) # 6 x 10s = 60s

    def _check_and_run_tasks(self):
        """Verifica qué tareas tocan ahora"""
        now = datetime.now()
        today = now.date()
        
        # 1. Ciclo de Facturación (Una vez al día)
        if self.last_check_date != today:
            logger.info(f"📅 AutomationManager: Detectado cambio de día ({today}). Ejecutando ciclo de facturación...")
            try:
                service = BillingService()
                # generate_monthly_invoices es idempotente
                service.generate_monthly_invoices()
                self.last_check_date = today
            except Exception as e:
                logger.error(f"Error ejecutando Facturación: {e}")

        # 2. Ciclo de Suspensiones (Soporta revisión horaria)
        # Ejecutar suspensiones cada hora para asegurar que el corte de las 5:00 PM sea efectivo
        try:
            # Solo loggear cada hora para evitar spam
            if now.minute == 0: 
                logger.info("⚡ AutomationManager: Ejecutando verificación horaria de suspensiones...")
                service = BillingService()
                service.process_suspensions()
        except Exception as e:
            logger.error(f"Error en verificación de suspensiones: {e}")

        # Aquí se pueden agregar otras tareas diarias o periódicas
        # como limpiezas de logs, backups, etc.

    def _record_traffic_snapshots(self):
        """Captura snapshots de tráfico de todos los clientes para el historial"""
        from src.infrastructure.database.db_manager import get_db
        from src.infrastructure.mikrotik.adapter import MikroTikAdapter
        from src.application.services.monitoring_manager import MonitoringManager
        
        try:
            db = get_db()
            router_repo = db.get_router_repository()
            client_repo = db.get_client_repository()
            traffic_repo = db.get_traffic_repository()
            
            manager = MonitoringManager.get_instance()
            routers = router_repo.get_all()
            
            for router in routers:
                # Solo procesar routers que estén marcados como online
                if router.status != 'online': continue
                
                adapter = MikroTikAdapter()
                try:
                    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port, timeout=5):
                        clients = client_repo.get_by_router(router.id)
                        client_ids = [c.id for c in clients]
                        
                        if not client_ids:
                            adapter.disconnect()
                            continue

                        # 1. Obtener velocidades actuales (bps)
                        traffic_bps = manager.get_router_clients_traffic(router.id, client_ids, adapter)
                        
                        # 2. Obtener contadores de bytes totales (Consumption)
                        # Mapeamos client_id -> username para el adapter
                        client_map = {c.id: c.username for c in clients}
                        traffic_bytes = adapter.get_bulk_interface_stats(list(client_map.values()))
                        
                        # 3. Quality Pulse (Ping Test para clientes online o con IP)
                        # Solo ping a quienes tienen IP detectada
                        pulse_targets = []
                        ip_to_client = {}
                        
                        for client in clients:
                            cid = client.id
                            info_bps = traffic_bps.get(str(cid), {})
                            # Prioridad: IP reportada por monitor -> IP en DB
                            target_ip = info_bps.get('ip') or client.ip_address
                            
                            # Validar que sea IP válida (no red/mascara) y no vacía
                            if target_ip and '/' not in target_ip:
                                pulse_targets.append(target_ip)
                                ip_to_client[target_ip] = cid

                        pulse_results = {}
                        if pulse_targets:
                            # Hacer ping en batch (limitado por el adapter a 50)
                            pulse_results = adapter.ping_bulk(pulse_targets, count=2)

                        for client in clients:
                            cid = client.id
                            user = client.username
                            
                            info_bps = traffic_bps.get(str(cid), {})
                            info_bytes = traffic_bytes.get(user, {})
                            
                            target_ip = info_bps.get('ip') or client.ip_address
                            quality_data = {'latency': 0, 'loss': 0, 'status': 'unknown'}
                            
                            if target_ip and target_ip in pulse_results:
                                quality_data = pulse_results[target_ip]
                            
                            # Si falló el ping pero tenía tráfico, asumimos online pero con 100% loss (extraño)
                            # Mejor: Si traffic_monitor dice online, es online. El ping es calidad.
                            is_online_traffic = info_bps.get('status') == 'online'
                            
                            # Calcular Quality Score (0-100)
                            # Base 100. Resta % loss. Resta 1 pto por cada 10ms > 20ms
                            q_score = 100.0
                            if quality_data['loss'] > 0:
                                q_score -= quality_data['loss']
                            
                            lat = quality_data['latency']
                            if lat > 20:
                                penalty = (lat - 20) / 5 # 1 pto por cada 5ms extra
                                q_score -= penalty
                            
                            if not is_online_traffic and quality_data['status'] != 'online':
                                q_score = 0
                            
                            q_score = max(0, min(100, q_score))

                            # Grabamos el snapshot con toda la info disponible
                            traffic_repo.add_snapshot({
                                'client_id': cid,
                                'download_bps': float(info_bps.get('download', 0)),
                                'upload_bps': float(info_bps.get('upload', 0)),
                                'download_bytes': float(info_bytes.get('tx_bytes', 0)), 
                                'upload_bytes': float(info_bytes.get('rx_bytes', 0)),
                                'is_online': is_online_traffic,
                                'latency_ms': lat,
                                'packet_loss_pct': quality_data['loss'],
                                'quality_score': round(q_score, 1),
                                'timestamp': datetime.utcnow()
                            })
                        adapter.disconnect()
                except Exception as e:
                    logger.error(f"Error recording traffic for router {router.alias}: {e}")
            
            # Limpiar historial viejo de vez en cuando (una vez al día)
            # if datetime.now().hour == 3 and datetime.now().minute < 30:
            #     traffic_repo.delete_old_history(days=30)
                
        except Exception as e:
            logger.error(f"Critical error in _record_traffic_snapshots: {e}")
        finally:
             if 'db' in locals():
                 db.remove_session()
