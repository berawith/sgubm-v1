/**
 * Sync Dashboard Component
 * Maneja la visualización y control de la cola de sincronización de MikroTik
 */
class SyncDashboard {
    constructor(elementId) {
        this.container = document.getElementById(elementId);
        this.templateUrl = '/static/js/components/sync-dashboard/sync-dashboard.template.html';
        this.socket = window.socket || (window.app ? window.app.socket : null); // Referencia global al socket
        this._initialized = false;
    }

    async init() {
        if (this._initialized) return;

        try {
            // Re-chequear socket por si se inicializó tarde
            if (!this.socket) {
                this.socket = window.socket || (window.app ? window.app.socket : null);
            }

            const response = await fetch(this.templateUrl);
            const template = await response.text();
            this.container.innerHTML = template;

            this.setupEventListeners();
            this.setupSocketEvents();
            await this.reloadData();

            this._initialized = true;
            console.log("✅ SyncDashboard initialized");
        } catch (error) {
            console.error("❌ Error initializing SyncDashboard:", error);
        }
    }

    setupEventListeners() {
        // Botón Forzar Sincronización Global
        const forceAllBtn = document.getElementById('sync-force-all-btn');
        if (forceAllBtn) {
            forceAllBtn.addEventListener('click', () => this.handleForceSyncAll());
        }

        // Botón Actualizar Historial
        const refreshHistoryBtn = document.getElementById('refresh-history-btn');
        if (refreshHistoryBtn) {
            refreshHistoryBtn.addEventListener('click', () => this.loadHistory());
        }
    }

    setupSocketEvents() {
        if (!this.socket) {
            console.warn("⚠️ SocketIO not available for SyncDashboard");
            return;
        }

        // Escuchar eventos de sincronización completada/fallida
        this.socket.on('sync_completed', (data) => {
            console.log("🔄 Sync completed event:", data);
            this.showNotification(`Sincronización exitosa en ${data.router_name}: ${data.completed} tareas procesadas.`, 'success');
            this.reloadData();
        });

        this.socket.on('sync_failed', (data) => {
            console.warn("⚠️ Sync failed event:", data);
            this.showNotification(`Error de sincronización en ${data.router_name}: ${data.failed} tareas fallidas.`, 'error');
            this.reloadData();
        });
    }

    async reloadData() {
        await Promise.all([
            this.loadStats(),
            this.loadPendingOperations(),
            this.loadHistory()
        ]);
    }

    async loadStats() {
        try {
            const response = await fetch('/api/sync/stats');
            const data = await response.json();

            if (data.success) {
                document.getElementById('stat-pending-count').textContent = data.stats.total_pending;
                document.getElementById('stat-completed-count').textContent = data.stats.last_24h.completed;
                document.getElementById('stat-failed-count').textContent = data.stats.last_24h.failed;
                document.getElementById('pending-badge').textContent = `${data.stats.total_pending} en espera`;
            }
        } catch (error) {
            console.error("Error loading sync stats:", error);
        }
    }

    async loadPendingOperations() {
        try {
            const response = await fetch('/api/sync/pending');
            const data = await response.json();

            const tbody = document.getElementById('pending-operations-list');
            if (!tbody) return;

            if (data.success && data.operations.length > 0) {
                tbody.innerHTML = '';
                data.operations.forEach(op => {
                    const row = document.createElement('tr');
                    row.className = 'premium-row';
                    row.innerHTML = `
                        <td><span class="badge-premium" style="background:rgba(30, 27, 75, 0.05); color:var(--accent-dark);">#${op.id}</span></td>
                        <td><span class="badge-premium" style="background:rgba(99, 102, 241, 0.15); color:var(--accent-primary); border-color: rgba(99,102,241,0.2);">${op.operation_type.toUpperCase()}</span></td>
                        <td style="font-weight:800; color:var(--accent-dark);">Cliente #${op.client_id}<br><small style="color:#64748b; font-weight:600; font-size: 0.7rem;">${op.ip_address}</small></td>
                        <td><span style="font-weight:700; color:#475569; font-size: 0.85rem;">Router #${op.router_id}</span></td>
                        <td>
                            <div style="display:flex; align-items:center; gap:5px;">
                                <span style="font-weight:900; color:var(--accent-dark);">${op.attempts}</span>
                                <div style="width:30px; height:4px; background:rgba(0,0,0,0.05); border-radius:10px; overflow:hidden;">
                                    <div style="width:${(op.attempts / 5) * 100}%; height:100%; background:var(--accent-primary);"></div>
                                </div>
                                <span style="color:#94a3b8; font-size:0.7rem;">/ 5</span>
                            </div>
                        </td>
                        <td title="${op.created_at}" style="font-weight:600; color:#64748b;">${this.formatDate(op.created_at)}</td>
                        <td class="text-right">
                            <div class="action-buttons">
                                <button class="btn-action-premium cancel" onclick="syncDashboard.cancelOperation(${op.id})">
                                    <i class="fas fa-trash-alt"></i> Cancelar
                                </button>
                                <button class="btn-action-premium force" onclick="syncDashboard.handleForceSync(${op.router_id})">
                                    <i class="fas fa-play"></i> Sincronizar
                                </button>
                            </div>
                        </td>
                    `;
                    tbody.appendChild(row);
                });
            } else {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7" class="empty-state">
                            <i class="fas fa-ghost"></i> No hay operaciones pendientes
                        </td>
                    </tr>
                `;
            }
        } catch (error) {
            console.error("Error loading pending operations:", error);
        }
    }

    async loadHistory() {
        try {
            const response = await fetch('/api/sync/history?limit=15');
            const data = await response.json();

            const tbody = document.getElementById('sync-history-list');
            if (!tbody) return;

            if (data.success && data.history.length > 0) {
                tbody.innerHTML = '';
                data.history.forEach(op => {
                    const row = document.createElement('tr');
                    const statusClass = op.status === 'completed' ? 'completed' : 'failed';
                    const icon = op.status === 'completed' ? 'fa-check-circle' : 'fa-exclamation-circle';

                    row.innerHTML = `
                        <td style="font-weight:800; color:var(--accent-dark);">${op.operation_type.toUpperCase()}</td>
                        <td style="font-size:0.8rem; color:#475569;">
                            <span style="font-weight:700;">ID:${op.client_id}</span> <br> 
                            <small style="color:var(--accent-secondary); font-weight:700; font-family:'JetBrains Mono'; font-size:0.7rem;">${op.ip_address}</small>
                        </td>
                        <td>
                            <span class="stat-pill-history ${statusClass}" style="box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                                <i class="fas ${icon}"></i> ${op.status.toUpperCase()}
                            </span>
                        </td>
                        <td style="font-weight:700; color:#64748b; font-size: 0.75rem;">${this.formatDate(op.last_attempt)}</td>
                        <td>
                            ${op.error_message ? `<div class="error-cell" title="${op.error_message}" style="color:#e11d48; font-weight:500;">${op.error_message}</div>` : '<span style="color:#94a3b8;">-</span>'}
                        </td>
                    `;
                    tbody.appendChild(row);
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="5" class="empty-state">Historial vacío</td></tr>';
            }
        } catch (error) {
            console.error("Error loading history:", error);
        }
    }

    async cancelOperation(opId) {
        if (!confirm('¿Seguro que desea cancelar esta operación pendiente?')) return;

        try {
            const response = await fetch(`/api/sync/pending/${opId}`, { method: 'DELETE' });
            const data = await response.json();

            if (data.success) {
                this.showNotification("Operación cancelada correctamente", 'info');
                this.reloadData();
            }
        } catch (error) {
            console.error("Error canceling operation:", error);
        }
    }

    async handleForceSync(routerId) {
        try {
            this.showNotification("Iniciando sincronización manual...", 'info');
            const response = await fetch(`/api/sync/force/${routerId}`, { method: 'POST' });
            const data = await response.json();

            if (data.success) {
                this.showNotification(data.message, 'success');
            } else {
                this.showNotification(data.message, 'warning');
            }
            this.reloadData();
        } catch (error) {
            console.error("Error forcing sync:", error);
        }
    }

    async handleForceSyncAll() {
        try {
            this.showNotification("Sincronizando todos los routers online...", 'info');
            const response = await fetch('/api/sync/force-all', { method: 'POST' });
            const data = await response.json();

            if (data.success) {
                this.showNotification(data.message, 'success');
            } else {
                this.showNotification(data.message, 'warning');
            }
            this.reloadData();
        } catch (error) {
            console.error("Error forcing sync all:", error);
        }
    }

    formatDate(dateStr) {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        return date.toLocaleString('es-ES', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    showNotification(message, type = 'info') {
        // Intentar usar el sistema global de notificaciones si existe
        if (window.showToast) {
            window.showToast(message, type);
        } else {
            console.log(`[SYNC NOTIFY] [${type}] ${message}`);
            // Fallback simple si no hay sistema de Toasts
            alert(message);
        }
    }
}

// Singleton instance
window.syncDashboard = new SyncDashboard('dynamic-content-area');
