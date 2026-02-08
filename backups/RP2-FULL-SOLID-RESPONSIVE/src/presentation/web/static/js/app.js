/**
 * SGUBM-V1 - Main Application Module
 * Modular JavaScript Architecture
 */

import { DashboardModule } from './modules/dashboard.js';
import { RoutersModule } from './modules/routers.js';
import { ClientsModule } from './modules/clients.js';
import { PaymentsModule } from './modules/payments.js';
import { NavigationModule } from './modules/navigation.js';
import { ApiService } from './services/api.service.js';
import { EventBus } from './services/event-bus.service.js';
import toast from './components/toast.js';
import clientModal from './components/client-modal.js';

class App {
    constructor() {
        this.eventBus = new EventBus();
        this.apiService = new ApiService();
        this.modules = {};

        this.init();
    }

    init() {
        console.log('🚀 SGUBM-V1 Starting...');

        // Inicializar módulos
        this.modules.navigation = new NavigationModule(this.eventBus);
        this.modules.dashboard = new DashboardModule(this.apiService, this.eventBus);
        this.modules.routers = new RoutersModule(this.apiService, this.eventBus);
        this.modules.clients = new ClientsModule(this.apiService, this.eventBus);
        this.modules.payments = new PaymentsModule(this.apiService, this.eventBus);

        // Suscribir a eventos globales
        this.subscribeToEvents();

        // Cargar módulo inicial basado en URL
        const path = window.location.pathname.substring(1); // eliminar primer slash
        const initialView = path || 'dashboard';

        if (this.modules[initialView]) {
            // Usar navigate para actualizar UI y cargar módulo
            // Pasamos history: false para no hacer pushState de nuevo si ya estamos ahí
            this.modules.navigation.navigate(initialView);
        } else {
            this.modules.dashboard.load();
        }

        console.log('✅ SGUBM-V1 Ready');
    }

    subscribeToEvents() {
        // Escuchar cambios de navegación
        this.eventBus.subscribe('navigate', (data) => {
            const moduleName = data.view;
            if (this.modules[moduleName]) {
                this.modules[moduleName].load();
            }
        });

        // Escuchar errores globales
        this.eventBus.subscribe('error', (error) => {
            console.error('Application error:', error);
            toast.error(error.message || 'Error en la aplicación');
        });
    }

    showNotification(title, message, type = 'info') {
        // Usar el sistema de notificaciones toast
        const fullMessage = title ? `${title}: ${message}` : message;
        toast[type](fullMessage);
    }
}

// Inicializar aplicación cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();

    // Hacer componentes accesibles globalmente
    window.toast = toast;
    window.clientModal = clientModal;

    console.log('✅ SGUBM-V1 Ready - Premium UI Loaded');
});
