/**
 * Client Modal Component
 * Modal profesional para CRUD de clientes con tabs y validación
 */

import toast from './toast.js';
import { ApiService } from '../services/api.service.js';

// Crear instancia de API service
const apiService = new ApiService();

class ClientModal {
    constructor() {
        this.modal = null;
        this.currentClient = null;
        this.routers = [];
        this.plans = [];
        this.trafficChart = null;
        this.consumptionChart = null;
        this.stabilityChart = null;

        // Throttling
        this.lastChartUpdate = 0;
        this.chartUpdateInterval = 2000; // 2s throttle for modal chart

        this.init();
    }

    init() {
        // Crear modal
        this.createModal();
        // Cargar routers para el select
        this.loadRouters();
        // Cargar planes
        this.loadPlans();
        // Inicializar listeners de tráfico en tiempo real
        this.initTrafficSocket();
    }

    initTrafficSocket() {
        // Esperamos a que el socket global esté disponible
        const checkSocket = setInterval(() => {
            if (window.app && window.app.socket) {
                clearInterval(checkSocket);

                window.app.socket.on('client_traffic', (data) => {
                    // Si el modal no está activo o no hay cliente actual, ignorar
                    if (!this.modal.classList.contains('active') || !this.currentClient) return;

                    const clientId = this.currentClient.id.toString();
                    const traffic = data[clientId];

                    if (traffic && traffic.status === 'online') {
                        // console.log(`📈 Actualizando gráfica vivo: ${clientId}`, traffic);
                        this.updateLiveChart(traffic.upload, traffic.download);
                    }
                });
            }
        }, 1000);
    }

    updateLiveChart(uploadBps, downloadBps) {
        if (!this.trafficChart) return;

        // PERFORMANCE: Throttle chart updates to avoid UI lag in the modal
        const now = Date.now();
        if (now - this.lastChartUpdate < this.chartUpdateInterval) {
            return;
        }
        this.lastChartUpdate = now;

        const range = this.modal.querySelector('#traffic-time-range')?.value || 'live';
        const date = new Date();
        const label = `${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}:${date.getSeconds().toString().padStart(2, '0')}`;

        const upMbps = (uploadBps / 1000000).toFixed(2);
        const dwMbps = (downloadBps / 1000000).toFixed(2);

        // Actualizar tarjeta de velocidad en Reportes
        const dlLabel = this.modal.querySelector('#report-download');
        const ulLabel = this.modal.querySelector('#report-upload');
        if (dlLabel) dlLabel.textContent = dwMbps;
        if (ulLabel) ulLabel.textContent = upMbps;

        // Si es modo REAL-TIME, hacemos scroll (Winbox style)
        if (range === 'live') {
            this.trafficChart.data.labels.push(label);
            this.trafficChart.data.datasets[0].data.push(dwMbps);
            this.trafficChart.data.datasets[1].data.push(upMbps);

            const maxPoints = 60; // ~30-50 segundos de buffer visible
            if (this.trafficChart.data.labels.length > maxPoints) {
                this.trafficChart.data.labels.shift();
                this.trafficChart.data.datasets[0].data.shift();
                this.trafficChart.data.datasets[1].data.shift();
            }
        } else {
            // Si es modo HISTÓRICO, añadimos el punto pero permitimos que crezca un poco 
            // para que el usuario "vea" que la gráfica se mueve incluso en 24h
            this.trafficChart.data.labels.push(label);
            this.trafficChart.data.datasets[0].data.push(dwMbps);
            this.trafficChart.data.datasets[1].data.push(upMbps);

            // Limitamos a 500 puntos para no saturar si deja el modal abierto horas
            if (this.trafficChart.data.labels.length > 500) {
                this.trafficChart.data.labels.shift();
                this.trafficChart.data.datasets[0].data.shift();
                this.trafficChart.data.datasets[1].data.shift();
            }
        }

        // Actualizar sin animación pesada para rendimiento
        this.trafficChart.update('none');
    }

    createModal() {
        const modalHTML = `
            <div id="client-modal" class="modal">
                <div class="modal-content large-modal" style="border-radius: 24px; border: 1px solid rgba(226, 232, 240, 0.8); background: #f4f7f9; overflow: hidden; box-shadow: 0 30px 60px -15px rgba(0,0,0,0.2);">
                    <div class="modal-header" style="background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border-bottom: 1px solid rgba(226, 232, 240, 0.8); padding: 24px 32px; display: flex; align-items: center;">
                        <div style="flex: 1;">
                            <h3 id="modal-title" style="font-size: 1.5rem; font-weight: 800; color: #1e293b; margin: 0; letter-spacing: -0.02em;">Nuevo Cliente</h3>
                            <p class="modal-subtitle-text" style="font-size: 0.75rem; font-weight: 800; color: #64748b; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.08em; opacity: 0.8;">GESTIÓN INTEGRAL DE SUSCRIPTOR</p>
                        </div>
                        
                        <!-- Info Box para nombre e IP (solicitado por usuario) -->
                        <div id="modal-client-summary" class="modal-client-summary-box premium-status-badge" style="display: none; padding: 8px 18px; border-radius: 20px; font-weight: 900; font-size: 0.85rem; letter-spacing: 0.02em; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid rgba(255,255,255,0.4); background: #ffffff; color: #1e293b; align-items: center; gap: 8px; margin-left: auto; margin-right: 20px;">
                            <span id="header-client-name" class="header-info-name"></span>
                            <span class="header-info-divider" style="color: #cbd5e1;">|</span>
                            <span id="header-client-ip" class="header-info-ip" style="color: #6366f1;"></span>
                        </div>

                        <button class="close-btn" onclick="window.clientModal.close()" style="background: #f1f5f9; border: none; width: 38px; height: 38px; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #64748b; cursor: pointer; transition: all 0.2s;" onmouseover="this.style.background='#e2e8f0'; this.style.color='#0f172a';" onmouseout="this.style.background='#f1f5f9'; this.style.color='#64748b';">
                            <i class="fas fa-times" style="font-size: 1.15rem;"></i>
                        </button>
                    </div>
                    
                    <div class="modal-body" style="padding: 32px; background: #f4f7f9;">
                        <!-- Tabs - Glass Pills UI -->
                        <div class="modal-tabs">
                            <button class="tab-btn active" data-tab="personal">
                                <i class="fas fa-user"></i>
                                Datos Personales
                            </button>
                            <button class="tab-btn" data-tab="service">
                                <i class="fas fa-book-open"></i>
                                Servicio
                            </button>
                            <button class="tab-btn" data-tab="billing">
                                <i class="fas fa-credit-card"></i>
                                Facturación
                            </button>
                            <button class="tab-btn" data-tab="reports">
                                <i class="fas fa-chart-bar"></i>
                                Reportes
                            </button>
                        </div>

                        <!-- Tab: Datos Personales - High Fidelity Refinement -->
                        <div class="tab-content active" data-tab="personal">
                            <div class="form-grid compact-grid">
                                <div class="form-group span-1">
                                    <label for="subscriber_code">Código</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-hashtag field-icon"></i>
                                        <input type="text" id="subscriber_code" class="form-control readonly-glass" placeholder="CLI-0047" readonly>
                                    </div>
                                </div>
                                
                                <div class="form-group span-1">
                                    <label for="identity_document">N° Documento</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-id-card field-icon"></i>
                                        <input type="text" id="identity_document" class="form-control" placeholder="12345678">
                                    </div>
                                </div>

                                <div class="form-group span-2">
                                    <label for="legal_name">Nombre Completo *</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-user field-icon"></i>
                                        <input type="text" id="legal_name" class="form-control" placeholder="Juan Pérez" required>
                                    </div>
                                </div>
                                
                                <div class="form-group span-2">
                                    <label for="phone">Teléfono de Contacto</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-phone field-icon"></i>
                                        <input type="tel" id="phone" class="form-control" placeholder="+58 414 123 4567">
                                    </div>
                                </div>
                                
                                <div class="form-group span-2">
                                    <label for="email">Correo Electrónico</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-envelope field-icon"></i>
                                        <input type="email" id="email" class="form-control" placeholder="cliente@example.com">
                                    </div>
                                </div>
                                
                                <div class="form-group span-full">
                                    <label for="address">Dirección de Domicilio</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-map-marked-alt field-icon"></i>
                                        <textarea id="address" class="form-control" rows="1" placeholder="Calle, Sector, Ciudad"></textarea>
                                    </div>
                                </div>

                                <div class="form-group span-2">
                                    <label for="coordinates">Coordenadas (Lat, Long)</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-map-pin field-icon"></i>
                                        <input type="text" id="coordinates" class="form-control" placeholder="10.48, -66.90">
                                    </div>
                                </div>

                                <div class="form-group span-2">
                                    <label for="affiliation_date">Fecha de Afiliación</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-calendar-alt field-icon"></i>
                                        <input type="date" id="affiliation_date" class="form-control">
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Tab: Servicio - High Fidelity Refinement -->
                        <div class="tab-content" data-tab="service">
                            <div class="form-grid compact-grid">
                                <div class="form-group span-2">
                                    <label for="router_id">Router de Conexión *</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-network-wired field-icon"></i>
                                        <select id="router_id" class="form-control" required>
                                            <option value="">Seleccione un router...</option>
                                        </select>
                                    </div>
                                </div>
                                
                                <div class="form-group span-2">
                                    <label for="plan_id">Plan de Internet *</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-bolt field-icon"></i>
                                        <select id="plan_id" class="form-control" required>
                                            <option value="">Seleccione un plan...</option>
                                        </select>
                                    </div>
                                </div>

                                <div class="form-group span-2">
                                    <label for="username">Usuario PPPoE *</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-user-circle field-icon"></i>
                                        <input type="text" id="username" class="form-control" placeholder="usuario123" required autocomplete="username">
                                    </div>
                                </div>
                                
                                <div class="form-group span-2">
                                    <label for="password">Contraseña de Servicio</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-key field-icon"></i>
                                        <input type="text" id="password" class="form-control" placeholder="••••••••" autocomplete="current-password">
                                    </div>
                                </div>
                                
                                <div class="form-group span-2">
                                    <label for="ip_address">Dirección IP Estática</label>
                                    <div class="input-group-premium">
                                        <div class="input-icon-wrapper flex-grow">
                                            <i class="fas fa-map-marker-alt field-icon"></i>
                                            <input type="text" id="ip_address" class="form-control" placeholder="10.0.0.100">
                                        </div>
                                        <button class="btn-sync-field" onclick="window.clientModal.lookupIdentity('ip')" title="Sincronizar IP por MAC o Usuario">
                                            <i class="fas fa-sync-alt"></i>
                                        </button>
                                    </div>
                                </div>

                                <div class="form-group span-2">
                                    <label for="mac_address">Dirección MAC</label>
                                    <div class="input-group-premium">
                                        <div class="input-icon-wrapper flex-grow">
                                            <i class="fas fa-fingerprint field-icon"></i>
                                            <input type="text" id="mac_address" class="form-control" placeholder="00:00:00:00:00:00">
                                        </div>
                                        <button class="btn-sync-field" onclick="window.clientModal.lookupIdentity('mac')" title="Sincronizar MAC por IP o Usuario">
                                            <i class="fas fa-sync-alt"></i>
                                        </button>
                                    </div>
                                </div>

                                <div class="form-group span-2">
                                    <label for="service_type">Tipo de Servicio</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-microchip field-icon"></i>
                                        <select id="service_type" class="form-control">
                                            <option value="pppoe">PPPoE</option>
                                            <option value="simple_queue">Simple Queue</option>
                                            <option value="hotspot">Hotspot</option>
                                        </select>
                                    </div>
                                </div>
                                
                                <div class="form-group span-2">
                                    <label for="status">Estado del Cliente</label>
                                    <div class="input-icon-wrapper">
                                        <i class="fas fa-toggle-on field-icon"></i>
                                        <select id="status" class="form-control">
                                            <option value="ACTIVE">Activo</option>
                                            <option value="SUSPENDED">Suspendido</option>
                                            <option value="INACTIVE">Inactivo</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Tab: Facturación -->
                        <div id="tab-billing" class="tab-content tab-billing" data-tab="billing">
                            <!-- Premium Metrics Dashboard -->
                            <div class="metrics-row">
                                <div class="metric-card fee">
                                    <div class="icon"><i class="fas fa-tag"></i></div>
                                    <div class="metric-label">Cuota Mensual</div>
                                    <div class="metric-value" id="metric-monthly-fee">$0</div>
                                    <div class="metric-subtext">Tarifa congelada</div>
                                </div>
                                <div class="metric-card balance" id="card-balance">
                                    <div class="icon"><i class="fas fa-wallet"></i></div>
                                    <div class="metric-label" style="display: flex; justify-content: space-between; align-items: center;">
                                        Balance de Cuenta
                                        <button class="btn-balance-adjust" onclick="window.clientModal.adjustBalance()" title="Ajustar Balance Manualmente" style="background: none; border: none; font-size: 0.8rem; color: #64748b; cursor: pointer; opacity: 0.6; transition: all 0.2s;">
                                            <i class="fas fa-edit"></i>
                                        </button>
                                    </div>
                                    <div class="metric-value" id="metric-balance">$0</div>
                                    <div class="metric-subtext" id="metric-balance-subtext">Crédito a favor</div>
                                </div>
                                <div class="metric-card due">
                                    <div class="icon"><i class="fas fa-calendar-exclamation"></i></div>
                                    <div class="metric-label">Vencimiento</div>
                                    <div class="metric-value" id="metric-due-date">--/--</div>
                                    <div class="metric-subtext">Próximo corte</div>
                                </div>
                                <div class="metric-card payment">
                                    <div class="icon"><i class="fas fa-hand-holding-usd"></i></div>
                                    <div class="metric-label">Último Pago</div>
                                    <div class="metric-value" id="metric-last-payment-val">--/--</div>
                                    <div class="metric-subtext" id="metric-last-payment-date">Sin registros</div>
                                </div>
                            </div>

                            <!-- Hidden functional inputs for form saving consistency -->
                            <div style="display:none">
                                <input type="number" id="monthly_fee">
                                <input type="number" id="account_balance">
                                <input type="date" id="due_date">
                                <input type="date" id="last_payment_date">
                            </div>

                            <!-- Refined History Section -->
                            <div class="history-grid-refined">
                                <div style="display: flex; flex-direction: column; gap: 24px;">
                                    <div class="modern-panel">
                                        <div class="panel-header-modern">
                                            <div class="panel-title"><i class="fas fa-history"></i> Historial de Pagos</div>
                                        </div>
                                        <div class="panel-body-modern">
                                            <div id="client-payments-history" class="compact-table-container">
                                                <p class="text-muted text-center py-4">Cargando...</p>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="modern-panel">
                                        <div class="panel-header-modern">
                                            <div class="panel-title"><i class="fas fa-handshake"></i> Historial de Promesas</div>
                                        </div>
                                        <div class="panel-body-modern">
                                            <div id="client-promises-history" class="compact-table-container">
                                                <p class="text-muted text-center py-4">Cargando...</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="modern-panel">
                                    <div class="panel-header-modern">
                                        <div class="panel-title"><i class="fas fa-chart-line"></i> Análisis de Tráfico</div>
                                        <div class="panel-actions">
                                            <select id="traffic-time-range" class="select-mini" onchange="window.clientModal.loadTrafficHistory()">
                                                <option value="live" selected>Tiempo Real</option>
                                                <option value="24">24h</option>
                                                <option value="168">Semana</option>
                                                <option value="720">Mes</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div class="panel-body-modern">
                                        <div class="chart-container-modal" style="height: 250px;">
                                            <canvas id="client-traffic-chart"></canvas>
                                        </div>
                                        <div id="traffic-stats-summary" class="traffic-summary" style="justify-content: center; margin-top: 20px; font-weight: bold;">
                                            <!-- Consumo total -->
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Tab: Reportes - Diagnóstico Avanzado -->
                        <div class="tab-content" data-tab="reports">
                            <div class="metrics-row">
                                <div class="metric-card availability">
                                    <div class="icon"><i class="fas fa-heartbeat"></i></div>
                                    <div class="metric-label">Quality Score</div>
                                    <div class="metric-value" id="report-quality">100</div>
                                    <div class="metric-subtext">Calidad de Enlace</div>
                                </div>
                                <div class="metric-card consumption-total cursor-pointer" onclick="window.clientModal.showStabilityHistory()">
                                    <div class="icon"><i class="fas fa-wave-square"></i></div>
                                    <div class="metric-label">Latencia / Jitter</div>
                                    <div class="metric-value">
                                        <span id="report-latency">0ms</span>
                                        <small class="text-muted" style="font-size: 0.5em;" id="report-jitter">±0ms</small>
                                    </div>
                                    <div class="metric-subtext">Estabilidad de Respuesta</div>
                                </div>
                                <div class="metric-card availability">
                                    <div class="icon"><i class="fas fa-signal"></i></div>
                                    <div class="metric-label">Disponibilidad</div>
                                    <div class="metric-value" id="report-availability">--%</div>
                                    <div class="metric-subtext">Histórico 30 días</div>
                                </div>
                                <div class="metric-card consumption-total">
                                    <div class="icon"><i class="fas fa-bolt"></i></div>
                                    <div class="metric-label">Velocidad Live</div>
                                    <div class="metric-value">
                                        <span id="report-download">0</span> <small style="font-size: 0.6em; opacity: 0.7;">↓</small>
                                        <span class="text-muted" style="font-size: 0.8em;">/</span>
                                        <span id="report-upload">0</span> <small style="font-size: 0.6em; opacity: 0.7;">↑</small>
                                    </div>
                                    <div class="metric-subtext">Mbps Actuales</div>
                                </div>
                            </div>

                            <!-- IA & Traffic Engineering Section (Requested by User) -->
                            <div class="premium-intelligence-panel glass-panel">
                                <div class="ai-header">
                                    <div class="ai-title">
                                        <i class="fas fa-brain ai-pulse"></i>
                                        SGUBM Intelligence & Traffic Analytics
                                    </div>
                                    <div class="ai-badge">ENGINEERING MODE</div>
                                </div>
                                <div class="ai-grid">
                                    <div class="ai-card">
                                        <div class="ai-label">Perfil de Consumidor</div>
                                        <div class="ai-value" id="ai-user-profile">Analizando...</div>
                                        <div class="ai-trend" id="ai-user-trend">Buscando patrones de ráfaga</div>
                                    </div>
                                    <div class="ai-card">
                                        <div class="ai-label">Proyección Mensual</div>
                                        <div class="ai-value" id="ai-prediction">0.0 GB</div>
                                        <div class="ai-trend">Basado en tendencia actual</div>
                                    </div>
                                    <div class="ai-card">
                                        <div class="ai-label">Punto de Saturación (Hora Pico)</div>
                                        <div class="ai-value" id="ai-peak-hour">--:--</div>
                                        <div class="ai-trend">Mayor demanda detectada</div>
                                    </div>
                                    <div class="ai-card">
                                        <div class="ai-label">Ingeniería de Tráfico</div>
                                        <div class="ai-value" id="ai-recom-plan">Optimizando...</div>
                                        <div class="ai-trend" id="ai-stability-status">Link Health: --</div>
                                    </div>
                                </div>
                            </div>

                            <div class="history-grid-refined">
                                <div class="modern-panel">
                                    <div class="panel-header-modern">
                                        <div class="panel-title"><i class="fas fa-history"></i> Histograma de Consumo Diario</div>
                                    </div>
                                    <div class="panel-body-modern">
                                        <div class="chart-container-modal" style="height: 250px;">
                                            <canvas id="client-consumption-chart"></canvas>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="modern-panel">
                                    <div class="panel-header-modern">
                                        <div class="panel-title"><i class="fas fa-plug"></i> Log de Fallas y Cortes</div>
                                    </div>
                                    <div class="panel-body-modern">
                                        <div id="client-outages-list" class="compact-table-container">
                                            <p class="text-muted text-center py-4">Sin fallas recientes</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Modal Footer -->
                    <div class="modal-footer" style="padding: 24px 32px; background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(12px); border-top: 1px solid rgba(226, 232, 240, 0.8); display: flex; gap: 14px; align-items: center; justify-content: flex-end;">
                        <button class="btn-secondary" data-close onclick="window.clientModal.close()" 
                            style="padding: 14px 28px; border-radius: 16px; font-weight: 800; font-size: 0.95rem; background: #ffffff; color: #475569; border: 1px solid rgba(226, 232, 240, 0.8); cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.02);"
                            onmouseover="this.style.background='#f8fafc'; this.style.borderColor='#cbd5e1'; this.style.color='#1e293b';"
                            onmouseout="this.style.background='#ffffff'; this.style.borderColor='rgba(226, 232, 240, 0.8)'; this.style.color='#475569';">
                            <i class="fas fa-times"></i>
                            Cancelar
                        </button>
                        <button class="btn-primary" id="save-client-btn" onclick="window.clientModal.save()"
                            style="padding: 14px 32px; border-radius: 16px; font-weight: 800; font-size: 0.95rem; text-transform: none; background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); color: white; border: none; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 10px; box-shadow: 0 10px 20px -5px rgba(99, 102, 241, 0.4), inset 0 1px 0 rgba(255,255,255,0.2);"
                            onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 15px 25px -5px rgba(99, 102, 241, 0.5), inset 0 1px 0 rgba(255,255,255,0.2)';"
                            onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 10px 20px -5px rgba(99, 102, 241, 0.4), inset 0 1px 0 rgba(255,255,255,0.2)';"
                            onmousedown="this.style.transform='translateY(1px)';">
                            <i class="fas fa-save"></i>
                            Guardar Cliente
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Agregar al DOM
        const container = document.createElement('div');
        container.innerHTML = modalHTML;
        document.body.appendChild(container.firstElementChild);

        this.modal = document.getElementById('client-modal');

        // Setup tab switching
        this.setupTabs();

        // Listeners para actualización en tiempo real del header (Solicitado por usuario)
        this.modal.querySelector('#legal_name').addEventListener('input', (e) => {
            const headerName = this.modal.querySelector('#header-client-name');
            if (headerName && this.modal.querySelector('#modal-client-summary').style.display !== 'none') {
                headerName.textContent = e.target.value || 'Sin Nombre';
            }
        });

        this.modal.querySelector('#ip_address').addEventListener('input', (e) => {
            const headerIp = this.modal.querySelector('#header-client-ip');
            if (headerIp && this.modal.querySelector('#modal-client-summary').style.display !== 'none') {
                headerIp.textContent = e.target.value || 'Sin IP';
            }
        });
    }

    setupTabs() {
        const tabBtns = this.modal.querySelectorAll('.tab-btn');
        const tabContents = this.modal.querySelectorAll('.tab-content');

        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const tabName = btn.dataset.tab;

                // Update buttons
                tabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // Update content
                tabContents.forEach(c => c.classList.remove('active'));
                const targetContent = this.modal.querySelector(`.tab-content[data-tab="${tabName}"]`);
                if (targetContent) targetContent.classList.add('active');

                // Si es la pestaña de reportes, cargar datos
                if (tabName === 'reports' && this.currentClient) {
                    this.loadUsageReport();
                }
            });
        });
    }

    async loadRouters() {
        try {
            const data = await apiService.get('/api/routers');
            this.routers = data;

            // Actualizar select
            const select = this.modal.querySelector('#router_id');
            if (select) {
                select.innerHTML = '<option value="">Seleccione un router...</option>';

                this.routers.forEach(router => {
                    const option = document.createElement('option');
                    option.value = router.id;
                    option.textContent = router.alias;
                    select.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Error loading routers:', error);
            toast.error('Error al cargar routers');
        }
    }

    async loadPlans() {
        try {
            const data = await apiService.get('/api/plans');
            this.plans = data;

            // Actualizar select
            const select = this.modal.querySelector('#plan_id');
            if (select) {
                select.innerHTML = '<option value="">Seleccione un plan...</option>';

                this.plans.forEach(plan => {
                    const option = document.createElement('option');
                    option.value = plan.id;
                    // Mostrar nombre + precio para referencia
                    option.textContent = `${plan.name} ($${parseFloat(plan.monthly_price).toLocaleString()})`;
                    select.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Error loading plans:', error);
            toast.error('Error al cargar planes de internet');
        }
    }

    /**
     * Abre el modal para crear un nuevo cliente
     */
    showCreate() {
        this.currentClient = null;
        this.modal.querySelector('#modal-title').textContent = 'Nuevo Cliente';
        this.modal.querySelector('#modal-client-summary').style.display = 'none';
        this.resetForm();
        this.modal.classList.add('active');

        // Focus en primer campo
        setTimeout(() => {
            this.modal.querySelector('#legal_name').focus();
        }, 100);
    }

    /**
     * Abre el modal para editar un cliente existente
     * @param {object} client - Datos del cliente
     */
    showEdit(client) {
        this.currentClient = client;
        this.modal.querySelector('#modal-title').textContent = 'Editar Cliente';
        this.loadClientData(client);
        this.modal.classList.add('active');

        // Cargar historial si es edición
        this.loadHistoryData(client.id);
    }

    /**
     * Carga los datos del cliente en el formulario
     */
    loadClientData(client) {
        // Mostrar resumen en el header
        const summaryBox = this.modal.querySelector('#modal-client-summary');
        const headerName = this.modal.querySelector('#header-client-name');
        const headerIp = this.modal.querySelector('#header-client-ip');

        if (summaryBox && headerName && headerIp) {
            summaryBox.style.display = 'flex';
            headerName.textContent = client.legal_name || 'Sin Nombre';
            headerIp.textContent = client.ip_address || 'Sin IP';
        }

        // Datos personales
        this.modal.querySelector('#legal_name').value = client.legal_name || '';
        this.modal.querySelector('#identity_document').value = client.identity_document || '';
        this.modal.querySelector('#phone').value = client.phone || '';
        this.modal.querySelector('#email').value = client.email || '';
        this.modal.querySelector('#address').value = client.address || '';

        // Servicio
        this.modal.querySelector('#router_id').value = client.router_id || '';
        this.modal.querySelector('#subscriber_code').value = client.subscriber_code || '';
        this.modal.querySelector('#username').value = client.username || '';
        this.modal.querySelector('#password').value = client.password || '';
        this.modal.querySelector('#ip_address').value = client.ip_address || '';
        this.modal.querySelector('#mac_address').value = client.mac_address || '';
        this.modal.querySelector('#plan_id').value = client.plan_id || '';
        this.modal.querySelector('#service_type').value = client.service_type || 'pppoe';
        this.modal.querySelector('#status').value = client.status || 'ACTIVE';

        // Facturación
        this.modal.querySelector('#monthly_fee').value = client.monthly_fee || 0;
        this.modal.querySelector('#account_balance').value = client.account_balance || 0;
        this.modal.querySelector('#due_date').value = client.due_date ? client.due_date.split('T')[0] : '';
        this.modal.querySelector('#last_payment_date').value = client.last_payment_date ? client.last_payment_date.split('T')[0] : '';

        // Update Premium Metrics
        const fee = parseFloat(client.monthly_fee || 0);
        const balance = parseFloat(client.account_balance || 0);

        this.modal.querySelector('#metric-monthly-fee').textContent = `$${fee.toLocaleString()}`;
        this.modal.querySelector('#metric-balance').textContent = `$${Math.abs(balance).toLocaleString()}`;

        const balanceCard = this.modal.querySelector('#card-balance');
        const balanceSub = this.modal.querySelector('#metric-balance-subtext');
        if (balance < 0) {
            balanceCard.classList.add('debt');
            balanceCard.querySelector('.metric-value').classList.add('text-danger');
            balanceSub.textContent = 'Deuda pendiente';
            balanceSub.classList.add('text-danger');
        } else {
            balanceCard.classList.remove('debt');
            balanceCard.querySelector('.metric-value').classList.remove('text-danger');
            balanceSub.textContent = balance > 0 ? 'Crédito a favor' : 'Cuenta al día';
            balanceSub.classList.remove('text-danger');
        }

        if (client.due_date) {
            const d = new Date(client.due_date);
            this.modal.querySelector('#metric-due-date').textContent = `${d.getDate()}/${d.getMonth() + 1}`;
        } else {
            this.modal.querySelector('#metric-due-date').textContent = '--/--';
        }

        if (client.last_payment_date) {
            const d = new Date(client.last_payment_date);
            this.modal.querySelector('#metric-last-payment-val').textContent = `${d.getDate()}/${d.getMonth() + 1}`;
            this.modal.querySelector('#metric-last-payment-date').textContent = d.toLocaleDateString();
        } else {
            this.modal.querySelector('#metric-last-payment-val').textContent = '--/--';
            this.modal.querySelector('#metric-last-payment-date').textContent = 'Sin registros';
        }
    }

    /**
     * Resetea el formulario
     */
    resetForm() {
        const form = this.modal.querySelector('.modal-body');
        form.querySelectorAll('input, textarea, select').forEach(field => {
            if (field.type === 'checkbox') {
                field.checked = false;
            } else if (field.id !== 'router_id' && field.id !== 'service_type' && field.id !== 'status') {
                field.value = '';
            }
        });

        // Valores por defecto
        this.modal.querySelector('#service_type').value = 'pppoe';
        this.modal.querySelector('#status').value = 'ACTIVE';
        this.modal.querySelector('#account_balance').value = '0';

        // Volver al primer tab
        this.modal.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        this.modal.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        this.modal.querySelector('.tab-btn').classList.add('active');
        this.modal.querySelector('.tab-content').classList.add('active');

        // Ocultar resumen del header al resetear
        const summaryBox = this.modal.querySelector('#modal-client-summary');
        if (summaryBox) summaryBox.style.display = 'none';
    }

    /**
     * Valida el formulario
     */
    validate() {
        const legal_name = this.modal.querySelector('#legal_name').value.trim();
        const router_id = this.modal.querySelector('#router_id').value;
        const username = this.modal.querySelector('#username').value.trim();

        if (!legal_name) {
            toast.warning('Por favor ingrese el nombre del cliente');
            this.modal.querySelector('#legal_name').focus();
            return false;
        }

        if (!router_id) {
            toast.warning('Por favor seleccione un router');
            // Cambiar a tab de servicio
            this.modal.querySelector('.tab-btn[data-tab="service"]').click();
            this.modal.querySelector('#router_id').focus();
            return false;
        }

        if (!username) {
            toast.warning('Por favor ingrese el usuario PPPoE');
            this.modal.querySelector('.tab-btn[data-tab="service"]').click();
            this.modal.querySelector('#username').focus();
            return false;
        }

        const plan_id = this.modal.querySelector('#plan_id').value;
        if (!plan_id) {
            toast.warning('Por favor seleccione un plan de internet');
            this.modal.querySelector('.tab-btn[data-tab="service"]').click();
            this.modal.querySelector('#plan_id').focus();
            return false;
        }

        return true;
    }

    /**
     * Recopila los datos del formulario
     */
    getFormData() {
        return {
            legal_name: this.modal.querySelector('#legal_name').value.trim(),
            identity_document: this.modal.querySelector('#identity_document').value.trim(),
            phone: this.modal.querySelector('#phone').value.trim(),
            email: this.modal.querySelector('#email').value.trim(),
            address: this.modal.querySelector('#address').value.trim(),
            router_id: parseInt(this.modal.querySelector('#router_id').value),
            subscriber_code: this.modal.querySelector('#subscriber_code').value.trim(),
            username: this.modal.querySelector('#username').value.trim(),
            password: this.modal.querySelector('#password').value.trim(),
            ip_address: this.modal.querySelector('#ip_address').value.trim(),
            mac_address: this.modal.querySelector('#mac_address').value.trim(),
            plan_id: parseInt(this.modal.querySelector('#plan_id').value),
            service_type: this.modal.querySelector('#service_type').value,
            status: this.modal.querySelector('#status').value,
            monthly_fee: parseFloat(this.modal.querySelector('#monthly_fee').value) || 0,
            account_balance: parseFloat(this.modal.querySelector('#account_balance').value) || 0,
            due_date: this.modal.querySelector('#due_date').value || null,
        };
    }

    /**
     * Busca la identidad (IP o MAC) en el router basándose en los datos actuales
     * @param {string} target - 'ip' o 'mac'
     */
    async lookupIdentity(target) {
        const routerId = this.modal.querySelector('#router_id').value;
        const ipAddress = this.modal.querySelector('#ip_address').value.trim();
        const username = this.modal.querySelector('#username').value.trim();

        if (!routerId) {
            toast.warning('Debe seleccionar un router primero');
            return;
        }

        if (!ipAddress && !username) {
            toast.warning('Debe ingresar al menos la IP o el Usuario');
            return;
        }

        const btn = target === 'ip' ?
            this.modal.querySelector('.btn-sync-field[onclick*="ip"]') :
            this.modal.querySelector('.btn-sync-field[onclick*="mac"]');

        const originalIcon = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        btn.disabled = true;

        try {
            const result = await apiService.post('/api/clients/lookup-identity', {
                router_id: routerId,
                ip_address: ipAddress,
                username: username
            });

            if (result.success) {
                if (target === 'ip' && result.ip_address) {
                    this.updateFieldWithAnimation('#ip_address', result.ip_address);
                    toast.success('IP sincronizada desde el router');
                } else if (target === 'mac' && result.mac_address) {
                    this.updateFieldWithAnimation('#mac_address', result.mac_address);
                    toast.success('Dirección MAC sincronizada');
                } else {
                    toast.info('No se encontró información adicional en el router');
                }
            }
        } catch (error) {
            console.error('Error lookup identity:', error);
            toast.error('Error al consultar el router');
        } finally {
            btn.innerHTML = originalIcon;
            btn.disabled = false;
        }
    }

    updateFieldWithAnimation(selector, value) {
        const field = this.modal.querySelector(selector);
        if (!field) return;

        field.value = value;
        field.classList.add('field-highlight');
        setTimeout(() => field.classList.remove('field-highlight'), 1000);
    }

    /**
     * Guarda el cliente
     */
    async save() {
        if (!this.validate()) {
            return;
        }

        const data = this.getFormData();

        try {
            if (this.currentClient) {
                // Actualizar existente
                await apiService.put(`/api/clients/${this.currentClient.id}`, data);
                toast.success('Cliente actualizado correctamente');
            } else {
                // Crear nuevo
                await apiService.post('/api/clients', data);
                toast.success('Cliente creado correctamente');
            }

            if (window.app && window.app.modalManager) {
                window.app.modalManager.close('client');
            } else {
                this.close();
            }

            // Recargar lista de clientes
            if (window.app && window.app.modules && window.app.modules.clients) {
                window.app.modules.clients.loadClients();
            }
        } catch (error) {
            console.error('Error saving client:', error);
            const msg = error.data?.error || error.message || 'Error al guardar cliente';
            toast.error(msg);
        }
    }

    /**
     * Cierra el modal
     */
    close() {
        this.modal.classList.remove('active');
        this.resetForm();

        // Destruir chart para evitar memory leaks
        if (this.trafficChart) {
            this.trafficChart.destroy();
            this.trafficChart = null;
        }
        if (this.consumptionChart) {
            this.consumptionChart.destroy();
            this.consumptionChart = null;
        }
        if (this.stabilityChart) {
            this.stabilityChart.destroy();
            this.stabilityChart = null;
        }
    }

    /**
     * Carga datos de historial (Pagos y Tráfico)
     */
    async loadHistoryData(clientId) {
        try {
            // 1. Cargar Pagos
            const payments = await apiService.get(`/api/payments?client_id=${clientId}&limit=10`);
            this.renderPaymentsHistory(payments);

            // 2. Cargar Promesas (NUEVO)
            const promises = await apiService.get(`/api/clients/${clientId}/promises`);
            this.renderPromiseHistory(promises);

            // 3. Cargar Tráfico
            this.loadTrafficHistory();
        } catch (error) {
            console.error('Error loading history data:', error);
        }
    }

    async loadTrafficHistory() {
        if (!this.currentClient) return;

        const clientId = this.currentClient.id;
        const range = this.modal.querySelector('#traffic-time-range')?.value || 'live';

        // Si es LIVE, reiniciamos el chart vacío para empezar de cero
        if (range === 'live') {
            this.renderTrafficChart([]);
            return;
        }

        const hours = parseInt(range);
        try {
            const history = await apiService.get(`/api/clients/${clientId}/traffic-history?hours=${hours}`);
            this.renderTrafficChart(history);
            this.updateTrafficSummary(history);
        } catch (error) {
            console.error('Error loading traffic history:', error);
        }
    }

    renderPaymentsHistory(payments) {
        const container = this.modal.querySelector('#client-payments-history');
        if (!container) return;

        if (!payments || payments.length === 0) {
            container.innerHTML = '<p class="text-muted text-center py-4">No hay pagos registrados</p>';
            return;
        }

        let html = `
            <table class="compact-history-table">
                <thead>
                    <tr>
                        <th>Fecha</th>
                        <th>Monto</th>
                        <th>Método</th>
                        <th>Ref</th>
                    </tr>
                </thead>
                <tbody>
        `;

        payments.forEach(p => {
            const date = new Date(p.payment_date).toLocaleDateString();
            html += `
                <tr>
                    <td>${date}</td>
                    <td class="font-bold">$${parseFloat(p.amount).toLocaleString()}</td>
                    <td>${p.payment_method}</td>
                    <td><small>${p.reference || '-'}</small></td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        container.innerHTML = html;
    }

    renderPromiseHistory(promises) {
        const container = this.modal.querySelector('#client-promises-history');
        if (!container) return;

        if (!promises || promises.length === 0) {
            container.innerHTML = '<p class="text-muted text-center py-4">No hay historial de promesas</p>';
            return;
        }

        let html = `
            <table class="compact-history-table">
                <thead>
                    <tr>
                        <th>Fecha</th>
                        <th>Estado</th>
                        <th>Vencimiento</th>
                    </tr>
                </thead>
                <tbody>
        `;

        promises.forEach(p => {
            const createdDate = new Date(p.created_at).toLocaleDateString();
            const promiseDate = new Date(p.promise_date).toLocaleDateString();

            let statusClass = '';
            let statusLabel = '';
            let icon = '';

            switch (p.status) {
                case 'fulfilled':
                    statusClass = 'status-active';
                    statusLabel = 'Cumplida';
                    icon = '<i class="fas fa-check-circle"></i>';
                    break;
                case 'broken':
                    statusClass = 'status-suspended';
                    statusLabel = 'Incumplida';
                    icon = '<i class="fas fa-times-circle"></i>';
                    break;
                default:
                    statusClass = 'status-pending';
                    statusLabel = 'Pendiente';
                    icon = '<i class="fas fa-clock"></i>';
            }

            html += `
                <tr title="${p.notes || ''}">
                    <td><small>${createdDate}</small></td>
                    <td>
                        <span class="badge ${statusClass}" style="font-size: 0.7rem; padding: 2px 6px;">
                            ${icon} ${statusLabel}
                        </span>
                    </td>
                    <td><small>${promiseDate}</small></td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        container.innerHTML = html;
    }

    renderTrafficChart(history) {
        const ctx = document.getElementById('client-traffic-chart')?.getContext('2d');
        if (!ctx) return;

        if (this.trafficChart) {
            this.trafficChart.destroy();
        }

        // Si no hay historial y no es modo live, podríamos mostrar algo,
        // pero para LIVE siempre necesitamos inicializar el objeto chart.
        const labels = (history || []).map(h => {
            const d = new Date(h.timestamp);
            return `${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`;
        });

        const downloadData = (history || []).map(h => (h.download_bps / 1000000).toFixed(2)); // Mbps
        const uploadData = (history || []).map(h => (h.upload_bps / 1000000).toFixed(2)); // Mbps

        // Create Gradients
        const gradDown = ctx.createLinearGradient(0, 0, 0, 250);
        gradDown.addColorStop(0, 'rgba(0, 212, 255, 0.4)');
        gradDown.addColorStop(1, 'rgba(0, 212, 255, 0)');

        const gradUp = ctx.createLinearGradient(0, 0, 0, 250);
        gradUp.addColorStop(0, 'rgba(168, 85, 247, 0.4)');
        gradUp.addColorStop(1, 'rgba(168, 85, 247, 0)');

        this.trafficChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Descarga (Mbps)',
                        data: downloadData,
                        borderColor: '#00D4FF',
                        backgroundColor: gradDown,
                        fill: true,
                        tension: 0.4,
                        borderWidth: 3,
                        pointRadius: 0,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#00D4FF',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2
                    },
                    {
                        label: 'Subida (Mbps)',
                        data: uploadData,
                        borderColor: '#A855F7',
                        backgroundColor: gradUp,
                        fill: true,
                        tension: 0.4,
                        borderWidth: 3,
                        pointRadius: 0,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#A855F7',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            boxWidth: 12,
                            font: { size: 10 }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 8,
                            font: { size: 9 }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(0,0,0,0.05)' },
                        ticks: {
                            callback: value => value + 'M',
                            font: { size: 9 }
                        }
                    }
                }
            }
        });
    }

    updateTrafficSummary(history) {
        const summary = this.modal.querySelector('#traffic-stats-summary');
        if (!summary) return;

        if (!history || history.length === 0) {
            summary.innerHTML = '<span>Sin datos de consumo</span>';
            return;
        }

        // Cálculo aproximado de consumo total (Simplificado: asumiendo intervalos constantes)
        // Mbps * 15 min / 8 = MB
        let totalDownMB = 0;
        let totalUpMB = 0;

        history.forEach(h => {
            totalDownMB += (h.download_bps / 8 / 1024 / 1024) * (15 * 60); // Asumiendo cada snapshot representa 15m
            totalUpMB += (h.upload_bps / 8 / 1024 / 1024) * (15 * 60);
        });

        summary.innerHTML = `
            <span><i class="fas fa-arrow-down text-blue"></i> ${(totalDownMB / 1024).toFixed(2)} GB</span>
            <span><i class="fas fa-arrow-up text-purple"></i> ${(totalUpMB / 1024).toFixed(2)} GB</span>
        `;
    }

    async loadUsageReport() {
        if (!this.currentClient) return;
        const clientId = this.currentClient.id;

        try {
            const data = await apiService.get(`/api/clients/${clientId}/usage-report?days=30`);
            this.renderUsageCharts(data);
            this.updateUsageOutages(data.outages);

            // Actualizar métricas
            // Actualizar métricas
            const qualityEl = document.getElementById('report-quality');
            if (qualityEl) {
                const score = (data.quality_score !== undefined && data.quality_score !== null) ? data.quality_score : 100;
                qualityEl.textContent = score;
            }

            const latencyEl = document.getElementById('report-latency');
            if (latencyEl) latencyEl.textContent = `${data.avg_latency || 0}ms`;

            const availEl = document.getElementById('report-availability');
            if (availEl) availEl.textContent = `${data.availability}%`;

            const jitterEl = document.getElementById('report-jitter');
            if (jitterEl) jitterEl.textContent = `±${data.latency_jitter || 0}ms`;

            // IA Intelligence Updates
            const intelligence = data.intelligence || {};
            const profileEl = document.getElementById('ai-user-profile');
            if (profileEl) profileEl.textContent = intelligence.user_profile || 'Normal';

            const predictEl = document.getElementById('ai-prediction');
            if (predictEl) predictEl.textContent = `${intelligence.predicted_monthly_gb || 0} GB`;

            const peakEl = document.getElementById('ai-peak-hour');
            if (peakEl) peakEl.textContent = intelligence.peak_hour || '--:--';

            const recomEl = document.getElementById('ai-recom-plan');
            if (recomEl) {
                recomEl.textContent = intelligence.recommended_plan || 'Óptimo';
                if (intelligence.recommended_plan === 'Upgrade Sugerido') {
                    recomEl.style.color = '#f59e0b';
                } else {
                    recomEl.style.color = '#10b981';
                }
            }

            const statusEl = document.getElementById('ai-stability-status');
            if (statusEl) statusEl.textContent = `Salud del Enlace: ${intelligence.stability_status || 'Estable'}`;

        } catch (error) {
            console.error('Error loading usage report:', error);
        }
    }

    renderUsageCharts(reportData) {
        const ctx = document.getElementById('client-consumption-chart');
        if (!ctx) return;

        // Limpiar anterior
        if (this.consumptionChart) this.consumptionChart.destroy();

        const labels = reportData.daily_usage.map(d => d.date.split('-').slice(1).reverse().join('/')); // MM/DD -> DD/MM
        const downData = reportData.daily_usage.map(d => d.download_gb);
        const upData = reportData.daily_usage.map(d => d.upload_gb);

        this.consumptionChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Descarga (GB)',
                        data: downData,
                        backgroundColor: '#00D4FF',
                        borderRadius: 4
                    },
                    {
                        label: 'Subida (GB)',
                        data: upData,
                        backgroundColor: '#A855F7',
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { stacked: true, grid: { display: false } },
                    y: { stacked: true, beginAtZero: true, ticks: { callback: v => v + ' GB' } }
                }
            }
        });
    }

    updateUsageOutages(outages) {
        const list = document.getElementById('client-outages-list');
        if (!list) return;

        if (!outages || outages.length === 0) {
            list.innerHTML = '<p class="text-muted text-center py-4">Sin fallas detectadas en el periodo</p>';
            return;
        }

        let html = `
            <table class="table-compact">
                <thead>
                    <tr>
                        <th>Inicio</th>
                        <th>Fin</th>
                        <th>Duración</th>
                    </tr>
                </thead>
                <tbody>
        `;

        outages.forEach(o => {
            const startStr = new Date(o.start).toLocaleString();
            const endStr = o.end === 'En curso' ? '<span class="badge badge-danger">Activo</span>' : new Date(o.end).toLocaleString();
            const duration = o.duration_mins ? `${o.duration_mins} min` : '--';

            html += `
                <tr>
                    <td>${startStr}</td>
                    <td>${endStr}</td>
                    <td><b>${duration}</b></td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        list.innerHTML = html;
    }

    async showStabilityHistory() {
        if (!this.currentClient) return;
        const clientId = this.currentClient.id;

        // Abrir modal usando ModalManager
        if (window.app && window.app.modalManager) {
            window.app.modalManager.open('stability-history', { clientId });
        } else {
            // Fallback (Legacy)
            const modal = document.getElementById('stability-history-modal');
            if (modal) modal.classList.add('active');
        }

        try {
            const data = await apiService.get(`/api/clients/${clientId}/usage-report?days=7`);
            this.renderStabilityChart(data);
            this.renderStabilityTable(data.history_raw || []);
        } catch (error) {
            console.error('Error loading stability history:', error);
            toast.error('Error al cargar historial de estabilidad');
        }
    }

    renderStabilityChart(data) {
        let canvas = document.getElementById('stability-history-chart');
        if (!canvas) return;

        const container = canvas.parentElement;

        if (this.stabilityChart) {
            this.stabilityChart.destroy();
            this.stabilityChart = null;
        }

        const history = data.history_raw || [];

        const modernPanel = container.closest('.modern-panel');
        const headerTitle = modernPanel ? modernPanel.querySelector('.panel-title') : null;

        let offlineMsg = container.querySelector('.offline-telemetry-msg');

        if (history.length === 0) {
            canvas.style.display = 'none';
            if (!offlineMsg) {
                offlineMsg = document.createElement('div');
                offlineMsg.className = 'offline-telemetry-msg';
                offlineMsg.style.cssText = "display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #94a3b8; font-weight: 700; font-family: 'JetBrains Mono', 'Courier New', monospace;";
                offlineMsg.innerHTML = `<i class="fas fa-satellite-dish" style="font-size: 3.5rem; margin-bottom: 20px; opacity: 0.3; color: #64748b;"></i><span style="letter-spacing: 0.15em; font-size: 0.9rem;">[ TELEMETRÍA OFFLINE ]</span><span style="font-size: 0.75rem; font-weight: 500; margin-top: 8px; opacity: 0.8;">Esperando inicialización de sondas de red...</span>`;
                container.appendChild(offlineMsg);
            }
            offlineMsg.style.display = 'flex';
            if (headerTitle) {
                headerTitle.style.display = 'flex';
                headerTitle.style.justifyContent = 'flex-start';
                headerTitle.innerHTML = `<i class="fas fa-chart-area" style="color: #6366f1;"></i> Análisis de Salud de Red (LHI)`;
            }
            return;
        }

        canvas.style.display = 'block';
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        if (offlineMsg) offlineMsg.style.display = 'none';

        const ctx = canvas.getContext('2d');

        // Cálculo algorítmico del LHI (Link Health Index) basado en ingeniería de tráfico
        let totalScore = 0;
        let validSamples = 0;

        history.forEach(h => {
            if (!h.is_online) return;
            validSamples++;
            let sampleScore = 100;

            // Penalización logarítmica/proporcional por latencia térmica
            if (h.latency_ms > 40) {
                sampleScore -= Math.min(30, (h.latency_ms - 40) * 0.25);
            }

            // Penalización por fluctuación de fase (Jitter)
            if (h.jitter_ms > 8) {
                sampleScore -= Math.min(25, (h.jitter_ms - 8) * 0.8);
            }

            // Penalización severa por Packet Loss (Micro-cortes)
            if (h.packet_loss_pct > 0) {
                sampleScore -= Math.min(100, h.packet_loss_pct * 8); // 12.5% loss = 0 score
            }

            totalScore += Math.max(0, sampleScore);
        });

        const finalLhi = validSamples > 0 ? Math.round(totalScore / validSamples) : 0;

        if (headerTitle) {
            const lhiColor = finalLhi >= 90 ? '#10b981' : (finalLhi >= 70 ? '#f59e0b' : '#ef4444');
            const lhiBgColor = finalLhi >= 90 ? '16, 185, 129' : (finalLhi >= 70 ? '245, 158, 11' : '239, 68, 68');
            const lhiStatus = finalLhi >= 90 ? 'OPTIMAL' : (finalLhi >= 70 ? 'DEGRADED' : 'CRITICAL');

            headerTitle.style.display = 'flex';
            headerTitle.style.justifyContent = 'space-between';
            headerTitle.style.width = '100%';
            headerTitle.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <i class="fas fa-satellite-dish" style="color: #6366f1;"></i> 
                    <span>Métricas de Vuelo (Telemetría de Enlace)</span>
                </div>
                <div style="margin-left: auto; display: flex; align-items: center; gap: 12px; font-family: 'JetBrains Mono', 'Courier New', monospace;">
                    <span style="font-size: 0.7rem; font-weight: 800; color: #94a3b8; letter-spacing: 0.1em; text-transform: uppercase;">Health Index:</span>
                    <div style="background: rgba(${lhiBgColor}, 0.1); border: 1px solid rgba(${lhiBgColor}, 0.3); border-radius: 8px; padding: 4px 12px; display: flex; align-items: center; gap: 8px; box-shadow: inset 0 0 10px rgba(${lhiBgColor}, 0.05);">
                        <span style="font-size: 1.15rem; font-weight: 900; color: ${lhiColor};">${finalLhi}<span style="font-size: 0.7rem; opacity:0.6;">/100</span></span>
                        <div style="width: 1px; height: 16px; background: ${lhiColor}; opacity: 0.3;"></div>
                        <span style="font-size: 0.65rem; font-weight: 900; letter-spacing: 0.1em; color: ${lhiColor}; text-shadow: 0 0 8px rgba(${lhiBgColor}, 0.6);">${lhiStatus}</span>
                    </div>
                </div>
            `;
        }

        const labels = history.map(h => {
            const d = new Date(h.timestamp);
            return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
        });

        const latencyData = history.map(h => h.latency_ms);
        const jitterData = history.map(h => h.jitter_ms || 0);
        const lossData = history.map(h => h.packet_loss_pct || 0);

        // Gradients (Neon Vibes)
        const gradientLatency = ctx.createLinearGradient(0, 0, 0, 400);
        gradientLatency.addColorStop(0, 'rgba(99, 102, 241, 0.45)');
        gradientLatency.addColorStop(1, 'rgba(99, 102, 241, 0.0)');

        const gradientLoss = ctx.createLinearGradient(0, 0, 0, 400);
        gradientLoss.addColorStop(0, 'rgba(239, 68, 68, 0.35)');
        gradientLoss.addColorStop(1, 'rgba(239, 68, 68, 0.0)');

        try {
            this.stabilityChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'LATENCIA REAL (ms)',
                            data: latencyData,
                            borderColor: '#6366f1',
                            backgroundColor: gradientLatency,
                            borderWidth: 3,
                            pointBackgroundColor: '#ffffff',
                            pointBorderColor: '#6366f1',
                            pointBorderWidth: 2,
                            pointRadius: 0,
                            pointHoverRadius: 6,
                            fill: true,
                            tension: 0.4,
                            yAxisID: 'y'
                        },
                        {
                            label: 'JITTER DE ONDA (ms)',
                            data: jitterData,
                            borderColor: '#10b981',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            pointRadius: 0,
                            pointHoverRadius: 5,
                            fill: false,
                            tension: 0.4,
                            yAxisID: 'y'
                        },
                        {
                            label: 'PÉRDIDA DE PAQUETES (%)',
                            data: lossData,
                            borderColor: '#ef4444',
                            backgroundColor: gradientLoss,
                            borderWidth: 2,
                            fill: true,
                            stepped: 'middle',
                            yAxisID: 'y1',
                            pointBackgroundColor: '#ef4444',
                            pointRadius: history.map(h => h.packet_loss_pct > 0 ? 4 : 0),
                            pointHoverRadius: 6
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: {
                                font: { family: "'JetBrains Mono', 'Courier New', monospace", size: 10, weight: 'bold' },
                                usePointStyle: true,
                                boxWidth: 8,
                                padding: 20
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(15, 23, 42, 0.95)',
                            titleFont: { family: "'JetBrains Mono', 'Courier New', monospace", size: 12 },
                            bodyFont: { family: "'JetBrains Mono', 'Courier New', monospace", size: 11 },
                            padding: 14,
                            cornerRadius: 12,
                            displayColors: true,
                            borderColor: 'rgba(255,255,255,0.1)',
                            borderWidth: 1,
                            callbacks: {
                                label: function (context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed.y !== null) {
                                        label += context.parsed.y + (context.dataset.yAxisID === 'y1' ? '%' : 'ms');
                                    }
                                    return label;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'TIEMPO (ms)', font: { family: "'JetBrains Mono', 'Courier New', monospace", size: 10, weight: 'bold' }, color: '#64748b' },
                            grid: { color: 'rgba(226, 232, 240, 0.6)', borderDash: [4, 4] },
                            ticks: { font: { family: "'JetBrains Mono', 'Courier New', monospace", size: 10 }, color: '#94a3b8' }
                        },
                        y1: {
                            beginAtZero: true,
                            max: 100,
                            position: 'right',
                            title: { display: true, text: 'PÉRDIDA (%)', font: { family: "'JetBrains Mono', 'Courier New', monospace", size: 10, weight: 'bold' }, color: '#ef4444' },
                            grid: { drawOnChartArea: false },
                            ticks: { font: { family: "'JetBrains Mono', 'Courier New', monospace", size: 10 }, color: '#ef4444' }
                        },
                        x: {
                            grid: { color: 'rgba(226, 232, 240, 0.6)', drawBorder: false },
                            ticks: {
                                font: { family: "'JetBrains Mono', 'Courier New', monospace", size: 10 },
                                color: '#94a3b8',
                                maxRotation: 0,
                                autoSkip: true,
                                maxTicksLimit: 12
                            }
                        }
                    }
                }
            });
        } catch (e) {
            console.error("Chart.js Error in renderStabilityChart:", e);
            if (headerTitle) {
                headerTitle.innerHTML = `<span style="color:red; font-size:12px;">CHART ERROR: ${e.message}</span>`;
            }
        }
    }

    async adjustBalance() {
        if (!this.currentClient) return;
        if (!window.Swal) {
            toast.error('Sistema de diálogos no disponible');
            return;
        }

        const { value: formValues } = await window.Swal.fire({
            title: 'Corregir Balance Manualmente',
            html:
                `<div>
                    <label style="display:block; text-align:left; font-weight:700; margin-bottom:8px; font-size:0.85rem;">Nuevo Balance ($)</label>
                    <input id="swal-new-balance" class="swal2-input" type="number" step="1" style="margin:0; width:100% !important; border-radius:12px;" value="${this.currentClient.account_balance || 0}">
                </div>
                <div style="margin-top:20px;">
                    <label style="display:block; text-align:left; font-weight:700; margin-bottom:8px; font-size:0.85rem;">Motivo del Ajuste</label>
                    <textarea id="swal-reason" class="swal2-textarea" style="margin:0; width:100% !important; border-radius:12px; height:80px;" placeholder="Ej: Error en facturación duplicada"></textarea>
                </div>`,
            focusConfirm: false,
            showCancelButton: true,
            confirmButtonText: 'Confirmar Ajuste',
            cancelButtonText: 'Cancelar',
            preConfirm: () => {
                const newBalance = document.getElementById('swal-new-balance').value;
                const reason = document.getElementById('swal-reason').value;
                if (newBalance === "") {
                    window.Swal.showValidationMessage('El balance es requerido');
                    return false;
                }
                return { newBalance, reason };
            }
        });

        if (formValues) {
            try {
                if (window.app && window.app.showLoading) window.app.showLoading(true);
                const response = await apiService.post(`/api/clients/${this.currentClient.id}/adjust-balance`, {
                    new_balance: formValues.newBalance,
                    reason: formValues.reason
                });

                if (response.error) throw new Error(response.error);

                toast.success('Balance ajustado correctamente');

                // Actualizar cliente local y vista
                this.currentClient.account_balance = parseFloat(formValues.newBalance);
                this.loadClientData(this.currentClient);

                // Emitir evento para refrescar lista de clientes si es necesario
                if (window.app && window.app.refreshList) {
                    window.app.refreshList();
                }

            } catch (error) {
                console.error('Error adjusting balance:', error);
                toast.error(error.message || 'Error al ajustar balance');
            } finally {
                if (window.app && window.app.showLoading) window.app.showLoading(false);
            }
        }
    }

    renderStabilityTable(history) {
        const container = document.getElementById('stability-history-table-container');
        if (!container) return;

        if (!history || history.length === 0) {
            container.innerHTML = '<div style="padding: 40px; text-align: center; color: #94a3b8; font-weight: 600;"><i class="fas fa-satellite-dish" style="font-size: 2.5rem; margin-bottom: 16px; opacity: 0.3; display: block;"></i>Sin datos de telemetría suficientes para el análisis predictivo</div>';
            return;
        }

        let html = `
            <table style="width: 100%; border-collapse: separate; border-spacing: 0; text-align: left;">
                <thead style="background: rgba(248, 250, 252, 0.95); position: sticky; top: 0; backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); z-index: 10;">
                    <tr>
                        <th style="padding: 16px 24px; font-size: 0.7rem; text-transform: uppercase; font-weight: 800; color: #64748b; border-bottom: 1px solid rgba(226, 232, 240, 0.8); letter-spacing: 0.08em;"><i class="fas fa-clock" style="margin-right: 6px; opacity:0.7;"></i> Trace Time (TS)</th>
                        <th style="padding: 16px 24px; font-size: 0.7rem; text-transform: uppercase; font-weight: 800; color: #64748b; border-bottom: 1px solid rgba(226, 232, 240, 0.8); letter-spacing: 0.08em;"><i class="fas fa-bolt" style="margin-right: 6px; opacity:0.7;"></i> Latencia Real</th>
                        <th style="padding: 16px 24px; font-size: 0.7rem; text-transform: uppercase; font-weight: 800; color: #64748b; border-bottom: 1px solid rgba(226, 232, 240, 0.8); letter-spacing: 0.08em;"><i class="fas fa-wave-square" style="margin-right: 6px; opacity:0.7;"></i> Jitter (Desviación)</th>
                        <th style="padding: 16px 24px; font-size: 0.7rem; text-transform: uppercase; font-weight: 800; color: #64748b; border-bottom: 1px solid rgba(226, 232, 240, 0.8); letter-spacing: 0.08em;"><i class="fas fa-box-open" style="margin-right: 6px; opacity:0.7;"></i> Packet Loss</th>
                        <th style="padding: 16px 24px; font-size: 0.7rem; text-transform: uppercase; font-weight: 800; color: #64748b; border-bottom: 1px solid rgba(226, 232, 240, 0.8); letter-spacing: 0.08em;"><i class="fas fa-microchip" style="margin-right: 6px; opacity:0.7;"></i> Estado del Vector</th>
                    </tr>
                </thead>
                <tbody>
        `;

        // Mostrar últimos 50 registros
        history.slice().reverse().slice(0, 50).forEach(h => {
            const d = new Date(h.timestamp);
            const dateStr = `${d.getDate().toString().padStart(2, '0')}/${(d.getMonth() + 1).toString().padStart(2, '0')}/${d.getFullYear()} <span style="color:#94a3b8;margin-left:5px;">${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}</span>`;

            const isOnline = h.is_online;
            const latency = h.latency_ms;
            const jitter = h.jitter_ms || 0;
            const loss = h.packet_loss_pct || 0;

            let statusBadge = isOnline ?
                '<span style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; background: rgba(16, 185, 129, 0.1); color: #10b981; border-radius: 20px; font-size: 0.7rem; font-weight: 800; border: 1px solid rgba(16, 185, 129, 0.2); letter-spacing: 0.05em; text-transform: uppercase;"><div style="width: 6px; height: 6px; background: #10b981; border-radius: 50%; box-shadow: 0 0 8px #10b981; animation: pulse 2s infinite;"></div> LINK ACTIVE</span>' :
                '<span style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; background: rgba(239, 68, 68, 0.1); color: #ef4444; border-radius: 20px; font-size: 0.7rem; font-weight: 800; border: 1px solid rgba(239, 68, 68, 0.2); letter-spacing: 0.05em; text-transform: uppercase;"><div style="width: 6px; height: 6px; background: #ef4444; border-radius: 50%; box-shadow: 0 0 8px #ef4444;"></div> CRITICAL FAULT</span>';

            let latencyColor = latency < 50 ? '#10b981' : (latency < 150 ? '#f59e0b' : '#ef4444');
            let lossColor = loss === 0 ? '#10b981' : (loss < 5 ? '#f59e0b' : '#ef4444');

            html += `
                <tr style="transition: all 0.2s ease; cursor: default; border-bottom: 1px solid #f8fafc;" onmouseover="this.style.background='rgba(241, 245, 249, 0.5)'" onmouseout="this.style.background='transparent'">
                    <td style="padding: 16px 24px; border-bottom: 1px solid rgba(226, 232, 240, 0.4); font-family: 'JetBrains Mono', 'Courier New', monospace; font-size: 0.8rem; color: #475569;">${dateStr}</td>
                    <td style="padding: 16px 24px; border-bottom: 1px solid rgba(226, 232, 240, 0.4);">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-weight: 800; color: ${latencyColor}; font-family: 'JetBrains Mono', 'Courier New', monospace; font-size: 0.95rem;">${latency}<span style="font-size: 0.7rem; color: #94a3b8; margin-left:3px; font-weight:600;">ms</span></span>
                            ${latency < 50 ? '<i class="fas fa-check-circle" style="color: #10b981; font-size: 0.85rem;" title="Óptimo"></i>' : (latency < 150 ? '<i class="fas fa-exclamation-triangle" style="color: #f59e0b; font-size: 0.85rem;" title="Degradado"></i>' : '<i class="fas fa-times-octagon" style="color: #ef4444; font-size: 0.85rem;" title="Crítico"></i>')}
                        </div>
                    </td>
                    <td style="padding: 16px 24px; border-bottom: 1px solid rgba(226, 232, 240, 0.4); color: #64748b; font-family: 'JetBrains Mono', 'Courier New', monospace; font-size: 0.85rem;">
                        <span style="background: rgba(148, 163, 184, 0.1); padding: 2px 6px; border-radius: 6px; border: 1px solid rgba(148, 163, 184, 0.2);">±${jitter}<span style="font-size: 0.7rem; margin-left:2px;">ms</span></span>
                    </td>
                    <td style="padding: 16px 24px; border-bottom: 1px solid rgba(226, 232, 240, 0.4);">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <div style="flex: 1; height: 6px; background: #e2e8f0; border-radius: 10px; overflow: hidden; max-width: 60px; box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);">
                                <div style="height: 100%; width: ${Math.min(loss, 100)}%; background: ${lossColor}; border-radius: 10px; transition: width 0.5s ease;"></div>
                            </div>
                            <span style="font-weight: 800; color: ${lossColor}; font-family: 'JetBrains Mono', 'Courier New', monospace; font-size: 0.85rem;">${loss}%</span>
                        </div>
                    </td>
                    <td style="padding: 16px 24px; border-bottom: 1px solid rgba(226, 232, 240, 0.4);">${statusBadge}</td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        container.innerHTML = html;
    }
}

// Crear instancia global
window.clientModal = new ClientModal();

export default window.clientModal;
