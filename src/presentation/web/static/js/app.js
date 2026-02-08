/**
 * SGUBM-V1 - Main Application Module
 * Modular JavaScript Architecture
 */

import { DashboardModule } from './modules/dashboard.js';
import { RoutersModule } from './modules/routers.js';
import { ClientsModule } from './modules/clients.js';
import { PaymentsModule } from './modules/payments.js';
import { PlansManagerModule } from './modules/plans_manager.js';
import { NavigationModule } from './modules/navigation.js';
import { ApiService } from './services/api.service.js';
import { EventBus } from './services/event-bus.service.js';
import { ViewManager } from './services/view-manager.service.js';
import toast from './components/toast.js';
import clientModal from './components/client-modal.js';

class App {
    constructor() {
        this.eventBus = new EventBus();
        this.apiService = new ApiService();
        this.viewManager = new ViewManager();
        this.modules = {};
        this.socket = null;

        this.init();
    }

    init() {
        console.log('🚀 SGUBM-V1 Starting...');

        // Inicializar WebSockets
        this.initSocket();

        // Inicializar módulos con ViewManager compartido
        this.modules.navigation = new NavigationModule(this.eventBus, this.viewManager);
        this.modules.dashboard = new DashboardModule(this.apiService, this.eventBus, this.viewManager);
        this.modules.routers = new RoutersModule(this.apiService, this.eventBus, this.viewManager);
        this.modules.clients = new ClientsModule(this.apiService, this.eventBus, this.viewManager);
        this.modules.payments = new PaymentsModule(this.apiService, this.eventBus, this.viewManager);
        this.modules.plans = new PlansManagerModule(this.apiService, this.eventBus, this.viewManager);

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

    initSocket() {
        console.log('🔌 WebSocket: Initializing connection...');
        try {
            // Conectar al mismo host/puerto automáticamente
            this.socket = io({
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionAttempts: 10,
                reconnectionDelay: 2000
            });

            this.socket.on('connect', () => {
                console.log('%c✅ WebSocket Connected!', 'color: #10b981; font-weight: bold;');
                this.eventBus.publish('socket_connected', { id: this.socket.id });
            });

            this.socket.on('disconnect', (reason) => {
                console.warn('❌ WebSocket Disconnected:', reason);
            });

            this.socket.on('connect_error', (err) => {
                console.error('❌ WebSocket Connection Error:', err.message);
            });

            // Logger global para debug (Ver todos los eventos que llegan)
            this.socket.onAny((eventName, ...args) => {
                console.log(`🔌 [SocketIO] Event: ${eventName}`, args);
            });

        } catch (e) {
            console.error('❌ WebSocket Critical Failure:', e);
        }
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

    showLoading(show) {
        let loader = document.getElementById('global-loader');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'global-loader';
            loader.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.7); backdrop-filter: blur(5px);
                z-index: 99999; display: flex; align-items: center; justify-content: center;
                flex-direction: column; opacity: 0; transition: opacity 0.3s;
                pointer-events: none;
            `;
            loader.innerHTML = `
                <div class="loader-spinner" style="
                    width: 50px; height: 50px; border: 4px solid rgba(255,255,255,0.1);
                    border-top: 4px solid #00D4FF; border-radius: 50%;
                    animation: spin 1s linear infinite;"></div>
                <p style="color: white; margin-top: 15px; font-weight: 500;">Procesando...</p>
                <style>@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }</style>
            `;
            document.body.appendChild(loader);
        }

        if (show) {
            loader.style.pointerEvents = 'all';
            loader.style.opacity = '1';
        } else {
            loader.style.opacity = '0';
            loader.style.pointerEvents = 'none';
        }
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
