/**
 * Dashboard Module - Vista Principal
 */
export class DashboardModule {
    constructor(api, eventBus) {
        this.api = api;
        this.eventBus = eventBus;
        this.servers = [];

        console.log('📊 Dashboard Module initialized');
    }

    async load() {
        console.log('📊 Loading Dashboard...');

        // Mostrar vista
        this.showView();

        // Cargar datos
        await Promise.all([
            this.loadStats(),
            this.loadServers(),
            this.loadActivity()
        ]);
    }

    showView() {
        // Ocultar todas las vistas
        document.querySelectorAll('.content-view').forEach(v => v.classList.remove('active'));

        // Mostrar dashboard
        const view = document.getElementById('dashboard-view');
        if (view) {
            view.classList.add('active');
        }
    }

    async loadStats() {
        try {
            const stats = await this.api.get('/api/dashboard/stats');
            this.renderStats(stats);
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    async loadServers() {
        try {
            const servers = await this.api.get('/api/routers');
            this.servers = servers;
            this.renderServers();
        } catch (error) {
            console.error('Error loading servers:', error);
            this.servers = [];
        }
    }

    async loadActivity() {
        try {
            const activity = await this.api.get('/api/activity/recent');
            this.renderActivity(activity);
        } catch (error) {
            console.error('Error loading activity:', error);
        }
    }

    renderStats(stats) {
        // Actualizar tarjetas de estadísticas
        const statServers = document.getElementById('stat-servers');
        const statClients = document.getElementById('stat-clients');
        const statRevenue = document.getElementById('stat-revenue');
        const statUptime = document.getElementById('stat-uptime');

        if (statServers) statServers.textContent = stats.total_servers || 0;
        if (statClients) statClients.textContent = stats.active_clients || 0;
        if (statRevenue) statRevenue.textContent = `$${(stats.monthly_revenue || 0).toFixed(2)}`;
        if (statUptime) statUptime.textContent = `${(stats.average_uptime || 0).toFixed(1)}%`;

        // Actualizar contadores de estado
        const serversOnline = document.getElementById('servers-online');
        const serversWarning = document.getElementById('servers-warning');
        const serversOffline = document.getElementById('servers-offline');

        if (serversOnline) serversOnline.textContent = stats.servers_online || 0;
        if (serversWarning) serversWarning.textContent = stats.servers_warning || 0;
        if (serversOffline) serversOffline.textContent = stats.servers_offline || 0;
    }

    renderServers() {
        const container = document.getElementById('servers-list');
        if (!container) return;

        if (this.servers.length === 0) {
            container.innerHTML = '<p style="color: rgba(255,255,255,0.5); padding: 1rem;">No hay routers configurados</p>';
            return;
        }

        container.innerHTML = this.servers.map(server => `
            <div class="server-mini-item" onclick="app.modules.navigation.navigate('routers')">
                <div class="server-status ${server.status?.toLowerCase() || 'offline'}"></div>
                <div class="server-info">
                    <span class="server-name">${server.alias || 'Sin nombre'}</span>
                    <span class="server-address">${server.host_address || 'N/A'}</span>
                </div>
                <div class="server-metrics">
                    <span>${server.clients_connected || 0} clientes</span>
                </div>
            </div>
        `).join('');
    }

    renderActivity(activities) {
        const container = document.getElementById('activity-list');
        if (!container) return;

        if (!activities || activities.length === 0) {
            container.innerHTML = '<p style="color: rgba(255,255,255,0.5); padding: 1rem;">No hay actividad reciente</p>';
            return;
        }

        container.innerHTML = activities.map(activity => `
            <div class="activity-item">
                <div class="activity-icon ${activity.type}">
                    <i class="fas fa-${this.getActivityIcon(activity.type)}"></i>
                </div>
                <div class="activity-content">
                    <p class="activity-text">${activity.message}</p>
                    <span class="activity-time">${this.formatTime(activity.timestamp)}</span>
                </div>
            </div>
        `).join('');
    }

    getActivityIcon(type) {
        const icons = {
            'server': 'server',
            'client': 'user',
            'payment': 'dollar-sign',
            'system': 'cog',
            'alert': 'exclamation-triangle'
        };
        return icons[type] || 'circle';
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;

        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (minutes < 1) return 'Ahora';
        if (minutes < 60) return `Hace ${minutes} min`;
        if (hours < 24) return `Hace ${hours}h`;
        return `Hace ${days}d`;
    }
}
