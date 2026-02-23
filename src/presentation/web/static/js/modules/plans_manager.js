/**
 * Plans Manager Module - Frontend para gestión de planes
 */
export class PlansManagerModule {
    constructor(api, eventBus, viewManager, modalManager = null) {
        this.api = api;
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.modalManager = modalManager;
        this.currentPlanId = null;
        this.sortState = { column: 'name', direction: 'asc' };
        this.clientSortState = { column: 'legal_name', direction: 'asc' };
        console.log('📦 Plans Manager Module initialized');

        // Bind methods to this instance
        this.loadPlans = this.loadPlans.bind(this);
        this.deletePlan = this.deletePlan.bind(this);
        this.showPlanClients = this.showPlanClients.bind(this);
        this.closePlanClientsModal = this.closePlanClientsModal.bind(this);

        // Listen for modal events if modalManager is present
        if (this.modalManager) {
            document.addEventListener('modal:plan:plan-saved', () => this.loadPlans());
        }
    }

    async load() {
        console.log('📦 Loading Plans Manager View...');
        this.showView();

        // Attach global functions for HTML onclick events
        window.openPlanModal = () => this.openPlanModal();
        window.deletePlan = this.deletePlan;
        window.showPlanClients = this.showPlanClients;
        window.closePlanClientsModal = this.closePlanClientsModal;
        window.sortPlansBy = (col) => this.sortBy(col);
        window.sortPlanClientsBy = (col) => this.sortByClients(col);
        window.editPlanById = (id) => {
            const plan = this.plans.find(p => p.id === id);
            if (plan) this.openPlanModal(plan);
        };

        await this.loadPlans();
    }

    showView() {
        // Delegar visualización a ViewManager
        this.viewManager.showMainView('plans');
    }
    async loadPlans() {
        try {
            const plans = await this.api.get('/api/plans');
            this.plans = plans || []; // Guardar localmente
            this.renderPlansTable();

            const totalEl = document.getElementById('totalPlans');
            if (totalEl) totalEl.textContent = this.plans.length;
        } catch (error) {
            console.error('Error loading plans:', error);
            if (window.toast) window.toast.error('Error cargando planes');
        }
    }

    sortBy(column) {
        if (this.sortState.column === column) {
            this.sortState.direction = this.sortState.direction === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortState.column = column;
            this.sortState.direction = 'asc';
        }
        this.renderPlansTable();
    }

    renderPlansTable() {
        // Find containers via ID
        const view = document.getElementById('plans-view');
        const tbody = document.getElementById('plansTableBody');

        if (!tbody || !this.plans) return;

        // Upgrade container class if exists (Safer selection relative to table)
        const table = tbody.closest('table');
        if (table) {
            const container = table.parentElement;
            // Verificar si es el div contenedor viejo (bg-white/70...)
            if (container && container.tagName === 'DIV' && !container.classList.contains('plans-wrapper')) {
                container.className = 'plans-wrapper';
                table.className = 'premium-plans-table';
            }
        }

        const dir = this.sortState.direction === 'asc' ? 1 : -1;
        const col = this.sortState.column;

        const sorted = [...this.plans].sort((a, b) => {
            let valA = a[col];
            let valB = b[col];

            if (col === 'download_speed' || col === 'monthly_price' || col === 'clients_count') {
                return (parseFloat(valA || 0) - parseFloat(valB || 0)) * dir;
            }

            return (valA || '').toString().localeCompare((valB || '').toString()) * dir;
        });

        tbody.innerHTML = '';
        sorted.forEach(plan => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="padding-left: 24px;">
                    <div class="plan-name-cell">
                        <span class="plan-name">${plan.name}</span>
                        <span class="plan-id">ID: ${plan.id}</span>
                    </div>
                </td>
                <td>
                    <div class="speed-badge-group">
                        <span class="speed-badge down" title="Descarga">
                            <i class="fas fa-arrow-down"></i> ${this.formatMbps(plan.download_speed)}
                        </span>
                        <span class="speed-badge up" title="Subida">
                             ${this.formatMbps(plan.upload_speed)} <i class="fas fa-arrow-up"></i>
                        </span>
                    </div>
                </td>
                <td>
                    <div style="display: flex; flex-direction: column;">
                        <span class="price-display">$${plan.monthly_price.toLocaleString()}<span class="currency-tag">${plan.currency}</span></span>
                    </div>
                </td>
                <td>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div style="width: 32px; height: 32px; border-radius: 8px; background: #e0f2fe; display: flex; align-items: center; justify-content: center; color: #0284c7;">
                            <i class="fas fa-server"></i>
                        </div>
                        <span style="font-weight: 600; color: #475569; font-size: 0.85rem;">${plan.router_name || 'Global'}</span>
                    </div>
                </td>
                <td>
                    <span class="service-badge ${plan.service_type}">
                         <i class="fas fa-network-wired" style="font-size: 0.6rem;"></i> ${plan.service_type.toUpperCase()}
                    </span>
                </td>
                <td>
                    <div onclick="window.showPlanClients(${plan.id}, '${plan.name}')" class="clients-counter-pill ${plan.clients_count > 0 ? 'has-clients' : ''}" title="Ver Clientes">
                        <i class="fas fa-users"></i>
                        <span>${plan.clients_count || 0} Clientes</span>
                    </div>
                </td>
                <td style="text-align: right; padding-right: 24px;">
                    <div class="plan-actions-cell">
                        <button onclick='window.editPlanById(${plan.id})' class="btn-icon-soft edit" title="Editar Plan">
                            <i class="fas fa-pen"></i>
                        </button>
                        <button onclick="window.deletePlan(${plan.id})" class="btn-icon-soft delete ${plan.clients_count > 0 ? 'disabled' : ''}" 
                                title="${plan.clients_count > 0 ? 'No se puede eliminar: tiene clientes' : 'Eliminar Plan'}"
                                ${plan.clients_count > 0 ? 'disabled' : ''}>
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });

        this.renderSortIcons('plans-view', this.sortState);
        this.renderPlansCards(sorted);
    }

    renderPlansCards(plans) {
        const grid = document.getElementById('plans-cards-grid');
        if (!grid) return;

        grid.innerHTML = plans.map(plan => `
            <div class="plan-card-mobile">
                <div class="card-mobile-header">
                    <div class="card-mobile-client-info">
                        <div class="card-mobile-avatar" style="background: linear-gradient(135deg, #4f46e5, #818cf8);">
                            <i class="fas fa-layer-group"></i>
                        </div>
                        <div class="card-mobile-name-group">
                            <span class="card-mobile-name">${plan.name}</span>
                            <span class="card-mobile-code">ID: ${plan.id}</span>
                        </div>
                    </div>
                </div>
                
                <div class="card-mobile-body">
                    <div class="card-mobile-data-item">
                        <span class="data-item-label">Velocidad</span>
                        <span class="data-item-value">${this.formatMbps(plan.download_speed)} / ${this.formatMbps(plan.upload_speed)}</span>
                    </div>
                    <div class="card-mobile-data-item">
                        <span class="data-item-label">Servicio</span>
                        <span class="data-item-value">${plan.service_type.toUpperCase()}</span>
                    </div>
                    <div class="card-mobile-data-item">
                        <span class="data-item-label">Router</span>
                        <span class="data-item-value">${plan.router_name || 'Global'}</span>
                    </div>
                    <div class="card-mobile-data-item">
                        <span class="data-item-label">Clientes</span>
                        <span class="data-item-value">${plan.clients_count || 0} Activos</span>
                    </div>
                </div>

                <div class="card-mobile-footer">
                    <div class="card-mobile-balance">
                        <span class="balance-label">Tarifa Mensual</span>
                        <span class="balance-value ok">$${plan.monthly_price.toLocaleString()} ${plan.currency}</span>
                    </div>
                    <div class="card-mobile-actions">
                        <button onclick="window.editPlanById(${plan.id})" class="mobile-action-btn edit">
                            <i class="fas fa-pen"></i>
                        </button>
                        <button onclick="window.showPlanClients(${plan.id}, '${plan.name}')" class="mobile-action-btn more">
                            <i class="fas fa-users"></i>
                        </button>
                        <button onclick="window.deletePlan(${plan.id})" 
                                class="mobile-action-btn delete ${plan.clients_count > 0 ? 'disabled' : ''}"
                                ${plan.clients_count > 0 ? 'disabled' : ''}>
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
    }

    renderSortIcons(viewId, state) {
        const view = document.getElementById(viewId);
        if (!view) return;

        const headers = view.querySelectorAll('th.sortable');
        headers.forEach(th => {
            const icon = th.querySelector('i');
            th.classList.remove('active-sort');
            if (icon) icon.className = 'fas fa-sort';

            const onClickAttr = th.getAttribute('onclick');
            if (onClickAttr && onClickAttr.includes(`'${state.column}'`)) {
                th.classList.add('active-sort');
                if (icon) {
                    icon.className = state.direction === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down';
                }
            }
        });
    }

    sortByClients(column) {
        if (this.clientSortState.column === column) {
            this.clientSortState.direction = this.clientSortState.direction === 'asc' ? 'desc' : 'asc';
        } else {
            this.clientSortState.column = column;
            this.clientSortState.direction = 'asc';
        }
        this.renderPlanClientsTable();
    }

    renderPlanClientsTable() {
        const tbody = document.getElementById('planClientsTableBody');
        const emptyState = document.getElementById('planClientsEmpty');
        if (!tbody || !this.currentClients) return;

        const dir = this.clientSortState.direction === 'asc' ? 1 : -1;
        const col = this.clientSortState.column;

        const sorted = [...this.currentClients].sort((a, b) => {
            let valA = a[col] || '';
            let valB = b[col] || '';
            return valA.toString().localeCompare(valB.toString(), undefined, { numeric: true }) * dir;
        });

        tbody.innerHTML = '';
        if (sorted.length === 0) {
            if (emptyState) emptyState.style.display = 'block';
            return;
        }
        if (emptyState) emptyState.style.display = 'none';

        sorted.forEach(c => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="padding-left: 20px;">
                    <div style="font-weight: 600; color: #1e293b;">${c.legal_name}</div>
                    <small style="color: #64748b;">${c.subscriber_code}</small>
                </td>
                <td><span style="font-family: monospace; font-size: 0.85rem;">${c.username}</span></td>
                <td><span style="color: #4f46e5; font-weight: 600; font-family: monospace;">${c.ip_address || '-'}</span></td>
                <td>
                    <span class="status-badge-table ${c.status === 'active' ? 'active' : (c.status === 'suspended' ? 'suspended' : 'cortado')}" 
                          style="font-size: 0.65rem; padding: 2px 8px;">
                        ${c.status.toUpperCase()}
                    </span>
                </td>
            `;
            tbody.appendChild(tr);
        });

        this.renderSortIcons('planClientsModal', this.clientSortState);
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
        if (this.modalManager) {
            this.modalManager.open('plan', { plan });
        } else {
            console.error('ModalManager not available for Plan Modal');
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

        if (this.modalManager) {
            this.modalManager.open('plan-clients');
        } else {
            modal.classList.add('active');
        }

        try {
            const clients = await this.api.get(`/api/clients?plan_id=${planId}`);
            this.currentClients = clients || [];
            this.renderPlanClientsTable();

        } catch (error) {
            console.error('Error fetching plan clients:', error);
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #ef4444; padding: 20px;">Error al cargar clientes</td></tr>';
        }
    }

    closePlanClientsModal() {
        if (this.modalManager) {
            this.modalManager.close('plan-clients');
        } else {
            const modal = document.getElementById('planClientsModal');
            if (modal) modal.classList.remove('active');
        }
    }
}
