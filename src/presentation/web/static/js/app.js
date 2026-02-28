/**
 * SGUBM-V1 - Main Application Module
 * Modular JavaScript Architecture
 */


import '../css/core.css';
import '../css/compact-modals.css';
import { DashboardModule } from './modules/dashboard.js';
import { RoutersModule } from './modules/routers.js';
import { ClientsModule } from './modules/clients.js';
import { ClientsAlertsModule } from './modules/clients-alerts.js';
import { ClientsSupportModule } from './modules/clients-support.js';
import { PaymentsModule } from './modules/payments.js';
import { PlansManagerModule } from './modules/plans_manager.js';
import { WhatsAppModule } from './modules/whatsapp.js';
import { NavigationModule } from './modules/navigation.js';
import { MetricsModule } from './modules/metrics.js';
import { ApiService } from './services/api.service.js';
import { FinanceStatsService } from './services/finance-stats.service.js';
import { EventBus } from './services/event-bus.service.js';
import { ViewManager } from './services/view-manager.service.js';
import { AuthService } from './services/auth.service.js';
import { AuthModule } from './modules/auth.module.js';
import { UsersModule } from './modules/users.js';
import { RecicladorModule } from './modules/reciclador.js';
import CollectorFinanceModule from './modules/collector_finance.js';
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
        this.authService = new AuthService(this.apiService);
        this.financeStats = new FinanceStatsService(this.apiService, this.logger);
        this.modules = {};
        this.socket = null;
        this.loaderCount = 0;

        // No llamar a init() en el constructor si es async
        // La inicialización se manejará en initApp
    }

    /**
     * Helper centralizado para verificar permisos RBAC en el lado del cliente (UI).
     * Evita realizar llamadas API que resultarán en 403 y ensucian la consola.
     * @param {string} module El nombre del módulo/permiso (ej: 'sync', 'clients:list')
     * @param {string} action La acción pedida (ej: 'can_view', 'can_edit')
     * @returns {boolean} True si tiene permiso, False si no (y muestra un Toast)
     */
    checkPermission(module, action = 'can_view') {
        const user = this.authService.getUser();
        if (!user) return false;

        // Admins siempre tienen permiso
        if (user.role === 'admin' || user.role === 'administradora') return true;

        const perms = window.RBAC_PERMS || {};
        const modPerms = perms[module];

        if (!modPerms || !modPerms[action]) {
            if (typeof toast !== 'undefined') {
                toast.error('Este procedimiento no se puede procesar porque no posee los privilegios necesarios.');
            }
            return false;
        }

        return true;
    }

    async init() {
        this.logger.info('🚀 SGUBM-V1 Starting...');
        window.app = this; // Disponible globalmente inmediatamente

        // Inicializar Autenticación PRIMERO
        this.modules.auth = new AuthModule(this.authService);

        // Validar sesión contra el servidor ANTES de continuar
        if (this.authService.token) {
            this.logger.info('🔑 Validating session...');
            await this.authService.refreshUserData();
        }

        // Si después de la validación no está autenticado, detener aquí y mostrar login
        if (!this.authService.isAuthenticated()) {
            this.logger.warn('🔒 User not authenticated. Waiting for login...');
            this.modules.auth.showLogin(); // Asegurar que showLogin se ejecute explícitamente
            return;
        }

        // Sesión validada correctamente: revelar la app
        this.modules.auth.hideLogin();
        this.applyTenantBranding(); // Aplicar branding del tenant
        await this.modules.auth.applyRoleRestrictions();
        this.modules.auth.updateUserUI();

        // Inicializar WebSockets
        this.initSocket();

        // Inicializar módulos con ViewManager y ModalManager compartidos
        this.modules.navigation = new NavigationModule(this.eventBus, this.viewManager);
        this.modules.dashboard = new DashboardModule(this.apiService, this.eventBus, this.viewManager, this.modalManager);
        this.modules.routers = new RoutersModule(this.apiService, this.eventBus, this.viewManager, this.modalManager);
        this.modules.clients = new ClientsModule(this.apiService, this.eventBus, this.viewManager, this.modalManager);
        this.modules.clients_alerts = new ClientsAlertsModule(this.apiService, this.eventBus, this.viewManager, this.modalManager);
        this.modules.clients_support = new ClientsSupportModule(this.apiService, this.eventBus, this.viewManager, this.modalManager);
        this.modules.payments = new PaymentsModule(this.apiService, this.eventBus, this.viewManager, this.modalManager, this.financeStats);
        this.modules.plans = new PlansManagerModule(this.apiService, this.eventBus, this.viewManager, this.modalManager);
        this.modules.whatsapp = new WhatsAppModule(this.apiService, this.eventBus, this.viewManager, this.modalManager);
        this.modules.metrics = new MetricsModule(this.apiService, this.eventBus, this.viewManager);
        this.modules.users = new UsersModule(this.apiService, this.eventBus, this.viewManager);
        this.modules.reciclador = new RecicladorModule(this.apiService, this.eventBus, this.viewManager);

        // Collector Finance módule — only initialized when role is collector
        const currentUser = this.authService.currentUser;
        if (currentUser && currentUser.role === 'collector') {
            this.modules.collectorFinance = new CollectorFinanceModule(this.apiService);
        }

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
                const subViewRaw = parts[1];
                // Normalizar guiones bajos a guiones para compatibilidad
                const subView = subViewRaw.replace(/_/g, '-');

                // Lista blanca de sub-vistas soportadas por navegación
                const knownSubViews = [
                    'clients', 'clients-import', 'clients-trash', 'clients-alerts', 'clients-support',
                    'finance-overview', 'payments-list', 'invoices', 'reports', 'promises', 'automation', 'sync', 'trash', 'expenses', 'system',
                    'collector-finance', 'system-reciclador'
                ];

                if (knownSubViews.includes(subView)) {
                    // Navegación profunda a la sub-vista
                    console.log(`🚀 Initial Deep Link detected: ${subView} (raw: ${subViewRaw})`);
                    this.modules.navigation.navigateToSubView(subView);
                    return;
                }
            }
        }

        // 2. Ruta estándar (ej: dashboard, routers)
        let initialView = path || 'dashboard';

        if (initialView === 'collector-finance') {
            this.modules.navigation.navigateToSubView('collector-finance');
        } else if (this.modules[initialView]) {
            // Usar navigate para actualizar UI y cargar módulo
            this.modules.navigation.navigate(initialView);
        } else {
            this.modules.dashboard.load();
        }

        // Registrar modales de sistema
        this.modalManager.register('user-form', {
            open: () => { /* Implementado vía Swal en UsersModule */ },
            close: () => { /* Implementado vía Swal en UsersModule */ }
        });

        this.logger.info('✅ SGUBM-V1 Ready');
    }

    initModals() {
        this.logger.info('📦 Initializing modal components...');

        // Payment Modal
        const paymentModal = new PaymentModal(this.apiService, this.eventBus);
        paymentModal._initPromise = paymentModal.init();
        this.modalManager.register('payment', paymentModal);

        // Client Modal (legacy adapter)
        const clientModalAdapter = new ClientModalAdapter(this.apiService, this.eventBus);
        this.modalManager.register('client', clientModalAdapter);

        // Inicializar el modal singleton de clientes (legacy)
        if (window.clientModal && typeof window.clientModal.init === 'function') {
            window.clientModal.init();
        }

        // Router Modal (legacy adapter)
        const routerModal = new RouterModalAdapter(this.apiService, this.eventBus, this.modules.routers);
        this.modalManager.register('router', routerModal);

        // Plan Modal
        const planModal = new PlanModal(this.apiService, this.eventBus);
        planModal._initPromise = planModal.init();
        this.modalManager.register('plan', planModal);

        // Promise Modal
        const promiseModal = new PromiseModal(this.apiService, this.eventBus);
        promiseModal._initPromise = promiseModal.init();
        this.modalManager.register('promise', promiseModal);

        // History Modal
        const historyModal = new HistoryModal(this.apiService, this.eventBus);
        historyModal._initPromise = historyModal.init();
        this.modalManager.register('history', historyModal);

        // Month Detail Modal
        const monthDetailModal = new MonthDetailModal(this.apiService, this.eventBus);
        monthDetailModal._initPromise = monthDetailModal.init();
        this.modalManager.register('month-detail', monthDetailModal);

        // Payment Detail Modal
        const paymentDetailModal = new PaymentDetailModal(this.apiService, this.eventBus);
        paymentDetailModal._initPromise = paymentDetailModal.init();
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

        // Client Status Details Modal (Dashboard)
        this.modalManager.register('client-status-details', {
            open: (data) => {
                const modal = document.getElementById('modal-client-status-details');
                if (modal) {
                    console.log('🔍 [App] Found status modal element, activating...');
                    modal.classList.add('active');
                    modal.style.display = 'flex'; // Forzar visibilidad
                } else {
                    console.error('❌ [App] Status modal element NOT FOUND (modal-client-status-details)');
                }
                return this.modules.dashboard.showClientStatusDetails(data.routerId, data.status);
            },
            close: () => {
                const modal = document.getElementById('modal-client-status-details');
                if (modal) {
                    modal.classList.remove('active');
                    modal.style.display = 'none';
                }
                this.modules.dashboard.stopClientDetailsMonitoring();
            }
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

        // Support Ticket Modal
        this.modalManager.register('support', {
            open: (data) => {
                const modal = document.getElementById('new-ticket-modal');
                if (modal) {
                    modal.style.display = 'flex';
                    setTimeout(() => modal.classList.add('active'), 10);
                }
            },
            close: () => {
                const modal = document.getElementById('new-ticket-modal');
                if (modal) {
                    modal.classList.remove('active');
                    setTimeout(() => modal.style.display = 'none', 400);
                }
            }
        });

        // Resolution Closure Modal
        this.modalManager.register('resolve-ticket', {
            open: (data) => {
                const modal = document.getElementById('resolve-ticket-modal');
                if (modal) {
                    modal.style.display = 'flex';
                    setTimeout(() => modal.classList.add('active'), 10);
                }
            },
            close: () => {
                const modal = document.getElementById('resolve-ticket-modal');
                if (modal) {
                    modal.classList.remove('active');
                    setTimeout(() => modal.style.display = 'none', 400);
                }
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

                // UNIRSE AL ROOM DEL TENANT PARA REAL-TIME SYNC
                if (this.authService.tenant && this.authService.tenant.id) {
                    this.socket.emit('join_tenant', { tenant_id: this.authService.tenant.id });
                } else if (window.SGUBM_CONFIG && window.SGUBM_CONFIG.tenant_id) {
                    this.socket.emit('join_tenant', { tenant_id: window.SGUBM_CONFIG.tenant_id });
                }
            });

            this.socket.on('reconnect', (attempt) => {
                this.logger.info(`🔄 WebSocket Reconnected (Attempt ${attempt})`);
                // AUTO-RELOAD EN DESARROLLO (ASOMBRO PARA EL USUARIO)
                if (window.SGUBM_CONFIG && window.SGUBM_CONFIG.debug) {
                    this.logger.warn('🛠️ Dev Mode: Auto-reloading page after server restart...');
                    setTimeout(() => window.location.reload(), 500);
                }
            });

            // ESCUCHAR EVENTOS DE REFRESCO DE DATOS
            this.socket.on('data_refresh', (data) => {
                this.logger.info('🔔 Data refresh signal received:', data);
                // Notificar a toda la app mediante el EventBus local
                this.eventBus.publish('data_refresh', data);

                // Mostrar notificación visual opcional si es relevante
                if (data.event_type === 'client.created') {
                    this.showNotification('Nuevo Cliente', `${data.client_name} se ha unido al sistema.`, 'success');
                }
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
                this.modules[moduleName].load(data);
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

            // SMART LOADER: Only show after 200ms of waiting, to avoid flicker on fast requests
            if (!this._loaderShowTimeout) {
                this._loaderShowTimeout = setTimeout(() => {
                    if (this.loaderCount > 0) {
                        loader.style.pointerEvents = 'all';
                        loader.style.opacity = '1';
                        this._loaderStartTime = Date.now();
                    }
                    this._loaderShowTimeout = null;
                }, 200);
            }

            // SAFETY TIMEOUT: auto-hide after 10 seconds to prevent permanent lockup
            // Optimized: Don't reset the timeout if it's already pending, 
            // ensuring we eventually unlock even if bombarded with requests.
            if (!this.loaderTimeout) {
                this.loaderTimeout = setTimeout(() => {
                    if (this.loaderCount > 0) {
                        console.warn('🚨 Global loader safety timeout reached. Forced reset.');
                        this.loaderCount = 0;
                        this.showLoading(false);
                    }
                    this.loaderTimeout = null;
                }, 10000);
            }
        } else {
            this.loaderCount--;
            if (this.loaderCount <= 0) {
                this.loaderCount = 0; // Guard
                if (this.loaderTimeout) clearTimeout(this.loaderTimeout);

                if (this._loaderShowTimeout) {
                    clearTimeout(this._loaderShowTimeout);
                    this._loaderShowTimeout = null;
                }

                // Ensure a minimum display time (300ms) to avoid visual glitch if it appeared
                const now = Date.now();
                const elapsed = now - (this._loaderStartTime || 0);
                const minTime = 300;

                if (this._loaderStartTime && elapsed < minTime) {
                    setTimeout(() => {
                        loader.style.opacity = '0';
                        loader.style.pointerEvents = 'none';
                        this._loaderStartTime = null;
                    }, minTime - elapsed);
                } else {
                    loader.style.opacity = '0';
                    loader.style.pointerEvents = 'none';
                    this._loaderStartTime = null;
                }
            }
        }
    }

    /**
     * Alias for showLoading(false)
     */
    hideLoading() {
        this.showLoading(false);
    }

    /**
     * Aplica el branding personalizado del Tenant (Color, Logo, Nombre)
     */
    applyTenantBranding() {
        const tenant = this.authService.tenant;
        if (!tenant) return;

        this.logger.info(`🎨 Applying tenant branding: ${tenant.name}`);

        // 1. Aplicar Color de Marca mediante Variables CSS
        if (tenant.brand_color) {
            document.documentElement.style.setProperty('--primary', tenant.brand_color);
            // Generar una versión con opacidad para efectos glassmorphism
            document.documentElement.style.setProperty('--primary-rgb', this._hexToRgb(tenant.brand_color));
        }

        // 2. Actualizar Título de la Aplicación
        if (tenant.name) {
            document.title = `${tenant.name} - SGUBM Premium`;
            // Si hay un elemento de texto de logo en el header, lo actualizamos
            const logoText = document.querySelector('.logo-text');
            if (logoText) {
                logoText.textContent = tenant.name;
            }
        }

        // 3. Actualizar Logo si existe
        if (tenant.logo_path) {
            const logoImg = document.querySelector('.logo-img');
            if (logoImg) {
                logoImg.src = tenant.logo_path;
            }
        }
    }

    /**
     * Helper para convertir HEX a RGB (para variables CSS con opacidad)
     */
    _hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        if (!result) return '79, 70, 229'; // Default indigo

        return `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`;
    }
}

// Función de inicialización robusta
const initApp = async () => {
    if (window.app) return;

    console.log('🚀 Initializing App Instance...');
    const app = new App();
    await app.init();

    // Hacer componentes accesibles globalmente
    window.toast = toast;
    window.showToast = (message, type) => toast[type](message);
    window.clientModal = clientModal;

    // Register Service Worker for PWA
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/static/service-worker.js')
                .then(registration => {
                    console.log('✅ ServiceWorker registered with scope:', registration.scope);
                })
                .catch(error => {
                    console.error('❌ ServiceWorker registration failed:', error);
                });
        });
    }

    console.log('✅ SGUBM-V1 Ready - Premium UI Loaded');
};

// Punto de entrada seguro
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
