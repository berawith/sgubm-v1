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
            // Silencioso para monitoreo recurrente
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
        const setSafeText = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };

        setSafeText('stat-servers', stats.total_servers || 0);
        setSafeText('stat-total-clients', stats.total_clients || 0);
        setSafeText('stat-active-clients', stats.active_clients || 0);
        setSafeText('stat-suspended-clients', stats.suspended_clients || 0);
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
                ${this.servers.map(server => `
                    <div class="elegant-item" onclick="app.modules.dashboard.showRouterDetails(${server.id})" style="display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid #f8fafc; cursor: pointer; transition: background 0.2s;">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <span class="status-indicator ${server.status || 'offline'}" title="${server.status || 'offline'}"></span>
                            <div style="display: flex; flex-direction: column;">
                                <span style="font-weight: 600; color: #1e293b; font-size: 0.875rem;">${server.alias || 'Router'}</span>
                                <span style="color: #94a3b8; font-size: 0.75rem; font-family: 'JetBrains Mono', monospace;">${server.host_address || 'N/A'}</span>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <span style="font-weight: 700; color: #6366f1; font-size: 0.75rem;">
                                ${server.clients_connected || 0} <span style="font-weight: 500; opacity: 0.7;">cli</span>
                            </span>
                            <div style="display: flex; gap: 4px;">
                                <button class="action-btn-xs minimal" onclick="event.stopPropagation(); app.modules.dashboard.showRouterGraph(${server.id}, '${server.alias}')" style="background: transparent; border: none; color: #cbd5e1; cursor: pointer;">
                                    <i class="fas fa-chart-line"></i>
                                </button>
                                <button class="action-btn-xs minimal" onclick="event.stopPropagation(); app.modules.dashboard.syncRouter(${server.id})" style="background: transparent; border: none; color: #cbd5e1; cursor: pointer;">
                                    <i class="fas fa-sync-alt"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // --- Action Handlers ---

    async syncRouter(routerId) {
        if (!confirm('¿Deseas sincronizar este router con MikroTik ahora?')) return;

        try {
            app.showLoading(true);
            const response = await this.api.post(`/api/routers/${routerId}/sync`, { confirm: true });

            if (response.success) {
                alert(`Sincronización exitosa: ${response.message}`);
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
        const content = document.getElementById(tabId);
        if (content) content.classList.add('active');

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
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #f1f5f9; font-weight: 500;">
                        <span style="color:#94a3b8; font-size:0.7rem; margin-right:5px;">${idx + 1}.</span> ${c.subscriber_code}
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #f1f5f9;">${c.legal_name}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #f1f5f9; font-family: 'JetBrains Mono';">${c.ip_address || '-'}</td>
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
            } else {
                toast.error(data.message || 'Error al escanear router');
            }
        } catch (e) {
            console.error(e);
            toast.error('Error durante el escaneo del router');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-sync"></i> Sincronizar Ahora';
        }
    }

    async confirmSync() {
        if (!this.activeRouterId) return;

        app.showLoading(true);
        try {
            const data = await this.api.post(`/api/routers/${this.activeRouterId}/sync`, { confirm: true });
            if (data.success) {
                toast.success(data.message);
                document.getElementById('sync-preview-container').style.display = 'none';
                this.loadRouterClients(); // Recargar lista
            } else {
                toast.error(data.message);
            }
        } catch (e) {
            toast.error('Error en la sincronización final');
        } finally {
            app.showLoading(false);
        }
    }

    async loadRouterInterfaces() {
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
            container.innerHTML = '<p style="color: #94a3b8; padding: 1rem; font-size: 0.875rem;">No hay actividad reciente</p>';
            return;
        }

        container.innerHTML = activities.map(activity => `
            <div class="activity-item">
                <div style="width: 32px; height: 32px; border-radius: 8px; background: #f8fafc; display: flex; align-items: center; justify-content: center; color: #64748b; flex-shrink: 0;">
                    <i class="fas fa-${this.getActivityIcon(activity.type)}" style="font-size: 0.875rem;"></i>
                </div>
                <div class="activity-content">
                    <p style="font-size: 0.875rem; color: #1e293b; font-weight: 500; margin-bottom: 2px;">${activity.message}</p>
                    <p style="font-size: 0.75rem; color: #94a3b8;">${activity.time_ago || 'Hace un momento'}</p>
                </div>
            </div>
        `).join('');
    }

    formatUptime(uptime) {
        if (!uptime || uptime === 'N/A') return 'N/A';
        // Traducir unidades crudas de MikroTik a versión corta: 2w5d -> 2sem 5d
        return uptime
            .replace(/(\d+)w/g, '$1sem ')
            .replace(/(\d+)d/g, '$1d ')
            .replace(/(\d+)h/g, '$1h ')
            .replace(/(\d+)m/g, '$1m ')
            .replace(/(\d+)s/g, '$1s ')
            .trim();
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


}
