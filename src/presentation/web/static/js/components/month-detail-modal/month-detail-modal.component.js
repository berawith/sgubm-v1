import { BaseModal } from '../shared/base-modal.component.js';

/**
 * Componente para mostrar detalles de recaudación mensual
 */
export class MonthDetailModal extends BaseModal {
    constructor(api, eventBus) {
        super('month-detail', api, eventBus);
        this.monthData = null;
    }

    async init() {
        await this.loadResources(
            '/static/js/components/month-detail-modal/month-detail-modal.template.html'
        );
    }

    /**
     * @param {object} data - { monthData: {...} }
     */
    async open(data = {}) {
        await this._initPromise;
        this.monthData = data.monthData;

        if (!this.monthData) {
            console.error('No monthData provided to MonthDetailModal');
            return;
        }

        // Reset UI with basics manually before it starts loading
        super.open();

        const titleEl = this.modalElement.querySelector('#month-detail-title');
        const periodEl = this.modalElement.querySelector('#month-detail-period');

        if (titleEl) titleEl.textContent = `${this.monthData.month_name} ${this.monthData.year}`;
        if (periodEl) periodEl.textContent = 'Recaudación y Eficiencia';

        this.updateStats();
        await this.loadMonthlyPayments();
    }

    updateStats() {
        const d = this.monthData;
        const missing = Math.max(0, d.billed - d.collected);
        const efficiency = d.billed > 0 ? (d.collected / d.billed) * 100 : 0;

        const setVal = (id, val, isPrice = true) => {
            const el = this.modalElement.querySelector(`#${id}`);
            if (el) el.textContent = isPrice ? `$${val.toLocaleString()}` : val;
        };

        setVal('month-val-collected', d.collected);
        setVal('month-val-billed', d.billed);
        setVal('month-val-missing', missing);

        const fill = this.modalElement.querySelector('#month-efficiency-fill');
        const text = this.modalElement.querySelector('#month-efficiency-text');
        if (fill) fill.style.width = `${Math.min(100, efficiency)}%`;
        if (text) text.textContent = `${efficiency.toFixed(1)}%`;
    }

    async loadMonthlyPayments() {
        const listBody = this.modalElement.querySelector('#month-payments-list');
        if (!listBody) return;

        listBody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px;"><div class="spinner-mini"></div> Cargando pagos...</td></tr>';

        try {
            const startStr = `${this.monthData.year}-${String(this.monthData.month).padStart(2, '0')}-01T00:00:00Z`;
            const lastDay = new Date(this.monthData.year, this.monthData.month, 0).getDate();
            const endStr = `${this.monthData.year}-${String(this.monthData.month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}T23:59:59Z`;

            // Using the existing report endpoint
            const data = await this.api.post('/api/payments/report', {
                start_date: startStr,
                end_date: endStr
            });

            const paymentsList = [];
            Object.values(data.daily_totals || {}).forEach(day => {
                if (day.payments) {
                    paymentsList.push(...day.payments);
                }
            });

            if (paymentsList.length === 0) {
                listBody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px;">No hay pagos en este periodo.</td></tr>';
            } else {
                listBody.innerHTML = paymentsList.map(p => `
                    <tr>
                        <td>
                            <div class="client-cell-mini">
                                <div class="avatar-circle">${(p.client_name || 'C').charAt(0)}</div>
                                <span>${p.client_name || 'Desconocido'}</span>
                            </div>
                        </td>
                        <td>${new Date(p.payment_date).toLocaleDateString()}</td>
                        <td><code class="ref-code">${p.reference || 'N/A'}</code></td>
                        <td class="amount-cell">$${p.amount.toLocaleString()}</td>
                        <td><span class="status-pill success">Completado</span></td>
                    </tr>
                `).join('');
            }
        } catch (error) {
            console.error('Error loading month payments:', error);
            listBody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px; color: #ef4444;">Error al cargar datos.</td></tr>';
        }
    }
}
