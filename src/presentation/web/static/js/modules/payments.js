/**
 * Payments Module - Frontend para gestión de pagos
 */
export class PaymentsModule {
    constructor(api, eventBus, viewManager, modalManager = null, statsService = null) {
        this.api = api;
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.modalManager = modalManager;
        this.statsService = statsService;

        this.rates = {
            'USD_COP': 4000,
            'USD_VES': 36.5,
            'COP_VES': 0.009
        };

        // Cargar tasas al iniciar
        this.loadExchangeRates();
        this.payments = [];
        this.statistics = null;
        console.log('✨ v2.0.4 - Financial Engine & Reports Active');
        this.filterState = {
            startDate: '',
            endDate: '',
            method: '',
            search: '',
            cycle: '2026-02'
        };
        this.searchTimeout = null;
        this.routers = []; // Centralized router cache

        this.sortStates = {
            payments: { column: 'id', direction: 'desc' },
            invoices: { column: 'id', direction: 'desc' },
            promises: { column: 'legal_name', direction: 'asc' },

            trash: { column: 'deleted_at', direction: 'desc' }
        };

        console.log('💰 Payments Module initialized');

        // Escuchar eventos del Payment Modal component
        this.setupModalListeners();

        // Mobile View Detection
        this.isMobile = window.innerWidth < 1024;
        window.addEventListener('resize', () => {
            const wasMobile = this.isMobile;
            this.isMobile = window.innerWidth < 1024;
            if (wasMobile !== this.isMobile) {
                console.log(`📱 Responsive Switch: ${wasMobile ? 'Mobile' : 'Desktop'} -> ${this.isMobile ? 'Mobile' : 'Desktop'}`);
                if (this.viewManager && (this.viewManager.currentSubView === 'payments-list' || this.viewManager.currentSubView === 'list')) {
                    this.renderPayments();
                }
            }
        });
    }

    setupModalListeners() {
        // Escuchar evento de pago guardado del componente
        document.addEventListener('modal:payment-modal:payment-saved', async (e) => {
            console.log('✅ Payment saved via component, refreshing list...', e.detail);
            // Recargar lista de pagos (loadPayments already calls loadStatistics)
            await this.loadPayments();
            // Mostrar toast de éxito
            if (window.toast) {
                window.toast.success('Pago registrado exitosamente');
            }
        });

        // Escuchar evento de solicitud de historial desde payment modal
        document.addEventListener('modal:payment-modal:show-client-history', async (e) => {
            console.log('📋 Show client history requested:', e.detail);
            const { client } = e.detail;

            // Abrir el modal de historial usando el manager
            if (this.modalManager) {
                await this.modalManager.open('history', { client });
            } else {
                console.warn('⚠️ ModalManager not available');
                if (window.toast) {
                    window.toast.error('Gestor de modales no disponible');
                }
            }
        });



        console.log('✅ Payment Modal event listeners configured');
    }

    async load() {
        console.log('💰 Loading Payments...');
        this.showView();
        this.startClock();
        this.initAutomationParams();

        // Load with current filters
        await Promise.all([
            this.loadPayments(),
            this.loadStatistics(),
            this.loadRouters() // Ensure routers are available for all views
        ]);

        // Initialize reports filters if we're in that view
        if (document.getElementById('reports-view')) {
            this.initReportsFilters();
        }

        // Initialize chart after loading data
        this.initChart();
    }

    startClock() {
        if (this.clockInterval) clearInterval(this.clockInterval);

        const update = () => {
            try {
                const now = new Date();
                const timeEl = document.getElementById('live-time');
                const dateEl = document.getElementById('live-date');

                if (timeEl) {
                    timeEl.textContent = now.toLocaleTimeString('es-CO', {
                        hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'
                    });
                }
                if (dateEl) {
                    dateEl.textContent = now.toLocaleDateString('es-CO', {
                        weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
                    });
                }
            } catch (e) {
                console.error('Error in clock update:', e);
            }
        };

        // Try immediately
        update();

        // Retry shortly after if elements possibly not loaded yet (100ms)
        setTimeout(update, 100);

        // Start interval
        this.clockInterval = setInterval(update, 1000);
    }

    showView() {
        // Delegate to NavigationModule's subview if possible, otherwise default to payments-list
        if (window.app && window.app.modules.navigation) {
            window.app.modules.navigation.navigateToSubView('finance-overview');
        } else {
            this.viewManager.showSubView('finance-overview');
        }
    }

    switchTab(tabName) {
        console.log('🔄 Switching Finance Tab to:', tabName);

        // Map legacy tab names to new sub-view names if needed
        const viewMap = {
            'overview': 'finance-overview',
            'list': 'payments-list',
            'invoices': 'invoices',
            'reports': 'reports',
            'promises': 'promises',

            'automation': 'automation',

            'trash': 'trash',
            'expenses': 'expenses',
            'sync': 'sync'
        };

        const targetView = viewMap[tabName] || tabName;

        if (window.app && window.app.modules.navigation) {
            window.app.modules.navigation.navigateToSubView(targetView);
        } else {
            this.viewManager.showSubView(targetView);
            // Trigger load if manual switch
            this.triggerViewLoad(tabName);
        }
    }

    switchFinanceTab(tabName) {
        console.log('📑 PaymentsModule: Switching Finance Sub-tab ->', tabName);

        try {
            // 1. Update Buttons (Find by onclick content)
            const buttons = document.querySelectorAll('.segment-btn');
            buttons.forEach(btn => {
                const onClick = btn.getAttribute('onclick');
                const isActive = onClick && onClick.includes(`'${tabName}'`);
                if (isActive) btn.classList.add('active');
                else btn.classList.remove('active');
            });

            // 2. Update Content Panels
            // Fix ID mismatch: HTML uses finance-list-tab, not finance-tab-list
            const targetId = `finance-${tabName}-tab`;
            const contents = document.querySelectorAll('.finance-tab');

            contents.forEach(content => {
                const isTarget = (content.id === targetId);
                content.classList.toggle('active', isTarget);
                content.style.display = isTarget ? 'block' : 'none';
            });

            // 3. Load specific data
            this.triggerViewLoad(tabName);

            console.log('✅ Tab switch completed successfully');
        } catch (err) {
            console.error('❌ Error switching finance tab:', err);
        }
    }

    /**
     * Called by NavigationModule to update view state
     */
    /**
     * Called by NavigationModule to update view state
     */
    handleNavigation(subView) {
        console.log(`🧭 PaymentsModule handling navigation to: ${subView}`);

        // Define valid sub-views for this module
        const validViews = [
            'finance-overview',
            'payments-list',
            'invoices',
            'reports',
            'promises',
            'expenses',
            'automation',
            'trash',
            'sync'
        ];

        if (validViews.includes(subView)) {
            // 1. Show the view
            if (this.viewManager) {
                this.viewManager.showSubView(subView);
            }

            // 2. Trigger data load
            // Normalize legacy names for data loading
            let loadKey = subView;
            if (subView === 'payments-list') loadKey = 'list';
            if (subView === 'finance-overview') loadKey = 'overview';

            this.triggerViewLoad(loadKey);
        } else {
            // Fallback for unknown views
            console.warn(`⚠️ Unknown sub-view in PaymentsModule: ${subView}`);
            if (this.viewManager) this.viewManager.showMainView('payments');
        }
    }

    /**
     * Handles internal tab switching within the Finance Overview view
     */
    switchOverviewTab(tabName) {
        console.log('📊 Switching Overview Tab to:', tabName);

        // 1. Update Buttons
        const buttons = document.querySelectorAll('.finance-tab-btn');
        buttons.forEach(btn => btn.classList.remove('active'));
        const activeBtn = document.getElementById(`tab-btn-${tabName}`);
        if (activeBtn) activeBtn.classList.add('active');

        // 2. Update Content Visibility
        const contents = document.querySelectorAll('.finance-tab-content');
        contents.forEach(content => {
            content.classList.remove('active');
            // Force hide to override any potential CSS conflicts
            content.style.display = 'none';
        });

        const targetId = `finance-tab-${tabName}`;
        const activeContent = document.getElementById(targetId);

        if (activeContent) {
            activeContent.classList.add('active');
            // Force show
            activeContent.style.display = 'block';
            console.log(`✅ Activated content: ${targetId}`);
        } else {
            console.error(`❌ Target content not found: ${targetId}`);
        }
    }

    initSync() {
        console.log('🔄 Initializing Sync Sub-module...');
        if (window.syncDashboard) {
            window.syncDashboard.init();
        } else {
            console.warn('⚠️ syncDashboard instance not found in window');
        }
    }

    triggerViewLoad(tabName) {
        if (tabName === 'overview' || tabName === 'finance-overview') this.loadStatistics();
        else if (tabName === 'list' || tabName === 'payments-list') this.loadPayments();
        else if (tabName === 'invoices') this.loadInvoices();
        else if (tabName === 'reports') {
            this.initReportsFilters();
            this.loadStatistics();
        }
        else if (tabName === 'expenses') this.loadExpenses();
        else if (tabName === 'promises') this.loadPromises();
        else if (tabName === 'batch') {
            this.loadRoutersForBatch(); // TODO: unify with this.routers
            this.loadBatchClients();
        } else if (tabName === 'automation') {
            this.loadRouters();
            this.loadExchangeRates(); // Recargar tasas globales al entrar
        }
        else if (tabName === 'revert') {
            this.loadRoutersForBatch();
            this.loadRevertiblePayments();
        } else if (tabName === 'trash') this.loadDeletedPayments();
        else if (tabName === 'sync') {
            if (window.syncDashboard) {
                window.syncDashboard.init();
            }
        }
    }

    async loadDeletedPayments() {
        try {
            const deleted = await this.api.get('/api/payments/deleted');
            this.deletedPayments = deleted || []; // Store for filtering
            this.selectedTrash = new Set(); // Reset selections
            this.updateTrashStatistics(this.deletedPayments);
            this.filterTrashLocal(); // Apply any active filters
        } catch (e) {
            console.error('Error loading deleted payments:', e);
            this.deletedPayments = [];
            this.updateTrashStatistics([]);
            if (window.toast) toast.error('Error al cargar papelera');
        }
    }

    updateTrashStatistics(deletedList) {
        const count = deletedList.length;
        const totalAmount = deletedList.reduce((sum, d) => sum + (d.amount || 0), 0);
        const lastDeleted = deletedList.length > 0 ? deletedList[0].deleted_at : null;

        // Update stats cards
        const countEl = document.getElementById('trash-stat-count');
        const amountEl = document.getElementById('trash-stat-amount');
        const lastEl = document.getElementById('trash-stat-last');
        const recoverableEl = document.getElementById('trash-stat-recoverable');

        if (countEl) countEl.textContent = count;
        if (amountEl) amountEl.textContent = `$${totalAmount.toLocaleString('en-US')}`;
        if (lastEl) {
            if (lastDeleted) {
                const date = new Date(lastDeleted);
                lastEl.textContent = date.toLocaleDateString('es-ES', {
                    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
                });
            } else {
                lastEl.textContent = '---';
            }
        }
        if (recoverableEl) recoverableEl.textContent = count; // All are recoverable for now
    }

    filterTrashLocal() {
        if (!this.deletedPayments) return;

        const search = document.getElementById('trash-search')?.value.toLowerCase() || '';
        const dateFrom = document.getElementById('trash-filter-date-from')?.value || '';
        const dateTo = document.getElementById('trash-filter-date-to')?.value || '';
        const amountMin = parseFloat(document.getElementById('trash-filter-amount-min')?.value) || 0;
        const amountMax = parseFloat(document.getElementById('trash-filter-amount-max')?.value) || Infinity;

        const filtered = this.deletedPayments.filter(d => {
            // Search filter
            const matchesSearch = !search ||
                (d.client_name && d.client_name.toLowerCase().includes(search)) ||
                (d.subscriber_code && d.subscriber_code.toLowerCase().includes(search)) ||
                (d.reference && d.reference.toLowerCase().includes(search));

            // Date range filter
            let matchesDate = true;
            if (dateFrom || dateTo) {
                const deletedDate = new Date(d.deleted_at).toISOString().split('T')[0];
                if (dateFrom && deletedDate < dateFrom) matchesDate = false;
                if (dateTo && deletedDate > dateTo) matchesDate = false;
            }

            // Amount filter
            const matchesAmount = (d.amount >= amountMin) && (d.amount <= amountMax);

            return matchesSearch && matchesDate && matchesAmount;
        });

        // 4. Sort
        const state = this.sortStates.trash;
        const col = state.column;
        const dir = state.direction === 'asc' ? 1 : -1;

        filtered.sort((a, b) => {
            let valA = a[col];
            let valB = b[col];

            if (col === 'amount') return (valA - valB) * dir;
            if (col === 'deleted_at' || col === 'payment_date') {
                return (new Date(valA || 0) - new Date(valB || 0)) * dir;
            }

            return (valA || '').toString().localeCompare((valB || '').toString()) * dir;
        });

        this.renderDeletedPayments(filtered);
    }

    clearTrashFilters() {
        const search = document.getElementById('trash-search');
        const dateFrom = document.getElementById('trash-filter-date-from');
        const dateTo = document.getElementById('trash-filter-date-to');
        const amountMin = document.getElementById('trash-filter-amount-min');
        const amountMax = document.getElementById('trash-filter-amount-max');

        if (search) search.value = '';
        if (dateFrom) dateFrom.value = '';
        if (dateTo) dateTo.value = '';
        if (amountMin) amountMin.value = '';
        if (amountMax) amountMax.value = '';

        this.filterTrashLocal();
    }

    renderDeletedPayments(deleted) {
        const tbody = document.getElementById('trash-table-body');
        if (!tbody) return;

        if (!deleted || deleted.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align:center; padding: 80px 30px;">
                        <div style="opacity: 0.3;">
                            <i class="fas fa-trash-alt" style="font-size: 4rem; color: #cbd5e1; margin-bottom: 20px; display: block;"></i>
                        </div>
                        <div style="font-size: 1.2rem; font-weight: 700; color: #475569; margin-bottom: 8px;">
                            Papelera Vacía
                        </div>
                        <div style="font-size: 0.9rem; color: #94a3b8;">
                            No hay pagos eliminados para mostrar
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        const totalAmount = deleted.reduce((sum, d) => sum + (d.amount || 0), 0);
        const totalClients = deleted.length;

        tbody.innerHTML = deleted.map(d => {
            const isSelected = this.selectedTrash && this.selectedTrash.has(d.id);
            const rowClass = isSelected ? 'premium-row selected' : 'premium-row';
            const paymentDate = d.payment_date ? new Date(d.payment_date).toLocaleDateString('es-ES', {
                day: '2-digit', month: 'short', year: 'numeric'
            }) : '---';

            return `
            <tr class="${rowClass}" style="${isSelected ? 'background: rgba(16, 185, 129, 0.05);' : ''}">
                <td style="text-align: center;">
                    <input type="checkbox" class="trash-checkbox" data-id="${d.id}" 
                        ${isSelected ? 'checked' : ''} 
                        onchange="app.modules.payments.toggleTrashSelection(${d.id})"
                        style="cursor: pointer; width: 18px; height: 18px;">
                </td>
                <td>
                    <div style="font-weight: 600; color: #1e293b;">${d.client_name || '---'}</div>
                    <div style="font-size: 0.8rem; color: #64748b;">${d.subscriber_code || '---'}</div>
                </td>
                <td>
                    <div style="font-family: 'JetBrains Mono', monospace; font-weight: 800; font-size: 1.1rem; color: #dc2626;">
                        $${(d.amount || 0).toLocaleString('en-US')}
                    </div>
                </td>
                <td>
                    <div style="font-size: 0.85rem; color: #475569;">
                        <i class="far fa-calendar-alt" style="margin-right: 5px; color: #94a3b8;"></i>
                        ${paymentDate}
                    </div>
                </td>
                <td>
                    <div style="font-size: 0.85rem; color: #1e293b; margin-bottom: 3px;">
                        ${new Date(d.deleted_at).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' })}
                    </div>
                    <div style="font-size: 0.75rem; color: #94a3b8;">
                        el <strong style="color: #64748b;">${new Date(d.deleted_at).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}</strong>
                    </div>
                </td>
                <td>
                    <div style="font-style: italic; color: #64748b; font-size: 0.82rem; line-height: 1.4;">
                        ${d.reason || 'Sin motivo especificado'}
                    </div>
                </td>
                <td style="text-align: right;">
                    <div style="display: flex; gap: 8px; justify-content: flex-end; align-items: center;">
                        <button class="btn-premium" 
                            onclick="app.modules.payments.restorePayment(${d.id})" 
                            style="padding: 6px 12px; font-size: 0.75rem; background: #10b981; border-color: #10b981;">
                            <i class="fas fa-undo"></i> Restaurar
                        </button>
                        <button class="delete-btn-premium" 
                            onclick="app.modules.payments.deleteTrashPermanently(${d.id})" 
                            title="Eliminar permanentemente"
                            style="width: 32px; height: 32px; border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.1); background: rgba(239, 68, 68, 0.05); color: #ef4444; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; box-shadow: 0 2px 4px rgba(239, 68, 68, 0.05);">
                            <i class="fas fa-trash-alt" style="font-size: 0.85rem;"></i>
                        </button>
                    </div>
                </td>
            </tr>
            `;
        }).join('');

        // Append Totals Row
        const totalsRow = document.createElement('tr');
        totalsRow.style.background = '#f8fafc';
        totalsRow.style.fontWeight = '900';
        totalsRow.style.borderTop = '2px solid #e2e8f0';
        totalsRow.innerHTML = `
            <td></td>
            <td style="color: #1e293b; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em;">TOTAL GENERAL</td>
            <td style="font-family: 'JetBrains Mono', monospace; color: #dc2626; font-size: 1.1rem;">$${totalAmount.toLocaleString('en-US')}</td>
            <td></td>
            <td></td>
            <td colspan="2" style="text-align: right; color: #64748b; font-size: 0.85rem;">
                ${totalClients} pagos listados
            </td>
        `;
        tbody.appendChild(totalsRow);

        // Update checkbox header
        this.updateTrashSelectionUI();
    }

    toggleTrashSelection(id) {
        if (!this.selectedTrash) this.selectedTrash = new Set();

        if (this.selectedTrash.has(id)) {
            this.selectedTrash.delete(id);
        } else {
            this.selectedTrash.add(id);
        }

        this.updateTrashSelectionUI();
    }

    toggleSelectAllTrash() {
        if (!this.selectedTrash) this.selectedTrash = new Set();

        const checkboxes = document.querySelectorAll('.trash-checkbox');
        const selectAllCheckbox = document.getElementById('trash-select-all');

        if (selectAllCheckbox && selectAllCheckbox.checked) {
            // Select all visible
            checkboxes.forEach(cb => {
                const id = parseInt(cb.dataset.id);
                this.selectedTrash.add(id);
                cb.checked = true;
            });
        } else {
            // Deselect all
            this.selectedTrash.clear();
            checkboxes.forEach(cb => cb.checked = false);
        }

        this.updateTrashSelectionUI();
    }

    updateTrashSelectionUI() {
        const count = this.selectedTrash ? this.selectedTrash.size : 0;
        const batchBar = document.getElementById('trash-batch-actions');
        const countEl = document.getElementById('trash-selected-count');
        const selectAllCheckbox = document.getElementById('trash-select-all');

        if (countEl) countEl.textContent = count;

        if (batchBar) {
            batchBar.style.display = count > 0 ? 'block' : 'none';
        }

        // Update select-all checkbox state
        if (selectAllCheckbox) {
            const visibleCheckboxes = document.querySelectorAll('.trash-checkbox');
            const allChecked = visibleCheckboxes.length > 0 &&
                Array.from(visibleCheckboxes).every(cb => cb.checked);
            selectAllCheckbox.checked = allChecked;
        }
    }

    clearTrashSelection() {
        if (this.selectedTrash) this.selectedTrash.clear();

        const checkboxes = document.querySelectorAll('.trash-checkbox');
        checkboxes.forEach(cb => cb.checked = false);

        const selectAllCheckbox = document.getElementById('trash-select-all');
        if (selectAllCheckbox) selectAllCheckbox.checked = false;

        this.updateTrashSelectionUI();
    }

    async batchRestoreTrash() {
        if (!this.selectedTrash || this.selectedTrash.size === 0) {
            if (window.toast) toast.warning('No hay pagos seleccionados');
            return;
        }

        const count = this.selectedTrash.size;
        const confirmMsg = `¿Desea restaurar ${count} pago${count > 1 ? 's' : ''}? Se re-aplicarán a los balances de los clientes.`;

        if (!confirm(confirmMsg)) return;

        try {
            if (window.app) app.showLoading(true);

            const restorePromises = Array.from(this.selectedTrash).map(id =>
                this.api.post(`/api/payments/deleted/${id}/restore`, {})
            );

            await Promise.all(restorePromises);

            if (window.app) app.showLoading(false);
            if (window.toast) toast.success(`${count} pago${count > 1 ? 's' : ''} restaurado${count > 1 ? 's' : ''} exitosamente`);

            this.selectedTrash.clear();
            this.loadDeletedPayments();
            this.loadPayments();
            this.loadStatistics();
        } catch (e) {
            if (window.app) app.showLoading(false);
            console.error(e);
            if (window.toast) toast.error('Error al restaurar algunos pagos');
            // Reload to show current state
            this.loadDeletedPayments();
        }
    }

    async restorePayment(deletedId) {
        if (!confirm('¿Deseas restaurar este pago? Se re-aplicará al balance del cliente.')) return;

        try {
            if (window.app) app.showLoading(true);
            await this.api.post(`/api/payments/deleted/${deletedId}/restore`, {});

            if (window.toast) toast.success('Pago restaurado exitosamente');
            this.loadDeletedPayments();
            this.loadPayments();
            this.loadStatistics();
        } catch (e) {
            console.error(e);
            const errText = e.data && e.data.error ? e.data.error : e.message;
            if (window.toast) toast.error('Error al restaurar: ' + errText);
        } finally {
            if (window.app) app.showLoading(false);
        }
    }

    async emptyTrash() {
        if (!confirm('¿Deseas vaciar COMPLETAMENTE la papelera? Esta acción es irreversible.')) return;

        try {
            if (window.app) app.showLoading(true);
            await this.api.delete('/api/payments/deleted/clear');

            if (window.toast) toast.success('Papelera vaciada correctamente');
            this.loadDeletedPayments();
        } catch (e) {
            console.error(e);
            if (window.toast) toast.error('Error al vaciar papelera');
        } finally {
            if (window.app) app.showLoading(false);
        }
    }

    async deleteTrashPermanently(id) {
        if (!confirm('¿Deseas eliminar este registro de forma permanente?')) return;

        try {
            if (window.app) app.showLoading(true);
            await this.api.delete(`/api/payments/deleted/${id}`);

            if (window.toast) toast.success('Registro eliminado permanentemente');
            this.loadDeletedPayments();
        } catch (e) {
            console.error(e);
            if (window.toast) toast.error('Error al eliminar registro');
        } finally {
            if (window.app) app.showLoading(false);
        }
    }

    async batchDeleteTrashPermanently() {
        if (!this.selectedTrash || this.selectedTrash.size === 0) return;

        const count = this.selectedTrash.size;
        if (!confirm(`¿Deseas eliminar permanentemente los ${count} registros seleccionados? Esta acción no se puede deshacer.`)) return;

        try {
            if (window.app) app.showLoading(true);
            await this.api.post('/api/payments/deleted/delete-batch', {
                deleted_ids: Array.from(this.selectedTrash)
            });

            if (window.toast) toast.success(`${count} registros eliminados permanentemente`);
            this.selectedTrash.clear();
            this.loadDeletedPayments();
        } catch (e) {
            console.error(e);
            if (window.toast) toast.error('Error al eliminar registros masivamente');
        } finally {
            if (window.app) app.showLoading(false);
        }
    }

    applyFilters() {
        const start = document.getElementById('filter-date-start');
        const end = document.getElementById('filter-date-end');
        const method = document.getElementById('filter-method');
        const searchQuick = document.getElementById('payment-search-quick');
        const searchReport = document.getElementById('payment-search');

        this.filterState.startDate = start ? start.value : '';
        this.filterState.endDate = end ? end.value : '';
        this.filterState.method = method ? method.value : '';

        if (searchQuick && searchQuick.offsetParent !== null) {
            this.filterState.search = searchQuick.value;
        } else if (searchReport) {
            this.filterState.search = searchReport.value;
        }

        if (document.getElementById('finance-reports-tab') && document.getElementById('finance-reports-tab').style.display !== 'none') {
            this.loadStatistics();
        } else if (document.getElementById('finance-list-tab') && document.getElementById('finance-list-tab').style.display !== 'none') {
            this.loadPayments();
        }
    }

    onSearchInput(value) {
        this.filterState.search = value;
        if (this.searchTimeout) clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
            this.loadPayments(); // Use loadPayments directly to include filters
        }, 500);
    }

    onCycleFilterChange(value) {
        this.filterState.cycle = value;
        // Limpiar fechas manuales al cambiar el ciclo predefinido para evitar conflictos
        const start = document.getElementById('payment-date-start');
        const end = document.getElementById('payment-date-end');
        if (start) start.value = '';
        if (end) end.value = '';
        this.filterState.startDate = '';
        this.filterState.endDate = '';

        this.loadPayments();
    }

    onDateFilterChange() {
        const start = document.getElementById('payment-date-start')?.value;
        const end = document.getElementById('payment-date-end')?.value;

        this.filterState.startDate = start || '';
        this.filterState.endDate = end || '';

        // Si hay una fecha manual, ponemos el ciclo en 'all' visualmente
        if (start || end) {
            const cycleFilter = document.getElementById('payment-cycle-filter');
            if (cycleFilter) {
                cycleFilter.value = 'all';
                this.filterState.cycle = 'all';
            }
        }

        this.loadPayments();
    }

    getCycleRange(cycle) {
        if (cycle === 'all') return { start: null, end: null };

        // Handle YYYY-MM format
        const [year, month] = cycle.split('-').map(Number);

        // Start of the month
        const start = new Date(year, month - 1, 1);
        // End of the month
        const end = new Date(year, month, 0); // Day 0 of next month is last day of current

        return {
            start: start.toISOString().split('T')[0],
            end: end.toISOString().split('T')[0]
        };
    }

    async loadPayments() {
        console.log('🔄 loadPayments() triggered. Current filterState:', this.filterState);
        try {
            const params = new URLSearchParams({ limit: 1000 });

            // Prioridad: Fechas manuales > Ciclo
            if (this.filterState.startDate || this.filterState.endDate) {
                console.log('📅 Using Manual Date Range:', this.filterState.startDate, 'to', this.filterState.endDate);
                if (this.filterState.startDate) params.append('start_date', this.filterState.startDate);
                if (this.filterState.endDate) params.append('end_date', this.filterState.endDate);
            }
            else if (this.filterState.cycle && this.filterState.cycle !== 'all') {
                console.log('🔄 Using Cycle Filter:', this.filterState.cycle);
                const range = this.getCycleRange(this.filterState.cycle);
                if (range.start) params.append('start_date', range.start);
                if (range.end) params.append('end_date', range.end);
            }

            if (this.filterState.method) params.append('method', this.filterState.method);
            if (this.filterState.search) params.append('search', this.filterState.search);

            const url = `/api/payments?${params.toString()}`;
            console.log(`📡 Fetching payments from: ${url}`);

            const response = await this.api.get(url);
            console.log('📦 API Response received:', Array.isArray(response) ? `Array(${response.length})` : response);

            this.payments = Array.isArray(response) ? response : (response.data || []);
            console.log(`✅ ${this.payments.length} payments loaded into state.`);

            this.renderPayments();
            await this.loadStatistics(); // Refresh stats too
        } catch (error) {
            console.error('❌ Error loading payments:', error);
            this.payments = [];
            this.renderPayments();
        }
    }

    async loadInvoices() {
        try {
            const params = new URLSearchParams({ limit: 1000 });
            const statusInput = document.getElementById('invoice-filter-status');
            const searchInput = document.getElementById('invoice-search');
            const monthInput = document.getElementById('invoice-filter-month');

            if (statusInput && statusInput.value) params.append('status', statusInput.value);
            if (searchInput && searchInput.value) params.append('search', searchInput.value);
            if (monthInput && monthInput.value) params.append('month', monthInput.value);

            this.invoices = await this.api.get(`/api/billing/invoices?${params.toString()}`);
            this.renderInvoices();
        } catch (error) {
            console.error('❌ Error loading invoices:', error);
            this.invoices = [];
            this.renderInvoices();
        }
    }

    sortBy(tab, column) {
        const state = this.sortStates[tab];
        if (state.column === column) {
            state.direction = state.direction === 'asc' ? 'desc' : 'asc';
        } else {
            state.column = column;
            state.direction = 'asc';
        }

        if (tab === 'payments') this.renderPayments();
        else if (tab === 'invoices') this.renderInvoices();
        else if (tab === 'promises') this.renderPromises();
        else if (tab === 'trash') this.filterTrashLocal();
        else if (tab === 'batch') this.renderBatchClients();

        this.updateSortIcons(tab);
    }

    updateSortIcons(tab) {
        const selectors = {
            payments: '#payments-list table',
            invoices: '#invoices table',
            promises: '#promises table',
            trash: '#trash table',
            batch: '#batch table'
        };
        const table = document.querySelector(selectors[tab]);
        if (!table) return;

        const state = this.sortStates[tab];
        const headers = table.querySelectorAll('th.sortable');
        headers.forEach(th => {
            const icon = th.querySelector('i');
            th.classList.remove('active-sort');
            if (icon) icon.className = 'fas fa-sort';

            const onClickAttr = th.getAttribute('onclick');
            if (onClickAttr && onClickAttr.includes(`'${state.column}'`)) {
                th.classList.add('active-sort');
                if (icon) {
                    icon.className = state.direction === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down';
                }
            }
        });
    }

    renderInvoices() {
        const tbody = document.getElementById('invoices-table-body');
        if (!tbody) return;

        if (!this.invoices || this.invoices.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align:center; padding: 60px; color: #94a3b8;">
                        <i class="fas fa-file-invoice" style="font-size: 3rem; opacity:0.2; margin-bottom:15px; display:block;"></i>
                        <p style="font-weight:600; font-size:1.1rem;">No se encontraron facturas</p>
                        <p style="font-size:0.85rem; opacity:0.7;">Intente ajustar los filtros de búsqueda</p>
                    </td>
                </tr>
            `;
            return;
        }

        const state = this.sortStates.invoices;
        const col = state.column;
        const dir = state.direction === 'asc' ? 1 : -1;

        const sorted = [...this.invoices].sort((a, b) => {
            let valA = a[col];
            let valB = b[col];

            if (col === 'total_amount') return (valA - valB) * dir;
            if (col === 'issue_date' || col === 'due_date') {
                return (new Date(valA || 0) - new Date(valB || 0)) * dir;
            }

            return (valA || '').toString().localeCompare((valB || '').toString()) * dir;
        });

        tbody.innerHTML = sorted.map(inv => {
            let statusText = 'Pendiente';
            let statusClass = 'warning';
            let statusIcon = 'fa-clock';

            if (inv.status === 'paid') {
                statusText = 'Pagada'; statusClass = 'success'; statusIcon = 'fa-check-circle';
            }
            else if (inv.status === 'overdue') {
                statusText = 'Vencida'; statusClass = 'danger'; statusIcon = 'fa-exclamation-triangle';
            }
            else if (inv.status === 'cancelled') {
                statusText = 'Anulada'; statusClass = 'secondary'; statusIcon = 'fa-times-circle';
            }

            const initial = (inv.client_name || 'C').charAt(0).toUpperCase();

            return `
            <tr class="premium-row">
                <td class="id-cell">
                    <span class="id-badge">#${inv.id}</span>
                </td>
                <td class="client-cell-premium">
                    <div class="avatar-mini">${initial}</div>
                    <div class="client-info-stack">
                        <span class="client-name-text">${inv.client_name || 'Cliente'}</span>
                        <span class="client-sub-text">${inv.subscriber_code || '---'}</span>
                    </div>
                </td>
                <td class="date-cell">
                    <div class="date-wrapper">
                        <i class="far fa-calendar-alt"></i>
                        <span>${new Date(inv.issue_date).toLocaleDateString()}</span>
                    </div>
                </td>
                <td class="date-cell">
                    <div class="date-wrapper due">
                        <i class="fas fa-history"></i>
                        <span>${new Date(inv.due_date).toLocaleDateString()}</span>
                    </div>
                </td>
                <td class="amount-cell-premium">
                    <div class="amount-main">$${(inv.total_amount || 0).toLocaleString('en-US')}</div>
                    <div class="amount-sub">COP</div>
                </td>
                <td>
                    <span class="premium-status-badge ${statusClass}">
                        <i class="fas ${statusIcon}"></i>
                        ${statusText}
                    </span>
                </td>
                <td style="text-align: right;">
                    <div class="action-flex-right">
                        <button class="action-btn-mini" onclick="window.open('/api/billing/invoices/${inv.id}/print', '_blank')" title="Imprimir PDF">
                            <i class="fas fa-print"></i>
                        </button>
                         ${inv.status === 'unpaid' ? `
                        <button class="action-btn-mini success" onclick="app.modules.payments.showNewPaymentModal(${inv.client_id})" title="Pagar">
                            <i class="fas fa-dollar-sign"></i>
                        </button>` : ''}
                    </div>
                </td>
            </tr>
            `;
        }).join('');
    }

    async generateMonthlyInvoices() {
        const confirmMsg = "Esto generará facturas para todos los clientes activos del mes actual. ¿Continuar?";
        if (!confirm(confirmMsg)) return;

        try {
            if (window.app && window.app.showLoading) window.app.showLoading(true);
            const res = await this.api.post('/api/billing/generate', {});

            if (window.toast) window.toast.show(`Generadas: ${res.details.created}, Saltadas: ${res.details.skipped}`, 'success');
            this.loadInvoices();
        } catch (e) {
            console.error(e);
            if (window.toast) window.toast.show('Error generando facturas', 'error');
        } finally {
            if (window.app && window.app.showLoading) window.app.showLoading(false);
        }
    }

    async loadStatistics() {
        if (!this.statsService) return;
        this.startClock();

        // Initialize filters if we are in Reports view
        if (document.getElementById('reports-view')) {
            this.initReportsFilters();
        }

        const stats = await this.statsService.loadStatistics(this.filterState);
        this.statistics = stats;
        if (stats) {
            this.statsService.renderStatistics(stats, this.filterState);
        }
    }

    renderStatistics() {
        if (!this.statsService || !this.statistics) return;
        this.statsService.renderStatistics(this.statistics, this.filterState);
    }

    async generateReport() {
        const { startDate, endDate, method } = this.filterState;
        if (!startDate || !endDate) {
            if (window.toast) toast.warning('Seleccione un rango de fechas para el reporte');
            return;
        }

        if (window.toast) toast.info('Generando descarga de pagos...');

        const params = new URLSearchParams({
            start_date: startDate,
            end_date: endDate,
            method: method
        });

        window.open(`/api/payments/export?${params.toString()}`, '_blank');

        try {
            await this.loadStatistics();
        } catch (e) { console.error(e); }
    }

    async exportDebtors() {
        if (this.statsService) {
            if (window.toast) toast.info('Generando reporte de morosos...');
            this.statsService.exportReport({}, 'csv', 'debtors');
        }
    }

    openReportModal() {
        if (this.modalManager) {
            // FIX: Move modal to body to prevent stacking context issues with Main vs Overlay
            const modalEl = document.getElementById('modal-report-config');
            if (modalEl && modalEl.parentNode !== document.body) {
                document.body.appendChild(modalEl);
                console.log('🏗️ Moved report modal to document.body for Z-Index safety');
            }

            this.modalManager.open('report');

            // Force bind event listener after modal opens
            setTimeout(() => {
                const btnSubmitReport = document.getElementById('btn-submit-report');
                if (btnSubmitReport) {
                    console.log('✅ Re-binding report submit button (CLONE + ONCLICK)');

                    // Nuke existing listeners by cloning
                    const newBtn = btnSubmitReport.cloneNode(true);
                    btnSubmitReport.parentNode.replaceChild(newBtn, btnSubmitReport);

                    // Force styles
                    // Force styles
                    newBtn.style.position = 'relative';
                    newBtn.style.zIndex = '10000';
                    newBtn.style.pointerEvents = 'auto';
                    // Clean debug visual styles
                    newBtn.style.border = '';
                    newBtn.style.boxShadow = '';

                    // Direct binding
                    newBtn.onclick = (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log('🖱️ Report Submit Button Clicked (FINAL FIX)');

                        // Visual confirmation for user
                        if (window.app && window.app.components && window.app.components.toast) {
                            window.app.components.toast.success('Procesando solicitud...', 'Sistema');
                        }

                        this.submitReportExport();
                    };
                } else {
                    console.error('❌ Report submit button not found in DOM');
                }
            }, 100);

            // DIAGNOSTIC - UNFILTERED CAPTURE PHASE
            const debugClick = (e) => {
                console.log('🕵️ GLOBAL CLICK (CAPTURE):', e.target.tagName, e.target.className, e.target.id);
            };
            document.removeEventListener('click', debugClick, true);
            document.addEventListener('click', debugClick, true); // true = Capture phase

            // Inicializar fechas por defecto (mes actual)
            const now = new Date();
            const start = new Date(now.getFullYear(), now.getMonth(), 1);

            const startEl = document.getElementById('report-date-start');
            const endEl = document.getElementById('report-date-end');
            if (startEl) startEl.value = start.toISOString().split('T')[0];
            if (endEl) endEl.value = now.toISOString().split('T')[0];
        } else {
            const modal = document.getElementById('modal-report-config');
            if (modal) modal.classList.add('active');
        }
    }

    closeReportModal() {
        if (this.modalManager) {
            this.modalManager.close('report');
        } else {
            const modal = document.getElementById('modal-report-config');
            if (modal) modal.classList.remove('active');
        }
    }

    onReportTypeChange() {
        const type = document.getElementById('report-type').value;
        const dateRangeGroup = document.getElementById('report-date-range-group');
        const methodGroup = document.getElementById('report-method').closest('.form-group');
        const formatPdf = document.querySelector('input[name="report-format"][value="pdf"]').closest('.format-option-ultra');

        if (type === 'debtors') {
            dateRangeGroup.style.display = 'none';
            methodGroup.style.display = 'none';
            formatPdf.style.display = 'none'; // Morosos por ahora solo CSV/Excel por simplificación de ReportService
        } else if (type === 'today') {
            dateRangeGroup.style.display = 'none';
            methodGroup.style.display = 'block';
            formatPdf.style.display = 'block';
        } else {
            dateRangeGroup.style.display = 'block';
            methodGroup.style.display = 'block';
            formatPdf.style.display = 'block';
        }
    }

    async submitReportExport() {
        if (!this.statsService) return;

        const type = document.getElementById('report-type').value;
        const startDate = document.getElementById('report-date-start').value;
        const endDate = document.getElementById('report-date-end').value;
        const method = document.getElementById('report-method').value;
        const formatInput = document.querySelector('input[name="report-format"]:checked');
        const format = formatInput ? formatInput.value : 'csv';

        if ((type === 'payments' || type === 'routers') && (!startDate || !endDate)) {
            if (window.toast) toast.warning('Seleccione el rango de fechas');
            return;
        }

        const reportFilter = {
            startDate: type === 'today' ? new Date().toISOString().split('T')[0] : startDate,
            endDate: type === 'today' ? new Date().toISOString().split('T')[0] : endDate,
            method: method
        };

        if (window.toast) toast.info(`Generando reporte ${format.toUpperCase()}...`);
        this.statsService.exportReport(reportFilter, format, type);
        this.closeReportModal();
    }

    initChart() {
        if (this.statsService && this.statistics) {
            this.statsService.initCharts(this.statistics);
        }
    }





    async showClientHistory(clientId) {
        try {
            // we need the client object for the modal header
            const client = await this.api.get(`/api/clients/${clientId}`);

            if (this.modalManager) {
                this.modalManager.open('history', { client });
            } else {
                console.error('ModalManager not available for History Modal');
            }
        } catch (error) {
            console.error('Error opening history modal:', error);
            if (window.toast) toast.error('Error al obtener datos del cliente');
        }
    }



    async showMonthDetailModal(monthData) {
        if (this.modalManager) {
            this.modalManager.open('month-detail', { monthData });
        } else {
            console.error('ModalManager not available for Month Detail Modal');
        }
    }

    /**
     * Show revert payment modal with cycle-aware confirmation
     */
    async showRevertPaymentModal(paymentId, clientId, paymentDate) {
        try {
            const paymentDateTime = new Date(paymentDate);
            const now = new Date();
            const daysDiff = Math.floor((now - paymentDateTime) / (1000 * 60 * 60 * 24));
            const isCurrentCycle = daysDiff <= 30;

            let confirmMessage = '';
            let requiresStrongConfirm = false;

            if (isCurrentCycle) {
                confirmMessage = `⚠️ REVERTIR PAGO DEL CICLO ACTUAL\n\n` +
                    `Esta acción:\n` +
                    `✓ Restaurará la deuda del cliente\n` +
                    `✓ Suspenderá el servicio inmediatamente\n` +
                    `✓ Bloqueará acceso en MikroTik\n` +
                    `✓ Ajustará la contabilidad\n\n` +
                    `¿Confirmar reversión?`;
            } else {
                confirmMessage = `🚨 ADVERTENCIA: PAGO HISTÓRICO (${daysDiff} días)\n\n` +
                    `Esta reversión afectará la contabilidad de ciclos pasados.\n\n` +
                    `⚠️ IMPACTOS:\n` +
                    `• Modificará reportes históricos\n` +
                    `• Puede descuadrar cierres contables anteriores\n` +
                    `• Solo ajusta contabilidad (NO suspende servicio actual)\n\n` +
                    `Para confirmar, escribe "CONFIRMAR" en el siguiente prompt:`;
                requiresStrongConfirm = true;
            }

            const userConfirmed = confirm(confirmMessage);
            if (!userConfirmed) return;

            if (requiresStrongConfirm) {
                const confirmText = prompt('Escribe "CONFIRMAR" para proceder:');
                if (confirmText !== 'CONFIRMAR') {
                    if (window.toast) toast.warning('Reversión cancelada');
                    return;
                }

                const reason = prompt('Motivo obligatorio de reversión histórica:');
                if (!reason || reason.trim().length < 10) {
                    if (window.toast) toast.error('Debe proporcionar un motivo detallado (mínimo 10 caracteres)');
                    return;
                }

                await this.executePaymentReversion(paymentId, clientId, reason, isCurrentCycle);
            } else {
                const reason = prompt('Motivo de reversión (opcional):') || 'Reversión de pago';
                await this.executePaymentReversion(paymentId, clientId, reason, isCurrentCycle);
            }

        } catch (error) {
            console.error('Error showing revert modal:', error);
            if (window.toast) toast.error('Error al preparar reversión');
        }
    }

    async executePaymentReversion(paymentId, clientId, reason, isCurrentCycle) {
        try {
            if (window.app) app.showLoading(true);

            const response = await this.api.post(`/api/payments/${paymentId}/revert`, {
                reason: reason,
                is_current_cycle: isCurrentCycle
            });

            if (window.toast) {
                toast.success(response.message || 'Pago revertido exitosamente');
            }

            // Recargar lista de pagos
            await this.loadPayments();

            if (this.modalManager) {
                const historyModal = this.modalManager.modals.get('history');
                if (historyModal && historyModal.currentClientId === clientId) {
                    await historyModal.loadHistory();
                }
            }
        } catch (error) {
            console.error('Error reverting payment:', error);
            const errorMsg = error.data?.error || error.message || 'Error al revertir pago';
            if (window.toast) toast.error(errorMsg);
        } finally {
            if (window.app) app.showLoading(false);
        }
    }

    renderPaymentsCards(payments) {
        const grid = document.getElementById('payments-cards-grid');
        if (!grid) return;

        grid.innerHTML = payments.map((payment, index) => {
            const sequentialNumber = index + 1;
            const methodMap = {
                'cash': 'EFECTIVO',
                'transfer': 'TRANSFERENCIA',
                'card': 'TARJETA/DIGITAL',
                'pago_movil': 'PAGO MÓVIL',
                'zelle': 'ZELLE/INTL'
            };
            const statusMap = {
                'paid': 'PAGADO',
                'completed': 'PAGADO',
                'verified': 'PAGADO',
                'verificated': 'PAGADO',
                'pending': 'PENDIENTE',
                'voided': 'ANULADO'
            };

            const methodName = methodMap[payment.payment_method?.toLowerCase()] || payment.payment_method?.toUpperCase() || 'EFECTIVO';
            const statusName = statusMap[payment.status?.toLowerCase()] || payment.status?.toUpperCase() || 'PAGADO';
            const statusClass = (payment.status === 'paid' || payment.status === 'completed' || payment.status === 'verified' || payment.status === 'verificated') ? 'success' : 'warning';
            const initial = (payment.client_name || 'C').charAt(0).toUpperCase();

            return `
            <div class="plan-card-mobile payment-card-premium">
                <div class="card-mobile-header">
                    <div class="card-mobile-client-info">
                        <div class="avatar-mini" style="width:40px; height:40px; background:linear-gradient(135deg, #1e293b, #0f172a); color:#38bdf8; display:flex; align-items:center; justify-content:center; border-radius:10px; font-weight:800; font-size:1rem;">#${sequentialNumber}</div>
                        <div class="card-mobile-name-group">
                            <span class="card-mobile-name">${payment.client_name || 'Desconocido'}</span>
                            <span class="card-mobile-code">${payment.subscriber_code || '---'}</span>
                        </div>
                    </div>
                    <span class="premium-status-badge ${statusClass}" style="font-size:0.6rem;">
                        ${statusName}
                    </span>
                </div>
                
                <div class="card-mobile-body">
                    <div class="card-mobile-data-item">
                        <span class="data-item-label">Monto Pagado</span>
                        <span class="data-item-value" style="font-weight:800; color:#0f172a; font-size:1.1rem;">$${(payment.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div class="card-mobile-data-item">
                        <span class="data-item-label">Fecha</span>
                        <span class="data-item-value">${new Date(payment.payment_date).toLocaleDateString()} ${new Date(payment.payment_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <div class="card-mobile-data-item">
                        <span class="data-item-label">Método</span>
                        <span class="data-item-value" style="text-transform:uppercase; font-size:0.75rem; font-weight:700;">${methodName}</span>
                    </div>
                    <div class="card-mobile-data-item">
                        <span class="data-item-label">Referencia</span>
                        <span class="data-item-value" style="font-family:'JetBrains Mono';">${payment.reference || '---'}</span>
                    </div>
                </div>

                <div class="card-mobile-footer" style="justify-content: flex-end; border-top: 1px dashed rgba(0, 0, 0, 0.05); padding-top: 10px;">
                    <div class="mobile-dropdown-container">
                        <button class="mobile-action-btn" onclick="this.nextElementSibling.classList.toggle('show')" onblur="setTimeout(() => this.nextElementSibling?.classList.remove('show'), 200)" title="Opciones" style="background: transparent; border: none; font-size: 1.1rem; color: #94a3b8; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">
                            <i class="fas fa-ellipsis-v"></i>
                        </button>
                        <div class="mobile-dropdown-menu">
                            <button onclick="app.modules.payments.printReceipt(${payment.id})" class="dropdown-item">
                                <i class="fas fa-print" style="color: #64748b; width: 16px; text-align: center;"></i> Imprimir Recibo
                            </button>
                            <button onclick="app.modules.payments.showEditPaymentModal(${payment.id})" class="dropdown-item">
                                <i class="fas fa-edit" style="color: #6366f1; width: 16px; text-align: center;"></i> Editar Pago
                            </button>
                            ${payment.status !== 'cancelled' ? `
                            <button onclick="app.modules.payments.showRevertPaymentModal(${payment.id}, ${payment.client_id}, '${payment.payment_date}')" class="dropdown-item">
                                <i class="fas fa-undo" style="color: #eab308; width: 16px; text-align: center;"></i> Revertir Pago
                            </button>
                            ` : ''}
                            <button onclick="app.modules.payments.voidPayment(${payment.id})" class="dropdown-item" style="color: #dc2626;">
                                <i class="fas fa-trash" style="width: 16px; text-align: center;"></i> Eliminar Pago
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            `;
        }).join('');
    }

    renderPayments() {
        const container = document.getElementById('payments-table-container');
        const cardsGrid = document.getElementById('payments-cards-grid');
        const tableView = document.getElementById('payments-table-view');

        if (!container) return;

        // Ensure display logic is applied
        this.isMobile = window.innerWidth < 1024;

        if (this.isMobile) {
            if (tableView) tableView.style.display = 'none';
            if (cardsGrid) cardsGrid.style.display = 'grid';
        } else {
            if (tableView) tableView.style.display = 'block';
            if (cardsGrid) cardsGrid.style.display = 'none';
        }

        let tbody = document.getElementById('payments-table-body');
        if (!tbody && tableView) {
            tableView.innerHTML = `
                <table class="premium-data-table" style="border-spacing: 0 2px;">
                    <thead>
                        <tr>
                            <th>NRO</th>
                            <th>CLIENTE</th>
                            <th>FECHA</th>
                            <th>MONTO</th>
                            <th>MÉTODO</th>
                            <th>REFERENCIA</th>
                            <th>ESTADO</th>
                            <th style="text-align:right">ACCIONES</th>
                        </tr>
                    </thead>
                    <tbody id="payments-table-body"></tbody>
                </table>
            `;
            tbody = document.getElementById('payments-table-body');
        }

        if (this.payments.length === 0) {
            const emptyHtml = `
                <div class="empty-state-premium" style="text-align:center; padding: 60px; color: #94a3b8; grid-column: 1 / -1; width: 100%;">
                    <i class="fas fa-search-dollar" style="font-size: 2.5rem; opacity:0.1; margin-bottom:15px; display:block;"></i>
                    <p style="font-weight:600; color:#1e293b;">No hay registros</p>
                </div>
            `;

            if (this.isMobile && cardsGrid) {
                cardsGrid.innerHTML = emptyHtml;
            } else if (tbody) {
                tbody.innerHTML = `<tr><td colspan="8">${emptyHtml}</td></tr>`;
            }
            return;
        }

        const state = this.sortStates.payments;
        const col = state.column;
        const dir = state.direction === 'asc' ? 1 : -1;

        const sorted = [...this.payments].sort((a, b) => {
            let valA = a[col];
            let valB = b[col];

            if (col === 'amount' || col === 'id') return (valA - valB) * dir;
            if (col === 'payment_date') {
                return (new Date(valA || 0) - new Date(valB || 0)) * dir;
            }

            return (valA || '').toString().localeCompare((valB || '').toString()) * dir;
        });

        // Logic to render either table or cards
        if (this.isMobile) {
            if (cardsGrid) {
                this.renderPaymentsCards(sorted);
            }
        } else {
            if (tbody) {
                tbody.innerHTML = sorted.map((payment, index) => {
                    const sequentialNumber = index + 1;

                    const methodMap = {
                        'cash': 'EFECTIVO',
                        'transfer': 'TRANSFERENCIA',
                        'card': 'TARJETA/DIGITAL',
                        'pago_movil': 'PAGO MÓVIL',
                        'zelle': 'ZELLE/INTL'
                    };
                    const statusMap = {
                        'paid': 'PAGADO',
                        'completed': 'PAGADO',
                        'verified': 'PAGADO',
                        'verificated': 'PAGADO',
                        'pending': 'PENDIENTE',
                        'voided': 'ANULADO'
                    };

                    const methodName = methodMap[payment.payment_method?.toLowerCase()] || payment.payment_method?.toUpperCase() || 'EFECTIVO';
                    const statusName = statusMap[payment.status?.toLowerCase()] || payment.status?.toUpperCase() || 'PAGADO';
                    const statusClass = (payment.status === 'paid' || payment.status === 'completed' || payment.status === 'verified' || payment.status === 'verificated') ? 'success' : 'warning';

                    return `
                <tr class="premium-row" style="background: rgba(255,255,255,0.4);">
                    <td>
                        <div class="avatar-mini" style="width:32px; height:32px; font-size:0.8rem; background:linear-gradient(135deg, #1e293b, #0f172a); color:#38bdf8;">#${sequentialNumber}</div>
                    </td>
                    <td>
                        <div style="display:flex; flex-direction:column;">
                            <span style="font-weight:750; color:#1e293b; font-size:0.85rem;">${payment.client_name || 'Desconocido'}</span>
                            <span style="font-size:0.7rem; color:#94a3b8; font-weight:600;">${payment.subscriber_code || '---'}</span>
                        </div>
                    </td>
                    <td>
                        <div style="display:flex; flex-direction:column;">
                            <span style="font-weight:700; color:#475569; font-size:0.75rem;">${new Date(payment.payment_date).toLocaleDateString()}</span>
                            <span style="font-size:0.65rem; color:#94a3b8;">${new Date(payment.payment_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                    </td>
                    <td>
                        <div style="display:flex; flex-direction:column; align-items:flex-start;">
                            <span style="font-weight:800; color:#0f172a; font-size:0.95rem;">$${(payment.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                            <span style="font-size:0.6rem; color:#94a3b8; letter-spacing:0.05em;">COP TRANSACCIÓN</span>
                        </div>
                    </td>
                    <td>
                        <span class="id-badge" style="background:white; border:1px solid #e2e8f0; font-size:0.65rem; color:#475569; text-transform:uppercase;">
                            ${methodName}
                        </span>
                    </td>
                    <td>
                        <span style="font-family:'JetBrains Mono'; font-size:0.7rem; color:#64748b;">${payment.reference || '---'}</span>
                    </td>
                    <td>
                        <span class="premium-status-badge ${statusClass}" style="font-size:0.6rem; padding: 4px 8px;">
                            <i class="fas ${statusClass === 'success' ? 'fa-check-circle' : 'fa-clock'}" style="font-size:0.7rem;"></i> ${statusName}
                        </span>
                    </td>
                    <td style="text-align: right;">
                        <div style="display:flex; gap:6px; justify-content:flex-end;">
                            <button class="action-btn-mini success" onclick="app.modules.payments.printReceipt(${payment.id})" title="Imprimir">
                                <i class="fas fa-print"></i>
                            </button>
                            <button class="action-btn-mini" onclick="app.modules.payments.showEditPaymentModal(${payment.id})" title="Editar">
                                <i class="fas fa-edit"></i>
                            </button>
                            ${payment.status !== 'cancelled' ? `
                            <button class="action-btn-mini danger" onclick="app.modules.payments.showRevertPaymentModal(${payment.id}, ${payment.client_id}, '${payment.payment_date}')" title="Revertir">
                                <i class="fas fa-undo"></i>
                            </button>
                            ` : ''}
                            <button class="action-btn-mini danger" onclick="app.modules.payments.voidPayment(${payment.id})" title="Eliminar">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </td>
                </tr>
                `;
                }).join('');
            }
        }
    }


    printReceipt(id) {
        if (window.toast) window.toast.show('Generando vista de impresión...', 'info');
        window.open(`/api/payments/${id}/print`, '_blank');
    }

    /**
     * View payment receipt details
     * Called from history modal when user clicks the "eye" icon
     */
    viewReceiptDetails(paymentId) {
        // Open the dedicated payment detail report modal
        if (this.modalManager) {
            this.modalManager.open('payment-detail', { paymentId });
        } else {
            console.error('ModalManager not available');
        }
    }

    async showReactivationConfirm(clientName, clientStatus) {
        return new Promise((resolve) => {
            const statusText = clientStatus === 'suspended' ? 'SUSPENDIDO' : 'CORTADO';
            const statusIcon = clientStatus === 'suspended' ? '⏸️' : '🚫';

            // Crear modal de confirmación personalizado
            const modal = document.createElement('div');
            modal.style.cssText = 'position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:10000; display:flex; align-items:center; justify-content:center;';

            modal.innerHTML = `
                <div style="background:white; border-radius:16px; padding:32px; max-width:500px; box-shadow: 0 20px 60px rgba(0,0,0,0.3);">
                    <div style="text-align:center; margin-bottom:24px;">
                        <div style="font-size:3rem; margin-bottom:16px;">${statusIcon}</div>
                        <h3 style="font-size:1.5rem; color:#0f172a; margin:0 0 8px 0;">Cliente ${statusText}</h3>
                        <p style="font-size:0.9rem; color:#64748b; margin:0;"><strong>${clientName}</strong></p>
                    </div>
                    
                    <div style="background:#f1f5f9; border-radius:12px; padding:16px; margin-bottom:24px; border-left:4px solid #6366f1;">
                        <p style="margin:0; font-size:0.9rem; color:#475569; line-height:1.6;">
                            El servicio de este cliente está actualmente ${statusText.toLowerCase()}. ¿Qué deseas hacer?
                        </p>
                    </div>
                    
                    <div style="display:flex; gap:12px; flex-direction:column;">
                        <button id="reactivate-btn" style="background:linear-gradient(135deg, #6366f1, #4f46e5); color:white; border:none; padding:14px 24px; border-radius:10px; font-weight:700; font-size:0.95rem; cursor:pointer; box-shadow:0 4px 12px rgba(99,102,241,0.3); transition:transform 0.2s;">
                            <i class="fas fa-check-circle" style="margin-right:8px;"></i>
                            Registrar Pago y ACTIVAR Servicio
                        </button>
                        <button id="payment-only-btn" style="background:white; color:#64748b; border:2px solid #e2e8f0; padding:14px 24px; border-radius:10px; font-weight:600; font-size:0.95rem; cursor:pointer; transition:all 0.2s;">
                            <i class="fas fa-dollar-sign" style="margin-right:8px;"></i>
                            Solo Registrar Pago
                        </button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            // Efectos hover
            const reactivateBtn = modal.querySelector('#reactivate-btn');
            const paymentOnlyBtn = modal.querySelector('#payment-only-btn');

            reactivateBtn.addEventListener('mouseenter', () => reactivateBtn.style.transform = 'translateY(-2px)');
            reactivateBtn.addEventListener('mouseleave', () => reactivateBtn.style.transform = 'translateY(0)');
            paymentOnlyBtn.addEventListener('mouseenter', () => paymentOnlyBtn.style.borderColor = '#94a3b8');
            paymentOnlyBtn.addEventListener('mouseleave', () => paymentOnlyBtn.style.borderColor = '#e2e8f0');

            // Event listeners
            reactivateBtn.addEventListener('click', () => {
                document.body.removeChild(modal);
                resolve('reactivate');
            });

            paymentOnlyBtn.addEventListener('click', () => {
                document.body.removeChild(modal);
                resolve('payment_only');
            });
        });
    }

    closePaymentModal() {
        const modal = document.getElementById('payment-modal');
        if (!modal) return;

        // Cerrar el modal
        modal.classList.remove('active');

        // Limpiar modo de edición
        delete modal.dataset.mode;
        delete modal.dataset.paymentId;

        // Resetear título y botón
        const modalTitle = document.getElementById('payment-modal-title');
        if (modalTitle) modalTitle.innerText = 'Registrar Nuevo Pago';

        const submitText = document.getElementById('payment-submit-text');
        if (submitText) submitText.innerText = 'Confirmar Pago';

        // Ocultar cuadro de auditoría
        const auditBox = document.getElementById('payment-audit-box');
        if (auditBox) auditBox.style.display = 'none';

        const layoutDivider = document.getElementById('layout-divider-v');
        if (layoutDivider) layoutDivider.style.display = 'none';

        // Limpiar formulario
        const form = document.getElementById('payment-form');
        if (form) form.reset();

        // Limpiar campo oculto de client_id
        const clientIdInput = document.getElementById('payment-client-id');
        if (clientIdInput) clientIdInput.value = '';

        // Resetear vista a búsqueda inicial
        const searchStep = document.getElementById('payment-client-search-step');
        const selectedDisplay = document.getElementById('selected-client-display');
        const detailsFields = document.getElementById('payment-details-fields');

        if (searchStep) searchStep.style.display = 'block';
        if (selectedDisplay) selectedDisplay.style.display = 'none';
        if (detailsFields) detailsFields.style.display = 'none';
    }

    async showEditPaymentModal(paymentId) {
        if (window.toast) toast.info('Cargando datos del pago...');
        try {
            const p = await this.api.get(`/api/payments/${paymentId}`);

            if (this.modalManager) {
                // Usar el ModalManager para abrir el modal correctamente
                await this.modalManager.open('payment', { payment: p });
            } else {
                console.error('ModalManager no disponible');
                if (window.toast) toast.error('Error interno: Gestor de modales no disponible');
            }
        } catch (e) {
            console.error(e);
            if (window.toast) toast.error('Error al cargar pago: ' + (e.message || e));
        }
    }



    async voidPayment(id) {
        let reason = prompt('¿Por qué deseas anular este pago?\n(Esta acción moverá el pago a la papelera y restaurará la deuda del cliente)');
        if (reason === null) return; // Cancelled
        if (!reason.trim()) reason = 'Sin motivo especificado';

        try {
            if (window.app) app.showLoading(true);
            await this.api.delete(`/api/payments/${id}?reason=${encodeURIComponent(reason)}`);

            if (window.toast) window.toast.show('Pago anulado y movido a papelera', 'success');
            this.loadPayments();
            this.loadStatistics();
        } catch (e) {
            console.error(e);
            const errText = e.data && e.data.error ? e.data.error : e.message;
            if (window.toast) window.toast.show('Error al anular pago: ' + errText, 'error');
        } finally {
            if (window.app) app.showLoading(false);
        }
    }

    async loadPromises() {
        try {
            const queryEl = document.getElementById('promise-search');
            const query = queryEl ? queryEl.value : '';
            const clients = await this.api.get(`/api/clients?status=all&search=${encodeURIComponent(query)}`);
            const now = new Date();
            this.promises = clients.filter(c => {
                if (!c.promise_date) return false;
                const promiseDate = new Date(c.promise_date);
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                return promiseDate.getTime() >= today.getTime();
            });
            this.renderPromises();
        } catch (error) {
            console.error('❌ Error loading promises:', error);
            this.promises = [];
            this.renderPromises();
        }
    }

    async createPromise(clientId, date) {
        // Alias for external calls if needed, though ClientsModule handles the modal
        // Ideally this logic should reside in ClientsModule or shared service
    }

    renderPromises() {
        const tbody = document.getElementById('promises-table-body');
        if (!tbody) return;

        if (!this.promises || this.promises.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align:center; padding: 40px; color: #94a3b8;">
                        <i class="fas fa-handshake" style="font-size: 2rem; opacity:0.5; margin-bottom:10px;"></i>
                        <p>No se encontraron promesas de pago activas</p>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.promises.map(client => {
            const initial = (client.legal_name || 'C').charAt(0).toUpperCase();
            return `
             <tr class="premium-row">
                <td class="client-cell-premium">
                    <div class="avatar-mini">${initial}</div>
                    <div class="client-info-stack">
                        <span class="client-name-text">${client.legal_name}</span>
                        <span class="client-sub-text">${client.subscriber_code}</span>
                    </div>
                </td>
                <td>
                    <span class="id-badge" style="background:#eef2ff; color:#4f46e5; border:none; font-size:0.65rem;">
                        <i class="fas fa-server" style="margin-right:4px; opacity:0.5;"></i> ${client.router || 'Global'}
                    </span>
                 </td>
                <td class="amount-cell-premium">
                    <div class="amount-main">$${(client.account_balance || 0).toLocaleString()}</div>
                    <div class="amount-sub">DEUDA ACTUAL</div>
                </td>
                <td>
                    <div class="date-wrapper" style="color:#6366f1;">
                        <i class="far fa-calendar-check"></i>
                        <span>${new Date(client.promise_date).toLocaleDateString()}</span>
                    </div>
                </td>
                <td style="text-align: right;">
                    <div class="action-flex-right">
                        <button class="action-btn-mini" onclick="app.modules.clients.openClientDetails(${client.id})" title="Ver Cliente">
                            <i class="fas fa-external-link-alt"></i>
                        </button>
                        <button class="action-btn-mini success" onclick="app.modules.payments.showNewPaymentModal(${client.id})" title="Registrar Pago">
                            <i class="fas fa-dollar-sign"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `}).join('');
    }

    toggleAutomationFilters() {
        const scope = document.getElementById('automation-scope').value;
        const routerFilter = document.getElementById('automation-router-filter');
        if (routerFilter) {
            routerFilter.style.display = scope === 'router' ? 'block' : 'none';
        }
    }


    async runBillingCycle() {
        const scope = document.getElementById('automation-scope').value;
        const routerId = document.getElementById('automation-router-id').value;
        const month = document.getElementById('automation-month').value;
        const year = document.getElementById('automation-year').value;

        const monthName = document.getElementById('automation-month').options[document.getElementById('automation-month').selectedIndex]?.text || '';

        let confirmMsg = `¿Deseas ejecutar el ciclo de facturación y cortes para ${monthName} ${year}?\n\nEsto generará deudas y procesará suspensiones según los parámetros del router.`;

        if (scope === 'router') {
            if (!routerId) {
                if (window.toast) toast.error('Selecciona un router para continuar');
                return;
            }
            const routerName = document.getElementById('automation-router-id').options[document.getElementById('automation-router-id').selectedIndex].text;
            confirmMsg = `¿Ejecutar ciclo para ${monthName} ${year} SOLO en el router [${routerName}]?`;
        }

        if (!confirm(confirmMsg)) return;

        try {
            if (window.app) app.showLoading(true);
            const payload = {
                year: parseInt(year),
                month: parseInt(month)
            };
            if (scope === 'router') payload.router_id = parseInt(routerId);

            const response = await this.api.post('/api/billing/run-cycle', payload);

            if (response.success) {
                if (window.toast) toast.success('Ciclo iniciado correctamente.');
                this.loadStatistics();
            } else {
                if (window.toast) toast.error('Error: ' + response.message);
            }
        } catch (error) {
            console.error(error);
            if (window.toast) toast.error('Error al ejecutar el ciclo');
        } finally {
            if (window.app) app.showLoading(false);
        }
    }

    showNewPaymentModal(preSelectedClient = null) {
        // Usar el nuevo Payment Modal component via ModalManager
        if (this.modalManager) {
            // Abrir modal via componente
            const data = {};
            if (preSelectedClient) {
                // Puede ser un ID o un objeto cliente
                data.clientId = typeof preSelectedClient === 'object'
                    ? preSelectedClient.id
                    : preSelectedClient;
            }
            this.modalManager.open('payment', data);
        } else {
            console.error('❌ ModalManager not available. Cannot open Payment Modal.');
        }
    }



    async searchClients(query) {
        if (!query || query.trim().length < 2) return;

        const container = document.getElementById('payment-search-results');
        if (!container) return;

        console.log(`🔍 Searching for: "${query}"`);

        container.innerHTML = `
            <div style="padding: 30px; text-align: center; color: #64748b; background: white; border-radius: 12px;">
                <div class="spinner-premium" style="margin: 0 auto 15px;"></div>
                <p style="font-weight: 600; font-size: 0.9rem;">Buscando en la base de datos...</p>
                <p style="font-size: 0.75rem; opacity: 0.7; margin-top: 5px;">Consultando "${query}"</p>
            </div>
        `;
        container.classList.add('active');
        container.style.display = 'block';

        try {
            const results = await this.api.get(`/api/clients?search=${encodeURIComponent(query)}`);
            this.lastSearchResults = results;
            console.log(`✅ Search results for "${query}":`, results.length);
            this.renderSearchResults(results);
        } catch (error) {
            console.error('❌ Search Error:', error);
            container.innerHTML = `
                <div style="padding: 30px; text-align: center; color: #ef4444; background: white; border-radius: 12px;">
                    <i class="fas fa-exclamation-triangle" style="font-size: 2rem; margin-bottom: 15px;"></i>
                    <p style="font-weight: 700;">Error en la búsqueda</p>
                    <p style="font-size: 0.8rem; opacity: 0.8;">No pudimos conectar con el servidor. Reintente en un momento.</p>
                </div>
            `;
        }
    }

    // --- RE-IMPLEMENTED TAIL METHODS ---

    renderSearchResults(clients) {
        const container = document.getElementById('payment-search-results');
        if (!container) return;

        if (clients.length === 0) {
            container.innerHTML = `
                <div class="search-no-results" style="padding: 30px 20px; text-align: center; color: #94a3b8;">
                    <div style="background: #f1f5f9; width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 15px;">
                        <i class="fas fa-user-slash" style="font-size: 1.25rem;"></i>
                    </div>
                    <div style="font-weight: 700; color: #475569; font-size: 0.95rem;">No se encontraron clientes</div>
                    <div style="font-size: 0.8rem; margin-top: 4px;">Intenta con otro nombre, IP o documento</div>
                </div>
            `;
            container.style.display = 'block';
            return;
        }

        container.innerHTML = `
            <div style="padding: 10px 0;">
                <div style="padding: 0 16px 10px 16px; font-size: 0.7rem; font-weight: 800; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em;">
                    Resultados encontrados (${clients.length})
                </div>
                ${clients.map(c => {
            const statusClass = c.status === 'active' ? 'success' : (c.status === 'suspended' ? 'danger' : 'secondary');
            const initials = (c.legal_name || 'C').split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();

            return `
                        <div class="search-result-item-premium" onclick="app.modules.payments.selectClient({
                            id: ${c.id}, 
                            legal_name: '${(c.legal_name || 'Sin Nombre').replace(/'/g, "\\'")}', 
                            status: '${c.status}',
                            account_balance: ${c.account_balance || 0},
                            ip_address: '${c.ip_address || ''}',
                            subscriber_code: '${c.subscriber_code || ''}',
                            identity_document: '${c.identity_document || ''}'
                        })">
                            <div class="res-avatar" style="background: ${c.status === 'active' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)'}; color: ${c.status === 'active' ? '#059669' : '#dc2626'};">
                                ${initials}
                            </div>
                            <div class="res-content">
                                <div class="res-name">${c.legal_name}</div>
                                <div class="res-meta">
                                    <span class="res-code"><i class="fas fa-hashtag"></i> ${c.subscriber_code || '---'}</span>
                                    <span class="res-ip"><i class="fas fa-network-wired"></i> ${c.ip_address || 'Sin IP'}</span>
                                </div>
                            </div>
                            <div class="res-status-tag ${statusClass}">
                                ${c.status === 'active' ? 'ACTIVO' : 'CORTADO'}
                            </div>
                        </div>
                    `;
        }).join('')}
            </div>
        `;
        container.style.display = 'block';
    }

    hideSearchResults() {
        const container = document.getElementById('payment-search-results');
        if (container) container.style.display = 'none';
    }

    selectClient(client) {
        // Guardar cliente para uso posterior (reactivación)
        this.selectedClient = client;

        document.getElementById('payment-client-id').value = client.id;

        const display = document.getElementById('selected-client-display');
        const searchStep = document.getElementById('payment-client-search-step');
        const detailsFields = document.getElementById('payment-details-fields');

        if (display && searchStep) {
            display.style.display = 'block';
            searchStep.style.display = 'none';
            if (detailsFields) detailsFields.style.display = 'block';

            // Fill Basic Info
            const nameEl = document.getElementById('display-client-name');
            if (nameEl) nameEl.textContent = client.legal_name || 'Sin Nombre';

            const codeEl = document.getElementById('display-client-code');
            if (codeEl) codeEl.textContent = client.subscriber_code || '---';

            const ipEl = document.getElementById('display-client-ip');
            if (ipEl) ipEl.textContent = client.ip_address ? `IP: ${client.ip_address}` : '';

            // Fill Debt/Status Info con estados específicos
            const debtContainer = document.getElementById('display-client-debt-info');
            if (debtContainer) {
                const balance = client.account_balance || 0;
                const status = client.status || 'active';

                // Determinar badge de estado según cliente
                let statusLabel, statusClass, statusIcon, statusBg;

                if (balance <= 0 && status === 'active') {
                    // Cliente al día y activo
                    statusLabel = 'PAGO Y ACTIVO';
                    statusClass = 'success';
                    statusIcon = 'fa-check-circle';
                    statusBg = 'rgba(22, 163, 74, 0.1)';
                } else if (balance > 0 && status === 'active') {
                    // Tiene deuda pero activo
                    statusLabel = 'PENDIENTE';
                    statusClass = 'warning';
                    statusIcon = 'fa-exclamation-circle';
                    statusBg = 'rgba(234, 88, 12, 0.1)';
                } else if (status === 'suspended') {
                    // Servicio suspendido
                    statusLabel = 'SUSPENDIDO';
                    statusClass = 'danger';
                    statusIcon = 'fa-pause-circle';
                    statusBg = 'rgba(220, 38, 38, 0.1)';
                } else if (status === 'cut' || status === 'inactive') {
                    // Servicio cortado
                    statusLabel = 'CORTADO';
                    statusClass = 'secondary';
                    statusIcon = 'fa-ban';
                    statusBg = 'rgba(100, 116, 139, 0.1)';
                } else {
                    // Otros estados
                    statusLabel = status.toUpperCase();
                    statusClass = 'secondary';
                    statusIcon = 'fa-circle';
                    statusBg = 'rgba(100, 116, 139, 0.1)';
                }

                // Calcular mes de deuda (aproximado)
                const monthlyFee = client.monthly_fee || 0;
                const monthsOfDebt = monthlyFee > 0 ? Math.ceil(balance / monthlyFee) : 0;
                const debtMonthsText = monthsOfDebt > 0 ? `${monthsOfDebt} mes${monthsOfDebt > 1 ? 'es' : ''}` : 'N/A';

                const balanceLabel = balance > 0 ? 'DEBE' : 'AL DÍA';
                const balanceColor = balance > 0 ? '#dc2626' : '#16a34a';

                debtContainer.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; width:100%; padding: 8px 0;">
                        <div style="flex: 1;">
                            <div style="font-size:0.6rem; color:#94a3b8; font-weight:800; text-transform:uppercase; margin-bottom: 4px; letter-spacing: 0.05em;">Saldo Pendiente</div>
                            <div style="display:flex; align-items: baseline; gap:10px;">
                                <div style="font-size:1.9rem; font-weight:950; color:${balanceColor}; line-height:1; letter-spacing:-0.03em;">
                                    $${balance.toLocaleString()}
                                </div>
                                <span style="font-size:0.65rem; font-weight:800; color:#64748b;">COP</span>
                            </div>
                            ${monthsOfDebt > 0 ? `
                                <div style="font-size:0.65rem; color:#94a3b8; margin-top:4px;">
                                    <i class="far fa-calendar-alt" style="margin-right:4px;"></i>
                                    Aprox. ${debtMonthsText} de atraso
                                </div>
                            ` : ''}
                        </div>
                        <div style="text-align:right; background: ${statusBg}; padding: 10px 16px; border-radius: 12px; border: 1px solid ${statusClass === 'success' ? '#16a34a33' : (statusClass === 'warning' ? '#ea580c33' : (statusClass === 'danger' ? '#dc262633' : '#64748b33'))};">
                            <div style="font-size:0.6rem; color:#64748b; font-weight:800; text-transform:uppercase; margin-bottom:6px; letter-spacing: 0.05em;">Estado del Servicio</div>
                            <span class="premium-status-badge ${statusClass}" style="font-size:0.75rem; padding:6px 12px; font-weight: 900; box-shadow: 0 2px 8px ${statusBg};">
                                <i class="fas ${statusIcon}" style="margin-right:6px;"></i>
                                ${statusLabel}
                            </span>
                        </div>
                    </div>
                `;
            }

            // Pre-fill amount if debt exists
            const amountInput = document.getElementById('pay-amount');
            if (amountInput && (client.account_balance || 0) > 0) {
                amountInput.value = client.account_balance;
            }
        }
        this.hideSearchResults();
    }

    async selectClientById(id) {
        try {
            const client = await this.api.get(`/api/clients/${id}`);
            this.selectClient(client);
        } catch (e) { console.error(e); }
    }

    clearSelectedClient() {
        document.getElementById('payment-client-id').value = '';

        const display = document.getElementById('selected-client-display');
        const searchStep = document.getElementById('payment-client-search-step');
        const detailsFields = document.getElementById('payment-details-fields');
        const auditBox = document.getElementById('payment-audit-box');

        if (display && searchStep) {
            display.style.display = 'none';
            searchStep.style.display = 'block';
            if (detailsFields) detailsFields.style.display = 'none';

            // Hide audit box for new payments
            if (auditBox) auditBox.style.display = 'none';

            const input = document.getElementById('payment-client-query');
            if (input) {
                input.value = '';
                input.focus();
            }
        }

        // Also reset modal title
        const modalTitle = document.getElementById('payment-modal-title');
        if (modalTitle) modalTitle.innerText = 'Registrar Nuevo Pago';
    }


    showNewPromiseModal(preSelectedClient = null) {
        if (this.modalManager) {
            const data = {};
            if (preSelectedClient) {
                if (typeof preSelectedClient === 'object') {
                    data.client = preSelectedClient;
                    data.clientId = preSelectedClient.id;
                } else {
                    data.clientId = preSelectedClient;
                }
            }
            this.modalManager.open('promise', data);
        } else {
            console.error('❌ ModalManager not available for Promise Modal');
            // Fallback legacy (si existiera)
        }
    }

    closeNewPromiseModal() {
        if (this.modalManager) {
            this.modalManager.close('promise');
        }
    }

    // legacy methods removed - handled by PromiseModal component

    initAutomationParams() {
        const now = new Date();
        const yearEl = document.getElementById('automation-year');
        const monthEl = document.getElementById('automation-month');

        if (yearEl) yearEl.value = now.getFullYear();
        if (monthEl) monthEl.value = now.getMonth() + 1;
    }

    // --- CENTRALIZED ROUTER MANAGEMENT ---

    async loadRouters() {
        if (this._loadingRouters) return this._loadingRouters;

        this._loadingRouters = (async () => {
            try {
                this.routers = await this.api.get('/api/routers');
                console.log(`📡 Cache: ${this.routers.length} routers loaded`);

                // Populate all active selectors in the DOM
                this.populateRouterSelectors();
                return this.routers;
            } catch (e) {
                console.error('Error in centralized loadRouters:', e);
                return [];
            } finally {
                this._loadingRouters = null;
            }
        })();

        return this._loadingRouters;
    }

    populateRouterSelectors() {
        if (!this.routers || this.routers.length === 0) return;

        const selectors = [
            { id: 'report-router-id', defaultLabel: 'TODOS LOS ROUTERS (General)' },

            { id: 'automation-router-id', defaultLabel: '-- Seleccionar Router --' }
        ];

        selectors.forEach(sel => {
            const element = document.getElementById(sel.id);
            if (element) {
                const currentVal = element.value;
                element.innerHTML = `<option value="">${sel.defaultLabel}</option>` +
                    this.routers.map(r => `<option value="${r.id}">${r.alias} ${r.host_address ? '(' + r.host_address + ')' : ''}</option>`).join('');
                if (currentVal) element.value = currentVal;
            }
        });
    }

    initReportsFilters() {
        // Ensure selectors are populated if routers are already cached
        if (this.routers.length > 0) {
            this.populateRouterSelectors();
        } else {
            this.loadRouters();
        }

        // Set default values for time selectors
        const now = new Date();
        const daySelect = document.getElementById('report-audit-day');
        const monthSelect = document.getElementById('report-audit-month');
        const yearSelect = document.getElementById('report-audit-year');

        if (daySelect && !daySelect.dataset.initialized) {
            // No default day (default to whole month) unless specifically needed
            daySelect.dataset.initialized = "true";
        }
        if (monthSelect && !monthSelect.dataset.initialized) {
            monthSelect.value = now.getMonth() + 1;
            monthSelect.dataset.initialized = "true";
        }
        if (yearSelect && !yearSelect.dataset.initialized) {
            yearSelect.value = now.getFullYear();
            yearSelect.dataset.initialized = "true";
        }
    }

    loadRoutersForReports() {
        // Redirigir a la lógica centralizada
        this.populateRouterSelectors();
    }



    async loadAdvancedFinancialReport() {
        const period = document.getElementById('report-financial-period')?.value || 'annual';
        const year = new Date().getFullYear();

        try {
            if (window.app) app.showLoading(true);
            const data = await this.api.get(`/api/reports/financial`, {
                period,
                year,
                router_id: document.getElementById('report-router-id')?.value
            });

            this.renderAdvancedFinancialReport(data);
        } catch (e) {
            console.error('Error loading financial report:', e);
            if (window.toast) toast.error('Error al cargar reporte financiero');
        } finally {
            if (window.app) app.showLoading(false);
        }
    }

    renderAdvancedFinancialReport(data) {
        const container = document.getElementById('report-results-container');
        const placeholder = document.getElementById('report-initial-placeholder');
        const content = document.getElementById('report-data-content');
        const tableHead = document.getElementById('report-table-head');
        const tableBody = document.getElementById('report-table-body');
        const tableHeader = document.getElementById('report-table-header');
        const footer = document.getElementById('report-footer-stats');

        if (!container || !data) return;

        placeholder.style.display = 'none';
        content.style.display = 'block';

        // Update Print Title
        const titleEl = document.getElementById('print-report-title');
        const dateEl = document.getElementById('print-current-date');
        if (titleEl) titleEl.textContent = `Balance Financiero ${data.period === 'annual' ? 'Anual' : data.period === 'quarter' ? 'Trimestral' : 'Semestral'} - ${data.year}`;
        if (dateEl) dateEl.textContent = new Date().toLocaleString();

        tableHeader.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin:0; color:#1e293b; font-weight:800; font-size:1.2rem;">
                    Resumen Periodo: ${data.year}
                </h3>
                <div style="text-align: right;">
                    <span class="premium-status-badge success" style="font-size: 0.8rem; padding: 5px 12px; background: #ecfdf5; color: #059669; border: 1px solid #10b981;">
                        Rendimiento: ${data.summary.overall_performance.toFixed(1)}%
                    </span>
                </div>
            </div>
        `;

        tableHead.innerHTML = `
            <tr>
                <th>Periodo</th>
                <th style="text-align: right;">Meta (Activos)</th>
                <th style="text-align: right;">Meta (Bajas)</th>
                <th style="text-align: right;">Recogido (Real)</th>
                <th style="text-align: right;">Faltante (Pérdidas)</th>
                <th style="text-align: center;">Eficiencia</th>
            </tr>
        `;

        tableBody.innerHTML = data.breakdown.map(item => {
            const loss = Math.max(0, item.theoretical - item.collected);
            return `
            <tr>
                <td style="font-weight: 700; color: #475569;">${item.label}</td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace; color: #64748b; font-size: 0.8rem;">
                    $${(item.theoretical_active || 0).toLocaleString()}
                </td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace; color: #ef4444; font-size: 0.8rem; opacity: 0.8;">
                    $${(item.theoretical_lost || 0).toLocaleString()}
                </td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-weight: 800; color: #059669;">
                    $${item.collected.toLocaleString()}
                </td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-weight: 700; color: ${loss > 0 ? '#dc2626' : '#94a3b8'};">
                    $${loss.toLocaleString()}
                </td>
                <td style="text-align: center;">
                    <div style="display: flex; align-items: center; gap: 8px; justify-content: center;">
                        <div style="flex: 1; max-width: 80px; height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden;">
                            <div style="width: ${Math.min(100, item.performance)}%; height: 100%; background: ${item.performance >= 90 ? '#10b981' : item.performance > 70 ? '#f59e0b' : '#ef4444'};"></div>
                        </div>
                        <span style="font-size: 0.75rem; font-weight: 700; min-width: 45px;">${item.performance.toFixed(1)}%</span>
                    </div>
                </td>
            </tr>
        `}).join('');

        const totalLoss = Math.max(0, data.summary.total_theoretical - data.summary.total_collected);

        // NEW: Layout with Analytics Row
        footer.innerHTML = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 25px;">
                <!-- Analysis Panel -->
                <div id="report-detailed-analysis">
                    ${this.generateDetailedAnalysis(data)}
                </div>
                
                <!-- Chart Panel -->
                <div style="background: white; padding: 20px; border-radius: 16px; border: 1px solid #e2e8f0; min-height: 200px;">
                    <h4 style="margin: 0 0 12px 0; color: #1e293b; font-size: 0.9rem;">Distribución de Clientes (%)</h4>
                    <div style="height: 150px; position: relative;" id="status-chart-container">
                        <!-- Chart rendered by JS -->
                    </div>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                <div style="background: #f8fafc; padding: 12px; border-radius: 12px; border: 1px solid #e2e8f0;">
                    <span style="font-size: 0.65rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Meta de Recaudo (Total)</span>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #1e293b; margin-top: 5px;">$${data.summary.total_theoretical.toLocaleString()}</div>
                    <div style="font-size: 0.7rem; color: #94a3b8; margin-top: 2px;">
                        Activos: $${(data.summary.total_theoretical_active || 0).toLocaleString()} | 
                        Bajas: $${(data.summary.total_theoretical_lost || 0).toLocaleString()}
                    </div>
                </div>
                <div style="background: #f0fdf4; padding: 12px; border-radius: 12px; border: 1px solid #bcf0da;">
                    <span style="font-size: 0.65rem; font-weight: 700; color: #059669; text-transform: uppercase;">Total Recogido</span>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #059669; margin-top: 5px;">$${data.summary.total_collected.toLocaleString()}</div>
                    <div style="font-size: 0.7rem; color: #64748b; margin-top: 2px;">Ingresos reales liquidados</div>
                </div>
                <div style="background: #fef2f2; padding: 12px; border-radius: 12px; border: 1px solid #fee2e2;">
                    <span style="font-size: 0.65rem; font-weight: 700; color: #991b1b; text-transform: uppercase;">Faltante (Meses Pendientes)</span>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #dc2626; margin-top: 5px;">$${totalLoss.toLocaleString()}</div>
                    <div style="font-size: 0.7rem; color: #ef4444; margin-top: 2px;">Diferencia Meta vs Real</div>
                </div>
                <div style="background: #eff6ff; padding: 12px; border-radius: 12px; border: 1px solid #bfdbfe;">
                    <span style="font-size: 0.65rem; font-weight: 700; color: #1d4ed8; text-transform: uppercase;">Clientes Impacto</span>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #1e40af; margin-top: 5px;">${data.summary.active_clients_count}</div>
                    <div style="font-size: 0.7rem; color: #60a5fa; margin-top: 2px;">Base activa actual</div>
                </div>
            </div>
        `;

        // Render the cake chart
        if (data.summary.status_distribution) {
            this.renderStatusChart('status-chart-container', data.summary.status_distribution);
        }
    }

    generateDetailedAnalysis(data) {
        const perf = data.summary.overall_performance;
        const loss_pct = 100 - perf;
        let analysis = "";

        if (perf >= 95) {
            analysis = "Excelente rendimiento operativo. La recaudación real está casi alineada con la meta teórica, lo que indica un flujo de caja saludable y mínima morosidad.";
        } else if (perf >= 85) {
            analysis = "Buen rendimiento. Existe un margen de mejora en la gestión de cobros o recuperación de cartera vencida para alcanzar la meta óptima.";
        } else {
            analysis = "Alerta de recaudación. El índice de eficiencia está por debajo del promedio esperado, lo que requiere una revisión de las políticas de corte y cobranza.";
        }

        const loss = data.summary.total_loss;
        const routerLoss = data.summary.loss_by_router || {};
        let routerBreakdownHtml = "";

        if (Object.keys(routerLoss).length > 0) {
            const totalRouterLoss = Object.values(routerLoss).reduce((sum, item) => sum + (item.loss || 0), 0);
            const totalRouterClients = Object.values(routerLoss).reduce((sum, item) => sum + (item.unpaid_estimate || 0), 0);

            routerBreakdownHtml = `
                <div style="margin-top: 15px; border-top: 1px solid #f1f5f9; padding-top: 12px;">
                    <div style="font-size: 0.75rem; font-weight: 800; color: #1e293b; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.05em;">Desglose de Pérdida por Router:</div>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        ${Object.entries(routerLoss).map(([router, stats]) => `
                            <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #64748b;">
                                <span><i class="fas fa-server" style="font-size: 0.7rem; margin-right: 6px; opacity: 0.5;"></i> ${router}</span>
                                <span style="font-family: 'JetBrains Mono'; font-weight: 700; color: #dc2626;">
                                    $${stats.loss.toLocaleString()} <span style="font-weight: 400; opacity: 0.7; font-size: 0.7rem;">(${stats.unpaid_estimate} clientes)</span>
                                </span>
                            </div>
                        `).join('')}
                        
                        <!-- Summary Row -->
                        <div style="display: flex; justify-content: space-between; font-size: 0.82rem; color: #1e293b; margin-top: 8px; padding-top: 8px; border-top: 2px solid #f1f5f9; font-weight: 900;">
                            <span><i class="fas fa-sigma" style="margin-right: 6px; color: #6366f1;"></i> TOTAL GENERAL:</span>
                            <span style="font-family: 'JetBrains Mono';">
                                $${totalRouterLoss.toLocaleString()} <span style="font-weight: 700; opacity: 0.8; font-size: 0.75rem;">(${totalRouterClients} clientes)</span>
                            </span>
                        </div>
                    </div>
                </div>
            `;
        }

        return `
            <div style="background: white; padding: 20px; border-radius: 16px; border: 1px solid #e2e8f0; height: 100%; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <h4 style="margin: 0; color: #1e293b; font-size: 0.95rem; font-weight: 800;">Análisis Detallado de Índices</h4>
                    <div style="display: flex; gap: 10px;">
                        <div style="text-align: right;">
                            <div style="font-size: 0.6rem; color: #94a3b8; font-weight: 800; text-transform: uppercase;">Recepción</div>
                            <div style="font-size: 0.95rem; font-weight: 900; color: #10b981;">${perf.toFixed(1)}%</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 0.6rem; color: #94a3b8; font-weight: 800; text-transform: uppercase;">Pérdida</div>
                            <div style="font-size: 0.95rem; font-weight: 900; color: #dc2626;">${loss_pct.toFixed(1)}%</div>
                        </div>
                    </div>
                </div>
                
                <p style="font-size: 0.88rem; color: #475569; line-height: 1.6; margin-bottom: 15px; font-weight: 500;">
                    ${analysis}
                </p>
                
                <div style="background: #f8fafc; padding: 12px; border-radius: 10px; font-size: 0.82rem; color: #475569; border-left: 5px solid #6366f1; border: 1px solid #e2e8f0; border-left-width: 5px;">
                    <i class="fas fa-info-circle" style="color: #6366f1; margin-right: 8px;"></i>
                    <span style="font-weight: 600;">Se identifica un faltante de $${loss.toLocaleString()}</span> que corresponde principalmente a mensualidades no liquidadas o clientes en mora.
                </div>

                ${routerBreakdownHtml}
            </div>
        `;
    }

    renderStatusChart(containerId, distribution) {
        // Wait for next tick to ensure container is ready in DOM
        setTimeout(() => {
            const container = document.getElementById(containerId);
            if (!container) return;

            const canvas = document.createElement('canvas');
            canvas.style.maxWidth = '100%';
            canvas.style.maxHeight = '150px';
            container.appendChild(canvas);

            const totalClients = (distribution.active || 0) + (distribution.offline || 0) + (distribution.suspended || 0) + (distribution.retired || 0);

            new Chart(canvas, {
                type: 'pie',
                data: {
                    labels: [
                        `Activos (${distribution.active || 0})`,
                        `Offline (${distribution.offline || 0})`,
                        `Suspendidos (${distribution.suspended || 0})`,
                        `Retirados (${distribution.retired || 0})`
                    ],
                    datasets: [{
                        data: [
                            distribution.active,
                            distribution.offline,
                            distribution.suspended,
                            distribution.retired
                        ],
                        backgroundColor: ['#10b981', '#94a3b8', '#f59e0b', '#ef4444'],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right',
                            labels: {
                                boxWidth: 12,
                                padding: 8,
                                font: { size: 9, weight: 'bold' }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function (context) {
                                    const label = context.label || '';
                                    const value = context.parsed || 0;
                                    const percentage = totalClients > 0 ? ((value / totalClients) * 100).toFixed(1) : 0;
                                    return `${label}: ${percentage}%`;
                                }
                            }
                        }
                    }
                },
                plugins: [{
                    id: 'percentageLabels',
                    afterDraw: (chart) => {
                        const { ctx, data } = chart;
                        ctx.save();
                        const dataset = data.datasets[0];
                        const meta = chart.getDatasetMeta(0);

                        meta.data.forEach((element, index) => {
                            const value = dataset.data[index];
                            if (value === 0) return;

                            const percentage = totalClients > 0 ? ((value / totalClients) * 100).toFixed(0) : 0;
                            if (parseFloat(percentage) < 5) return; // Don't show if too small

                            const { x, y } = element.tooltipPosition();

                            ctx.fillStyle = '#fff';
                            ctx.font = 'bold 10px Inter, system-ui';
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'middle';

                            // Drop shadow for legibility
                            ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
                            ctx.shadowBlur = 4;
                            ctx.fillText(`${percentage}%`, x, y);
                        });
                        ctx.restore();
                    }
                }]
            });
        }, 100);
    }

    async loadClientsStatusReport() {
        const type = document.getElementById('report-client-type')?.value || 'debtors';
        const routerId = document.getElementById('report-router-id')?.value;
        const day = document.getElementById('report-audit-day')?.value;
        const month = document.getElementById('report-audit-month')?.value;
        const year = document.getElementById('report-audit-year')?.value;

        try {
            if (window.app) app.showLoading(true);
            const data = await this.api.get(`/api/reports/clients-status`, {
                type,
                router_id: routerId,
                day: day,
                month: month,
                year: year
            });

            this.renderClientsStatusReport(data);
        } catch (e) {
            console.error('Error loading client status report:', e);
            if (window.toast) toast.error('Error al cargar listado de clientes');
        } finally {
            if (window.app) app.showLoading(false);
        }
    }

    renderClientsStatusReport(data) {
        const placeholder = document.getElementById('report-initial-placeholder');
        const content = document.getElementById('report-data-content');
        const tableHead = document.getElementById('report-table-head');
        const tableBody = document.getElementById('report-table-body');
        const tableHeader = document.getElementById('report-table-header');
        const footer = document.getElementById('report-footer-stats');

        if (!data) return;

        placeholder.style.display = 'none';
        content.style.display = 'block';

        const typeNames = {
            'paid': 'Clientes al Día',
            'missing': 'Clientes Faltantes (Sin pago este mes)',
            'debtors': 'Pendientes y Morosos',
            'deleted': 'Papelera de Clientes'
        };

        // Update Print Title
        const titleEl = document.getElementById('print-report-title');
        const dateEl = document.getElementById('print-current-date');
        if (titleEl) titleEl.textContent = `Reporte de Auditoría: ${typeNames[data.type]}`;
        if (dateEl) dateEl.textContent = new Date().toLocaleString();

        tableHeader.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h3 style="margin:0; color:#1e293b; font-weight:800; font-size:1rem;">
                    ${typeNames[data.type]} (${data.count} clientes)
                </h3>
                <div class="no-print" style="font-size: 0.75rem; color: #64748b; background: #f1f5f9; padding: 4px 10px; border-radius: 6px;">
                    <i class="fas fa-info-circle"></i> Seleccione los clientes que desea incluir en la impresión
                </div>
            </div>
        `;

        tableHead.innerHTML = `
            <tr style="font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; background: rgba(248, 250, 252, 0.5);">
                <th style="width: 40px; text-align: center; padding: 6px 10px;" class="no-print">
                    <input type="checkbox" id="report-select-all" checked style="cursor: pointer; transform: scale(1.1);">
                </th>
                <th style="width: 20px; text-align: center; padding: 6px 2px;">#</th>
                <th style="width: 25%; padding: 6px 10px;">Código/Nombre</th>
                <th style="width: 20%; padding: 6px 10px;">Router/Zona</th>
                <th style="text-align: right; width: 14%; padding: 6px 10px;">${data.type === 'paid' ? 'Abonado' : 'Mensualización'}</th>
                <th style="text-align: right; width: 14%; padding: 6px 10px;">Pendiente</th>
                <th style="text-align: center; width: 10%; padding: 6px 10px;">Estado</th>
                <th style="text-align: center; width: 12%; padding: 6px 10px;" class="no-print">Acciones</th>
            </tr>
        `;

        if (!data.clients || data.clients.length === 0) {
            let emptyMsg = 'No se encontraron clientes para este reporte';
            let emptySubMsg = 'Intente con otros filtros de búsqueda';

            if (data.type === 'paid') {
                if (!data.has_payments) {
                    emptyMsg = 'En este mes no se generó ningún ingreso';
                    emptySubMsg = 'No se encontraron pagos registrados en el periodo seleccionado.';
                }
            } else if (data.type === 'missing' || data.type === 'debtors') {
                if (!data.cycle_exists) {
                    emptyMsg = 'Aún no se ha generado ciclo para el mes seleccionado';
                    emptySubMsg = 'No existen facturas emitidas en este periodo para auditar faltantes.';
                }
            }

            tableBody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align: center; padding: 60px 40px; color: #94a3b8;">
                        <i class="fas fa-folder-open" style="font-size: 3rem; opacity: 0.2; margin-bottom: 15px; display: block;"></i>
                        <h4 style="margin: 0; color: #64748b; font-weight: 700;">${emptyMsg}</h4>
                        <p style="margin: 5px 0 0 0; font-size: 0.85rem; opacity: 0.8;">${emptySubMsg}</p>
                    </td>
                </tr>
            `;
        } else {
            // Sort Alphabetically by Name
            const sortedClients = [...data.clients].sort((a, b) => a.name.localeCompare(b.name));

            tableBody.innerHTML = sortedClients.map((c, index) => `
                <tr class="premium-row" data-client-id="${c.id}" style="transition: background 0.1s;">
                    <td style="text-align: center; padding: 1px 4px !important;" class="no-print">
                        <input type="checkbox" class="client-report-checkbox" data-id="${c.id}" checked style="cursor: pointer; transform: scale(0.7);">
                    </td>
                    <td style="text-align: center; font-size: 0.6rem; font-weight: 800; color: #94a3b8; width: 20px; padding: 1px 2px !important;">
                        ${index + 1}
                    </td>
                    <td style="padding: 1px 8px !important;">
                        <div style="font-weight: 700; color: #1e293b; font-size: 0.65rem; line-height: 0.9;">${c.name}</div>
                        <div style="font-size: 0.5rem; color: #94a3b8; font-family: 'JetBrains Mono'; line-height: 0.9;">${c.code}</div>
                    </td>
                    <td style="font-size: 0.6rem; color: #475569; padding: 1px 8px !important;">
                        <div style="display: flex; flex-direction: column; line-height: 0.9;">
                            <span style="font-weight: 600; color: #1e293b;">${c.router}</span>
                            ${c.zone ? `<span style="font-size: 0.45rem; color: #94a3b8; text-transform: uppercase;">${c.zone}</span>` : ''}
                        </div>
                    </td>
                    <td style="text-align: right; font-family: 'JetBrains Mono', monospace; color: ${data.type === 'paid' ? '#059669' : '#475569'}; font-weight: 700; font-size: 0.65rem; padding: 1px 8px !important;">
                        $${(data.type === 'paid' ? c.paid_amount : c.fee).toLocaleString()}
                    </td>
                    <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-weight: 800; font-size: 0.68rem; color: ${c.balance > 0 ? '#dc2626' : (c.balance < 0 ? '#059669' : '#64748b')}; padding: 1px 8px !important;">
                        ${c.balance > 0 ? '- ' : (c.balance < 0 ? '+ ' : '')}$${Math.abs(c.balance).toLocaleString()}
                    </td>
                    <td style="text-align: center; padding: 1px 4px !important;">
                        <span class="premium-status-badge ${c.status.toLowerCase() === 'active' ? 'success' : c.status.toLowerCase() === 'suspended' ? 'warning' : 'secondary'}" style="font-size: 0.45rem; padding: 0px 3px; border-radius: 2px; font-weight: 800;">
                            ${c.status.toUpperCase()}
                        </span>
                    </td>
                    <td style="text-align: center; padding: 1px 4px !important;" class="no-print">
                        <div style="display: flex; gap: 2px; justify-content: center;">
                            <button type="button" 
                                    onclick="event.preventDefault(); event.stopPropagation(); app.modules.payments.showNewPaymentModal(${c.id})" 
                                    title="Registrar" style="background: #ecfdf5; border-radius: 2px; padding: 0px 3px; border: 1px solid #a7f3d0; cursor: pointer;">
                                <i class="fas fa-dollar-sign" style="color: #059669; font-size: 0.6rem;"></i>
                            </button>
                            <button type="button" 
                                    onclick="event.preventDefault(); event.stopPropagation(); app.modules.payments.showClientHistory(${c.id})" 
                                    title="Historial" style="background: #f1f5f9; border-radius: 2px; padding: 0px 3px; border: 1px solid #e2e8f0; cursor: pointer;">
                                <i class="fas fa-history" style="color: #6366f1; font-size: 0.6rem;"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');

            // Add Event Listeners for checkboxes
            const selectAll = document.getElementById('report-select-all');
            const checkboxes = tableBody.querySelectorAll('.client-report-checkbox');

            selectAll.addEventListener('change', (e) => {
                const checked = e.target.checked;
                checkboxes.forEach(cb => {
                    cb.checked = checked;
                    const row = cb.closest('tr');
                    if (checked) row.classList.remove('no-print-row');
                    else row.classList.add('no-print-row');
                });
            });

            checkboxes.forEach(cb => {
                cb.addEventListener('change', (e) => {
                    const row = e.target.closest('tr');
                    if (e.target.checked) row.classList.remove('no-print-row');
                    else row.classList.add('no-print-row');

                    // Update selectAll state
                    const allChecked = Array.from(checkboxes).every(c => c.checked);
                    selectAll.checked = allChecked;
                    selectAll.indeterminate = !allChecked && Array.from(checkboxes).some(c => c.checked);
                });
            });

            // 1. Render to SCREEN Header (Premium Boxes) - DYNAMIC TO FILTER
            const screenStats = document.getElementById('report-screen-stats');
            if (screenStats) {
                screenStats.style.display = 'flex';

                // Contextual colors depending on report type
                const colors = {
                    'paid': { bg: '#eff6ff', border: '#bfdbfe', text: '#2563eb', label: '#1d4ed8' },
                    'debtors': { bg: '#fff1f2', border: '#fecaca', text: '#dc2626', label: '#be123c' },
                    'missing': { bg: '#fefce8', border: '#fef08a', text: '#a16207', label: '#854d0e' },
                    'deleted': { bg: '#f1f5f9', border: '#e2e8f0', text: '#475569', label: '#1e293b' }
                };

                const theme = colors[data.type] || colors.deleted;
                const labelSuffix = data.type === 'paid' ? ' (Grupo Al Día)' : (data.type === 'debtors' ? ' (Cartera Mora)' : '');

                screenStats.innerHTML = `
                    <div style="text-align: right; background: ${theme.bg}; padding: 6px 15px; border-radius: 10px; border: 1.5px solid ${theme.border}; min-width: 140px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);">
                        <span style="font-size: 0.65rem; font-weight: 850; color: ${theme.label}; text-transform: uppercase; display: block;">${data.type === 'paid' ? 'Recogido' : 'Cobros'} ${labelSuffix}</span>
                        <div style="font-size: 1.1rem; font-weight: 950; color: ${theme.text};">$${(data.total_collected || 0).toLocaleString()}</div>
                    </div>
                    <div style="text-align: right; background: #fff1f2; padding: 6px 15px; border-radius: 10px; border: 1.5px solid #fecaca; min-width: 140px; opacity: ${data.type === 'paid' ? '0.5' : '1'};">
                        <span style="font-size: 0.65rem; font-weight: 800; color: #be123c; text-transform: uppercase; display: block;">Deuda Pendiente</span>
                        <div style="font-size: 1.1rem; font-weight: 900; color: #dc2626;">${data.total_pending > 0 ? '- ' : ''}$${(data.total_pending || 0).toLocaleString()}</div>
                    </div>
                    <div style="text-align: right; background: #ecfdf5; padding: 6px 15px; border-radius: 10px; border: 1.5px solid #a7f3d0; min-width: 140px; opacity: ${data.type === 'paid' ? '1' : '0.5'};">
                        <span style="font-size: 0.65rem; font-weight: 800; color: #047857; text-transform: uppercase; display: block;">Saldos Caja</span>
                        <div style="font-size: 1.1rem; font-weight: 900; color: #059669;">+ $${(data.total_credit || 0).toLocaleString()}</div>
                    </div>
                `;
            }

            // 2. Render to PRINT Header (Elegance)
            const printStatsHeader = document.getElementById('print-stats-header');
            if (printStatsHeader) {
                printStatsHeader.innerHTML = `
                    <div style="text-align: center; border: 1.5px solid #bfdbfe; padding: 8px 15px; border-radius: 10px; min-width: 140px;">
                        <span style="font-size: 8pt; font-weight: 800; color: #1d4ed8; text-transform: uppercase; display: block;">Total Recogido</span>
                        <div style="font-size: 14pt; font-weight: 900; color: #2563eb;">$${(data.total_collected || 0).toLocaleString()}</div>
                    </div>
                    <div style="text-align: center; border: 1.5px solid #fecaca; padding: 8px 15px; border-radius: 10px; min-width: 140px;">
                        <span style="font-size: 8pt; font-weight: 800; color: #be123c; text-transform: uppercase; display: block;">Deuda Pendiente</span>
                        <div style="font-size: 14pt; font-weight: 900; color: #dc2626;">${data.total_pending > 0 ? '- ' : ''}$${(data.total_pending || 0).toLocaleString()}</div>
                    </div>
                    <div style="text-align: center; border: 1.5px solid #a7f3d0; padding: 8px 15px; border-radius: 10px; min-width: 140px;">
                        <span style="font-size: 8pt; font-weight: 800; color: #047857; text-transform: uppercase; display: block;">Saldos Caja</span>
                        <div style="font-size: 14pt; font-weight: 900; color: #059669;">+ $${(data.total_credit || 0).toLocaleString()}</div>
                    </div>
                `;
            }

            // Keep footer stats for screen context
            footer.innerHTML = `
                <div style="display: flex; justify-content: flex-end; gap: 20px; align-items: flex-end; padding: 10px 0; border-top: 2px dashed #f1f5f9; margin-top: 10px;">
                    <div style="text-align: right; background: #eff6ff; padding: 6px 12px; border-radius: 8px; border: 1px solid #bfdbfe;">
                        <span style="font-size: 0.6rem; font-weight: 800; color: #1d4ed8; text-transform: uppercase;">Total Recogido</span>
                        <div style="font-size: 1rem; font-weight: 900; color: #2563eb;">$${(data.total_collected || 0).toLocaleString()}</div>
                    </div>
                    <div style="text-align: right; background: #fff1f2; padding: 6px 12px; border-radius: 8px; border: 1px solid #fecaca;">
                        <span style="font-size: 0.6rem; font-weight: 800; color: #be123c; text-transform: uppercase;">Deuda Pendiente</span>
                        <div style="font-size: 1rem; font-weight: 900; color: #dc2626;">${data.total_pending > 0 ? '- ' : ''}$${(data.total_pending || 0).toLocaleString()}</div>
                    </div>
                    <div style="text-align: right; background: #ecfdf5; padding: 6px 12px; border-radius: 8px; border: 1px solid #a7f3d0;">
                        <span style="font-size: 0.6rem; font-weight: 800; color: #047857; text-transform: uppercase;">Saldos Caja</span>
                        <div style="font-size: 1rem; font-weight: 900; color: #059669;">+ $${(data.total_credit || 0).toLocaleString()}</div>
                    </div>
                </div>
            `;
        }
    }

    viewClientHistory(clientId, clientName) {
        console.log(`🔍 Opening history modal for: ${clientName}`);
        this.showClientHistory(clientId);
    }

    // ==========================================
    //  MÓDULO DE GASTOS Y DEDUCIBLES
    // ==========================================



    async loadLossesDetail() {
        const tbody = document.getElementById('losses-table-body');
        if (!tbody) return;

        try {
            const params = new URLSearchParams();
            if (this.filterState.startDate) params.append('start_date', this.filterState.startDate);
            if (this.filterState.endDate) params.append('end_date', this.filterState.endDate);

            // Fetch losses detail from API
            const losses = await this.api.get(`/api/payments/losses-detail?${params.toString()}`);

            if (!losses || losses.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center py-5 text-muted">
                            <div style="opacity: 0.2; margin-bottom: 15px;">
                                <i class="fas fa-search-dollar" style="font-size: 3rem;"></i>
                            </div>
                            <div style="font-weight: 700; font-size: 1.1rem; color: #475569;">No hay fugas detectadas</div>
                            <div style="font-size: 0.85rem; color: #94a3b8;">La contabilidad está saneada para este periodo</div>
                        </td>
                    </tr>
                `;
                return;
            }

            tbody.innerHTML = losses.map(loss => {
                const date = loss.date ? new Date(loss.date).toLocaleDateString('es-CO', {
                    day: '2-digit', month: 'short', year: 'numeric'
                }) : '---';

                let catClass = 'bg-light text-secondary';
                if (loss.category === 'FX Variance') catClass = 'bg-info-soft text-info';
                if (loss.category === 'Prorating') catClass = 'bg-warning-soft text-warning';
                if (loss.category === 'Bad Debt') catClass = 'bg-danger-soft text-danger';

                return `
                    <tr class="premium-row">
                        <td class="ps-4">
                            <div style="font-weight: 700; color: #1e293b;">${loss.concept}</div>
                            <div style="font-size: 0.75rem; color: #64748b;">${loss.client_name}</div>
                        </td>
                        <td>
                            <span class="badge ${catClass}" style="font-size: 0.7rem; text-transform: uppercase; font-weight: 800; border-radius: 6px; padding: 4px 8px;">
                                ${loss.category}
                            </span>
                        </td>
                        <td>
                            <div style="font-size: 0.85rem; color: #475569;">
                                <i class="far fa-calendar-alt me-1" style="opacity: 0.5;"></i> ${date}
                            </div>
                        </td>
                        <td>
                            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #94a3b8;">
                                ${loss.reference || '---'}
                            </div>
                        </td>
                        <td class="text-end pe-4">
                            <div style="font-family: 'JetBrains Mono', monospace; font-weight: 900; color: #dc2626; font-size: 1rem;">
                                -$${(loss.amount || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');

        } catch (error) {
            console.error('❌ Error loading losses detail:', error);
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center py-4 text-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i> Error al cargar el detalle de pérdidas.
                    </td>
                </tr>
            `;
        }
    }
    async loadExchangeRates() {
        try {
            // TODO: Fetch real rates from API
            this.rates = {
                'USD_COP': 4200,
                'USD_VES': 36.5,
                'COP_VES': 0.009
            };
        } catch (e) {
            console.warn('⚠️ Error loading exchange rates, using defaults', e);
        }
    }
}

