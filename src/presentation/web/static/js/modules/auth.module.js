/**
 * Auth Module
 * Controla la interfaz de usuario del Login y la visualización por roles
 */

export class AuthModule {
    constructor(authService) {
        this.auth = authService;
        this.container = document.getElementById('login-container');
        this.form = document.getElementById('login-form');
        this.btnSubmit = document.getElementById('login-submit');
        this.togglePwd = document.getElementById('toggle-password');
        this.pwdInput = document.getElementById('login-password');

        this.init();
    }

    init() {
        if (!this.container || !this.form) return;

        // Listener de envío
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));

        // Toggle Password
        if (this.togglePwd && this.pwdInput) {
            this.togglePwd.addEventListener('click', () => {
                const type = this.pwdInput.type === 'password' ? 'text' : 'password';
                this.pwdInput.type = type;
            });
        }

        // Eventos globales de sesión
        window.addEventListener('auth:required', () => this.showLogin());
        window.addEventListener('auth:logout', () => this.showLogin());

        // Verificar estado inicial
        this.checkInitialState();
    }

    async checkInitialState() {
        if (!this.auth.isAuthenticated()) {
            this.showLogin();
        } else {
            // El usuario tiene un token en localStorage, pero aún NO ha sido validado contra el servidor.
            // NO debemos revelar la UI principal aquí (hideLogin) para evitar el pantallazo de seguridad.
            // app.js se encargará de validar el token de forma asíncrona y, si es válido, llamará a hideLogin().
            console.log('Token found locally, waiting for server validation...');
        }
    }

    async handleSubmit(e) {
        e.preventDefault();

        const username = this.form.username.value;
        const password = this.form.password.value;

        this.setLoading(true);

        try {
            const result = await this.auth.login(username, password);
            if (result.success) {
                this.hideLogin();
                this.applyRoleRestrictions();
                this.updateUserUI();
                // Notificar éxito al usuario
                if (window.Swal) {
                    Swal.fire({
                        icon: 'success',
                        title: '¡Bienvenido!',
                        text: `Has ingresado como ${result.user.username}`,
                        timer: 2000,
                        showConfirmButton: false,
                        position: 'top-end',
                        toast: true
                    }).then(() => {
                        window.location.reload();
                    });
                } else {
                    window.location.reload();
                }
            } else {
                this.showError(result.error);
            }
        } catch (error) {
            this.showError('Error de servidor');
        } finally {
            this.setLoading(false);
        }
    }

    showLogin() {
        if (this.container) {
            this.container.style.display = 'flex';
            document.body.style.overflow = 'hidden';

            // Revelar el body y ocultar el wrapper de la app
            document.body.style.opacity = '1';
            document.body.style.pointerEvents = 'auto';
            const wrapper = document.getElementById('app-wrapper');
            if (wrapper) wrapper.style.display = 'none';
        }
    }

    hideLogin() {
        if (this.container) {
            this.container.style.display = 'none';
            document.body.style.overflow = '';

            // Revelar el body y mostrar el wrapper de la app
            document.body.style.opacity = '1';
            document.body.style.pointerEvents = 'auto';
            const wrapper = document.getElementById('app-wrapper');
            if (wrapper) wrapper.style.display = 'block';
        }
    }

    setLoading(isLoading) {
        if (!this.btnSubmit) return;

        if (isLoading) {
            this.btnSubmit.disabled = true;
            this.btnSubmit.innerHTML = '<span>Verificando...</span> <i class="fas fa-spinner fa-spin"></i>';
        } else {
            this.btnSubmit.disabled = false;
            this.btnSubmit.innerHTML = '<span>Ingresar al Sistema</span> <i class="fas fa-sign-in-alt"></i>';
        }
    }

    showError(message) {
        if (window.Swal) {
            Swal.fire({
                icon: 'error',
                title: 'Error de Acceso',
                text: message,
                confirmButtonColor: '#4f46e5'
            });
        } else {
            alert(message);
        }
    }

    /**
     * Aplica restricciones visuales basadas en la Matriz de Permisos RBAC (DB-driven).
     * Traduce los permisos del módulo a visibilidad en el sidebar y botones de acción.
     */
    async applyRoleRestrictions() {
        const user = this.auth.getUser();
        if (!user) return;

        // Exponer rol globalmente para otros módulos
        window.RBAC_PERMS = {
            role: user.role,
            _isAdmin: (user.role === 'admin' || user.role === 'administradora')
        };
        console.log('Applying RBAC for role:', user.role);

        // Siempre ocultar el módulo Mis Finanzas por defecto (sólo visible para cobrador)
        const cfNav = document.getElementById('nav-collector-finance');
        if (cfNav) cfNav.style.display = 'none';

        // Los admins tienen acceso total (whitelist bypass)
        if (window.RBAC_PERMS._isAdmin) {
            console.log('Admin detected: granting full bypass');
            // Populate basic permissions as true just in case some module checks them directly 
            // without using app.checkPermission or our role check
            const modules = ['dashboard', 'routers:list', 'clients:list', 'clients:import', 'clients:actions', 'finance:reports', 'finance:payments', 'finance:invoices'];
            modules.forEach(m => {
                window.RBAC_PERMS[m] = { can_view: true, can_edit: true, can_delete: true, can_create: true };
            });
            return;
        }

        // ── Obtener permisos de la Matriz RBAC desde la DB ──────────────────────
        let permissions = [];
        try {
            permissions = await window.app.apiService.get('/api/users/permissions/me');
        } catch (e) {
            console.warn('Could not fetch RBAC permissions, falling back to role defaults.', e);
        }

        // Construir el mapa: module → permissions desde la DB
        const permMap = {};
        (permissions || []).forEach(p => { permMap[p.module] = p; });

        // Exponer globalmente para que otros módulos (clients.js, etc.) puedan leer permisos en render-time
        window.RBAC_PERMS = permMap;
        console.log('DEBUG: RBAC_PERMS populated:', permMap);
        console.log('DEBUG: clients:list permissions:', permMap['clients:list']);

        // ── Mapeo: data-view del sidebar → módulo en la DB ────────────────────
        const viewToModule = {
            'dashboard': 'dashboard',
            'routers': 'routers:list',
            'plans': 'plans',
            'clients': 'clients:list',
            'clients-import': 'clients:import',
            'clients-actions': 'clients:actions',
            'clients-trash': 'clients:list',
            'clients-alerts': 'clients:list',
            'finance-overview': 'finance:reports', // Overview draws from reports
            'payments-list': 'finance:payments',
            'invoices': 'finance:invoices',
            'reports': 'finance:reports',
            'promises': 'finance:promises',
            'expenses': 'finance:expenses',
            'automation': 'automation',
            'sync': 'sync',
            'metrics': 'metrics',
            'system': 'system:users',
            'trash': 'trash',
            'whatsapp': 'whatsapp:chats',
            'collector-finance': 'collector-finance',
            'clients-support': 'clients:support',
            'system-reciclador': 'system:reciclador',
            'clients-actions': 'clients:actions',
        };

        // ── Aplicar visibilidad a todos los nav items del sidebar ───────────────
        document.querySelectorAll('.nav-item:not(.has-submenu), .submenu-item').forEach(el => {
            const view = el.getAttribute('data-view');
            if (!view) return;
            const module = viewToModule[view];
            if (!module) return;

            const perm = permMap[module];
            // Si no tiene permiso explícito de can_view (o es nulo), se oculta (whitelist approach)
            // Excepción: clients-alerts (Bandeja de cobradores) siempre visible
            if (view === 'clients-alerts') {
                el.style.display = '';
            } else if (!perm || perm.can_view === false || perm.can_view === 0) {
                el.style.display = 'none';
            } else {
                el.style.display = ''; // Asegurar visibilidad si tiene permiso
            }
        });

        // ── Submenús completos sin can_view ─────────────────────────────────────
        const menuHideMap = {
            'nav-finanzas': ['finance:reports', 'finance:payments', 'finance:invoices', 'finance:expenses', 'collector-finance'],
            'nav-clientes': ['clients:list', 'clients:import', 'clients:trash', 'clients:actions'],
            'nav-routers': ['routers:list', 'routers:monitoring'],
            'nav-whatsapp': ['whatsapp:chats', 'whatsapp:config'],
            'nav-metrics': ['metrics'],
            'nav-sistema': ['system:users', 'system:rbac', 'system:reciclador'],
        };
        Object.entries(menuHideMap).forEach(([menuId, modules]) => {
            const allHidden = modules.every(m => permMap[m] && !permMap[m].can_view);
            if (allHidden) {
                const el = document.getElementById(menuId);
                if (el) el.style.display = 'none';
            }
        });

        // ── Excepciones manuales para menús padres que deben verse si hay hijos especiales ──
        // ── Excepciones manuales para menús padres que deben verse si hay hijos especiales ──
        // Mostrar 'nav-clientes' siempre para rol collector porque tienen 'Alertas' dentro
        if (user.role === 'collector' || user.role === 'cobrador') {
            const clientesNav = document.getElementById('nav-clientes');
            const clientesSubmenu = document.getElementById('clientes-submenu');
            if (clientesNav) clientesNav.style.display = 'flex';
            if (clientesSubmenu) clientesSubmenu.style.display = 'block';
        }

        // ── Mostrar Mis Finanzas SOLO si el cobrador tiene can_view ─────────
        const cfPerm = permMap['collector-finance'];
        if (cfPerm && cfPerm.can_view && cfNav) {
            cfNav.style.display = 'flex';
        }

        // ── Botones de acción: ocultar según permisos de módulo ─────────────────
        const canCreateClients = permMap['clients:list']?.can_create ?? true;
        const canImportClients = permMap['clients:import']?.can_view ?? true;
        if (!canCreateClients) {
            const btn = document.getElementById('add-client-btn');
            if (btn) btn.style.display = 'none';
        }
        if (!canImportClients) {
            const btn = document.getElementById('import-clients-btn');
            if (btn) btn.style.display = 'none';
            const bar = document.getElementById('bulk-actions-bar');
            if (bar) bar.style.display = 'none';
        }
    }



    /**
     * Actualiza el perfil del usuario en el sidebar
     */
    updateUserUI() {
        const user = this.auth.getUser();
        if (!user) return;

        const nameEl = document.querySelector('.user-name');
        const roleEl = document.querySelector('.user-role');

        if (nameEl) nameEl.textContent = user.username.charAt(0).toUpperCase() + user.username.slice(1);
        if (roleEl) roleEl.textContent = user.role === 'admin' ? 'Administrador' : 'Cobrador';

        // Agregar botón de logout si no existe
        this.ensureLogoutButton();
    }

    ensureLogoutButton() {
        const footer = document.querySelector('.sidebar-footer');
        if (!footer || document.getElementById('btn-logout')) return;

        const logoutBtn = document.createElement('button');
        logoutBtn.id = 'btn-logout';
        logoutBtn.className = 'btn-logout';
        logoutBtn.style.cssText = `
            margin: 12px 16px 16px 16px;
            width: calc(100% - 32px);
            padding: 10px 16px;
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(220, 38, 38, 0.03) 100%);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.15);
            border-radius: 12px;
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 4px 15px -3px rgba(239, 68, 68, 0.05);
            letter-spacing: 0.3px;
        `;
        logoutBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
            </svg>
            <span>Cerrar Sesión</span>
        `;

        logoutBtn.onmouseover = () => {
            logoutBtn.style.background = 'linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.08) 100%)';
            logoutBtn.style.borderColor = 'rgba(239, 68, 68, 0.3)';
            logoutBtn.style.transform = 'translateY(-2px)';
            logoutBtn.style.boxShadow = '0 6px 20px -4px rgba(239, 68, 68, 0.15)';
            logoutBtn.style.color = '#dc2626';
        };

        logoutBtn.onmouseout = () => {
            logoutBtn.style.background = 'linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(220, 38, 38, 0.03) 100%)';
            logoutBtn.style.borderColor = 'rgba(239, 68, 68, 0.15)';
            logoutBtn.style.transform = 'translateY(0)';
            logoutBtn.style.boxShadow = '0 4px 15px -3px rgba(239, 68, 68, 0.05)';
            logoutBtn.style.color = '#ef4444';
        };

        logoutBtn.onclick = () => {
            if (window.Swal) {
                Swal.fire({
                    title: '¿Cerrar sesión?',
                    text: "Tendrás que ingresar tus credenciales nuevamente.",
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#ef4444',
                    cancelButtonColor: '#4f46e5',
                    confirmButtonText: 'Sí, salir',
                    cancelButtonText: 'Cancelar'
                }).then((result) => {
                    if (result.isConfirmed) {
                        this.auth.logout();
                    }
                });
            } else if (confirm('¿Estás seguro de que deseas cerrar sesión?')) {
                this.auth.logout();
            }
        };

        footer.appendChild(logoutBtn);
    }

    /**
     * Verifica si el usuario tiene un permiso específico.
     * Útil para componentes que necesitan habilitar/deshabilitar UI.
     */
    checkPermission(module, action) {
        const user = this.auth.getUser();
        if (!user) return false;

        // Admins tienen pase total
        if (user.role === 'admin' || user.role === 'administradora') return true;

        const perm = (window.RBAC_PERMS || {})[module];
        if (!perm) return false;

        const actionMap = {
            'view': perm.can_view,
            'create': perm.can_create,
            'edit': perm.can_edit,
            'delete': perm.can_delete,
            'print': perm.can_print,
            'revert': perm.can_revert
        };

        return !!actionMap[action];
    }
}
