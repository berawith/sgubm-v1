/**
 * Clients Module - Frontend para gestión de clientes (Table View)
 */
export class ClientsModule {
    constructor(api, eventBus, viewManager) {
        this.api = api;
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.clients = [];
        this.routers = [];
        this.plans = []; // Store plans for filtering

        // State
        this.filterState = {
            routerId: '',
            status: 'all',
            planId: '',
            search: ''
        };

        this.socketInitialized = false;

        // Auto-resubscribir cuando el socket se conecte (o reconecte)
        this.eventBus.subscribe('socket_connected', () => {
            console.log('🔄 Socket connected: restarting client monitoring...');
            this.startTrafficMonitor();
        });

        // Escuchar cuando se guarde un pago para refrescar la lista
        this.eventBus.subscribe('payment_saved', (data) => {
            console.log('💰 Pago detectado! Refrescando lista de clientes...', data);
            this.loadClients();
        });

        console.log('👥 Clients Module initialized');
    }

    async load() {
        console.log('👥 Loading Clients View...');
        this.showView();

        const tbody = document.getElementById('clients-table-body');
        if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="loading-cell"><div class="spinner"></div><p>Cargando Clientes...</p></td></tr>';

        try {
            // 1. Cargar routers y planes para los filtros
            await Promise.all([this.loadRouters(), this.loadPlans()]);

            // 2. Pre-seleccionar router si no hay filtro
            if (!this.filterState.routerId && this.routers.length > 0) {
                this.filterState.routerId = this.routers[0].id; // Default to first router
                const routerSelect = document.getElementById('filter-router');
                if (routerSelect) routerSelect.value = this.filterState.routerId;
            }

            // 3. Cargar clientes
            await this.loadClients();

            // 4. Inicializar interacción de pills
            this.setupStatsListeners();
        } catch (e) {
            console.error('Error during load:', e);
        }
    }

    showView() {
        // Delegar visualización a ViewManager
        this.viewManager.showMainView('clients');
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
        const status = this.filterState.status;

        // Remove active class from all
        document.querySelectorAll('.stat-pill').forEach(p => p.classList.remove('active-filter'));

        // Find current and add
        const map = {
            'all': 'count-total',
            'online': 'count-online',
            'offline': 'count-offline',
            'suspended': 'count-suspended'
        };

        const pillId = map[status];
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
        // Start with all
        let filtered = [...(this.allClients || [])];

        // 1. Filter by Status (Client-Side)
        const status = this.filterState.status;
        if (status !== 'all') {
            if (status === 'online') {
                filtered = filtered.filter(c => this.onlineStatusMap[c.id] === 'online');
            } else if (status === 'offline') {
                filtered = filtered.filter(c => this.onlineStatusMap[c.id] !== 'online');
            } else {
                // Active / Suspended / Deleted
                filtered = filtered.filter(c => (c.status || '').toLowerCase() === status);
            }
        }

        // 2. Filter by Plan
        if (this.filterState.planId) {
            filtered = filtered.filter(c => c.plan_name === this.filterState.planId);
        }

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

        // 4. Sort: Online first, then by ID (or name)
        filtered.sort((a, b) => {
            const aOnline = this.onlineStatusMap[a.id] === 'online';
            const bOnline = this.onlineStatusMap[b.id] === 'online';

            if (aOnline && !bOnline) return -1;
            if (!aOnline && bOnline) return 1;

            return a.id - b.id; // Stability: secondary sort by ID
        });

        this.clients = filtered;
        console.log('DEBUG: Filtered clients:', this.clients.length);

        this.renderClients();
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
        const tbody = document.getElementById('clients-table-body');
        if (!tbody) return;

        // Inicializar estado desde API
        if (!this.onlineStatusMap || Object.keys(this.onlineStatusMap).length === 0) {
            this.onlineStatusMap = {};
            this.clients.forEach(c => {
                this.onlineStatusMap[c.id] = c.is_online ? 'online' : 'offline';
            });
        }

        this.updateStaticStats();

        if (this.clients.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7">
                        <div class="no-clients">
                            <i class="fas fa-users"></i>
                            <p>No se encontraron clientes con los filtros actuales</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.clients.map(client => {
            // Status Logic
            const isOnline = this.onlineStatusMap[client.id] === 'online';
            const isDeleted = (client.status || '').toLowerCase() === 'deleted';
            const isSuspended = (client.status || '').toLowerCase() === 'suspended';

            let statusClass = isOnline ? 'online' : 'offline';
            let statusLabel = isOnline ? 'Online' : 'Offline';

            if (isDeleted) {
                statusClass = 'suspended'; // Using suspended color (red/orange) or we could add a new one
                statusLabel = 'Eliminado (Archivado)';
            } else if (isSuspended) {
                statusClass = 'suspended';
                statusLabel = 'Suspendido';
            }

            // Avatar Initials
            const names = (client.legal_name || '?').split(' ');
            const initials = (names[0][0] + (names.length > 1 ? names[1][0] : '')).toUpperCase();

            return `
             <tr data-client-id="${client.id}">
                <td><input type="checkbox" class="client-checkbox" value="${client.id}" onclick="app.modules.clients.updateSelection()"></td>
                <td><span class="client-code">${client.id}</span></td>
                <td>
                    <div class="client-name-cell">
                        <div class="client-avatar">
                            <i class="fas fa-user-circle"></i>
                        </div>
                        <div class="client-info">
                            <span class="client-real-name">${client.legal_name}</span>
                        </div>
                    </div>
                </td>
                <td>
                    <div class="client-info">
                        <span class="ip-badge">${client.ip_address || 'Sin IP'}</span>
                        <span class="credential-text">${client.mac_address || ''}</span>
                    </div>
                </td>
                <td>
                    <div class="client-info">
                        <strong>${client.router ? client.router.substring(0, 15) : '---'}</strong>
                        <span class="sub-detail">${client.zone || 'Sin Zona'}</span>
                    </div>
                </td>
                <td>
                    <div class="client-info">
                        ${(client.account_balance || 0) > 0 ?
                    `<span class="badge-status-table suspended">Pendiente</span>
                             <span class="debt-amount negative">$${client.account_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>` :
                    `<span class="badge-status-table active">Al día</span>
                             <span class="debt-amount positive">$${Math.abs(client.account_balance || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>`
                }
                    </div>
                </td>
                <td>
                    <div class="client-info" style="gap: 4px;">
                        <span class="plan-name">${this.formatPlanName(client.plan_name)}</span>
                        <span class="status-badge-table ${statusClass}">${statusLabel}</span>
                        ${!isOnline && client.last_seen ? `<span class="last-seen-text">${this.formatLastSeen(client.last_seen)}</span>` : ''}
                    </div>
                </td>
                <td>
                   <div class="traffic-mini">
                        <div class="traffic-row traffic-up">
                            <i class="fas fa-upload"></i> <span class="val-up">0 Kbps</span>
                        </div>
                        <div class="traffic-row traffic-down">
                            <i class="fas fa-download"></i> <span class="val-down">0 Kbps</span>
                        </div>
                   </div>
                </td>
                <td>
                    <div class="action-menu">
                        <button class="action-btn" onclick="app.modules.clients.showClientHistory(${client.id})" title="Historial de Pagos">
                            <i class="fas fa-history"></i>
                        </button>
                        
                        ${!isDeleted ? `
                        <button class="action-btn" onclick="app.modules.clients.editClient(${client.id})" title="Editar">
                            <i class="fas fa-edit"></i>
                        </button>
                        ${isSuspended ?
                        `<button class="action-btn" onclick="app.modules.clients.activateClient(${client.id})" title="Activar" style="color:#059669; border-color:#059669;">
                                <i class="fas fa-play"></i>
                             </button>` :
                        `<button class="action-btn" onclick="app.modules.clients.suspendClient(${client.id})" title="Suspender">
                                <i class="fas fa-pause"></i>
                             </button>`
                    }
                        <button class="action-btn" onclick="app.modules.clients.registerPayment(${client.id})" title="Pagar">
                            <i class="fas fa-dollar-sign"></i>
                        </button>
                        <button class="action-btn" onclick="app.modules.clients.showPromiseModal(${client.id})" title="Promesa de Pago">
                            <i class="fas fa-handshake"></i>
                        </button>
                        ` : `
                        <button class="action-btn" onclick="app.modules.clients.restoreClient(${client.id})" title="Restaurar" style="color:#3b82f6; border-color:#3b82f6;">
                            <i class="fas fa-undo"></i>
                        </button>
                        `}
                        
                        <button class="action-btn delete-btn" onclick="app.modules.clients.deleteClient(${client.id})" title="Eliminar">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `}).join('');
    }

    updateStaticStats() {
        // Use Global Dataset (allClients) for stats to keep them "Real" during search
        const dataset = this.allClients || this.clients || [];
        const isDeletedView = this.filterState.status === 'deleted';

        const active = dataset.filter(c => (c.status || '').toLowerCase() === 'active').length;
        const suspended = dataset.filter(c => (c.status || '').toLowerCase() === 'suspended').length;
        const deleted = dataset.filter(c => (c.status || '').toLowerCase() === 'deleted').length;

        // Operacional refers to anyone not deleted
        const totalOperational = active + suspended;

        // Online count depends on WebSocket map
        const online = dataset.filter(c => this.onlineStatusMap[c.id] === 'online').length;
        const offline = Math.max(0, totalOperational - online);

        // Update UI
        // If we are in Deleted view, 'Total' should probably show the count of deleted clients
        // but typically these pills show the "health" of the router.
        // Let's make it smarter:
        if (isDeletedView) {
            this.setSafeText('count-total', deleted);
            this.setSafeText('count-online', 0);
            this.setSafeText('count-offline', deleted);
            this.setSafeText('count-suspended', 0);
        } else {
            this.setSafeText('count-total', totalOperational);
            this.setSafeText('count-online', online);
            this.setSafeText('count-offline', offline);
            this.setSafeText('count-suspended', suspended);
        }
    }

    setSafeText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    setupWebsocketListeners() {
        if (app.socket && !this.socketInitialized) {
            app.socket.on('client_traffic', (data) => {
                // Remove global stats if present
                if (data['__stats__']) delete data['__stats__'];

                const count = Object.keys(data).length;
                if (count > 0) {
                    console.log(`📡 Recibido tráfico de ${count} clientes`);
                    this.updateTrafficUI(data);
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

        // Remove global stats if present
        if (data['__stats__']) delete data['__stats__'];

        // 1. Update internal state
        Object.keys(data).forEach(clientId => {
            this.onlineStatusMap[clientId] = data[clientId].status;
        });

        // 2. Update UI Rows
        Object.keys(data).forEach(clientId => {
            const row = document.querySelector(`tr[data-client-id="${clientId}"]`);
            if (row) {
                const info = data[clientId];
                const isOnline = info.status === 'online';

                // Update Status Badge
                const badge = row.querySelector('.status-badge-table');
                if (badge && !badge.classList.contains('suspended')) { // Don't override suspended status
                    badge.className = `status-badge-table ${isOnline ? 'online' : 'offline'}`;
                    badge.textContent = isOnline ? 'Online' : 'Offline';

                    // UX: Manage last-seen text
                    let lastSeenEl = row.querySelector('.last-seen-text');

                    if (isOnline) {
                        if (lastSeenEl) lastSeenEl.style.display = 'none';
                    } else if (data.last_seen) {
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
                            lastSeenEl.textContent = this.formatLastSeen(data.last_seen);
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
        this.clientToDelete = clientId;
        const client = this.clients.find(c => c.id === clientId);

        const modal = document.getElementById('delete-client-modal');
        const nameEl = document.getElementById('delete-client-name');

        if (modal && nameEl) {
            nameEl.textContent = client ? client.legal_name : 'Cliente Desconocido';
            modal.classList.add('active');
        } else {
            // Fallback if modal not present (should not happen)
            if (confirm('Eliminar cliente?')) this.confirmDelete('global');
        }
    }

    async confirmDelete(scope) {
        if (!this.clientToDelete) return;
        const clientId = this.clientToDelete;
        const modal = document.getElementById('delete-client-modal');

        try {
            // Close modal immediately
            if (modal) modal.classList.remove('active');

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

    async showClientHistory(clientId) {
        const client = this.clients.find(c => c.id === clientId);
        if (!client) return;

        if (window.app && window.app.modules && window.app.modules.payments && typeof window.app.modules.payments.showClientHistoryModal === 'function') {
            // If payments module is loaded and has the function
            app.modules.payments.showClientHistoryModal(clientId);
        } else {
            console.error('Payments module not loaded or function missing');
            if (window.toast) toast.error('El módulo de pagos no está listo. Intente recargar.');
            else alert('Error: Módulo de pagos no cargado.');
        }
    }

    // --- PROMISE MODAL ---

    async showPromiseModal(clientId) {
        const client = this.clients.find(c => c.id === clientId);
        if (!client) return;

        const modal = document.getElementById('payment-promise-modal');
        if (!modal) return;

        document.getElementById('promise-client-id').value = clientId;
        document.getElementById('promise-client-name').textContent = client.legal_name || 'Cliente';

        // Populate if exists
        const dateInput = document.getElementById('promise-date-input');
        if (client.promise_date) {
            dateInput.value = client.promise_date.split('T')[0];
        } else {
            // Default to next week? Or empty?
            const nextWeek = new Date();
            nextWeek.setDate(nextWeek.getDate() + 7);
            dateInput.value = nextWeek.toISOString().split('T')[0];
        }

        modal.classList.add('active');

        // Bind form submit once
        const form = document.getElementById('payment-promise-form');
        if (form) {
            form.onsubmit = (e) => {
                e.preventDefault();
                this.savePromise();
            };
        }
    }

    async savePromise() {
        const clientId = document.getElementById('promise-client-id').value;
        const date = document.getElementById('promise-date-input').value;

        if (!date) return toast.warning('Seleccione una fecha');

        try {
            if (window.app) app.showLoading(true);
            await this.api.post(`/api/clients/${clientId}/promise`, { date: date });
            if (window.app) app.showLoading(false);

            if (window.toast) toast.success('Promesa de pago guardada');
            document.getElementById('payment-promise-modal').classList.remove('active');
            this.loadClients(); // Reload to update UI
        } catch (e) {
            if (window.app) app.showLoading(false);
            console.error(e);
            if (window.toast) toast.error('Error al guardar promesa');
        }
    }

    async clearPromise() {
        const clientId = document.getElementById('promise-client-id').value;
        if (!confirm('¿Eliminar la promesa de pago?')) return;

        try {
            await this.api.delete(`/api/clients/${clientId}/promise`);
            if (window.toast) toast.success('Promesa eliminada');
            document.getElementById('payment-promise-modal').classList.remove('active');
            this.loadClients();
        } catch (e) {
            console.error(e);
            if (window.toast) toast.error('Error al eliminar promesa');
        }
    }

    async registerPayment(clientId) {
        const client = this.clients.find(c => c.id === clientId);
        if (!client) return;

        // Use the Premium Payment Modal from PaymentsModule
        if (app.modules.payments) {
            app.modules.payments.showNewPaymentModal(client);
        } else {
            console.error('Payments module not loaded');
            alert('Error: Módulo de pagos no cargado');
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

                // Pre-seleccionar el router actual si existe Y AUTO-ESCANEAR
                // Si no hay seleccionado, selecionar el primero por defecto para agilizar
                let targetRouterId = this.selectedRouter;

                if (!targetRouterId && routers.length > 0) {
                    targetRouterId = routers[0].id; // Default to first
                }

                if (targetRouterId) {
                    select.value = targetRouterId;

                    // Asegurar que el evento change o similar se procese si es necesario, 
                    // aunque scanRouter toma el valor directo del DOM

                    // Auto-scan inmediato con pequeño delay visual
                    setTimeout(() => {
                        this.scanRouter();
                    }, 100);
                }
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
            const isDiscovered = client.type === 'discovered';
            const rowClass = isDuplicate ? 'duplicate-row' : (isDiscovered ? 'needs-provision-row' : '');

            const checkbox = isDuplicate
                ? `<input type="checkbox" disabled>`
                : `<input type="checkbox" class="import-check" data-index="${index}" onchange="app.modules.clients.updateSelectedCount()">`;

            let statusBadge = isDuplicate
                ? `<span class="badge warning">Registrado</span>`
                : `<span class="badge success">Nuevo</span>`;

            if (isDiscovered) {
                statusBadge = `<span class="badge danger">Sin Simple Queue</span>`;
            }

            return `<tr class="${rowClass}">
                <td>${checkbox}</td>
                <td>
                    <div class="user-info-cell">
                        <strong>${client.username}</strong>
                        <small>${client.type.toUpperCase()}</small>
                    </div>
                </td>
                <td class="ip-cell">${client.ip_address}</td>
                <td>${client.profile}</td>
                <td>${statusBadge}</td>
            </tr>`;
        }).join('');

        const dupMsg = document.getElementById('scan-duplicates');
        if (dupMsg) dupMsg.style.display = hasDuplicates ? 'block' : 'none';

        // NUEVA FUNCIONALIDAD: Mostrar alerta si hay clientes sin Simple Queues
        const toolbar = document.getElementById('import-toolbar-top');
        if (needsProvisioning && discoveredCount > 0) {
            // Eliminar alerta anterior si existe
            const oldAlert = document.getElementById('auto-provision-alert');
            if (oldAlert) oldAlert.remove();

            const alertDiv = document.createElement('div');
            alertDiv.id = 'auto-provision-alert';
            alertDiv.className = 'premium-alert';

            alertDiv.innerHTML = `
                <div class="alert-icon">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="alert-content">
                    <h4>⚠️ <span class="alert-count-badge" onclick="app.modules.clients.filterClientsWithoutQueues()">${discoveredCount}</span> cliente${discoveredCount > 1 ? 's' : ''} sin Simple Queue</h4>
                    <p>
                        Se detectaron <span class="alert-count-badge" onclick="app.modules.clients.filterClientsWithoutQueues()">${discoveredCount}</span> clientes conectados pero sin Simple Queue configurada en el router <strong>${routerName}</strong>. 
                        Esto puede afectar el control de velocidad y la facturación.
                    </p>
                </div>
                <div class="alert-actions" style="display: flex; gap: 12px; align-items: center;">
                    <button class="btn-secondary" onclick="app.modules.clients.resetImport()">Cancelar</button>
                    <button class="btn-alert-sync" onclick="app.modules.clients.redirectToRouterSync(${routerId}, '${routerName}')">
                        <i class="fas fa-sync-alt"></i> Sincronizar Ahora
                    </button>
                    <button class="btn-primary" onclick="app.modules.clients.executeImport()">
                        Importar Seleccionados (<span id="selected-count-alert">0</span>)
                    </button>
                </div>
            `;

            // Insertar antes de la tabla y Ocultar el toolbar original
            const table = document.getElementById('import-preview-body').closest('table');
            if (table && table.parentNode) {
                table.parentNode.insertBefore(alertDiv, table);
                if (toolbar) toolbar.style.display = 'none';
            }
        } else {
            // Asegurar que el toolbar original sea visible si no hay alerta
            if (toolbar) toolbar.style.display = 'flex';
        }

        const selectAll = document.getElementById('select-all-import');
        if (selectAll) {
            selectAll.onclick = (e) => {
                const checks = document.querySelectorAll('.import-check:not(:disabled)');
                checks.forEach(c => c.checked = e.target.checked);
                this.updateSelectedCount();
            };
        }

        this.updateSelectedCount();
    }

    filterClientsWithoutQueues() {
        const rows = document.querySelectorAll('#import-preview-body tr');
        let filteredAny = false;

        rows.forEach(row => {
            const statusCell = row.querySelector('td:last-child');
            if (statusCell && (statusCell.textContent.includes('Sin Simple Queue') || row.classList.contains('needs-provision-row'))) {
                row.style.display = '';
                filteredAny = true;
            } else {
                row.style.display = 'none';
            }
        });

        if (filteredAny) {
            // Mostrar un botón pequeño para resetear el filtro
            let resetBtn = document.getElementById('reset-filter-btn');
            if (!resetBtn) {
                resetBtn = document.createElement('button');
                resetBtn.id = 'reset-filter-btn';
                resetBtn.className = 'btn-secondary btn-sm';
                resetBtn.style.marginLeft = '10px';
                resetBtn.innerHTML = '<i class="fas fa-times"></i> Mostrar todos';
                resetBtn.onclick = () => {
                    rows.forEach(r => r.style.display = '');
                    resetBtn.remove();
                };

                const toolbar = document.querySelector('.step-actions') || document.querySelector('.alert-actions');
                if (toolbar) toolbar.appendChild(resetBtn);
            }
        }
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
        const countSpan = document.getElementById('selected-count');
        const alertCountSpan = document.getElementById('selected-count-alert');

        if (countSpan) countSpan.textContent = count;
        if (alertCountSpan) alertCountSpan.textContent = count;
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
        // IDs correctos de los elementos span dentro de las pildoras
        const pills = [
            { id: 'count-total', status: 'all' },
            { id: 'count-online', status: 'online' },
            { id: 'count-offline', status: 'offline' },
            { id: 'count-suspended', status: 'suspended' }
        ];

        pills.forEach(p => {
            const pillEl = document.getElementById(p.id)?.parentElement;
            if (pillEl) {
                pillEl.style.cursor = 'pointer';
                pillEl.onclick = () => {
                    const statusSelect = document.getElementById('filter-status');
                    if (statusSelect) {
                        statusSelect.value = p.status;

                        // UX: Clean search when clicking a status pill to show "All Offline" etc.
                        const searchInput = document.getElementById('client-search');
                        if (searchInput) {
                            searchInput.value = '';
                            this.filterState.search = '';
                        }

                        this.applyFilters();
                    }
                };

                // Añadir tooltip sutil
                pillEl.setAttribute('title', `Filtrar por ${p.status.toUpperCase()}`);
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
