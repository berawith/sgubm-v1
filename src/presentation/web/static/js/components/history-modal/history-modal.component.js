import { BaseModal } from '../shared/base-modal.component.js';

/**
 * Componente para mostrar el historial financiero de un cliente
 */
export class HistoryModal extends BaseModal {
    constructor(api, eventBus) {
        super('history', api, eventBus);
        this.currentClientId = null;
    }

    async init() {
        await this.loadResources(
            '/static/js/components/history-modal/history-modal.template.html'
        );
    }

    /**
     * @param {object} data - { client: {...} }
     */
    async open(data = {}) {
        await this._initPromise;
        let client = data.client;

        // Fallback: if we only have clientId, fetch the client object
        if (!client && data.clientId) {
            try {
                this.showLoading();
                client = await this.api.get(`/api/clients/${data.clientId}`);
            } catch (error) {
                console.error('Error fetching client for HistoryModal:', error);
                this.showError('Error al cargar datos del cliente');
                return;
            } finally {
                this.hideLoading();
            }
        }

        if (!client) {
            console.error('No client provided to HistoryModal');
            return;
        }

        this.currentClientId = client.id;
        this.isOpen = true; // Flag for resize listener

        // Reset and open
        super.open();

        // Populate header
        const nameHeader = this.modalElement.querySelector('#history-header-name');
        const idHeader = this.modalElement.querySelector('#history-header-id');
        if (nameHeader) nameHeader.textContent = client.legal_name || 'Sin Nombre';
        if (idHeader) idHeader.textContent = client.subscriber_code || `CLI-${client.id}`;

        const container = this.modalElement.querySelector('#history-loading-placeholder');
        if (container) {
            container.style.display = 'block';
            container.innerHTML = '<div class="spinner"></div><p style="margin-top:15px; color: #64748b;">Cargando historial...</p>';
        }

        // Hidden views until data
        const tableView = this.modalElement.querySelector('#history-table-view');
        const cardsView = this.modalElement.querySelector('#history-cards-view');
        if (tableView) tableView.style.display = 'none';
        if (cardsView) cardsView.style.display = 'none';

        await this.loadHistory();
    }

    onClose() {
        this.isOpen = false; // Reset flag
        super.onClose();
    }

    async loadHistory() {
        try {
            const payments = await this.api.get(`/api/payments?client_id=${this.currentClientId}&limit=50`);
            this.lastPaymentsData = payments; // Cache data
            this.renderHistory(payments);
        } catch (error) {
            console.error('Error loading history:', error);
            const container = this.modalElement.querySelector('#history-loading-placeholder');
            if (container) {
                container.innerHTML = `<div style="padding: 40px; text-align:center; color: #ef4444;">Error cargando historial: ${error.message}</div>`;
            }
        }
    }

    renderHistory(payments) {
        this.isMobile = window.innerWidth < 1100;
        console.log(`[HistoryModal] Rendering. isMobile: ${this.isMobile}, width: ${window.innerWidth}`);
        const tableView = this.modalElement.querySelector('#history-table-view');
        const cardsView = this.modalElement.querySelector('#history-cards-view');
        const loadingPlaceholder = this.modalElement.querySelector('#history-loading-placeholder');

        if (loadingPlaceholder) loadingPlaceholder.style.display = 'none';

        // Definir mapeos comunes
        this.methodMap = {
            'cash': 'Efectivo',
            'transfer': 'Transferencia',
            'card': 'Tarjeta',
            'zelle': 'Zelle',
            'pago_movil': 'Pago Móvil',
            'other': 'Otro'
        };

        this.statusMap = {
            'paid': 'PAGADO',
            'verified': 'PAGADO',
            'pending': 'PENDIENTE',
            'cancelled': 'ANULADO'
        };

        if (!payments || payments.length === 0) {
            if (tableView) tableView.style.display = 'none';
            if (cardsView) cardsView.style.display = 'block';
            const cardsGrid = this.modalElement.querySelector('#client-history-cards-grid');
            if (cardsGrid) {
                cardsGrid.innerHTML = `
                    <div style="text-align:center; padding: 60px; color: #94a3b8; grid-column: 1/-1;">
                        <i class="fas fa-file-invoice-dollar" style="font-size: 3rem; opacity:0.1; margin-bottom:15px; display:block;"></i>
                        <p style="font-weight:600; font-size:1.1rem; color:#1e293b;">Sin movimientos financieros</p>
                        <p style="font-size:0.85rem; opacity:0.7;">Este cliente no ha registrado pagos en el sistema.</p>
                    </div>
                `;
            }
            return;
        }

        if (this.isMobile) {
            if (tableView) tableView.style.display = 'none';
            if (cardsView) cardsView.style.display = 'block';
            this.renderHistoryCards(payments);
        } else {
            if (cardsView) cardsView.style.display = 'none';
            if (tableView) tableView.style.display = 'block';
            this.renderHistoryTable(payments);
        }

        // Add resize listener only once
        if (!this._resizeAttached) {
            window.addEventListener('resize', () => {
                if (this.isOpen && this.lastPaymentsData) {
                    const wasMobile = this.isMobile;
                    this.isMobile = window.innerWidth < 1100;
                    if (wasMobile !== this.isMobile) {
                        this.renderHistory(this.lastPaymentsData);
                    }
                }
            });
            this._resizeAttached = true;
        }
    }

    renderHistoryTable(payments) {
        const container = this.modalElement.querySelector('#client-history-list');
        if (!container) return;

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
            const methodName = this.methodMap[p.payment_method] || p.payment_method;
            const statusName = this.statusMap[p.status] || p.status;
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
                                            ${p.status !== 'cancelled' ? `
                                            <button class="action-btn-mini danger" onclick="app.modules.payments.showRevertPaymentModal(${p.id}, ${p.client_id}, '${p.payment_date}')" title="Revertir Pago">
                                                <i class="fas fa-undo"></i>
                                            </button>
                                            ` : ''}
                                        </div>
                                    </td>
                                </tr>
                            `;
        }).join('')}
                    </tbody>
                </table>
            </div>
        `;
        container.innerHTML = html;
    }

    renderHistoryCards(payments) {
        const container = this.modalElement.querySelector('#client-history-cards-grid');
        if (!container) return;

        const html = payments.map(p => {
            const statusClass = p.status === 'paid' || p.status === 'verified' ? 'success' : (p.status === 'pending' ? 'warning' : 'danger');
            const methodName = this.methodMap[p.payment_method] || p.payment_method;

            return `
                <div class="payment-card-premium slideInDown">
                    <div class="card-header-premium">
                        <div class="receipt-id">#${String(p.id).padStart(4, '0')}</div>
                        <span class="premium-status-badge ${statusClass}">${this.statusMap[p.status]}</span>
                    </div>

                    <div class="card-body-premium">
                        <div class="main-info">
                            <div class="amount-value-premium">$${p.amount.toLocaleString(undefined, { minimumFractionDigits: 0 })} <span class="currency">COP</span></div>
                            <div class="method-badge-premium">
                                <i class="fas ${p.payment_method === 'cash' ? 'fa-wallet' : 'fa-university'}"></i>
                                ${methodName}
                            </div>
                        </div>

                        <div class="meta-info-grid">
                            <div class="meta-item">
                                <i class="far fa-calendar-alt"></i>
                                <span>${new Date(p.payment_date).toLocaleDateString()}</span>
                            </div>
                            <div class="meta-item">
                                <i class="far fa-clock"></i>
                                <span>${new Date(p.payment_date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                            </div>
                            <div class="meta-item full-width">
                                <i class="fas fa-hashtag"></i>
                                <span>Ref: ${p.reference || 'N/A'}</span>
                            </div>
                        </div>
                    </div>

                    <div class="card-footer-actions">
                        <button class="card-action-btn success" onclick="app.modules.payments.printReceipt(${p.id})">
                            <i class="fas fa-print"></i> Imprimir
                        </button>
                        <button class="card-action-btn" onclick="app.modules.payments.viewReceiptDetails(${p.id})">
                            <i class="fas fa-eye"></i> Ver
                        </button>
                        ${p.status !== 'cancelled' ? `
                            <button class="card-action-btn danger" onclick="app.modules.payments.showRevertPaymentModal(${p.id}, ${p.client_id}, '${p.payment_date}')">
                                <i class="fas fa-undo"></i> Revertir
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = html;
    }
}
