/**
 * CollectorFinanceModule
 * Panel de Finanzas personal del Cobrador y vista de Administrador por Cobrador.
 * Muestra: Pagos cobrados, desglose por método, ganancia personal,
 * gastos/deducibles, monto a enviar a la empresa y registro de envíos.
 */
class CollectorFinanceModule {
    constructor(apiService) {
        this.api = apiService;
        this.summary = null;
        this.transfers = [];
        this.collectors = [];
        this.selectedCollectorId = null;
        this._listenersAttached = false;
    }

    async init() {
        console.log('💰 Collector Finance Module initialized');
        this._listenersAttached = false;

        // Initial load
        await this.load();

        // If user is Admin, we need to load collectors list for the selector
        if (this.summary && this.summary.user && this._isAdmin(this.summary.user.role)) {
            await this.loadCollectors();
        }
    }

    _isAdmin(role) {
        return ['admin', 'admin_fem', 'partner'].includes(role.toLowerCase());
    }

    async loadCollectors() {
        try {
            const users = await this.api.get('/api/users/collectors');
            this.collectors = users;
            this.renderCollectors();
        } catch (e) {
            console.error('Error loading collectors:', e);
        }
    }

    renderCollectors() {
        const select = document.getElementById('cf-collector-select');
        if (!select) return;

        const currentUserId = this.summary?.user?.id;

        select.innerHTML = `
            <option value="">Mi resumen (${this.summary?.user?.name || 'Yo'})</option>
            ${this.collectors.map(c => `
                <option value="${c.id}" ${this.selectedCollectorId == c.id ? 'selected' : ''}>
                    ${c.username} (${c.assigned_router_name || 'Sin Ruta'})
                </option>
            `).join('')}
        `;

        document.getElementById('cf-admin-controls').style.display = 'flex';
    }

    async load() {
        const params = this.buildParams();
        try {
            const [summary, transfers] = await Promise.all([
                this.api.get(`/api/collector/summary${params}`),
                this.api.get(`/api/collector/transfers${params}`)
            ]);
            this.summary = summary;
            this.transfers = transfers;
            this.render();
        } catch (e) {
            console.error('Error loading collector finance:', e);
            window.showToast && window.showToast('Error al cargar datos financieros', 'error');
        }

        // Always wire listeners after each load (view may have been re-rendered)
        if (!this._listenersAttached) {
            this.setupListeners();
            this._listenersAttached = true;
        }
    }

    buildParams() {
        const start = document.getElementById('cf-start-date')?.value;
        const end = document.getElementById('cf-end-date')?.value;
        const collectorId = document.getElementById('cf-collector-select')?.value;

        const parts = [];
        if (start) parts.push(`start_date=${start}`);
        if (end) parts.push(`end_date=${end}`);
        if (collectorId) {
            parts.push(`collector_id=${collectorId}`);
            this.selectedCollectorId = collectorId;
        } else {
            this.selectedCollectorId = null;
        }

        return parts.length ? '?' + parts.join('&') : '';
    }

    setupListeners() {
        document.getElementById('cf-filter-btn')?.addEventListener('click', () => this.load());
        document.getElementById('cf-register-btn')?.addEventListener('click', () => this.showSendModal());
        document.getElementById('cf-manage-expenses-btn')?.addEventListener('click', () => this.showExpensesModal());
        document.getElementById('cf-collector-select')?.addEventListener('change', () => this.load());
    }

    fmt(n) {
        return parseFloat(n || 0).toLocaleString('es-CO', { minimumFractionDigits: 0 });
    }

    fmtDate(iso) {
        if (!iso) return '—';
        return new Date(iso).toLocaleDateString('es-VE', { day: '2-digit', month: 'short', year: 'numeric' });
    }

    render() {
        const s = this.summary;
        if (!s) return;

        // Change Title if viewing someone else
        const titleEl = document.querySelector('#collector-finance-view .page-title');
        if (titleEl) {
            titleEl.innerHTML = this.selectedCollectorId ? `📊 Finanzas: ${s.user.name}` : `💰 Mis Finanzas`;
        }

        // --- Summary Cards ---
        this.setEl('cf-total-collected', `$${this.fmt(s.total_collected)}`);
        this.setEl('cf-payment-count', s.payment_count);

        // Method breakdown
        const byMethod = s.by_method || {};
        const cash = byMethod['efectivo'] || byMethod['cash'] || 0;
        const transfer = byMethod['transferencia'] || byMethod['transfer'] || 0;
        const other = s.total_collected - cash - transfer;

        this.setEl('cf-cash', `$${this.fmt(cash)}`);
        this.setEl('cf-transfer', `$${this.fmt(transfer)}`);

        // Progress bars
        const total = s.total_collected || 1;
        this.setEl('cf-cash-pct', ((cash / total) * 100).toFixed(1) + '%');
        this.setEl('cf-transfer-pct', ((transfer / total) * 100).toFixed(1) + '%');

        // --- Earnings ---
        this.setEl('cf-profit-pct', `${s.profit_percentage || 0}%`);
        this.setEl('cf-bonus', `$${this.fmt(s.bonus_amount)}`);
        this.setEl('cf-earnings', `$${this.fmt(s.collector_earnings)}`);

        // Multi-Router Breakdown
        const breakdownEl = document.getElementById('cf-earnings-breakdown');
        if (breakdownEl) {
            if (s.earnings_breakdown && s.earnings_breakdown.length > 1) {
                breakdownEl.innerHTML = s.earnings_breakdown.map(b => `
                    <div style="display:flex;justify-content:space-between;align-items:center;font-size:0.75rem;margin-bottom:4px;color:#475569;">
                        <span><i class="fas fa-server" style="font-size:0.6rem;opacity:0.7;margin-right:4px;"></i>${b.router_name}</span>
                        <strong style="color:#1e293b;">$${this.fmt(b.earnings)}</strong>
                    </div>
                `).join('');
                breakdownEl.style.display = 'block';
            } else {
                breakdownEl.style.display = 'none';
            }
        }

        // --- Expenses ---
        this.setEl('cf-total-expenses', `$${this.fmt(s.total_expenses)}`);
        this.setEl('cf-expense-count', s.expenses?.length || 0);

        const previewEl = document.getElementById('cf-expenses-preview');
        if (previewEl) {
            if (s.expenses && s.expenses.length > 0) {
                previewEl.innerHTML = s.expenses.slice(0, 2).map(e =>
                    `• ${e.description}: <strong>$${this.fmt(e.amount)}</strong>`
                ).join('<br>');
                if (s.expenses.length > 2) previewEl.innerHTML += `<br><em>y ${s.expenses.length - 2} más...</em>`;
            } else {
                previewEl.innerHTML = '<span style="color:#94a3b8;">Sin gastos registrados en este período.</span>';
            }
        }

        // --- Company Remittance ---
        this.setEl('cf-to-send', `$${this.fmt(s.amount_to_send)}`);
        this.setEl('cf-sent', `$${this.fmt(s.total_sent_to_company)}`);
        this.setEl('cf-pending', `$${this.fmt(s.balance_pending)}`);
        this.setEl('cf-first-date', this.fmtDate(s.first_ever_remittance));

        // Pending badge color
        const pendingEl = document.getElementById('cf-pending');
        if (pendingEl) {
            pendingEl.style.color = s.balance_pending > 0 ? '#ef4444' : '#10b981';
        }

        // Progress bar for sent vs target
        const sendTarget = s.amount_to_send || 1;
        const sentPct = Math.min(100, ((s.total_sent_to_company / sendTarget) * 100)).toFixed(1);
        const sentBar = document.getElementById('cf-sent-bar');
        if (sentBar) sentBar.style.width = sentPct + '%';
        this.setEl('cf-sent-pct', sentPct + '%');

        // --- Transfers Table ---
        this.renderTransfers();
    }

    renderTransfers() {
        const tbody = document.getElementById('cf-transfers-body');
        if (!tbody) return;

        if (!this.transfers || this.transfers.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:40px;color:#94a3b8;">
                <i class="fas fa-inbox" style="font-size:2rem;display:block;margin-bottom:12px;opacity:0.3;"></i>
                No se han registrado envíos en este período
            </td></tr>`;
            return;
        }

        let runningBalance = this.summary?.amount_to_send || 0;
        const rows = [];
        const sorted = [...this.transfers].sort((a, b) => new Date(a.sent_at) - new Date(b.sent_at));

        for (const t of sorted) {
            runningBalance -= t.amount;
            rows.push({ ...t, balance_after: Math.max(0, runningBalance) });
        }
        rows.reverse();

        const methodIcon = (m) => {
            const icons = { 'transferencia': '🏦', 'efectivo': '💵', 'pago_movil': '📱' };
            return icons[m.toLowerCase()] || '💳';
        };

        tbody.innerHTML = rows.map(t => `
            <tr>
                <td style="color:#64748b;">${this.fmtDate(t.sent_at)}</td>
                <td style="font-weight:800;color:#6366f1;">$${this.fmt(t.amount)}</td>
                <td>
                    <span class="status-badge" style="background:rgba(99,102,241,0.1);color:#6366f1;border:none;">
                        ${methodIcon(t.method)} ${t.method}
                    </span>
                </td>
                <td style="color:${t.balance_after > 0 ? '#ef4444' : '#10b981'};font-weight:700;">
                    $${this.fmt(t.balance_after)}
                    ${t.notes ? `<div style="font-size:0.7rem;color:#94a3b8;font-weight:400;margin-top:2px;">${t.notes}</div>` : ''}
                </td>
            </tr>
        `).join('');
    }

    setEl(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    async showSendModal() {
        const pending = this.summary?.balance_pending || 0;
        const { value: formValues } = await Swal.fire({
            title: '📤 Registrar Envío a Empresa',
            html: `
                <div style="text-align:left;padding:10px 0;">
                    <div style="margin-bottom:12px;padding:12px;background:rgba(99,102,241,0.07);border-radius:12px;border-left:4px solid #6366f1;">
                        <div style="font-size:0.8rem;color:#64748b;">Saldo pendiente por enviar</div>
                        <div style="font-size:1.5rem;font-weight:800;color:#ef4444;">$${this.fmt(pending)}</div>
                    </div>
                    <label style="font-size:0.75rem;font-weight:700;color:#64748b;display:block;margin-bottom:5px;">Monto Enviado</label>
                    <input id="cf-amount" type="number" step="1000" value="${pending.toFixed(0)}" class="swal2-input" style="width:100%;margin:0 0 14px 0;">
                    
                    <label style="font-size:0.75rem;font-weight:700;color:#64748b;display:block;margin-bottom:5px;">Método de Envío</label>
                    <select id="cf-method" class="swal2-select" style="width:100%;margin:0 0 14px 0;">
                        <option value="transferencia">🏦 Transferencia Bancaria</option>
                        <option value="efectivo">💵 Efectivo</option>
                        <option value="pago_movil">📱 Pago Móvil</option>
                    </select>
                    
                    <label style="font-size:0.75rem;font-weight:700;color:#64748b;display:block;margin-bottom:5px;">Notas / Referencia</label>
                    <textarea id="cf-notes" class="swal2-textarea" style="width:100%;margin:0;height:60px;resize:none;"></textarea>
                </div>
            `,
            confirmButtonText: 'Registrar Envío',
            showCancelButton: true,
            preConfirm: () => {
                const amount = parseFloat(document.getElementById('cf-amount').value);
                if (!amount || amount <= 0) return Swal.showValidationMessage('Ingresa un monto válido');
                return {
                    amount,
                    method: document.getElementById('cf-method').value,
                    notes: document.getElementById('cf-notes').value,
                    user_id: this.selectedCollectorId || this.summary.user.id
                };
            }
        });

        if (formValues) {
            try {
                const res = await this.api.post('/api/collector/transfers', formValues);
                if (res.success) {
                    window.showToast && window.showToast('✅ Envío registrado', 'success');
                    await this.load();
                } else {
                    window.showToast && window.showToast(res.message, 'error');
                }
            } catch (e) { console.error(e); }
        }
    }

    async showExpensesModal() {
        const isAdmin = this._isAdmin(this.summary.user.role);
        const collectorId = this.selectedCollectorId || this.summary.user.id;

        let html = `
            <div style="text-align:left;max-height:400px;overflow-y:auto;padding:10px;">
                <table style="width:100%;font-size:0.85rem;border-collapse:collapse;">
                    <thead style="background:#f8fafc;position:sticky;top:0;">
                        <tr>
                            <th style="padding:8px;text-align:left;">Fecha</th>
                            <th style="padding:8px;text-align:left;">Descripción</th>
                            <th style="padding:8px;text-align:right;">Monto</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${this.summary.expenses.map(e => `
                            <tr style="border-bottom:1px solid #f1f5f9;">
                                <td style="padding:8px;">${this.fmtDate(e.expense_date)}</td>
                                <td style="padding:8px;">${e.description}</td>
                                <td style="padding:8px;text-align:right;font-weight:700;color:#ef4444;">$${this.fmt(e.amount)}</td>
                            </tr>
                        `).join('') || '<tr><td colspan="3" style="padding:20px;text-align:center;color:#94a3b8;">No hay gastos registrados.</td></tr>'}
                    </tbody>
                </table>
            </div>
        `;

        if (isAdmin) {
            html += `
                <hr style="margin:20px 0;border:none;border-top:1px dashed #e2e8f0;">
                <div style="text-align:left;">
                    <h4 style="margin:0 0 12px;font-size:0.9rem;color:#1e293b;">➕ Registrar Nuevo Gasto/Ajuste</h4>
                    <label style="font-size:0.75rem;font-weight:700;color:#64748b;display:block;margin-bottom:5px;">Descripción</label>
                    <input id="exp-desc" class="swal2-input" style="width:100%;margin:0 0 10px 0;" placeholder="Ej: Pago internet, Gasolina, Ajuste balance...">
                    
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <div>
                            <label style="font-size:0.75rem;font-weight:700;color:#64748b;display:block;margin-bottom:5px;">Monto</label>
                            <input id="exp-amount" type="number" class="swal2-input" style="width:100%;margin:0;" placeholder="0">
                        </div>
                        <div>
                            <label style="font-size:0.75rem;font-weight:700;color:#64748b;display:block;margin-bottom:5px;">Categoría</label>
                            <select id="exp-cat" class="swal2-select" style="width:100%;margin:0;">
                                <option value="variable">Variable / Ajuste</option>
                                <option value="fixed">Gasto Fijo</option>
                            </select>
                        </div>
                    </div>
                </div>
            `;
        }

        const { value: newExpense } = await Swal.fire({
            title: '📜 Gestión de Gastos',
            html: html,
            showCancelButton: true,
            confirmButtonText: isAdmin ? 'Guardar Gasto' : 'Cerrar',
            confirmButtonColor: isAdmin ? '#6366f1' : '#94a3b8',
            preConfirm: () => {
                if (!isAdmin) return null;
                const desc = document.getElementById('exp-desc').value;
                const amount = parseFloat(document.getElementById('exp-amount').value);
                if (!desc || !amount) return Swal.showValidationMessage('Completa todos los campos');
                return {
                    description: desc,
                    amount: amount,
                    category: document.getElementById('exp-cat').value,
                    user_id: collectorId
                };
            }
        });

        if (newExpense && isAdmin) {
            try {
                const res = await this.api.post('/api/collector/expenses', newExpense);
                if (res.success) {
                    window.showToast && window.showToast('✅ Gasto registrado', 'success');
                    await this.load();
                }
            } catch (e) { console.error(e); }
        }
    }
}

export default CollectorFinanceModule;
