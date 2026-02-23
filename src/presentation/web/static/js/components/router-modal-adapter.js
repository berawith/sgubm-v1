/**
 * Router Modal Adapter
 * Wrapper para integrar el Router Modal legacy (inline en modals.html) con el nuevo ModalManager
 */

export class RouterModalAdapter {
    constructor(apiService, eventBus, routersModule) {
        this.apiService = apiService;
        this.eventBus = eventBus;
        this.routersModule = routersModule; // Referencia al módulo que tiene la lógica
        this.modalId = 'router-form-modal';
        this.isRendered = true; // El modal ya está en modals.html
    }

    /**
     * Abre el modal (compatible con ModalManager)
     * @param {object} data - { router: {...} } para editar, {} para crear
     */
    async open(data = {}) {
        if (data.router) {
            // Modo editar
            this.routersModule.showEditRouter(data.router);
        } else if (data.routerId) {
            // Cargar router por ID y editar
            try {
                const router = await this.apiService.get(`/api/routers/${data.routerId}`);
                this.routersModule.showEditRouter(router);
            } catch (error) {
                console.error('Error loading router:', error);
            }
        } else {
            // Modo crear
            this.routersModule.showNewRouterModal();
        }
    }

    /**
     * Cierra el modal (compatible con ModalManager)
     */
    close() {
        const modal = document.getElementById(this.modalId);
        if (modal) {
            modal.classList.remove('active');
            console.log(`🔌 [LegacyAdapter] Closed modal: ${this.modalId}`);
        }
    }

    /**
     * No-op render (el modal ya está en el HTML)
     */
    async render() {
        // El modal router-form-modal ya está renderizado en modals.html
        // No se necesita hacer nada aquí
    }

    /**
     * Emite eventos para compatibilidad con sistema de eventos
     */
    emit(eventName, data) {
        const event = new CustomEvent(`modal:${this.modalId}:${eventName}`, {
            detail: data,
            bubbles: true
        });
        document.dispatchEvent(event);
    }
}
