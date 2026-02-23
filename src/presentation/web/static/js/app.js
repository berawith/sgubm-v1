/**
 * SGUBM-V1 - Main Application Module
 * Modular JavaScript Architecture
 */

console.log('🔴 App Module script evaluating...');
import '../css/core.css';
import '../css/compact-modals.css';
import { DashboardModule } from './modules/dashboard.js';
import { RoutersModule } from './modules/routers.js';
import { ClientsModule } from './modules/clients.js';
import { PaymentsModule } from './modules/payments.js';
import { PlansManagerModule } from './modules/plans_manager.js';
import { WhatsAppModule } from './modules/whatsapp.js';
import { NavigationModule } from './modules/navigation.js';
import { MetricsModule } from './modules/metrics.js';
import { ApiService } from './services/api.service.js';
import { FinanceStatsService } from './services/finance-stats.service.js';
import { EventBus } from './services/event-bus.service.js';
import { ViewManager } from './services/view-manager.service.js';
import { ModalManager } from './components/shared/modal-manager.service.js';
import { PaymentModal } from './components/payment-modal/payment-modal.component.js';
import { PlanModal } from './components/plan-modal/plan-modal.component.js';
import { PromiseModal } from './components/promise-modal/promise-modal.component.js';
import { HistoryModal } from './components/history-modal/history-modal.component.js';
import { MonthDetailModal } from './components/month-detail-modal/month-detail-modal.component.js';
import { PaymentDetailModal } from './components/payment-detail-modal/payment-detail-modal.component.js';
import toast from './components/toast.js';
import clientModal from './components/client-modal.js';
import { ClientModalAdapter } from './components/client-modal-adapter.js';
import { RouterModalAdapter } from './components/router-modal-adapter.js';

class Logger {
    constructor() {
        this.enabled = true;
        this.levels = {
            DEBUG: 0,
            INFO: 1,
            WARN: 2,
            ERROR: 3
        };
        this.currentLevel = this.levels.INFO;
    }

    log(level, ...args) {
        if (!this.enabled || level < this.currentLevel) return;

        const timestamp = new Date().toLocaleTimeString();
        const prefix = `[SGUBM ${timestamp}]`;

        switch (level) {
            case this.levels.DEBUG: console.log(`%c${prefix}`, 'color: #94a3b8', ...args); break;
            case this.levels.INFO: console.log(`%c${prefix}`, 'color: #0ea5e9', ...args); break;
            case this.levels.WARN: console.warn(prefix, ...args); break;
            case this.levels.ERROR: console.error(prefix, ...args); break;
        }
    }

    debug(...args) { this.log(this.levels.DEBUG, ...args); }
    info(...args) { this.log(this.levels.INFO, ...args); }
    warn(...args) { this.log(this.levels.WARN, ...args); }
    error(...args) { this.log(this.levels.ERROR, ...args); }

    toggle(state) { this.enabled = state; }
}

class App {
    constructor() {
        this.eventBus = new EventBus();
        this.apiService = new ApiService();
        this.viewManager = new ViewManager();
        this.modalManager = new ModalManager();
        this.logger = new Logger();
        this.financeStats = new FinanceStatsService(this.apiService, this.logger);
        this.modules = {};
        this.socket = null;
        this.loaderCount = 0;

        this.init();
    }

    init() {
        this.logger.info('🚀 SGUBM-V1 Starting...');
        window.app = this; // Disponible globalmente inmediatamente

        // Inicializar WebSockets
        this.initSocket();

        // Inicializar módulos con ViewManager y ModalManager compartidos
        this.modules.navigation = new NavigationModule(this.eventBus, this.viewManager);
        this.modules.dashboard = new DashboardModule(this.apiService, this.eventBus, this.viewManager, this.modalManager);
        this.modules.routers = new RoutersModule(this.apiService, this.eventBus, this.viewManager, this.modalManager);
        this.modules.clients = new ClientsModule(this.apiService, this.eventBus, this.viewManager, this.modalManager);
        this.modules.payments = new PaymentsModule(this.apiService, this.eventBus, this.viewManager, this.modalManager, this.financeStats);
        this.modules.plans = new PlansManagerModule(this.apiService, this.eventBus, this.viewManager, this.modalManager);
        this.modules.whatsapp = new WhatsAppModule(this.apiService, this.eventBus, this.viewManager, this.modalManager);
        this.modules.metrics = new MetricsModule(this.apiService, this.eventBus, this.viewManager);

        // Inicializar componentes modales (DESPUÉS de los módulos para que los adapters tengan referencias válidas)
        this.initModals();

        // Suscribir a eventos globales
        this.subscribeToEvents();

        // Cargar módulo inicial basado en URL
        const path = window.location.pathname.substring(1); // eliminar primer slash

        // 1. Verificar si es una sub-ruta (ej: payments/invoices)
        if (path.includes('/')) {
            const parts = path.split('/');
            if (parts.length >= 2) {
                const subView = parts[1];
                // Lista blanca de sub-vistas soportadas por navegación
                const knownSubViews = [
                    'clients', 'clients-import',
                    'payments-list', 'invoices', 'reports', 'promises', 'automation', 'sync', 'trash', 'expenses'
                ];

                if (knownSubViews.includes(subView)) {
                    // Navegación profunda a la sub-vista
                    this.modules.navigation.navigateToSubView(subView);
                    return;
                }
            }
        }

        // 2. Ruta estándar (ej: dashboard, routers)
        const initialView = path || 'dashboard';

        if (this.modules[initialView]) {
            // Usar navigate para actualizar UI y cargar módulo
            this.modules.navigation.navigate(initialView);
        } else {
            this.modules.dashboard.load();
        }

        this.logger.info('✅ SGUBM-V1 Ready');
    }

    initModals() {
        this.logger.info('📦 Initializing modal components...');

        // Payment Modal
        const paymentModal = new PaymentModal(this.apiService, this.eventBus);
        this.modalManager.register('payment', paymentModal);

        // Client Modal (legacy adapter)
        const clientModal = new ClientModalAdapter(this.apiService, this.eventBus);
        this.modalManager.register('client', clientModal);

        // Router Modal (legacy adapter)
        const routerModal = new RouterModalAdapter(this.apiService, this.eventBus, this.modules.routers);
        this.modalManager.register('router', routerModal);

        // Plan Modal
        const planModal = new PlanModal(this.apiService, this.eventBus);
        this.modalManager.register('plan', planModal);

        // Promise Modal
        const promiseModal = new PromiseModal(this.apiService, this.eventBus);
        this.modalManager.register('promise', promiseModal);

        // History Modal
        const historyModal = new HistoryModal(this.apiService, this.eventBus);
        this.modalManager.register('history', historyModal);

        // Month Detail Modal
        const monthDetailModal = new MonthDetailModal(this.apiService, this.eventBus);
        this.modalManager.register('month-detail', monthDetailModal);

        // Payment Detail Modal
        const paymentDetailModal = new PaymentDetailModal(this.apiService, this.eventBus);
        this.modalManager.register('payment-detail', paymentDetailModal);

        // Report Modal (Legacy HTML based)
        this.modalManager.register('report', {
            open: () => {
                const modal = document.getElementById('modal-report-config');
                if (modal) modal.classList.add('active');
            },
            close: () => {
                const modal = document.getElementById('modal-report-config');
                if (modal) modal.classList.remove('active');
            }
        });

        // Delete Client Modal (Legacy HTML based)
        this.modalManager.register('delete-client', {
            open: () => {
                const modal = document.getElementById('delete-client-modal');
                if (modal) modal.classList.add('active');
            },
            close: () => {
                const modal = document.getElementById('delete-client-modal');
                if (modal) modal.classList.remove('active');
            }
        });

        // Plan Clients Modal (Legacy HTML based)
        this.modalManager.register('plan-clients', {
            open: () => {
                const modal = document.getElementById('planClientsModal');
                if (modal) modal.classList.add('active');
            },
            close: () => {
                const modal = document.getElementById('planClientsModal');
                if (modal) modal.classList.remove('active');
            }
        });

        // Dashboard Modals
        this.modalManager.register('router-details', {
            open: () => document.getElementById('router-details-modal')?.classList.add('active'),
            close: () => document.getElementById('router-details-modal')?.classList.remove('active')
        });
        this.modalManager.register('router-graph', {
            open: () => document.getElementById('router-graph-modal')?.classList.add('active'),
            close: () => document.getElementById('router-graph-modal')?.classList.remove('active')
        });
        this.modalManager.register('router-error', {
            open: () => document.getElementById('router-error-modal')?.classList.add('active'),
            close: () => document.getElementById('router-error-modal')?.classList.remove('active')
        });

        // Import Clients Modal (Smart Sync)
        this.modalManager.register('import-clients-modal', {
            open: () => {
                const modal = document.getElementById('import-clients-modal');
                if (modal) modal.classList.add('active');
            },
            close: () => {
                const modal = document.getElementById('import-clients-modal');
                if (modal) modal.classList.remove('active');
            }
        });

        // WhatsApp Config Modal
        this.modalManager.register('whatsapp-config', {
            open: () => {
                const modal = document.getElementById('whatsapp-config-modal');
                if (modal) {
                    modal.classList.add('active');
                    this.modules.whatsapp.loadConfigData();
                }
            },
            close: () => {
                this.modules.whatsapp.closeConfig();
            }
        });

        // Stability History Modal (Managed via ModalManager)
        this.modalManager.register('stability-history', {
            open: () => {
                const modal = document.getElementById('stability-history-modal');
                if (modal) modal.classList.add('active');
            },
            close: () => {
                const modal = document.getElementById('stability-history-modal');
                if (modal) modal.classList.remove('active');
            }
        });

        this.logger.info('✅ Modal components initialized');
    }

    initSocket() {
        this.logger.info('🔌 WebSocket: Initializing connection...');
        try {
            // Conectar al mismo host/puerto automáticamente
            this.socket = io({
                transports: ['polling', 'websocket'],
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
            // this.socket.onAny((eventName, ...args) => {
            //     console.log(`🔌 [SocketIO] Event: ${eventName}`, args);
            // });

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

            // Caso especial para vistas de componentes (Sync Dashboard)
            if (moduleName === 'sync') {
                if (window.syncDashboard) {
                    window.syncDashboard.init();
                }
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
            this.loaderCount++;
            loader.style.pointerEvents = 'all';
            loader.style.opacity = '1';

            // Safety timeout: auto-hide after 10 seconds to prevent permanent lockup
            if (this.loaderTimeout) clearTimeout(this.loaderTimeout);
            this.loaderTimeout = setTimeout(() => {
                if (this.loaderCount > 0) {
                    console.warn('⚠️ Global loader safety timeout reached. Resetting...');
                    this.loaderCount = 0;
                    this.showLoading(false);
                }
            }, 10000);
        } else {
            this.loaderCount--;
            if (this.loaderCount <= 0) {
                this.loaderCount = 0; // Guard
                if (this.loaderTimeout) clearTimeout(this.loaderTimeout);
                loader.style.opacity = '0';
                loader.style.pointerEvents = 'none';
            }
        }
    }
}

// Función de inicialización robusta
const initApp = () => {
    if (window.app) return;

    console.log('🚀 Initializing App Instance...');
    window.app = new App();

    // Hacer componentes accesibles globalmente
    window.toast = toast;
    window.showToast = (message, type) => toast[type](message);
    window.clientModal = clientModal;

    console.log('✅ SGUBM-V1 Ready - Premium UI Loaded');
};

// Punto de entrada seguro
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
