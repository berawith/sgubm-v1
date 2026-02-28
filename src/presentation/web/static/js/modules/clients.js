/**
 * Clients Module - Frontend para gestión de clientes (Table View)
 */
export class ClientsModule {
    constructor(api, eventBus, viewManager, modalManager = null) {
        this.api = api;
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.modalManager = modalManager;
        this.clients = [];
        this.routers = [];
        this.plans = []; // Store plans for filtering

        // State
        this.filterState = {
            routerId: '',
            status: 'all',
            planId: '',
            collectorId: '',
            search: '',
            financialStatus: 'all' // 'all', 'morosos', 'paid'
        };

        this.socketInitialized = false;
        this.trafficCache = {}; // Cache for real-time traffic values {clientId: {up, down}}
        this.importSort = { column: '', direction: 'asc' };
        this.sortState = { column: 'id', direction: 'asc' };
        this.trashState = { search: '', clients: [], selectedIds: new Set(), sort: { column: 'updated_at', direction: 'desc' } };

        // Pagination State
        this.currentPage = 1;
        this.pageSize = 50;
        this.totalFiltered = 0;
        this.selectedIds = new Set();

        // Online Status & Cache
        this.onlineStatusMap = {};
        this.trafficCache = {};
        this.trafficBuffer = {};
        this.lastTrafficUpdate = 0;

        // Monitoring
        this.rowCache = new Map();


        // Auto-resubscribir cuando el socket se conecte (o reconecte)
        if (!ClientsModule._socketListenerAdded) {
            this.eventBus.subscribe('socket_connected', () => {
                console.log('🔄 Socket connected: restarting client monitoring...');
                this.startTrafficMonitor();
            });
            ClientsModule._socketListenerAdded = true;
        }

        // Handle visibility change to recover from suspended state
        if (!ClientsModule._visibilityListenerAdded) {
            document.addEventListener('visibilitychange', () => {
                if (!document.hidden && this.socketInitialized) {
                    console.log('👁️ Tab visible: forcing traffic UI update');
                    // Force update immediately if we have buffered data
                    if (Object.keys(this.trafficBuffer).length > 0) {
                        this.updateTrafficUI(this.trafficBuffer);
                        this.trafficBuffer = {};
                        this.lastTrafficUpdate = Date.now();
                    }
                }
            });
            ClientsModule._visibilityListenerAdded = true;
        }

        // Throttling
        this.isUpdatePending = false;
        this.trafficBuffer = {};
        this.lastTrafficUpdate = 0;
        this.trafficUpdateInterval = 1000;

        // REAL-TIME DATA REFRESH (SI EL EVENTO ES DE CLIENTE)
        this.eventBus.subscribe('data_refresh', (data) => {
            if (this.viewManager.currentSubView === 'clients' || this.viewManager.currentSubView === 'clients-list') {
                if (data.event_type && data.event_type.startsWith('client.')) {
                    console.log(`♻️ Real-time: Refreshing clients list due to ${data.event_type}`);
                    // Throttled refresh to prevent blinking if many events arrive
                    if (this._refreshTimeout) clearTimeout(this._refreshTimeout);
                    this._refreshTimeout = setTimeout(() => this.loadClients(), 300);
                }
            }
        });

        // Mobile View Detection
        this.isMobile = window.innerWidth < 1100;
        window.addEventListener('resize', () => {
            const wasMobile = this.isMobile;
            this.isMobile = window.innerWidth < 1100;
            if (wasMobile !== this.isMobile && (this.viewManager.currentSubView === 'clients' || this.viewManager.currentSubView === 'clients-list')) {
                this.renderClients();
            }
        });

        console.log('👥 Clients Module initialized');
    }

    async load(params = {}) {
        console.log('👥 Loading Clients List...', params);

        const tbody = document.getElementById('clients-table-body');
        if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="loading-cell"><div class="spinner"></div><p>Cargando Clientes...</p></td></tr>';

        try {
            await Promise.all([this.loadRouters(), this.loadPlans(), this.loadCollectors()]);

            // Handle external filters from navigation
            if (params.routerId || params.status || params.financialStatus) {
                if (params.routerId) this.filterState.routerId = params.routerId;
                if (params.status) this.filterState.status = params.status;
                if (params.financialStatus) this.filterState.financialStatus = params.financialStatus;

                // Sync UI select elements
                const routerSelect = document.getElementById('filter-router');
                const statusSelect = document.getElementById('filter-status');
                if (routerSelect) routerSelect.value = this.filterState.routerId;
                if (statusSelect) statusSelect.value = this.filterState.status;

                this.updatePillActiveState();
            } else if (!this.filterState.routerId && this.routers.length > 0) {
                // Default fallback if no params provided
                this.filterState.routerId = this.routers[0].id;
                const routerSelect = document.getElementById('filter-router');
                if (routerSelect) routerSelect.value = this.filterState.routerId;
            }

            // RBAC: If user is a collector, fix the collector filter to their ID
            const user = window.app?.authService?.getUser();
            if (user && (user.role === 'collector' || user.role === 'cobrador')) {
                this.filterState.collectorId = user.id;
            }

            await this.loadClients();
            this.setupStatsListeners();
        } catch (e) {
            console.error('Error during load:', e);
        }
    }

    async loadClientsImport() {
        console.log('👥 Loading Clients Import View...');

        this.resetImport('view');

        try {
            const select = document.getElementById('import-view-router-select');
            if (!select) return;

            let routers = this.routers;
            if (routers.length === 0) {
                routers = await this.api.get('/api/routers');
                this.routers = routers;
            }

            if (routers.length === 0) {
                select.innerHTML = '<option value="">No hay routers configurados</option>';
            } else {
                select.innerHTML = '<option value="">Selecciona un router...</option>' +
                    routers.map(r => {
                        const status = (r.status || 'offline').toUpperCase();
                        const color = status === 'ONLINE' ? '🟢' : '🔴';
                        return `<option value="${r.id}" ${status !== 'ONLINE' ? 'style="color: #94a3b8;"' : ''}>${color} ${r.alias} (${r.host_address})</option>`;
                    }).join('');

                if (this.filterState.routerId) {
                    select.value = this.filterState.routerId;
                }
            }
        } catch (e) {
            console.error('Error loading import view:', e);
            toast.error('Error al cargar routers para importación');
        }
    }

    async loadClientsActions() {
        console.log('⚡ Loading Clients Actions View...');

        const tbody = document.getElementById('clients-table-body-actions');
        if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="loading-cell"><div class="spinner"></div><p>Cargando Clientes...</p></td></tr>';

        try {
            await this.loadRouters();
            this.populateRouterFilterActions();

            if (!this.filterState.routerId && this.routers.length > 0) {
                this.filterState.routerId = this.routers[0].id;
                const routerSelect = document.getElementById('filter-router-actions');
                if (routerSelect) routerSelect.value = this.filterState.routerId;
            }

            await this.loadClientsForActions();
        } catch (e) {
            console.error('Error loading actions view:', e);
        }
    }

    populateRouterFilterActions() {
        const select = document.getElementById('filter-router-actions');
        if (!select) return;

        const currentVal = select.value || this.filterState.routerId;
        select.innerHTML = '<option value="">Todos los Routers</option>' +
            this.routers.map(r => `<option value="${r.id}">${r.alias}</option>`).join('');

        if (currentVal) select.value = currentVal;
    }

    async loadTrash() {
        console.log('🗑️ Loading Clients Trash...');
        this.trashState.selectedIds.clear();
        this.updateTrashSelectionUI();

        const tbody = document.getElementById('clients-trash-table-body');
        if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="loading-cell"><div class="spinner"></div><p>Cargando Papelera...</p></td></tr>';

        try {
            const response = await this.api.get('/api/clients?status=deleted');
            this.trashState.clients = response || [];
            this.renderTrash();
        } catch (e) {
            console.error('Error loading trash:', e);
            if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="error-cell">Error al cargar la papelera</td></tr>';
        }
    }

    onTrashSearch(value) {
        this.trashState.search = value.toLowerCase();
        this.renderTrash();
    }

    sortTrash(column) {
        if (this.trashState.sort.column === column) {
            this.trashState.sort.direction = this.trashState.sort.direction === 'asc' ? 'desc' : 'asc';
        } else {
            this.trashState.sort = { column: column, direction: 'asc' };
        }
        this.renderTrash();
    }

    async confirmEmptyTrash() {
        if (await this.modalManager.confirm({
            title: 'Vaciar Papelera',
            content: '¿Estás seguro de que deseas eliminar permanentemente todos los clientes en la papelera? Esta acción no se puede deshacer.',
            type: 'danger',
            confirmText: 'Sí, Vaciar Papelera'
        })) {
            this.emptyTrash();
        }
    }

    renderTrash() {
        const tbody = document.getElementById('clients-trash-table-body');
        const countSpan = document.getElementById('clients-trash-count-total');
        const selectAllCheck = document.getElementById('clients-trash-select-all');
        if (!tbody) return;

        let filtered = this.trashState.clients.filter(c => {
            const search = this.trashState.search;
            return !search ||
                (c.legal_name && c.legal_name.toLowerCase().includes(search)) ||
                (c.subscriber_code && c.subscriber_code.toLowerCase().includes(search)) ||
                (c.ip_address && c.ip_address.includes(search));
        });

        // Sorting
        const { column, direction } = this.trashState.sort;
        filtered.sort((a, b) => {
            let valA = a[column] || '';
            let valB = b[column] || '';

            if (column === 'id') {
                valA = parseInt(valA) || 0;
                valB = parseInt(valB) || 0;
            } else if (column === 'updated_at') {
                valA = new Date(valA || 0).getTime();
                valB = new Date(valB || 0).getTime();
            } else {
                valA = valA.toString().toLowerCase();
                valB = valB.toString().toLowerCase();
            }

            if (valA < valB) return direction === 'asc' ? -1 : 1;
            if (valA > valB) return direction === 'asc' ? 1 : -1;
            return 0;
        });

        // Update Sort Icons
        document.querySelectorAll('.sort-icon').forEach(icon => {
            icon.className = 'fas fa-sort sort-icon';
            icon.style.opacity = '0.3';
        });
        const activeIcon = document.getElementById(`sort-clients-trash-${column}`);
        if (activeIcon) {
            activeIcon.className = `fas fa-sort-${direction === 'asc' ? 'up' : 'down'} sort-icon active`;
            activeIcon.style.opacity = '1';
            activeIcon.style.color = '#4f46e5';
        }

        if (countSpan) countSpan.textContent = filtered.length;
        if (selectAllCheck) selectAllCheck.checked = filtered.length > 0 && filtered.every(c => this.trashState.selectedIds.has(c.id));

        if (filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">No hay clientes eliminados</td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(c => {
            const isSelected = this.trashState.selectedIds.has(c.id);
            const deletionDate = c.updated_at ? new Date(c.updated_at) : null;
            const formattedDate = deletionDate ? deletionDate.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-';

            return `
                <tr class="${isSelected ? 'active' : ''}">
                    <td><input type="checkbox" class="trash-check" value="${c.id}" ${isSelected ? 'checked' : ''} onchange="app.modules.clients.toggleTrashSelection(${c.id}, this.checked)"></td>
                    <td style="color: #94a3b8; font-weight: 700;">#${c.id}</td>
                    <td>
                        <div class="client-name-cell">
                            <div class="client-avatar" style="background: #f1f5f9; color: #94a3b8;">${c.legal_name.charAt(0).toUpperCase()}</div>
                            <div class="client-info">
                                <span class="client-real-name" style="color: #94a3b8;">${c.legal_name}</span>
                                <span class="client-code">${c.subscriber_code || '---'}</span>
                            </div>
                        </div>
                    </td>
                    <td>
                        <div class="ip-display" style="color: #94a3b8;">${c.ip_address || '---'}</div>
                        <span class="credential-text">${c.username || '---'}</span>
                    </td>
                    <td>
                        <div style="font-weight: 600; color: #94a3b8;">${c.router || '---'}</div>
                        <div style="font-size: 0.75rem; color: #cbd5e1;">${c.zone || ''}</div>
                    </td>
                    <td style="font-weight: 600; color: #64748b; font-size: 0.8rem;">${formattedDate}</td>
                    <td style="text-align: right;">
                        <div class="action-menu" style="justify-content: flex-end;">
                            <button class="action-btn" style="color: #10b981;" onclick="app.modules.clients.restoreClientFromTrash(${c.id})" title="Restaurar al Sistema">
                                <i class="fas fa-undo"></i>
                            </button>
                            <button class="action-btn" style="color: #6366f1; background: #eef2ff; border-radius: 8px; width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; transition: transform 0.2s;" onclick="app.modules.clients.openSupportForClient(${c.id})" title="Reportar Falla / Soporte">
                               <i class="fas fa-headset" style="font-size: 0.9rem;"></i>
                           </button>
                            <button class="action-btn" style="color: #ef4444;" onclick="app.modules.clients.hardDeleteClient(${c.id})" title="Eliminar Definitivamente">
                                <i class="fas fa-times-circle"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
        this.updateTrashSelectionUI();
    }

    formatSimpleDate(dateStr) {
        if (!dateStr) return '---';
        try {
            const d = new Date(dateStr);
            return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch (e) {
            return dateStr;
        }
    }

    toggleTrashSelection(clientId, isChecked) {
        if (isChecked) this.trashState.selectedIds.add(clientId);
        else this.trashState.selectedIds.delete(clientId);
        this.renderTrash();
    }

    toggleSelectAllTrash(isChecked) {
        const search = this.trashState.search;
        const filtered = this.trashState.clients.filter(c => {
            return !search ||
                (c.legal_name && c.legal_name.toLowerCase().includes(search)) ||
                (c.subscriber_code && c.subscriber_code.toLowerCase().includes(search)) ||
                (c.ip_address && c.ip_address.includes(search));
        });

        if (isChecked) {
            filtered.forEach(c => this.trashState.selectedIds.add(c.id));
        } else {
            filtered.forEach(c => this.trashState.selectedIds.delete(c.id));
        }
        this.renderTrash();
    }

    updateTrashSelectionUI() {
        const count = this.trashState.selectedIds.size;
        const bulkActions = document.getElementById('clients-trash-bulk-actions');
        const countSpan = document.getElementById('clients-trash-selected-count');

        if (bulkActions) bulkActions.style.display = count > 0 ? 'inline-flex' : 'none';
        if (countSpan) countSpan.textContent = count;
    }

    async bulkRestoreTrash() {
        const ids = Array.from(this.trashState.selectedIds);
        if (ids.length === 0) return;

        if (!confirm(`¿Deseas restaurar ${ids.length} clientes seleccionados?`)) return;

        try {
            const response = await this.api.post('/api/clients/bulk-restore', { ids });
            toast.success(response.message);
            this.loadTrash();
            if (this.loadClients) this.loadClients();
        } catch (e) {
            toast.error('Error en restauración masiva');
        }
    }

    async bulkHardDeleteClients() {
        const ids = Array.from(this.trashState.selectedIds);
        if (ids.length === 0) return;

        if (!confirm(`🛑 ATENCIÓN: ¿Eliminar definitivamente ${ids.length} clientes del SISTEMA? Esta acción no se puede deshacer.`)) return;

        try {
            const response = await this.api.post('/api/clients/bulk-delete', { ids });
            toast.success(response.message);
            this.loadTrash();
        } catch (e) {
            toast.error('Error en eliminación masiva');
        }
    }

    async emptyTrash() {
        if (!confirm('🛑 ¿ESTÁS SEGURO? Esta acción eliminará permanentemente TODOS los clientes de la papelera del sistema.')) return;

        try {
            const response = await this.api.post('/api/clients/empty-trash');
            toast.success(response.message);
            this.loadTrash();
        } catch (e) {
            toast.error('Error al vaciar papelera');
        }
    }

    async restoreClientFromTrash(clientId) {
        if (!confirm('¿Deseas restaurar este cliente al sistema?')) return;
        try {
            await this.api.post(`/api/clients/${clientId}/restore`, {});
            // Check if window.toast exists
            if (window.toast) toast.success('Cliente restaurado correctamente');
            else alert('Cliente restaurado correctamente');

            this.loadTrash();
            this.loadClients();
        } catch (e) {
            console.error(e);
            alert('Error al restaurar: ' + e.message);
        }
    }

    async openSupportForClient(clientId) {
        console.log(`🧭 Navigating to support for client ${clientId}`);
        if (window.app && window.app.modules.navigation) {
            window.app.modules.navigation.navigateToSubView('clients-support', { client_id: clientId });
        }
    }

    async hardDeleteClient(clientId) {
        if (!confirm('🛑 ¡ATENCIÓN! ¿Eliminar este cliente definitivamente del sistema? Esta acción no se puede deshacer.')) return;
        try {
            await this.api.delete(`/api/clients/${clientId}?scope=global`);
            if (window.toast) toast.success('Cliente eliminado permanentemente');
            else alert('Cliente eliminado permanentemente');

            this.loadTrash();
        } catch (e) {
            console.error(e);
            alert('Error al eliminar: ' + e.message);
        }
    }

    async loadClientsForActions() {
        console.log('🔍 loadClientsForActions: Starting...');
        console.trace('Tracing call to loadClientsForActions');
        try {
            let url = '/api/clients';
            const params = [];

            const routerId = document.getElementById('filter-router-actions')?.value;
            console.log('🔍 Router ID from filter:', routerId);

            if (routerId) {
                params.push(`router_id=${routerId}`);
                this.filterState.routerId = routerId;
            }

            if (params.length > 0) url += '?' + params.join('&');
            console.log('🔍 API URL:', url);

            const tbody = document.getElementById('clients-table-body-actions');
            if (tbody) tbody.style.opacity = '0.5';

            console.log('🔍 Fetching clients from API...', url);
            const response = await this.api.get(url);

            // Manejo robusto de respuesta (array directo o paginado)
            if (response && response.clients) {
                this.actionsClients = response.clients;
            } else {
                this.actionsClients = response || [];
            }

            console.log('✅ Clients loaded for actions:', this.actionsClients.length);

            if (!this.onlineStatusMap) this.onlineStatusMap = {};
            this.actionsClients.forEach(c => {
                if (!this.onlineStatusMap[c.id]) {
                    this.onlineStatusMap[c.id] = c.is_online ? 'online' : 'offline';
                }
            });

            console.log('🔍 Filtering clients...');
            this.filterClientsActions();

            console.log('🔍 Setting up websocket listeners...');
            this.setupWebsocketListeners();

            console.log('🔍 Starting traffic monitor...');
            this.startTrafficMonitor();

            if (tbody) tbody.style.opacity = '1';
            console.log('✅ loadClientsForActions: Complete');
        } catch (error) {
            console.error('❌ Error loading clients for actions:', error);
            console.error('❌ Error details:', error.message, error.stack);
            const tbody = document.getElementById('clients-table-body-actions');
            if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="error-cell">Error cargando clientes: ' + error.message + '</td></tr>';
        }
    }

    filterClientsActions() {
        let filtered = [...(this.actionsClients || [])];

        const status = document.getElementById('filter-status-actions')?.value || 'all';
        const balance = document.getElementById('filter-balance-actions')?.value || 'all';
        const search = (document.getElementById('client-search-actions')?.value || '').toLowerCase();

        // Aplicar filtros adicionales del usuario
        if (status !== 'all') {
            filtered = filtered.filter(c => (c.status || '').toLowerCase() === status);
        }

        if (balance === 'pending') {
            filtered = filtered.filter(c => (c.account_balance || 0) > 0);
        } else if (balance === 'uptodate') {
            filtered = filtered.filter(c => (c.account_balance || 0) <= 0);
        }

        if (search) {
            filtered = filtered.filter(c =>
                (c.legal_name || '').toLowerCase().includes(search) ||
                (c.subscriber_code || '').toLowerCase().includes(search) ||
                (c.ip_address || '').includes(search) ||
                (c.username || '').toLowerCase().includes(search)
            );
        }

        this.actionsClientsFiltered = filtered;
        this.renderClientsActions(filtered);
        this.updateStatsActions();
    }

    renderClientsActions(clients) {
        const tbody = document.getElementById('clients-table-body-actions');
        if (!tbody) return;

        if (!clients || clients.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="no-data">No se encontraron clientes para estas acciones</td></tr>';
            return;
        }

        tbody.innerHTML = clients.map(client => {
            const isOnline = this.onlineStatusMap[client.id] === 'online';
            const isSuspended = (client.status || '').toLowerCase() === 'suspended';
            const isPending = (client.account_balance || 0) > 0;

            return `
            <tr data-client-id="${client.id}">
                <td><input type="checkbox" class="client-checkbox-actions" value="${client.id}" onclick="app.modules.clients.updateSelectionActions()"></td>
                <td style="font-size: 0.75rem; color: #94a3b8; font-weight: 700;">#${client.id}</td>
                <td>
                    <div class="client-name-cell">
                        <div class="client-avatar">${(client.legal_name || '?').charAt(0).toUpperCase()}</div>
                        <div class="client-info">
                            <span class="client-real-name">${client.legal_name}</span>
                        </div>
                    </div>
                </td>
                <td>
                    <div class="ip-display">${client.ip_address || '---'}</div>
                    <span class="credential-text">${client.mac_address || ''}</span>
                </td>
                <td>
                    <div style="font-weight: 600;">${client.router ? client.router.substring(0, 15) : '---'}</div>
                    <div style="font-size: 0.75rem; color: #64748b;">${client.zone || ''}</div>
                </td>
                <td>
                    ${isPending ?
                    `<span class="status-badge-table status-badge-fin suspended">Pendiente</span>
                         <div class="debt-amount negative">$${client.account_balance.toLocaleString('es-CO', { minimumFractionDigits: 0 })}</div>` :
                    `<span class="status-badge-table status-badge-fin active">Al día</span>
                         <div class="debt-amount positive">$0</div>`
                }
                </td>
                <td>
                    <div style="display: flex; flex-direction: column; gap: 4px;">
                        <span style="font-size: 0.8rem; font-weight: 700;">${this.formatPlanName(client.plan_name)}</span>
                        <span class="status-badge-table status-badge-connection ${isSuspended ? 'suspended' : 'active'}">
                            ${isSuspended ? 'Bloqueado' : (isOnline ? 'Online' : 'Offline')}
                        </span>
                    </div>
                </td>
                <td>
                    <div class="traffic-mini">
                        <div class="traffic-row traffic-up">
                            <i class="fas fa-upload" style="font-size: 0.6rem;"></i> <span class="val-up">0K</span>
                        </div>
                        <div class="traffic-row traffic-down">
                            <i class="fas fa-download" style="font-size: 0.6rem;"></i> <span class="val-down">0K</span>
                        </div>
                    </div>
                </td>
            </tr>
            `;
        }).join('');
    }

    updateStatsActions() {
        // Usar el dataset filtrado (solo clientes con problemas)
        const dataset = this.actionsClientsFiltered || [];

        const total = dataset.length;
        const pending = dataset.filter(c => (c.account_balance || 0) > 0).length;

        document.getElementById('count-total-actions').textContent = total;
        document.getElementById('count-pending-actions').textContent = pending;
    }

    async applyFiltersActions() {
        const currentRouterId = document.getElementById('filter-router-actions')?.value;
        console.log('🔍 applyFiltersActions: currentRouterId=', currentRouterId, 'stateRouterId=', this.filterState.routerId);

        // Si cambió el router (comparación robusta), LIMPIAR SELECCIÓN y recargar
        if (String(currentRouterId) !== String(this.filterState.routerId)) {
            console.log('🔄 Router changed, clearing selection and reloading clients...');
            this.clearSelectionActions();  // LIMPIAR SELECCIÓN ANTES DE RECARGAR
            await this.loadClientsForActions();
        } else {
            // Si solo cambiaron otros filtros, refilter sin recargar
            this.filterClientsActions();
        }
    }

    /**
     * Obtiene los IDs de clientes seleccionados y valida que pertenezcan al router actual
     * @returns {Array} Array de IDs de clientes seleccionados
     */
    getSelectedClientIdsForActions() {
        const selectedCheckboxes = document.querySelectorAll('.client-checkbox-actions:checked');
        const clientIds = Array.from(selectedCheckboxes).map(cb => parseInt(cb.value));

        if (clientIds.length === 0) {
            return [];
        }

        // Validar que todos los clientes seleccionados pertenezcan al filtro actual
        const currentRouterId = document.getElementById('filter-router-actions')?.value;

        if (currentRouterId) {
            // Filtrar solo clientes que pertenezcan al router actual
            const validClientIds = clientIds.filter(id => {
                const client = this.actionsClientsFiltered.find(c => c.id === id);
                return client && client.router_id?.toString() === currentRouterId;
            });

            if (validClientIds.length < clientIds.length) {
                const removed = clientIds.length - validClientIds.length;
                console.warn(`⚠️ Removed ${removed} client(s) that don't belong to selected router`);
                if (window.toast) toast.warning(`Se omitieron ${removed} cliente(s) que no pertenecen al router seleccionado`);
            }

            return validClientIds;
        }

        return clientIds;
    }

    clearSelectionActions() {
        const checkboxes = document.querySelectorAll('.client-checkbox-actions');
        checkboxes.forEach(cb => cb.checked = false);
        const master = document.getElementById('select-all-clients-actions');
        if (master) master.checked = false;
        const buttonsContainer = document.getElementById('bulk-actions-buttons-actions');
        if (buttonsContainer) {
            buttonsContainer.style.opacity = '0.5';
            buttonsContainer.style.pointerEvents = 'none';
        }
        const countDisplay = document.getElementById('selected-count-display-actions');
        if (countDisplay) countDisplay.textContent = '0';
        const countStat = document.getElementById('count-selected-actions');
        if (countStat) countStat.textContent = '0';
    }

    async processBulkCashPayment() {
        const clientIds = this.getSelectedClientIdsForActions();

        if (clientIds.length === 0) {
            alert('Selecciona al menos un cliente');
            return;
        }

        const confirmMsg = `¿Procesar pago en EFECTIVO para ${clientIds.length} cliente(s)?\n\nEsto registrará el pago de la cuota mensual y activará automáticamente el servicio.`;

        if (!confirm(confirmMsg)) return;

        try {
            toast.info('Procesando pagos masivos...');

            const response = await this.api.post('/api/clients/bulk-cash-payment', {
                client_ids: clientIds
            });

            toast.success(response.message || `Pagos procesados: ${response.processed || clientIds.length}`);
        } catch (e) {
            console.error('Error in bulk cash payment:', e);
            toast.error('Error al procesar pagos masivos');
        } finally {
            this.clearSelectionActions();
            this.loadClientsForActions();
        }
    }

    async bulkTemporaryActivation() {
        const clientIds = this.getSelectedClientIdsForActions();

        if (clientIds.length === 0) {
            alert('Selecciona al menos un cliente');
            return;
        }

        const confirmMsg = `📅 ¿Crear PROMESA DE PAGO de 5 días para ${clientIds.length} cliente(s)?

Esto significa:
✔ Servicio se ACTIVA en MikroTik (tendrán internet)
✔ Status en sistema NO cambia (permanece suspendido/pendiente)
✔ Tienen 5 días para pagar completamente
入 Si no pagan, se suspenderá automáticamente
入 Si ya tenían promesas anteriores, se marcarán como incumplidas

¿Continuar?`;

        if (!confirm(confirmMsg)) return;

        try {
            toast.info('Creando promesas de pago...');

            const response = await this.api.post('/api/clients/bulk-temporary-activation', {
                client_ids: clientIds
            });

            const promisesCount = response.results?.success_count || clientIds.length;
            toast.success(`✅ ${promisesCount} promesa(s) de 5 días creada(s) exitosamente`);
        } catch (e) {
            console.error('Error in bulk temporary activation:', e);
            toast.error('Error al activar servicios');
        } finally {
            this.clearSelectionActions();
            this.loadClientsForActions();
        }
    }

    async bulkSuspend() {
        const clientIds = this.getSelectedClientIdsForActions();

        if (clientIds.length === 0) {
            alert('Selecciona al menos un cliente');
            return;
        }

        const confirmMsg = `⚠️ ¿SUSPENDER el servicio para ${clientIds.length} cliente(s)?\n\nEsto cortará el internet de los clientes seleccionados.`;

        if (!confirm(confirmMsg)) return;

        try {
            toast.info('Suspendiendo servicios...');

            const response = await this.api.post('/api/clients/bulk-suspend', {
                client_ids: clientIds
            });

            toast.success(response.message || `Servicios suspendidos: ${response.suspended || clientIds.length}`);
        } catch (e) {
            console.error('Error in bulk suspension:', e);
            toast.error('Error al suspender servicios');
        } finally {
            this.clearSelectionActions();
            this.loadClientsForActions();
        }
    }

    async bulkRevertPayments() {
        const clientIds = this.getSelectedClientIdsForActions();

        if (clientIds.length === 0) {
            alert('Selecciona al menos un cliente');
            return;
        }

        const confirmMsg = `⚠️ ¿REVERTIR los últimos pagos de ${clientIds.length} cliente(s)?

Esto significa:
✖ Sus pagos recientes se moverán a la papelera
✖ Sus deudas se RESTAURARÁN al monto anterior
✖ Sus servicios serán SUSPENDIDOS automáticamente

Esta acción es seria y debe usarse con precaución.`;

        if (!confirm(confirmMsg)) return;

        try {
            toast.info('Revirtiendo pagos...');

            const response = await this.api.post('/api/clients/bulk-revert-recent-payments', {
                client_ids: clientIds,
                reason: 'Reversión masiva desde Acción Masiva'
            });

            toast.success(response.message || `Reversiones completadas: ${response.reverted || clientIds.length}`);
        } catch (e) {
            console.error('Error in bulk revert:', e);
            toast.error('Error al revertir pagos masivos');
        } finally {
            this.clearSelectionActions();
            this.loadClientsForActions();
        }
    }

    async suspendAllPendingByRouter() {
        const routerId = document.getElementById('filter-router-actions')?.value;

        if (!routerId) {
            alert('Selecciona un router específico en el filtro');
            return;
        }

        const router = this.routers.find(r => r.id == routerId);
        const routerName = router ? router.alias : 'Router';

        const confirmMsg = `⚠️ ¿CORTE MASIVO en router "${routerName}"?\n\nEsto suspenderá TODOS los clientes con deuda pendiente de este router.`;

        if (!confirm(confirmMsg)) return;

        try {
            toast.info(`Ejecutando corte en ${routerName}...`);

            const response = await this.api.post('/api/clients/bulk-suspend-pending', {
                router_id: parseInt(routerId)
            });

            toast.success(response.message || `Corte completado: ${response.suspended || 0} clientes suspendidos`);
            this.loadClientsForActions();
        } catch (e) {
            console.error('Error in router bulk suspension:', e);
            toast.error('Error al ejecutar corte masivo');
        }
    }

    async suspendAllPending() {
        const confirmMsg = `🚨 ¿CORTE MASIVO GLOBAL?\n\nEsto suspenderá TODOS los clientes con deuda en TODOS los routers.\n\n⚠️ Esta acción afecta a toda la red.`;

        if (!confirm(confirmMsg)) return;

        const doubleConfirm = prompt('Escribe "CORTE GLOBAL" para confirmar:');
        if (doubleConfirm !== 'CORTE GLOBAL') {
            alert('Operación cancelada');
            return;
        }

        try {
            toast.info('Ejecutando corte masivo global...');

            const response = await this.api.post('/api/clients/bulk-suspend-pending', {
                router_id: null // null = todos los routers
            });

            toast.success(response.message || `Corte global completado: ${response.suspended || 0} clientes suspendidos`);
            this.loadClientsForActions();
        } catch (e) {
            console.error('Error in global bulk suspension:', e);
            toast.error('Error al ejecutar corte global');
        }
    }

    async activateAllByRouter() {
        const routerId = document.getElementById('filter-router-actions')?.value;

        if (!routerId) {
            alert('Selecciona un router específico en el filtro');
            return;
        }

        const router = this.routers.find(r => r.id == routerId);
        const routerName = router ? router.alias : 'Router';

        const confirmMsg = `¿Activar TODOS los clientes del router "${routerName}"?\n\nEsto reactivará el servicio de internet sin cambiar el estado de deuda.\nÚtil para cortesías o fines de semana.`;

        if (!confirm(confirmMsg)) return;

        try {
            toast.info(`Activando clientes en ${routerName}...`);

            const response = await this.api.post('/api/clients/bulk-activate-router', {
                router_id: parseInt(routerId)
            });

            toast.success(response.message || `Activación completada: ${response.activated || 0} clientes`);
            this.loadClientsForActions();
        } catch (e) {
            console.error('Error in router bulk activation:', e);
            toast.error('Error al activar router');
        }
    }

    async loadRouters() {
        try {
            this.routers = await this.api.get('/api/routers');
            this.populateRouterFilter();
        } catch (error) {
            console.error('Error loading routers:', error);
        }
    }

    async loadPlans() {
        try {
            // Asumiendo endpoint de planes existe o extraer de clientes mas tarde si falla
            // Si no existe endpoint /api/plans, extraer de clientes cargados
            // Por ahora, intentamos endpoint comun
            // Update: We can try extracting unique plans from the full client list later if API is heavy
            // For now, let's keep it simple and load filtering after clients load if needed.
            // But populating plans filter is good UX.
        } catch (e) { console.warn("Could not load plans for filter", e); }
    }

    async loadCollectors() {
        try {
            const users = await this.api.get('/api/users/collectors');
            this.collectors = users;
            this.populateCollectorFilter();
        } catch (e) {
            console.error('Error loading collectors for filter:', e);
        }
    }

    populateCollectorFilter() {
        const select = document.getElementById('filter-collector');
        if (!select) return;

        const user = window.app?.authService?.getUser();
        const isCollector = user && (user.role === 'collector' || user.role === 'cobrador');

        if (isCollector) {
            // For collectors, only show themselves and disable selection
            select.innerHTML = `<option value="${user.id}">${user.username}</option>`;
            select.value = user.id;
            select.disabled = true;
            this.filterState.collectorId = user.id;
        } else {
            // For admins, show all collectors
            const currentVal = select.value || this.filterState.collectorId;
            select.innerHTML = '<option value="">Todos los Cobradores</option>' +
                this.collectors.map(c => `<option value="${c.id}">${c.username}</option>`).join('');
            if (currentVal) select.value = currentVal;
            select.disabled = false;
        }
    }

    populateRouterFilter() {
        const select = document.getElementById('filter-router');
        if (!select) return;

        const currentVal = select.value || this.filterState.routerId;

        select.innerHTML = '<option value="">Todos los Routers</option>' +
            this.routers.map(r => `<option value="${r.id}">${r.alias}</option>`).join('');

        if (currentVal) select.value = currentVal;
    }

    populatePlanFilter() {
        const select = document.getElementById('filter-plan');
        if (!select) return;

        // Extract unique plans from ALL clients, not just filtered ones
        const plans = new Set((this.allClients || this.clients).map(c => c.plan_name).filter(Boolean));
        const currentVal = select.value;

        select.innerHTML = '<option value="">Todos los Planes</option>' +
            Array.from(plans).sort().map(p => `<option value="${p}">${this.formatPlanName(p)}</option>`).join('');

        if (currentVal) select.value = currentVal;
    }

    applyFilters() {
        const routerSelect = document.getElementById('filter-router');
        const statusSelect = document.getElementById('filter-status');
        const planSelect = document.getElementById('filter-plan');
        const collectorSelect = document.getElementById('filter-collector');
        const searchInput = document.getElementById('client-search');

        const newRouterId = routerSelect ? routerSelect.value : '';
        const oldRouterId = this.filterState.routerId;

        const newCollectorId = collectorSelect ? collectorSelect.value : '';
        const oldCollectorId = this.filterState.collectorId;

        this.filterState.routerId = newRouterId;
        this.filterState.collectorId = newCollectorId;
        this.filterState.status = statusSelect ? statusSelect.value : 'all';
        this.filterState.planId = planSelect ? planSelect.value : '';
        if (searchInput) this.filterState.search = searchInput.value;

        this.currentPage = 1; // RESET PAGINATION on filter change

        // Update active class on pills
        this.updatePillActiveState();

        // If Router or Collector changed, we must reload from API
        if (newRouterId !== oldRouterId || newCollectorId !== oldCollectorId || !this.allClients) {
            this.loadClients();
        } else {
            this.filterClients();
        }
    }

    updatePillActiveState() {
        const { status, financialStatus } = this.filterState;

        // Remove active class from all
        document.querySelectorAll('.stat-pill').forEach(p => {
            if (p && p.classList) p.classList.remove('active-filter');
        });

        let pillId = null;

        // Financial filters take precedence for visual feedback if active
        if (financialStatus === 'morosos') pillId = 'count-morosos';
        else if (financialStatus === 'paid') pillId = 'count-pagos';
        else {
            const map = {
                'all': 'count-total',
                'active': 'count-active',
                'suspended': 'count-suspended',
                'online': 'count-online',
                'offline': 'count-offline',
                'warning': 'count-warning'
            };
            pillId = map[status];
        }

        if (pillId) {
            const pillEl = document.getElementById(pillId)?.parentElement;
            if (pillEl && pillEl.classList) pillEl.classList.add('active-filter');
        }
    }

    onSearchInput(value) {
        if (this.searchTimeout) clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
            this.applyFilters();
        }, 500); // 500ms debounce
    }

    formatPlanName(name) {
        if (!name) return 'Sin Plan';
        // Clean name (remove profiles like Mikrotik defaults)
        if (name === 'default' || name === 'default-encryption') return name;
        return name;
    }

    formatLastSeen(dateString) {
        if (!dateString) return '';

        try {
            const date = new Date(dateString);
            const now = new Date();
            const diffMs = now - date;

            if (diffMs < 0) return 'Ahora mismo';

            const seconds = Math.floor(diffMs / 1000);
            if (seconds < 60) return `Hace ${seconds}s`;

            const minutes = Math.floor(seconds / 60);
            if (minutes < 60) return `Hace ${minutes}m`;

            const hours = Math.floor(minutes / 60);
            if (hours < 24) return `Hace ${hours}h ${minutes % 60}m`;

            const days = Math.floor(hours / 24);
            return `Hace ${days}d ${hours % 24}h`;
        } catch (e) {
            return '';
        }
    }

    async loadClients() {
        try {
            this.currentPage = 1;
            // 1. Fetch ALL clients for the current context (or filtered by Router only)
            // We do NOT send search or status to backend to ensure we have the full dataset for stats.
            let url = '/api/clients';
            const params = [];

            if (this.filterState.routerId) {
                params.push(`router_id=${this.filterState.routerId}`);
            }

            if (this.filterState.collectorId) {
                params.push(`assigned_collector_id=${this.filterState.collectorId}`);
            }

            // NOTE: We fetch all statuses so we can calculate totals correctly client-side.
            // If we are in 'deleted' view (special case), maybe we should fetch deleted?
            // The backend defaults to returning active/suspended?
            // Let's assume get_filtered returns all types if status is not specified.
            // Wait, standard practice usually excludes deleted unless requested.
            // Let's filter 'deleted' explicitly if needed.
            // For now, let's just get everything.

            if (params.length > 0) {
                url += '?' + params.join('&');
            }

            const tbody = document.getElementById('clients-table-body');
            if (tbody) tbody.style.opacity = '0.5';

            // Store in this.allClients (Cache)
            this.allClients = await this.api.get(url);
            console.log('DEBUG: loadClients raw response:', this.allClients);

            if (!Array.isArray(this.allClients)) {
                console.error('DEBUG: loadClients - response is not an array:', this.allClients);
                this.allClients = [];
            }

            // Initialize Status Map for ALL clients
            if (!this.onlineStatusMap) this.onlineStatusMap = {};
            this.allClients.forEach(c => {
                // Preserve existing status if available (from websocket)
                if (!this.onlineStatusMap[c.id]) {
                    this.onlineStatusMap[c.id] = c.is_online ? 'online' : 'offline';
                }
            });

            console.log('DEBUG: Loaded total clients:', this.allClients.length);

            // 2. Apply Filters in Memory
            this.filterClients();

            // 3. Start Monitor for ALL clients (so stats stay live)
            this.setupWebsocketListeners();
            this.startTrafficMonitor();

            if (tbody) tbody.style.opacity = '1';
        } catch (error) {
            console.error('Error loading clients:', error);
            const tbody = document.getElementById('clients-table-body');
            if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="error-cell">Error cargando clientes</td></tr>';
        }
    }

    filterClients() {
        console.log('DEBUG: filterClients starting. total clients:', (this.allClients || []).length);
        console.log('DEBUG: filterState:', JSON.stringify(this.filterState));
        console.log('DEBUG: currentPage:', this.currentPage);

        // Start with all
        let filtered = [...(this.allClients || [])];

        // 1. Filter by Status (Client-Side)
        const status = this.filterState.status;
        if (status !== 'all') {
            if (status === 'online') {
                filtered = filtered.filter(c => this.onlineStatusMap[c.id] === 'online');
            } else if (status === 'offline') {
                filtered = filtered.filter(c => this.onlineStatusMap[c.id] === 'offline');
            } else if (status === 'debtors') {
                filtered = filtered.filter(c => (c.account_balance || 0) > 0);
            } else if (status === 'warning') {
                filtered = filtered.filter(c => this.onlineStatusMap[c.id] === 'detected_no_queue');
            } else {
                // Active / Suspended / Deleted
                const statusLower = status.toLowerCase();
                filtered = filtered.filter(c => (c.status || '').toLowerCase() === statusLower);
            }
        }
        console.log('DEBUG: After status filter:', filtered.length);

        // 2. Filter by Financial Status
        const finStatus = this.filterState.financialStatus;
        if (finStatus === 'morosos') {
            filtered = filtered.filter(c => (c.account_balance || 0) > 0);
        } else if (finStatus === 'paid') {
            filtered = filtered.filter(c => (c.account_balance || 0) <= 0);
        }

        // 3. Filter by Plan
        if (this.filterState.planId) {
            filtered = filtered.filter(c => String(c.plan_name) === String(this.filterState.planId));
        }
        console.log('DEBUG: After plan filter:', filtered.length);

        // 3. Filter by Search
        const search = (this.filterState.search || '').toLowerCase();
        if (search) {
            filtered = filtered.filter(c =>
                (c.legal_name || '').toLowerCase().includes(search) ||
                (c.subscriber_code || '').toLowerCase().includes(search) ||
                (c.ip_address || '').includes(search) ||
                (c.username || '').toLowerCase().includes(search)
            );
        }

        // 4. Sort Logic
        const col = this.sortState.column;
        const dir = this.sortState.direction === 'asc' ? 1 : -1;

        filtered.sort((a, b) => {
            if (!a || !b) return 0; // Stability

            // Default: Online first
            if (!col || col === 'id') {
                const aStatus = (this.onlineStatusMap || {})[a.id];
                const bStatus = (this.onlineStatusMap || {})[b.id];
                const aOnline = (aStatus === 'online' || aStatus === 'detected_no_queue');
                const bOnline = (bStatus === 'online' || bStatus === 'detected_no_queue');
                if (aOnline && !bOnline) return -1;
                if (!aOnline && bOnline) return 1;
                if (col === 'id') return (parseInt(a.id) - parseInt(b.id)) * dir;
                return parseInt(a.id) - parseInt(b.id);
            }

            let valA = a[col];
            let valB = b[col];

            // Special case for legal_name
            if (col === 'legal_name') {
                return (String(valA || '')).localeCompare(String(valB || ''), undefined, { numeric: true, sensitivity: 'base' }) * dir;
            }

            // Special case for IP
            if (col === 'ip_address') {
                const ipToNum = (ip) => {
                    if (!ip) return dir === 1 ? Infinity : -Infinity;
                    return ip.split('.').reduce((acc, octet) => (acc << 8) + (parseInt(octet, 10) || 0), 0) >>> 0;
                };
                return (ipToNum(valA) - ipToNum(valB)) * dir;
            }

            // Special case for account_balance
            if (col === 'account_balance') {
                return ((valA || 0) - (valB || 0)) * dir;
            }

            // Special case for status/state
            if (col === 'status') {
                const aStatus = (this.onlineStatusMap || {})[a.id] || 'offline';
                const bStatus = (this.onlineStatusMap || {})[b.id] || 'offline';
                return aStatus.localeCompare(bStatus) * dir;
            }

            // Generic string/number sort
            if (typeof valA === 'string' || typeof valB === 'string') {
                return (String(valA || '')).localeCompare(String(valB || ''), undefined, { numeric: true, sensitivity: 'base' }) * dir;
            }
            return ((parseFloat(valA) || 0) - (parseFloat(valB) || 0)) * dir;
        });

        this.totalFiltered = filtered.length;
        console.log('DEBUG: Total filtered:', this.totalFiltered);

        // 5. Pagination Slice
        const start = (this.currentPage - 1) * this.pageSize;
        this.clients = filtered.slice(start, start + this.pageSize);
        console.log('DEBUG: Sliced clients for page:', this.clients.length);

        this.renderClients();
        this.updatePaginationUI();
        this.updateStaticStats();
        this.updatePillActiveState();
        this.populateBulkPlans();
    }

    sortClients(column) {
        console.log('🔄 Sorting clients by:', column);
        if (this.sortState.column === column) {
            this.sortState.direction = this.sortState.direction === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortState.column = column;
            this.sortState.direction = 'asc';
        }

        // Update UI headers
        document.querySelectorAll('.premium-data-table th.sortable').forEach(th => {
            if (th.classList) {
                th.classList.remove('active');
                th.classList.remove('active-sort');
            }
            const icon = th.querySelector('.sort-icon');
            if (icon) icon.className = 'fas fa-sort sort-icon';

            // Re-match header by data-sort attribute (Template uses both)
            if (th.dataset.sort === column) {
                if (th.classList) {
                    th.classList.add('active');
                    th.classList.add('active-sort');
                }
                if (icon) {
                    icon.className = this.sortState.direction === 'asc' ? 'fas fa-sort-up sort-icon' : 'fas fa-sort-down sort-icon';
                }
            }
        });

        this.filterClients();
    }

    toggleSelectAll(input) {
        if (!this.clients) return;
        const isChecked = (typeof input === 'boolean') ? input : input.checked;

        // Mark all CURRENT PAGE clients
        this.clients.forEach(c => {
            if (isChecked) this.selectedIds.add(parseInt(c.id));
            else this.selectedIds.delete(parseInt(c.id));
        });

        // Sync DOM
        document.querySelectorAll('.client-checkbox').forEach(cb => {
            if (cb) cb.checked = isChecked;
        });

        this.updateSelection();
    }

    toggleClientSelection(checkbox, clientId) {
        if (checkbox.checked) {
            this.selectedIds.add(clientId);
        } else {
            this.selectedIds.delete(clientId);
        }
        this.updateSelection();
    }

    updateSelection() {
        const count = this.selectedIds.size;
        const bar = document.getElementById('bulk-actions-bar');
        const label = document.getElementById('selected-count-label');

        if (label) label.textContent = count;

        if (bar && bar.classList) {
            if (count > 0) {
                bar.classList.add('active');
            } else {
                bar.classList.remove('active');
                const master = document.getElementById('client-select-all');
                if (master) master.checked = false;
            }
        }
    }

    clearSelection() {
        this.selectedIds.clear();
        const checkboxes = document.querySelectorAll('.client-checkbox');
        checkboxes.forEach(cb => cb.checked = false);
        const master = document.getElementById('client-select-all');
        if (master) master.checked = false;
        this.updateSelection();
    }

    // Pagination Methods
    updatePaginationUI() {
        const start = (this.currentPage - 1) * this.pageSize + 1;
        const end = Math.min(this.currentPage * this.pageSize, this.totalFiltered);

        const startEl = document.getElementById('pagination-start');
        const endEl = document.getElementById('pagination-end');
        const totalEl = document.getElementById('pagination-total');
        const prevBtn = document.getElementById('prev-page');
        const nextBtn = document.getElementById('next-page');

        if (startEl) startEl.textContent = this.totalFiltered > 0 ? start : 0;
        if (endEl) endEl.textContent = end;
        if (totalEl) totalEl.textContent = this.totalFiltered;

        if (prevBtn) prevBtn.disabled = this.currentPage <= 1;
        if (nextBtn) nextBtn.disabled = end >= this.totalFiltered;
    }

    prevPage() {
        if (this.currentPage > 1) {
            this.currentPage--;
            this.filterClients();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    }

    nextPage() {
        if (this.currentPage * this.pageSize < this.totalFiltered) {
            this.currentPage++;
            this.filterClients();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    }

    async populateBulkPlans() {
        try {
            const plans = await this.api.get('/api/plans');
            const select = document.getElementById('bulk-plan-select');
            if (!select) return;

            select.innerHTML = '<option value="">Cambiar Plan a...</option>' +
                plans.map(p => `<option value="${p.id}">${p.name} ($${p.monthly_price})</option>`).join('');
        } catch (e) {
            console.error("Error populating bulk plans:", e);
        }
    }

    async applyBulkPlan() {
        const select = document.getElementById('bulk-plan-select');
        if (!select) return;
        const planId = select.value;
        if (!planId) {
            toast.warning('Por favor seleccione un plan');
            return;
        }

        const selectedCheckboxes = document.querySelectorAll('.client-checkbox:checked');
        const clientIds = Array.from(selectedCheckboxes).map(cb => parseInt(cb.value));

        const confirmMsg = `¿Está seguro de migrar ${clientIds.length} clientes al nuevo plan? Se encolarán tareas de sincronización para los routers.`;

        if (!confirm(confirmMsg)) return;

        try {
            toast.info('Iniciando migración masiva...');
            const response = await this.api.post('/api/clients/bulk-update-plan', {
                client_ids: clientIds,
                plan_id: planId
            });

            toast.success(response.message || 'Migración completada');
            this.clearSelection();
            this.loadClients(); // Reload to show new plan names
        } catch (e) {
            console.error("Error in bulk update:", e);
            toast.error('Error al procesar la migración masiva');
        }
    }

    renderClients() {
        console.log('Rendering clients...', this.clients ? this.clients.length : 0);

        // Clear DOM cache when re-rendering
        this.rowCache.clear();

        const tbody = document.getElementById('clients-table-body');
        const cardGrid = document.getElementById('clients-cards-grid');
        const tableView = document.getElementById('clients-table-view');

        // Safety check for mobile detection
        this.isMobile = window.innerWidth < 1100;

        // Pre-compute RBAC flags (read once, used in every row render)
        const user = window.app?.authService?.getUser();
        const role = (user?.role || '').toLowerCase();
        const isAdmin = role === 'admin' || role === 'superuser' || role === 'administradora';

        const _rp = window.RBAC_PERMS || {};
        const clientPerms = _rp['clients:list'] || {};

        const canEdit = isAdmin || clientPerms.can_edit === true;
        const canDelete = isAdmin || clientPerms.can_delete === true;

        const onlineMap = this.onlineStatusMap || {};
        this.clients.forEach(c => {
            if (onlineMap[c.id] === undefined) {
                onlineMap[c.id] = 'offline';
            }
        });

        const html = this.clients.map(client => this.renderSingleClientHtml(client, onlineMap, canEdit, canDelete)).join('');

        if (this.isMobile && cardGrid) {
            if (tbody) tbody.innerHTML = '';
            if (tableView) tableView.style.display = 'none';
            cardGrid.style.display = 'grid';
            cardGrid.innerHTML = html;
        } else if (tbody) {
            if (cardGrid) {
                cardGrid.innerHTML = '';
                cardGrid.style.display = 'none';
            }
            if (tableView) tableView.style.display = 'block';
            tbody.innerHTML = html;
        }
    }

    renderSingleClientHtml(client, onlineMap, canEdit, canDelete) {
        const status = onlineMap[client.id] || 'offline';
        const isOnline = status === 'online';
        const isDeleted = (client.status || '').toLowerCase() === 'deleted';
        const isSuspended = (client.status || '').toLowerCase() === 'suspended';

        const traffic = this.trafficCache[client.id] || { up: 0, down: 0 };
        const upText = this.formatSpeed(traffic.up);
        const downText = this.formatSpeed(traffic.down);

        let statusClass = 'offline';
        let statusLabel = 'OFFLINE';

        if (isDeleted) {
            statusClass = 'deleted';
            statusLabel = 'ELIMINADO';
        } else if (isSuspended) {
            statusClass = 'suspended';
            statusLabel = 'SUSPENDIDO';
        } else if (isOnline) {
            statusClass = 'online';
            statusLabel = 'ONLINE';
        }

        if (this.isMobile) {
            // Card View (Mobile Premium) - Mantenido pero con retoques
            const avatarChar = (client.legal_name || '?').charAt(0).toUpperCase();
            const balance = client.account_balance || 0;
            const isPositive = balance <= 0;
            const balanceText = Math.abs(balance).toLocaleString('es-CO');

            return `
                <div class="premium-mobile-card client-card-mobile" data-client-id="${client.id}">
                    <div class="card-row">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <input type="checkbox" class="client-checkbox" value="${client.id}" 
                                   ${this.selectedIds.has(client.id) ? 'checked' : ''}
                                   onclick="event.stopPropagation(); app.modules.clients.toggleClientSelection(this, ${client.id})" 
                                   style="width: 18px; height: 18px; border-radius: 4px;">
                            <div class="avatar-mini" style="background: var(--primary); color: white; width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-weight: 700;">
                                ${avatarChar}
                            </div>
                            <div>
                                <div class="card-value">${client.legal_name}</div>
                                <div class="card-label">${client.subscriber_code || '---'}</div>
                            </div>
                        </div>
                        <span class="status-badge-table ${statusClass}">${statusLabel}</span>
                    </div>
                    
                    <div class="card-row">
                        <span class="card-label">IP / Conexión</span>
                        <div style="display: flex; flex-direction: column; align-items: flex-end;">
                            <span class="card-value" style="font-family: 'JetBrains Mono';">${client.ip_address || '---'}</span>
                            <div class="traffic-mini-mobile" style="font-size: 0.65rem; color: var(--primary); font-weight: 600;">
                                <i class="fas fa-arrow-up"></i> <span class="val-up">0 Kbps</span> 
                                <i class="fas fa-arrow-down" style="margin-left: 4px;"></i> <span class="val-down">0 Kbps</span>
                            </div>
                        </div>
                    </div>

                    <div class="card-row">
                        <span class="card-label">Plan / Servidor</span>
                        <div class="card-value" style="text-align: right;">
                            <div>${this.formatPlanName(client.plan_name)}</div>
                            <div style="font-size: 0.7rem; color: #64748b;">${client.router || '---'}</div>
                        </div>
                    </div>

                    <div class="card-row">
                        <span class="card-label">Balance de Cuenta</span>
                        <span class="card-badge financial ${isPositive ? 'ok' : 'debt'}">$${balanceText}</span>
                    </div>
                    
                    <div class="action-menu" style="justify-content: flex-end; gap: 8px;">
                        <button class="action-btn history" onclick="app.modules.clients.showHistory(${client.id})" title="Historial Transaccional">
                            <i class="fas fa-file-invoice-doll"></i>
                        </button>
                        <button class="action-btn pay" onclick="app.modules.clients.showPaymentModal(${client.id})" title="Registrar Pago">
                            <i class="fas fa-cash-register"></i>
                        </button>
                        <button class="action-btn edit" onclick="app.modules.clients.showEditModal(${client.id})" title="Configuración de Perfil">
                            <i class="fas fa-user-gear"></i>
                        </button>
                        <button class="action-btn suspend" onclick="app.modules.clients.toggleStatus(${client.id})" title="${isSuspended ? 'Reactivar Servicio' : 'Suspender Servicio'}">
                            <i class="fas fa-user-slash"></i>
                        </button>
                        <button class="action-btn delete" onclick="app.modules.clients.deleteClient(${client.id})" title="Eliminar del Sistema">
                            <i class="fas fa-user-minus"></i>
                        </button>
                    </div>
                </div>
            `;
        } else {
            // Table View (Super Premium Desktop)
            const balance = client.account_balance || 0;
            const isDebt = balance > 0;

            return `
            <tr data-client-id="${client.id}" class="premium-row row-hover-effect">
                <td><input type="checkbox" class="client-checkbox" value="${client.id}" 
                    ${this.selectedIds.has(client.id) ? 'checked' : ''}
                    onclick="app.modules.clients.toggleClientSelection(this, ${client.id})"></td>
                <td style="font-size: 0.7rem; color: #94a3b8; font-weight: 800; opacity: 0.6;">#${client.id}</td>
                <td>
                    <div class="client-name-cell">
                        <div class="client-avatar-glow" style="--glow-color: ${isOnline ? '#10b98133' : '#94a3b833'}">
                            ${(client.legal_name || '?').charAt(0).toUpperCase()}
                        </div>
                        <div class="client-info">
                            <span class="client-real-name">${client.legal_name}</span>
                            <span class="client-code">${client.subscriber_code || '---'}</span>
                        </div>
                    </div>
                </td>
                <td>
                    <div class="ip-premium-badge">
                        <i class="fas fa-network-wired"></i>
                        <span>${client.ip_address || '---'}</span>
                    </div>
                    <div class="mac-text-mini">${client.mac_address || ''}</div>
                </td>
                <td>
                    <div class="router-info-cell">
                        <span class="router-name">${client.router ? client.router.substring(0, 18) : '---'}</span>
                        <div class="collector-tag">
                            <i class="fas fa-user-tag"></i>
                            ${client.assigned_collector_name || 'Enrutado Automático'}
                        </div>
                    </div>
                </td>
                <td>
                    <div class="balance-premium-widget ${isDebt ? 'is-debt' : 'is-paid'}">
                        <span class="balance-label">${isDebt ? 'PENDIENTE' : 'AL DÍA'}</span>
                        <div class="balance-amount">$${Math.abs(balance).toLocaleString('es-CO')}</div>
                    </div>
                </td>
                <td>
                    <div class="plan-status-stack">
                        <span class="plan-bold">${this.formatPlanName(client.plan_name)}</span>
                        <div class="status-indicator-premium ${statusClass}">
                            <span class="status-dot-pulse ${isOnline ? 'online' : 'offline'}"></span>
                            <span class="status-text status-badge-connection">${statusLabel}</span>
                        </div>
                        ${!isOnline && client.last_seen ? `<span class="last-seen-mini">${this.formatLastSeen(client.last_seen)}</span>` : ''}
                    </div>
                </td>
                <td>
                    <div class="traffic-glass-widget" style="opacity: ${isOnline ? '1' : '0.4'}">
                        <div class="traffic-item up">
                            <i class="fas fa-arrow-up"></i> <span class="val-up">${isOnline ? upText : '---'}</span>
                        </div>
                        <div class="traffic-item down">
                            <i class="fas fa-arrow-down"></i> <span class="val-down">${isOnline ? downText : '---'}</span>
                        </div>
                    </div>
                </td>
                <td style="text-align: right;">
                    <div class="action-menu-premium" style="display: flex; gap: 8px; justify-content: flex-end;">
                        <button class="action-btn history" onclick="app.modules.clients.showClientHistory(${client.id})" title="Historial Transaccional">
                            <i class="fas fa-receipt"></i>
                        </button>
                        ${!isDeleted ? `
                            <button class="action-btn pay" onclick="app.modules.clients.registerPayment(${client.id})" title="Registrar Pago">
                                <i class="fas fa-cash-register"></i>
                            </button>
                            ${canEdit ? `
                                <button class="action-btn edit" onclick="app.modules.clients.editClient(${client.id})" title="Configuración de Perfil">
                                    <i class="fas fa-user-gear"></i>
                                </button>
                                <button class="action-btn suspend" 
                                        onclick="app.modules.clients.${isSuspended ? 'activateClient' : 'suspendClient'}(${client.id})" 
                                        title="${isSuspended ? 'Reactivar Servicio' : 'Suspender Servicio'}">
                                    <i class="fas fa-user-slash"></i>
                                </button>
                            ` : ''}
                        ` : ''}
                        ${canDelete ? `
                        <button class="action-btn delete" onclick="app.modules.clients.deleteClient(${client.id})" title="Eliminar del Sistema">
                            <i class="fas fa-user-minus"></i>
                        </button>
                        ` : ''}
                    </div>
                </td>
            </tr>
            `;
        }
    }

    /**
     * Updates a single client in the local cache and refreshes its UI row
     * without reloading the entire list.
     * @param {Object} updatedClient - The updated client data from API
     */
    updateClientInUI(updatedClient) {
        if (!updatedClient || !updatedClient.id) return;
        console.log('♻️ Granular UI Update for Client:', updatedClient.id);

        // 1. Update in allClients (Persistent Cache)
        if (this.allClients) {
            const index = this.allClients.findIndex(c => c.id === updatedClient.id);
            if (index !== -1) {
                this.allClients[index] = { ...this.allClients[index], ...updatedClient };
            }
        }

        // 2. Update in current view (this.clients)
        if (this.clients) {
            const index = this.clients.findIndex(c => c.id === updatedClient.id);
            if (index !== -1) {
                this.clients[index] = { ...this.clients[index], ...updatedClient };

                // 3. Re-render only this row/card if it's currently visible
                this.refreshClientElement(updatedClient.id);
            }
        }

        // 4. Update stats in case status/balance changed
        this.updateStaticStats();
    }

    refreshClientElement(clientId) {
        const client = (this.clients || []).find(c => c.id === clientId);
        if (!client) return;

        // Select row or card
        const element = document.querySelector(`[data-client-id="${clientId}"]`);
        if (!element) return;

        // RBAC Check (needed for renderSingleClientHtml)
        const _rp = window.RBAC_PERMS || {};
        const canEdit = _rp.clients ? _rp.clients.can_edit !== false : true;
        const canDelete = _rp.clients ? _rp.clients.can_delete !== false : true;
        const onlineMap = this.onlineStatusMap || {};

        // Re-generate HTML for this single item
        const html = this.renderSingleClientHtml(client, onlineMap, canEdit, canDelete);

        if (this.isMobile) {
            // In mobile, 'element' IS the card. We replace its outerHTML
            const div = document.createElement('div');
            div.innerHTML = html;
            element.replaceWith(div.firstElementChild);
        } else {
            // In desktop, 'element' IS the <tr>. We replace its outerHTML
            const table = document.createElement('table');
            const tbody = document.createElement('tbody');
            table.appendChild(tbody);
            tbody.innerHTML = html;
            element.replaceWith(tbody.firstElementChild);
        }
    }

    updateStaticStats() {
        // Use Global Dataset (allClients) for stats to keep them "Real" during search
        const dataset = this.allClients || this.clients || [];
        const isDeletedView = this.filterState.status === 'deleted';

        const active = dataset.filter(c => (c.status || '').toLowerCase() === 'active' || (c.status || '').toLowerCase() === 'suspended').length;
        const deleted = dataset.filter(c => (c.status || '').toLowerCase() === 'deleted').length;

        // Financiero: Basado en account_balance
        const morosos = dataset.filter(c => (c.account_balance || 0) > 0).length;
        const pagos = dataset.filter(c => (c.account_balance || 0) <= 0).length;

        // Operacional refers to anyone not deleted
        const totalOperational = active;

        // Online count depends on WebSocket map
        const onlineStatusMap = this.onlineStatusMap || {};
        const online = dataset.filter(c => onlineStatusMap[c.id] === 'online').length;
        const offline = dataset.filter(c => onlineStatusMap[c.id] === 'offline' || !onlineStatusMap[c.id]).length;

        // Update UI
        if (isDeletedView) {
            this.setSafeText('count-total', deleted);
            this.setSafeText('count-active', 0);

            this.setSafeText('count-online', 0);
            this.setSafeText('count-offline', deleted);
            this.setSafeText('count-morosos', 0);
            this.setSafeText('count-pagos', 0);

        } else {
            this.setSafeText('count-total', totalOperational);
            this.setSafeText('count-active', active);

            this.setSafeText('count-online', online);
            this.setSafeText('count-offline', offline);
            this.setSafeText('count-morosos', morosos);
            this.setSafeText('count-pagos', pagos);

        }
    }

    setSafeText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    async bulkGenerateInvoice() {
        const selectedIds = Array.from(this.selectedIds);
        if (selectedIds.length === 0) {
            toast.warning('No hay clientes seleccionados');
            return;
        }

        if (await this.modalManager.confirm({
            title: 'Generar Facturas Masivas',
            content: `¿Deseas generar la factura del mes actual para los ${selectedIds.length} clientes seleccionados ? `,
            type: 'info',
            confirmText: 'Sí, Generar Facturas'
        })) {
            try {
                const response = await this.api.post('/api/billing/generate', {
                    client_ids: selectedIds,
                    month: new Date().getMonth() + 1,
                    year: new Date().getFullYear()
                });

                if (response.details && response.details.generated_count > 0) {
                    toast.success(`Se generaron ${response.details.generated_count} facturas correctamente`);
                } else {
                    toast.info('No se generaron facturas nuevas (posiblemente ya existían)');
                }

                this.clearSelection();
                this.loadClients(); // Refresh to show new balances/status
            } catch (error) {
                console.error('Error generating bulk invoices:', error);
                toast.error('Error al generar facturas: ' + (error.message || 'Error desconocido'));
            }
        }
    }

    setupWebsocketListeners() {
        if (app.socket && !this.socketInitialized) {
            app.socket.on('client_traffic', (data) => {
                // PERFORMANCE: Buffer traffic updates
                if (data) Object.assign(this.trafficBuffer, data);

                if (!this.isUpdatePending) {
                    this.isUpdatePending = true;

                    // Use requestAnimationFrame instead of setTimeout
                    // This naturally pauses when tab is hidden, preventing background CPU usage
                    requestAnimationFrame(() => {
                        const now = Date.now();
                        if (now - this.lastTrafficUpdate >= this.trafficUpdateInterval) {
                            this.updateTrafficUI(this.trafficBuffer);
                            this.trafficBuffer = {};
                            this.lastTrafficUpdate = now;
                        }
                        this.isUpdatePending = false;
                    });
                }
            });
            this.socketInitialized = true;
        }
    }

    startTrafficMonitor() {
        this.stopTrafficMonitor();
        const dataset = this.allClients || this.clients || [];

        if (dataset.length === 0) return;

        // Monitor ALL clients in current scope so pills update in real-time even if filtered
        if (app.socket && app.socket.connected) {
            const clientIds = dataset.map(c => c.id);

            // Join router room(s)
            if (this.filterState.routerId) {
                app.socket.emit('join_router', { router_id: this.filterState.routerId });
            } else if (this.routers && this.routers.length > 0) {
                // If "All Routers", join rooms for all existing routers to receive their traffic
                this.routers.forEach(r => {
                    app.socket.emit('join_router', { router_id: r.id });
                });
            }

            // No matter if router is selected or not, we send client IDs.
            app.socket.emit('subscribe_clients', {
                router_id: this.filterState.routerId || null,
                client_ids: clientIds
            });

            console.log(`🔌 Suscrito al monitoreo de ${clientIds.length} clientes en ${this.filterState.routerId ? '1 router' : (this.routers ? this.routers.length : 0) + ' routers'}...`);
        }
    }

    stopTrafficMonitor() {
        if (app.socket && app.socket.connected) {
            const dataset = this.allClients || this.clients || [];
            const clientIds = dataset.map(c => c.id);
            if (clientIds.length > 0) {
                app.socket.emit('unsubscribe_clients', { client_ids: clientIds });
            }

            // Also leave router rooms if needed, but usually viewManager handles this
            // or we prefer staying in rooms if other modules need them.
            // For safety, when switching views, the viewManager or the new module
            // should handle leaving/joining.
        }
    }

    updateTrafficUI(data) {
        if (!this.onlineStatusMap) this.onlineStatusMap = {};

        // Remove global stats if present
        if (data['__stats__']) delete data['__stats__'];

        // 1. Update internal state and UI Rows
        Object.keys(data).forEach(clientId => {
            this.onlineStatusMap[clientId] = data[clientId].status;
            this.trafficCache[clientId] = {
                up: data[clientId].upload || 0,
                down: data[clientId].download || 0
            };

            // En móviles las filas de desktop están ocultas pero en el DOM. Necesitamos actualizar TODAS.
            const rows = document.querySelectorAll(`[data-client-id="${clientId}"]`);

            rows.forEach(row => {
                const info = data[clientId];
                if (!info) return; // FIX: Prevent crash if data point is missing

                const isOnline = info.status === 'online';

                // Update Cache for re-renders (Pagination/Sort stability)
                this.onlineStatusMap[clientId] = info.status;
                this.trafficCache[clientId] = {
                    up: info.upload || 0,
                    down: info.download || 0
                };

                // Update Status Badge
                const badge = row.querySelector('.status-badge-connection');
                if (row && badge && badge.classList && !badge.classList.contains('suspended') && !badge.classList.contains('cortado')) {
                    badge.className = `status-badge-table status-badge-connection ${isOnline ? 'active' : 'grey'}`;
                    badge.textContent = isOnline ? 'Online' : 'Offline';

                    // Fix "Detected (No Queue)" on the fly if status changes


                    // UX: Manage last-seen text
                    let lastSeenEl = row.querySelector('.last-seen-text');

                    if (isOnline) {
                        if (lastSeenEl) lastSeenEl.style.display = 'none';
                    } else if (info.last_seen) {
                        // If it doesn't exist, create it inside the cell
                        if (!lastSeenEl) {
                            const container = row.querySelector('.client-info[style*="gap: 4px"]');
                            if (container) {
                                lastSeenEl = document.createElement('span');
                                lastSeenEl.className = 'last-seen-text';
                                container.appendChild(lastSeenEl);
                            }
                        }

                        if (lastSeenEl) {
                            lastSeenEl.style.display = 'block';
                            lastSeenEl.textContent = this.formatLastSeen(info.last_seen);
                        }
                    }
                }

                // Update Traffic
                const upEl = row.querySelector('.val-up');
                const downEl = row.querySelector('.val-down');

                if (upEl && downEl) {
                    if (isOnline) {
                        upEl.textContent = this.formatSpeed(info.upload);
                        downEl.textContent = this.formatSpeed(info.download);
                        upEl.parentElement.style.opacity = '1';
                        downEl.parentElement.style.opacity = '1';
                    } else {
                        upEl.textContent = '---';
                        downEl.textContent = '---';
                        upEl.parentElement.style.opacity = '0.5';
                        downEl.parentElement.style.opacity = '0.5';
                    }
                }
            });
        });

        // 3. Update Global Counters
        this.updateStaticStats();

        // 4. If current filter is online/offline/warning, re-filter to update the list view
        const status = this.filterState.status;
        if (status === 'online' || status === 'offline' || status === 'warning') {
            this.filterClients();
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
        if (!planName || planName === 'Detected (No Queue)' || planName === 'Sin Plan') return 'Sin Plan';
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
            importBtn.addEventListener('click', () => app.modules.clients.loadClientsImport());
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

        // REMOVED: Search is handled by oninput in HTML calling onSearchInput
        // const searchInput = document.getElementById('client-search');
        // if (searchInput) {
        //     searchInput.addEventListener('input', (e) => {
        //         this.searchClients(e.target.value);
        //     });
        // }

        this.setupStatsListeners();
    }

    async searchClients(query) {
        // Legacy support or external calls
        const input = document.getElementById('client-search');
        if (input) input.value = query;
        this.onSearchInput(query);
    }

    async exportClients() {
        try {
            toast.info('Generando reporte de clientes...');

            // Construir params de filtro actuales
            const params = new URLSearchParams();
            if (this.filterState.routerId) params.append('router_id', this.filterState.routerId);
            if (this.filterState.status && this.filterState.status !== 'all') params.append('status', this.filterState.status);
            if (this.filterState.planId) params.append('plan_id', this.filterState.planId);
            if (this.filterState.search) params.append('search', this.filterState.search);
            if (this.filterState.financialStatus && this.filterState.financialStatus !== 'all') params.append('financial_status', this.filterState.financialStatus);

            window.open(`/api/clients/export?${params.toString()}`, '_blank');
        } catch (e) {
            console.error('Error exporting clients:', e);
            toast.error('Error al exportar clientes');
        }
    }

    showCreateModal() {
        if (this.modalManager) {
            this.modalManager.open('client');
        } else if (window.clientModal) {
            window.clientModal.showCreate();
        } else {
            console.error('Client Modal not loaded');
        }
    }

    async editClient(clientId) {
        const client = this.clients.find(c => c.id === clientId);
        if (!client) return;

        if (this.modalManager) {
            this.modalManager.open('client', { client });
        } else {
            console.error('ModalManager not available');
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

    async fixClientQueue(clientId) {
        if (!confirm('¿Intentar crear/reparar la Simple Queue en MikroTik para este cliente?')) return;

        try {
            if (window.app) app.showLoading(true);
            const response = await this.api.post(`/api/clients/${clientId}/fix-queue`, {});

            if (response.success) {
                if (window.toast) toast.success('Cola reparada exitosamente');
                else alert('Cola reparada exitosamente');
                this.loadClients();
            } else {
                if (window.toast) toast.error('No se pudo reparar: ' + (response.error || 'Unknown error'));
            }
        } catch (e) {
            console.error(e);
            if (window.toast) toast.error('Error al reparar cola: ' + (e.message || e));
        } finally {
            if (window.app) app.showLoading(false);
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
        this.clientToDelete = clientId;
        const client = this.clients.find(c => c.id === clientId);

        if (this.modalManager) {
            this.modalManager.open('delete-client');
            const nameEl = document.getElementById('delete-client-name');
            if (nameEl) nameEl.textContent = client ? client.legal_name : 'Cliente Desconocido';
        } else {
            const modal = document.getElementById('delete-client-modal');
            const nameEl = document.getElementById('delete-client-name');
            if (modal && nameEl) {
                nameEl.textContent = client ? client.legal_name : 'Cliente Desconocido';
                if (modal.classList) modal.classList.add('active');
            }
        }
    }

    async confirmDelete(scope) {
        if (!this.clientToDelete) return;
        const clientId = this.clientToDelete;

        try {
            // Close modal immediately via manager
            if (this.modalManager) {
                this.modalManager.close('delete-client');
            } else {
                const modal = document.getElementById('delete-client-modal');
                if (modal && modal.classList) modal.classList.remove('active');
            }

            // Show loading toast? (Assuming window.toast or similar exists, else log)
            console.log(`Deleting client ${clientId} with scope: ${scope}`);

            await this.api.delete(`/api/clients/${clientId}?scope=${scope}`);
            await this.loadClients();

            if (scope === 'local') {
                alert('Cliente eliminado del sistema (Archivado). Aún existe en Mikrotik.');
            } else {
                alert('Cliente eliminado de Sistema y Router Mikrotik correctamente.');
            }
        } catch (error) {
            console.error('Error deleting client:', error);
            alert('Error al eliminar cliente: ' + (error.message || 'Error desconocido'));
        } finally {
            this.clientToDelete = null;
        }
    }

    async showMobileActionMenu(clientId) {
        const client = this.clients.find(c => c.id === clientId) || (this.allClients && this.allClients.find(c => c.id === clientId));
        if (!client) return;

        const isSuspended = (client.status || '').toLowerCase() === 'suspended';
        const stColor = isSuspended ? '#10b981' : '#f59e0b';
        const stText = isSuspended ? 'Activar Servicio' : 'Suspender Servicio';
        const stIcon = isSuspended ? 'fa-play' : 'fa-pause';

        // RBAC: Check permissions for the menu
        const _rp = window.RBAC_PERMS || {};
        const clientPerms = _rp['clients:list'] || {};
        const canEdit = clientPerms.can_edit === true;
        const canDelete = clientPerms.can_delete === true;

        const html = `
            <div style="display: flex; flex-direction: column; gap: 12px; margin-top: 10px;">
                <!-- Registrar Pago: siempre visible (según requerimientos) -->
                <button class="btn-primary" onclick="Swal.close(); setTimeout(() => app.modules.clients.registerPayment(${clientId}), 300)" style="width: 100%; padding: 14px; background: #10b981; border: none; color: white; border-radius: 12px; font-weight: 600; font-size: 1rem; display: flex; align-items: center; justify-content: center; gap: 10px;">
                    <i class="fas fa-dollar-sign"></i> Registrar Pago
                </button>

                <button class="btn-primary" onclick="Swal.close(); setTimeout(() => app.modules.clients.showClientHistory(${clientId}), 300)" style="width: 100%; padding: 14px; background: #3b82f6; border: none; color: white; border-radius: 12px; font-weight: 600; font-size: 1rem; display: flex; align-items: center; justify-content: center; gap: 10px;">
                    <i class="fas fa-history"></i> Historial / Edo. Cuenta
                </button>

                ${canEdit ? `
                <button class="btn-primary" onclick="Swal.close(); setTimeout(() => app.modules.clients.editClient(${clientId}), 300)" style="width: 100%; padding: 14px; background: #6366f1; border: none; color: white; border-radius: 12px; font-weight: 600; font-size: 1rem; display: flex; align-items: center; justify-content: center; gap: 10px;">
                    <i class="fas fa-edit"></i> Editar Cliente
                </button>
                <button class="btn-primary" onclick="Swal.close(); setTimeout(() => app.modules.clients.${isSuspended ? 'activateClient' : 'suspendClient'}(${clientId}), 300)" style="width: 100%; padding: 14px; background: ${stColor}; border: none; color: white; border-radius: 12px; font-weight: 600; font-size: 1rem; display: flex; align-items: center; justify-content: center; gap: 10px;">
                    <i class="fas ${stIcon}"></i> ${stText}
                </button>
                ` : ''}

                ${canDelete ? `
                <button class="btn-primary" onclick="Swal.close(); setTimeout(() => app.modules.clients.deleteClient(${clientId}), 300)" style="width: 100%; padding: 14px; background: #ef4444; border: none; color: white; border-radius: 12px; font-weight: 600; font-size: 1rem; display: flex; align-items: center; justify-content: center; gap: 10px;">
                    <i class="fas fa-trash-alt"></i> Eliminar Cliente
                </button>
                ` : ''}
            </div>
        `;

        Swal.fire({
            title: '<span style="font-size: 1.2rem; color: #1e293b;">Opciones de Cliente</span>',
            html: html,
            showConfirmButton: false,
            showCloseButton: true,
            background: '#ffffff',
            customClass: {
                popup: 'premium-compact-modal',
                title: 'premium-modal-title'
            }
        });
    }

    async restoreClient(clientId) {
        if (!confirm('¿Restaurar este cliente al sistema?')) return;

        try {
            await this.api.post(`/api/clients/${clientId}/restore`, {});
            await this.loadClients();
            alert('Cliente restaurado correctamente');
        } catch (error) {
            console.error('Error restoring client:', error);
            alert('Error al restaurar cliente: ' + (error.message || 'Error desconocido'));
        }
    }

    async restoreClientFromImport(clientId, target) {
        if (!confirm('¿Deseas restaurar este cliente archivado al sistema?')) return;

        try {
            await this.api.post(`/api/clients/${clientId}/restore`, {});
            alert('Cliente restaurado correctamente');
            // Recargar el escaneo para reflejar el cambio de estado
            this.scanRouter(target);
            this.loadClients();
        } catch (error) {
            console.error('Error restoring client:', error);
            alert('Error al restaurar cliente: ' + (error.message || 'Error desconocido'));
        }
    }

    async showClientHistory(clientId) {
        if (this.modalManager) {
            const client = this.clients.find(c => c.id === clientId) || this.allClients?.find(c => c.id === clientId);
            this.modalManager.open('history', { clientId, client });
        } else {
            console.error('ModalManager not available');
        }
    }

    async showPromiseModal(clientId) {
        if (this.modalManager) {
            const client = this.clients.find(c => c.id === clientId) || this.allClients?.find(c => c.id === clientId);
            this.modalManager.open('promise', { clientId, client });
        } else {
            console.error('ModalManager not available');
        }
    }

    async registerPayment(clientId) {
        if (this.modalManager) {
            const client = this.clients.find(c => c.id === clientId) || this.allClients?.find(c => c.id === clientId);
            this.modalManager.open('payment', { clientId, client });
        } else {
            console.error('ModalManager not available');
        }
    }

    async showImportModal() {
        // Redundant, now using view
        app.modules.clients.loadClientsImport();
    }

    resetImport(target = 'view') {
        const suffix = target === 'view' ? '-view' : '';
        const idPrefix = target === 'view' ? 'import-view-' : 'import-';

        const step1 = document.getElementById(`${idPrefix}step-1`);
        const step2 = document.getElementById(`${idPrefix}step-2`);
        const loading = document.getElementById(`${idPrefix}loading`);
        const tbody = document.getElementById(`${idPrefix}preview-body`);
        const selectAll = document.getElementById(`select-all${suffix}-import`);

        if (step1) step1.style.display = 'block';
        if (step2) step2.style.display = 'none';
        if (loading) loading.style.display = 'none';
        if (tbody) tbody.innerHTML = '';
        if (selectAll) selectAll.checked = false;

        this.previewData = [];
    }

    async scanRouter(target = 'view') {
        const idPrefix = target === 'view' ? 'import-view-' : 'import-';
        const select = document.getElementById(`${idPrefix}router-select`);
        const scanTypeSelect = document.getElementById(`${idPrefix}scan-type`);
        const routerId = select ? select.value : null;
        const scanType = scanTypeSelect ? scanTypeSelect.value : 'mixed';

        if (!routerId) return alert('Por favor selecciona un router');

        const loading = document.getElementById(`${idPrefix}loading`);
        const loadingText = document.getElementById(`${idPrefix}loading-text`);

        if (loading) loading.style.display = 'flex';
        if (loadingText) loadingText.textContent = 'Escaneando router... (Esto puede tardar unos segundos)';

        try {
            const result = await this.api.get(`/api/clients/preview-import/${routerId}?scan_type=${scanType}`);
            this.renderPreview(result, target);

            const step1 = document.getElementById(`${idPrefix}step-1`);
            const step2 = document.getElementById(`${idPrefix}step-2`);
            if (step1) step1.style.display = 'none';
            if (step2) step2.style.display = 'block';
        } catch (e) {
            console.error(e);
            alert('Error escaneando router: ' + (e.message || 'Verifica la conexión'));
        } finally {
            if (loading) loading.style.display = 'none';
        }
    }

    sortPreview(column, target = 'modal') {
        if (!this.previewData || this.previewData.length === 0) return;

        // Cambiar dirección si es la misma columna
        if (this.importSort.column === column) {
            this.importSort.direction = this.importSort.direction === 'asc' ? 'desc' : 'asc';
        } else {
            this.importSort.column = column;
            this.importSort.direction = 'asc';
        }

        const dir = this.importSort.direction === 'asc' ? 1 : -1;

        this.previewData.sort((a, b) => {
            let valA = (a[column] || '').toString();
            let valB = (b[column] || '').toString();

            // Lógica especial para IP
            if (column === 'ip_address') {
                const ipToNum = (ip) => {
                    if (!ip || ip === 'Dinámica' || ip === 'Sin IP') return dir === 1 ? Infinity : -Infinity;
                    const clean = ip.split('/')[0];
                    return clean.split('.').reduce((acc, octet) => (acc << 8) + (parseInt(octet, 10) || 0), 0) >>> 0;
                };
                return (ipToNum(valA) - ipToNum(valB)) * dir;
            }

            // Lógica especial para Status (Combinar db_status y type para sorteo)
            if (column === 'status') {
                valA = a.db_status || (a.type === 'discovered' ? 'cortado' : 'nuevo');
                valB = b.db_status || (b.type === 'discovered' ? 'cortado' : 'nuevo');
            }

            return valA.localeCompare(valB, undefined, { numeric: true, sensitivity: 'base' }) * dir;
        });

        // Re-renderizar
        this.renderPreview({ clients: this.previewData, total_found: this.previewData.length }, target);

        // Actualizar UI de los headers (iconos)
        setTimeout(() => this.updateSortIcons(target), 0);
    }

    sortBy(column) {
        if (this.sortState.column === column) {
            this.sortState.direction = this.sortState.direction === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortState.column = column;
            this.sortState.direction = 'asc';
        }
        this.filterClients();
        this.updateMainSortIcons();
    }

    updateMainSortIcons() {
        const table = document.querySelector('.clients-table');
        if (!table) return;

        const headers = table.querySelectorAll('th.sortable');
        headers.forEach(th => {
            const icon = th ? th.querySelector('i') : null; // Added null guard for th
            if (th && th.classList) th.classList.remove('active-sort'); // Added null guard for th
            if (icon) icon.className = 'fas fa-sort';

            const onClickAttr = th ? th.getAttribute('onclick') : null; // Added null guard for th
            if (onClickAttr && onClickAttr.includes(`'${this.sortState.column}'`)) {
                if (th && th.classList) th.classList.add('active-sort'); // Added null guard for th
                if (icon) {
                    icon.className = this.sortState.direction === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down';
                }
            }
        });
    }

    updateSortIcons(target) {
        const table = document.querySelector(target === 'view' ? '#clients-import-view table' : '#import-clients-modal table');
        if (!table) return;

        const headers = table.querySelectorAll('th.sortable');
        headers.forEach(th => {
            const icon = th ? th.querySelector('i') : null;
            if (th && th.classList) th.classList.remove('active-sort');
            if (icon) icon.className = 'fas fa-sort';

            const onClickAttr = th ? th.getAttribute('onclick') : null;
            if (onClickAttr && onClickAttr.includes(`'${this.importSort.column}'`)) {
                if (th && th.classList) th.classList.add('active-sort');
                if (icon) {
                    icon.className = this.importSort.direction === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down';
                }
            }
        });
    }

    renderPreview(data, target = 'modal') {
        const idPrefix = target === 'view' ? 'import-view-' : 'import-';
        const suffix = target === 'view' ? '-view' : '';

        const tbody = document.getElementById(`${idPrefix}preview-body`);
        const totalSpan = document.getElementById(`scan${suffix}-total`);

        // Elementos de la Barra Maestra (Solo aplica a 'view')
        const masterBar = document.getElementById('master-import-bar');
        const masterIcon = document.getElementById('master-bar-icon');
        const masterTitle = document.getElementById('master-bar-title');
        const masterText = document.getElementById('master-bar-text');
        const extraActions = document.getElementById('master-extra-actions');
        const btnImport = document.getElementById('btn-master-import');

        if (totalSpan) totalSpan.textContent = data.total_found;

        this.previewData = data.clients || [];
        const needsProvisioning = data.summary?.needs_provisioning || false;
        const discoveredCount = data.summary?.discovered_no_queue || 0;
        const routerId = data.router_id;
        const routerName = data.router_alias;

        // Reset de Barra Maestra si existe
        if (masterBar && target === 'view') {
            masterBar.style.borderLeft = '4px solid var(--primary-solid)';
            masterBar.style.background = '#ffffff';
            if (masterIcon) masterIcon.innerHTML = '<i class="fas fa-broadcast-tower"></i>';
            if (masterIcon) masterIcon.style.background = 'rgba(99, 102, 241, 0.1)';
            if (masterTitle) masterTitle.textContent = 'Resultados del Escaneo';
            if (masterText) masterText.innerHTML = `Se encontraron <span style="font-weight: 850; color: var(--primary-solid);">${data.total_found}</span> clientes en el router.`;
            if (extraActions) extraActions.innerHTML = '';
            if (btnImport) btnImport.className = 'btn-primary';
        }

        // Lógica de Error Crítico
        if (data.total_found === 0 && data.error_message) {
            if (masterBar && target === 'view') {
                masterBar.style.borderLeft = '4px solid #ef4444';
                if (masterIcon) masterIcon.innerHTML = '<i class="fas fa-exclamation-circle"></i>';
                if (masterIcon) masterIcon.style.background = 'rgba(239, 68, 68, 0.1)';
                if (masterTitle) masterTitle.innerHTML = '<span style="color: #b91c1c;">⚠️ Importación Bloqueada</span>';
                if (masterText) masterText.innerHTML = `<span style="color: #dc2626; font-weight: 600;">${data.error_message}</span>`;
            }
        }
        // Lógica de Transformación a Alerta (Clientes sin Colas)
        else if (needsProvisioning && discoveredCount > 0 && target === 'view') {
            if (masterBar) {
                masterBar.style.borderLeft = '4px solid #f59e0b';
                if (masterIcon) masterIcon.innerHTML = '<i class="fas fa-exclamation-triangle"></i>';
                if (masterIcon) masterIcon.style.background = 'rgba(245, 158, 11, 0.1)';
                if (masterTitle) masterTitle.innerHTML = `⚠️ <span class="alert-count-badge" style="background:#f59e0b; color:white; padding:2px 8px; border-radius:10px; cursor:pointer;" onclick="app.modules.clients.filterClientsWithoutQueues('${target}')">${discoveredCount}</span> Clientes con Anomalías`;
                if (masterText) masterText.innerHTML = `Se detectaron clientes sin Simple Queue en <strong>${routerName}</strong>.`;

                if (extraActions) {
                    extraActions.innerHTML = `
                        <button class="btn-secondary" style="color: #d97706; border-color: #fbbf24;" onclick="app.modules.clients.redirectToRouterSync(${routerId}, '${routerName}')">
                            <i class="fas fa-sync-alt"></i> Sincronizar
                        </button>
                    `;
                }
                if (btnImport) btnImport.className = 'btn-premium';
            }
        }

        if (!tbody) return;

        tbody.innerHTML = this.previewData.map((client, index) => {
            const isDuplicate = client.exists_in_db;
            const isDiscovered = client.type === 'discovered';
            const rowClass = isDuplicate ? 'duplicate-row' : (isDiscovered ? 'needs-provision-row' : '');
            const suffix = target === 'view' ? '-view' : '';

            const canSyncIp = isDuplicate && client.ip_changed;
            const checkbox = (isDuplicate && !canSyncIp)
                ? `<input type="checkbox" disabled>`
                : `<input type="checkbox" class="import-check${suffix}" data-index="${index}" ${canSyncIp ? 'data-sync-only="true"' : ''} onchange="app.modules.clients.updateSelectedCount('${target}')">`;

            let statusBadge = '';
            let restoreBtn = '';

            if (isDuplicate) {
                const dbStatus = client.db_status || 'active';
                const statusMap = {
                    'active': { label: 'Activo', class: 'active' },
                    'suspended': { label: 'Suspendido', class: 'suspended' },
                    'pending': { label: 'Pendiente', class: 'pendiente' },
                    'inactive': { label: 'Cortado', class: 'cortado' },
                    'deleted': { label: 'Eliminado', class: 'cortado' }
                };
                const s = statusMap[dbStatus] || { label: dbStatus, class: 'active' };
                statusBadge = `<span class="status-badge-table ${s.class}">${s.label}</span>`;

                if (dbStatus === 'deleted') {
                    restoreBtn = `<button class="btn-sync-ip" onclick="app.modules.clients.restoreClientFromImport(${client.client_id}, '${target}')" title="Restaurar al sistema">
                        <i class="fas fa-undo"></i>
                    </button>`;
                }
            } else if (isDiscovered) {
                statusBadge = `<span class="status-badge-table cortado">Sin Simple Queue</span>`;
            } else {
                statusBadge = `<span class="status-badge-table online">Nuevo</span>`;
            }

            const ipDisplay = client.ip_changed
                ? `<div class="ip-sync-container dual-ip">
                    <div class="ip-diff">
                        <span class="ip-old" title="IP en Base de Datos">${client.db_ip}</span>
                        <i class="fas fa-arrow-right ip-arrow"></i>
                        <span class="ip-new" title="IP en MikroTik">${client.ip_address}</span>
                    </div>
                    <button class="btn-sync-ip" onclick="app.modules.clients.syncClientIp(${client.client_id}, '${client.ip_address}', '${target}')" title="Actualizar IP en Base de Datos">
                        <i class="fas fa-sync-alt"></i>
                    </button>
                   </div>`
                : client.ip_address;

            return `<tr class="${rowClass}">
                <td data-label="Seleccion">${checkbox}</td>
                <td data-label="Usuario / Nombre">
                    <div class="user-info-cell">
                        <strong>${client.username}</strong>
                    </div>
                </td>
                <td data-label="Gestión">
                    <span class="badge" style="background: ${client.type === 'pppoe' ? '#e0e7ff' : '#f3e8ff'}; color: ${client.type === 'pppoe' ? '#4338ca' : '#7e22ce'}; border: 1px solid rgba(0,0,0,0.05); text-transform: uppercase; font-weight: 700; display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.7rem;">
                        ${client.type === 'pppoe' ? 'PPPoE' : (client.type === 'simple_queue' ? 'S. QUEUE' : (client.type || 'N/A').toUpperCase())}
                    </span>
                </td>
                <td data-label="IP / MikroTik" class="ip-cell">${ipDisplay}</td>
                <td data-label="Plan / Perfil">${client.profile}</td>
                <td data-label="Estado Actual">
                    <div style="display: flex; align-items: center; gap: 8px; justify-content: flex-end;">
                        ${statusBadge}
                        ${restoreBtn}
                    </div>
                </td>
            </tr>`;
        }).join('');

        const selectAll = document.getElementById(`select-all${suffix}-import`);
        if (selectAll) {
            selectAll.onclick = (e) => {
                const checks = document.querySelectorAll(`.import-check${suffix}:not(:disabled)`);
                checks.forEach(c => c.checked = e.target.checked);
                this.updateSelectedCount(target);
            };
        }

        this.updateSelectedCount(target);
    }

    filterClientsWithoutQueues(target = 'modal') {
        const idPrefix = target === 'view' ? 'import-view-' : 'import-';
        const rows = document.querySelectorAll(`#${idPrefix}preview-body tr`);
        rows.forEach(row => {
            if (row && row.classList && row.classList.contains('needs-provision-row')) {
                row.style.display = '';
            } else if (row) {
                row.style.display = 'none';
            }
        });
    }

    redirectToRouterSync(routerId, routerName) {
        if (confirm(`¿Deseas sincronizar el router "${routerName}" para crear Simple Queues automáticamente?`)) {
            const modal = document.getElementById('import-clients-modal');
            if (modal && modal.classList) modal.classList.remove('active');

            this.eventBus.publish('navigate', { view: 'routers' });
            setTimeout(() => {
                if (window.app && window.app.modules && window.app.modules.routers) {
                    window.app.modules.routers.syncRouter(routerId);
                }
            }, 500);
        }
    }

    updateSelectedCount(target = 'modal') {
        const suffix = target === 'view' ? '-view' : '';
        const checks = document.querySelectorAll(`.import-check${suffix}:checked`);
        const count = checks.length;

        const syncChecks = Array.from(checks).filter(c => c.dataset.syncOnly === 'true');
        const syncCount = syncChecks.length;
        const importCount = count - syncCount;

        const countSpan = document.getElementById(`selected${suffix}-count`);
        const alertCountSpan = document.getElementById(`selected-count-alert${suffix}`);
        const syncAlertCountSpan = document.getElementById(`sync-count-alert${suffix}`);
        const btnSyncBulk = document.getElementById(`btn-bulk-sync-ips${suffix}`);

        if (countSpan) countSpan.textContent = importCount;
        if (alertCountSpan) alertCountSpan.textContent = importCount;
        if (syncAlertCountSpan) syncAlertCountSpan.textContent = syncCount;

        if (btnSyncBulk) {
            btnSyncBulk.style.display = syncCount > 0 ? 'inline-block' : 'none';
        }
    }

    async syncSelectedIps(target = 'modal') {
        const suffix = target === 'view' ? '-view' : '';
        const checks = document.querySelectorAll(`.import-check${suffix}:checked`);
        const syncItems = Array.from(checks)
            .filter(c => c.dataset.syncOnly === 'true')
            .map(c => {
                const client = this.previewData[c.dataset.index];
                return {
                    client_id: client.client_id,
                    ip_address: client.ip_address
                };
            });

        if (syncItems.length === 0) return;

        if (!confirm(`¿Deseas actualizar la IP de ${syncItems.length} cliente(s) en la base de datos?`)) return;

        try {
            const response = await this.api.post('/api/clients/bulk-sync-ips', { updates: syncItems });
            if (response.success) {
                toast.success(`${response.synchronized} IPs actualizadas correctamente`);
                this.scanRouter(target);
            } else {
                toast.error('Error en la sincronización: ' + (response.errors ? response.errors.join(', ') : 'Desconocido'));
            }
        } catch (e) {
            console.error('Error in bulk IP sync:', e);
            toast.error('Error al sincronizar IPs de forma masiva');
        }
    }

    async syncClientIp(clientId, newIp, target) {
        if (!confirm(`¿Estás seguro de que deseas actualizar la IP del cliente a ${newIp}?`)) return;

        try {
            await this.api.put(`/api/clients/${clientId}`, { ip_address: newIp });
            toast.success('IP actualizada correctamente en la base de datos');
            // Re-escanear para actualizar la vista después de la sincronización
            this.scanRouter(target);
        } catch (e) {
            console.error('Error syncing IP:', e);
            toast.error('Error al actualizar IP: ' + e.message);
        }
    }

    async executeImport(target = 'modal') {
        const idPrefix = target === 'view' ? 'import-view-' : 'import-';
        const suffix = target === 'view' ? '-view' : '';

        const select = document.getElementById(`${idPrefix}router-select`);
        const routerId = select ? select.value : null;

        // CORRECCIÓN: Filtrar para obtener solo lo que NO es de sincronización única
        const allChecks = document.querySelectorAll(`.import-check${suffix}:checked`);
        const checks = Array.from(allChecks).filter(c => c.dataset.syncOnly !== 'true');

        if (checks.length === 0) return alert('Selecciona al menos un cliente nuevo para importar');

        const selectedClients = checks.map(c => this.previewData[c.dataset.index]);

        const loading = document.getElementById(`${idPrefix}loading`);
        const loadingText = document.getElementById(`${idPrefix}loading-text`);

        if (loading) loading.style.display = 'flex';
        if (loadingText) loadingText.textContent = `Importando ${checks.length} clientes...`;

        const importModeSelect = document.getElementById(`${idPrefix}mode-select`);
        const importMode = importModeSelect ? importModeSelect.value : 'standard';

        try {
            const response = await this.api.post('/api/clients/execute-import', {
                router_id: routerId,
                import_mode: importMode,
                clients: selectedClients
            });

            if (response.success && response.imported > 0) {
                toast.success(`Importación completada: ${response.imported} clientes importados.`);

                // Mostrar alerta si hubo algunos fallos parciales
                if (response.errors && response.errors.length > 0) {
                    alert('Atención: Algunos clientes no pudieron ser importados:\n' + response.errors.join('\n'));
                }

                if (target === 'modal') {
                    const modal = document.getElementById('import-clients-modal');
                    if (modal && modal.classList) modal.classList.remove('active');
                } else {
                    this.eventBus.publish('navigate', { view: 'clients' });
                }
                this.loadClients();
            } else {
                // Si no se importó nada o hubo error total
                const errorMsg = response.errors && response.errors.length > 0
                    ? 'Errores en la importación:\n' + response.errors.join('\n')
                    : 'No se importó ningún cliente. Es posible que ya existan con el mismo nombre o IP.';
                alert(errorMsg);

                // Si estamos en modal, no lo cerramos para que pueda corregir
                if (loading) loading.style.display = 'none';
                return; // Evita el finally para no ocultar el loading si queremos que se quede (aunque aquí lo ocultamos manualmente)
            }
        } catch (e) {
            alert('Error en importación: ' + e.message);
        } finally {
            if (loading) loading.style.display = 'none';
        }
    }

    setupStatsListeners() {
        const pills = [
            { id: 'count-total', status: 'all' },
            { id: 'count-active', status: 'active' },
            { id: 'count-suspended', status: 'suspended' },
            { id: 'count-online', status: 'online' },
            { id: 'count-offline', status: 'offline' },
            { id: 'count-morosos', status: 'morosos' },
            { id: 'count-pagos', status: 'paid' },
            { id: 'count-warning', status: 'warning' }
        ];

        pills.forEach(p => {
            const pillEl = document.getElementById(p.id)?.parentElement;
            if (pillEl) {
                pillEl.style.cursor = 'pointer';
                pillEl.onclick = () => {
                    const statusSelect = document.getElementById('filter-status');
                    if (statusSelect) {
                        // Special handling for financial filters
                        if (p.status === 'morosos' || p.status === 'paid') {
                            statusSelect.value = 'all'; // Financials filter globally for now
                            this.filterState.financialStatus = p.status;
                        } else {
                            statusSelect.value = p.status;
                            this.filterState.financialStatus = 'all';
                        }

                        const searchInput = document.getElementById('client-search');
                        if (searchInput) {
                            searchInput.value = '';
                            this.filterState.search = '';
                        }
                        this.applyFilters();
                    }
                };
            }
        });
    }
}
