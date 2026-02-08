/**
 * Plans Manager Module - Frontend para gestión de planes
 */
export class PlansManagerModule {
    constructor(api, eventBus, viewManager) {
        this.api = api;
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.currentPlanId = null;
        console.log('📦 Plans Manager Module initialized');

        // Bind methods to this instance
        this.loadPlans = this.loadPlans.bind(this);
        this.openPlanModal = this.openPlanModal.bind(this);
        this.closePlanModal = this.closePlanModal.bind(this);
        this.handlePlanSubmit = this.handlePlanSubmit.bind(this);
        this.deletePlan = this.deletePlan.bind(this);
        this.showPlanClients = this.showPlanClients.bind(this);
        this.closePlanClientsModal = this.closePlanClientsModal.bind(this);
    }

    async load() {
        console.log('📦 Loading Plans Manager View...');
        this.showView();

        // Attach global functions for HTML onclick events
        window.openPlanModal = this.openPlanModal;
        window.closePlanModal = this.closePlanModal;
        window.handlePlanSubmit = this.handlePlanSubmit;
        window.deletePlan = this.deletePlan;
        window.showPlanClients = this.showPlanClients;
        window.closePlanClientsModal = this.closePlanClientsModal;
        window.editPlanById = (id) => {
            const plan = this.plans.find(p => p.id === id);
            if (plan) this.openPlanModal(plan);
        };

        await this.loadPlans();

        // Listen for type changes
        const typeSelect = document.getElementById('planType');
        if (typeSelect) {
            typeSelect.addEventListener('change', () => this.togglePPPoEFields());
        }
    }

    showView() {
        // Delegar visualización a ViewManager
        this.viewManager.showMainView('plans');
    }
    async loadPlans() {
        try {
            const plans = await this.api.get('/api/plans');
            this.plans = plans; // Guardar localmente

            const tbody = document.getElementById('plansTableBody');
            if (!tbody) return;

            tbody.innerHTML = '';

            plans.forEach(plan => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="padding-left: 24px;">
                        <div class="user-info-cell">
                            <strong style="font-size: 1.05rem; color: #1e293b;">${plan.name}</strong>
                        </div>
                    </td>
                    <td>
                        <div style="display: flex; flex-direction: column; gap: 2px;">
                            <div style="display: flex; gap: 6px; align-items: center;">
                                <span class="badge-speed down">
                                    <i class="fas fa-arrow-down"></i> ${this.formatMbps(plan.download_speed)}
                                </span>
                                <span class="badge-speed up">
                                    <i class="fas fa-arrow-up"></i> ${this.formatMbps(plan.upload_speed)}
                                </span>
                            </div>
                        </div>
                    </td>
                    <td>
                        <div style="display: flex; flex-direction: column;">
                            <span style="font-weight: 700; color: #334155; font-size: 1rem;">$${plan.monthly_price.toLocaleString()}</span>
                            <span style="font-size: 0.7rem; color: #64748b; font-weight: 600; text-transform: uppercase;">${plan.currency} / MES</span>
                        </div>
                    </td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <div style="width: 32px; height: 32px; border-radius: 8px; background: #f1f5f9; display: flex; align-items: center; justify-content: center; color: #64748b;">
                                <i class="fas fa-server" style="font-size: 0.9rem;"></i>
                            </div>
                            <div style="display: flex; flex-direction: column;">
                                <span style="font-weight: 600; color: #475569; font-size: 0.9rem;">${plan.router_name || 'Global'}</span>
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="badge-premium ${plan.service_type}">
                            ${plan.service_type.toUpperCase()}
                        </span>
                    </td>
                    <td>
                        <div onclick="window.showPlanClients(${plan.id}, '${plan.name}')" class="clients-counter-premium" style="cursor: pointer;" title="Ver Clientes">
                            <i class="fas fa-users"></i>
                            <span>${plan.clients_count || 0}</span>
                        </div>
                    </td>
                    <td style="text-align: right; padding-right: 24px;">
                        <div style="display: flex; justify-content: flex-end; gap: 10px;">
                            <button onclick='window.editPlanById(${plan.id})' class="btn-icon-action edit" title="Editar Plan">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button onclick="window.deletePlan(${plan.id})" class="btn-icon-action delete ${plan.clients_count > 0 ? 'disabled' : ''}" 
                                    title="${plan.clients_count > 0 ? 'No se puede eliminar: tiene clientes' : 'Eliminar Plan'}"
                                    ${plan.clients_count > 0 ? 'disabled' : ''}>
                                <i class="fas fa-trash-alt"></i>
                            </button>
                        </div>
                    </td>
                `;
                tbody.appendChild(tr);
            });

            const totalEl = document.getElementById('totalPlans');
            if (totalEl) totalEl.textContent = plans.length;

        } catch (error) {
            console.error('Error loading plans:', error);
            if (window.toast) window.toast.error('Error cargando planes');
        }
    }

    formatMbps(kbps) {
        if (!kbps) return '0 Mbps';
        const num = parseInt(kbps);

        // Si el número es gigante (ej: 15000000), asumimos que son BITS
        if (num >= 1000000) {
            return `${(num / 1000000).toFixed(0)} Mbps`;
        }

        // Si es moderado (ej: 30000), son Kbps
        if (num >= 1000) {
            return `${(num / 1024).toFixed(0)} Mbps`;
        }

        return `${num} Kbps`;
    }

    formatSpeed(kbps) {
        return this.formatMbps(kbps);
    }

    getTypeColor(type) {
        const colors = {
            'pppoe': 'bg-purple-100 text-purple-800',
            'hotspot': 'bg-orange-100 text-orange-800',
            'simple_queue': 'bg-gray-100 text-gray-800'
        };
        return colors[type] || 'bg-gray-100 text-gray-800';
    }
    openPlanModal(plan = null) {
        const modal = document.getElementById('planModal');
        const form = document.getElementById('planForm');

        this.currentPlanId = plan ? plan.id : null;
        document.getElementById('modalTitle').textContent = plan ? 'Editar Plan' : 'Nuevo Plan';

        if (plan) {
            document.getElementById('planId').value = plan.id;
            document.getElementById('planName').value = plan.name;
            document.getElementById('planDownload').value = plan.download_speed;
            document.getElementById('planUpload').value = plan.upload_speed;
            document.getElementById('planPrice').value = plan.monthly_price;
            document.getElementById('planCurrency').value = plan.currency;
            document.getElementById('planType').value = plan.service_type;
            document.getElementById('planProfile').value = plan.mikrotik_profile || '';
            document.getElementById('planRouter').value = plan.router_id || '';
            document.getElementById('planLocalAddress').value = plan.local_address || '';
            document.getElementById('planRemoteAddress').value = plan.remote_address || '';
        } else {
            form.reset();
            document.getElementById('planId').value = '';
            document.getElementById('planRouter').value = '';
            document.getElementById('planLocalAddress').value = '';
            document.getElementById('planRemoteAddress').value = '';
        }

        // Load routers if not loaded
        this.populateRouters();
        this.togglePPPoEFields();

        modal.classList.add('active');
    }

    togglePPPoEFields() {
        const type = document.getElementById('planType').value;
        const pppoeContainer = document.getElementById('pppoe-fields');
        if (pppoeContainer) {
            pppoeContainer.style.display = type === 'pppoe' ? 'grid' : 'none';
        }
    }

    async populateRouters() {
        try {
            const routers = await this.api.get('/api/routers');
            const select = document.getElementById('planRouter');
            if (!select) return;

            const currentVal = select.value;
            select.innerHTML = '<option value="">Global (Todos los routers)</option>' +
                routers.map(r => `<option value="${r.id}">${r.alias}</option>`).join('');

            if (currentVal) select.value = currentVal;
        } catch (e) { console.error("Error populating routers in plan modal", e); }
    }

    closePlanModal() {
        document.getElementById('planModal').classList.remove('active');
    }

    async handlePlanSubmit(e) {
        e.preventDefault();

        const data = {
            name: document.getElementById('planName').value,
            download_speed: parseInt(document.getElementById('planDownload').value),
            upload_speed: parseInt(document.getElementById('planUpload').value),
            monthly_price: parseFloat(document.getElementById('planPrice').value),
            currency: document.getElementById('planCurrency').value,
            service_type: document.getElementById('planType').value,
            mikrotik_profile: document.getElementById('planProfile').value,
            router_id: document.getElementById('planRouter').value ? parseInt(document.getElementById('planRouter').value) : null,
            local_address: document.getElementById('planLocalAddress').value,
            remote_address: document.getElementById('planRemoteAddress').value
        };

        const method = this.currentPlanId ? 'PUT' : 'POST';
        const url = this.currentPlanId ? `/api/plans/${this.currentPlanId}` : '/api/plans';

        try {
            // Using direct fetch wrapper via this.api
            let response;
            if (method === 'POST') response = await this.api.post(url, data);
            else response = await this.api.put(url, data);

            this.closePlanModal();
            this.loadPlans();
            if (window.toast) window.toast.success('Plan guardado exitosamente');

        } catch (error) {
            console.error('Error saving plan:', error);
            if (window.toast) window.toast.error('Error guardando plan');
        }
    }

    async deletePlan(id) {
        if (!confirm('¿Estás seguro de eliminar este plan?')) return;

        try {
            await this.api.delete(`/api/plans/${id}`);
            this.loadPlans();
            if (window.toast) window.toast.success('Plan eliminado');
        } catch (error) {
            console.error('Error deleting plan:', error);
            if (window.toast) window.toast.error('Error eliminando plan');
        }
    }

    async showPlanClients(planId, planName) {
        const modal = document.getElementById('planClientsModal');
        const title = document.getElementById('planClientsModalTitle');
        const tbody = document.getElementById('planClientsTableBody');
        const emptyState = document.getElementById('planClientsEmpty');

        if (!modal || !title || !tbody || !emptyState) return;

        title.textContent = `Clientes - ${planName}`;
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px;">Cargando clientes...</td></tr>';
        emptyState.style.display = 'none';

        modal.classList.add('active');

        try {
            const clients = await this.api.get(`/api/clients?plan_id=${planId}`);

            tbody.innerHTML = '';
            if (!clients || clients.length === 0) {
                emptyState.style.display = 'block';
                return;
            }

            clients.forEach(c => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="padding-left: 20px;">
                        <div style="font-weight: 600; color: #1e293b;">${c.legal_name}</div>
                        <small style="color: #64748b;">${c.subscriber_code}</small>
                    </td>
                    <td><span style="font-family: monospace; font-size: 0.85rem;">${c.username}</span></td>
                    <td><span style="color: #4f46e5; font-weight: 600; font-family: monospace;">${c.ip_address || '-'}</span></td>
                    <td>
                        <span class="badge ${c.status === 'active' ? 'online' : (c.status === 'suspended' ? 'warning' : 'danger')}" 
                              style="font-size: 0.65rem; padding: 2px 8px;">
                            ${c.status.toUpperCase()}
                        </span>
                    </td>
                `;
                tbody.appendChild(tr);
            });

        } catch (error) {
            console.error('Error fetching plan clients:', error);
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #ef4444; padding: 20px;">Error al cargar clientes</td></tr>';
        }
    }

    closePlanClientsModal() {
        const modal = document.getElementById('planClientsModal');
        if (modal) modal.classList.remove('active');
    }
}
