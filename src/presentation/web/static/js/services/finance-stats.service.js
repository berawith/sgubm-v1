/**
 * FinanceStatsService - Handles financial statistics, reporting, and charting.
 * Extracted from PaymentsModule for better maintainability.
 */
export class FinanceStatsService {
    constructor(api, logger) {
        this.api = api;
        this.logger = logger || console;
        this.revenueChart = null;
        this.revenueChartMain = null;
        this.expenseTrendChart = null;
    }

    async loadStatistics(filterState) {
        try {
            const params = new URLSearchParams();
            if (filterState.startDate) params.append('start_date', filterState.startDate);
            if (filterState.endDate) params.append('end_date', filterState.endDate);
            if (filterState.method) params.append('method', filterState.method);

            const statistics = await this.api.get(`/api/payments/statistics?${params.toString()}`);
            return statistics;
        } catch (error) {
            this.logger.error('Error loading statistics:', error);
            return null;
        }
    }

    renderStatistics(stats, filterState) {
        if (!stats) return;

        const updateVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = `$${(val || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        };

        updateVal('pay-stat-today', stats.totals.today || 0);
        updateVal('pay-stat-today-main', stats.totals.today || 0);

        if (filterState.startDate || filterState.endDate) {
            updateVal('pay-stat-month', stats.totals.filtered_period_total || 0);
            updateVal('pay-stat-month-main', stats.totals.filtered_period_total || 0);
            updateVal('pay-stat-expenses-main', stats.totals.filtered_period_expenses || 0);
            updateVal('pay-stat-net-main', stats.totals.filtered_period_net || 0);
            updateVal('pay-stat-fx-main', stats.totals.total_fx_variance || 0);

            const monthLabel = document.querySelector('.payment-stat-icon.month')?.nextElementSibling?.querySelector('h4');
            if (monthLabel) monthLabel.textContent = 'Periodo Seleccionado';
        } else {
            updateVal('pay-stat-month', stats.totals.month || 0);
            updateVal('pay-stat-month-main', stats.totals.month || 0);
            updateVal('pay-stat-expenses-main', stats.totals.month_expenses || 0);
            updateVal('pay-stat-net-main', stats.totals.month_net || 0);
            updateVal('pay-stat-fx-main', stats.totals.total_fx_variance || 0);
            updateVal('pay-stat-prorated-main', stats.totals.prorated_adjustment || 0);
            updateVal('pay-stat-promises-main', stats.totals.pending_promises || 0);
            updateVal('pay-stat-surplus-main', stats.totals.client_surplus || 0);

            const monthLabel = document.querySelector('.payment-stat-icon.month')?.nextElementSibling?.querySelector('h4');
            if (monthLabel) monthLabel.textContent = 'Este Mes';
        }

        updateVal('pay-stat-total', stats.totals.all_time || 0);
        updateVal('pay-stat-pending', stats.totals.total_pending_debt || 0);
        updateVal('pay-stat-pending-main', stats.totals.total_pending_debt || 0);
        updateVal('pay-stat-loss-main', stats.totals.combined_losses || 0);

        const paidEl = document.getElementById('pay-stat-clients-paid');
        if (paidEl) paidEl.textContent = stats.counts.paid_clients || 0;

        const pendingEl = document.getElementById('pay-stat-clients-pending');
        if (pendingEl) pendingEl.textContent = stats.counts.debt_clients || 0;

        const pendingMainEl = document.getElementById('pay-stat-clients-pending-main');
        if (pendingMainEl) pendingMainEl.textContent = stats.counts.debt_clients || 0;

        // --- FX Variance ---
        const fxEl = document.getElementById('loss-stat-fx');
        if (fxEl) {
            const val = stats.totals.total_fx_variance || 0;
            fxEl.textContent = `$${Math.abs(val).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
            fxEl.style.color = val < 0 ? '#ef4444' : '#10b981';
        }

        updateVal('loss-stat-prorating', stats.totals.prorated_adjustment || 0);
        updateVal('loss-stat-bad-debt', stats.totals.bad_debt || 0);

        this.renderMethodBreakdown(stats.payment_methods || {});
        this.renderMethodBreakdown(stats.payment_methods || {}, 'method-breakdown-main');
        this.renderExpenseCategoryBreakdown(stats.expense_categories || {});

        // Update Chart
        this.initCharts(stats);
    }

    renderMethodBreakdown(methods, containerId = 'method-breakdown') {
        const container = document.getElementById(containerId);
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

    renderExpenseCategoryBreakdown(categories, containerId = 'expense-category-breakdown') {
        const container = document.getElementById(containerId);
        if (!container) return;

        if (!categories || Object.keys(categories).length === 0) {
            container.innerHTML = '<p style="color:#94a3b8; padding:20px; text-align:center;">Sin datos de gastos</p>';
            return;
        }

        container.innerHTML = Object.entries(categories).map(([cat, data]) => `
            <div class="method-card">
                <div class="method-card-left">
                    <div class="method-icon-box" style="background: rgba(244, 63, 94, 0.1); color: #f43f5e;">
                        <i class="fas ${cat === 'fixed' ? 'fa-anchor' : (cat === 'variable' ? 'fa-bolt' : 'fa-tag')}"></i>
                    </div>
                    <div class="method-info">
                        <span class="method-name">${cat === 'fixed' ? 'Fijos' : (cat === 'variable' ? 'Variables' : cat.charAt(0).toUpperCase() + cat.slice(1))}</span>
                        <span class="method-count">${data.count} registros</span>
                    </div>
                </div>
                <div class="method-amount" style="color: #ef4444;">$${(data.total || 0).toLocaleString()}</div>
            </div>
        `).join('');
    }

    initCharts(stats) {
        if (!stats) return;
        this._initChart('revenue-chart', stats);
        this._initChart('revenue-chart-main', stats);
        this._initExpenseChart('expense-trend-chart', stats);
    }

    _initChart(canvasId, stats) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        // Limpiar el chart anterior
        if (canvasId === 'revenue-chart' && this.revenueChart) {
            this.revenueChart.destroy();
            this.revenueChart = null;
        }
        if (canvasId === 'revenue-chart-main' && this.revenueChartMain) {
            this.revenueChartMain.destroy();
            this.revenueChartMain = null;
        }

        const trend = stats.annual_trend || [];
        if (trend.length === 0) return;

        const labels = trend.map(t => t.label);
        const collectedData = trend.map(t => t.collected);
        const expensesData = trend.map(t => t.expenses || 0);
        const metaData = trend.map(t => t.theoretical || 0);

        const ctx2d = ctx.getContext('2d');
        const gradientReal = ctx2d.createLinearGradient(0, 0, 0, 400);
        gradientReal.addColorStop(0, 'rgba(16, 185, 129, 0.8)');
        gradientReal.addColorStop(1, 'rgba(16, 185, 129, 0.1)');

        const gradientMeta = ctx2d.createLinearGradient(0, 0, 0, 400);
        gradientMeta.addColorStop(0, 'rgba(99, 102, 241, 0.4)');
        gradientMeta.addColorStop(1, 'rgba(99, 102, 241, 0.05)');

        const gradientExpenses = ctx2d.createLinearGradient(0, 0, 0, 400);
        gradientExpenses.addColorStop(0, 'rgba(244, 63, 94, 0.6)');
        gradientExpenses.addColorStop(1, 'rgba(244, 63, 94, 0.1)');

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Meta (Teórico)',
                        data: metaData,
                        backgroundColor: gradientMeta,
                        borderColor: 'rgba(99, 102, 241, 0.5)',
                        borderWidth: 1,
                        borderRadius: 4,
                        barPercentage: 0.9,
                        categoryPercentage: 0.8
                    },
                    {
                        label: 'Egresos (Gastos)',
                        data: expensesData,
                        backgroundColor: gradientExpenses,
                        borderColor: 'rgba(244, 63, 94, 0.8)',
                        borderWidth: 1.5,
                        borderRadius: 4,
                        barPercentage: 0.7,
                        categoryPercentage: 0.8
                    },
                    {
                        label: 'Recaudado (Real)',
                        data: collectedData,
                        backgroundColor: gradientReal,
                        borderRadius: 4,
                        hoverBackgroundColor: '#10b981',
                        borderWidth: 0,
                        barPercentage: 0.5,
                        categoryPercentage: 0.8
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: (event, elements) => {
                    if (elements.length > 0 && window.app && window.app.modules.payments) {
                        const index = elements[0].index;
                        const monthData = trend[index];
                        window.app.modules.payments.showMonthDetailModal(monthData);
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            font: { size: 11, weight: '700' }
                        }
                    },
                    tooltip: {
                        backgroundColor: '#1a1a2e',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        padding: 12,
                        callbacks: {
                            label: function (context) {
                                let label = context.dataset.label || '';
                                if (label) label += ': ';
                                if (context.parsed.y !== null) {
                                    label += new Intl.NumberFormat('en-US', { style: 'currency', currency: 'COP' }).format(context.parsed.y);
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: { stacked: false, grid: { display: false } },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(0,0,0,0.05)' },
                        ticks: { callback: value => '$' + value.toLocaleString('en-US') }
                    }
                }
            }
        });

        if (canvasId === 'revenue-chart') this.revenueChart = chart;
        else if (canvasId === 'revenue-chart-main') this.revenueChartMain = chart;
    }

    _initExpenseChart(canvasId, stats) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        if (this.expenseTrendChart) {
            this.expenseTrendChart.destroy();
            this.expenseTrendChart = null;
        }

        const trend = stats.annual_trend || [];
        if (trend.length === 0) return;

        const labels = trend.map(t => t.label);
        const expensesData = trend.map(t => t.expenses || 0);

        const ctx2d = ctx.getContext('2d');
        const gradient = ctx2d.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(244, 63, 94, 0.8)');
        gradient.addColorStop(1, 'rgba(244, 63, 94, 0.1)');

        this.expenseTrendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Mensual de Gastos',
                    data: expensesData,
                    backgroundColor: gradient,
                    borderColor: '#f43f5e',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 4,
                    pointBackgroundColor: '#fff',
                    pointBorderColor: '#f43f5e',
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                return ' Gasto: ' + new Intl.NumberFormat('en-US', {
                                    style: 'currency',
                                    currency: 'COP'
                                }).format(context.parsed.y);
                            }
                        }
                    }
                },
                scales: {
                    x: { grid: { display: false } },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(0,0,0,0.05)' },
                        ticks: { callback: v => '$' + v.toLocaleString('en-US') }
                    }
                }
            }
        });
    }

    exportReport(filterState, format = 'csv', type = 'payments') {
        const params = new URLSearchParams();
        if (filterState.startDate) params.append('start_date', filterState.startDate);
        if (filterState.endDate) params.append('end_date', filterState.endDate);
        if (filterState.method) params.append('method', filterState.method);
        params.append('report_type', type);

        let endpoint = '/api/payments/export';
        if (format === 'pdf') endpoint = '/api/payments/export-pdf';
        if (format === 'excel') endpoint = '/api/payments/export-excel';

        if (type === 'debtors' && format === 'csv') {
            window.open('/api/payments/export-debtors', '_blank');
        } else {
            window.open(`${endpoint}?${params.toString()}`, '_blank');
        }
    }
}
