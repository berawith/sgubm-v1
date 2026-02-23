import { BaseModal } from '../shared/base-modal.component.js';

/**
 * Componente para creación y edición de planes de internet
 */
export class PlanModal extends BaseModal {
    constructor(api, eventBus) {
        super('plan', api, eventBus);
        this.currentPlanId = null;
        this.routers = [];
    }

    async init() {
        // Cargar template y estilos
        await this.loadResources(
            '/static/js/components/plan-modal/plan-modal.template.html',
            '/static/js/components/plan-modal/plan-modal.styles.css'
        );

        // Listeners específicos
        const typeSelect = this.modalElement.querySelector('#service_type');
        if (typeSelect) {
            typeSelect.addEventListener('change', () => this.togglePPPoEFields());
        }

        // Cargar routers para el select
        await this.loadRouters();
    }

    async loadRouters() {
        try {
            this.routers = await this.api.get('/api/routers');
            const select = this.modalElement.querySelector('#router_id');
            if (select) {
                const currentVal = select.value;
                select.innerHTML = '<option value="">Global (Todos los routers)</option>' +
                    this.routers.map(r => `<option value="${r.id}">${r.alias}</option>`).join('');
                if (currentVal) select.value = currentVal;
            }
        } catch (e) {
            console.error("Error loading routers in plan modal", e);
        }
    }

    togglePPPoEFields() {
        const typeSelect = this.modalElement.querySelector('#service_type');
        const pppoeContainer = this.modalElement.querySelector('#pppoe-fields-container');
        if (typeSelect && pppoeContainer) {
            pppoeContainer.style.display = typeSelect.value === 'pppoe' ? 'grid' : 'none';
        }
    }

    /**
     * @param {object} data - Datos del plan ({ plan: {...} })
     */
    async open(data = {}) {
        await this._initPromise;
        const plan = data.plan || null;
        this.currentPlanId = plan ? plan.id : null;

        const title = this.modalElement.querySelector('#plan-modal-title');
        const isEdit = !!(plan && plan.id);

        if (title) title.textContent = isEdit ? 'Editar Plan' : 'Nuevo Plan';

        const form = this.modalElement.querySelector('#plan-form');
        if (form) form.reset();

        if (isEdit) {
            this.setFormValues({
                id: plan.id,
                name: plan.name,
                download_speed: plan.download_speed,
                upload_speed: plan.upload_speed,
                monthly_price: (plan.monthly_price || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 }),
                currency: plan.currency,
                service_type: plan.service_type,
                mikrotik_profile: plan.mikrotik_profile || '',
                router_id: plan.router_id || '',
                local_address: plan.local_address || '',
                remote_address: plan.remote_address || ''
            });
        } else {
            // Valores por defecto + Datos prellenados (ej: router_id)
            const defaults = {
                id: '',
                name: '',
                download_speed: '',
                upload_speed: '',
                monthly_price: '',
                currency: 'COP',
                service_type: 'pppoe',
                mikrotik_profile: '',
                router_id: '',
                local_address: '',
                remote_address: ''
            };

            // Si viene data parcial (ej: router_id), sobreescribe defaults
            const merged = { ...defaults, ...(plan || {}) };
            this.setFormValues(merged);
        }

        this.togglePPPoEFields();
        super.open();
    }

    validate() {
        const name = this.modalElement.querySelector('#name').value.trim();
        const dl = this.modalElement.querySelector('#download_speed').value;
        const ul = this.modalElement.querySelector('#upload_speed').value;
        const rawPrice = this.modalElement.querySelector('#monthly_price').value || '0';
        const price = this.parseCurrencyValue(rawPrice);

        if (!name) {
            this.showError('El nombre del plan es obligatorio');
            return false;
        }
        if (!dl || dl <= 0) {
            this.showError('La velocidad de descarga debe ser mayor a 0');
            return false;
        }
        if (!ul || ul <= 0) {
            this.showError('La velocidad de subida debe ser mayor a 0');
            return false;
        }
        if (!price || price < 0) {
            this.showError('El precio no puede ser negativo');
            return false;
        }

        return true;
    }

    getFormData() {
        const form = this.modalElement.querySelector('#plan-form');
        const formData = new FormData(form);
        const data = {};

        // Mapear campos manualmente para asegurar tipos correctos
        data.name = this.modalElement.querySelector('#name').value.trim();
        data.download_speed = parseInt(this.modalElement.querySelector('#download_speed').value);
        data.upload_speed = parseInt(this.modalElement.querySelector('#upload_speed').value);
        const rawPrice = this.modalElement.querySelector('#monthly_price').value || '0';
        data.monthly_price = this.parseCurrencyValue(rawPrice);
        data.currency = this.modalElement.querySelector('#currency').value;
        data.service_type = this.modalElement.querySelector('#service_type').value;
        data.mikrotik_profile = this.modalElement.querySelector('#mikrotik_profile').value.trim();

        const routerId = this.modalElement.querySelector('#router_id').value;
        data.router_id = routerId ? parseInt(routerId) : null;

        data.local_address = this.modalElement.querySelector('#local_address').value.trim();
        data.remote_address = this.modalElement.querySelector('#remote_address').value.trim();

        return data;
    }

    async handleSubmit(e) {
        e.preventDefault();

        if (!this.validate()) return;

        const data = this.getFormData();
        const method = this.currentPlanId ? 'PUT' : 'POST';
        const url = this.currentPlanId ? `/api/plans/${this.currentPlanId}` : '/api/plans';

        try {
            this.showLoading();
            let response;
            if (method === 'POST') {
                response = await this.api.post(url, data);
            } else {
                response = await this.api.put(url, data);
            }

            // Emitir evento de éxito
            this.emit('plan-saved', { plan: response });

            // Publicar en EventBus global
            this.eventBus.publish('plan_saved', response);

            if (window.toast) window.toast.success('Plan guardado exitosamente');
            this.close();
        } catch (error) {
            console.error('Error saving plan:', error);
            this.showError(error.message || 'Error guardando plan');
        } finally {
            this.hideLoading();
        }
    }
    /**
     * Formats an input value with thousands separators while typing
     */
    formatCurrencyInput(input) {
        if (!input) return;
        let value = input.value.replace(/[^\d.]/g, '');
        const parts = value.split('.');
        if (parts.length > 2) value = parts[0] + '.' + parts.slice(1).join('');
        if (value === '') { input.value = ''; return; }
        let integerPart = parts[0];
        let decimalPart = parts.length > 1 ? '.' + parts[1].substring(0, 2) : '';
        integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        input.value = integerPart + decimalPart;
    }

    /**
     * Parses a formatted currency string back to a float
     */
    parseCurrencyValue(value) {
        if (typeof value !== 'string') return parseFloat(value) || 0;
        return parseFloat(value.replace(/,/g, '')) || 0;
    }
}
