/**
 * Routers Module - Gestión de Routers MikroTik
 */
export class RoutersModule {
    constructor(api, eventBus) {
        this.api = api;
        this.eventBus = eventBus;
        this.routers = [];

        console.log('🌐 Routers Module initialized');
    }

    async load() {
        console.log('🌐 Loading Routers...');

        // Mostrar vista
        this.showView();

        // Cargar routers
        await this.loadRouters();
    }

    showView() {
        document.querySelectorAll('.content-view').forEach(v => v.classList.remove('active'));
        const view = document.getElementById('routers-view');
        if (view) view.classList.add('active');
    }

    async loadRouters() {
        try {
            this.routers = await this.api.get('/api/routers');
            this.renderRouters();

            // Iniciar monitoreo en vivo (Keep-Alive)
            this.startLiveMonitor();

        } catch (error) {
            console.error('Error loading routers:', error);
            this.routers = [];
            this.renderRouters();
        }
    }

    startLiveMonitor() {
        if (this.monitorInterval) clearInterval(this.monitorInterval);

        // Polling cada 2 segundos (Casi tiempo real)
        this.monitorInterval = setInterval(async () => {
            // Detener si no estamos viendo routers
            const view = document.getElementById('routers-view');
            if (!view || !view.classList.contains('active')) return;

            try {
                // Llamar al endpoint optimizado de monitoreo
                const liveData = await this.api.get('/api/routers/monitor');
                this.updateRouterCards(liveData);
            } catch (e) {
                // Silencioso para no saturar consola en errores de red
            }
        }, 2000);
    }

    updateRouterCards(liveData) {
        liveData.forEach(data => {
            // Encontrar la tarjeta correspondiente
            // Buscamos el botón de sync que tiene el ID más fiable
            const syncBtn = document.querySelector(`button[onclick="app.modules.routers.syncRouter(${data.id})"]`);
            if (!syncBtn) return;

            const card = syncBtn.closest('.router-card');
            if (!card) return;

            // Actualizar estado visual (borde/punto)
            const statusDot = card.querySelector('.status-dot-mini');
            const statusBar = card.querySelector('.card-status-bar');

            card.classList.remove('online', 'offline');
            card.classList.add(data.status);

            // Actualizar valores numéricos
            if (data.status === 'online') {
                // CPU
                const cpuVal = card.querySelector('.stat-group:first-child .stat-value');
                const cpuBar = card.querySelector('.stat-group:first-child .bar');
                if (cpuVal) cpuVal.textContent = `${data.cpu_usage}%`;
                if (cpuBar) {
                    cpuBar.style.width = `${data.cpu_usage}%`;
                    cpuBar.style.backgroundColor = data.cpu_usage > 80 ? '#ef4444' : data.cpu_usage > 50 ? '#f59e0b' : '#10b981';
                }

                // RAM
                const ramVal = card.querySelector('.stat-group:nth-child(2) .stat-value');
                const ramBar = card.querySelector('.stat-group:nth-child(2) .bar');
                if (ramVal) ramVal.textContent = `${data.memory_usage}%`;
                if (ramBar) ramBar.style.width = `${data.memory_usage}%`;

                // Clientes
                const clientsVal = card.querySelector('.meta-item:first-child .meta-value');
                if (clientsVal) clientsVal.textContent = data.clients_connected;
            }
        });
    }

    renderRouters() {
        const grid = document.getElementById('routers-grid');
        if (!grid) return;

        if (this.routers.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <rect x="2" y="2" width="20" height="8" rx="2"/>
                            <rect x="2" y="14" width="20" height="8" rx="2"/>
                            <line x1="6" y1="6" x2="6.01" y2="6"/>
                            <line x1="6" y1="18" x2="6.01" y2="18"/>
                        </svg>
                    </div>
                    <h3>No hay routers configurados</h3>
                    <p>Agrega tu primer router MikroTik para comenzar a gestionar tu red.</p>
                    <button onclick="app.modules.routers.showCreateModal()" class="btn-primary glow-effect">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
                        Agregar Router
                    </button>
                </div>
            `;
            return;
        }

        grid.innerHTML = this.routers.map(router => {
            // Calcular colores de estado
            const statusClass = router.status ? router.status.toLowerCase() : 'offline';
            const isOnline = statusClass === 'online';

            // Formatear uptime
            let uptimeDisplay = router.uptime || 'N/A';

            // Calcular uso de recursos para barras de progreso
            const cpu = parseInt(router.cpu_usage || 0);
            const ram = parseInt(router.memory_usage || 0);
            const cpuColor = cpu > 80 ? '#ef4444' : cpu > 50 ? '#f59e0b' : '#10b981';
            const ramColor = ram > 80 ? '#ef4444' : ram > 50 ? '#f59e0b' : '#3b82f6';

            return `
            <div class="router-card ${statusClass}">
                <div class="card-status-bar"></div>
                <div class="router-main">
                    <div class="router-header">
                        <div class="router-identity">
                            <div class="router-name-row">
                                <span class="status-dot-mini"></span>
                                <h3 class="router-alias" title="${router.alias}">${router.alias || 'Router Sin Nombre'}</h3>
                            </div>
                            <span class="router-ip">${router.host_address}</span>
                        </div>
                        <div class="router-actions">
                            <button onclick="app.modules.routers.syncRouter(${router.id})" class="action-btn minimal" title="Sincronizar">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3"/></svg>
                            </button>
                            <button onclick="app.modules.routers.editRouter(${router.id})" class="action-btn minimal" title="Configurar">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                            </button>
                        </div>
                    </div>
                
                    <div class="router-stats-minimal">
                        <div class="stat-group">
                            <div class="stat-info">
                                <span class="stat-label">CPU</span>
                                <span class="stat-value">${cpu}%</span>
                            </div>
                            <div class="progress-bar-minimal">
                                <div class="bar" style="width: ${cpu}%; background-color: ${cpuColor}"></div>
                            </div>
                        </div>
                        <div class="stat-group">
                            <div class="stat-info">
                                <span class="stat-label">RAM</span>
                                <span class="stat-value">${ram}%</span>
                            </div>
                            <div class="progress-bar-minimal">
                                <div class="bar" style="width: ${ram}%; background-color: ${ramColor}"></div>
                            </div>
                        </div>
                    </div>

                    <div class="router-meta-grid">
                        <div class="meta-item">
                            <span class="meta-label">Clientes</span>
                            <span class="meta-value">${router.clients_connected || 0}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Uptime</span>
                            <span class="meta-value">${uptimeDisplay.replace(/(\d+)([dhm])/g, '$1$2 ')}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Zona</span>
                            <span class="meta-value">${router.zone || '-'}</span>
                        </div>
                    </div>
                </div>
            </div>
            `;
        }).join('');
    }

    async syncRouter(routerId) {
        const btn = document.querySelector(`button[onclick="app.modules.routers.syncRouter(${routerId})"]`);
        const originalContent = btn ? btn.innerHTML : '';

        if (btn) {
            btn.innerHTML = '<div class="spinner-mini"></div>'; // Necesitarías CSS para esto, o usa un texto simple
            btn.disabled = true;
            btn.style.opacity = '0.7';
        }

        try {
            console.log('Syncing router', routerId);
            const result = await this.api.post(`/api/routers/${routerId}/sync`, {});

            if (result.success) {
                // Notificación Toast sería mejor, pero alert por ahora
                // alert('Router sincronizado correctamente');
                await this.loadRouters();
            } else {
                alert(`Error: ${result.message}`);
            }
        } catch (error) {
            console.error('Error syncing router:', error);
            // Intentar extraer mensaje del backend si existe
            let msg = error.message;
            if (error.response && error.response.data && error.response.data.message) {
                msg = error.response.data.message;
            }
            alert(`Fallo en sincronización: ${msg}\n\nVerifica que la IP sea accesible desde este servidor.`);
        } finally {
            if (btn) {
                btn.innerHTML = originalContent;
                btn.disabled = false;
                btn.style.opacity = '1';
            }
        }
    }

    async editRouter(routerId) {
        console.log('Edit router', routerId);
        alert('Función de edición en desarrollo');
    }

    async deleteRouter(routerId) {
        if (!confirm('¿Eliminar este router?')) return;

        try {
            await this.api.delete(`/api/routers/${routerId}`);
            await this.loadRouters();
            alert('Router eliminado correctamente');
        } catch (error) {
            console.error('Error deleting router:', error);
            alert('Error al eliminar router');
        }
    }

    showCreateModal() {
        alert('Modal de creación en desarrollo');
    }
}
