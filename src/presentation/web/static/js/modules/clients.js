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
            search: '',
            financialStatus: 'all' // 'all', 'morosos', 'paid'
        };

        this.socketInitialized = false;
        this.importSort = { column: '', direction: 'asc' };
        this.sortState = { column: 'id', direction: 'asc' };
        this.trashState = { search: '', clients: [], selectedIds: new Set(), sort: { column: 'updated_at', direction: 'desc' } };

        // Pagination State
        this.currentPage = 1;
        this.pageSize = 50;
        this.totalFiltered = 0;

        // DOM Cache
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

        // Mobile View Detection
        this.isMobile = window.innerWidth < 1024;
        window.addEventListener('resize', () => {
            const wasMobile = this.isMobile;
            this.isMobile = window.innerWidth < 1024;
            if (wasMobile !== this.isMobile && this.viewManager.currentSubView === 'clients') {
                this.renderClients();
            }
        });

        console.log('👥 Clients Module initialized');
    }

    async load() {
        console.log('👥 Loading Clients List...');
        this.viewManager.showSubView('clients');

        const tbody = document.getElementById('clients-table-body');
        if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="loading-cell"><div class="spinner"></div><p>Cargando Clientes...</p></td></tr>';

        try {
            await Promise.all([this.loadRouters(), this.loadPlans()]);

            if (!this.filterState.routerId && this.routers.length > 0) {
                this.filterState.routerId = this.routers[0].id;
                const routerSelect = document.getElementById('filter-router');
                if (routerSelect) routerSelect.value = this.filterState.routerId;
            }

            await this.loadClients();
            this.setupStatsListeners();
        } catch (e) {
            console.error('Error during load:', e);
        }
    }

    async loadClientsImport() {
        console.log('👥 Loading Clients Import View...');
        this.viewManager.showSubView('clients-import');

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
        this.viewManager.showSubView('clients-actions');

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
        this.viewManager.showSubView('clients-trash');
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
                    `<span class="status-badge-table suspended">Pendiente</span>
                         <div class="debt-amount negative">$${client.account_balance.toLocaleString('es-CO', { minimumFractionDigits: 0 })}</div>` :
                    `<span class="status-badge-table active">Al día</span>
                         <div class="debt-amount positive">$0</div>`
                }
                </td>
                <td>
                    <div style="display: flex; flex-direction: column; gap: 4px;">
                        <span style="font-size: 0.8rem; font-weight: 700;">${this.formatPlanName(client.plan_name)}</span>
                        <span class="status-badge-table ${isSuspended ? 'suspended' : 'active'}">
                            ${isSuspended ? 'Bloqueado' : 'Activo'}
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
        const suspended = dataset.filter(c => (c.status || '').toLowerCase() === 'suspended').length;
        const pending = dataset.filter(c => (c.account_balance || 0) > 0).length;

        document.getElementById('count-total-actions').textContent = total;
        document.getElementById('count-suspended-actions').textContent = suspended;
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

    onSearchInputActions(value) {
        if (this.searchTimeoutActions) clearTimeout(this.searchTimeoutActions);
        this.searchTimeoutActions = setTimeout(() => {
            this.filterClientsActions();
        }, 500);
    }

    toggleSelectAllActions(master) {
        const checkboxes = document.querySelectorAll('.client-checkbox-actions');
        checkboxes.forEach(cb => cb.checked = master.checked);
        this.updateSelectionActions();
    }

    updateSelectionActions() {
        const checkboxes = document.querySelectorAll('.client-checkbox-actions:checked');
        const count = checkboxes.length;
        const buttonsContainer = document.getElementById('bulk-actions-buttons-actions');
        const countDisplay = document.getElementById('selected-count-display-actions');

        if (countDisplay) countDisplay.textContent = count;

        const countStat = document.getElementById('count-selected-actions');
        if (countStat) countStat.textContent = count;

        if (buttonsContainer) {
            if (count > 0) {
                // Habilitar botones
                buttonsContainer.style.opacity = '1';
                buttonsContainer.style.pointerEvents = 'auto';
            } else {
                // Deshabilitar botones
                buttonsContainer.style.opacity = '0.5';
                buttonsContainer.style.pointerEvents = 'none';
                const master = document.getElementById('select-all-clients-actions');
                if (master) master.checked = false;
            }
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
                toast.warning(`Se omitieron ${removed} cliente(s) que no pertenecen al router seleccionado`);
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
        this.updateSelectionActions();
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
        const searchInput = document.getElementById('client-search');

        const newRouterId = routerSelect ? routerSelect.value : '';
        const oldRouterId = this.filterState.routerId;

        this.filterState.routerId = newRouterId;
        this.filterState.status = statusSelect ? statusSelect.value : 'all';
        this.filterState.planId = planSelect ? planSelect.value : '';
        if (searchInput) this.filterState.search = searchInput.value;

        this.currentPage = 1; // RESET PAGINATION on filter change

        // Update active class on pills
        this.updatePillActiveState();

        // If Router changed, we must reload from API (as Router is a server-side scope)
        // If only local filters changed, just re-filter in memory
        if (newRouterId !== oldRouterId || !this.allClients) {
            this.loadClients();
        } else {
            this.filterClients();
        }
    }

    updatePillActiveState() {
        const { status, financialStatus } = this.filterState;

        // Remove active class from all
        document.querySelectorAll('.stat-pill').forEach(p => p.classList.remove('active-filter'));

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
            if (pillEl) pillEl.classList.add('active-filter');
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
            // Default: Online first if no specific column is active-sorting (except if explicitly sorting by online status)
            if (!col || col === 'id') {
                const aStatus = this.onlineStatusMap[a.id];
                const bStatus = this.onlineStatusMap[b.id];
                const aOnline = (aStatus === 'online' || aStatus === 'detected_no_queue');
                const bOnline = (bStatus === 'online' || bStatus === 'detected_no_queue');
                if (aOnline && !bOnline) return -1;
                if (!aOnline && bOnline) return 1;
                if (col === 'id') return (a.id - b.id) * dir;
                return a.id - b.id; // Stability
            }

            let valA = a[col];
            let valB = b[col];

            // Special case for legal_name (case insensitive)
            if (col === 'legal_name') {
                valA = (valA || '').toString().toLowerCase();
                valB = (valB || '').toString().toLowerCase();
                return valA.localeCompare(valB) * dir;
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

            // Generic string/number sort
            if (typeof valA === 'string') {
                return valA.localeCompare(valB || '') * dir;
            }
            return ((valA || 0) - (valB || 0)) * dir;
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

        // IMPORTANT: We do NOT re-populate plan filter here to avoid shrinking the dropdown options while filtering.
        // We only populate it once on load or if specifically refreshed.
    }

    toggleSelectAll(master) {
        const checkboxes = document.querySelectorAll('.client-checkbox');
        checkboxes.forEach(cb => cb.checked = master.checked);
        this.updateSelection();
    }

    updateSelection() {
        const checkboxes = document.querySelectorAll('.client-checkbox:checked');
        const count = checkboxes.length;
        const bar = document.getElementById('bulk-actions-bar');
        const label = document.getElementById('selected-count-label');

        if (label) label.textContent = count;

        if (count > 0) {
            bar.classList.add('active');
        } else {
            bar.classList.remove('active');
            const master = document.getElementById('select-all-clients');
            if (master) master.checked = false;
        }
    }

    clearSelection() {
        const checkboxes = document.querySelectorAll('.client-checkbox');
        checkboxes.forEach(cb => cb.checked = false);
        const master = document.getElementById('select-all-clients');
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

        // Safety check for mobile detection
        this.isMobile = window.innerWidth < 1024;

        // Initialize onlineStatusMap for all clients to avoid undefined if socket hasn't emitted yet
        const onlineMap = this.onlineStatusMap || {};
        this.clients.forEach(c => {
            if (onlineMap[c.id] === undefined) {
                onlineMap[c.id] = 'offline';
            }
        });

        const html = this.clients.map(client => {
            if (!client) return '';
            // Logic for status and colors
            const isOnline = onlineMap[client.id] === 'online';
            const isDeleted = (client.status || '').toLowerCase() === 'deleted';
            const isSuspended = (client.status || '').toLowerCase() === 'suspended';

            let statusColor = 'grey';
            let statusLabel = isOnline ? 'Online' : 'Offline';

            if (isDeleted) {
                statusColor = 'cortado';
                statusLabel = 'Eliminado';
            } else if (isSuspended) {
                statusColor = 'suspended';
                statusLabel = 'Suspendido';
            } else if (isOnline) {
                statusColor = 'active';
            }

            if (this.isMobile) {
                // Card View (Mobile)
                const avatarChar = (client.legal_name || '?').charAt(0).toUpperCase();
                const balance = client.account_balance || 0;
                const isPositive = balance <= 0;
                const balanceText = Math.abs(balance).toLocaleString('es-CO');

                return `
                <div class="client-card-mobile" data-client-id="${client.id}">
                    <div class="card-mobile-header">
                        <div class="card-mobile-client-info">
                            <div class="card-mobile-avatar">${avatarChar}</div>
                            <div class="card-mobile-name-group">
                                <span class="card-mobile-name">${client.legal_name}</span>
                                <span class="card-mobile-code">${client.subscriber_code || '---'}</span>
                            </div>
                        </div>
                        <div class="card-mobile-status">
                            <span class="status-badge-table ${statusColor}" style="margin: 0;">${statusLabel}</span>
                        </div>
                    </div>
                    
                    <div class="card-mobile-body">
                        <div class="card-mobile-data-item">
                            <span class="data-item-label">Conexión</span>
                            <span class="data-item-value">${client.ip_address || '---'}</span>
                        </div>
                        <div class="card-mobile-data-item">
                            <span class="data-item-label">Plan</span>
                            <span class="data-item-value">${this.formatPlanName(client.plan_name)}</span>
                        </div>
                        <div class="card-mobile-data-item">
                            <span class="data-item-label">Router</span>
                            <span class="data-item-value">${client.router || '---'}</span>
                        </div>
                        <div class="card-mobile-data-item">
                            <span class="data-item-label">Balance</span>
                            <span class="data-item-value ${isPositive ? 'ok' : 'debt'}">$${balanceText}</span>
                        </div>
                    </div>
                    
                    <div class="card-mobile-footer">
                        <div class="card-mobile-traffic">
                            <div class="traffic-pill up">
                                <i class="fas fa-upload"></i> <span class="val-up">0K</span>
                            </div>
                            <div class="traffic-pill down">
                                <i class="fas fa-download"></i> <span class="val-down">0K</span>
                            </div>
                        </div>
                        
                        <div class="card-mobile-actions">
                            <button class="mobile-action-btn pay" onclick="app.modules.clients.registerPayment(${client.id})">
                                <i class="fas fa-dollar-sign"></i>
                            </button>
                            <button class="mobile-action-btn edit" onclick="app.modules.clients.editClient(${client.id})">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="mobile-action-btn more" onclick="app.modules.clients.showMobileActionMenu(${client.id})">
                                <i class="fas fa-ellipsis-h"></i>
                            </button>
                        </div>
                    </div>
                </div>`;
            } else {
                // Table View (Desktop)
                return `
                <tr data-client-id="${client.id}">
                    <td><input type="checkbox" class="client-checkbox" value="${client.id}" onclick="app.modules.clients.updateSelection()"></td>
                    <td style="font-size: 0.75rem; color: #94a3b8; font-weight: 700;">#${client.id}</td>
                    <td>
                        <div class="client-name-cell">
                            <div class="client-avatar">${(client.legal_name || '?').charAt(0).toUpperCase()}</div>
                            <div class="client-info">
                                <span class="client-real-name">${client.legal_name}</span>
                                <span class="client-code">${client.subscriber_code || '---'}</span>
                            </div>
                        </div>
                    </td>
                    <td>
                        <div class="ip-display">${client.ip_address || 'Sin IP'}</div>
                        <span class="credential-text">${client.mac_address || ''}</span>
                    </td>
                    <td>
                        <div style="font-weight: 600;">${client.router ? client.router.substring(0, 15) : '---'}</div>
                        <div style="font-size: 0.75rem; color: #64748b;">${client.zone || ''}</div>
                    </td>
                    <td>
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            ${(client.account_balance || 0) > 0 ?
                        `<span class="status-badge-table suspended">Pendiente</span>
                                 <div class="debt-amount negative">$${client.account_balance.toLocaleString('es-CO', { minimumFractionDigits: 0 })}</div>` :
                        `<span class="status-badge-table active">Al día</span>
                                 <div class="debt-amount positive">$${Math.abs(client.account_balance || 0).toLocaleString('es-CO', { minimumFractionDigits: 0 })}</div>`
                    }
                        </div>
                    </td>
                    <td>
                        <div style="display: flex; flex-direction: column; gap: 4px;">
                            <span style="font-size: 0.8rem; font-weight: 700;">${this.formatPlanName(client.plan_name)}</span>
                            <span class="status-badge-table ${statusColor}">${statusLabel}</span>
                            ${!isOnline && client.last_seen ? `<span class="last-seen-text">${this.formatLastSeen(client.last_seen)}</span>` : ''}
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
                    <td style="text-align: right;">
                        <div class="action-menu" style="justify-content: flex-end;">
                            <button class="action-btn" onclick="app.modules.clients.showClientHistory(${client.id})" title="Kardex / Pagos">
                                <i class="fas fa-history"></i>
                            </button>
    
                            ${!isDeleted ? `
                                <button class="action-btn" onclick="app.modules.clients.registerPayment(${client.id})" title="Pagar">
                                    <i class="fas fa-dollar-sign"></i>
                                </button>
                                <button class="action-btn" onclick="app.modules.clients.editClient(${client.id})" title="Editar">
                                    <i class="fas fa-edit"></i>
                                </button>
                                ${isSuspended ?
                            `<button class="action-btn" style="color: #10b981; border-color: #10b981;" onclick="app.modules.clients.activateClient(${client.id})" title="Activar">
                                        <i class="fas fa-play"></i>
                                     </button>` :
                            `<button class="action-btn" style="color: #f59e0b; border-color: #f59e0b;" onclick="app.modules.clients.suspendClient(${client.id})" title="Suspender">
                                        <i class="fas fa-pause"></i>
                                     </button>`
                        }
                            ` : `
                                <button class="action-btn" style="color: #3b82f6; border-color: #3b82f6;" onclick="app.modules.clients.restoreClient(${client.id})" title="Restaurar">
                                    <i class="fas fa-undo"></i>
                                </button>
                            `}
    
                            <button class="action-btn delete" onclick="app.modules.clients.deleteClient(${client.id})" title="Eliminar">
                                <i class="fas fa-trash-alt"></i>
                            </button>
                        </div>
                    </td>
                </tr>
                `;
            }
        }).join('');

        if (this.isMobile && cardGrid) {
            tbody.innerHTML = ''; // Clear table
            cardGrid.innerHTML = html;
        } else if (tbody) {
            if (cardGrid) cardGrid.innerHTML = ''; // Clear cards
            tbody.innerHTML = html;
        }
    }

    updateStaticStats() {
        // Use Global Dataset (allClients) for stats to keep them "Real" during search
        const dataset = this.allClients || this.clients || [];
        const isDeletedView = this.filterState.status === 'deleted';

        const active = dataset.filter(c => (c.status || '').toLowerCase() === 'active').length;
        const suspended = dataset.filter(c => (c.status || '').toLowerCase() === 'suspended').length;
        const deleted = dataset.filter(c => (c.status || '').toLowerCase() === 'deleted').length;

        // Financiero: Basado en account_balance
        const morosos = dataset.filter(c => (c.account_balance || 0) > 0).length;
        const pagos = dataset.filter(c => (c.account_balance || 0) <= 0).length;

        // Operacional refers to anyone not deleted
        const totalOperational = active + suspended;

        // Online count depends on WebSocket map
        const onlineStatusMap = this.onlineStatusMap || {};
        const online = dataset.filter(c => onlineStatusMap[c.id] === 'online').length;
        const warning = dataset.filter(c => onlineStatusMap[c.id] === 'detected_no_queue').length;
        const offline = dataset.filter(c => onlineStatusMap[c.id] === 'offline' || !onlineStatusMap[c.id]).length;

        // Update UI
        if (isDeletedView) {
            this.setSafeText('count-total', deleted);
            this.setSafeText('count-active', 0);
            this.setSafeText('count-suspended', 0);
            this.setSafeText('count-online', 0);
            this.setSafeText('count-offline', deleted);
            this.setSafeText('count-morosos', 0);
            this.setSafeText('count-pagos', 0);
            this.setSafeText('count-warning', 0);
        } else {
            this.setSafeText('count-total', totalOperational);
            this.setSafeText('count-active', active);
            this.setSafeText('count-suspended', suspended);
            this.setSafeText('count-online', online);
            this.setSafeText('count-offline', offline);
            this.setSafeText('count-morosos', morosos);
            this.setSafeText('count-pagos', pagos);
            this.setSafeText('count-warning', warning);
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

            // Join router room if specific router is selected
            if (this.filterState.routerId) {
                app.socket.emit('join_router', { router_id: this.filterState.routerId });
            }

            // No matter if router is selected or not, we send client IDs.
            // Backend will now handle finding the correct routers for these clients.
            app.socket.emit('subscribe_clients', {
                router_id: this.filterState.routerId || null,
                client_ids: clientIds
            });

            console.log(`🔌 Suscrito al monitoreo de ${clientIds.length} clientes...`);
        }
    }

    stopTrafficMonitor() {
        if (app.socket && app.socket.connected) {
            const dataset = this.allClients || this.clients || [];
            const clientIds = dataset.map(c => c.id);
            if (clientIds.length > 0) {
                app.socket.emit('unsubscribe_clients', { client_ids: clientIds });
            }
        }
    }

    updateTrafficUI(data) {
        if (!this.onlineStatusMap) this.onlineStatusMap = {};

        // PERFORMANCE: Only update UI if we are in the clients view AND the tab is visible
        const currentView = this.viewManager.currentSubView;
        const isOperationalView = (currentView === 'clients' || currentView === 'clients-actions') && !document.hidden;

        if (!isOperationalView) {
            // Still update internal state even if not visible
            Object.keys(data).forEach(clientId => {
                if (clientId !== '__stats__') {
                    this.onlineStatusMap[clientId] = data[clientId].status;
                }
            });
            return;
        }

        // Remove global stats if present
        if (data['__stats__']) delete data['__stats__'];

        // 1. Update internal state and UI Rows
        Object.keys(data).forEach(clientId => {
            this.onlineStatusMap[clientId] = data[clientId].status;

            // Get element from cache or DOM (works for tr or cards)
            let row = this.rowCache.get(clientId);
            if (!row) {
                row = document.querySelector(`[data-client-id="${clientId}"]`);
                if (row) this.rowCache.set(clientId, row);
            }

            if (row) {
                const info = data[clientId];
                const isOnline = info.status === 'online';

                // Update Status Badge
                const badge = row.querySelector('.status-badge-table');
                if (badge && !badge.classList.contains('suspended')) { // Don't override suspended status
                    badge.className = `status - badge - table ${isOnline ? 'active' : 'grey'}`;
                    badge.textContent = isOnline ? 'Online' : 'Offline';

                    // Fix "Detected (No Queue)" on the fly if status changes
                    if (info.status === 'detected_no_queue') {
                        badge.className = 'status-badge-table warning';
                        badge.innerHTML = 'Detected (No Queue) <i class="fas fa-exclamation-triangle" style="margin-left:4px; cursor:pointer;" onclick="event.stopPropagation(); app.modules.clients.fixClientQueue(' + clientId + ')" title="Reparar Cola Simple"></i>';
                    }

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
            }
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

            window.open(`/ api / clients /export?${params.toString()} `, '_blank');
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
            await this.api.post(`/ api / clients / ${clientId}/suspend`, {});
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
                modal.classList.add('active');
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
                if (modal) modal.classList.remove('active');
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

        const html = `
            <div style="display: flex; flex-direction: column; gap: 12px; margin-top: 10px;">
                <button class="btn-primary" onclick="Swal.close(); setTimeout(() => app.modules.clients.showClientHistory(${clientId}), 300)" style="width: 100%; padding: 14px; background: #3b82f6; border: none; color: white; border-radius: 12px; font-weight: 600; font-size: 1rem; display: flex; align-items: center; justify-content: center; gap: 10px;">
                    <i class="fas fa-history"></i> Historial y Pagos
                </button>
                <button class="btn-primary" onclick="Swal.close(); setTimeout(() => app.modules.clients.${isSuspended ? 'activateClient' : 'suspendClient'}(${clientId}), 300)" style="width: 100%; padding: 14px; background: ${stColor}; border: none; color: white; border-radius: 12px; font-weight: 600; font-size: 1rem; display: flex; align-items: center; justify-content: center; gap: 10px;">
                    <i class="fas ${stIcon}"></i> ${stText}
                </button>
                <button class="btn-primary" onclick="Swal.close(); setTimeout(() => app.modules.clients.deleteClient(${clientId}), 300)" style="width: 100%; padding: 14px; background: #ef4444; border: none; color: white; border-radius: 12px; font-weight: 600; font-size: 1rem; display: flex; align-items: center; justify-content: center; gap: 10px;">
                    <i class="fas fa-trash-alt"></i> Eliminar Cliente
                </button>
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
            const icon = th.querySelector('i');
            th.classList.remove('active-sort');
            if (icon) icon.className = 'fas fa-sort';

            const onClickAttr = th.getAttribute('onclick');
            if (onClickAttr && onClickAttr.includes(`'${this.sortState.column}'`)) {
                th.classList.add('active-sort');
                if (icon) {
                    icon.className = this.sortState.direction === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down';
                }
            }
        });
    }

    updateSortIcons(target) {
        const idPrefix = target === 'view' ? 'import-view-' : 'import-';
        const table = document.querySelector(target === 'view' ? '#clients-import-view table' : '#import-clients-modal table');

        if (!table) return;

        const headers = table.querySelectorAll('th.sortable');
        headers.forEach(th => {
            const icon = th.querySelector('i');
            th.classList.remove('active-sort');
            if (icon) icon.className = 'fas fa-sort';

            // Si coincide con la columna actual, marcar activa
            const onClickAttr = th.getAttribute('onclick');
            if (onClickAttr && onClickAttr.includes(`'${this.importSort.column}'`)) {
                th.classList.add('active-sort');
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
        if (totalSpan) totalSpan.textContent = data.total_found;

        this.previewData = data.clients || [];

        const needsProvisioning = data.summary?.needs_provisioning || false;
        const discoveredCount = data.summary?.discovered_no_queue || 0;
        const routerId = data.router_id;
        const routerName = data.router_alias;

        let hasDuplicates = false;

        if (!tbody) return;

        tbody.innerHTML = this.previewData.map((client, index) => {
            if (client.exists_in_db) hasDuplicates = true;

            const isDuplicate = client.exists_in_db;
            const isDiscovered = client.type === 'discovered';
            const rowClass = isDuplicate ? 'duplicate-row' : (isDiscovered ? 'needs-provision-row' : '');

            const canSyncIp = isDuplicate && client.ip_changed;
            const checkbox = (isDuplicate && !canSyncIp)
                ? `<input type="checkbox" disabled>`
                : `<input type="checkbox" class="import-check${suffix}" data-index="${index}" ${canSyncIp ? 'data-sync-only="true"' : ''} onchange="app.modules.clients.updateSelectedCount('${target}')">`;

            // Lógica de Estados Granulares
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

            // Lógica de IP cambiada
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
                <td>${checkbox}</td>
                <td>
                    <div class="user-info-cell">
                        <strong>${client.username}</strong>
                    </div>
                </td>
                <td>
                    <span class="badge" style="font-size: 0.7rem; padding: 3px 10px; border-radius: 12px; background: ${client.type === 'pppoe' ? '#dbeafe' : '#f3e8ff'}; color: ${client.type === 'pppoe' ? '#1e40af' : '#6b21a8'}; border: 1px solid ${client.type === 'pppoe' ? '#93c5fd' : '#d8b4fe'}; text-transform: uppercase; font-weight: 700; display: inline-block; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                        ${client.type === 'pppoe' ? 'PPPoE' : (client.type === 'simple_queue' ? 'S. QUEUE' : (client.type || 'N/A').toUpperCase())}
                    </span>
                </td>
                <td class="ip-cell">${ipDisplay}</td>
                <td>${client.profile}</td>
                <td>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        ${statusBadge}
                        ${restoreBtn}
                    </div>
                </td>
            </tr>`;
        }).join('');

        const dupMsg = document.getElementById(`scan${suffix}-duplicates`);
        if (dupMsg) dupMsg.style.display = hasDuplicates ? 'block' : 'none';

        // Re-integrar alerta de auto-provisioning
        const toolbar = document.getElementById(`${idPrefix}toolbar-top`);
        const alertId = `auto-provision-alert${suffix}`;
        const oldAlert = document.getElementById(alertId);
        if (oldAlert) oldAlert.remove();

        if (needsProvisioning && discoveredCount > 0) {
            const alertDiv = document.createElement('div');
            alertDiv.id = alertId;
            alertDiv.className = 'premium-alert';

            alertDiv.innerHTML = `
                <div class="alert-icon">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="alert-content">
                    <h4>⚠️ <span class="alert-count-badge" onclick="app.modules.clients.filterClientsWithoutQueues('${target}')">${discoveredCount}</span> cliente${discoveredCount > 1 ? 's' : ''} sin Simple Queue</h4>
                    <p>
                        Se detectaron <span class="alert-count-badge" onclick="app.modules.clients.filterClientsWithoutQueues('${target}')">${discoveredCount}</span> clientes conectados pero sin Simple Queue en <strong>${routerName}</strong>.
                    </p>
                </div>
                <div class="alert-actions">
                    <button class="btn-alert-sync" onclick="app.modules.clients.redirectToRouterSync(${routerId}, '${routerName}')">
                        <i class="fas fa-sync-alt"></i> Sincronizar
                    </button>
                    <button class="btn-primary" onclick="app.modules.clients.executeImport('${target}')">
                        Importar (<span id="selected-count-alert${suffix}">0</span>)
                    </button>
                    <button id="btn-bulk-sync-ips${suffix}" class="btn-premium" style="display:none; margin-left: 10px;" onclick="app.modules.clients.syncSelectedIps('${target}')">
                        <i class="fas fa-sync"></i> Corregir IPs (<span id="sync-count-alert${suffix}">0</span>)
                    </button>
                </div>
            `;

            const table = tbody.closest('table');
            if (table && table.parentNode) {
                table.parentNode.insertBefore(alertDiv, table);
                if (toolbar) toolbar.style.display = 'none';
            }
        } else {
            if (toolbar) toolbar.style.display = 'flex';
        }

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
            if (row.classList.contains('needs-provision-row')) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    redirectToRouterSync(routerId, routerName) {
        if (confirm(`¿Deseas sincronizar el router "${routerName}" para crear Simple Queues automáticamente?`)) {
            const modal = document.getElementById('import-clients-modal');
            if (modal) modal.classList.remove('active');

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
                    if (modal) modal.classList.remove('active');
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

    setFilter(type) {
        this.currentFilter = type;
        document.querySelectorAll('.client-stats-bar .stat-item').forEach(el => el.classList.remove('active'));
        const activeId = {
            'ALL': 'count-total',
            'ACTIVE': 'count-active',
            'SUSPENDED': 'count-suspended',
            'ONLINE': 'count-online',
            'OFFLINE': 'count-offline'
        }[type];
        const activeEl = document.getElementById(activeId)?.parentElement;
        if (activeEl) activeEl.classList.add('active');
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
