/**
 * Dashboard Module - Vista Principal
 */
export class DashboardModule {
    constructor(api, eventBus, viewManager, modalManager) {
        this.api = api;
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.modalManager = modalManager;
        this.servers = [];
        this.dashboardChart = null;
        this.dashboardInterval = null;


        console.log('📊 Dashboard Module initialized');

        // REAL-TIME DATA REFRESH
        this.eventBus.subscribe('data_refresh', (data) => {
            if (this.viewManager?.currentMainView === 'dashboard') {
                console.log(`♻️ Real-time Dashboard: Refreshing due to ${data.event_type}`);
                // Throttled refresh
                if (this._refreshTimeout) clearTimeout(this._refreshTimeout);
                this._refreshTimeout = setTimeout(() => {
                    this.loadStats();
                    this.loadActivity();
                    if (data.event_type === 'payment.received') {
                        this.loadReportedPayments();
                    }
                }, 500);
            }
        });
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
            this.initDashboardChart(),
            this.loadReportedPayments() // NUEVO: Cargar pagos reportados
        ]);

        this.applyRoleVisibility();

        this.startDashboardMonitoring();
        this.startServerAutoRefresh();
    }

    applyRoleVisibility() {
        const user = window.app.authService.getUser();
        if (user && (user.role === 'collector' || user.role === 'cobrador')) {
            const reportedWidget = document.getElementById('reported-payments-widget');
            const activityWidget = document.getElementById('recent-activity-widget');

            if (reportedWidget) reportedWidget.style.display = 'none';
            if (activityWidget) activityWidget.style.display = 'none';
        }
    }


    showView() {
        // Delegar visualización a ViewManager
        this.viewManager.showMainView('dashboard');
    }

    async loadStats() {
        try {
            const user = window.app.authService.getUser();
            let url = '/api/dashboard/stats';

            // Si es cobrador, filtrar por su router asignado
            if (user && user.role === 'collector' && user.assigned_router_id) {
                url += `?router_id=${user.assigned_router_id}`;
            }

            const stats = await this.api.get(url);
            this.renderStats(stats);
        } catch (error) {
            console.error('Error loading stats:', error);
            this.renderStats({});
            if (typeof toast !== 'undefined') toast.error('Error al cargar estadísticas.');
        }
    }

    async loadServers() {
        try {
            const user = window.app.authService.getUser();
            let url = '/api/routers';

            // Cargar datos rápidos de la BD primero
            let servers = await this.api.get(url);

            // Si es cobrador, filtrar la lista localmente para mayor seguridad de UI
            if (user && user.role === 'collector' && user.assigned_router_id) {
                servers = servers.filter(s => s.id === user.assigned_router_id);
            }

            this.servers = servers;
            this.renderServers();

            // Inmediatamente intentar refrescar el estado "Live"
            this.refreshLiveStatus();
        } catch (error) {
            console.error('Error loading servers:', error);
            this.servers = [];
            this.renderServers();
            if (typeof toast !== 'undefined') toast.error('Error al cargar lista de routers.');
        }
    }

    async refreshLiveStatus() {
        try {
            const user = window.app.authService.getUser();
            let url = '/api/routers/monitor';

            if (user && user.role === 'collector' && user.assigned_router_id) {
                url += `?router_id=${user.assigned_router_id}`;
            }

            // El monitor también actualiza la BD en el backend
            const liveInfo = await this.api.get(url);

            // Actualizar solo los campos que cambiaron en nuestro array local
            liveInfo.forEach(info => {
                const sIdx = this.servers.findIndex(s => s.id === info.id);
                if (sIdx !== -1) {
                    this.servers[sIdx] = { ...this.servers[sIdx], ...info };
                }
            });

            this.renderServers();
        } catch (e) {
            // Silencioso para monitoreo recurrente
        }
    }

    async loadActivity() {
        try {
            const activity = await this.api.get('/api/activity/recent');
            this.renderActivity(activity);
        } catch (error) {
            console.error('Error loading activity:', error);
            if (typeof this.renderActivity === 'function') this.renderActivity([]);
        }
    }

    async loadReportedPayments() {
        const user = window.app.authService.getUser();
        // Solo admins y secretarias ven esto
        if (!user || user.role === 'collector') return;

        try {
            const reports = await this.api.get('/api/payments/reported/pending');
            this.renderReportedPayments(reports);
        } catch (e) {
            console.error('Error loading reported payments', e);
        }
    }

    renderReportedPayments(reports) {
        const container = document.getElementById('reported-payments-list');
        const badge = document.getElementById('reported-payments-badge');

        if (!container) return; // Si el widget no existe en la UI (ej. para cobradores), salir

        if (badge) {
            badge.textContent = reports.length;
            badge.style.display = reports.length > 0 ? 'inline-block' : 'none';
        }

        if (reports.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 30px 10px; color: #94a3b8;">
                    <i class="fas fa-check-circle" style="font-size: 2rem; margin-bottom: 10px; opacity: 0.5;"></i>
                    <p style="margin: 0; font-size: 0.85rem;">No hay pagos pendientes de autorización</p>
                </div>
            `;
            return;
        }

        // Sorting: Prioritize those with alerts
        reports.sort((a, b) => (b.alert_count || 0) - (a.alert_count || 0));

        container.innerHTML = reports.map(r => {
            const alertBadge = (r.alert_count > 0)
                ? `<span style="background: #ef4444; color: white; padding: 2px 6px; border-radius: 12px; font-size: 0.65rem; font-weight: bold; margin-left: 8px; display: inline-flex; align-items: center; gap: 4px;"><i class="fas fa-bell"></i> ${r.alert_count}</span>`
                : '';

            return `
            <div class="reported-payment-card" style="background: #fff; border: 1px solid ${(r.alert_count > 0) ? '#fca5a5' : '#e2e8f0'}; border-left: 4px solid ${(r.alert_count > 0) ? '#ef4444' : '#f59e0b'}; border-radius: 8px; padding: 12px; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                    <div>
                        <div style="font-weight: 600; color: #1e293b; font-size: 0.9rem; display: flex; align-items: center;">${r.client_name} ${alertBadge}</div>
                        <div style="color: #64748b; font-size: 0.75rem;"><i class="fas fa-id-badge"></i> ${r.subscriber_code} | Rep: ${r.collector_name}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-weight: 700; color: #10b981;">$${r.amount.toLocaleString('en-US')}</div>
                        <div style="color: #94a3b8; font-size: 0.7rem;">${this.formatTime(r.payment_date)}</div>
                    </div>
                </div>
                <div style="display: flex; gap: 8px; justify-content: flex-end; border-top: 1px solid #f1f5f9; padding-top: 8px;">
                    <button onclick="app.modules.dashboard.rejectReportedPayment(${r.id})" class="btn-secondary btn-sm" style="color: #ef4444; border-color: #fca5a5; padding: 4px 8px; font-size: 0.75rem;"><i class="fas fa-times"></i> Rechazar</button>
                    <button onclick="app.modules.dashboard.approveReportedPayment(${r.id})" class="btn-primary btn-sm" style="background: #10b981; border-color: #10b981; padding: 4px 12px; font-size: 0.75rem;"><i class="fas fa-check"></i> Aprobar</button>
                </div>
            </div>
            `;
        }).join('');
    }

    async approveReportedPayment(id) {
        if (!confirm('¿Está seguro de aprobar este pago? Esto afectará el balance del cliente y podría reactivar su servicio.')) return;

        try {
            app.showLoading(true);
            const res = await this.api.post(`/api/payments/reported/${id}/approve`);
            toast.success(res.message || 'Pago aprobado formalmente');
            this.loadReportedPayments(); // Reload list
            this.loadStats(); // Reload stats since balance changed
        } catch (e) {
            toast.error(e.message || 'Error al aprobar el pago');
        } finally {
            app.showLoading(false);
        }
    }

    async rejectReportedPayment(id) {
        const reason = prompt('Motivo del rechazo (opcional):');
        if (reason === null) return; // Cancelled

        try {
            app.showLoading(true);
            const res = await this.api.post(`/api/payments/reported/${id}/reject`, { reason });
            toast.success('Pago reportado fue rechazado');
            this.loadReportedPayments(); // Reload list
        } catch (e) {
            toast.error(e.message || 'Error al rechazar el pago');
        } finally {
            app.showLoading(false);
        }
    }


    renderStats(stats) {
        // Actualizar tarjetas de estadísticas
        const setSafeText = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };

        setSafeText('stat-servers', stats.total_servers || 0);
        setSafeText('stat-total-clients', stats.total_clients || 0);
        setSafeText('stat-active-clients', (stats.active_clients || 0) + (stats.suspended_clients || 0));
        setSafeText('stat-online-clients', stats.online_clients || 0);
        setSafeText('stat-offline-clients', stats.offline_clients || 0);
        setSafeText('stat-paid-clients', stats.paid_clients || 0);
        setSafeText('stat-debt-clients', stats.pending_debt_clients || 0);

        // Revenue formatting
        const revenueVal = stats.monthly_revenue || 0;
        const statRevenue = document.getElementById('stat-revenue');
        if (statRevenue) statRevenue.textContent = `$${revenueVal.toLocaleString('es-CO')}`;

        // Debt formatting
        const debtVal = stats.total_pending_debt || 0;
        const statDebt = document.getElementById('stat-debt');
        if (statDebt) statDebt.textContent = `$${debtVal.toLocaleString('es-CO')} en mora`;

        // Servers monitoring counters
        setSafeText('servers-online', stats.servers_online || 0);
        setSafeText('servers-warning', stats.servers_warning || 0);
        setSafeText('servers-offline', stats.servers_offline || 0);
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
            container.innerHTML = '<p style="color: #94a3b8; padding: 1rem; font-size: 0.875rem;">No hay routers configurados</p>';
            return;
        }

        container.innerHTML = `
            <div class="elegant-list">
                ${this.servers.map(server => {
            const isOffline = (server.status || 'offline') === 'offline';
            const hasOfflineClients = (server.clients_offline || 0) > 0;
            const alertIcon = isOffline
                ? `<i class="fas fa-exclamation-triangle router-alert-icon" onclick="event.stopPropagation(); app.modules.dashboard.showConnectionError(${server.id})" title="Ver error de conexión"></i>`
                : '';

            return `
                    <div class="elegant-item">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span class="status-indicator ${server.status || 'offline'}" style="width: 12px; height: 12px;"></span>
                            <div style="display: flex; flex-direction: column; gap: 2px;">
                                <div style="display: flex; align-items: center; gap: 6px;">
                                    <span class="router-name-premium" onclick="app.modules.dashboard.showRouterDetails(${server.id})">${(server.alias || 'Router').toUpperCase()}</span>
                                    ${alertIcon}
                                </div>
                                <span class="router-ip-premium">${server.host_address || '---'}</span>
                                
                                 <!-- Mini Tarjetas de Clientes -->
                                 <div style="display: flex; gap: 4px; margin-top: 4px;">
                                    <div class="router-mini-card active" title="Activos" onclick="event.stopPropagation(); app.modalManager.open('client-status-details', { routerId: ${server.id}, status: 'active' })">
                                        <i class="fas fa-users"></i> ${server.clients_active || 0}
                                    </div>
                                    <div class="router-mini-card online" title="Conectados" onclick="event.stopPropagation(); app.modalManager.open('client-status-details', { routerId: ${server.id}, status: 'online' })">
                                        <i class="fas fa-circle"></i> ${server.clients_online || 0}
                                    </div>
                                    <div class="router-mini-card offline ${hasOfflineClients ? 'alert-pulse' : ''}" title="Offline" onclick="event.stopPropagation(); app.modalManager.open('client-status-details', { routerId: ${server.id}, status: 'offline' })">
                                        <i class="fas fa-circle"></i> ${server.clients_offline || 0}
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <div style="text-align: right; min-width: 50px;">
                                <span class="router-cli-count">${server.clients_connected || 0}</span>
                                <span class="router-cli-label">cli</span>
                            </div>
                            <div style="display: flex; gap: 6px;">
                                <button class="action-btn-xs minimal" onclick="event.stopPropagation(); app.modules.dashboard.showRouterGraph(${server.id}, '${server.alias}')" title="Ver Gráfico" style="background: transparent; border: none; color: #cbd5e1; cursor: pointer; font-size: 0.9rem;">
                                    <i class="fas fa-chart-line"></i>
                                </button>
                                <button class="action-btn-xs minimal" onclick="event.stopPropagation(); app.modules.dashboard.syncRouter(${server.id})" title="Sincronizar" style="background: transparent; border: none; color: #cbd5e1; cursor: pointer; font-size: 0.9rem;">
                                    <i class="fas fa-sync-alt"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                `}).join('')}
            </div>
        `;

    }

    // --- Action Handlers ---

    async syncRouter(routerId) {
        if (!window.app.checkPermission('sync', 'can_edit')) return;
        if (!confirm('¿Deseas sincronizar este router con MikroTik ahora?')) return;

        try {
            app.showLoading(true);
            const response = await this.api.post(`/api/routers/${routerId}/sync`, { confirm: true });

            if (response.success) {
                toast.success(`Sincronización exitosa: ${response.message}`);
                this.loadServers(); // Reload list
            } else {
                alert('Error al sincronizar: ' + response.message);
            }
        } catch (error) {
            console.error(error);
            alert('Error de conexión al intentar sincronizar');
        } finally {
            app.showLoading(false);
        }
    }

    async confirmReboot(routerId, alias) {
        if (!window.app.checkPermission('routers:reboot', 'can_edit')) return;
        if (!confirm(`⚠️ PELIGRO ⚠️\n\n¿Estás SEGURO de que quieres reiniciar el router "${alias}"?\n\nSe cortará la conexión temporalmente.`)) return;

        try {
            app.showLoading(true);
            const response = await this.api.post(`/api/routers/${routerId}/reboot`, {});
            if (response.success) {
                toast.success('Comando enviado. El router se está reiniciando.');
            } else {
                toast.error('Error: ' + response.message);
            }
        } catch (error) {
            toast.error('Error al intentar reiniciar el router');
        } finally {
            app.showLoading(false);
        }
    }

    switchTab(param1, param2 = null) {
        const modal = document.getElementById('router-details-modal');
        if (!modal) return;

        let tabId = param2;
        let btn = null;

        if (typeof param1 === 'string') {
            // Case: switchTab('info')
            const name = param1;
            tabId = tabId || (name.startsWith('tab-') ? name : `tab-${name}`);
            btn = Array.from(modal.querySelectorAll('.tab-btn')).find(b =>
                b.textContent.toLowerCase().includes(name.toLowerCase()) ||
                (b.getAttribute('onclick') && b.getAttribute('onclick').includes(name))
            );
        } else if (param1 && param1.target) {
            // Case: switchTab(event, 'tab-info')
            btn = param1.target.closest('.tab-btn');
            tabId = param2 || btn?.getAttribute('onclick')?.match(/'([^']+)'/)?.[1];
            if (tabId && !tabId.startsWith('tab-')) tabId = `tab-${tabId}`;
        }

        if (!tabId) return;

        // UI Reset
        modal.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        modal.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

        // UI Activate
        if (btn) btn.classList.add('active');
        const content = document.getElementById(tabId.startsWith('tab-') ? tabId : `tab-${tabId}`);
        if (content) content.classList.add('active');

        // RBAC Tab Protection (Safety Guard for manual calls)
        if (tabId === 'tab-interfaces' || tabId === 'tab-logs') {
            if (!app.modules.auth.checkPermission('system:users', 'view')) {
                toast.error('Este procedimiento no se puede procesar porque no posee los privilegios necesarios.');
                this.switchTab('info');
                return;
            }
        }

        // Logic Hook
        const clientsFooter = document.getElementById('clients-footer-info');
        const syncPreview = document.getElementById('sync-preview-container');

        if (tabId === 'tab-clients') {
            this.loadRouterClients();
            if (clientsFooter) clientsFooter.style.display = 'flex';
        } else {
            if (clientsFooter) clientsFooter.style.display = 'none';
            if (syncPreview) syncPreview.style.display = 'none'; // Reset preview when switching away
        }

        if (tabId === 'tab-interfaces') {
            this.loadRouterInterfaces();
        } else if (tabId === 'tab-logs') {
            this.loadRouterLogs();
        }
    }

    // --- Router Details Logic ---

    async showRouterDetails(routerId) {
        window.currentRouterId = routerId; // Global reference for buttons in modal

        if (this.modalManager) {
            this.modalManager.open('router-details');
        } else {
            const modal = document.getElementById('router-details-modal');
            if (modal) modal.classList.add('active');
        }

        // Safety check for tabs
        const modalContainer = document.getElementById('router-details-modal');
        if (modalContainer) {
            // Reset tabs
            modalContainer.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            modalContainer.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            const firstTab = modalContainer.querySelector('.tab-btn:first-child');
            if (firstTab) firstTab.classList.add('active');

            const infoTabContent = document.getElementById('tab-info');
            if (infoTabContent) infoTabContent.classList.add('active');
        }

        await this.loadRouterInfo(routerId);
    }

    async loadRouterInfo(routerId) {
        try {
            const router = await this.api.get(`/api/routers/${routerId}`);

            const setTitle = (id, val) => {
                const el = document.getElementById(id);
                if (el) el.textContent = val;
            };

            setTitle('details-modal-title', router.alias || 'Detalles del Router');
            setTitle('details-modal-subtitle', `IP: ${router.host_address}`);

            // Status Dot
            const dot = document.getElementById('details-header-status-dot');
            if (dot) dot.className = `status-dot-mini ${router.status || 'offline'}`;

            // Populate Info Cards
            const setVal = (id, val) => {
                const el = document.getElementById(id);
                if (el) el.textContent = val || '-';
            };

            setVal('detail-alias', router.alias);
            setVal('detail-host', router.host_address);
            setVal('detail-zone', router.zone);
            setVal('detail-api-port', router.api_port);
            setVal('detail-version', router.version || 'RouterOS');

            // Technical Metrics
            const cpu = parseInt(router.cpu_usage || 0);
            const ram = parseInt(router.memory_usage || 0);

            setVal('detail-cpu-text', `${cpu}%`);
            setVal('detail-ram-text', `${ram}%`);
            setVal('detail-uptime-text', this.formatUptime(router.uptime));

            // Progress Bars
            const cpuBar = document.getElementById('detail-cpu-bar');
            if (cpuBar) {
                cpuBar.style.width = `${cpu}%`;
                cpuBar.className = 'tech-metric-progress ' + (cpu > 80 ? 'danger' : cpu > 50 ? 'warning' : '');
            }

            const ramBar = document.getElementById('detail-ram-bar');
            if (ramBar) {
                ramBar.style.width = `${ram}%`;
                ramBar.className = 'tech-metric-progress ' + (ram > 80 ? 'danger' : ram > 50 ? 'warning' : 'success');
            }

            // Styled Status
            const statusEl = document.getElementById('detail-status');
            if (statusEl) {
                const status = (router.status || 'offline').toUpperCase();
                statusEl.innerHTML = `<span class="badge ${router.status || 'offline'}" style="margin:0">${status}</span>`;
            }

            // Guardar para uso en la otra pestaña
            this.activeRouterId = routerId;

            // RBAC Check for Sync Button in Modal
            const syncBtn = document.getElementById('btn-sync-router');
            if (syncBtn) {
                const canSync = app.modules.auth.checkPermission('routers:monitoring', 'edit');
                syncBtn.style.display = canSync ? 'flex' : 'none';
            }

            // RBAC Check for Admin Tabs (Interfaces / Logs) SCOPED to the current modal
            const isAdmin = app.modules.auth.checkPermission('system:users', 'view');
            const modalEl = document.getElementById('router-details-modal');
            if (modalEl) {
                const interfacesTabBtn = Array.from(modalEl.querySelectorAll('.tab-btn')).find(b => b.textContent.includes('Interfaces'));
                const logsTabBtn = Array.from(modalEl.querySelectorAll('.tab-btn')).find(b => b.textContent.includes('Logs'));

                if (interfacesTabBtn) interfacesTabBtn.style.display = isAdmin ? 'flex' : 'none';
                if (logsTabBtn) logsTabBtn.style.display = isAdmin ? 'flex' : 'none';
            }
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

            // Ordenar alfabéticamente por nombre
            clients.sort((a, b) => a.legal_name.localeCompare(b.legal_name));

            // Actualizar contador
            const countEl = document.getElementById('router-clients-count');
            if (countEl) countEl.textContent = `${clients.length} Clientes`;

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

            body.innerHTML = clients.map((c, idx) => `
                <tr class="premium-row" style="transition: background 0.2s;">
                    <td style="padding: 15px 12px; border-bottom: 1px solid rgba(226, 232, 240, 0.5);">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="color: #94a3b8; font-size: 0.75rem; font-weight: 700; width: 25px;">${idx + 1}.</span>
                            <span class="status-badge-table pending" style="font-size: 0.7rem; letter-spacing: 0.05em;">${c.subscriber_code}</span>
                        </div>
                    </td>
                    <td style="padding: 15px 12px; border-bottom: 1px solid rgba(226, 232, 240, 0.5); font-weight: 600; color: #1e293b;">
                        ${c.legal_name}
                    </td>
                    <td style="padding: 15px 12px; border-bottom: 1px solid rgba(226, 232, 240, 0.5);">
                        <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #4f46e5; background: rgba(79, 70, 229, 0.05); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(79, 70, 229, 0.1);">
                            ${c.ip_address || 'Sin IP'}
                        </span>
                    </td>
                </tr>
            `).join('');

            if (clients.length === 0) {
                body.innerHTML = '<tr><td colspan="3" style="text-align:center; padding: 2rem; color: #64748b;">No hay clientes registrados en este router.</td></tr>';
            }

            loader.style.display = 'none';
            list.style.display = 'block';
        } catch (e) {
            loader.innerHTML = '<p style="color:#ef4444;">Error al cargar clientes</p>';
        }
    }

    async exportClients(format) {
        if (!this.activeRouterId) return;
        toast.info(`Generando reporte ${format.toUpperCase()}...`);
        window.open(`/api/routers/${this.activeRouterId}/clients/export?format=${format}`, '_blank');
    }

    async previewSync() {
        if (!window.app.checkPermission('sync', 'can_edit')) return;
        if (!this.activeRouterId) return;

        const btn = document.getElementById('btn-sync-router');
        const previewContainer = document.getElementById('sync-preview-container');
        const previewList = document.getElementById('sync-preview-list');

        if (!btn || !previewContainer || !previewList) return;

        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Buscando...';

        try {
            const data = await this.api.post(`/api/routers/${this.activeRouterId}/sync`, { confirm: false });

            if (data.success) {
                if (data.candidates && data.candidates.length > 0) {
                    previewList.innerHTML = data.candidates.map(c => `
                        <div style="display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid #f1f5f9;">
                            <span style="font-weight: 600; color: #1e1b4b;">${c.host}</span>
                            <span style="color: #6366f1; font-family: monospace;">${c.ip || 'Sin IP'}</span>
                        </div>
                    `).join('');

                    previewContainer.style.display = 'block';
                    // Scroll to preview
                    previewContainer.scrollIntoView({ behavior: 'smooth' });
                } else {
                    toast.success('No hay clientes nuevos para sincronizar.');
                    previewContainer.style.display = 'none';
                }
            }
        } catch (e) {
            console.error(e);
            // Redundant toast removed: api.service.js now handles the 403 message professionally
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-sync"></i> Sincronizar Ahora';
        }
    }

    async confirmSync() {
        if (!window.app.checkPermission('sync', 'can_edit')) return;
        if (!this.activeRouterId) return;

        app.showLoading(true);
        try {
            const data = await this.api.post(`/api/routers/${this.activeRouterId}/sync`, { confirm: true });
            if (data.success) {
                toast.success(data.message);
                document.getElementById('sync-preview-container').style.display = 'none';
                this.loadRouterClients(); // Recargar lista
            }
        } catch (e) {
            // Redundant toast removed: api.service.js now handles the 403 message professionally
        } finally {
            app.showLoading(false);
        }
    }

    async loadRouterInterfaces() {
        if (!window.app.checkPermission('routers:interfaces', 'can_view')) return;
        if (!this.activeRouterId) return;

        const container = document.getElementById('interfaces-list-container');
        if (!container) return;

        container.innerHTML = '<div style="text-align:center; padding:20px;"><div class="spinner-mini"></div><p>Cargando interfaces...</p></div>';

        try {
            const interfaces = await this.api.get(`/api/routers/${this.activeRouterId}/interfaces`);

            container.innerHTML = `
                <table class="premium-data-table">
                    <thead>
                        <tr>
                            <th>NOMBRE</th>
                            <th>TIPO</th>
                            <th>ESTADO</th>
                            <th style="text-align:right">TRÁFICO</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${interfaces.map(iface => `
                            <tr>
                                <td style="font-weight: 600;">
                                    <i class="fas fa-network-wired" style="margin-right:8px; opacity:0.5;"></i> ${iface.name}
                                </td>
                                <td><span class="badge muted">${iface.type}</span></td>
                                <td>
                                    <span class="status-dot-mini ${iface.running ? 'online' : 'offline'}"></span>
                                    ${iface.running ? 'Running' : 'Stopped'}
                                    ${iface.disabled ? '<span class="badge danger" style="font-size:0.6rem; padding:1px 4px; margin-left:5px;">DISABLED</span>' : ''}
                                </td>
                                <td style="text-align:right">
                                    <button class="btn-text" onclick="app.modules.dashboard.showInterfaceTraffic('${iface.name}')">
                                        <i class="fas fa-chart-line"></i> Ver Tráfico
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        } catch (e) {
            container.innerHTML = '<p style="color:#ef4444; padding:20px; text-align:center;">Error al cargar interfaces</p>';
        }
    }

    async loadRouterLogs() {
        if (!window.app.checkPermission('routers:logs', 'can_view')) return;
        if (!this.activeRouterId) return;

        const container = document.getElementById('router-logs-container');
        if (!container) return;

        container.innerHTML = 'Buscando logs...';

        try {
            const logs = await this.api.get(`/api/routers/${this.activeRouterId}/logs?limit=50`);

            if (!logs || logs.length === 0) {
                container.innerHTML = 'No se encontraron logs recientes.';
                return;
            }

            container.innerHTML = logs.map(log => `
                <div class="log-entry">
                    <span class="log-time">[${log.time || ''}]</span>
                    <span class="log-tag">${log.topics || ''}</span>
                    <span class="log-msg">${log.message || ''}</span>
                </div>
            `).join('');

            // Scroll to bottom
            container.scrollTop = container.scrollHeight;
        } catch (e) {
            container.innerHTML = '<span style="color:#ef4444;">Error al cargar logs del router.</span>';
        }
    }

    showInterfaceTraffic(interfaceName) {
        toast.info(`Cargando gráfico de tráfico para ${interfaceName}...`);
        if (this.modalManager) {
            this.modalManager.open('router-graph');
        }
    }

    closeDetailsModal() {
        if (this.modalManager) {
            this.modalManager.close('router-details');
        } else {
            const modal = document.getElementById('router-details-modal');
            if (modal) modal.classList.remove('active');
        }
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

        if (this.modalManager) {
            this.modalManager.open('router-error');
        } else {
            modal.classList.add('active');
        }
    }

    closeErrorModal() {
        if (this.modalManager) {
            this.modalManager.close('router-error');
        } else {
            const modal = document.getElementById('router-error-modal');
            if (modal) modal.classList.remove('active');
        }
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
        if (this.modalManager) {
            this.modalManager.open('router-graph');
        } else {
            if (modal) modal.classList.add('active');
        }

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
            if (res.success) {
                toast.success('Preferencias guardadas');
            }
        } catch (e) {
            console.error('Error saving monitoring preferences:', e);
            toast.error('Error al guardar preferencias');
        } finally {
            app.showLoading(false);
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
        if (this.modalManager) {
            this.modalManager.close('router-graph');
        } else {
            const modal = document.getElementById('router-graph-modal');
            if (modal) modal.classList.remove('active');
        }
        this.stopTrafficMonitor();
    }

    initChart() {
        // No longer using single trafficChart for modal
        this.setupWebsocketHandlers();
        return;
    }

    setupWebsocketHandlers() {
        if (!app.socket) return;

        // Limpiar manejadores previos para evitar duplicados
        app.socket.off('interface_traffic');
        app.socket.off('router_metrics');
        app.socket.off('dashboard_traffic_update');
        // NO limpiar 'connect' globalmente. Solo limpiar nuestro handler específico si existe.
        if (this.onSocketConnect) {
            app.socket.off('connect', this.onSocketConnect);
        }

        // Definir el handler de reconexión específico
        this.onSocketConnect = () => {
            console.log('🔄 Dashboard: Socket Reconnected. Restoring monitoring subscriptions...');
            if (this.currentGraphRouterId && this.activeCharts && this.activeCharts.length > 0) {
                app.socket.emit('join_router', { router_id: this.currentGraphRouterId });
                const ifaces = this.activeCharts.map(m => m.name);
                app.socket.emit('subscribe_interfaces', {
                    router_id: this.currentGraphRouterId,
                    interfaces: ifaces
                });
            }
        };

        // Asignar el handler
        app.socket.on('connect', this.onSocketConnect);

        // Escuchar tráfico de interfaces en tiempo real
        app.socket.on('interface_traffic', (data) => {
            if (!this.activeCharts || data.router_id != this.currentGraphRouterId) return;

            const formatSpeed = (bps) => {
                if (bps >= 1000000000) return (bps / 1000000000).toFixed(1) + ' Gbps';
                if (bps >= 1000000) return (bps / 1000000).toFixed(1) + ' Mbps';
                if (bps >= 1000) return (bps / 1000).toFixed(1) + ' Kbps';
                return bps + ' bps';
            };

            this.activeCharts.forEach((monitor, idx) => {
                const ifaceTraffic = data.traffic[monitor.name];

                // Si viene tráfico para esta interfaz, actualizamos
                if (ifaceTraffic && monitor.chart) {
                    const labels = monitor.chart.data.labels;
                    labels.shift();
                    const now = new Date();
                    labels.push(`${now.getHours()}:${now.getMinutes()}:${now.getSeconds()}`);

                    const txData = monitor.chart.data.datasets[0].data;
                    const rxData = monitor.chart.data.datasets[1].data;

                    txData.shift();
                    txData.push(ifaceTraffic.tx); // Download (Green)
                    rxData.shift();
                    rxData.push(ifaceTraffic.rx); // Upload (Blue)

                    // Actualizar texto de velocidad actual
                    const txText = document.getElementById(monitor.txId);
                    const rxText = document.getElementById(monitor.rxId);
                    if (txText) txText.textContent = formatSpeed(ifaceTraffic.tx);
                    if (rxText) rxText.textContent = formatSpeed(ifaceTraffic.rx);

                    // Forzar actualización eficiente
                    monitor.chart.update('none');
                }
            });
        });

        // Escuchar métricas del sistema (CPU/RAM)
        app.socket.on('router_metrics', (data) => {
            // Optional: Update modal header or specific metric elements if needed
        });

        // Escuchar actualización de tráfico del dashboard (Global)
        app.socket.on('dashboard_traffic_update', (data) => {
            if (this.dashboardChart) {
                const labels = this.dashboardChart.data.labels;
                labels.shift();
                const now = new Date();
                labels.push(`${now.getHours()}:${now.getMinutes()}:${now.getSeconds()}`);

                this.dashboardChart.data.datasets[0].data.shift();
                this.dashboardChart.data.datasets[0].data.push(data.tx);

                this.dashboardChart.data.datasets[1].data.shift();
                this.dashboardChart.data.datasets[1].data.push(data.rx);

                this.dashboardChart.update('none');

                // Actualizar total en texto si existe
                const totalTxEl = document.getElementById('total-tx-text');
                const totalRxEl = document.getElementById('total-rx-text');

                const formatSpeed = (bps) => {
                    if (bps >= 1000000) return (bps / 1000000).toFixed(1) + ' Mbps';
                    if (bps >= 1000) return (bps / 1000).toFixed(1) + ' Kbps';
                    return bps + ' bps';
                };

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

        // Limpiar handler de conexión si existe
        if (this.onSocketConnect) {
            if (app.socket) app.socket.off('connect', this.onSocketConnect);
            this.onSocketConnect = null;
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
            container.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; color: #94a3b8;">
                    <i class="fas fa-inbox" style="font-size: 2.5rem; margin-bottom: 12px; display: block; opacity: 0.4;"></i>
                    <p style="font-size: 0.9rem; font-weight: 600;">Sin actividad reciente</p>
                    <p style="font-size: 0.78rem;">Las acciones del sistema aparecerán aquí</p>
                </div>`;
            return;
        }

        container.innerHTML = activities.map((activity, i) => {
            const iconClass = this.getActivityIconClass(activity.type);
            const iconName = this.getActivityIcon(activity.type);
            const delay = Math.min(i * 30, 300);

            // Highlight monetary amounts in the message
            let msg = activity.message || '';
            msg = msg.replace(/\$[\d,\.]+/g, '<strong style="color: #10b981;">$&</strong>');

            return `
                <div class="activity-item" style="animation: fadeInUp 0.3s ease ${delay}ms both;">
                    <div class="activity-icon ${iconClass}">
                        <i class="fas fa-${iconName}"></i>
                    </div>
                    <div class="activity-content" style="flex: 1; min-width: 0;">
                        <p style="font-size: 0.875rem; color: #1e293b; font-weight: 600; margin: 0 0 3px 0; line-height: 1.4; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${msg}</p>
                        <p style="font-size: 0.72rem; color: #94a3b8; margin: 0; font-weight: 500;">
                            <i class="far fa-clock" style="margin-right: 3px;"></i>${activity.time_ago || 'Hace un momento'}
                        </p>
                    </div>
                </div>
            `;
        }).join('');
    }

    getActivityIconClass(type) {
        const classes = {
            'payment': 'payment',
            'suspended': 'suspended',
            'client': 'client',
            'server': 'system',
            'system': 'system',
            'alert': 'alert'
        };
        return classes[type] || 'system';
    }

    getActivityIcon(type) {
        const icons = {
            'server': 'server',
            'client': 'user-check',
            'payment': 'dollar-sign',
            'system': 'cog',
            'alert': 'exclamation-triangle',
            'suspended': 'user-slash'
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
        if (hours < 24) return `Hace ${hours} h`;
        return `Hace ${days} d`;
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
                animation: { duration: 500 },
                plugins: {
                    legend: {
                        position: 'top',
                        align: 'end',
                        labels: {
                            boxWidth: 8,
                            usePointStyle: true,
                            font: { size: 11, weight: '600' }
                        }
                    }
                },
                scales: {
                    x: { display: false },
                    y: {
                        min: 0,
                        grace: '5%',
                        grid: { display: false },
                        ticks: {
                            font: { size: 10 },
                            callback: value => formatSpeed(value)
                        }
                    }
                },
                elements: {
                    point: { radius: 0, hoverRadius: 4 }
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


    formatUptime(uptime) {
        if (!uptime || uptime === 'N/A') return 'OFFLINE';
        if (uptime.includes('w') || uptime.includes('d') || uptime.includes('h')) return uptime;

        // Si viene en segundos (usado a veces por monitoreo rápido)
        if (!isNaN(uptime)) {
            const seconds = parseInt(uptime);
            const d = Math.floor(seconds / (3600 * 24));
            const h = Math.floor(seconds % (3600 * 24) / 3600);
            const m = Math.floor(seconds % 3600 / 60);

            if (d > 0) return `${d}d ${h}h`;
            if (h > 0) return `${h}h ${m}m`;
            return `${m}m`;
        }

        return uptime;
    }

    formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    async showClientStatusDetails(routerId, status) {
        console.log(`📊 [Dashboard] showClientStatusDetails: routerId=${routerId}, status=${status}`);
        const router = this.servers.find(s => s.id === routerId);
        const routerName = router ? router.alias : 'Router';
        const titles = {
            'active': 'Clientes Activos',
            'online': 'Clientes Conectados',
            'offline': 'Clientes Desconectados'
        };

        // UI Updates for the modal
        const titleEl = document.getElementById('client-status-modal-title');
        const subtitleEl = document.getElementById('client-status-modal-subtitle');
        const listEl = document.getElementById('status-clients-list');
        const trafficIndicator = document.getElementById('modal-traffic-indicator-global');

        if (!titleEl || !listEl) {
            console.error('❌ [Dashboard] Modal elements not found in DOM!', { titleEl, listEl });
        }

        if (titleEl) titleEl.textContent = `${titles[status]} - ${routerName}`;
        if (subtitleEl) subtitleEl.textContent = `ESTADO: ${status.toUpperCase()} | ROUTER: ${router?.host_address || '---'}`;
        if (listEl) {
            listEl.innerHTML = '<div class="loading-cell" style="grid-column: 1/-1; text-align: center; padding: 40px;"><div class="spinner"></div><p style="margin-top: 15px; color: #64748b;">Cargando listado de clientes...</p></div>';
        }
        if (trafficIndicator) trafficIndicator.style.display = (status === 'online') ? 'flex' : 'none';

        try {
            // Para online / offline, partimos siempre de la base de clientes 'active' administrativamente
            // para mantener consistencia con los totales de la tarjeta.
            const clients = await this.api.get(`/api/clients?router_id=${routerId}&status=active`);
            let filtered = clients || [];

            if (status === 'online') filtered = filtered.filter(c => c.is_online);
            if (status === 'offline') filtered = filtered.filter(c => !c.is_online);

            this.currentModalClients = filtered;
            this.currentModalStatus = status;
            this.currentModalRouterId = routerId;

            const searchInput = document.getElementById('client-status-search');
            if (searchInput) {
                searchInput.value = ''; // Reset search

                // Remove generic old listeners if any by cloning
                const newSearchInput = searchInput.cloneNode(true);
                searchInput.parentNode.replaceChild(newSearchInput, searchInput);

                newSearchInput.addEventListener('input', (e) => {
                    const term = e.target.value.toLowerCase();
                    const searchedClients = this.currentModalClients.filter(c =>
                        (c.legal_name && c.legal_name.toLowerCase().includes(term)) ||
                        (c.ip_address && c.ip_address.toLowerCase().includes(term)) ||
                        (c.subscriber_code && c.subscriber_code.toLowerCase().includes(term))
                    );
                    this.renderStatusClients(searchedClients, this.currentModalStatus, this.currentModalRouterId);
                });
            }

            this.renderStatusClients(filtered, status, routerId);
        } catch (e) {
            console.error('Error fetching clients for status details:', e);
            if (listEl) listEl.innerHTML = `<div class="error-cell" style="grid-column: 1/-1; text-align: center; padding: 20px; color: #ef4444;">Error al cargar datos: ${e.message}</div>`;
        }
    }

    renderStatusClients(clients, status, routerId) {
        const container = document.getElementById('status-clients-list');
        if (!container) return;

        if (clients.length === 0) {
            container.innerHTML = `<p style="grid-column: 1/-1; text-align: center; color: #94a3b8; padding: 2rem;">No hay clientes en este estado</p>`;
            return;
        }

        container.innerHTML = clients.map(client => {
            const avatar = (client.legal_name || '?').charAt(0).toUpperCase();
            let detailHtml = '';

            if (status === 'offline') {
                const downtime = client.last_seen ? this.calculateDowntime(client.last_seen) : 'Tiempo desconocido';
                detailHtml = `<div class="downtime-indicator" style="color: #ef4444; font-size: 0.75rem; font-weight: 700; margin-top: 10px; background: rgba(239, 68, 68, 0.05); padding: 8px; border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.1);">
                                <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 2px;">
                                    <i class="fas fa-plug-circle-xmark"></i> 
                                    <span>Desconectado</span>
                                </div>
                                <div style="font-size: 0.7rem; margin-top: 4px; color: #1e293b; opacity: 0.9;">
                                    <span style="font-weight: 400;">Desde:</span> 
                                    <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700;">${client.last_seen ? new Date(client.last_seen).toLocaleString() : '---'}</span>
                                </div>
                                <div style="font-size: 0.75rem; font-weight: 800; margin-top: 4px; color: #b91c1c;">
                                    <span>Hace:</span>
                                    <span style="font-family: 'JetBrains Mono', monospace;">${downtime}</span>
                                </div>
                             </div>`;
            } else if (status === 'online') {
                detailHtml = `<div class="traffic-mini" id="traffic-${client.id}" style="display: flex; gap: 8px; margin-left: auto; align-items: center; flex-shrink: 0;">
                                <div style="background: rgba(16, 185, 129, 0.08); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(16, 185, 129, 0.2); display: flex; flex-direction: column; min-width: 80px;">
                                    <div style="display: flex; align-items: center; gap: 4px; color: #059669; font-size: 0.65rem; font-weight: 800; text-transform: uppercase;">
                                        <i class="fas fa-arrow-down" style="font-size: 0.65rem;"></i> DESCARGA
                                    </div>
                                    <div class="val-down" style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 800; color: #064e3b; margin-top: 2px;">0 bps</div>
                                </div>
                                <div style="background: rgba(99, 102, 241, 0.08); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(99, 102, 241, 0.2); display: flex; flex-direction: column; min-width: 80px;">
                                    <div style="display: flex; align-items: center; gap: 4px; color: #4338ca; font-size: 0.65rem; font-weight: 800; text-transform: uppercase;">
                                        <i class="fas fa-arrow-up" style="font-size: 0.65rem;"></i> SUBIDA
                                    </div>
                                    <div class="val-up" style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 800; color: #312e81; margin-top: 2px;">0 bps</div>
                                </div>
                             </div>`;
            } else if (status === 'active') {
                detailHtml = `<div style="margin-top: 10px; display: flex; gap: 6px;">
                                <span style="font-size: 0.65rem; font-weight: 700; background: #f1f5f9; color: #475569; padding: 4px 8px; border-radius: 6px; border: 1px solid #e2e8f0;">
                                    <i class="fas fa-tag"></i> ${client.service_type || 'Servicio'}
                                </span>
                             </div>`;
            }

            return `
                <div class="client-detail-card premium-card glass" style="padding: 16px; border: 1px solid rgba(148, 163, 184, 0.1); height: 100%; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center; overflow: hidden;">
                    <div style="display: flex; align-items: center; gap: 12px; width: 100%;">
                        <div class="client-avatar" style="width: 36px; height: 36px; font-size: 1rem; flex-shrink: 0;">${avatar}</div>
                        <div style="display: flex; flex-direction: column; justify-content: center; min-width: 0; flex: 1;">
                            <div style="font-weight: 800; color: #1e293b; font-size: 0.95rem; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${client.legal_name}">${client.legal_name}</div>
                            <div style="font-size: 0.8rem; color: #64748b; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${client.subscriber_code || '---'}</div>
                            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #94a3b8; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${client.ip_address || '---'}</div>
                            ${status !== 'online' ? detailHtml : ''}
                        </div>
                        ${status === 'online' ? detailHtml : ''}
                    </div>
                </div>
            `;
        }).join('');

        if (status === 'online') {
            const trafficIndicator = document.getElementById('modal-traffic-indicator');
            if (trafficIndicator) trafficIndicator.style.display = 'flex';
            this.startClientDetailsMonitoring(routerId, clients.map(c => c.id));
        }
    }

    calculateDowntime(lastOnline) {
        if (!lastOnline) return '---';
        const last = new Date(lastOnline).getTime();
        const now = Date.now();
        const diff = Math.max(0, now - last);

        const totalSeconds = Math.floor(diff / 1000);
        const days = Math.floor(totalSeconds / 86400);
        const hours = Math.floor((totalSeconds % 86400) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;

        let result = [];
        if (days > 0) result.push(`${days}d`);
        if (hours > 0) result.push(`${hours}h`);
        if (minutes > 0) result.push(`${minutes}m`);
        if (seconds > 0 || result.length === 0) result.push(`${seconds}s`);

        return result.join(' ');
    }

    startClientDetailsMonitoring(routerId, clientIds) {
        if (!app.socket) return;

        if (app.socket.connected) {
            app.socket.emit('join_router', { router_id: routerId });
            app.socket.emit('subscribe_clients', { router_id: routerId, client_ids: clientIds });

            // Escuchar actualizaciones de tráfico (Solo si esta vista está activa para evitar fugas)
            const trafficHandler = (data) => {
                if (!document.getElementById('status-clients-list')) {
                    app.socket.off('client_traffic', trafficHandler);
                    return;
                }
                Object.keys(data).forEach(clientId => {
                    const trafficEl = document.getElementById(`traffic-${clientId}`);
                    if (trafficEl) {
                        const downEl = trafficEl.querySelector('.val-down');
                        const upEl = trafficEl.querySelector('.val-up');
                        if (downEl) downEl.textContent = this.formatSpeedModal(data[clientId].download || 0);
                        if (upEl) upEl.textContent = this.formatSpeedModal(data[clientId].upload || 0);
                    }
                });
            };
            app.socket.on('client_traffic', trafficHandler);
        }
    }

    stopClientDetailsMonitoring() {
        // No apagamos 'client_traffic' globalmente porque otros módulos lo usan.
        // Los handlers locales se auto-limpian.
    }

    formatSpeedModal(bps) {
        if (bps >= 1000000) return (bps / 1000000).toFixed(1) + ' Mbps';
        if (bps >= 1000) return (bps / 1000).toFixed(1) + ' Kbps';
        return bps + ' bps';
    }
}
