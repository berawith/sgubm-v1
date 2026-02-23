/**
 * Client Modal Adapter
 * Wrapper para integrar el Client Modal legacy con el nuevo ModalManager
 */

import { default as ClientModalLegacy } from './client-modal.js';

export class ClientModalAdapter {
    constructor(apiService, eventBus) {
        this.legacy = ClientModalLegacy;
        this.apiService = apiService;
        this.eventBus = eventBus;
        this.modalId = 'client-modal';
        this.isRendered = true; // El modal legacy ya se renderiza en su constructor
    }

    /**
     * Abre el modal (compatible con ModalManager)
     * @param {object} data - { client: {...} } para editar, {} para crear
     */
    async open(data = {}) {
        if (data.client) {
            // Modo editar
            this.legacy.showEdit(data.client);
        } else if (data.clientId) {
            // Cargar cliente por ID y editar
            try {
                const client = await this.apiService.get(`/api/clients/${data.clientId}`);
                this.legacy.showEdit(client);
            } catch (error) {
                console.error('Error loading client:', error);
            }
        } else {
            // Modo crear
            this.legacy.showCreate();
        }
    }

    /**
     * Cierra el modal (compatible con ModalManager)
     */
    close() {
        this.legacy.close();
    }

    /**
     * No-op render (el modal legacy ya está renderizado)
     */
    async render() {
        // El client-modal.js se renderiza automáticamente en su constructor
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
