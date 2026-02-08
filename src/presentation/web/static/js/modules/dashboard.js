/**
 * Dashboard Module - Vista Principal
 */
export class DashboardModule {
    constructor(api, eventBus) {
        this.api = api;
        this.eventBus = eventBus;
        this.servers = [];
        this.dashboardChart = null;
        this.dashboardInterval = null;


        console.log('📊 Dashboard Module initialized');
    }

    async load() {
        console.log('📊 Loading Dashboard...');

        // Mostrar vista
        this.showView();

        // Cargar datos
        await Promise.all([
            this.loadStats(),
            this.loadServers(),
            this.loadActivity(),
            this.initDashboardChart()
        ]);

        this.startDashboardMonitoring();
        this.startServerAutoRefresh();
    }


    showView() {
        // Delegar visualización a ViewManager
        this.viewManager.showMainView('dashboard');
    }

    async loadStats() {
        try {
            const stats = await this.api.get('/api/dashboard/stats');
            this.renderStats(stats);
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    async loadServers() {
        try {
            // Cargar datos rápidos de la BD primero
            const servers = await this.api.get('/api/routers');
            this.servers = servers;
            this.renderServers();

            // Inmediatamente intentar refrescar el estado "Live"
            this.refreshLiveStatus();
        } catch (error) {
            console.error('Error loading servers:', error);
            this.servers = [];
        }
    }

    async refreshLiveStatus() {
        try {
            // El monitor también actualiza la BD en el backend
            const liveInfo = await this.api.get('/api/routers/monitor');

            // Actualizar solo los campos que cambiaron en nuestro array local
            liveInfo.forEach(info => {
                const sIdx = this.servers.findIndex(s => s.id === info.id);
                if (sIdx !== -1) {
                    this.servers[sIdx] = { ...this.servers[sIdx], ...info };
                }
            });

            this.renderServers();
        } catch (e) {
            console.error("Error refreshing live status", e);
        }
    }

    async loadActivity() {
        try {
            const activity = await this.api.get('/api/activity/recent');
            this.renderActivity(activity);
        } catch (error) {
            console.error('Error loading activity:', error);
        }
    }

    renderStats(stats) {
        // Actualizar tarjetas de estadísticas
        const statServers = document.getElementById('stat-servers');
        const statClients = document.getElementById('stat-clients');
        const statSuspended = document.getElementById('stat-suspended');
        const statRevenue = document.getElementById('stat-revenue');
        const statUptime = document.getElementById('stat-uptime');
        const statDebt = document.getElementById('stat-debt');
        const statDebtClients = document.getElementById('stat-debt-clients');

        if (statServers) statServers.textContent = stats.total_servers || 0;
        if (statClients) {
            statClients.textContent = stats.active_clients || 0;
            const subtext = document.getElementById('stat-clients-subtext');
            if (subtext) subtext.textContent = `Total Base: ${stats.total_clients || 0}`;
        }
        if (statSuspended) {
            statSuspended.textContent = stats.suspended_clients || 0;
            const moraClients = document.getElementById('stat-mora-clients');
            if (moraClients) moraClients.textContent = stats.pending_debt_clients || 0;
        }
        if (statRevenue) {
            const revenueVal = stats.monthly_revenue || 0;
            const projectedVal = stats.projected_revenue || 0;

            statRevenue.textContent = `$${revenueVal.toLocaleString('es-CO')}`;

            // Si la recaudación es 0, mostrar la proyectada como mensaje de ayuda
            if (revenueVal === 0 && projectedVal > 0) {
                const subtext = document.getElementById('stat-revenue-subtext');
                if (subtext) {
                    subtext.textContent = `Proyectado: $${projectedVal.toLocaleString('es-CO')}`;
                    subtext.parentElement.classList.add('has-projection');
                }
            }
        }
        if (statUptime) statUptime.textContent = `${(stats.average_uptime || 0).toFixed(1)}%`;

        // Debt Stats
        if (statDebt) statDebt.textContent = `$${(stats.total_pending_debt || 0).toLocaleString('es-CO')}`;
        if (statDebtClients) statDebtClients.textContent = stats.pending_debt_clients || 0;

        // Actualizar contadores de estado
        const serversOnline = document.getElementById('servers-online');
        const serversWarning = document.getElementById('servers-warning');
        const serversOffline = document.getElementById('servers-offline');

        if (serversOnline) serversOnline.textContent = stats.servers_online || 0;
        if (serversWarning) serversWarning.textContent = stats.servers_warning || 0;
        if (serversOffline) serversOffline.textContent = stats.servers_offline || 0;
    }

    startServerAutoRefresh() {
        if (this.serverRefreshInterval) clearInterval(this.serverRefreshInterval);

        this.serverRefreshInterval = setInterval(async () => {
            const view = document.getElementById('dashboard-view');
            if (view && view.classList.contains('active')) {
                // Alternamos entre carga rápida y monitoreo real
                await this.loadServers();
                // await this.loadStats(); // loadStats ya lo llama el loop principal si es necesario
            } else {
                clearInterval(this.serverRefreshInterval);
                this.serverRefreshInterval = null;
            }
        }, 15000); // Refrescar cada 15s (el monitor tarda un poco)
    }

    async renderServers() {
        const container = document.getElementById('servers-list');
        if (!container) return;

        if (this.servers.length === 0) {
            container.innerHTML = '<p style="color: rgba(255,255,255,0.5); padding: 1rem;">No hay routers configurados</p>';
            return;
        }

        container.innerHTML = `
            <table class="premium-table" style="width: 100%; border-collapse: separate; border-spacing: 0;">
                <tbody>
                    ${this.servers.map(server => `
                        <tr class="server-row" style="transition: all 0.2s;">
                            <td style="padding: 10px 16px; border-bottom: 1px solid #f1f5f9; width: 50%;" onclick="app.modules.dashboard.showRouterDetails(${server.id})">
                                <div style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
                                    <span class="status-dot-mini ${server.status || 'offline'}" title="${server.status || 'offline'}"></span>
                                    <div style="display: flex; flex-direction: column; align-items: flex-start; gap: 0;">
                                        <span style="font-weight: 750; color: #1e293b; font-size: 0.85rem; text-transform: uppercase;">${server.alias || 'Sin nombre'}</span>
                                        <span style="color: #94a3b8; font-size: 0.7rem; font-family: 'JetBrains Mono', monospace;">${server.host_address || 'N/A'}</span>
                                    </div>
                                    ${server.status === 'offline' ? `
                                        <div class="warning-pulse" onclick="event.stopPropagation(); app.modules.dashboard.showConnectionError(${server.id})" style="cursor:pointer; margin-left: 10px;" title="Error de conexión">
                                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                                        </div>
                                    ` : ''}
                                </div>
                            </td>
                            <td style="padding: 10px 16px; border-bottom: 1px solid #f1f5f9; text-align: right; vertical-align: middle;">
                                <div style="display: flex; align-items: center; justify-content: flex-end; gap: 8px;">
                                    
                                    <!-- Clients Badge -->
                                    <span style="font-weight: 700; color: #6366f1; background: #f5f3ff; padding: 4px 12px; border-radius: 12px; font-size: 0.75rem; margin-right: 8px;">
                                        ${server.clients_connected || 0} <span style="font-weight: 600; color: #a5b4fc; font-size: 0.7rem;">clientes</span>
                                    </span>

                                    <!-- Actions -->
                                    <button class="action-btn-xs minimal" onclick="event.stopPropagation(); app.modules.dashboard.showRouterGraph(${server.id}, '${server.alias}')" title="Ver Gráficas" style="padding: 4px; background: transparent; border: none; color: #cbd5e1; cursor: pointer;">
                                        <i class="fas fa-chart-line" style="font-size: 0.8rem;"></i>
                                    </button>
                                    
                                    <button class="action-btn-xs minimal" onclick="event.stopPropagation(); app.modules.dashboard.syncRouter(${server.id})" title="Sincronizar" style="padding: 4px; background: transparent; border: none; color: #cbd5e1; cursor: pointer;">
                                        <i class="fas fa-sync-alt" style="font-size: 0.8rem;"></i>
                                    </button>
                                    
                                    <button class="action-btn-xs minimal" onclick="event.stopPropagation(); app.modules.dashboard.confirmReboot(${server.id}, '${server.alias}')" title="Reiniciar" style="padding: 4px; background: transparent; border: none; color: #cbd5e1; cursor: pointer;">
                                        <i class="fas fa-power-off" style="font-size: 0.8rem;"></i>
                                    </button>

                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        // Inject Modal if not exists
        if (!document.getElementById('router-graph-modal')) {
            const modalHTML = `
                <div id="router-graph-modal" class="modal">
                    <div class="modal-content large-modal">
                        <div class="modal-header">
                            <div>
                                <h3 id="graph-modal-title">Tráfico en Tiempo Real</h3>
                                <p id="graph-modal-subtitle" style="margin: 0; font-size: 0.8rem; color: #64748b;"></p>
                            </div>
                            <button class="close-btn" onclick="app.modules.dashboard.closeGraphModal()">×</button>
                        </div>
                        <div class="modal-body" style="display: flex; flex-direction: column; gap: 1rem;">
                            <div style="display: grid; grid-template-columns: 300px 1fr; gap: 1.5rem; height: 100%;">
                                <!-- Selector Lateral -->
                                <div style="display: flex; flex-direction: column; gap: 0.8rem; background: #f8fafc; padding: 1rem; border-radius: 12px; border: 1px solid #e2e8f0;">
                                    <h4 style="margin: 0; font-size: 0.9rem; color: #1e293b;">Interfaces Disponibles</h4>
                                    <div id="interfaces-selection-list" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 0.5rem;">
                                        <!-- Se llena dinámicamente -->
                                    </div>
                                    <button class="btn-primary" style="width: 100%; font-size: 0.85rem;" onclick="app.modules.dashboard.savePreferences()">
                                        <i class="fas fa-save" style="margin-right: 5px;"></i> Guardar Cambios
                                    </button>
                                </div>
                                
                                <!-- Gráficas en Cuadros Grandes -->
                                <div id="router-charts-container" style="flex: 1; display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 1.5rem; background: #f8fafc; border-radius: 12px; padding: 1.5rem; border: 1px solid #e2e8f0; overflow-y: auto; max-height: 82vh; align-content: start;">
                                    <!-- Se llenan dinámicamente -->
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', modalHTML);
        }

        // Inject Router Details Modal (Premium UI)
        if (!document.getElementById('router-details-modal')) {
            const detailsModalHTML = `
                <div id="router-details-modal" class="modal">
                    <div class="modal-content" style="max-width: 1400px; width: 95%; height: 85vh; display: flex; flex-direction: column; border-radius: 24px; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);">
                        <div class="modal-header" style="background: linear-gradient(to right, #ffffff, #f8fafc); border-bottom: 1px solid #e2e8f0; padding: 1.5rem 2rem; flex-shrink: 0;">
                            <div style="display: flex; flex-direction: column;">
                                <h3 id="details-modal-title" style="font-size: 1.5rem; background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0; font-weight: 800; letter-spacing: -0.5px;">Detalles del Router</h3>
                                <div style="display: flex; align-items: center; gap: 8px; margin-top: 6px;">
                                    <span class="status-dot-mini" id="details-header-status-dot"></span>
                                    <p id="details-modal-subtitle" style="margin:0; font-size:0.9rem; color:#64748b; font-family: 'JetBrains Mono', monospace;"></p>
                                </div>
                            </div>
                            <button class="close-btn" onclick="app.modules.dashboard.closeDetailsModal()" style="background: white; border: 1px solid #e2e8f0; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #64748b; transition: all 0.2s; cursor: pointer;">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                        <div class="modal-body" style="background: #f8fafc; padding: 0; flex: 1; overflow-y: auto; display: flex; flex-direction: column;">
                            <div class="modal-tabs" style="padding: 0 2rem; background: white; border-bottom: 1px solid #e2e8f0; margin: 0;">
                                <button class="tab-btn active" onclick="app.modules.dashboard.switchTab(event, 'tab-info')" style="padding: 1rem 0; margin-right: 2rem;">Información General</button>
                                <button class="tab-btn" onclick="app.modules.dashboard.switchTab(event, 'tab-clients')" style="padding: 1rem 0;">Clientes Conectados</button>
                            </div>

                            <div id="tab-info" class="tab-content active" style="padding: 1.5rem;">
                                <div class="info-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;">
                                    <!-- Tarjetas de Información -->
                                    <div class="info-card" style="padding: 12px; display: flex; align-items: center; gap: 10px; background: white; border: 1px solid #e2e8f0; border-radius: 12px;">
                                        <div class="info-icon blue" style="width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: rgba(59, 130, 246, 0.1); border-radius: 8px; color: #2563eb;"><i class="fas fa-server"></i></div>
                                        <div class="info-data" style="display: flex; flex-direction: column;">
                                            <span class="info-label" style="font-size: 0.7rem; color: #64748b; font-weight: 600;">ALIAS / NOMBRE</span>
                                            <span class="info-value text-dark" id="detail-alias" style="font-weight: 700; font-size: 0.9rem;">--</span>
                                        </div>
                                    </div>

                                    <div class="info-card" style="padding: 12px; display: flex; align-items: center; gap: 10px; background: white; border: 1px solid #e2e8f0; border-radius: 12px;">
                                        <div class="info-icon purple" style="width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: rgba(139, 92, 246, 0.1); border-radius: 8px; color: #7c3aed;"><i class="fas fa-network-wired"></i></div>
                                        <div class="info-data" style="display: flex; flex-direction: column;">
                                            <span class="info-label" style="font-size: 0.7rem; color: #64748b; font-weight: 600;">DIRECCIÓN IP</span>
                                            <span class="info-value font-mono" id="detail-host" style="font-weight: 700; font-size: 0.9rem;">--</span>
                                        </div>
                                    </div>

                                    <div class="info-card" style="padding: 12px; display: flex; align-items: center; gap: 10px; background: white; border: 1px solid #e2e8f0; border-radius: 12px;">
                                        <div class="info-icon green" style="width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: rgba(16, 185, 129, 0.1); border-radius: 8px; color: #059669;"><i class="fas fa-map-marker-alt"></i></div>
                                        <div class="info-data" style="display: flex; flex-direction: column;">
                                            <span class="info-label" style="font-size: 0.7rem; color: #64748b; font-weight: 600;">ZONA / UBICACIÓN</span>
                                            <span class="info-value" id="detail-zone" style="font-weight: 700; font-size: 0.9rem;">--</span>
                                        </div>
                                    </div>

                                    <div class="info-card" style="padding: 12px; display: flex; align-items: center; gap: 10px; background: white; border: 1px solid #e2e8f0; border-radius: 12px;">
                                        <div class="info-icon orange" style="width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: rgba(249, 115, 22, 0.1); border-radius: 8px; color: #ea580c;"><i class="fas fa-heartbeat"></i></div>
                                        <div class="info-data" style="display: flex; flex-direction: column;">
                                            <span class="info-label" style="font-size: 0.7rem; color: #64748b; font-weight: 600;">ESTADO ACTUAL</span>
                                            <span class="info-value" id="detail-status" style="font-weight: 700; font-size: 0.9rem;">--</span>
                                        </div>
                                    </div>

                                    <div class="info-card" style="padding: 12px; display: flex; align-items: center; gap: 10px; background: white; border: 1px solid #e2e8f0; border-radius: 12px;">
                                        <div class="info-icon" style="width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: #f1f5f9; border-radius: 8px; color: #64748b;"><i class="fas fa-plug"></i></div>
                                        <div class="info-data" style="display: flex; flex-direction: column;">
                                            <span class="info-label" style="font-size: 0.7rem; color: #64748b; font-weight: 600;">API PORT</span>
                                            <span class="info-value font-mono" id="detail-api-port" style="font-weight: 700; font-size: 0.9rem;">--</span>
                                        </div>
                                    </div>

                                    <div class="info-card" style="padding: 12px; display: flex; align-items: center; gap: 10px; background: white; border: 1px solid #e2e8f0; border-radius: 12px;">
                                        <div class="info-icon" style="width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: #f1f5f9; border-radius: 8px; color: #64748b;"><i class="fas fa-terminal"></i></div>
                                        <div class="info-data" style="display: flex; flex-direction: column;">
                                            <span class="info-label" style="font-size: 0.7rem; color: #64748b; font-weight: 600;">SSH PORT</span>
                                            <span class="info-value font-mono" id="detail-ssh-port" style="font-weight: 700; font-size: 0.9rem;">--</span>
                                        </div>
                                    </div>
                                    
                                    <!-- Configuración de Facturación (Compacta y Distribuida) -->
                                    <div class="info-card full-width" style="grid-column: span 3; background: white; border: 1px solid #e2e8f0; border-left: 3px solid #6366f1; border-radius: 12px; padding: 12px;">
                                        <div style="display: flex; align-items: center; justify-content: space-between; gap: 20px;">
                                            <div style="display: flex; align-items: center; gap: 8px; min-width: 180px;">
                                                <div style="background: rgba(99, 102, 241, 0.1); color: #6366f1; width: 32px; height: 32px; border-radius: 6px; display: flex; align-items: center; justify-content: center;"><i class="fas fa-file-invoice-dollar"></i></div>
                                                <span style="font-size: 0.85rem; font-weight: 700; color: #1e293b;">Configuración Zona</span>
                                            </div>
                                            
                                            <div style="display: flex; align-items: center; justify-content: space-evenly; flex: 1; padding: 0 40px;">
                                                <div style="display: flex; flex-direction: column; align-items: center; gap: 4px;">
                                                    <span style="font-size: 0.75rem; color: #64748b; font-weight: 500;">Día Factura</span>
                                                    <input type="number" id="edit-billing-day" class="input-premium small center-text" style="width: 80px; padding: 6px; font-size: 0.9rem; text-align: center; border: 1px solid #e2e8f0; border-radius: 8px;" min="1" max="31">
                                                </div>
                                                <div style="display: flex; flex-direction: column; align-items: center; gap: 4px;">
                                                    <span style="font-size: 0.75rem; color: #64748b; font-weight: 500;">Días Gracia</span>
                                                    <input type="number" id="edit-grace-period" class="input-premium small center-text" style="width: 80px; padding: 6px; font-size: 0.9rem; text-align: center; border: 1px solid #e2e8f0; border-radius: 8px;" min="0" max="30">
                                                </div>
                                                <div style="display: flex; flex-direction: column; align-items: center; gap: 4px;">
                                                    <span style="font-size: 0.75rem; color: #64748b; font-weight: 500;">Día Corte</span>
                                                    <input type="number" id="edit-cut-day" class="input-premium small center-text" style="width: 80px; padding: 6px; font-size: 0.9rem; text-align: center; border: 1px solid #e2e8f0; border-radius: 8px;" min="1" max="31">
                                                </div>
                                            </div>

                                            <button onclick="app.modules.dashboard.saveRouterBillingConfig()" class="btn-primary small" style="padding: 8px 20px; font-size: 0.8rem; white-space: nowrap;">
                                                Guardar
                                            </button>
                                        </div>
                                    </div>

                                    <!-- Notas full width -->
                                    <div class="info-card full-width" style="grid-column: span 3; background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px; display: flex; gap: 12px;">
                                        <div class="info-icon gray" style="color: #94a3b8; width: 24px;"><i class="fas fa-sticky-note"></i></div>
                                        <div class="info-data" style="width: 100%;">
                                            <span class="info-label" style="font-size: 0.7rem; color: #64748b; font-weight: 600;">NOTAS Y OBSERVACIONES</span>
                                            <p class="info-value notes-text" id="detail-notes" style="margin: 4px 0 0 0; line-height: 1.4; color: #475569; font-size: 0.85rem;">--</p>
                                        </div>
                                    </div>
                                </div>
                            </div>                            
                            <!-- Tab: Clients -->
                            <div id="tab-clients" class="tab-content" style="padding: 2rem;">
                                <!-- content kept same but wrapped in padding -->
                                <div id="router-clients-loading" style="text-align:center; padding: 2rem; color: #64748b;">
                                    <div class="spinner-mini" style="margin-bottom: 10px;"></div>
                                    Cargando clientes de este router...
                                </div>
                                <div id="router-clients-list" style="max-height: 400px; overflow-y: auto;">
                                    <table class="premium-table" style="width: 100%;">
                                        <thead>
                                            <tr>
                                                <th style="text-align:left; padding: 12px;">Código</th>
                                                <th style="text-align:left; padding: 12px;">Nombre Legal</th>
                                                <th style="text-align:left; padding: 12px;">IP</th>
                                                <th style="text-align:right; padding: 12px;">Plan</th>
                                            </tr>
                                        </thead>
                                        <tbody id="router-clients-table-body">
                                            <!-- Se llena dinámicamente -->
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', detailsModalHTML);
        }

        // ... (Error Info Modal remains unchanged) ...
        if (!document.getElementById('router-error-modal')) {
            // ... existing error modal code ...
            const errorModalHTML = `
                <div id="router-error-modal" class="modal">
                    <div class="modal-content" style="max-width: 500px; padding:0; border-radius: 16px; overflow: hidden;">
                        <div class="modal-header error-header">
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <div style="background: rgba(255,255,255,0.2); border-radius: 50%; padding: 6px; display: flex;">
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                                </div>
                                <h3 style="margin:0;">Error de Conexión</h3>
                            </div>
                            <button class="close-btn" onclick="app.modules.dashboard.closeErrorModal()">×</button>
                        </div>
                        <div class="modal-body" style="padding: 24px;">
                            <div style="display: flex; flex-direction: column; gap: 20px;">
                                <div id="error-router-name" style="font-weight: 800; font-size: 1.25rem; color: #1e293b;"></div>
                                
                                <div class="error-alert-box">
                                    <label class="error-alert-label">Posible Causa</label>
                                    <p id="error-message" class="error-alert-message"></p>
                                </div>

                                <div class="error-stats-grid">
                                    <div class="error-stat-item">
                                        <label class="error-stat-label">Última vez Online</label>
                                        <p id="error-last-online" class="error-stat-value"></p>
                                    </div>
                                    <div class="error-stat-item">
                                        <label class="error-stat-label">Tiempo desconectado</label>
                                        <p id="error-downtime" class="error-stat-value danger"></p>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer" style="padding: 16px 24px 24px; text-align: right; border-top: none;">
                            <button class="btn-error-action" onclick="app.modules.dashboard.closeErrorModal()">Entendido, volver</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', errorModalHTML);
        }
    }

    // --- Action Handlers --- (Unchanged)

    async syncRouter(routerId) {
        if (!confirm('¿Deseas sincronizar este router con MikroTik ahora?')) return;

        try {
            app.showLoading(true); // Assuming app has showLoading
            const response = await this.api.post(`/api/routers/${routerId}/sync`, { confirm: true });
            app.showLoading(false);

            if (response.success) {
                alert(`Sincronización exitosa: ${response.message}`);
                this.loadServers(); // Reload list
            } else {
                alert('Error al sincronizar: ' + response.message);
            }
        } catch (error) {
            app.showLoading(false);
            console.error(error);
            alert('Error de conexión al intentar sincronizar');
        }
    }

    async confirmReboot(routerId, alias) {
        if (!confirm(`⚠️ PELIGRO ⚠️\n\n¿Estás SEGURO de que quieres reiniciar el router "${alias}"?\n\nSe cortará la conexión temporalmente.`)) return;

        try {
            app.showLoading(true);
            const response = await this.api.post(`/api/routers/${routerId}/reboot`, {});
            app.showLoading(false);
            if (response.success) {
                toast.success('Comando enviado. El router se está reiniciando.');
            } else {
                toast.error('Error: ' + response.message);
            }
        } catch (error) {
            app.showLoading(false);
            toast.error('Error al intentar reiniciar el router');
        }
    }

    // --- Router Details Logic ---

    async showRouterDetails(routerId) {
        const modal = document.getElementById('router-details-modal');
        if (!modal) return;

        modal.classList.add('active');

        // Reset tabs
        document.querySelectorAll('#router-details-modal .tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('#router-details-modal .tab-content').forEach(c => c.classList.remove('active'));
        document.querySelector('#router-details-modal .tab-btn:first-child').classList.add('active');
        document.getElementById('tab-info').classList.add('active');

        await this.loadRouterInfo(routerId);
    }

    async loadRouterInfo(routerId) {
        try {
            const router = await this.api.get(`/api/routers/${routerId}`);

            document.getElementById('details-modal-title').textContent = router.alias || 'Detalles del Router';
            document.getElementById('details-modal-subtitle').textContent = `IP: ${router.host_address}`;

            // Status Dot
            const dot = document.getElementById('details-header-status-dot');
            dot.className = `status-dot-mini ${router.status || 'offline'}`;

            // Populate Info Cards
            const setVal = (id, val) => {
                const el = document.getElementById(id);
                if (el) el.textContent = val || '-';
            };

            setVal('detail-alias', router.alias);
            setVal('detail-host', router.host_address);
            setVal('detail-zone', router.zone);
            setVal('detail-api-port', router.api_port);
            setVal('detail-ssh-port', router.ssh_port);
            setVal('detail-notes', router.notes);

            // Styled Status
            const statusEl = document.getElementById('detail-status');
            if (statusEl) {
                const status = (router.status || 'offline').toUpperCase();
                statusEl.innerHTML = `<span class="badge ${router.status || 'offline'}">${status}</span>`;
            }

            // Guardar para uso en la otra pestaña
            this.activeRouterId = routerId;
        } catch (e) {
            console.error(e);
            toast.error('Error al cargar información del router');
        }
    }

    async loadRouterClients() {
        if (!this.activeRouterId) return;

        const loader = document.getElementById('router-clients-loading');
        const list = document.getElementById('router-clients-list');
        const body = document.getElementById('router-clients-table-body');

        loader.style.display = 'block';
        list.style.display = 'none';

        try {
            const clients = await this.api.get(`/api/clients?router_id=${this.activeRouterId}`);
            const formatBandwidth = (value) => {
                if (!value) return 'N/A';
                // Check if it looks like "rate/rate" (MikroTik format)
                if (/^\d+\/\d+$/.test(value)) {
                    return value.split('/').map(v => {
                        const num = parseInt(v, 10);
                        if (num >= 1000000) return (num / 1000000) + 'M';
                        if (num >= 1000) return (num / 1000) + 'k';
                        return num;
                    }).join('/');
                }
                return value;
            };

            body.innerHTML = clients.map(c => `
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #f1f5f9; font-weight: 500;">${c.subscriber_code}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #f1f5f9;">${c.legal_name}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #f1f5f9; font-family: 'JetBrains Mono';">${c.ip_address || '-'}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #f1f5f9; text-align: right;">
                        <span style="background:#eef2ff; color:#4f46e5; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem;">
                            ${formatBandwidth(c.plan_name) || 'N/A'}
                        </span>
                    </td>
                </tr>
            `).join('');

            if (clients.length === 0) {
                body.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 2rem; color: #64748b;">No hay clientes registrados en este router.</td></tr>';
            }

            loader.style.display = 'none';
            list.style.display = 'block';
        } catch (e) {
            loader.innerHTML = '<p style="color:#ef4444;">Error al cargar clientes</p>';
        }
    }

    switchTab(event, tabId) {
        // Update buttons
        const container = event.target.closest('.modal-tabs');
        container.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        event.target.classList.add('active');

        // Update content
        document.querySelectorAll('#router-details-modal .tab-content').forEach(c => c.classList.remove('active'));
        document.getElementById(tabId).classList.add('active');

        if (tabId === 'tab-clients') {
            this.loadRouterClients();
        }
    }

    closeDetailsModal() {
        const modal = document.getElementById('router-details-modal');
        if (modal) modal.classList.remove('active');
        this.activeRouterId = null;
    }

    showConnectionError(routerId) {
        const router = this.servers.find(s => s.id === routerId);
        if (!router) return;

        const modal = document.getElementById('router-error-modal');
        if (!modal) return;

        document.getElementById('error-router-name').textContent = router.alias || 'Router';
        document.getElementById('error-message').textContent = router.last_error || 'No se pudo contactar con el router a través de la API MikroTik.';

        const lastOnline = router.last_online_at ? new Date(router.last_online_at) : null;
        if (lastOnline) {
            document.getElementById('error-last-online').textContent = lastOnline.toLocaleString();

            // Calcular downtime
            const diff = new Date() - lastOnline;
            const minutes = Math.floor(diff / 60000);
            const hours = Math.floor(minutes / 60);
            const days = Math.floor(hours / 24);

            let downtimeStr = "";
            if (days > 0) downtimeStr = `${days}d ${hours % 24}h`;
            else if (hours > 0) downtimeStr = `${hours}h ${minutes % 60}m`;
            else downtimeStr = `${minutes}m`;

            document.getElementById('error-downtime').textContent = downtimeStr;
        } else {
            document.getElementById('error-last-online').textContent = 'Nunca (Sin historia)';
            document.getElementById('error-downtime').textContent = 'Indeterminado';
        }

        modal.classList.add('active');
    }

    closeErrorModal() {
        const modal = document.getElementById('router-error-modal');
        if (modal) modal.classList.remove('active');
    }

    // --- Graph Logic ---

    currentGraphRouterId = null;
    trafficChart = null;
    checkInterval = null;

    async showRouterGraph(routerId, alias) {
        this.currentGraphRouterId = routerId;
        const modal = document.getElementById('router-graph-modal');
        const title = document.getElementById('graph-modal-title');
        const subtitle = document.getElementById('graph-modal-subtitle');
        const list = document.getElementById('interfaces-selection-list');

        if (title) title.textContent = `Monitoreo: ${alias}`;
        if (subtitle) subtitle.textContent = 'Selecciona las interfaces que deseas visualizar en tiempo real.';
        if (modal) modal.classList.add('active');

        // Load interfaces
        list.innerHTML = '<div style="color: #64748b; font-style: italic;">Cargando...</div>';
        try {
            const interfaces = await this.api.get(`/api/routers/${routerId}/interfaces`);
            this.renderInterfaceSelection(interfaces);

            // Iniciar monitoreo de las que ya estén marcadas
            const activeInterfaces = interfaces.filter(i => i.monitored).map(i => i.name);
            if (activeInterfaces.length > 0) {
                this.startMultiTrafficMonitor(routerId, activeInterfaces);
            }
        } catch (e) {
            list.innerHTML = '<div style="color: #ef4444;">Error al cargar interfaces</div>';
        }

        // Init Chart if needed
        this.initChart();
    }

    renderInterfaceSelection(interfaces) {
        const list = document.getElementById('interfaces-selection-list');
        if (!list) return;

        list.innerHTML = interfaces.map(iface => `
            <div class="interface-item" style="display: flex; flex-direction: column; gap: 8px; padding: 10px; background: white; border-radius: 8px; border: 1px solid #e2e8f0;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <span style="font-weight: 600; color: #1e293b; font-size: 0.9rem;">${iface.name}</span>
                    <span style="font-size: 0.7rem; color: #94a3b8; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">${iface.type}</span>
                </div>
                <div style="display: flex; gap: 10px;">
                    <label style="display: flex; align-items: center; gap: 5px; cursor: pointer; font-size: 0.75rem;">
                        <input type="checkbox" class="monitor-check" data-name="${iface.name}" ${iface.monitored ? 'checked' : ''} onchange="app.modules.dashboard.onSelectionChange()">
                        Monitor
                    </label>
                    <label style="display: flex; align-items: center; gap: 5px; cursor: pointer; font-size: 0.75rem;">
                        <input type="checkbox" class="dashboard-check" data-name="${iface.name}" ${iface.on_dashboard ? 'checked' : ''}>
                        Dashboard
                    </label>
                </div>
            </div>
        `).join('');
    }

    async savePreferences() {
        if (!this.currentGraphRouterId) return;

        const preferences = {};
        const items = document.querySelectorAll('.interface-item');

        items.forEach(item => {
            const mCheck = item.querySelector('.monitor-check');
            const dCheck = item.querySelector('.dashboard-check');
            const name = mCheck.dataset.name;

            preferences[name] = {
                modal: mCheck.checked,
                dashboard: dCheck.checked
            };
        });

        try {
            app.showLoading(true);
            const res = await this.api.post(`/api/routers/${this.currentGraphRouterId}/monitoring-preferences`, { preferences });
            app.showLoading(false);
            if (res.success) {
                toast.success('Preferencias guardadas');
            }
        } catch (e) {
            app.showLoading(false);
            toast.error('Error al guardar preferencias');
        }
    }

    onSelectionChange() {
        const activeInterfaces = Array.from(document.querySelectorAll('.monitor-check:checked')).map(c => c.dataset.name);
        this.stopTrafficMonitor();
        if (activeInterfaces.length > 0 && this.currentGraphRouterId) {
            this.startMultiTrafficMonitor(this.currentGraphRouterId, activeInterfaces);
        } else {
            const container = document.getElementById('router-charts-container');
            if (container) container.innerHTML = '<div style="grid-column: 1/-1; display: flex; align-items: center; justify-content: center; height: 300px; color: #64748b;">Selecciona al menos una interfaz para monitorear</div>';
        }
    }

    closeGraphModal() {
        const modal = document.getElementById('router-graph-modal');
        if (modal) modal.classList.remove('active');
        this.stopTrafficMonitor();
    }

    initChart() {
        // No longer using single trafficChart for modal
        this.setupWebsocketHandlers();
        return;
    }

    setupWebsocketHandlers() {
        if (!app.socket) return;

        // Limpiar manejadores previos si existen
        app.socket.off('interface_traffic');
        app.socket.off('router_metrics');

        // Escuchar tráfico de interfaces en tiempo real
        app.socket.on('interface_traffic', (data) => {
            if (!this.activeCharts || data.router_id != this.currentGraphRouterId) return;

            const formatSpeed = (bps) => {
                if (bps >= 1000000) return (bps / 1000000).toFixed(1) + ' Mbps';
                if (bps >= 1000) return (bps / 1000).toFixed(1) + ' Kbps';
                return bps + ' bps';
            };

            this.activeCharts.forEach((monitor, idx) => {
                const ifaceTraffic = data.traffic[monitor.name];
                if (ifaceTraffic && monitor.chart) {
                    const labels = monitor.chart.data.labels;
                    labels.shift();
                    labels.push(new Date().toLocaleTimeString());

                    const txData = monitor.chart.data.datasets[0].data;
                    const rxData = monitor.chart.data.datasets[1].data;

                    txData.shift();
                    txData.push(ifaceTraffic.tx);
                    rxData.shift();
                    rxData.push(ifaceTraffic.rx);

                    // Actualizar texto
                    const txText = document.getElementById(monitor.txId);
                    const rxText = document.getElementById(monitor.rxId);
                    if (txText) txText.textContent = formatSpeed(ifaceTraffic.tx);
                    if (rxText) rxText.textContent = formatSpeed(ifaceTraffic.rx);

                    monitor.chart.update('none');
                }
            });
        });

        // Escuchar métricas del sistema (CPU/RAM)
        app.socket.on('router_metrics', (data) => {
            // Aquí se pueden actualizar indicadores de CPU globales si se desea
            console.log('Metrics received:', data);
        });

        // Escuchar actualización de tráfico del dashboard (Global)
        app.socket.on('dashboard_traffic_update', (data) => {
            if (this.dashboardChart) {
                const labels = this.dashboardChart.data.labels;
                labels.shift();
                labels.push(new Date().toLocaleTimeString());

                this.dashboardChart.data.datasets[0].data.shift();
                this.dashboardChart.data.datasets[0].data.push(data.tx);

                this.dashboardChart.data.datasets[1].data.shift();
                this.dashboardChart.data.datasets[1].data.push(data.rx);

                this.dashboardChart.update('none');

                // Actualizar total en texto si existe
                const totalTxEl = document.getElementById('total-tx-text');
                const totalRxEl = document.getElementById('total-rx-text');
                if (totalTxEl) totalTxEl.textContent = formatSpeed(data.tx);
                if (totalRxEl) totalRxEl.textContent = formatSpeed(data.rx);
            }
        });
    }

    createSingleInterfaceChart(canvasId, interfaceName) {
        const ctx = document.getElementById(canvasId).getContext('2d');

        const formatSpeed = (bps) => {
            if (bps >= 1000000) return (bps / 1000000).toFixed(1) + ' Mbps';
            if (bps >= 1000) return (bps / 1000).toFixed(1) + ' Kbps';
            return bps + ' bps';
        };

        return new Chart(ctx, {
            type: 'line',
            data: {
                labels: new Array(30).fill(''),
                datasets: [
                    {
                        label: 'Down (Tx)',
                        borderColor: '#10b981',
                        backgroundColor: 'transparent',
                        data: new Array(30).fill(0),
                        tension: 0.2, // Un poco de tensión para que se vea fluida en miniatura
                        fill: false,
                        borderWidth: 1.5,
                        pointRadius: 0 // Sin puntos para máximo ahorro
                    },
                    {
                        label: 'Up (Rx)',
                        borderColor: '#3b82f6',
                        backgroundColor: 'transparent',
                        data: new Array(30).fill(0),
                        tension: 0.2,
                        borderWidth: 1.5,
                        borderDash: [3, 3],
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: { display: false },
                    y: {
                        display: true,
                        min: 0,
                        grace: '10%',
                        grid: { color: 'rgba(0,0,0,0.02)' },
                        ticks: {
                            font: { size: 11 },
                            maxRotation: 0,
                            callback: value => formatSpeed(value)
                        }
                    }
                },
                plugins: {
                    legend: { display: false }, // Ocultar leyenda para ahorrar espacio
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: context => context.dataset.label + ': ' + formatSpeed(context.raw)
                        }
                    }
                }
            }
        });
    }


    startMultiTrafficMonitor(routerId, interfaceNames) {
        const container = document.getElementById('router-charts-container');
        if (!container) return;

        container.innerHTML = '';
        this.activeCharts = [];

        interfaceNames.forEach((name, idx) => {
            const canvasId = `chart-iface-${idx}`;
            const cardHTML = `
                <div class="traffic-card" style="background: white; border-radius: 12px; padding: 16px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); height: 250px; display: flex; flex-direction: column; gap: 12px; overflow: hidden;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 800; color: #1e293b; font-size: 0.95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 200px;" title="${name}">${name}</span>
                        <div style="display: flex; gap: 12px;">
                            <span style="font-size: 0.8rem; color: #10b981; font-weight: 800; font-family: 'JetBrains Mono', monospace;" id="live-tx-${idx}">0</span>
                            <span style="font-size: 0.8rem; color: #3b82f6; font-weight: 800; font-family: 'JetBrains Mono', monospace;" id="live-rx-${idx}">0</span>
                        </div>
                    </div>
                    <div style="flex: 1; position: relative;">
                        <canvas id="${canvasId}"></canvas>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', cardHTML);
            const chart = this.createSingleInterfaceChart(canvasId, name);
            this.activeCharts.push({ chart, name, txId: `live-tx-${idx}`, rxId: `live-rx-${idx}` });
        });

        // Iniciar monitoreo vía WebSockets (Alta velocidad, sin cuelgues)
        if (app.socket && app.socket.connected) {
            app.socket.emit('join_router', { router_id: routerId });
            app.socket.emit('subscribe_interfaces', {
                router_id: routerId,
                interfaces: interfaceNames
            });
        } else {
            console.warn("Socket no conectado, usando polling de respaldo (rendimiento limitado)");
            this.checkInterval = setInterval(async () => {
                try {
                    const promises = interfaceNames.map(name =>
                        this.api.get(`/api/routers/${routerId}/interface/${encodeURIComponent(name)}/traffic`)
                    );
                    const results = await Promise.all(promises);
                    // Actualización manual suave
                    results.forEach((data, idx) => {
                        const monitor = this.activeCharts[idx];
                        if (monitor && monitor.chart) {
                            const txData = monitor.chart.data.datasets[0].data;
                            const rxData = monitor.chart.data.datasets[1].data;
                            txData.shift(); txData.push(data.tx);
                            rxData.shift(); rxData.push(data.rx);
                            monitor.chart.update('none');
                        }
                    });
                } catch (e) { }
            }, 3000); // Polling lento para no saturar si WS falla
        }
    }

    stopTrafficMonitor() {
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
            this.checkInterval = null;
        }

        if (app.socket && app.socket.connected && this.currentGraphRouterId) {
            app.socket.emit('leave_router', { router_id: this.currentGraphRouterId });
            // Cleanup interfaces monitoring too
            app.socket.emit('unsubscribe_interfaces', {
                router_id: this.currentGraphRouterId,
                interfaces: (this.activeCharts || []).map(m => m.name)
            });
        }

        if (this.activeCharts) {
            this.activeCharts.forEach(m => {
                if (m.chart) m.chart.destroy();
            });
            this.activeCharts = [];
        }
    }

    renderActivity(activities) {
        const container = document.getElementById('activity-list');
        if (!container) return;

        if (!activities || activities.length === 0) {
            container.innerHTML = '<p style="color: rgba(255,255,255,0.5); padding: 1rem;">No hay actividad reciente</p>';
            return;
        }

        container.innerHTML = activities.map(activity => `
            <div class="activity-item">
                <div class="activity-icon ${activity.type}">
                    <i class="fas fa-${this.getActivityIcon(activity.type)}"></i>
                </div>
                <div class="activity-content">
                    <p class="activity-text">${activity.message}</p>
                    <span class="activity-time">${this.formatTime(activity.timestamp)}</span>
                </div>
            </div>
        `).join('');
    }

    getActivityIcon(type) {
        const icons = {
            'server': 'server',
            'client': 'user',
            'payment': 'dollar-sign',
            'system': 'cog',
            'alert': 'exclamation-triangle'
        };
        return icons[type] || 'circle';
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;

        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (minutes < 1) return 'Ahora';
        if (minutes < 60) return `Hace ${minutes} min`;
        if (hours < 24) return `Hace ${hours}h`;
        return `Hace ${days}d`;
    }
    stopDashboardMonitoring() {
        if (this.dashboardInterval) {
            clearInterval(this.dashboardInterval);
            this.dashboardInterval = null;
        }
    }

    // --- Main Dashboard Chart ---

    initDashboardChart() {
        const canvas = document.getElementById('traffic-chart');
        if (!canvas) return;

        if (this.dashboardChart) return;

        const ctx = canvas.getContext('2d');
        this.dashboardChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: new Array(30).fill(''),
                datasets: [
                    {
                        label: 'Descarga Total (Down)',
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        data: new Array(30).fill(0),
                        fill: true,
                        tension: 0.1
                    },
                    {
                        label: 'Carga Total (Up)',
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        data: new Array(30).fill(0),
                        fill: true,
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: { display: false },
                    y: {
                        min: 0,
                        grace: '10%',
                        grid: { color: 'rgba(0,0,0,0.05)' },
                        ticks: {
                            callback: function (value) {
                                return formatSpeed(value);
                            }
                        }
                    }
                }
            }
        });

        function formatSpeed(bps) {
            if (bps >= 1000000) return (bps / 1000000).toFixed(1) + ' Mbps';
            if (bps >= 1000) return (bps / 1000).toFixed(1) + ' Kbps';
            return bps + ' bps';
        }
    }

    startDashboardMonitoring() {
        this.stopDashboardMonitoring();
        console.log('🚀 Starting high-speed Dashboard monitoring...');

        // No necesitamos interval si el socket está escuchando 'dashboard_traffic_update'
        // pero podemos tener un fallback de seguridad cada 5s por si el socket muere
        if (!app.socket || !app.socket.connected) {
            this.dashboardInterval = setInterval(async () => {
                const view = document.getElementById('dashboard-view');
                if (!view || !view.classList.contains('active')) return;
                try {
                    const data = await this.api.get('/api/routers/dashboard/monitored-traffic');
                    if (this.dashboardChart) {
                        this.dashboardChart.data.datasets[0].data.shift();
                        this.dashboardChart.data.datasets[0].data.push(data.total_tx);
                        this.dashboardChart.data.datasets[1].data.shift();
                        this.dashboardChart.data.datasets[1].data.push(data.total_rx);
                        this.dashboardChart.update('none');
                    }
                } catch (e) { }
            }, 5000);
        }
    }


}
