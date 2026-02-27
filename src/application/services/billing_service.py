import logging
import calendar
from datetime import datetime, timedelta
from sqlalchemy import extract, and_
from sqlalchemy.orm import joinedload
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Invoice, InvoiceItem, InternetPlan, PaymentPromise, Router
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.application.services.audit_service import AuditService
from src.application.services.mikrotik_operations import safe_suspend_client
from src.domain.services.tax_engine import TaxEngine
from src.domain.services.currency_service import CurrencyService

logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self):
        pass

    def process_daily_cycle(self, router_id=None, client_ids=None, year=None, month=None):
        """
        Ejecuta todas las tareas diarias de facturación y cortes.
        Invocado por el AutomationManager o manualmente.
        """
        logger.info(f"📅 BillingService: Iniciando ciclo {'filtrado' if router_id or client_ids else 'diario'}...")
        
        # 2. Aplicar Prorrateo Dinámico (Día 16+)
        self.apply_daily_prorating(router_id=router_id, client_ids=client_ids)
        
        # 3. Procesar Suspensiones por falta de pago
        self.process_suspensions(router_id=router_id, client_ids=client_ids)
        
        return True

    def generate_monthly_invoices(self, year=None, month=None, router_id=None, client_ids=None):
        """
        Generar facturas masivas para todos los clientes activos.
        Vencimiento: Basado en la configuración del Router (billing_day + grace_period).
        """
        db = get_db()
        session = db.session
        
        now = datetime.now()
        target_year = year or now.year
        target_month = month or now.month
        
        # Fecha de emisión base (Día 1 del mes objetivo)
        issue_date_base = datetime(target_year, target_month, 1)
        
        logger.info(f"📊 Iniciando Facturación Masiva: {target_year}-{target_month}")
        
        try:
            # 0. Precargar configuraciones de todos los routers para evitar N+1 queries
            routers = session.query(Router).all()
            router_configs = {
                r.id: {
                    'billing_day': r.billing_day or 1,
                    'grace_period': r.grace_period or 5,
                    'cut_day': r.cut_day or 5,
                    'non_cumulative_debt': False # Default, could be extended from router model
                } for r in routers
            }

            # 1. Obtener clientes activos o suspendidos
            # OPTIMIZACIÓN: Eager loading de InternetPlan para evitar N+1
            query = session.query(Client).options(joinedload(Client.internet_plan)).filter(
                Client.status.in_(['active', 'suspended'])
            )
            
            if router_id:
                query = query.filter(Client.router_id == router_id)
            if client_ids:
                query = query.filter(Client.id.in_(client_ids))
                
            clients = query.all()

            # Pre-fetch facturas existentes del mes en una sola consulta
            existing_invoices_ids = set()
            existing_query = session.query(Invoice.client_id).filter(
                extract('year', Invoice.issue_date) == target_year,
                extract('month', Invoice.issue_date) == target_month
            )
            if router_id:
                existing_query = existing_query.join(Client).filter(Client.router_id == router_id)

            existing_invoices_ids = {row[0] for row in existing_query.all()}
            
            created_count = 0
            skipped_count = 0
            errors_count = 0
            
            # 1.4. Datos ERP (Moneda y Tasa) - Cargar una vez fuera del bucle
            settings_repo = db.get_system_setting_repository()
            currency_service = CurrencyService(settings_repo)

            erp_currency = settings_repo.get_value('ERP_REPORTING_CURRENCY', 'COP') # Moneda de facturación
            base_currency = settings_repo.get_value('ERP_BASE_CURRENCY', 'USD')

            # Tasa en el momento de la facturación
            erp_rate = currency_service.get_rate(erp_currency, base_currency)

            for client in clients:
                try:
                    # Verificar si ya tiene factura este mes (en memoria)
                    if client.id in existing_invoices_ids:
                        skipped_count += 1
                        continue
                    
                    # Determinar configuración de vencimiento según el Router (en memoria)
                    config = router_configs.get(client.router_id, {'billing_day': 1, 'grace_period': 5, 'cut_day': 5})
                    billing_day = config['billing_day']
                    grace_period = config['grace_period']
                    
                    # Fecha de emisión real (Día configurado en el router)
                    # Nota: Si el billing_day es 0 o > 28, simplificamos a 1 para evitar errores de calendario
                    try:
                        issue_date = datetime(target_year, target_month, billing_day)
                    except ValueError:
                        issue_date = datetime(target_year, target_month, 1)
                        
                    # Vencimiento: Usamos cut_day si está definido (ej. del 1 al 5), sino grace_period
                    cut_day = config.get('cut_day')
                    if cut_day and cut_day > 0:
                        try:
                            due_date = datetime(target_year, target_month, cut_day)
                            # Si el día de corte es anterior o igual al de cobro, asumimos el mes siguiente
                            # (A menos que el usuario explícitamente quiera cobrar y cortar el mismo día/mes)
                            if due_date <= issue_date:
                                if target_month == 12:
                                    due_date = datetime(target_year + 1, 1, cut_day)
                                else:
                                    due_date = datetime(target_year, target_month + 1, cut_day)
                        except ValueError:
                            due_date = issue_date + timedelta(days=grace_period)
                    else:
                        due_date = issue_date + timedelta(days=grace_period)
                        
                    due_date = due_date.replace(hour=17, minute=0, second=0)
                    
                    # Determinar precio
                    # OPTIMIZACIÓN: Usar la relación eager loaded
                    amount = client.monthly_fee or 0.0
                    plan_name = f"Plan Internet: {client.plan_name or 'Básico'}"
                    
                    if client.internet_plan:
                         amount = client.internet_plan.monthly_price
                         plan_name = f"Plan Internet: {client.internet_plan.name}"
                    
                    if amount <= 0:
                        logger.warning(f"⚠️ Cliente {client.legal_name} ({client.id}) tiene costo 0. Saltando.")
                        errors_count += 1
                        continue
                        
                    base_amount = amount * erp_rate

                    # Crear Factura
                    new_invoice = Invoice(
                        client_id=client.id,
                        issue_date=issue_date,
                        due_date=due_date,
                        total_amount=amount,
                        currency=erp_currency,
                        exchange_rate=erp_rate,
                        subtotal_amount=amount, # Simplificación: subtotal = total si no hay IVA explícito aquí
                        base_amount=base_amount,
                        status='unpaid'
                    )
                    session.add(new_invoice)
                    session.flush()
                    
                    # Crear Item
                    item = InvoiceItem(
                        invoice_id=new_invoice.id,
                        description=f"{plan_name} - {issue_date.strftime('%B %Y')}",
                        amount=amount
                    )
                    session.add(item)
                    
                    # --- Regla de Deuda: ERP Avanzado (Requerimiento de Prorrateo/Reset) ---
                    # 1. Resetear cuenta vieja para cortados (suspended)
                    # 2. Sumar anterior + actual solo si hay promesa de pago activa
                    
                    has_promise = client.promise_date is not None and client.promise_date >= now
                    is_suspended = client.status == 'suspended'
                    
                    old_balance = current_balance
                    
                    if has_promise:
                        # Si tiene promesa, la deuda es acumulativa (Anterior + Nueva)
                        client.account_balance = current_balance + amount
                        operation_type = "accumulated_with_promise"
                    elif is_suspended or config.get('non_cumulative_debt'):
                        # "Borrón y cuenta nueva": Se ignora deuda anterior, empieza nuevo ciclo
                        client.account_balance = amount
                        operation_type = "reset_cycle"
                    else:
                        # Caso base (Activos sin deuda configurada como no-acumulativa)
                        client.account_balance = current_balance + amount
                        operation_type = "accumulated"
                    
                    client.due_date = due_date
                    
                    # Registrar ajuste en Auditoría (Kardex)
                    if operation_type == "reset_cycle" and old_balance > 0:
                        AuditService.log(
                            operation='balance_reset_cycle',
                            category='accounting',
                            entity_type='client',
                            entity_id=client.id,
                            description=f"Balance reiniciado por nuevo ciclo (No acumulativo). Deuda anterior ${old_balance} ignorada para balance activo.",
                            previous_state={'balance': old_balance},
                            new_state={'balance': client.account_balance}
                        )
                    
                    created_count += 1
                    
                except Exception as e_inner:
                    logger.error(f"❌ Error facturando cliente {client.id}: {e_inner}")
                    errors_count += 1
            
            session.commit()
            summary = {'created': created_count, 'skipped': skipped_count, 'errors': errors_count}
            logger.info(f"✅ Facturación completada: {summary}")
            
            # Registrar en Auditoría
            AuditService.log(
                operation='mass_invoicing',
                category='accounting',
                description=f"Generación masiva de facturas para {target_month}/{target_year}. Creadas: {created_count}, Saltadas: {skipped_count}, Errores: {errors_count}"
            )
            
            return summary
            
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Error crítico en facturación: {e}")
            raise e

    def apply_daily_prorating(self, router_id=None, client_ids=None, force=False):
        """
        Aplica descuentos automáticos (Prorrateo) después del día configurado.
        'force' permite ignorar la validación de día si se requiere aplicación manual.
        """
        db = get_db()
        session = db.session
        now = datetime.now()
        
        settings_repo = db.get_system_setting_repository()
        enabled = settings_repo.get_value('PRORATING_ENABLED', 'true').lower() == 'true'
        start_day = int(settings_repo.get_value('PRORATING_START_DAY', 15))
        
        # Si no está forzado, validamos el día de inicio
        if not force:
            if not enabled or now.day <= start_day:
                return 0
            
        logger.info(f"⚖️ BillingService: Aplicando Prorrateo Dinámico (Día {now.day}, force={force})...")
        
        try:
            # 1. Obtener facturas impagas del mes actual
            query = session.query(Invoice).filter(
                Invoice.status == 'unpaid',
                extract('year', Invoice.issue_date) == now.year,
                extract('month', Invoice.issue_date) == now.month
            )
            
            if router_id or client_ids:
                query = query.join(Client)
                if router_id:
                    query = query.filter(Client.router_id == router_id)
                if client_ids:
                    query = query.filter(Client.id.in_(client_ids))
                    
            unpaid_invoices = query.all()
            
            _, days_in_month = calendar.monthrange(now.year, now.month)
            # Días restantes incluyendo hoy hasta el fin de mes
            days_remaining = days_in_month - now.day + 1
            
            updated_count = 0
            
            for inv in unpaid_invoices:
                client = inv.client
                if not client: continue
                
                # EXCEPCIÓN: Promesa de Pago activa
                if client.promise_date and client.promise_date >= now:
                    continue
                    
                # Obtener monto original desde el ítem de la factura
                # (Para evitar degradación si se corre varias veces el mismo día)
                original_amount = 0.0
                item = session.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv.id).first()
                if item:
                    original_amount = item.amount
                else:
                    original_amount = client.monthly_fee or inv.total_amount
                
                if original_amount <= 0: continue
                
                # Calcular nuevo monto prorrateado (Basado en regla: cuenta desde día 5 en adelante)
                # Si el mes tiene 30 días, el denominador es 25 (30 - 5)
                import math
                denominator = days_in_month - 5
                new_amount = math.ceil((original_amount * days_remaining) / denominator)
                
                # Solo aplicar si el nuevo monto es menor al actual (para evitar subir precios)
                if new_amount < inv.total_amount:
                    diff = inv.total_amount - new_amount
                    inv.total_amount = new_amount
                    
                    # El balance del cliente también debe bajar por la diferencia
                    client.account_balance = (client.account_balance or 0) - diff
                    updated_count += 1
            
            session.commit()
            if updated_count > 0:
                logger.info(f"✅ Prorrateo completado: {updated_count} facturas ajustadas.")
            return updated_count
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Error en prorrateo diario: {e}")

    def process_suspensions(self, router_id=None, client_ids=None):
        """
        Identifica clientes con deuda (invoices unpaid) pasada la fecha de vencimiento
        y ejecuta la suspensión automática en MikroTik.
        Respeta la 'Fecha de Promesa' del cliente.
        """
        from src.infrastructure.mikrotik.adapter import MikroTikAdapter
        db = get_db()
        session = db.session
        now = datetime.now()
        
        # --- Verificación de Congelación de Suspensiones ---
        try:
            from src.infrastructure.config.settings import get_config
            config = get_config()
            freeze_until_str = config.billing.suspension_freeze_until
            if freeze_until_str:
                freeze_until = datetime.fromisoformat(freeze_until_str)
                if now < freeze_until:
                    logger.info(f"❄️ BillingService: Suspensiones CONGELADAS hasta {freeze_until.strftime('%Y-%m-%d %H:%M:%S')}. Saltando proceso.")
                    return
        except Exception as e_freeze:
            logger.error(f"Error verificando freeze de suspensiones: {e_freeze}")

        logger.info("⚡ Iniciando proceso de suspensiones automáticas...")
        
        # 1. Obtener facturas vencidas de clientes que aún están 'active'
        query = session.query(Invoice).filter(
            Invoice.status == 'unpaid',
            Invoice.due_date <= now
        )
        
        if router_id or client_ids:
            query = query.join(Client)
            if router_id:
                query = query.filter(Client.router_id == router_id)
            if client_ids:
                query = query.filter(Client.id.in_(client_ids))
                
        overdue_invoices = query.all()
        
        # 2. PROCESAR CORTES (Optimizado con Bulk Suspend)
        client_ids_to_suspend = set([inv.client_id for inv in overdue_invoices])

        # Diccionario para agrupar clientes por router
        clients_by_router = {} # { router_id: [client_obj, ...] }

        skipped_promise_count = 0
        skipped_paid_count = 0
        
        # Fase 1: Filtrado y Agrupación (Sin IO de red)
        for client_id in client_ids_to_suspend:
            client = session.query(Client).get(client_id)
            if not client or client.status != 'active':
                continue
            
            # FILTRO CRÍTICO: Verificar Balance real (Problema 1 y 2)
            if (client.account_balance or 0) <= 0:
                logger.info(f"🛡️ BillingService: Saltando suspensión accidental de {client.legal_name}. Balance: {client.account_balance} (Ya pagó)")
                for inv in overdue_invoices:
                    if inv.client_id == client.id:
                        inv.status = 'paid'
                skipped_paid_count += 1
                continue

            # FILTRO: Promesa de Pago
            if client.promise_date and client.promise_date >= now:
                logger.info(f"🤝 Postponiendo suspensión de {client.legal_name} por PROMESA activa hasta {client.promise_date}")
                skipped_promise_count += 1
                continue
            
            # Gestión de Promesas Incumplidas
            if client.promise_date and client.promise_date < now:
                broken_promises = session.query(PaymentPromise).filter(
                    PaymentPromise.client_id == client.id,
                    PaymentPromise.status == 'pending'
                ).all()
                for bp in broken_promises:
                    bp.status = 'broken'
                    bp.notes = (bp.notes or "") + f" | Incumplida el {now.strftime('%Y-%m-%d')}"
                
                client.broken_promises_count = (client.broken_promises_count or 0) + 1
                logger.warning(f"💔 Promesa INCUMPLIDA por {client.legal_name}. Contador: {client.broken_promises_count}")
            
            # Agrupar para ejecución en lote
            if client.router_id:
                if client.router_id not in clients_by_router:
                    clients_by_router[client.router_id] = []
                clients_by_router[client.router_id].append(client)

        # Fase 2: Ejecución Masiva por Router (IO Optimizado)
        suspended_count = 0
        router_repo = db.get_router_repository()

        for r_id, clients_list in clients_by_router.items():
            router = router_repo.get_by_id(r_id)
            if not router: continue

            logger.info(f"🔌 Conectando a Router {router.alias} para suspender {len(clients_list)} clientes...")

            # Preparar datos para el adaptador
            clients_data = [c.to_dict() for c in clients_list]

            try:
                # Intento de conexión y bulk suspend
                adapter = MikroTikAdapter()
                if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):

                    results = adapter.bulk_suspend_clients(clients_data)
                    adapter.disconnect()

                    # Procesar resultados exitosos basado en IDs devueltos
                    successful_ids = set(results.get('successful_ids', []))

                    for client in clients_list:
                        if client.id in successful_ids:
                            # Éxito: Actualizar estado en BD
                            client.status = 'suspended'
                            suspended_count += 1

                            # Auditoría
                            AuditService.log(
                                operation='client_suspended',
                                category='client',
                                entity_type='client',
                                entity_id=client.id,
                                description=f"Suspensión automática (Bulk) por deuda: ${client.account_balance}",
                                previous_state={'status': 'active'},
                                new_state={'status': 'suspended'}
                            )
                        else:
                            # Fallo Individual: Encolar en SyncService
                            from src.application.services.sync_service import SyncService
                            sync = SyncService(db)
                            # Marcar como suspendido en BD para evitar reintentos infinitos en este ciclo,
                            # pero encolar la tarea técnica para que se reintente luego.
                            client.status = 'suspended'
                            sync.queue_operation(
                                operation_type='suspend',
                                client_id=client.id,
                                router_id=router.id,
                                ip_address=client.ip_address,
                                target_status='suspended',
                                commit=False
                            )
                            # Contamos como "procesado" (encolado) para el reporte
                            suspended_count += 1
                else:
                    raise Exception("Connection failed")

            except Exception as e:
                logger.error(f"❌ Falló suspensión masiva en Router {router.alias}: {e}")
                # Fallback: Encolar individualmente o marcar error
                # Por simplicidad en este paso, registramos error.
                # En producción idealmente se usaría SyncService.queue_operation por cada cliente fallido.
                from src.application.services.sync_service import SyncService
                sync = SyncService(db)
                for client in clients_list:
                    # Marcar como suspendido en BD para no reintentar infinitamente en el mismo ciclo
                    # pero encolar la tarea técnica
                    client.status = 'suspended'
                    sync.queue_operation(
                        operation_type='suspend',
                        client_id=client.id,
                        router_id=router.id,
                        ip_address=client.ip_address,
                        target_status='suspended',
                        commit=False
                    )
                    suspended_count += 1 # Contamos como procesado (encolado)

        # 3. PROCESAR RESTAURACIONES (Auto-fix para clientes que ya pagaron pero siguen cortados)
        restored_count = 0
        query_suspended = session.query(Client).filter(Client.status == 'suspended')
        if router_id:
            query_suspended = query_suspended.filter(Client.router_id == router_id)
        if client_ids:
            query_suspended = query_suspended.filter(Client.id.in_(client_ids))
            
        suspended_clients = query_suspended.all()
        for s_client in suspended_clients:
            # Si el balance es <= 0 y no tiene facturas unpaid vencidas, RESTAURAR
            if (s_client.account_balance or 0) <= 0:
                logger.info(f"✅ Restaurando servicio para {s_client.legal_name} (Balance {s_client.account_balance} <= 0)")
                from src.application.services.batch_service import BatchService
                BatchService()._restore_client(s_client)
                restored_count += 1
        
        session.commit()
        logger.info(f"✅ Proceso finalizado. Suspendidos: {suspended_count}, Restaurados: {restored_count}, Saltados (Promesa): {skipped_promise_count}, Saltados (Ya pagó): {skipped_paid_count}")
        return {
            'suspended': suspended_count,
            'restored': restored_count,
            'skipped_promise': skipped_promise_count,
            'skipped_paid': skipped_paid_count
        }

    def register_payment(self, client_id, amount, payment_data):
        """
        Registra un pago centralizadamente:
        1. Crea el registro de pago.
        2. Actualiza balance del cliente.
        3. Actualiza estatus de facturas (FIFO).
        4. Reactiva servicio si el balance llega a <= 0.
        """
        from src.infrastructure.database.models import Payment
        from src.application.services.batch_service import BatchService
        
        db = get_db()
        session = db.session
        
        client = session.query(Client).get(client_id)
        if not client:
            raise ValueError("Cliente no encontrado")

        # --- NUEVO: Aplicar Prorrateo SOLO SI se solicita en la transacción ---
        # User Feedback: "el monto real no debe variar solo que en el momento de realizar el pago se muestra el descuento"
        apply_prorating = payment_data.get('apply_prorating', False)
        
        if apply_prorating:
            try:
                # Forzamos aplicación de prorrateo para este pago específico
                self.apply_daily_prorating(client_ids=[client.id], force=True)
                session.refresh(client) # Refrescar para obtener el balance ajustado
                logger.info(f"🎁 Prorrateo aplicado exitosamente para el pago del cliente {client.id}")
            except Exception as e:
                logger.error(f"Error aplicando prorrateo en el pago para cliente {client_id}: {e}")

        # VALIDACIÓN: Pagos Incompletos (NUEVO REQUERIMIENTO)
        current_debt = client.account_balance or 0.0
        is_partial = (amount + 0.01) < current_debt # Margen de error para redondeo
        authorized = payment_data.get('authorized', False)
        allow_duplicate = payment_data.get('allow_duplicate', False)

        if is_partial and not authorized:
            # Lanzamos error específico para que el frontend pida autorización
            raise ValueError(f"PARTIAL_PAYMENT_REQUIRED|Monto ${amount} es menor a la deuda ${current_debt}. ¿Es un abono parcial o error de tipeo?")

        # VALIDACIÓN INTELIGENTE: Detectar Pagos Duplicados (Mismo cliente, mismo monto, últimos 10 min)
        if not allow_duplicate:
            ten_minutes_ago = datetime.now() - timedelta(minutes=10)
            recent_duplicate = session.query(Payment).filter(
                Payment.client_id == client.id,
                Payment.amount == amount,
                Payment.payment_date >= ten_minutes_ago
            ).first()

            if recent_duplicate:
                # Formatear hora para mostrar al usuario
                dup_time = recent_duplicate.payment_date.strftime("%I:%M %p")
                raise ValueError(f"DUPLICATE_PAYMENT|Se detectó un pago idéntico de ${amount} registrado hoy a las {dup_time}. ¿Desea registrarlo de nuevo?")

        # VALIDACIÓN: Problema 3 - Evitar pagos duplicados si no hay deuda
        unpaid_invoices = session.query(Invoice).filter(
            Invoice.client_id == client.id,
            Invoice.status == 'unpaid'
        ).count()
        
        if current_debt <= 0 and unpaid_invoices == 0:
            if not payment_data.get('is_overpayment', False):
                raise ValueError("El cliente ya está al día. No tiene saldo pendiente ni facturas por pagar.")

        # 1. Crear el pago
        payment_date = payment_data.get('payment_date')
        if isinstance(payment_date, str):
            try:
                # Handle ISO format or just date
                payment_date = datetime.fromisoformat(payment_date.replace('Z', '+00:00'))
            except:
                try:
                    payment_date = datetime.strptime(payment_date.split(' ')[0], '%Y-%m-%d')
                except:
                    payment_date = datetime.now()
        elif not payment_date:
            payment_date = datetime.now()

        # 1. Calcular Impuestos y Conversión de Moneda (ERP Logic)
        currency = payment_data.get('currency', 'COP')
        country = 'VEN' if currency.upper() in ['VES', 'USD'] else 'COL' # Heurística inicial
        
        tax_results = TaxEngine.calculate_taxes(amount, country, payment_data.get('payment_method', 'cash'), currency)
        
        # Obtener CurrencyService (necesita repo de settings)
        currency_service = CurrencyService(db.get_system_setting_repository())
        base_amount = currency_service.get_base_amount(amount, currency)
        exchange_rate = currency_service.get_rate(currency, db.get_system_setting_repository().get_value('ERP_BASE_CURRENCY', 'USD'))

        new_payment = Payment(
            client_id=client.id,
            amount=amount,
            currency=currency,
            base_amount=base_amount,
            exchange_rate=exchange_rate,
            tax_amount=tax_results['total_tax'],
            tax_details=TaxEngine.format_tax_details(tax_results),
            payment_date=payment_date,
            payment_method=payment_data.get('payment_method', 'cash'),
            reference=payment_data.get('reference', ''),
            notes=payment_data.get('notes', ''),
            status='verified'
        )
        
        # Calcular Hash de Integridad Final antes de persistir
        from src.domain.services.audit_service import AuditService as DomainAudit
        new_payment.transaction_hash = DomainAudit.calculate_transaction_hash('payment', new_payment.to_dict())
        
        session.add(new_payment)
        
        # 2. Actualizar balance y limpiar promesa
        client.account_balance = (client.account_balance or 0) - amount
        client.last_payment_date = new_payment.payment_date
        
        # Marcar promesas como CUMPLIDAS o INCUMPLIDAS según la fecha
        now = datetime.now()
        pending_promises = session.query(PaymentPromise).filter(
            PaymentPromise.client_id == client.id,
            PaymentPromise.status == 'pending'
        ).all()
        for pp in pending_promises:
            if now <= pp.promise_date:
                pp.status = 'fulfilled'
                pp.notes = (pp.notes or "") + f" | Pagada a tiempo el {now.strftime('%Y-%m-%d')}"
                # Resetear contador si cumple la promesa
                client.broken_promises_count = 0
            else:
                pp.status = 'broken'
                pp.notes = (pp.notes or "") + f" | Pagada FUERA DE PLAZO el {now.strftime('%Y-%m-%d')}"
                # Incrementar contador si paga fuera de plazo (era una promesa fallida)
                client.broken_promises_count = (client.broken_promises_count or 0) + 1
        
        client.promise_date = None  # Al pagar se extinguen los datos de la promesa actual
        
        # 3. Actualizar facturas (FIFO) e Identificar Diferencia en Cambio (FX Variance)
        invoices = session.query(Invoice).filter(
            Invoice.client_id == client.id,
            Invoice.status == 'unpaid'
        ).order_by(Invoice.issue_date).all()
        
        remaining = amount
        total_fx_variance = 0.0
        
        for inv in invoices:
            if remaining <= 0: break
            
            # Cantidad a aplicar a esta factura
            applied_amount = min(remaining, inv.total_amount)
            
            # Cálculo de Diferencia en Cambio (En moneda base, usualmente USD)
            # Comparamos cuánto valía ese monto al facturar vs cuánto vale al pagar
            historical_rate = inv.exchange_rate or 1.0 # Tasa al momento de la factura
            current_rate = new_payment.exchange_rate or 1.0 # Tasa al momento del pago
            
            # Monto en USD al facturar vs Monto en USD al cobrar
            historical_base = applied_amount * historical_rate
            current_base = applied_amount * current_rate
            
            # La varianza es la ganancia o pérdida por fluctuación
            # Variancia = (Valor Actual - Valor Histórico)
            invoice_variance = current_base - historical_base
            total_fx_variance += invoice_variance
            
            if remaining >= inv.total_amount:
                inv.status = 'paid'
                remaining -= inv.total_amount
            else:
                # Pago parcial
                remaining = 0
                break
                
        new_payment.fx_variance = total_fx_variance
                
        # session.commit() <-- REMOVED: Atomicity handled at controller level
        
        # 4. Reactivación Automática o Condicional
        # Si el usuario explícitamente marcó 'activate_service' en el modal, se honra esa decisión.
        # Si no se pasó el flag, se mantiene el comportamiento por defecto (activar si saldo <= 0).
        should_activate = payment_data.get('activate_service')
        
        # Lógica de decisión:
        # A. Si viene explícito True -> ACTIVAR
        # B. Si viene explícito False -> NO ACTIVAR
        # C. Si es None (no vino) -> ACTIVAR solo si deuda <= 0 (comportamiento legacy/auto)
        
        if should_activate is True:
             BatchService()._restore_client(client, commit=False)
             logger.info(f"🚀 Cliente {client.username} reactivado por solicitud explícita en pago.")
             AuditService.log(
                operation='client_reactivated',
                category='client',
                entity_type='client',
                entity_id=client.id,
                description="Reactivación manual solicitada al registrar pago",
                previous_state={'status': client.status},
                new_state={'status': 'active'},
                commit=False # Added commit=False
             )
        elif should_activate is False:
            logger.info(f"⚠️ Cliente {client.username} NO reactivado (activate_service=False explícito).")
        
        elif client.status == 'suspended' and (client.account_balance or 0) <= 0:
            # Caso C: Automático por deuda saldada
            BatchService()._restore_client(client, commit=False)
            logger.info(f"🚀 Cliente {client.username} reactivado automáticamente tras pago (Deuda saldada).")
            
            # Auditoría de Reactivación
            AuditService.log(
                operation='client_reactivated',
                category='client',
                entity_type='client',
                entity_id=client.id,
                description="Reactivación automática tras pago total",
                previous_state={'status': 'suspended'},
                new_state={'status': 'active'},
                commit=False # Added commit=False
            )
            
        # Auditoría de Pago
        AuditService.log_accounting(
            operation='payment_registered',
            amount=amount,
            client_id=client.id,
            description=f"Pago registrado vía {payment_data.get('payment_method', 'cash')}. Ref: {payment_data.get('reference', 'N/A')}",
            entity_id=new_payment.id,
            entity_type='payment',
            commit=False # Added commit=False
        )

        return new_payment

    def revert_payment(self, payment_id, reason="Reversión por incumplimiento"):
        """
        Revierte un pago realizado:
        1. Archiva el pago en la papelera.
        2. Restaura el balance del cliente.
        3. Revierte el estatus de las facturas (Reverse FIFO).
        4. Suspende al cliente en sistema y MikroTik.
        """
        from src.infrastructure.database.models import Payment, DeletedPayment
        
        db = get_db()
        session = db.session
        
        payment = session.query(Payment).get(payment_id)
        if not payment:
            raise ValueError("Pago no encontrado")
            
        client = session.query(Client).get(payment.client_id)
        if not client:
            raise ValueError("Cliente asociado al pago no encontrado")

        amount_to_revert = payment.amount
        
        try:
            # 1. Archivar en papelera
            deleted_payment = DeletedPayment(
                original_id=payment.id,
                client_id=client.id,
                amount=payment.amount,
                currency=payment.currency,
                payment_date=payment.payment_date,
                payment_method=payment.payment_method,
                reference=payment.reference,
                notes=payment.notes,
                deleted_by='admin',
                reason=reason
            )
            session.add(deleted_payment)
            
            # 2. Restaurar balance del cliente
            old_balance = client.account_balance or 0.0
            client.account_balance = old_balance + amount_to_revert
            
            # 3. Revertir facturas (Reverse FIFO: de la más reciente a la más antigua)
            # Buscamos facturas pagadas
            paid_invoices = session.query(Invoice).filter(
                Invoice.client_id == client.id,
                Invoice.status == 'paid'
            ).order_by(Invoice.issue_date.desc()).all()
            
            remaining = amount_to_revert
            for inv in paid_invoices:
                if remaining <= 0: break
                # Revertimos el estatus a unpaid
                # Nota: Una factura pudo haber sido pagada parcialmente por múltiples pagos,
                # pero aquí simplificamos revirtiendo el estatus si el monto calza o supera.
                inv.status = 'unpaid'
                remaining -= inv.total_amount
            
            # 4. Cambiar estatus a suspendido (Requerimiento explícito)
            previous_status = client.status
            client.status = 'suspended'
            
            # 5. Auditoría de Reversión
            AuditService.log(
                operation='payment_reverted',
                category='accounting',
                entity_type='payment',
                entity_id=payment.id,
                description=f"Pago de ${amount_to_revert} REVERTIDO. Cliente: {client.legal_name}. Motivo: {reason}",
                previous_state={'balance': old_balance, 'status': previous_status},
                new_state={'balance': client.account_balance, 'status': 'suspended'}
            )
            
            # 6. Eliminar el pago original
            session.delete(payment)
            session.commit()
            
            # 7. Ejecutar suspensión en MikroTik (Safe Suspend)
            router = db.get_router_repository().get_by_id(client.router_id)
            if router:
                safe_suspend_client(
                    db=db,
                    client=client,
                    router=router,
                    audit_service=AuditService,
                    audit_details=f"Suspensión por reversión de pago: {reason}"
                )
            
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Error al revertir pago {payment_id}: {e}")
            raise e
