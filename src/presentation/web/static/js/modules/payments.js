/**
 * Payments Module - Frontend para gestión de pagos
 */
export class PaymentsModule {
    constructor(api, eventBus) {
        this.api = api;
        this.eventBus = eventBus;
        this.payments = [];
        this.statistics = null;

        console.log('💰 Payments Module initialized');
    }

    async load() {
        console.log('💰 Loading Payments...');

        // Mostrar vista
        this.showView();

        // Cargar datos
        await Promise.all([
            this.loadPayments(),
            this.loadStatistics()
        ]);
    }

    showView() {
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        const view = document.getElementById('payments-view');
        if (view) view.classList.add('active');
    }

    async loadPayments() {
        try {
            this.payments = await this.api.get('/api/payments?limit=50');
            this.renderPayments();
        } catch (error) {
            console.error('Error loading payments:', error);
            this.payments = [];
            this.renderPayments();
        }
    }

    async loadStatistics() {
        try {
            this.statistics = await this.api.get('/api/payments/statistics');
            this.renderStatistics();
        } catch (error) {
            console.error('Error loading statistics:', error);
        }
    }

    renderPayments() {
        const container = document.getElementById('payments-list');
        if (!container) return;

        if (this.payments.length === 0) {
            container.innerHTML = `
                <div class="no-payments">
                    <i class="fas fa-receipt"></i>
                    <p>No hay pagos registrados</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="payments-table">
                <table>
                    <thead>
                        <tr>
                            <th>Fecha</th>
                            <th>Cliente</th>
                            <th>Código</th>
                            <th>Monto</th>
                            <th>Método</th>
                            <th>Referencia</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${this.payments.map(payment => `
                            <tr>
                                <td>${new Date(payment.payment_date).toLocaleDateString()}</td>
                                <td>${payment.client_name || 'N/A'}</td>
                                <td>${payment.subscriber_code || 'N/A'}</td>
                                <td class="amount">$${payment.amount.toFixed(2)}</td>
                                <td><span class="method-badge ${payment.payment_method}">${payment.payment_method || 'N/A'}</span></td>
                                <td>${payment.reference || '-'}</td>
                                <td><span class="status-badge ${payment.status}">${payment.status}</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    renderStatistics() {
        const container = document.getElementById('payments-stats');
        if (!container || !this.statistics) return;

        const stats = this.statistics;

        container.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon">
                        <i class="fas fa-calendar-day"></i>
                    </div>
                    <div class="stat-info">
                        <h4>Hoy</h4>
                        <p class="stat-value">$${stats.totals.today.toFixed(2)}</p>
                        <span class="stat-subtitle">${stats.counts.today} pagos</span>
                    </div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-icon">
                        <i class="fas fa-calendar-week"></i>
                    </div>
                    <div class="stat-info">
                        <h4>Esta Semana</h4>
                        <p class="stat-value">$${stats.totals.week.toFixed(2)}</p>
                        <span class="stat-subtitle">${stats.counts.week} pagos</span>
                    </div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-icon">
                        <i class="fas fa-calendar-alt"></i>
                    </div>
                    <div class="stat-info">
                        <h4>Este Mes</h4>
                        <p class="stat-value">$${stats.totals.month.toFixed(2)}</p>
                        <span class="stat-subtitle">${stats.counts.month} pagos</span>
                    </div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-icon">
                        <i class="fas fa-chart-line"></i>
                    </div>
                    <div class="stat-info">
                        <h4>Este Año</h4>
                        <p class="stat-value">$${stats.total.year.toFixed(2)}</p>
                        <span class="stat-subtitle">${stats.counts.year} pagos</span>
                    </div>
                </div>
            </div>
            
            <div class="payment-methods">
                <h3>Métodos de Pago</h3>
                <div class="methods-grid">
                    ${Object.entries(stats.payment_methods || {}).map(([method, data]) => `
                        <div class="method-stat">
                            <span class="method-name">${method}</span>
                            <span class="method-count">${data.count} pagos</span>
                            <span class="method-total">$${data.total.toFixed(2)}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
}
