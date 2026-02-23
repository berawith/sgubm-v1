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
        const submenuFinanzas = document.getElementById('finanzas-submenu');

        if (navFinanzas && submenuFinanzas) {
            navFinanzas.addEventListener('click', (e) => {
                e.preventDefault();
                navFinanzas.classList.toggle('expanded');
                submenuFinanzas.classList.toggle('expanded');
                // Colapsar otros submenús si estuviera abierto
                this.collapseSubmenu('clientes');
            });
        }

        // Manejar submenu toggle (Clientes)
        const navClientes = document.getElementById('nav-clientes');
        const submenuClientes = document.getElementById('clientes-submenu');

        if (navClientes && submenuClientes) {
            navClientes.addEventListener('click', (e) => {
                e.preventDefault();
                navClientes.classList.toggle('expanded');
                submenuClientes.classList.toggle('expanded');
                // Colapsar otros submenús si estuviera abierto
                this.collapseSubmenu('finanzas');
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
        if (this._currentNavigatingView === view) return;
        this._currentNavigatingView = view;

        console.log(`🧭 Navigating to: ${view}`);

        try {
            // Actualizar URL sin recargar
            const url = view === 'dashboard' ? '/' : `/${view}`;
            window.history.pushState({ view, params }, '', url);

            // Actualizar UI del sidebar
            document.querySelectorAll('.nav-item').forEach(item => {
                if (item.dataset.view === view) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });

            // Colapsar submenús
            this.collapseSubmenu('finanzas');
            this.collapseSubmenu('clientes');

            // Limpiar estado de submenu items
            document.querySelectorAll('.submenu-item').forEach(item => {
                item.classList.remove('active');
            });

            // Publicar evento de navegación (cada módulo manejará su visualización)
            this.eventBus.publish('navigate', { view, ...params });

            // Actualizar título de la página
            document.title = `SGUBM - ${view.charAt(0).toUpperCase() + view.slice(1)}`;
        } finally {
            // Reset state to allow future navigations to same view if needed (e.g. refresh)
            setTimeout(() => { this._currentNavigatingView = null; }, 500);
        }
    }

    /**
     * Colapsa un submenú específico
     * @param {string} prefix - 'finanzas' o 'clientes'
     */
    collapseSubmenu(prefix) {
        const nav = document.getElementById(`nav-${prefix}`);
        const submenu = document.getElementById(`${prefix}-submenu`);
        if (nav && submenu) {
            nav.classList.remove('expanded');
            submenu.classList.remove('expanded');
        }
    }

    collapseFinanzasSubmenu() {
        this.collapseSubmenu('finanzas');
    }

    navigateToSubView(subViewRaw, params = {}) {
        // Normalizar a guiones siempre
        const subView = subViewRaw.replace(/_/g, '-');

        if (this._currentNavigatingSubView === subView) return;
        this._currentNavigatingSubView = subView;

        try {
            console.log(`🧭 Navigating to sub-view: ${subView} (original: ${subViewRaw})`);

            const parentMenuMap = {
                'clients': 'clientes',
                'clients-import': 'clientes',
                'clients-actions': 'clientes',
                'clients-trash': 'clientes',
                'finance-overview': 'finanzas',
                'payments-list': 'finanzas',
                'invoices': 'finanzas',
                'reports': 'finanzas',
                'promises': 'finanzas',
                'expenses': 'finanzas',


                'automation': 'finanzas',
                'sync': 'finanzas',
                'trash': 'finanzas'
            };

            const parentPrefix = parentMenuMap[subView];
            if (parentPrefix) {
                const navParent = document.getElementById(`nav-${parentPrefix}`);
                const submenuParent = document.getElementById(`${parentPrefix}-submenu`);
                if (navParent && submenuParent) {
                    navParent.classList.add('expanded', 'active');
                    submenuParent.classList.add('expanded');
                }

                // Colapsar el otro menú para mantener limpieza (opcional)
                const otherPrefix = parentPrefix === 'finanzas' ? 'clientes' : 'finanzas';
                this.collapseSubmenu(otherPrefix);
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

            // Cargar datos del módulo correspondiente
            const moduleMap = {
                'finance-overview': 'payments',
                'payments-list': 'payments',
                'invoices': 'payments',
                'reports': 'payments',
                'promises': 'payments',
                'expenses': 'payments',
                'automation': 'payments',
                'sync': 'payments',
                'trash': 'payments',
                'clients': 'clients',
                'clients-import': 'clients',
                'clients-actions': 'clients',
                'clients-trash': 'clients'
            };

            const loadMethodMap = {
                'finance-overview': 'loadStatistics',
                'payments-list': 'loadPayments',
                'invoices': 'loadInvoices',
                'reports': 'loadStatistics',
                'promises': 'loadPromises',
                'expenses': 'loadExpenses',
                'automation': 'loadRouters',
                'trash': 'loadDeletedPayments',
                'clients': 'load',
                'clients-import': 'loadClientsImport',
                'clients-actions': 'loadClientsActions',
                'clients-trash': 'loadTrash',
                'sync': 'initSync'
            };

            const parentModule = moduleMap[subView];
            const moduleInstance = window.app && window.app.modules[parentModule];

            // NEW: Delegate to module's internal router if supported (e.g. Payments tabs)
            if (moduleInstance && typeof moduleInstance.handleNavigation === 'function') {
                console.log(`✨ Delegating navigation to ${parentModule}.handleNavigation('${subView}')`);
                moduleInstance.handleNavigation(subView);
            } else {
                // Legacy/Default behavior
                this.viewManager.showSubView(subView);

                if (moduleInstance) {
                    const loadMethod = loadMethodMap[subView];
                    if (loadMethod && typeof moduleInstance[loadMethod] === 'function') {
                        moduleInstance[loadMethod]();
                    }
                }
            }

            // Actualizar URL sin recargar
            const parent = moduleMap[subView];
            const url = `/${parent}/${subView}`;
            window.history.pushState({ view: subView, isSubView: true, params }, '', url);

            // Actualizar título de la página
            const titles = {
                'finance-overview': 'Resumen Financiero',
                'payments-list': 'Pagos',
                'invoices': 'Facturas',
                'reports': 'Reportes',
                'promises': 'Promesas',
                'expenses': 'Gastos y Deducibles',

                'automation': 'Automatización',
                'sync': 'Sincronización',
                'trash': 'Papelera',
                'clients': 'Clientes',
                'clients-import': 'Importar Clientes',
                'clients-trash': 'Papelera de Clientes',
                'whatsapp': 'WhatsApp Agent'
            };
            document.title = `SGUBM - ${titles[subView] || subView}`;
        } finally {
            // Reset state to allow future navigations
            setTimeout(() => { this._currentNavigatingSubView = null; }, 500);
        }
    }
}
