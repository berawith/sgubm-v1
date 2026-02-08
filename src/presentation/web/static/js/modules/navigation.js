/**
 * Navigation Module
 * Responsabilidad: Gestionar routing y estado visual del sidebar
 * NO manipula vistas directamente (delegado a ViewManager)
 */

export class NavigationModule {
    constructor(eventBus, viewManager) {
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.init();
    }

    init() {
        console.log('🧭 Navigation Module initialized');
        this.attachEvents();
    }

    attachEvents() {
        // Escuchar clicks en nav items principales
        document.querySelectorAll('.nav-item:not(.has-submenu)').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const view = item.dataset.view;
                if (view) {
                    this.navigate(view);
                    // Cerrar sidebar en movil tras navegar
                    this.closeSidebar();
                }
            });
        });

        // Manejar submenu toggle (Finanzas)
        const navFinanzas = document.getElementById('nav-finanzas');
        const submenu = document.getElementById('finanzas-submenu');

        if (navFinanzas && submenu) {
            navFinanzas.addEventListener('click', (e) => {
                e.preventDefault();
                navFinanzas.classList.toggle('expanded');
                submenu.classList.toggle('expanded');
            });
        }

        // Escuchar clicks en submenu items
        document.querySelectorAll('.submenu-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const view = item.dataset.view;
                if (view) {
                    this.navigateToSubView(view);
                    // Cerrar sidebar en movil tras navegar
                    this.closeSidebar();
                }
            });
        });

        // Toggle Sidebar en móvil
        const toggleBtn = document.getElementById('mobile-menu-toggle');
        const sidebar = document.querySelector('.sidebar');

        if (toggleBtn && sidebar) {
            toggleBtn.addEventListener('click', () => {
                sidebar.classList.toggle('active');
                this.updateOverlay();
            });
        }
    }

    updateOverlay() {
        const sidebar = document.querySelector('.sidebar');
        let overlay = document.querySelector('.sidebar-overlay');

        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'sidebar-overlay';
            document.body.appendChild(overlay);
            overlay.addEventListener('click', () => this.closeSidebar());
        }

        if (sidebar && sidebar.classList.contains('active')) {
            overlay.style.display = 'block';
        } else {
            overlay.style.display = 'none';
        }
    }

    closeSidebar() {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.remove('active');
            this.updateOverlay();
        }
    }

    navigate(view, params = {}) {
        console.log(`🧭 Navigating to: ${view}`);

        // Actualizar UI del sidebar
        document.querySelectorAll('.nav-item').forEach(item => {
            if (item.dataset.view === view) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        // Colapsar submenú de Finanzas
        this.collapseFinanzasSubmenu();

        // Limpiar estado de submenu items
        document.querySelectorAll('.submenu-item').forEach(item => {
            item.classList.remove('active');
        });

        // Publicar evento de navegación (cada módulo manejará su visualización)
        this.eventBus.publish('navigate', { view, ...params });

        // Actualizar URL sin recargar
        const url = view === 'dashboard' ? '/' : `/${view}`;
        window.history.pushState({ view, params }, '', url);

        // Actualizar título de la página
        document.title = `SGUBM - ${view.charAt(0).toUpperCase() + view.slice(1)}`;
    }

    /**
     * Colapsa el submenú de Finanzas (helper method)
     */
    collapseFinanzasSubmenu() {
        const navFinanzas = document.getElementById('nav-finanzas');
        const submenu = document.getElementById('finanzas-submenu');
        if (navFinanzas && submenu) {
            navFinanzas.classList.remove('expanded');
            submenu.classList.remove('expanded');
        }
    }

    navigateToSubView(subView, params = {}) {
        console.log(`🧭 Navigating to sub-view: ${subView}`);

        // Asegurar que el menú padre esté expandido
        const navFinanzas = document.getElementById('nav-finanzas');
        const submenu = document.getElementById('finanzas-submenu');
        if (navFinanzas && submenu) {
            navFinanzas.classList.add('expanded', 'active');
            submenu.classList.add('expanded');
        }

        // Remover active de items principales
        document.querySelectorAll('.nav-item:not(.has-submenu)').forEach(item => {
            item.classList.remove('active');
        });

        // Actualizar UI del submenu
        document.querySelectorAll('.submenu-item').forEach(item => {
            if (item.dataset.view === subView) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        // DELEGAR visualización a ViewManager
        this.viewManager.showSubView(subView);

        // Cargar datos del módulo correspondiente
        const moduleMap = {
            'payments-list': 'payments',
            'invoices': 'payments',
            'reports': 'payments',
            'promises': 'payments',
            'batch-payments': 'payments',
            'automation': 'payments',
            'trash': 'payments'
        };

        const loadMethodMap = {
            'payments-list': 'loadPayments',
            'invoices': 'loadInvoices',
            'reports': 'loadStatistics',
            'promises': 'loadPromises',
            'batch-payments': 'loadBatchClients',
            'automation': 'loadRouters',
            'trash': 'loadDeletedPayments'
        };

        const parentModule = moduleMap[subView];
        if (window.app && window.app.modules[parentModule]) {
            const loadMethod = loadMethodMap[subView];
            if (loadMethod && typeof window.app.modules[parentModule][loadMethod] === 'function') {
                window.app.modules[parentModule][loadMethod]();
            }
        }

        // Actualizar URL sin recargar
        const url = `/finanzas/${subView}`;
        window.history.pushState({ view: subView, isSubView: true, params }, '', url);

        // Actualizar título de la página
        const titles = {
            'payments-list': 'Pagos',
            'invoices': 'Facturas',
            'reports': 'Reportes',
            'promises': 'Promesas',
            'batch-payments': 'Gestión Masiva',
            'automation': 'Automatización',
            'trash': 'Papelera'
        };
        document.title = `SGUBM - ${titles[subView] || subView}`;
    }
}
