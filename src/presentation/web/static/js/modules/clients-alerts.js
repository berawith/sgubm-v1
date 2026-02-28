export class ClientsAlertsModule {
    constructor(apiService, eventBus, viewManager, modalManager) {
        this.api = apiService;
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.modalManager = modalManager;

        this.alerts = [];
        this.currentFilter = 'all'; // all, pending, rejected
        this.searchQuery = '';

        this.tableBody = document.getElementById('alerts-table-body');
        this.emptyState = document.getElementById('alerts-empty-state');
        this.statPending = document.getElementById('alerts-stat-pending');
        this.statRejected = document.getElementById('alerts-stat-rejected');

        // Registrar este módulo en el objeto global si no existe para comandos onkeyup/onclick
        if (!window.app) window.app = { modules: {} };
        if (!window.app.modules) window.app.modules = {};
        window.app.modules.clients_alerts = this;
    }

    async load() {
        console.log('📡 Cargando vista de Alertas...');
        await this.loadAlerts();
    }

    async loadAlerts() {
        try {
            if (window.app && window.app.showLoading) window.app.showLoading(true);

            const icon = document.getElementById('alerts-refresh-icon');
            if (icon) icon.classList.add('fa-spin');

            // API fetch
            this.alerts = await this.api.get('/api/payments/alerts');

            this.filterAlerts(); // Apply current filters and render UI

            if (icon) icon.classList.remove('fa-spin');
        } catch (error) {
            console.error('Error fetching alerts:', error);
            if (window.toast) window.toast.error('Error cargando las alertas.');
        } finally {
            if (window.app && window.app.showLoading) window.app.showLoading(false);
        }
    }

    filterAlerts() {
        const searchInput = document.getElementById('alerts-search-input');
        const filterSelect = document.getElementById('alerts-status-filter');

        this.searchQuery = searchInput ? searchInput.value.toLowerCase() : '';
        this.currentFilter = filterSelect ? filterSelect.value : 'all';

        let filtered = this.alerts;

        if (this.currentFilter !== 'all') {
            filtered = filtered.filter(a => a.status === this.currentFilter);
        }

        if (this.searchQuery) {
            filtered = filtered.filter(a =>
                (a.client_name && a.client_name.toLowerCase().includes(this.searchQuery)) ||
                (a.subscriber_code && a.subscriber_code.toLowerCase().includes(this.searchQuery)) ||
                (a.reference && a.reference.toLowerCase().includes(this.searchQuery))
            );
        }

        this.updateStats();
        this.renderTable(filtered);
    }

    updateStats() {
        if (!this.statPending || !this.statRejected) return;

        const pendingCount = this.alerts.filter(a => a.status === 'pending').length;
        const rejectedCount = this.alerts.filter(a => a.status === 'rejected').length;

        this.statPending.textContent = pendingCount;
        this.statRejected.textContent = rejectedCount;
    }

    renderTable(alerts) {
        if (!this.tableBody) return;

        this.tableBody.innerHTML = '';

        if (alerts.length === 0) {
            this.tableBody.parentElement.style.display = 'none';
            if (this.emptyState) this.emptyState.style.display = 'block';
            return;
        }

        this.tableBody.parentElement.style.display = 'table';
        if (this.emptyState) this.emptyState.style.display = 'none';

        alerts.forEach(alert => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid #f1f5f9';
            tr.style.transition = 'background 0.2s';

            // Format amounts and dates
            const amountFormatted = new Intl.NumberFormat('es-CO', { style: 'currency', currency: alert.currency || 'COP', minimumFractionDigits: 0 }).format(alert.amount || 0);

            let dateStr = 'N/A';
            if (alert.created_at) {
                const date = new Date(alert.created_at);
                dateStr = date.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
            }

            // Status Badge Definition
            let statusBadge = '';
            // Identificar si el usuario actual es un administrador
            const currentUser = app && app.modules && app.modules.auth && app.modules.auth.auth ? app.modules.auth.auth.getUser() : null;
            const isAdmin = currentUser && ['admin', 'admin_fem', 'partner'].includes(currentUser.role);

            let isRejected = alert.status === 'rejected';

            if (isRejected) {
                statusBadge = `<span style="display:inline-flex; align-items:center; gap:6px; padding:6px 12px; background:#fef2f2; color:#ef4444; border-radius:999px; font-size:0.75rem; font-weight:700; letter-spacing:0.05em;"><i class="fas fa-times-circle"></i> RECHAZADO</span>`;
            } else {
                statusBadge = `<span style="display:inline-flex; align-items:center; gap:6px; padding:6px 12px; background:#ffedd5; color:#f97316; border-radius:999px; font-size:0.75rem; font-weight:700; letter-spacing:0.05em;"><i class="fas fa-hourglass-half"></i> EN ESPERA</span>`;
            }

            // Rejection reason string if exists
            let reasonHtml = '';
            if (isRejected && alert.rejection_reason) {
                reasonHtml = `<div style="margin-top:8px; padding:8px 12px; background:#fff1f2; border-left:3px solid #ef4444; border-radius:6px; font-size:0.8rem; color:#991b1b;"><i class="fas fa-info-circle" style="margin-right:6px;"></i><strong>Motivo:</strong> ${alert.rejection_reason}</div>`;
            }

            tr.innerHTML = `
                <td style="padding: 16px 24px; vertical-align: top;">
                    <div style="font-weight: 700; color: #0f172a; margin-bottom: 4px;">${alert.client_name || 'Desconocido'}</div>
                    <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 4px;">ID: ${alert.subscriber_code || '#'} • Ref: ${alert.reference || 'N/A'}</div>
                    <div style="font-size: 0.75rem; color: #3b82f6; font-weight: 600;"><i class="fas fa-user-tag" style="margin-right: 4px;"></i>${alert.registered_by || 'Sistema'}</div>
                </td>
                <td style="padding: 16px 24px; text-align: right; vertical-align: top;">
                    <span style="font-weight: 800; color: #1e293b; font-size: 1.05rem;">${amountFormatted}</span>
                </td>
                <td style="padding: 16px 24px; text-align: center; font-size: 0.85rem; color: #64748b; vertical-align: top;">
                    ${dateStr}
                </td>
                <td style="padding: 16px 24px; text-align: center; vertical-align: top;">
                    ${statusBadge}
                    ${reasonHtml}
                </td>
                <td style="padding: 16px 24px; text-align: right; vertical-align: top;">
                    <div style="display: flex; justify-content: flex-end; gap: 8px;">
                        ${isRejected ? `
                         <button onclick="app.modules.clients_alerts.correctAlert(${alert.client_id})" title="Corregir Pago" style="width:36px; height:36px; border-radius:10px; border:none; background:#eff6ff; color:#3b82f6; cursor:pointer; transition:all 0.2s;">
                            <i class="fas fa-edit"></i>
                         </button>
                         <button onclick="app.modules.clients_alerts.deleteAlert(${alert.id})" title="Descartar Alerta" style="width:36px; height:36px; border-radius:10px; border:none; background:#fef2f2; color:#ef4444; cursor:pointer; transition:all 0.2s;">
                            <i class="fas fa-trash"></i>
                         </button>
                        ` : isAdmin ? `
                         <button onclick="app.modules.clients_alerts.rejectAlert(${alert.id})" title="Rechazar" style="width:36px; height:36px; border-radius:10px; border:none; background:#fef2f2; color:#ef4444; cursor:pointer; transition:all 0.2s;">
                            <i class="fas fa-times"></i>
                         </button>
                         <button onclick="app.modules.clients_alerts.approveAlert(${alert.id})" title="Aprobar" style="width:36px; height:36px; border-radius:10px; border:none; background:#ecfdf5; color:#10b981; cursor:pointer; transition:all 0.2s;">
                            <i class="fas fa-check"></i>
                         </button>
                        ` : `
                         <span style="color:#94a3b8; font-size:0.8rem; font-style:italic;">Sin acciones</span>
                        `}
                    </div>
                </td>
            `;

            tr.addEventListener('mouseenter', () => tr.style.background = '#f8fafc');
            tr.addEventListener('mouseleave', () => tr.style.background = 'transparent');

            this.tableBody.appendChild(tr);
        });
    }

    // Funciones de Administrador insertadas localmente
    async approveAlert(id) {
        if (!confirm('¿Está seguro de aprobar este pago? Esto afectará el balance del cliente y podría reactivar su servicio.')) return;

        try {
            if (window.app && window.app.showLoading) window.app.showLoading(true);
            const res = await this.api.post(`/api/payments/reported/${id}/approve`);
            if (window.toast) window.toast.success(res.message || 'Pago aprobado formalmente');
            await this.loadAlerts(); // Recargar tabla local de alertas
        } catch (e) {
            if (window.toast) window.toast.error(e.message || 'Error al aprobar el pago');
        } finally {
            if (window.app && window.app.showLoading) window.app.showLoading(false);
        }
    }

    async rejectAlert(id) {
        const reason = prompt('Motivo del rechazo (opcional):');
        if (reason === null) return; // Cancelled

        try {
            if (window.app && window.app.showLoading) window.app.showLoading(true);
            const res = await this.api.post(`/api/payments/reported/${id}/reject`, { reason });
            if (window.toast) window.toast.success('Pago reportado fue rechazado');
            await this.loadAlerts(); // Recargar tabla local de alertas
        } catch (e) {
            if (window.toast) window.toast.error(e.message || 'Error al rechazar el pago');
        } finally {
            if (window.app && window.app.showLoading) window.app.showLoading(false);
        }
    }

    async deleteAlert(alertId) {
        // Confirm before deleting
        let result = await Swal.fire({
            title: '¿Descartar Alerta?',
            text: 'Esta acción borrará la alerta de rechazo permanentemente.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#ef4444',
            cancelButtonColor: '#94a3b8',
            confirmButtonText: 'Sí, descartar',
            cancelButtonText: 'Cancelar'
        });

        if (result.isConfirmed) {
            try {
                if (window.app && window.app.showLoading) window.app.showLoading(true);
                const res = await this.api.delete(`/api/payments/alerts/${alertId}`);
                if (res.success) {
                    if (window.toast) window.toast.success(res.message || 'Alerta descartada.');
                    // Refresh listing
                    await this.loadAlerts();
                }
            } catch (err) {
                console.error('Error deleting alert:', err);
                if (window.toast) window.toast.error('Error al descartar alerta.');
            } finally {
                if (window.app && window.app.showLoading) window.app.showLoading(false);
            }
        }
    }

    correctAlert(clientId) {
        // To correct it, the user can open the payment modal with the client selected
        if (this.modalManager) {
            this.modalManager.open('payment', { client_id: clientId });
        } else {
            console.error("No modal manager available to open payment modal.");
        }
    }
}
