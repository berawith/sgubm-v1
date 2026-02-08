/**
 * Payments Module - Frontend para gestión de pagos
 */
export class PaymentsModule {
    constructor(api, eventBus, viewManager) {
        this.api = api;
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.payments = [];
        this.statistics = null;
        this.filterState = {
            startDate: '',
            endDate: '',
            method: '',
            search: ''
        };
        this.searchTimeout = null;
        this.batchClients = [];
        this.selectedBatchIds = new Set();

        console.log('💰 Payments Module initialized');
    }

    async load() {
        console.log('💰 Loading Payments...');
        this.showView();
        this.startClock();
        this.initAutomationParams();

        // Load with current filters
        await Promise.all([
            this.loadPayments(),
            this.loadStatistics()
        ]);

        // Initialize chart after loading data
        this.initChart();
    }

    startClock() {
        if (this.clockInterval) clearInterval(this.clockInterval);
        const update = () => {
            const now = new Date();
            const timeEl = document.getElementById('live-time');
            const dateEl = document.getElementById('live-date');

            if (timeEl) {
                timeEl.textContent = now.toLocaleTimeString('es-ES', {
                    hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'
                });
            }
            if (dateEl) {
                dateEl.textContent = now.toLocaleDateString('es-ES', {
                    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
                });
            }
        };
        update();
        this.clockInterval = setInterval(update, 1000);
    }

    showView() {
        // Delegar visualización a ViewManager
        this.viewManager.showMainView('payments');

        // Default to list tab if no tab is active
        if (!document.querySelector('.finance-tab.active')) {
            this.switchTab('list');
        }
    }

    switchTab(tabName) {
        // Update Buttons
        document.querySelectorAll('.segment-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = document.querySelector(`.segment-btn[onclick*="'${tabName}'"]`);
        if (activeBtn) activeBtn.classList.add('active');

        // Update Content
        document.querySelectorAll('.finance-tab').forEach(tab => tab.style.display = 'none');
        document.querySelectorAll('.finance-tab').forEach(tab => tab.classList.remove('active'));

        const targetTab = document.getElementById(`finance-${tabName}-tab`);
        if (targetTab) {
            targetTab.style.display = 'block';
            targetTab.classList.add('active');
        }

        // Load data based on tab
        if (tabName === 'list') {
            this.loadPayments();
        } else if (tabName === 'invoices') {
            this.loadInvoices();
        } else if (tabName === 'reports') {
            this.loadStatistics();
        } else if (tabName === 'promises') {
            this.loadPromises();
        } else if (tabName === 'batch') {
            this.loadRoutersForBatch();
            this.loadBatchClients();
        } else if (tabName === 'automation') {
            this.loadRouters();
        } else if (tabName === 'trash') {
            this.loadDeletedPayments();
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
        if (amountEl) amountEl.textContent = `$${totalAmount.toLocaleString()}`;
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
                        $${(d.amount || 0).toLocaleString()}
                    </div>
                    <div style="font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em;">
                        ${d.currency || 'COP'}
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
                        ${new Date(d.deleted_at).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })} 
                        por <strong style="color: #64748b;">${d.deleted_by || 'admin'}</strong>
                    </div>
                </td>
                <td>
                    <div style="font-style: italic; color: #64748b; font-size: 0.85rem; line-height: 1.4;">
                        ${d.reason || 'Sin motivo especificado'}
                    </div>
                </td>
                <td style="text-align: right;">
                    <button class="action-btn-mini success" onclick="app.modules.payments.restorePayment(${d.id})" title="Restaurar Pago">
                        <i class="fas fa-undo"></i> Restaurar
                    </button>
                </td>
            </tr>
            `;
        }).join('');

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
            if (window.app) app.showLoading(false);

            if (window.toast) toast.success('Pago restaurado exitosamente');
            this.loadDeletedPayments();
            this.loadPayments();
            this.loadStatistics();
        } catch (e) {
            if (window.app) app.showLoading(false);
            console.error(e);
            const errText = e.data && e.data.error ? e.data.error : e.message;
            if (window.toast) toast.error('Error al restaurar: ' + errText);
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
        if (this.searchTimeout) clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
            this.applyFilters();
        }, 500);
    }

    async loadPayments() {
        try {
            const params = new URLSearchParams({ limit: 1000 });
            if (this.filterState.startDate) params.append('start_date', this.filterState.startDate);
            if (this.filterState.endDate) params.append('end_date', this.filterState.endDate);
            if (this.filterState.method) params.append('method', this.filterState.method);
            if (this.filterState.search) params.append('search', this.filterState.search);

            this.payments = await this.api.get(`/api/payments?${params.toString()}`);
            this.renderPayments();
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

        tbody.innerHTML = this.invoices.map(inv => {
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
                    <div class="amount-main">$${(inv.total_amount || 0).toLocaleString()}</div>
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
            if (window.app && window.app.showLoading) window.app.showLoading(false);

            if (window.toast) window.toast.show(`Generadas: ${res.details.created}, Saltadas: ${res.details.skipped}`, 'success');
            this.loadInvoices();
        } catch (e) {
            if (window.app && window.app.showLoading) window.app.showLoading(false);
            console.error(e);
            if (window.toast) window.toast.show('Error generando facturas', 'error');
        }
    }

    async loadStatistics() {
        try {
            const params = new URLSearchParams();
            if (this.filterState.startDate) params.append('start_date', this.filterState.startDate);
            if (this.filterState.endDate) params.append('end_date', this.filterState.endDate);
            if (this.filterState.method) params.append('method', this.filterState.method);

            this.statistics = await this.api.get(`/api/payments/statistics?${params.toString()}`);
            this.renderStatistics();
        } catch (error) {
            console.error('Error loading statistics:', error);
        }
    }

    renderStatistics() {
        if (!this.statistics) return;
        const stats = this.statistics;

        const updateVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = `$${(val || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
        };

        updateVal('pay-stat-today', stats.totals.today || 0);

        if (this.filterState.startDate || this.filterState.endDate) {
            updateVal('pay-stat-month', stats.totals.filtered || 0);
            const monthLabel = document.querySelector('.payment-stat-icon.month')?.nextElementSibling?.querySelector('h4');
            if (monthLabel) monthLabel.textContent = 'Periodo Seleccionado';
        } else {
            updateVal('pay-stat-month', stats.totals.month || 0);
            const monthLabel = document.querySelector('.payment-stat-icon.month')?.nextElementSibling?.querySelector('h4');
            if (monthLabel) monthLabel.textContent = 'Este Mes';
        }

        updateVal('pay-stat-total', stats.totals.all_time || 0);
        updateVal('pay-stat-pending', stats.totals.total_pending_debt || 0);

        const paidEl = document.getElementById('pay-stat-clients-paid');
        if (paidEl) paidEl.textContent = stats.counts.paid_clients || 0;

        const pendingEl = document.getElementById('pay-stat-clients-pending');
        if (pendingEl) pendingEl.textContent = stats.counts.debt_clients || 0;

        this.renderMethodBreakdown(stats.payment_methods || {});

        // Update Chart
        this.initChart();
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
        if (window.toast) toast.info('Generando reporte de morosos...');
        window.open('/api/payments/export-debtors', '_blank');
    }

    openReportModal() {
        const modal = document.getElementById('modal-report-config');
        if (!modal) return;

        // Inicializar fechas por defecto (mes actual)
        const now = new Date();
        const start = new Date(now.getFullYear(), now.getMonth(), 1);

        document.getElementById('report-date-start').value = start.toISOString().split('T')[0];
        document.getElementById('report-date-end').value = now.toISOString().split('T')[0];

        modal.classList.add('active');
    }

    closeReportModal() {
        const modal = document.getElementById('modal-report-config');
        if (modal) modal.classList.remove('active');
    }

    onReportTypeChange() {
        const type = document.getElementById('report-type').value;
        const dateRangeGroup = document.getElementById('report-date-range-group');
        const methodGroup = document.getElementById('report-method').closest('.form-group');
        const formatPdf = document.querySelector('input[name="report-format"][value="pdf"]').closest('.format-option');

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
        const type = document.getElementById('report-type').value;
        const startDate = document.getElementById('report-date-start').value;
        const endDate = document.getElementById('report-date-end').value;
        const method = document.getElementById('report-method').value;
        const format = document.querySelector('input[name="report-format"]:checked')?.value;

        let params = new URLSearchParams({
            method: method,
            report_type: type
        });

        if (type === 'payments') {
            if (!startDate || !endDate) {
                if (window.toast) toast.warning('Seleccione el rango de fechas');
                return;
            }
            params.append('start_date', startDate);
            params.append('end_date', endDate);
        } else if (type === 'today') {
            const today = new Date().toISOString().split('T')[0];
            params.append('start_date', today);
            params.append('end_date', today);
        }

        if (window.toast) toast.info(`Generando reporte ${format.toUpperCase()}...`);

        let endpoint = '/api/payments/export';
        if (format === 'pdf') endpoint = '/api/payments/export-pdf';
        if (format === 'excel') endpoint = '/api/payments/export-excel';

        // Redirigir morosos si es necesario (ya que el backend tiene un endpoint separado por ahora)
        if (type === 'debtors' && format === 'csv') {
            window.open('/api/payments/export-debtors', '_blank');
        } else {
            window.open(`${endpoint}?${params.toString()}`, '_blank');
        }

        this.closeReportModal();
    }

    initChart() {
        const ctx = document.getElementById('revenue-chart');
        if (!ctx) return;

        if (this.revenueChart) {
            this.revenueChart.destroy();
        }

        const trend = this.statistics?.annual_trend || [];
        if (trend.length === 0) return;

        const labels = trend.map(t => t.label);
        const collectedData = trend.map(t => t.collected);

        const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(0, 242, 254, 0.8)');
        gradient.addColorStop(1, 'rgba(0, 242, 254, 0.1)');

        this.revenueChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Recaudado',
                    data: collectedData,
                    backgroundColor: gradient,
                    borderRadius: 8,
                    hoverBackgroundColor: '#00f2fe',
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const monthData = trend[index];
                        this.showMonthDetailModal(monthData);
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1a1a2e',
                        titleColor: '#fff',
                        bodyColor: '#00f2fe',
                        padding: 12,
                        callbacks: {
                            label: (context) => `Recaudado: $${context.parsed.y.toLocaleString()} `
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.5)',
                            callback: (val) => `$${val.toLocaleString()} `
                        }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: 'rgba(255, 255, 255, 0.5)' }
                    }
                }
            }
        });
    }

    async showClientHistoryModal(clientId) {
        const modal = document.getElementById('client-history-modal');
        if (!modal) return;

        const container = document.getElementById('client-history-list');
        if (container) {
            container.innerHTML = '<div style="padding: 20px; text-align:center;"><div class="spinner"></div> Cargando historial...</div>';
        }

        modal.classList.add('active');

        // Reset header info initially
        const nameEl = document.getElementById('history-client-name');
        if (nameEl) nameEl.textContent = 'Cliente #' + clientId;

        try {
            // Fetch payments filtered by client
            const [payments, client] = await Promise.all([
                this.api.get(`/api/payments?client_id=${clientId}&limit=50`),
                this.api.get(`/api/clients/${clientId}`)
            ]);

            // Update Summary Box
            const nameHeader = document.getElementById('history-header-name');
            const idHeader = document.getElementById('history-header-id');
            if (nameHeader) nameHeader.textContent = client.legal_name || 'Sin Nombre';
            if (idHeader) idHeader.textContent = client.subscriber_code || `CLI-${clientId}`;

            // Render
            if (container) {
                if (payments.length === 0) {
                    container.innerHTML = `
                        <div style="text-align:center; padding: 60px; color: #94a3b8;">
                            <i class="fas fa-file-invoice-dollar" style="font-size: 3rem; opacity:0.1; margin-bottom:15px; display:block;"></i>
                            <p style="font-weight:600; font-size:1.1rem; color:#1e293b;">Sin movimientos financieros</p>
                            <p style="font-size:0.85rem; opacity:0.7;">Este cliente no ha registrado pagos en el sistema.</p>
                        </div>
                     `;
                } else {
                    const methodMap = {
                        'cash': 'Efectivo',
                        'transfer': 'Transferencia',
                        'card': 'Tarjeta',
                        'zelle': 'Zelle',
                        'pago_movil': 'Pago Móvil',
                        'other': 'Otro'
                    };

                    const statusMap = {
                        'paid': 'PAGADO',
                        'verified': 'PAGADO',
                        'pending': 'PENDIENTE',
                        'cancelled': 'ANULADO'
                    };

                    const html = `
                        <div class="table-container-premium" style="margin:0; box-shadow:none; background:transparent;">
                            <table class="premium-data-table" style="border-spacing: 0 4px;">
                                <thead>
                                    <tr>
                                        <th>Recibo #</th>
                                        <th>Fecha / Hora</th>
                                        <th>Referencia</th>
                                        <th>Monto (COP)</th>
                                        <th>Método</th>
                                        <th>Estado</th>
                                        <th style="text-align:right">Acciones</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${payments.map(p => {
                        const methodName = methodMap[p.payment_method] || p.payment_method;
                        const statusName = statusMap[p.status] || p.status;
                        const statusClass = p.status === 'paid' || p.status === 'verified' ? 'success' : (p.status === 'pending' ? 'warning' : 'danger');

                        return `
                                        <tr class="premium-row" style="background: rgba(255,255,255,0.5);">
                                            <td>
                                                <span class="id-badge" style="background:#0f172a; color:#38bdf8; font-weight:800; padding: 4px 10px;">
                                                    #${String(p.id).padStart(4, '0')}
                                                </span>
                                            </td>
                                            <td>
                                                <div class="date-wrapper">
                                                    <i class="far fa-calendar-alt"></i>
                                                    <div style="display:flex; flex-direction:column;">
                                                        <span style="font-weight:750; color:#1e293b;">${new Date(p.payment_date).toLocaleDateString()}</span>
                                                        <span style="font-size:0.75rem; color:#94a3b8;">${new Date(p.payment_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                                    </div>
                                                </div>
                                            </td>
                                            <td><span class="id-badge" style="background:white; border:1px solid #e2e8f0; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;">${p.reference || '---'}</span></td>
                                            <td>
                                                <div class="amount-cell-premium">
                                                    <div class="amount-main" style="color:#0f172a; font-size: 1.1rem;">$${p.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                                                    <div class="amount-sub" style="letter-spacing: 0.1em;">COP TRANSACCIÓN</div>
                                                </div>
                                            </td>
                                            <td>
                                                <span class="premium-status-badge secondary" style="background:white; border:1px solid #e2e8f0; padding: 5px 10px; font-size: 0.7rem;">
                                                    <i class="fas ${p.payment_method === 'cash' ? 'fa-wallet' : 'fa-university'}"></i>
                                                    ${methodName.toUpperCase()}
                                                </span>
                                            </td>
                                            <td>
                                                <span class="premium-status-badge ${statusClass}" style="font-size:0.65rem; padding: 5px 10px;">
                                                    <i class="fas ${statusClass === 'success' ? 'fa-check-circle' : 'fa-clock'}"></i>
                                                    ${statusName}
                                                </span>
                                            </td>
                                            <td style="text-align:right;">
                                                <div style="display: flex; gap: 8px; justify-content: flex-end;">
                                                    <button class="action-btn-mini success" onclick="app.modules.payments.printReceipt(${p.id})" title="Imprimir Recibo">
                                                        <i class="fas fa-print"></i>
                                                    </button>
                                                    <button class="action-btn-mini" onclick="app.modules.payments.viewReceiptDetails(${p.id})" title="Ver Detalles">
                                                        <i class="fas fa-eye"></i>
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    `}).join('')}
                                </tbody>
                            </table>
                        </div>
                     `;
                    container.innerHTML = html;
                }
            }

        } catch (e) {
            console.error(e);
            if (container) container.innerHTML = '<div class="error-state">Error al cargar historial</div>';
            if (window.toast) toast.error('Error cargando historial del cliente');
        }
    }

    async showMonthDetailModal(monthData) {
        const modal = document.getElementById('month-detail-modal');
        if (!modal) return;

        document.getElementById('month-detail-title').textContent = `${monthData.month_name} ${monthData.year} `;
        document.getElementById('month-detail-period').textContent = 'Recaudación y Eficiencia';

        const missing = Math.max(0, monthData.billed - monthData.collected);
        const efficiency = monthData.billed > 0 ? (monthData.collected / monthData.billed) * 100 : 0;

        document.getElementById('month-val-collected').textContent = `$${monthData.collected.toLocaleString()} `;
        document.getElementById('month-val-billed').textContent = `$${monthData.billed.toLocaleString()} `;
        document.getElementById('month-val-missing').textContent = `$${missing.toLocaleString()} `;

        const fill = document.getElementById('month-efficiency-fill');
        const text = document.getElementById('month-efficiency-text');
        if (fill) fill.style.width = `${Math.min(100, efficiency)}% `;
        if (text) text.textContent = `${efficiency.toFixed(1)}% `;

        modal.classList.add('active');

        const list = document.getElementById('month-payments-list');
        if (list) {
            list.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px;">Cargando pagos...</td></tr>';
            try {
                const startStr = `${monthData.year}-${String(monthData.month).padStart(2, '0')}-01T00:00:00Z`;
                const end = new Date(monthData.year, monthData.month, 0);
                const endStr = `${monthData.year}-${String(monthData.month).padStart(2, '0')}-${String(end.getDate()).padStart(2, '0')}T23:59:59Z`;

                const response = await fetch('/api/payments/report', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ start_date: startStr, end_date: endStr })
                });

                const data = await response.json();
                const paymentsList = [];
                Object.values(data.daily_totals || {}).forEach(day => {
                    paymentsList.push(...day.payments);
                });

                if (paymentsList.length === 0) {
                    list.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px;">No hay pagos en este periodo.</td></tr>';
                } else {
                    list.innerHTML = paymentsList.map(p => `
                        <tr>
                            <td>
                                <div class="client-cell">
                                    <div class="client-avatar">${(p.client_name || 'C').charAt(0)}</div>
                                    <span>${p.client_name || 'Desconocido'}</span>
                                </div>
                            </td>
                            <td>${new Date(p.payment_date).toLocaleDateString()}</td>
                            <td><code>${p.reference || 'N/A'}</code></td>
                            <td class="amount">$${p.amount.toLocaleString()}</td>
                            <td><span class="status-badge success">Completado</span></td>
                        </tr>
                    `).join('');
                }
            } catch (error) {
                list.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px; color: var(--danger);">Error al cargar datos.</td></tr>';
            }
        }
    }

    renderPayments() {
        const container = document.getElementById('payments-list');
        if (!container) return;

        let tbody = document.getElementById('payments-table-body');
        if (!tbody) {
            container.innerHTML = `
                <div class="table-container-premium glass-panel" style="margin:0; box-shadow:none;">
                    <table class="premium-data-table" style="border-spacing: 0 2px;">
                        <thead>
                            <tr>
                                <th>ID</th>
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
                </div>
            `;
            tbody = document.getElementById('payments-table-body');
        }

        if (this.payments.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" style="text-align:center; padding: 60px; color: #94a3b8;">
                        <i class="fas fa-search-dollar" style="font-size: 2.5rem; opacity:0.1; margin-bottom:15px; display:block;"></i>
                        <p style="font-weight:600; color:#1e293b;">No hay registros</p>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = this.payments.map((payment, index) => {
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
                        <button class="action-btn-mini danger" onclick="app.modules.payments.voidPayment(${payment.id})" title="Eliminar">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
        }).join('');
    }

    renderMethodBreakdown(methods) {
        const container = document.getElementById('method-breakdown');
        if (!container) return;

        if (Object.keys(methods).length === 0) {
            container.innerHTML = '<p style="color:#94a3b8; padding:10px;">Sin datos de métodos</p>';
            return;
        }

        container.innerHTML = Object.entries(methods).map(([method, data]) => `
        <div class="method-card">
            <div class="method-card-left">
                <div class="method-icon-box">
                    <i class="fas ${method === 'cash' ? 'fa-wallet' : (method === 'transfer' ? 'fa-university' : (method === 'card' ? 'fa-credit-card' : 'fa-money-bill'))}"></i>
                </div>
                <div class="method-info">
                    <span class="method-name">${method === 'cash' ? 'Efectivo' : (method === 'transfer' ? 'Transferencia' : (method === 'card' ? 'Tarjeta' : method.toUpperCase()))}</span>
                    <span class="method-count">${data.count} transacciones</span>
                </div>
            </div>
            <div class="method-amount">$${(data.total || 0).toLocaleString()}</div>
        </div>
    `).join('');
    }

    printReceipt(id) {
        if (window.toast) window.toast.show('Generando vista de impresión...', 'info');
        window.open(`/api/payments/${id}/print`, '_blank');
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

            // Re-use new payment modal for editing
            const modal = document.getElementById('payment-modal');
            const title = document.getElementById('payment-modal-title');
            if (title) title.innerText = 'Editar Pago #' + paymentId;

            // Cambiar texto del botón a "Actualizar Pago"
            const submitText = document.getElementById('payment-submit-text');
            if (submitText) submitText.innerText = 'Actualizar Pago';

            // Fill fields
            document.getElementById('payment-client-id').value = p.client_id;
            document.getElementById('pay-amount').value = p.amount;
            document.getElementById('pay-currency').value = p.currency || 'COP';
            document.getElementById('pay-method').value = p.payment_method || 'cash';
            document.getElementById('pay-reference').value = p.reference || '';
            document.getElementById('pay-notes').value = p.notes || '';

            // Date handling (assuming YYYY-MM-DD for input type="date")
            if (p.payment_date) {
                const date = new Date(p.payment_date);
                document.getElementById('pay-date').value = date.toISOString().split('T')[0];
            }

            // Show details view immediately (skip search)
            document.getElementById('payment-client-search-step').style.display = 'none';
            document.getElementById('selected-client-display').style.display = 'block';
            document.getElementById('payment-details-fields').style.display = 'block';

            // Set client info in display
            document.getElementById('display-client-name').innerText = p.client_name || 'Cliente';
            document.getElementById('display-client-code').innerText = p.subscriber_code || '';

            // ===== POPULATE DEBT/STATUS INFORMATION =====
            const debtContainer = document.getElementById('display-client-debt-info');
            if (debtContainer) {
                const balance = p.account_balance || 0;
                const status = p.client_status || 'active';

                // Determinar badge de estado según cliente
                let statusLabel, statusClass, statusIcon, statusBg;

                if (balance <= 0 && status === 'active') {
                    statusLabel = 'PAGO Y ACTIVO';
                    statusClass = 'success';
                    statusIcon = 'fa-check-circle';
                    statusBg = 'rgba(22, 163, 74, 0.1)';
                } else if (balance > 0 && status === 'active') {
                    statusLabel = 'PENDIENTE';
                    statusClass = 'warning';
                    statusIcon = 'fa-exclamation-circle';
                    statusBg = 'rgba(234, 88, 12, 0.1)';
                } else if (status === 'suspended') {
                    statusLabel = 'SUSPENDIDO';
                    statusClass = 'danger';
                    statusIcon = 'fa-pause-circle';
                    statusBg = 'rgba(220, 38, 38, 0.1)';
                } else if (status === 'cut' || status === 'inactive') {
                    statusLabel = 'CORTADO';
                    statusClass = 'secondary';
                    statusIcon = 'fa-ban';
                    statusBg = 'rgba(100, 116, 139, 0.1)';
                } else {
                    statusLabel = status.toUpperCase();
                    statusClass = 'secondary';
                    statusIcon = 'fa-circle';
                    statusBg = 'rgba(100, 116, 139, 0.1)';
                }

                // Calcular mes de deuda (aproximado)
                const monthlyFee = p.monthly_fee || 0;
                const monthsOfDebt = monthlyFee > 0 ? Math.ceil(balance / monthlyFee) : 0;
                const debtMonthsText = monthsOfDebt > 0 ? `${monthsOfDebt} mes${monthsOfDebt > 1 ? 'es' : ''}` : 'N/A';

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

            // ===== POPULATE AUDIT INFORMATION BOX =====
            const auditBox = document.getElementById('payment-audit-box');
            if (auditBox) {
                auditBox.style.display = 'block'; // Mostrar el cuadro azul

                const layoutDivider = document.getElementById('layout-divider-v');
                if (layoutDivider) layoutDivider.style.display = 'block';

                // ID de Operación
                const auditIdEl = document.getElementById('audit-payment-id');
                if (auditIdEl) auditIdEl.innerText = `#${String(p.id).padStart(4, '0')}`;

                // Fecha y Hora exactas
                if (p.payment_date) {
                    const paymentDateTime = new Date(p.payment_date);

                    // Fecha: formato DD/MM/YYYY
                    const auditDateEl = document.getElementById('audit-payment-date');
                    if (auditDateEl) {
                        auditDateEl.innerText = paymentDateTime.toLocaleDateString('es-ES', {
                            day: '2-digit',
                            month: '2-digit',
                            year: 'numeric'
                        });
                    }

                    // Hora: formato 12 horas con AM/PM
                    const auditTimeEl = document.getElementById('audit-payment-time');
                    if (auditTimeEl) {
                        auditTimeEl.innerText = paymentDateTime.toLocaleTimeString('es-ES', {
                            hour12: true,
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit'
                        });
                    }
                }
            }

            // Mark as edit mode
            modal.dataset.mode = 'edit';
            modal.dataset.paymentId = paymentId;

            modal.classList.add('active');
            this.toggleMethodFields();
        } catch (e) {
            console.error(e);
            if (window.toast) toast.error('Error al cargar pago: ' + e);
        }
    }

    async voidPayment(id) {
        let reason = prompt('¿Por qué deseas anular este pago?\n(Esta acción moverá el pago a la papelera y restaurará la deuda del cliente)');
        if (reason === null) return; // Cancelled
        if (!reason.trim()) reason = 'Sin motivo especificado';

        try {
            if (window.app) app.showLoading(true);
            await this.api.delete(`/api/payments/${id}?reason=${encodeURIComponent(reason)}`);
            if (window.app) app.showLoading(false);

            if (window.toast) window.toast.show('Pago anulado y movido a papelera', 'success');
            this.loadPayments();
            this.loadStatistics();
        } catch (e) {
            if (window.app) app.showLoading(false);
            console.error(e);
            const errText = e.data && e.data.error ? e.data.error : e.message;
            if (window.toast) window.toast.show('Error al anular pago: ' + errText, 'error');
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

    async loadRouters() {
        try {
            const routers = await this.api.get('/api/routers');
            const select = document.getElementById('automation-router-id');
            if (select) {
                const currentVal = select.value;
                select.innerHTML = '<option value="">-- Seleccionar Router --</option>' +
                    routers.map(r => `<option value="${r.id}">${r.alias}</option>`).join('');
                if (currentVal) select.value = currentVal;
            }
        } catch (e) {
            console.error("Error loading routers for automation", e);
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
            if (window.app) app.showLoading(false);

            if (response.success) {
                if (window.toast) toast.success('Ciclo iniciado correctamente.');
                this.loadStatistics();
            } else {
                if (window.toast) toast.error('Error: ' + response.message);
            }
        } catch (error) {
            if (window.app) app.showLoading(false);
            console.error(error);
            if (window.toast) toast.error('Error al ejecutar el ciclo');
        }
    }

    showNewPaymentModal(preSelectedClient = null) {
        const modal = document.getElementById('payment-modal');
        const form = document.getElementById('payment-form');
        if (!modal || !form) return;

        form.reset();

        // Hide details, show search
        document.getElementById('payment-client-search-step').style.display = 'block';
        document.getElementById('selected-client-display').style.display = 'none';
        document.getElementById('payment-details-fields').style.display = 'none';
        this.hideSearchResults();

        modal.classList.add('active');

        // Mode handling
        delete modal.dataset.mode;
        delete modal.dataset.paymentId;
        const title = modal.querySelector('h3');
        if (title) title.innerText = 'Registrar Nuevo Pago';

        // Set Default Date
        const dateEl = document.getElementById('pay-date');
        if (dateEl) {
            dateEl.value = new Date().toISOString().split('T')[0];
        }

        if (preSelectedClient) {
            this.selectClient(preSelectedClient);
        } else {
            // Auto-focus search after animation
            setTimeout(() => {
                const searchInput = document.getElementById('payment-client-query');
                if (searchInput) searchInput.focus();
            }, 300);
        }

        this.initModalSearchListeners();
    }

    initModalSearchListeners() {
        const searchInput = document.getElementById('payment-client-query');
        const form = document.getElementById('payment-form');

        if (searchInput && !searchInput.dataset.listenerAttached) {
            let timeout = null;

            // On input (debounce)
            searchInput.addEventListener('input', (e) => {
                const query = e.target.value.trim();
                clearTimeout(timeout);
                if (query.length < 2) {
                    this.hideSearchResults();
                    return;
                }
                timeout = setTimeout(() => this.searchClients(query), 400);
            });

            // On enter
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    clearTimeout(timeout);
                    this.searchClients(e.target.value.trim());
                }
            });

            searchInput.dataset.listenerAttached = 'true';
        }

        if (form && !form.dataset.listenerAttached) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.submitPayment();
            });
            form.dataset.listenerAttached = 'true';
        }

        // Click outside search
        if (!document.dataset.searchClickBound) {
            document.addEventListener('click', (e) => {
                const results = document.getElementById('payment-search-results');
                const query = document.getElementById('payment-client-query');
                if (results && query && !results.contains(e.target) && !query.contains(e.target)) {
                    this.hideSearchResults();
                }
            });
            document.dataset.searchClickBound = 'true';
        }
    }

    toggleMethodFields() {
        const method = document.getElementById('pay-method').value;
        const refGroup = document.getElementById('group-reference');
        const originGroup = document.getElementById('group-origin');

        if (method === 'transfer') {
            if (refGroup) refGroup.style.display = 'block';
            if (originGroup) originGroup.style.display = 'block';
        } else if (method === 'cash') {
            if (refGroup) refGroup.style.display = 'none';
            if (originGroup) originGroup.style.display = 'none';
        } else {
            if (refGroup) refGroup.style.display = 'block';
            if (originGroup) originGroup.style.display = 'none';
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

    async submitPayment() {
        const clientId = document.getElementById('payment-client-id').value;
        if (!clientId) {
            if (window.toast) toast.error('Seleccione un cliente');
            return;
        }

        const modal = document.getElementById('payment-modal');
        const isEdit = modal.dataset.mode === 'edit';
        const paymentId = modal.dataset.paymentId;

        const dateEl = document.getElementById('pay-date');
        const data = {
            amount: parseFloat(document.getElementById('pay-amount').value),
            payment_method: document.getElementById('pay-method').value,
            reference: document.getElementById('pay-reference').value,
            notes: document.getElementById('pay-notes').value,
            currency: document.getElementById('pay-currency').value,
            payment_date: dateEl ? dateEl.value : new Date().toISOString(),
            authorized: false // Default
        };

        // Verificar si cliente necesita reactivación (solo para nuevos pagos, no ediciones)
        let shouldReactivate = false;
        if (!isEdit && this.selectedClient) {
            const status = this.selectedClient.status;
            if (status === 'suspended' || status === 'cut' || status === 'inactive') {
                const action = await this.showReactivationConfirm(
                    this.selectedClient.legal_name || 'Cliente',
                    status
                );
                shouldReactivate = (action === 'reactivate');
            }
        }

        if (window.app) app.showLoading(true);
        try {
            let res;
            if (isEdit) {
                res = await this.api.put(`/api/payments/${paymentId}`, data);
                if (window.toast) toast.success('Pago actualizado correctamente');
            } else {
                try {
                    res = await this.api.post(`/api/clients/${clientId}/register-payment`, data);
                } catch (error) {
                    const errText = error.data && error.data.error ? error.data.error : error.message;
                    if (errText && errText.includes('PARTIAL_PAYMENT_REQUIRED')) {
                        if (window.app) app.showLoading(false);
                        const msg = errText.split('|')[1] || '¿Confirmar abono parcial?';
                        if (confirm(msg + '\n\nPresiona ACEPTAR para autorizar este abono parcial o CANCELAR para corregir el monto.')) {
                            if (window.app) app.showLoading(true);
                            data.authorized = true;
                            res = await this.api.post(`/api/clients/${clientId}/register-payment`, data);
                        } else {
                            return;
                        }
                    } else {
                        throw error;
                    }
                }
                if (window.toast) toast.success('Pago registrado correctamente');
            }

            // Si se debe reactivar el servicio
            if (shouldReactivate && !isEdit) {
                try {
                    await this.api.post(`/api/clients/${clientId}/activate`, {});
                    if (window.toast) toast.success('¡Servicio reactivado exitosamente!');
                } catch (error) {
                    console.error('Error reactivating service:', error);
                    if (window.toast) toast.error('Pago registrado, pero error al reactivar servicio');
                }
            }

            if (window.app) app.showLoading(false);
            if (modal) {
                modal.classList.remove('active');
                // Reset mode
                delete modal.dataset.mode;
                delete modal.dataset.paymentId;
            }

            this.loadPayments();
            this.loadStatistics();

            // Notificar a otros módulos (como Clientes) para que refresquen su UI
            if (this.eventBus) {
                this.eventBus.publish('payment_saved', { client_id: clientId });
            }

        } catch (e) {
            if (window.app) app.showLoading(false);
            const errText = e.data && e.data.error ? e.data.error : e.message;
            if (window.toast) toast.error('Error al procesar pago: ' + errText);
        }
    }

    // --- BATCH OPERATIONS ---

    async loadRoutersForBatch() {
        try {
            const routers = await this.api.get('/api/routers');
            const select = document.getElementById('batch-filter-router');
            if (select && select.options.length <= 1) { // Only if not loaded
                select.innerHTML = '<option value="">Todos los Routers</option>' +
                    routers.map(r => `<option value="${r.id}">${r.alias}</option>`).join('');
            }
        } catch (e) {
            console.error("Error loading routers for batch", e);
        }
    }

    async loadBatchClients() {
        const routerId = document.getElementById('batch-filter-router').value;
        const status = document.getElementById('batch-filter-status').value;
        const search = document.getElementById('batch-search') ? document.getElementById('batch-search').value : '';
        const tbody = document.getElementById('batch-clients-table');

        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px;">Cargando...</td></tr>';

        try {
            const params = new URLSearchParams({ limit: 500 }); // Limit high for batch
            if (routerId) params.append('router_id', routerId);
            if (status) params.append('status', status);
            if (search) params.append('search', search);

            // Using clients endpoint
            this.batchClients = await this.api.get(`/api/clients?${params.toString()}`);
            this.renderBatchClients();
        } catch (error) {
            console.error('Error loading batch clients:', error);
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px; color:red;">Error al cargar clientes</td></tr>';
        }
    }

    renderBatchClients() {
        const tbody = document.getElementById('batch-clients-table');
        const countSpan = document.getElementById('batch-selected-count');

        if (!tbody) return;

        // Reset selection on re-render? Or keep? Reset is safer to avoid ID mismatch.
        this.selectedBatchIds = new Set();
        if (countSpan) countSpan.textContent = '0';
        const header = document.getElementById('batch-select-all-header');
        if (header) header.checked = false;

        if (!this.batchClients || this.batchClients.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 30px;">No se encontraron clientes</td></tr>';
            return;
        }

        tbody.innerHTML = this.batchClients.map(c => `
            <tr>
                <td>
                    <input type="checkbox" class="batch-checkbox" value="${c.id}" onchange="app.modules.payments.updateBatchSelection(this)">
                </td>
                <td>
                    <div style="font-weight: 600;">${c.legal_name || c.username}</div>
                    <div style="font-size: 0.8rem; color: #64748b;">${c.subscriber_code || '---'}</div>
                </td>
                <td>${c.ip_address || '---'}</td>
                <td>
                    <div style="display:flex; flex-direction:column; gap:4px;">
                        <!-- Estado Servicio (Router) -->
                        <span class="badge-status-table ${c.status === 'active' ? 'verified' : (c.status === 'suspended' ? 'danger' : 'warning')}" 
                              style="font-size:0.75rem; padding: 2px 8px; width:fit-content;">
                            <i class="fas ${c.status === 'active' ? 'fa-wifi' : 'fa-ban'}"></i>
                            ${c.status === 'active' ? 'ACTIVO' : 'CORTADO'}
                        </span>
                    </div>
                </td>
                <td>
                     <!-- Estado Financiero -->
                    <span class="badge-status-table ${c.account_balance > 0 ? 'warning' : 'success'}" 
                          style="font-size:0.75rem; padding: 2px 8px; width:fit-content; background:${c.account_balance > 0 ? '#fff3cd' : '#d1fae5'}; color:${c.account_balance > 0 ? '#b45309' : '#065f46'}; border:1px solid ${c.account_balance > 0 ? '#fcd34d' : '#34d399'};">
                        <i class="fas ${c.account_balance > 0 ? 'fa-clock' : 'fa-check-circle'}"></i>
                        ${c.account_balance > 0 ? 'PENDIENTE' : 'AL DÍA'}
                    </span>
                </td>
                <td style="font-family: monospace; font-weight: 700;">
                    $${(c.account_balance || 0).toLocaleString()}
                </td>
            </tr>
        `).join('');
    }

    updateBatchSelection(checkbox) {
        const id = parseInt(checkbox.value);
        if (checkbox.checked) {
            this.selectedBatchIds.add(id);
        } else {
            this.selectedBatchIds.delete(id);
        }
        document.getElementById('batch-selected-count').textContent = this.selectedBatchIds.size;
    }

    toggleSelectAllBatch(source) {
        const header = document.getElementById('batch-select-all-header');

        if (source === 'button') {
            header.checked = !header.checked;
        }

        const checkboxes = document.querySelectorAll('.batch-checkbox');
        const isChecked = header.checked;

        checkboxes.forEach(cb => {
            cb.checked = isChecked;
            const id = parseInt(cb.value);
            if (isChecked) this.selectedBatchIds.add(id);
            else this.selectedBatchIds.delete(id);
        });

        document.getElementById('batch-selected-count').textContent = this.selectedBatchIds.size;
    }

    async executeBatch(action) {
        const ids = Array.from(this.selectedBatchIds);
        if (ids.length === 0) {
            if (window.toast) toast.warning('Seleccione al menos un cliente');
            return;
        }

        let actionName = action === 'suspend' ? 'SUSPENDER' : 'RESTAURAR';
        const confirmMsg = `¿Estás seguro de ${actionName} a ${ids.length} clientes seleccionados?\n\nEsta acción afectará el servicio en el Router MikroTik.`;

        if (!confirm(confirmMsg)) return;

        try {
            if (window.app) app.showLoading(true);

            const response = await this.api.post('/api/batch/execute', {
                action: action,
                client_ids: ids
            });

            if (window.app) app.showLoading(false);

            if (response.success) {
                if (window.toast) toast.success(`Acción masiva completada. Éxito: ${response.details.success_count}, Fallos: ${response.details.fail_count}`);
                this.loadBatchClients(); // Reload to see status changes
            } else {
                if (window.toast) toast.error('Error: ' + response.message);
            }
        } catch (e) {
            if (window.app) app.showLoading(false);
            console.error(e);
            if (window.toast) toast.error('Error al ejecutar acción masiva');
        }
    }
    async loadRoutersForBatch() {
        try {
            const routers = await this.api.get('/api/routers');
            const select = document.getElementById('batch-router-id');
            if (select) {
                select.innerHTML = '<option value="">Todos los Routers</option>' +
                    routers.map(r => `<option value="${r.id}">${r.alias}</option>`).join('');
            }
        } catch (error) {
            console.error('Error loading routers for batch:', error);
        }
    }

    initAutomationParams() {
        const now = new Date();
        const yearEl = document.getElementById('automation-year');
        const monthEl = document.getElementById('automation-month');

        if (yearEl) yearEl.value = now.getFullYear();
        if (monthEl) monthEl.value = now.getMonth() + 1;
    }
}
