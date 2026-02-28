/**
 * Clients Support Module
 * Handles viewing and creating support tickets with picture upload
 */

export class ClientsSupportModule {
    constructor(apiService, eventBus, viewManager, modalManager) {
        this.api = apiService;
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.modalManager = modalManager;

        this.container = document.getElementById('clients-support-view');
        this.tableBody = document.getElementById('support-table-body');
        this.emptyState = document.getElementById('support-empty-state');

        this.modal = document.getElementById('new-ticket-modal');
        this.form = document.getElementById('new-ticket-form');
        this.clientSelect = document.getElementById('ticket-client');

        this.resolveModal = document.getElementById('resolve-ticket-modal');
        this.resolveForm = document.getElementById('resolve-ticket-form');

        // Listeners
        this.initListeners();
        this.initSocketListeners();
        console.log('✅ ClientsSupportModule initialized');
    }

    initSocketListeners() {
        if (!this.eventBus) return;

        // NEW REAL-TIME SYNC HUB
        this.eventBus.subscribe('data_refresh', (data) => {
            if (this.viewManager.currentSubView === 'clients-support') {
                if (data.event_type && data.event_type.startsWith('support.')) {
                    console.log(`♻️ Real-time Support: Refreshing tickets due to ${data.event_type}`);
                    this.loadTickets();
                }
            }
        });
    }

    initListeners() {
        if (!this.container) return;

        // Form Submit
        if (this.form) {
            this.form.addEventListener('submit', (e) => this.handleSubmitForm(e));
        }

        if (this.resolveForm) {
            this.resolveForm.addEventListener('submit', (e) => this.handleSubmitResolution(e));
        }

        // File name preview
        const fileInput = document.getElementById('ticket-image');
        const filePreview = document.getElementById('file-name-preview');
        if (fileInput && filePreview) {
            fileInput.addEventListener('change', (e) => {
                if (e.target.files && e.target.files[0]) {
                    const textSpan = filePreview.querySelector('.text');
                    if (textSpan) textSpan.textContent = e.target.files[0].name;
                    filePreview.style.display = 'flex';
                } else {
                    filePreview.style.display = 'none';
                }
            });
        }

        // Close Modal logic helper
        const setupCloseM = (modalEl, mId, formEl) => {
            if (!modalEl) return;
            const closeBtns = modalEl.querySelectorAll('.close-modal');
            closeBtns.forEach(btn => btn.addEventListener('click', () => {
                this.modalManager.close(mId);
                if (formEl) formEl.reset();
            }));
            modalEl.addEventListener('click', (e) => {
                if (e.target === modalEl) {
                    this.modalManager.close(mId);
                    if (formEl) formEl.reset();
                }
            });
        };

        setupCloseM(this.modal, 'support', this.form);
        setupCloseM(this.resolveModal, 'resolve-ticket', this.resolveForm);
    }

    async load() {
        console.log('📡 Cargando vista de Soporte...');
        this.viewManager.showSubView('clients-support');
        await this.loadTickets();
    }

    async init() {
        await this.load();
    }

    async loadTickets() {
        try {
            const icon = document.getElementById('support-refresh-icon');
            if (icon) icon.classList.add('fa-spin');

            const tickets = await this.api.get('/api/support');
            this.renderTickets(tickets);
            await this.loadStats();

            if (icon) icon.classList.remove('fa-spin');
        } catch (e) {
            console.error("Error loading tickets:", e);
        }
    }

    async loadStats() {
        try {
            const stats = await this.api.get('/api/support/stats');

            const mapping = {
                'support-stat-abiertos': stats.open,
                'support-stat-resueltos': stats.resolved,
                'support-stat-cancelados': stats.cancelled,
                'support-stat-avg-time': stats.avg_resolution_hours,
                'support-stat-efficiency': stats.efficiency_pct
            };

            for (const [id, val] of Object.entries(mapping)) {
                const el = document.getElementById(id);
                if (el) el.textContent = val;
            }
        } catch (err) {
            console.error('Error loading support stats:', err);
        }
    }

    renderTickets(tickets) {
        if (!this.tableBody) return;

        this.tableBody.innerHTML = '';

        if (tickets.length === 0) {
            this.tableBody.parentElement.parentElement.style.display = 'none';
            if (this.emptyState) this.emptyState.style.display = 'block';
            return;
        }

        this.tableBody.parentElement.parentElement.style.display = 'block';
        if (this.emptyState) this.emptyState.style.display = 'none';

        const currentUser = app && app.modules && app.modules.auth && app.modules.auth.auth ? app.modules.auth.auth.getUser() : null;
        const isAdmin = currentUser && ['admin', 'admin_fem', 'partner', 'secretaria'].includes(currentUser.role);

        tickets.forEach(ticket => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid rgba(226, 232, 240, 0.6)';
            tr.className = 'support-row';

            let dateStr = ticket.created_at ? ticket.created_at.replace('T', ' ').substring(0, 16) : 'N/A';
            let statusBadge = '';

            switch (ticket.status) {
                case 'resolved':
                    statusBadge = `<span style="display:inline-flex; align-items:center; gap:6px; padding:6px 12px; background:#f0fdf4; color:#15803d; border:1px solid #dcfce7; border-radius:10px; font-size:0.7rem; font-weight:800;"><i class="fas fa-check-circle"></i> RESUELTO</span>`;
                    break;
                case 'cancelled':
                    statusBadge = `<span style="display:inline-flex; align-items:center; gap:6px; padding:6px 12px; background:#f1f5f9; color:#475569; border:1px solid #e2e8f0; border-radius:10px; font-size:0.7rem; font-weight:800;"><i class="fas fa-times-circle"></i> CANCELADO</span>`;
                    break;
                default:
                    statusBadge = `<span style="display:inline-flex; align-items:center; gap:6px; padding:6px 12px; background:#fff7ed; color:#c2410c; border:1px solid #ffedd5; border-radius:10px; font-size:0.7rem; font-weight:800;"><i class="fas fa-clock fa-spin"></i> ABIERTO</span>`;
            }

            let actionsHtml = '';
            if (isAdmin) {
                if (ticket.status === 'open') {
                    actionsHtml = `
                        <button onclick="app.modules.clients_support.openResolveModal(${ticket.id})" title="Resolver" style="width:32px; height:32px; border-radius:8px; border:none; background:#f0fdf4; color:#22c55e; cursor:pointer;"><i class="fas fa-check"></i></button>
                        <button onclick="app.modules.clients_support.cancelTicket(${ticket.id})" title="Cancelar" style="width:32px; height:32px; border-radius:8px; border:none; background:#fef2f2; color:#ef4444; cursor:pointer;"><i class="fas fa-ban"></i></button>
                    `;
                } else {
                    actionsHtml = `
                        <button onclick="app.modules.clients_support.revertTicket(${ticket.id})" title="Reabrir / Revertir" style="width:32px; height:32px; border-radius:8px; border:none; background:#eff6ff; color:#3b82f6; cursor:pointer;"><i class="fas fa-undo"></i></button>
                    `;
                }
            }

            let imageHtml = ticket.image_path ? `<a href="${ticket.image_path}" target="_blank" style="display:inline-flex; margin-top:8px; font-size:0.7rem; background:#4f46e5; padding:4px 10px; border-radius:8px; color:white; text-decoration:none; align-items:center; gap:4px; font-weight:700;"><i class="fas fa-image"></i> Ver Evidencia</a>` : '';

            tr.innerHTML = `
                <td style="padding: 16px 28px;">
                    <div style="font-weight: 800; color: #0f172a; font-size: 0.95rem;">#${ticket.id} · ${ticket.subject}</div>
                    <div style="font-size: 0.8rem; color: #64748b; margin-top:4px;">Suscriptor: <strong>${ticket.client_name || 'Desconocido'}</strong></div>
                    <div style="font-size: 0.85rem; color: #475569; margin-top: 6px; font-style: italic;">"${ticket.description}"</div>
                    ${imageHtml}
                </td>
                <td style="padding: 16px 28px;">
                    <span style="font-size: 0.85rem; color: #1e293b; font-weight: 700;">${ticket.user_name || 'Sistema'}</span>
                </td>
                <td style="padding: 16px 28px; text-align: center; font-size: 0.85rem; color: #64748b;">${dateStr}</td>
                <td style="padding: 16px 28px; text-align: center;">${statusBadge}</td>
                <td style="padding: 16px 28px; text-align: right;">
                    <div style="display: flex; justify-content: flex-end; gap: 8px;">${actionsHtml}</div>
                </td>
            `;

            this.tableBody.appendChild(tr);
        });
    }

    openResolveModal(id) {
        document.getElementById('resolve-ticket-id').value = id;

        // Predeterminar fecha actual en formato local ISO
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        document.querySelector('#resolve-ticket-form input[name="support_date"]').value = now.toISOString().slice(0, 16);

        this.modalManager.open('resolve-ticket');
    }

    async handleSubmitResolution(e) {
        e.preventDefault();
        const id = document.getElementById('resolve-ticket-id').value;
        const formData = new FormData(this.resolveForm);
        const data = Object.fromEntries(formData.entries());
        data.status = 'resolved';

        try {
            if (window.app) window.app.showLoading(true);
            await this.api.put(`/api/support/${id}/status`, data);
            if (window.toast) window.toast.success('Ticket resuelto y cerrado exitosamente.');
            this.modalManager.close('resolve-ticket');
            await this.loadTickets();
        } catch (err) {
            console.error('Error closing ticket:', err);
            if (window.toast) window.toast.error('No se pudo cerrar el ticket.');
        } finally {
            if (window.app) window.app.showLoading(false);
        }
    }

    async cancelTicket(id) {
        if (!confirm('¿Seguro que desea cancelar este ticket? (Falsa alarma / Error)')) return;
        try {
            await this.api.put(`/api/support/${id}/status`, { status: 'cancelled' });
            if (window.toast) window.toast.info('Ticket cancelado.');
            await this.loadTickets();
        } catch (err) {
            console.error('Error cancelling ticket:', err);
        }
    }

    async revertTicket(id) {
        if (!confirm('¿Reabrir este ticket y revertir su estado?')) return;
        try {
            await this.api.put(`/api/support/${id}/status`, { status: 'open' });
            if (window.toast) window.toast.success('Ticket reabierto.');
            await this.loadTickets();
        } catch (err) {
            console.error('Error reverting ticket:', err);
        }
    }

    async openNewTicketModal(preselectedClientId = null) {
        await this.loadClientsForDropdown(preselectedClientId);
        this.modalManager.open('support');
    }

    async loadClientsForDropdown(preselectedClientId = null) {
        try {
            const clients = await this.api.get('/api/clients');
            this.clientSelect.innerHTML = '<option value="">Seleccione un cliente...</option>';
            clients.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.id;
                opt.textContent = `${c.subscriber_code} - ${c.legal_name}`;
                if (preselectedClientId && parseInt(c.id) === parseInt(preselectedClientId)) opt.selected = true;
                this.clientSelect.appendChild(opt);
            });
        } catch (e) {
            console.error("Error loading clients:", e);
        }
    }

    async handleSubmitForm(e) {
        e.preventDefault();
        const token = localStorage.getItem('auth_token');
        const formData = new FormData(this.form);
        try {
            if (window.app) window.app.showLoading(true);
            const req = await fetch('/api/support', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });
            if (!req.ok) throw new Error("Error al subir ticket");
            if (window.toast) window.toast.success('Reporte enviado.');
            this.modalManager.close('support');
            this.form.reset();
            await this.loadTickets();
        } catch (e) {
            console.error("Error creating ticket", e);
        } finally {
            if (window.app) window.app.showLoading(false);
        }
    }
}
