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

        // Inicializar gráfico
        this.initChart();
    }

    showView() {
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.querySelectorAll('.content-view').forEach(v => v.classList.remove('active'));
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

    initChart() {
        const ctx = document.getElementById('revenue-chart');
        if (!ctx) return;

        // Limpiar gráfico anterior si existe
        if (this.revenueChart) {
            this.revenueChart.destroy();
        }

        // Datos de ejemplo para el gráfico (En el futuro venir de la API)
        const labels = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
        const dataValues = [12000, 15000, 18000, 14000, 22000, 25000, 24000, 28000, 32000, 35000, 38000, 42000];

        this.revenueChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Recaudación Mensual ($)',
                    data: dataValues,
                    borderColor: '#00f2fe',
                    backgroundColor: 'rgba(0, 242, 254, 0.1)',
                    fill: true,
                    tension: 0.4,
                    borderWidth: 4,
                    pointBackgroundColor: '#fff',
                    pointBorderColor: '#00f2fe',
                    pointBorderWidth: 3,
                    pointRadius: 5,
                    pointHoverRadius: 8,
                    shadowBlur: 10,
                    shadowColor: 'rgba(0, 242, 254, 0.5)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1a1a2e',
                        titleColor: '#fff',
                        bodyColor: '#00f2fe',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        padding: 15,
                        displayColors: false,
                        callbacks: {
                            label: (context) => `$ ${context.parsed.y.toLocaleString()}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)',
                            drawBorder: false
                        },
                        ticks: {
                            color: 'rgba(255, 255, 255, 0.5)',
                            callback: (val) => `$${val / 1000}k`
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

    renderStatistics() {
        if (!this.statistics) return;
        const stats = this.statistics;

        // Actualizar valores en las tarjetas
        const updateVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = `$${val.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
        };

        updateVal('pay-stat-today', stats.totals.today || 0);
        updateVal('pay-stat-month', stats.totals.month || 0);
        updateVal('pay-stat-total', stats.total.all_time || 0);

        // El pendiente podría calcularse como (total_mensual_esperado - mes_actual)
        // Por ahora simulamos un valor basado en los clientes
        const pendingValue = 150000;
        updateVal('pay-stat-pending', pendingValue);
    }

    renderPayments() {
        const container = document.getElementById('payments-list');
        if (!container) return;

        if (this.payments.length === 0) {
            container.innerHTML = `
                <div class="no-payments" style="text-align:center; padding: 40px; color: var(--text-muted);">
                    <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom:15px; opacity:0.5">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                    <p>No se encontraron pagos registrados</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <table class="payments-list-table">
                <thead>
                    <tr>
                        <th>Cliente</th>
                        <th>Fecha</th>
                        <th>Método</th>
                        <th>Referencia</th>
                        <th>Monto</th>
                        <th>Estado</th>
                    </tr>
                </thead>
                <tbody>
                    ${this.payments.map(payment => `
                        <tr>
                            <td>
                                <div class="client-cell">
                                    <div class="client-avatar">${(payment.client_name || 'U').charAt(0)}</div>
                                    <div class="client-info">
                                        <div class="client-name">${payment.client_name || 'Cliente Desconocido'}</div>
                                        <div class="client-code">${payment.subscriber_code || 'N/A'}</div>
                                    </div>
                                </div>
                            </td>
                            <td>${new Date(payment.payment_date).toLocaleDateString()}</td>
                            <td><span class="method-badge ${(payment.payment_method || 'otros').toLowerCase()}">${payment.payment_method || 'N/A'}</span></td>
                            <td><code style="background:rgba(255,255,255,0.05); padding:2px 6px; border-radius:4px;">${payment.reference || '-'}</code></td>
                            <td class="amount-cell">$${payment.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                            <td><span class="status-badge ${payment.status}">${payment.status === 'completed' ? 'Completado' : 'Pendiente'}</span></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    showNewPaymentModal() {
        const modal = document.getElementById('payment-modal');
        const form = document.getElementById('payment-form');
        if (!modal || !form) return;

        form.reset();
        this.clearSelectedClient();
        modal.classList.add('active');

        // Setup search listener
        const searchInput = document.getElementById('payment-client-query');
        if (searchInput) {
            // Debounce search
            let timeout = null;
            searchInput.oninput = (e) => {
                const query = e.target.value;
                clearTimeout(timeout);
                if (query.length < 2) {
                    this.hideSearchResults();
                    return;
                }
                timeout = setTimeout(() => this.searchClients(query), 300);
            };

            // Close search results when clicking outside
            document.addEventListener('click', (e) => {
                if (!searchInput.contains(e.target)) {
                    this.hideSearchResults();
                }
            });
        }

        // Setup form submission
        form.onsubmit = async (e) => {
            e.preventDefault();
            await this.submitPayment();
        };
    }

    async searchClients(query) {
        try {
            const results = await this.api.get(`/api/clients?search=${encodeURIComponent(query)}`);
            this.renderSearchResults(results);
        } catch (error) {
            console.error('Error searching clients:', error);
        }
    }

    renderSearchResults(clients) {
        const container = document.getElementById('payment-search-results');
        if (!container) return;

        if (clients.length === 0) {
            container.innerHTML = '<div class="search-result-item">No se encontraron clientes</div>';
        } else {
            container.innerHTML = clients.map(client => `
                <div class="search-result-item" onclick="app.modules.payments.selectClient(${JSON.stringify(client).replace(/"/g, '&quot;')})">
                    <div class="client-info">
                        <span class="client-name">${client.legal_name}</span>
                        <span class="client-meta">${client.ip_address || 'Sin IP'} • ${client.identity_document || 'S/D'}</span>
                    </div>
                    <span class="client-badge">${client.subscriber_code}</span>
                </div>
            `).join('');
        }
        container.classList.add('active');
    }

    hideSearchResults() {
        const container = document.getElementById('payment-search-results');
        if (container) container.classList.remove('active');
    }

    selectClient(client) {
        this.selectedClient = client;

        // Populate and show selected display
        document.getElementById('display-client-name').textContent = client.legal_name;
        document.getElementById('display-client-code').textContent = client.subscriber_code;
        document.getElementById('display-client-ip').textContent = client.ip_address || 'Sin IP';
        document.getElementById('display-client-document').textContent = client.identity_document || 'Sin documento';
        document.getElementById('payment-client-id').value = client.id;

        document.getElementById('payment-client-search-step').style.display = 'none';
        document.getElementById('selected-client-display').style.display = 'flex';
        document.getElementById('payment-details-fields').style.display = 'block';

        this.hideSearchResults();
    }

    clearSelectedClient() {
        this.selectedClient = null;
        document.getElementById('payment-client-search-step').style.display = 'block';
        document.getElementById('selected-client-display').style.display = 'none';
        document.getElementById('payment-details-fields').style.display = 'none';
        document.getElementById('payment-client-query').value = '';
    }

    async submitPayment() {
        const clientId = document.getElementById('payment-client-id').value;
        const amount = document.getElementById('payment-amount').value;
        const method = document.getElementById('payment-method').value;
        const reference = document.getElementById('payment-reference').value;
        const notes = document.getElementById('payment-notes').value;

        if (!clientId || !amount) {
            if (window.toast) window.toast.show('ID de cliente y monto son requeridos', 'error');
            return;
        }

        try {
            const result = await this.api.post('/api/payments', {
                client_id: parseInt(clientId),
                amount: parseFloat(amount),
                payment_method: method,
                reference: reference,
                notes: notes,
                payment_date: new Date().toISOString()
            });

            if (window.toast) window.toast.show('Pago registrado satisfactoriamente', 'success');

            // Close modal and refresh data
            document.getElementById('payment-modal').classList.remove('active');
            await this.load();

        } catch (error) {
            console.error('Error submitting payment:', error);
            if (window.toast) window.toast.show('Error al registrar el pago', 'error');
        }
    }
}
