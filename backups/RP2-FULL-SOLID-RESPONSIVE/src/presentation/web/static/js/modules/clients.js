/**
 * Clients Module - Frontend para gestión de clientes
 */
export class ClientsModule {
    constructor(api, eventBus) {
        this.api = api;
        this.eventBus = eventBus;
        this.clients = [];
        this.routers = [];
        this.selectedRouter = null; // ID del router seleccionado
        this.selectedStatus = 'all';

        console.log('👥 Clients Module initialized');
    }

    async load() {
        console.log('👥 Loading Clients...');
        this.showView();

        // Cargar routers primero
        await this.loadRouters();

        // Auto-seleccionar primer router si no hay selección
        if (!this.selectedRouter && this.routers.length > 0) {
            this.selectedRouter = this.routers[0].id;
        }

        // Renderizar pestañas de Routers
        this.renderRouterTabs();

        // Cargar clientes (filtrados por el router seleccionado)
        await this.loadClients();
    }

    renderRouterTabs() {
        const view = document.getElementById('clients-view');
        if (!view) return;

        // Buscar o crear contenedor de tabs
        let tabsContainer = document.getElementById('router-tabs-container');
        if (!tabsContainer) {
            tabsContainer = document.createElement('div');
            tabsContainer.id = 'router-tabs-container';
            tabsContainer.className = 'router-tabs-container';

            // Insertar después del header
            const header = view.querySelector('.clients-header') || view.querySelector('.view-header');
            if (header) {
                header.insertAdjacentElement('afterend', tabsContainer);
            } else {
                view.prepend(tabsContainer);
            }
        }

        if (this.routers.length === 0) {
            tabsContainer.innerHTML = '<div style="color:#666; font-style:italic; padding:10px;">No hay routers configurados</div>';
            return;
        }

        // Generar botones
        tabsContainer.innerHTML = this.routers.map(router => {
            const isActive = (this.selectedRouter == router.id);
            const className = isActive ? 'router-tab active' : 'router-tab';

            return `
                <button 
                    class="${className}"
                    onclick="app.modules.clients.selectRouter(${router.id})"
                >
                    <i class="fas fa-network-wired"></i>
                    ${router.alias}
                </button>
            `;
        }).join('');
    }

    async selectRouter(routerId) {
        if (this.selectedRouter == routerId) return;

        this.selectedRouter = routerId;
        this.renderRouterTabs(); // Actualizar UI de tabs
        await this.loadClients(); // Recargar clientes
    }

    showView() {
        document.querySelectorAll('.content-view').forEach(v => v.classList.remove('active'));
        const view = document.getElementById('clients-view');
        if (view) view.classList.add('active');
    }

    async loadRouters() {
        try {
            this.routers = await this.api.get('/api/routers');
        } catch (error) {
            console.error('Error loading routers:', error);
        }
    }

    async loadClients() {
        try {
            let url = '/api/clients';
            const params = [];

            if (this.selectedRouter) {
                params.push(`router_id=${this.selectedRouter}`);
            }
            if (this.selectedStatus !== 'all') {
                params.push(`status=${this.selectedStatus.toUpperCase()}`);
            }

            if (params.length > 0) {
                url += '?' + params.join('&');
            }

            this.clients = await this.api.get(url);
            this.renderClients();
        } catch (error) {
            console.error('Error loading clients:', error);
            this.clients = [];
            this.renderClients();
        }
    }

    renderClients() {
        // Inicializar estado
        if (!this.onlineStatusMap) this.onlineStatusMap = {};
        // Por defecto mostrar solo ONLINE como principal
        this.currentFilter = this.currentFilter || 'ONLINE';

        // Actualizar estadísticas estáticas
        this.updateStaticStats();

        const grid = document.getElementById('clients-grid');
        if (!grid) return;

        if (this.clients.length === 0) {
            grid.innerHTML = `
                <div class="no-clients">
                    <i class="fas fa-users"></i>
                    <p>No hay clientes asociados a este Router</p>
                    <button onclick="app.modules.clients.showImportModal()" class="btn-primary">
                        <i class="fas fa-file-import"></i> Importar Clientes
                    </button>
                </div>
            `;
            return;
        }

        grid.innerHTML = this.clients.map(client => `
             <div class="client-card ${client.status.toLowerCase()}" data-client-id="${client.id}" data-username="${client.username}">
                <!-- Header Compacto -->
                <div class="client-card-header">
                    <div class="client-id-group">
                        <span class="client-status-badge ${client.status.toLowerCase()}">${client.id}</span>
                        <span class="subscriber-code">${client.subscriber_code}</span>
                    </div>
                    <div class="financial-info">
                        <span class="balance ${client.account_balance >= 0 ? 'positive' : 'negative'}">
                            $${client.account_balance?.toLocaleString() || '0'}
                        </span>
                        <span class="separator">|</span>
                        <span class="monthly-fee"> $${client.monthly_fee?.toLocaleString() || '0'}</span>
                    </div>
                </div>

                <!-- Info Principal -->
                <div class="client-identity">
                    <h3 class="client-name">${client.legal_name}</h3>
                    <div class="client-username">
                        <i class="fas fa-user"></i> ${client.username} 
                        <span class="status-dot offline"></span>
                    </div>
                </div>

                <!-- Specs Compactas -->
                <div class="client-info-box">
                    <div class="info-row">
                        <span class="plan-name">${this.formatPlanName(client.plan_name)}</span>
                        <span class="speed-value">0 K / 0 K</span>
                    </div>
                    <div class="info-row sub-detail">
                        <span class="ip-display">${client.ip_address || '---'}</span>
                        <span class="uptime-value">Uptime: --</span>
                    </div>
                </div>

                <!-- Footer Acciones -->
                <div class="client-card-footer">
                    <div class="client-actions">
                        <button onclick="app.modules.clients.editClient(${client.id})" title="Editar" class="btn-secondary">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                        </button>
                        ${client.status.toUpperCase() === 'ACTIVE' ?
                `<button onclick="app.modules.clients.suspendClient(${client.id})" title="Suspender" class="btn-warning">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>
                            </button>` :
                `<button onclick="app.modules.clients.activateClient(${client.id})" title="Activar" class="btn-success">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                            </button>`
            }
                        <button onclick="app.modules.clients.registerPayment(${client.id})" title="Pago" class="btn-secondary">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
                        </button>
                        <button onclick="app.modules.clients.deleteClient(${client.id})" title="Eliminar" class="btn-danger">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                    </div>
                </div>
                
                <div class="client-router-label">
                    ${client.router ? client.router.substring(0, 20) : 'Sin Router'}
                </div>
            </div>
        `).join('');

        this.setupStatsListeners();
        this.startTrafficMonitor();
        this.setFilter(this.currentFilter);
    }

    updateStaticStats() {
        const total = this.clients.length;
        const active = this.clients.filter(c => c.status.toUpperCase() === 'ACTIVE').length;
        const suspended = this.clients.filter(c => c.status.toUpperCase() === 'SUSPENDED').length;

        const elTotal = document.getElementById('count-total');
        if (elTotal) elTotal.textContent = total;

        const elActive = document.getElementById('count-active');
        if (elActive) elActive.textContent = active;

        const elSuspended = document.getElementById('count-suspended');
        if (elSuspended) elSuspended.textContent = suspended;
    }

    startTrafficMonitor() {
        this.stopTrafficMonitor();
        if (this.clients.length === 0) return;

        const check = async () => {
            const visibleIds = this.clients.map(c => c.id);
            if (visibleIds.length === 0) return;
            try {
                const trafficData = await this.api.post('/api/clients/monitor', visibleIds);
                this.updateTrafficUI(trafficData);
            } catch (e) { }
        };

        check();
        this.monitorInterval = setInterval(check, 3000);
    }

    stopTrafficMonitor() {
        if (this.monitorInterval) {
            clearInterval(this.monitorInterval);
            this.monitorInterval = null;
        }
    }

    updateTrafficUI(data) {
        if (!this.onlineStatusMap) this.onlineStatusMap = {};

        // 1. Actualizar mapa de estados
        Object.keys(data).forEach(clientId => {
            const info = data[clientId];
            this.onlineStatusMap[clientId] = info.status;
        });

        // 2. Calcular contadores ONLINE/OFFLINE
        let onlineCount = 0;
        let offlineCount = 0;

        this.clients.forEach(c => {
            const status = this.onlineStatusMap[c.id] || 'offline';
            if (status === 'online') onlineCount++;
            else offlineCount++;
        });

        // 3. Actualizar tarjetas
        Object.keys(data).forEach(clientId => {
            const card = document.querySelector(`.client-card[data-client-id="${clientId}"]`);
            if (card) {
                const info = data[clientId];

                const dot = card.querySelector('.status-dot');
                if (dot) dot.className = `status-dot ${info.status}`;

                const speedVal = card.querySelector('.speed-value');
                const uptimeVal = card.querySelector('.uptime-value');
                const ipDisplay = card.querySelector('.ip-display');

                if (speedVal && uptimeVal) {
                    if (info.status === 'online') {
                        const down = this.formatSpeed(info.download);
                        const up = this.formatSpeed(info.upload);
                        speedVal.textContent = `${down} / ${up}`;

                        uptimeVal.style.display = 'block';
                        uptimeVal.textContent = `Uptime: ${info.uptime}`;

                        if (info.ip_address && ipDisplay) ipDisplay.textContent = info.ip_address;
                    } else {
                        speedVal.textContent = 'Offline';
                        speedVal.className = 'speed-value offline';
                        uptimeVal.style.display = 'none';
                    }
                }
            }
        });

        // 4. Actualizar contadores dinámicos
        const elOnline = document.getElementById('count-online');
        if (elOnline) elOnline.textContent = onlineCount;

        const elOffline = document.getElementById('count-offline');
        if (elOffline) elOffline.textContent = offlineCount;

        // 5. Re-aplicar filtro si es necesario
        if (this.currentFilter === 'ONLINE' || this.currentFilter === 'OFFLINE') {
            this.applyFilter();
        }
    }

    formatSpeed(bits) {
        const b = parseInt(bits);
        if (isNaN(b) || b === 0) return '0 Kbps';
        if (b < 1000) return b + ' bps';
        if (b < 1000000) return (b / 1000).toFixed(1) + ' Kbps';
        return (b / 1000000).toFixed(1) + ' Mbps';
    }

    formatPlanName(planName) {
        if (!planName) return 'Sin Plan';

        // Si el plan contiene números grandes (como "15000000/15000000"), formatearlos
        // Buscar patrones como "15000000/15000000" o "15000000" individual
        return planName.replace(/(\d{6,})/g, (match) => {
            const num = parseInt(match);
            if (num >= 1000000) {
                return (num / 1000000) + 'M';
            } else if (num >= 1000) {
                return (num / 1000) + 'K';
            }
            return match;
        });
    }

    setupEventListeners() {
        const addBtn = document.getElementById('add-client-btn');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.showCreateModal());
        }

        const importBtn = document.getElementById('import-clients-btn');
        if (importBtn) {
            importBtn.addEventListener('click', () => this.showImportModal());
        }

        const routerFilter = document.getElementById('router-filter');
        if (routerFilter) {
            routerFilter.addEventListener('change', (e) => {
                this.selectedRouter = e.target.value || null;
                this.loadClients();
            });
        }

        const statusFilter = document.getElementById('status-filter');
        if (statusFilter) {
            statusFilter.addEventListener('change', (e) => {
                this.selectedStatus = e.target.value;
                this.loadClients();
            });
        }

        const searchInput = document.getElementById('client-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchClients(e.target.value);
            });
        }

        this.setupStatsListeners();
    }

    async searchClients(query) {
        if (!query || query.length < 2) {
            await this.loadClients();
            return;
        }

        try {
            this.clients = await this.api.get(`/api/clients?search=${encodeURIComponent(query)}`);
            this.renderClients();
        } catch (error) {
            console.error('Error searching clients:', error);
        }
    }

    showCreateModal() {
        if (window.clientModal) {
            window.clientModal.showCreate();
        } else {
            console.error('Client Modal not loaded');
        }
    }

    async editClient(clientId) {
        const client = this.clients.find(c => c.id === clientId);
        if (client && window.clientModal) {
            window.clientModal.showEdit(client);
        } else {
            console.error('Client not found or Modal not loaded', clientId);
        }
    }

    async suspendClient(clientId) {
        if (!confirm('¿Suspender este cliente?')) return;

        try {
            await this.api.post(`/api/clients/${clientId}/suspend`, {});
            await this.loadClients();
            alert('Cliente suspendido correctamente');
        } catch (error) {
            console.error('Error suspending client:', error);
            alert('Error al suspender cliente');
        }
    }

    async activateClient(clientId) {
        if (!confirm('¿Activar este cliente?')) return;

        try {
            await this.api.post(`/api/clients/${clientId}/activate`, {});
            await this.loadClients();
            alert('Cliente activado correctamente');
        } catch (error) {
            console.error('Error activating client:', error);
            alert('Error al activar cliente');
        }
    }

    async deleteClient(clientId) {
        if (!confirm('¿Eliminar este cliente? Esta acción no se puede deshacer.')) return;

        try {
            await this.api.delete(`/api/clients/${clientId}`);
            await this.loadClients();
            alert('Cliente eliminado correctamente');
        } catch (error) {
            console.error('Error deleting client:', error);
            alert('Error al eliminar cliente');
        }
    }

    async registerPayment(clientId) {
        const amount = prompt('Monto del pago:');
        if (!amount) return;

        const method = prompt('Método de pago (cash/transfer/card):');

        try {
            await this.api.post(`/api/clients/${clientId}/register-payment`, {
                amount: parseFloat(amount),
                payment_method: method || 'cash',
                notes: `Pago registrado el ${new Date().toLocaleDateString()}`
            });
            await this.loadClients();
            alert('Pago registrado correctamente');
        } catch (error) {
            console.error('Error registering payment:', error);
            alert('Error al registrar pago');
        }
    }

    async showImportModal() {
        const modal = document.getElementById('import-clients-modal');
        if (!modal) return;

        modal.classList.add('active');
        this.resetImport();

        try {
            const select = document.getElementById('import-router-select');
            let routers = this.routers;
            if (routers.length === 0) {
                routers = await this.api.get('/api/routers');
                this.routers = routers;
            }

            if (routers.length === 0) {
                select.innerHTML = '<option value="">No hay routers configurados</option>';
            } else {
                select.innerHTML = '<option value="">Selecciona un router...</option>' +
                    routers.map(r => `<option value="${r.id}">${r.alias} (${r.host_address})</option>`).join('');
            }
        } catch (e) {
            console.error(e);
            alert('Error cargando routers');
        }
    }

    resetImport() {
        document.getElementById('import-step-1').style.display = 'block';
        document.getElementById('import-step-2').style.display = 'none';
        document.getElementById('import-loading').style.display = 'none';
        document.getElementById('import-preview-body').innerHTML = '';
        document.getElementById('select-all-import').checked = false;
        this.previewData = [];
    }

    async scanRouter() {
        const routerId = document.getElementById('import-router-select').value;
        if (!routerId) return alert('Por favor selecciona un router');

        document.getElementById('import-loading').style.display = 'flex';
        document.getElementById('import-loading-text').textContent = 'Escaneando router... (Esto puede tardar unos segundos)';

        try {
            const result = await this.api.get(`/api/clients/preview-import/${routerId}`);
            this.renderPreview(result);

            document.getElementById('import-step-1').style.display = 'none';
            document.getElementById('import-step-2').style.display = 'block';
        } catch (e) {
            console.error(e);
            alert('Error escaneando router: ' + (e.message || 'Verifica la conexión'));
        } finally {
            document.getElementById('import-loading').style.display = 'none';
        }
    }

    renderPreview(data) {
        const tbody = document.getElementById('import-preview-body');
        document.getElementById('scan-total').textContent = data.total_found;

        this.previewData = data.clients || [];

        // Detectar clientes sin Simple Queues
        const needsProvisioning = data.summary?.needs_provisioning || false;
        const discoveredCount = data.summary?.discovered_no_queue || 0;
        const routerId = data.router_id;
        const routerName = data.router_alias;

        let hasDuplicates = false;

        tbody.innerHTML = this.previewData.map((client, index) => {
            if (client.exists_in_db) hasDuplicates = true;

            const isDuplicate = client.exists_in_db;
            const rowClass = isDuplicate ? 'duplicate-row' : '';
            const checkbox = isDuplicate
                ? `<input type="checkbox" disabled>`
                : `<input type="checkbox" class="import-check" data-index="${index}" onchange="app.modules.clients.updateSelectedCount()">`;

            const statusBadge = isDuplicate
                ? `<span class="badge warning">Registrado</span>`
                : `<span class="badge success">Nuevo</span>`;

            return `<tr class="${rowClass}">
                <td>${checkbox}</td>
                <td>
                    <div class="user-info">
                        <strong>${client.username}</strong>
                        <small style="color:#888; display:block; font-size:0.8em">${client.type.toUpperCase()}</small>
                    </div>
                </td>
                <td>${client.ip_address}</td>
                <td>${client.profile}</td>
                <td>${statusBadge}</td>
            </tr>`;
        }).join('');

        const dupMsg = document.getElementById('scan-duplicates');
        if (dupMsg) dupMsg.style.display = hasDuplicates ? 'block' : 'none';

        // NUEVA FUNCIONALIDAD: Mostrar alerta si hay clientes sin Simple Queues
        if (needsProvisioning && discoveredCount > 0) {
            const alertDiv = document.createElement('div');
            alertDiv.id = 'auto-provision-alert';
            alertDiv.style.cssText = `
                background: linear-gradient(135deg, rgba(255,196,75,0.15), rgba(255,152,0,0.15));
                border: 2px solid #FFC44B;
                border-radius: 12px;
                padding: 20px;
                margin: 15px 0;
                display: flex;
                align-items: center;
                gap: 15px;
                animation: slideInDown 0.3s ease;
            `;

            alertDiv.innerHTML = `
                <div style="flex-shrink: 0;">
                    <i class="fas fa-exclamation-triangle" style="font-size: 2rem; color: #FFC44B;"></i>
                </div>
                <div style="flex: 1;">
                    <h4 style="margin: 0 0 8px 0; color: #FFC44B; font-size: 1.1rem;">
                        ⚠️ ${discoveredCount} cliente${discoveredCount > 1 ? 's' : ''} sin Simple Queue
                    </h4>
                    <p style="margin: 0; color: #ddd; font-size: 0.9rem;">
                        Se detectaron ${discoveredCount} cliente${discoveredCount > 1 ? 's' : ''} conectado${discoveredCount > 1 ? 's' : ''} en la red 
                        (DHCP/ARP) pero sin Simple Queue configurada en el router <strong>${routerName}</strong>.
                    </p>
                </div>
                <div style="flex-shrink: 0;">
                    <button 
                        onclick="app.modules.clients.redirectToRouterSync(${routerId}, '${routerName}')"
                        style="
                            background: linear-gradient(135deg, #FFC44B, #FF9800);
                            color: #000;
                            border: none;
                            padding: 12px 24px;
                            border-radius: 8px;
                            font-weight: 600;
                            cursor: pointer;
                            white-space: nowrap;
                            transition: all 0.3s ease;
                            box-shadow: 0 4px 15px rgba(255,196,75,0.3);
                        "
                        onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 20px rgba(255,196,75,0.4)'"
                        onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 15px rgba(255,196,75,0.3)'"
                    >
                        <i class="fas fa-sync-alt"></i>
                        Sincronizar Router
                    </button>
                </div>
            `;

            // Insertar antes de la tabla
            const table = document.getElementById('import-preview-body').closest('table');
            if (table && table.parentNode) {
                // Remover alerta anterior si existe
                const oldAlert = document.getElementById('auto-provision-alert');
                if (oldAlert) oldAlert.remove();

                table.parentNode.insertBefore(alertDiv, table);
            }
        }

        const selectAll = document.getElementById('select-all-import');
        selectAll.onclick = (e) => {
            const checks = document.querySelectorAll('.import-check:not(:disabled)');
            checks.forEach(c => c.checked = e.target.checked);
            this.updateSelectedCount();
        };

        this.updateSelectedCount();
    }

    redirectToRouterSync(routerId, routerName) {
        // Cerrar el modal de importación
        const modal = document.getElementById('import-clients-modal');
        if (modal) modal.classList.remove('active');

        // Mostrar confirmación
        if (confirm(`¿Deseas sincronizar el router "${routerName}" para crear Simple Queues automáticamente para los clientes descubiertos?`)) {
            // Navegar al módulo de routers
            this.eventBus.publish('navigate', { view: 'routers' });

            // Pequeño delay para que cargue el módulo
            setTimeout(() => {
                // Seleccionar el router y abrir el panel de sincronización
                if (window.app && window.app.modules && window.app.modules.routers) {
                    const routerModule = window.app.modules.routers;
                    // Llamar al método de sincronización del módulo routers
                    routerModule.syncRouter(routerId);
                }
            }, 500);
        }
    }

    updateSelectedCount() {
        const count = document.querySelectorAll('.import-check:checked').length;
        document.getElementById('selected-count').textContent = count;
    }

    async executeImport() {
        const routerId = document.getElementById('import-router-select').value;
        const checks = document.querySelectorAll('.import-check:checked');

        if (checks.length === 0) return alert('Selecciona al menos un cliente');

        const selectedClients = Array.from(checks).map(c => this.previewData[c.dataset.index]);

        document.getElementById('import-loading').style.display = 'flex';
        document.getElementById('import-loading-text').textContent = `Importando ${checks.length} clientes...`;

        try {
            const response = await this.api.post('/api/clients/execute-import', {
                router_id: routerId,
                clients: selectedClients
            });

            if (response.success) {
                alert(`Importación completada: ${response.imported} clientes importados.`);
                document.getElementById('import-clients-modal').classList.remove('active');
                this.loadClients();
            } else {
                alert('Hubo errores en la importación:\n' + response.errors.join('\n'));
            }
        } catch (e) {
            alert('Error en importación: ' + e.message);
        } finally {
            document.getElementById('import-loading').style.display = 'none';
        }
    }

    setupStatsListeners() {
        const filters = [
            { id: 'count-total', type: 'ALL' },
            { id: 'count-active', type: 'ACTIVE' },
            { id: 'count-suspended', type: 'SUSPENDED' },
            { id: 'count-online', type: 'ONLINE' },
            { id: 'count-offline', type: 'OFFLINE' }
        ];

        filters.forEach(f => {
            const el = document.getElementById(f.id)?.parentElement;
            if (el) {
                el.style.cursor = 'pointer';
                el.onclick = () => this.setFilter(f.type);
                el.setAttribute('title', 'Filtrar por ' + f.type);
            }
        });
    }

    setFilter(type) {
        this.currentFilter = type; // 'ALL', 'ACTIVE', 'SUSPENDED', 'ONLINE', 'OFFLINE'

        // Feedback visual en la barra - Usar clases CSS en lugar de inline styles
        document.querySelectorAll('.client-stats-bar .stat-item').forEach(el => {
            el.classList.remove('active');
        });

        const activeId = {
            'ALL': 'count-total',
            'ACTIVE': 'count-active',
            'SUSPENDED': 'count-suspended',
            'ONLINE': 'count-online',
            'OFFLINE': 'count-offline'
        }[type];

        const activeEl = document.getElementById(activeId)?.parentElement;
        if (activeEl) {
            activeEl.classList.add('active');
        }

        this.applyFilter();
    }

    applyFilter() {
        const cards = document.querySelectorAll('.client-card');
        const searchTerm = document.getElementById('client-search')?.value.toLowerCase() || '';

        cards.forEach(card => {
            const clientId = card.getAttribute('data-client-id');
            const client = this.clients.find(c => c.id == clientId);

            if (!client) return;

            const status = client.status.toUpperCase();
            const isOnline = (this.onlineStatusMap && this.onlineStatusMap[clientId] === 'online');

            let visible = true;

            if (this.currentFilter === 'ACTIVE') visible = (status === 'ACTIVE');
            else if (this.currentFilter === 'SUSPENDED') visible = (status === 'SUSPENDED');
            else if (this.currentFilter === 'ONLINE') visible = isOnline;
            else if (this.currentFilter === 'OFFLINE') visible = !isOnline;

            if (visible && searchTerm) {
                const text = (client.username + ' ' + client.legal_name + ' ' + (client.ip_address || '')).toLowerCase();
                visible = text.includes(searchTerm);
            }

            card.style.display = visible ? 'flex' : 'none';
        });
    }
}
