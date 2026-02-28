/**
 * Users Module
 * Gestión de usuarios y perfiles administrativos
 */

export class UsersModule {
    constructor(apiService, eventBus, viewManager) {
        this.apiService = apiService;
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.users = [];
        this.routers = [];
        this.container = document.getElementById('system-view');
        this.tableBody = document.getElementById('users-table-body');
        this.currentTab = 'users';
        this.permissions = [];
        this.initialized = false;
        this.isMobile = window.innerWidth < 1100;

        window.addEventListener('resize', () => {
            const wasMobile = this.isMobile;
            this.isMobile = window.innerWidth < 1100;
            if (wasMobile !== this.isMobile && this.viewManager.currentSubView === 'system') {
                this.renderUsers();
            }
        });

        this.subscribeToEvents();
    }

    subscribeToEvents() {
        if (this.eventBus) {
            this.eventBus.subscribe('navigate', (data) => {
                if (data.view === 'system') {
                    this.showView();
                    if (!this.initialized) {
                        this.load();
                    }
                }
            });
        }
    }

    showView() {
        if (this.viewManager) {
            this.viewManager.showMainView('system');
        }
    }

    async load() {
        if (!window.app.authService.isAdmin()) {
            window.showToast('Acceso restringido a administradores', 'error');
            return;
        }

        this.showLoading();
        try {
            // Cargar usuarios y routers en paralelo
            const [usersRes, routersRes] = await Promise.all([
                this.apiService.get('/api/users'),
                this.apiService.get('/api/routers')
            ]);

            this.users = usersRes;
            this.routers = routersRes;

            this.renderUsers();
            this.updateStats();
            this.initListeners();
            this.initialized = true;
        } catch (error) {
            console.error('Error loading users:', error);
            window.showToast('Error al cargar datos del sistema', 'error');
        } finally {
            this.hideLoading();
        }
    }

    renderUsers() {
        const tbody = document.getElementById('users-table-body');
        const cardsGrid = document.getElementById('system-users-cards-grid');
        const tableView = document.getElementById('system-users-table-view');

        if (!tbody && !cardsGrid) return;

        if (this.isMobile && cardsGrid) {
            if (tableView) tableView.style.display = 'none';
            cardsGrid.style.display = 'grid';
        } else if (tableView) {
            if (cardsGrid) cardsGrid.style.display = 'none';
            tableView.style.display = 'block';
        }

        if (this.users.length === 0) {
            const emptyMsg = 'No hay usuarios registrados';
            if (this.isMobile && cardsGrid) cardsGrid.innerHTML = `<div class="empty-state">${emptyMsg}</div>`;
            else if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center">${emptyMsg}</td></tr>`;
            return;
        }

        const html = this.users.map(user => this.renderSingleUserHtml(user)).join('');

        if (this.isMobile && cardsGrid) {
            cardsGrid.innerHTML = html;
        } else if (tbody) {
            tbody.innerHTML = html;
        }
    }

    renderSingleUserHtml(user) {
        const hasAssignments = user.assignments && user.assignments.length > 0;
        const router = this.routers.find(r => r.id === user.assigned_router_id);

        let routerDisplayName = 'N/A';
        let routerIcon = '<i class="fas fa-times-circle" style="color: #ef4444;"></i>';

        if (user.role === 'admin' || user.role === 'administradora' || user.role === 'partner') {
            routerDisplayName = 'Acceso Total';
            routerIcon = '<i class="fas fa-globe" style="color: #10b981;"></i>';
        } else if (hasAssignments) {
            if (user.assignments.length === 1) {
                const singleRouter = this.routers.find(r => r.id === user.assignments[0].router_id);
                routerDisplayName = singleRouter ? singleRouter.alias : 'Desconocido';
            } else {
                routerDisplayName = `${user.assignments.length} Routers`;
            }
            routerIcon = '<i class="fas fa-network-wired" style="color: #8b5cf6;"></i>';
        } else if (router) {
            routerDisplayName = router.alias;
            routerIcon = '<i class="fas fa-server" style="color: #6366f1;"></i>';
        }

        const roleBadge = user.role === 'admin' || user.role === 'administradora' ?
            '<span class="status-badge active"><i class="fas fa-shield-alt"></i> Administrador</span>' :
            (user.role === 'collector' || user.role === 'cobrador' ? '<span class="status-badge warning"><i class="fas fa-user-tag"></i> Cobrador</span>' :
                '<span class="status-badge primary"><i class="fas fa-user"></i> Operador</span>');

        const formatDate = (dateString) => {
            if (!dateString) return '-';
            const date = new Date(dateString);
            return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
        };

        const badge = user.username === 'admin' ?
            '<span class="status-badge active ml-2" style="font-size: 0.7em; padding: 3px 6px;"><i class="fas fa-crown"></i> Super Admin</span>' : '';

        const deleteBtn = user.username !== 'admin' ? `
            <button class="btn-secondary btn-icon delete" onclick="app.modules.users.deleteUser(${user.id})" title="Eliminar Usuario">
                <i class="fas fa-trash"></i>
            </button>
        ` : '';

        if (this.isMobile) {
            return `
                <div class="premium-mobile-card user-card-mobile" data-user-id="${user.id}">
                    <div class="card-row">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <div class="avatar-mini" style="background: var(--primary); color: white; width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-weight: 700;">
                                ${user.username.charAt(0).toUpperCase()}
                            </div>
                            <div>
                                <div class="card-value">${user.username} ${badge}</div>
                                <div class="card-label">${user.full_name || user.name || ''}</div>
                            </div>
                        </div>
                        <span class="status-badge-table ${user.role}">${user.role.toUpperCase()}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Ruta Asignada</span>
                        <div class="card-value" style="display: flex; align-items: center; gap: 6px;">
                            ${routerIcon} ${routerDisplayName}
                        </div>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Último Acceso</span>
                        <span class="card-value" style="font-size: 0.75rem;">${formatDate(user.last_login)}</span>
                    </div>
                    <div class="card-actions">
                        <button class="btn-icon" onclick="app.modules.users.editUser(${user.id})" title="Editar">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn-icon" onclick="app.modules.users.managePermissions(${user.id})" title="Permisos">
                            <i class="fas fa-key"></i>
                        </button>
                        ${deleteBtn}
                    </div>
                </div>
            `;
        }

        return `
            <tr data-id="${user.id}">
                <td style="font-weight: 600; color: #1e293b;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div style="width: 32px; height: 32px; border-radius: 8px; background: rgba(99, 102, 241, 0.1); color: #6366f1; display: flex; align-items: center; justify-content: center;">
                            <i class="fas fa-user"></i>
                        </div>
                        <span>${user.username}</span>
                        ${badge}
                    </div>
                </td>
                <td style="color: #64748b;">${user.identity_document || '-'}</td>
                <td style="color: #334155; font-weight: 500;">${user.full_name || '-'}</td>
                <td>${roleBadge}</td>
                <td style="color: #64748b; font-size: 0.9em;">
                    <i class="fas fa-map-marker-alt" style="margin-right: 4px; color: #94a3b8;"></i>
                    ${user.assigned_zone || '-'}
                </td>
                <td>
                    <div style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem;">
                        ${routerIcon}
                        <span style="color: #64748b;">${routerDisplayName}</span>
                    </div>
                </td>
                <td style="font-size: 0.85rem; color: #64748b;">${formatDate(user.last_login)}</td>
                <td style="text-align: right;">
                    <div style="display: flex; gap: 8px; justify-content: flex-end;">
                        <button class="btn-secondary btn-icon" onclick="app.modules.users.editUser(${user.id})" title="Editar">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn-secondary btn-icon" onclick="app.modules.users.managePermissions(${user.id})" title="Permisos"><i class="fas fa-key"></i></button>
                        ${deleteBtn}
                    </div>
                </td>
            </tr>
        `;
    }

    updateStats() {
        const total = this.users.length;
        const admins = this.users.filter(u => u.role === 'admin' || u.role === 'administradora').length;
        const collectors = this.users.filter(u => u.role === 'collector' || u.role === 'cobrador').length;

        const totalEl = document.getElementById('total-users-count');
        const adminEl = document.getElementById('admin-users-count');
        const collEl = document.getElementById('collector-users-count');

        if (totalEl) totalEl.textContent = total;
        if (adminEl) adminEl.textContent = admins;
        if (collEl) collEl.textContent = collectors;
    }

    initListeners() {
        const btnAdd = document.getElementById('btn-add-user');
        if (btnAdd && !btnAdd.getAttribute('listener')) {
            btnAdd.addEventListener('click', () => this.showUserForm());
            btnAdd.setAttribute('listener', 'true');
        }

        // Tabs
        // Tabs for Subsections (Auditoría/Backups)
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.onclick = () => {
                const target = btn.getAttribute('data-tab');
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');

                btn.classList.add('active');
                document.getElementById(target).style.display = 'block';
            };
        });
    }

    switchTab(tabId) {
        this.currentTab = tabId;

        // Update Buttons
        document.getElementById('tab-btn-users').classList.remove('active');
        document.getElementById('tab-btn-permissions').classList.remove('active');

        document.getElementById(`tab-btn-${tabId}`).classList.add('active');

        // Update Content visibility
        document.getElementById('tab-users-content').style.display = 'none';
        document.getElementById('tab-permissions-content').style.display = 'none';

        document.getElementById(`tab-${tabId}-content`).style.display = 'block';

        // Trigger loads
        if (tabId === 'permissions') {
            this.loadPermissions();
        }
    }

    async loadPermissions() {
        const role = document.getElementById('role-selector').value;
        const container = document.getElementById('permissions-container');

        container.innerHTML = `
            <div id="permissions-loading" class="text-center" style="padding: 100px 0; width: 100%; grid-column: 1 / -1;">
                <div class="spinner"></div>
                <p class="mt-3 text-muted">Diseñando matriz premium de ${role}...</p>
            </div>
        `;

        try {
            const data = await this.apiService.get(`/api/users/permissions/${role}`);
            this.permissions = data;
            this.renderPermissions();
        } catch (error) {
            console.error('Error cargando permisos:', error);
            window.showToast('Error al cargar la matriz de permisos', 'error');
            container.innerHTML = `<div class="text-center text-danger" style="grid-column: 1 / -1; padding: 50px;">Error de carga. Por favor intente de nuevo.</div>`;
        }
    }

    renderPermissions() {
        const container = document.getElementById('permissions-container');
        const role = document.getElementById('role-selector').value;

        if (!this.permissions || this.permissions.length === 0) {
            container.innerHTML = `<div class="text-center" style="grid-column: 1 / -1; padding: 50px;">No hay permisos definidos para este rol.</div>`;
            return;
        }

        const moduleNames = {
            'dashboard': { label: 'Panel & Estadísticas', icon: 'fas fa-chart-line', color: '#8b5cf6' },
            'clients:list': { label: 'Gestión de Clientes (Lista)', icon: 'fas fa-users', color: '#6366f1' },
            'clients:import': { label: 'Clientes: Importar/Crear', icon: 'fas fa-user-plus', color: '#6366f1' },
            'clients:trash': { label: 'Clientes: Papelera', icon: 'fas fa-trash-alt', color: '#6366f1' },
            'finance:payments': { label: 'Finanzas: Pagos', icon: 'fas fa-cash-register', color: '#10b981' },
            'finance:invoices': { label: 'Finanzas: Facturas', icon: 'fas fa-file-invoice-dollar', color: '#10b981' },
            'finance:promises': { label: 'Finanzas: Promesas', icon: 'fas fa-handshake', color: '#10b981' },
            'finance:reports': { label: 'Finanzas: Reportes', icon: 'fas fa-chart-bar', color: '#10b981' },
            'finance:expenses': { label: 'Finanzas: Gastos', icon: 'fas fa-shopping-cart', color: '#10b981' },
            'routers:list': { label: 'Routers: Gestión', icon: 'fas fa-server', color: '#f59e0b' },
            'routers:monitoring': { label: 'Routers: Monitoreo Real-Time', icon: 'fas fa-broadcast-tower', color: '#f59e0b' },
            'whatsapp:chats': { label: 'WhatsApp: Mensajería', icon: 'fab fa-whatsapp', color: '#22c55e' },
            'whatsapp:config': { label: 'WhatsApp: Configuración', icon: 'fas fa-mobile-alt', color: '#22c55e' },
            'system:users': { label: 'Sistema: Usuarios', icon: 'fas fa-user-shield', color: '#64748b' },
            'system:rbac': { label: 'Sistema: Roles y Permisos', icon: 'fas fa-key', color: '#64748b' },
            'system:reciclador': { label: 'Centinela (Reciclador)', icon: 'fas fa-shield-virus', color: '#64748b' },
            'collector-finance': { label: 'Finanzas: Vista Cobrador', icon: 'fas fa-wallet', color: '#0ea5e9' },
            'clients:support': { label: 'Clientes: Soporte/Tickets', icon: 'fas fa-headset', color: '#6366f1' },
            'clients:actions': { label: 'Clientes: Acciones Masivas', icon: 'fas fa-tasks', color: '#6366f1' },
            'automation': { label: 'Automatización (Cortes/Avisos)', icon: 'fas fa-robot', color: '#64748b' },
            'plans': { label: 'Gestión de Planes', icon: 'fas fa-boxes', color: '#f59e0b' },
            'fin-overview': { label: 'Finanzas: Resumen General', icon: 'fas fa-eye', color: '#10b981' }
        };

        const moduleCapabilities = {
            'dashboard': { view: 1 },
            'clients:list': { view: 1, create: 1, edit: 1, delete: 1 },
            'clients:import': { view: 1, create: 1 },
            'clients:trash': { view: 1, delete: 1 },
            'finance:payments': { view: 1, create: 1, edit: 1, delete: 1, print: 1, revert: 1 },
            'finance:invoices': { view: 1, create: 1, print: 1 },
            'finance:promises': { view: 1, create: 1, edit: 1, delete: 1 },
            'finance:reports': { view: 1, print: 1 },
            'finance:expenses': { view: 1, create: 1, edit: 1, delete: 1 },
            'routers:list': { view: 1, create: 1, edit: 1, delete: 1 },
            'routers:monitoring': { view: 1 },
            'whatsapp:chats': { view: 1, create: 1 },
            'whatsapp:config': { view: 1, edit: 1 },
            'system:users': { view: 1, create: 1, edit: 1, delete: 1 },
            'system:rbac': { view: 1, edit: 1 },
            'system:reciclador': { view: 1 },
            'collector-finance': { view: 1, create: 1, print: 1 },
            'clients:support': { view: 1, create: 1, edit: 1, delete: 1 },
            'clients:actions': { view: 1, edit: 1 },
            'automation': { view: 1, edit: 1 },
            'plans': { view: 1, create: 1, edit: 1, delete: 1 }
        };

        const categories = [
            { id: 'admin', label: 'Gestión Administrativa', icon: 'fas fa-tools', modules: ['dashboard', 'system:users', 'system:rbac', 'system:reciclador', 'automation'] },
            { id: 'ops', label: 'Operaciones de Campo', icon: 'fas fa-user-cog', modules: ['clients:list', 'clients:import', 'clients:support', 'clients:actions', 'clients:trash', 'plans'] },
            { id: 'finance', label: 'Módulo Financiero', icon: 'fas fa-dollar-sign', modules: ['finance:payments', 'finance:invoices', 'finance:promises', 'finance:reports', 'finance:expenses', 'collector-finance', 'fin-overview'] },
            { id: 'infra', label: 'Infraestructura y Red', icon: 'fas fa-broadcast-tower', modules: ['routers:list', 'routers:monitoring', 'whatsapp:chats', 'whatsapp:config'] }
        ];

        const renderToggle = (id, field, value, isAvailable = true) => {
            if (!isAvailable) return '';
            const labels = { 'view': 'Ver', 'create': 'Añadir', 'edit': 'Editar', 'delete': 'Borrar', 'print': 'Imprimir', 'revert': 'Revertir' };
            return `
                <div class="perm-action-item">
                    <span class="perm-action-label">${labels[field]}</span>
                    <label class="switch-ios">
                        <input type="checkbox" id="perm_${id}_${field}" ${value ? 'checked' : ''} ${role === 'admin' ? 'disabled' : ''}>
                        <span class="slider round"></span>
                    </label>
                </div>
            `;
        };

        // HUD Calculation
        let visibleCount = 0;
        let riskHigh = false;
        this.permissions.forEach(p => {
            if (p.can_view) visibleCount++;
            if (p.can_delete || p.can_revert) riskHigh = true;
        });

        const accessLabel = role === 'admin' || role === 'administradora' ? '<span class="text-primary"><i class="fas fa-crown"></i> Total</span>' :
            (role === 'tecnico' || role === 'secretaria') ? 'Operativo' : 'Restringido';

        document.getElementById('hud-access-level').innerHTML = accessLabel;
        document.getElementById('hud-visible-modules').innerText = visibleCount;
        const riskHud = document.getElementById('hud-risk-actions');
        riskHud.innerText = riskHigh ? 'Activadas' : 'Desactivadas';
        riskHud.style.color = riskHigh ? '#f43f5e' : '#10b981';
        if (riskHigh) riskHud.classList.add('perm-hud-pulse'); else riskHud.classList.remove('perm-hud-pulse');

        // Render Grid
        let html = '';
        categories.forEach(cat => {
            const catPerms = this.permissions.filter(p => cat.modules.includes(p.module));
            if (catPerms.length === 0) return;

            html += `
                <div class="category-section">
                    <div class="category-title">
                        <i class="${cat.icon}"></i> ${cat.label}
                    </div>
                </div>
            `;

            catPerms.forEach(perm => {
                const info = moduleNames[perm.module] || { label: perm.module, icon: 'fas fa-cube', color: '#64748b' };
                const caps = moduleCapabilities[perm.module] || { view: 1, create: 1, edit: 1, delete: 1, print: 1, revert: 1 };

                html += `
                    <div class="perm-card" data-module="${perm.module}" style="--card-theme-color: ${info.color}">
                        <div class="perm-card-header">
                            <i class="${info.icon}" style="color: ${info.color}"></i>
                            <div class="perm-card-title">${info.label}</div>
                        </div>
                        <div class="perm-actions-grid">
                            ${renderToggle(perm.id, 'view', perm.can_view, !!caps.view)}
                            ${renderToggle(perm.id, 'create', perm.can_create, !!caps.create)}
                            ${renderToggle(perm.id, 'edit', perm.can_edit, !!caps.edit)}
                            ${renderToggle(perm.id, 'delete', perm.can_delete, !!caps.delete)}
                            ${renderToggle(perm.id, 'print', perm.can_print, !!caps.print)}
                            ${renderToggle(perm.id, 'revert', perm.can_revert, !!caps.revert)}
                        </div>
                    </div>
                `;
            });
        });

        container.innerHTML = html;
    }

    async savePermissions() {
        const role = document.getElementById('role-selector').value;
        if (role === 'admin') {
            window.showToast('Los permisos del administrador no pueden alterarse por seguridad', 'warning');
            return;
        }

        const btn = document.querySelector('#tab-permissions-content .btn-premium');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
        btn.disabled = true;

        try {
            const updates = this.permissions.map(perm => {
                const getVal = (field) => {
                    const el = document.getElementById(`perm_${perm.id}_${field}`);
                    return el ? el.checked : !!perm[`can_${field}`]; // Keep existing value if not in UI
                };

                return {
                    id: perm.id,
                    can_view: getVal('view'),
                    can_create: getVal('create'),
                    can_edit: getVal('edit'),
                    can_delete: getVal('delete'),
                    can_print: getVal('print'),
                    can_revert: getVal('revert')
                };
            });

            await this.apiService.post(`/api/users/permissions/${role}`, { permissions: updates });
            window.showToast('Matriz de Permisos actualizada. Se aplicará a los cobradores inmediatamente.', 'success');
        } catch (error) {
            console.error('Error saving matrix:', error);
            window.showToast('Error al guardar matriz', 'error');
        } finally {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }

    async showUserForm(userId = null) {
        const user = userId ? this.users.find(u => u.id === userId) : null;

        const { value: formValues } = await Swal.fire({
            title: false,
            html: `
                <div class="premium-modal-container">
                    <div class="modal-header" style="background: transparent; padding: 0 0 15px 0; border: none; flex-direction: column; gap: 5px;">
                        <div style="width: 50px; height: 50px; border-radius: 14px; background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(79, 70, 229, 0.2) 100%); color: #6366f1; display: flex; align-items: center; justify-content: center; font-size: 20px; margin: 0 auto;">
                            <i class="fas ${user ? 'fa-user-edit' : 'fa-user-plus'}"></i>
                        </div>
                        <h3 style="color: #1e293b; font-size: 1.3rem; font-weight: 800; margin: 0;">${user ? 'Editar Usuario' : 'Nuevo Usuario'}</h3>
                    </div>

                    <!-- MODERN TABS NAVIGATION (Segmented Control / Pill Design) -->
                    <div class="modal-tabs-wrapper" style="background: #f1f5f9; padding: 4px; border-radius: 12px; display: flex; gap: 4px; margin-bottom: 25px; border: 1px solid #e2e8f0;">
                        <button type="button" class="form-tab-btn active" data-target="tab-profile" style="flex: 1; padding: 10px 15px; border: none; background: transparent; font-weight: 700; color: #64748b; cursor: pointer; border-radius: 9px; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); display: flex; align-items: center; justify-content: center; gap: 8px; white-space: nowrap; font-size: 0.9rem;">
                            <i class="fas fa-user-circle"></i> <span>Perfil</span>
                        </button>
                        <button type="button" class="form-tab-btn" data-target="tab-assignments" id="btn-tab-assignments" style="flex: 1; padding: 10px 15px; border: none; background: transparent; font-weight: 700; color: #64748b; cursor: pointer; border-radius: 9px; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); display: ${user?.role === 'collector' ? 'flex' : 'none'}; align-items: center; justify-content: center; gap: 8px; white-space: nowrap; font-size: 0.9rem;">
                            <i class="fas fa-percentage"></i> <span>Comisiones</span>
                        </button>
                    </div>

                    <form autocomplete="off" onsubmit="return false;" style="text-align: left;">
                        
                        <!-- TAB: PROFILE -->
                        <div id="tab-profile" class="form-tab-content">
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                                <div class="form-group">
                                    <label class="form-label-premium">Usuario</label>
                                    <div class="input-with-icon" style="position: relative;">
                                        <i class="fas fa-user" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #94a3b8;"></i>
                                        <input id="swal-username" class="swal2-input form-control-premium" style="width: 100%; margin: 0; padding-left: 35px; height: 38px; font-size: 0.9rem;" placeholder="Ej. jperez" value="${user ? user.username : ''}">
                                    </div>
                                </div>

                                <div class="form-group">
                                    <label class="form-label-premium">Nombre Real</label>
                                    <div class="input-with-icon" style="position: relative;">
                                        <i class="fas fa-id-card" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #94a3b8;"></i>
                                        <input id="swal-full-name" class="swal2-input form-control-premium" style="width: 100%; margin: 0; padding-left: 35px; height: 38px; font-size: 0.9rem;" placeholder="Juan Pérez" value="${user?.full_name || ''}">
                                    </div>
                                </div>

                                <div class="form-group">
                                    <label class="form-label-premium">Cédula</label>
                                    <div class="input-with-icon" style="position: relative;">
                                        <i class="fas fa-fingerprint" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #94a3b8;"></i>
                                        <input id="swal-identity-document" class="swal2-input form-control-premium" style="width: 100%; margin: 0; padding-left: 35px; height: 38px; font-size: 0.9rem;" placeholder="V-12345678" value="${user?.identity_document || ''}">
                                    </div>
                                </div>
                                
                                <div class="form-group">
                                    <label class="form-label-premium">Teléfono</label>
                                    <div class="input-with-icon" style="position: relative;">
                                        <i class="fas fa-phone" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #94a3b8;"></i>
                                        <input id="swal-phone-number" class="swal2-input form-control-premium" style="width: 100%; margin: 0; padding-left: 35px; height: 38px; font-size: 0.9rem;" placeholder="0414-..." value="${user?.phone_number || ''}">
                                    </div>
                                </div>

                                <div class="form-group" style="grid-column: span 2;">
                                    <label class="form-label-premium">Email</label>
                                    <div class="input-with-icon" style="position: relative;">
                                        <i class="fas fa-envelope" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #94a3b8;"></i>
                                        <input id="swal-email" type="email" class="swal2-input form-control-premium" style="width: 100%; margin: 0; padding-left: 35px; height: 38px; font-size: 0.9rem;" placeholder="correo@ejemplo.com" value="${user?.email || ''}">
                                    </div>
                                </div>

                                <div class="form-group" style="grid-column: span 2;">
                                    <label class="form-label-premium">Dirección</label>
                                    <div class="input-with-icon" style="position: relative;">
                                        <i class="fas fa-map-marker-alt" style="position: absolute; left: 10px; top: 15px; color: #94a3b8;"></i>
                                        <textarea id="swal-address" class="swal2-textarea form-control-premium" style="width: 100%; margin: 0; padding: 8px 8px 8px 35px; height: 60px; font-size: 0.9rem; resize: none;" placeholder="Dirección...">${user?.address || ''}</textarea>
                                    </div>
                                </div>

                                <div class="form-group">
                                    <label class="form-label-premium">Rol</label>
                                    <div class="input-with-icon" style="position: relative;">
                                        <i class="fas fa-shield-alt" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #6366f1;"></i>
                                        <select id="swal-role" class="swal2-select form-control-premium select-premium" style="width: 100%; margin: 0; padding-left: 35px; height: 38px; font-size: 0.9rem;">
                                            <option value="admin" ${user?.role === 'admin' ? 'selected' : ''}>Administrador</option>
                                            <option value="administradora" ${user?.role === 'administradora' ? 'selected' : ''}>Administradora</option>
                                            <option value="socio" ${user?.role === 'socio' ? 'selected' : ''}>Socio</option>
                                            <option value="secretaria" ${user?.role === 'secretaria' ? 'selected' : ''}>Secretaria</option>
                                            <option value="tecnico" ${user?.role === 'tecnico' ? 'selected' : ''}>Técnico</option>
                                            <option value="collector" ${user?.role === 'collector' ? 'selected' : ''}>Cobrador</option>
                                        </select>
                                    </div>
                                </div>

                                <div class="form-group">
                                    <label class="form-label-premium">${user ? 'Cambiar Clave' : 'Clave'}</label>
                                    <div class="input-with-icon" style="position: relative;">
                                        <i class="fas fa-lock" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #94a3b8;"></i>
                                        <input id="swal-password" type="password" class="swal2-input form-control-premium" style="width: 100%; margin: 0; padding-left: 35px; height: 38px; font-size: 0.9rem;" placeholder="••••••••">
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- TAB: ASSIGNMENTS -->
                        <div id="tab-assignments" class="form-tab-content" style="display: none;">
                            <div class="form-group" id="router-select-container" style="display: none;">
                                <label class="form-label-premium">Router Asignado (Técnico/Secretaria)</label>
                                <div class="input-with-icon" style="position: relative;">
                                    <i class="fas fa-server" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #94a3b8;"></i>
                                    <select id="swal-router" class="swal2-select form-control-premium select-premium" style="width: 100%; margin: 0; padding-left: 35px; height: 38px;">
                                        <option value="">-- Nodo Global --</option>
                                        ${this.routers.map(r => `<option value="${r.id}" ${user?.assigned_router_id === r.id ? 'selected' : ''}>${r.alias}</option>`).join('')}
                                    </select>
                                </div>
                            </div>
                            
                            <!-- Explicación Visual Breve -->
                            <div style="background: rgba(99, 102, 241, 0.05); border-left: 3px solid #6366f1; padding: 10px 15px; margin-bottom: 15px; border-radius: 4px; font-size: 0.85rem; color: #475569;">
                                <i class="fas fa-info-circle" style="color: #6366f1; margin-right: 5px;"></i>
                                Asigne aquí los nodos a los que este cobrador tendrá acceso.
                            </div>

                            <div id="collector-assignments-section" style="display: ${user?.role === 'collector' ? 'block' : 'none'}; margin-top: 5px;">
                                <div style="display: flex; gap: 10px; margin-bottom: 12px;">
                                    <div class="form-group" style="flex: 2; margin-bottom: 0;">
                                        <label class="form-label-premium">Zona (Texto)</label>
                                        <input id="swal-assigned-zone" class="swal2-input form-control-premium" style="width: 100%; margin: 0; height: 38px; font-size: 0.9rem;" placeholder="Ej. Zona Norte" value="${user?.assigned_zone || ''}">
                                    </div>
                                </div>

                                <label class="form-label-premium" style="color: #6366f1;"><i class="fas fa-network-wired"></i> Gestión Multirouter</label>
                                
                                <div id="assignments-list" style="max-height: 120px; overflow-y: auto; margin-bottom: 12px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; padding: 5px;">
                                    <!-- Dinámico -->
                                </div>

                                <div style="display: grid; grid-template-columns: 1.5fr 1fr 1fr 40px; gap: 8px; padding: 10px; background: #fff; border: 1px dashed #cbd5e1; border-radius: 8px;">
                                    <div>
                                        <select id="new-assignment-router" class="swal2-select" style="width: 100%; height: 35px; font-size: 0.8rem; margin: 0;">
                                            <option value="">-- Nodo --</option>
                                            ${this.routers.map(r => `<option value="${r.id}">${r.alias} ($${(r.potential_revenue || 0).toLocaleString()})</option>`).join('')}
                                        </select>
                                    </div>
                                    <input id="new-assignment-pct" type="number" step="0.1" class="swal2-input" style="width: 100%; height: 35px; font-size: 0.8rem; margin: 0;" placeholder="%">
                                    <input id="new-assignment-bonus" type="number" class="swal2-input" style="width: 100%; height: 35px; font-size: 0.8rem; margin: 0;" placeholder="$">
                                    <button type="button" id="btn-add-assignment" class="btn-premium primary" style="height: 35px; width: 40px; padding: 0; border-radius: 6px;">
                                        <i class="fas fa-plus"></i>
                                    </button>
                                </div>
                            </div>
                        </div>

                    </form>
                </div>

                <style>
                    .form-label-premium { font-size: 0.7rem; font-weight: 800; color: #64748b; margin-bottom: 4px; display: block; text-transform: uppercase; letter-spacing: 0.02em; }
                    .form-tab-btn.active { background: white !important; color: #6366f1 !important; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06) !important; }
                    .form-tab-btn:hover:not(.active) { color: #1e293b !important; }
                </style>
            `,
            customClass: {
                popup: 'premium-modal',
                confirmButton: 'btn-premium primary',
                cancelButton: 'btn-secondary',
                actions: 'swal-premium-actions'
            },
            buttonsStyling: false,
            showCancelButton: true,
            confirmButtonText: '<i class="fas fa-save"></i> Guardar',
            cancelButtonText: 'Cancelar',
            didOpen: () => {
                const roleSelect = Swal.getPopup().querySelector('#swal-role');
                const routerContainer = Swal.getPopup().querySelector('#router-select-container');
                const collectorSection = Swal.getPopup().querySelector('#collector-assignments-section');
                const btnTabAssignments = document.getElementById('btn-tab-assignments');

                // TABS LOGIC
                const tabs = Swal.getPopup().querySelectorAll('.form-tab-btn');
                const contents = Swal.getPopup().querySelectorAll('.form-tab-content');
                tabs.forEach(tab => {
                    tab.onclick = () => {
                        tabs.forEach(t => t.classList.remove('active'));
                        contents.forEach(c => c.style.display = 'none');
                        tab.classList.add('active');
                        document.getElementById(tab.getAttribute('data-target')).style.display = 'block';
                    };
                });

                // STATE FOR ASSIGNMENTS
                let currentAssignments = user?.assignments ? [...user.assignments] : [];

                // MIGRACIÓN DATOS LEGACY si se está editando y no tiene asignaciones nuevas
                if (user?.role === 'collector' && currentAssignments.length === 0 && user.assigned_router_id) {
                    console.log('Detectada ruta legacy, migrando a vista de asignaciones...');
                    currentAssignments.push({
                        router_id: user.assigned_router_id,
                        profit_percentage: user.profit_percentage || 0,
                        bonus_amount: user.bonus_amount || 0
                    });
                }

                const renderAssignments = () => {
                    const list = document.getElementById('assignments-list');
                    if (!list) return;
                    if (currentAssignments.length === 0) {
                        list.innerHTML = '<div style="padding: 10px; font-size: 0.8rem; color: #94a3b8; text-align: center;">Sin nodos asignados</div>';
                        return;
                    }
                    list.innerHTML = currentAssignments.map((a, idx) => {
                        const r = this.routers.find(rt => rt.id == a.router_id);
                        return `
                            <div id="assignment-row-${idx}" style="display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 4px; cursor: pointer; transition: all 0.2s;" onmouseover="this.style.borderColor='#6366f1'" onmouseout="this.style.borderColor='#e2e8f0'">
                                <div style="font-size: 0.8rem; font-weight: 600;" onclick="window._editAssignment(${idx})" title="Clic para editar">${r ? r.alias : 'N/A'}</div>
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <div style="font-size: 0.75rem; color: #6366f1; cursor: pointer;" onclick="window._editAssignment(${idx})" title="Clic para editar">
                                        <i class="fas fa-pen" style="font-size: 0.6rem; margin-right: 3px; opacity: 0.5;"></i>${a.profit_percentage}% + $${(a.bonus_amount || 0).toLocaleString()}
                                    </div>
                                    <i class="fas fa-times" style="color: #ef4444; cursor: pointer; font-size: 0.8rem;" onclick="window._removeAssignment(${idx})"></i>
                                </div>
                            </div>
                        `;
                    }).join('');
                };

                window._editAssignment = (idx) => {
                    const a = currentAssignments[idx];
                    const r = this.routers.find(rt => rt.id == a.router_id);
                    const row = document.getElementById(`assignment-row-${idx}`);
                    if (!row) return;
                    row.innerHTML = `
                        <div style="font-size: 0.8rem; font-weight: 600; flex-shrink: 0;">${r ? r.alias : 'N/A'}</div>
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <input id="edit-pct-${idx}" type="number" step="0.1" value="${a.profit_percentage}" style="width: 55px; height: 28px; font-size: 0.8rem; border: 1px solid #6366f1; border-radius: 4px; padding: 0 6px; text-align: center;" placeholder="%">
                            <span style="font-size: 0.75rem; color: #94a3b8;">%</span>
                            <input id="edit-bonus-${idx}" type="number" value="${a.bonus_amount || 0}" style="width: 70px; height: 28px; font-size: 0.8rem; border: 1px solid #6366f1; border-radius: 4px; padding: 0 6px; text-align: center;" placeholder="$">
                            <i class="fas fa-check-circle" style="color: #10b981; cursor: pointer; font-size: 1rem;" onclick="window._saveAssignment(${idx})" title="Guardar"></i>
                            <i class="fas fa-times" style="color: #ef4444; cursor: pointer; font-size: 0.8rem;" onclick="window._removeAssignment(${idx})" title="Eliminar"></i>
                        </div>
                    `;
                    row.style.borderColor = '#6366f1';
                    row.style.cursor = 'default';
                    document.getElementById(`edit-pct-${idx}`).focus();
                };

                window._saveAssignment = (idx) => {
                    const pct = document.getElementById(`edit-pct-${idx}`).value;
                    const bonus = document.getElementById(`edit-bonus-${idx}`).value;
                    currentAssignments[idx].profit_percentage = parseFloat(pct || 0);
                    currentAssignments[idx].bonus_amount = parseFloat(bonus || 0);
                    renderAssignments();
                    window.showToast('Comisión actualizada', 'success');
                };

                window._removeAssignment = (idx) => {
                    currentAssignments.splice(idx, 1);
                    renderAssignments();
                };

                const btnAdd = document.getElementById('btn-add-assignment');
                btnAdd.onclick = () => {
                    const rId = document.getElementById('new-assignment-router').value;
                    const pct = document.getElementById('new-assignment-pct').value;
                    const bonus = document.getElementById('new-assignment-bonus').value;
                    if (!rId) { window.showToast('Seleccione un nodo', 'error'); return; }
                    if (currentAssignments.some(a => a.router_id == rId)) { window.showToast('Nodo ya asignado', 'warning'); return; }
                    currentAssignments.push({
                        router_id: parseInt(rId),
                        profit_percentage: parseFloat(pct || 0),
                        bonus_amount: parseFloat(bonus || 0)
                    });
                    renderAssignments();
                    // Limpiar inputs
                    document.getElementById('new-assignment-router').value = '';
                    document.getElementById('new-assignment-pct').value = '';
                    document.getElementById('new-assignment-bonus').value = '';
                };

                // CALCULATOR
                const inputPct = document.getElementById('new-assignment-pct');
                const inputBonus = document.getElementById('new-assignment-bonus');
                const selectRouter = document.getElementById('new-assignment-router');
                const getPotential = () => {
                    const r = this.routers.find(rt => rt.id == selectRouter.value);
                    return r ? (r.potential_revenue || 0) : 0;
                };

                inputPct.oninput = () => {
                    const p = getPotential();
                    if (p > 0) inputBonus.value = Math.round((parseFloat(inputPct.value || 0) / 100) * p);
                };
                inputBonus.oninput = () => {
                    const p = getPotential();
                    if (p > 0) inputPct.value = ((parseFloat(inputBonus.value || 0) / p) * 100).toFixed(2);
                };

                roleSelect.onchange = () => {
                    const role = roleSelect.value;
                    const isLegacySpecial = ['tecnico', 'secretaria'].includes(role);
                    const isCollector = role === 'collector';

                    btnTabAssignments.style.display = (isLegacySpecial || isCollector) ? 'flex' : 'none';
                    routerContainer.style.display = isLegacySpecial ? 'block' : 'none';
                    collectorSection.style.display = isCollector ? 'block' : 'none';

                    if (!isLegacySpecial && !isCollector && tabs[1].classList.contains('active')) {
                        tabs[0].click();
                    }
                };

                renderAssignments();
                Swal.getPopup()._collectorAssignments = currentAssignments;
            },
            preConfirm: () => {
                const data = {
                    username: document.getElementById('swal-username').value,
                    password: document.getElementById('swal-password').value,
                    role: document.getElementById('swal-role').value,
                    full_name: document.getElementById('swal-full-name').value,
                    identity_document: document.getElementById('swal-identity-document').value,
                    phone_number: document.getElementById('swal-phone-number').value,
                    email: document.getElementById('swal-email').value,
                    address: document.getElementById('swal-address').value,
                    assigned_zone: document.getElementById('swal-assigned-zone')?.value || '',
                    assigned_router_id: document.getElementById('swal-router')?.value || null,
                    assignments: Swal.getPopup()._collectorAssignments || []
                };

                if (!data.username || (!user && !data.password)) {
                    Swal.showValidationMessage('Usuario y contraseña son obligatorios');
                    return false;
                }

                if (data.role === 'collector' && data.assignments.length === 0) {
                    Swal.showValidationMessage('Asigne al menos un nodo al cobrador');
                    return false;
                }

                if (['tecnico', 'secretaria'].includes(data.role) && !data.assigned_router_id) {
                    Swal.showValidationMessage('Este rol requiere un router asignado');
                    return false;
                }

                return data;
            }
        });

        if (formValues) {
            this.saveUser(userId, formValues);
        }
    }

    async saveUser(userId, data) {
        window.app.showLoading();
        try {
            const url = userId ? `/api/users/${userId}` : '/api/users';
            const method = userId ? 'PUT' : 'POST';

            const result = await this.apiService[method.toLowerCase()](url, data);

            if (result.success) {
                window.showToast(userId ? 'Usuario actualizado' : 'Usuario creado', 'success');
                this.load(); // Recargar lista
            } else {
                window.showToast(result.message || 'Error al guardar', 'error');
            }
        } catch (error) {
            window.showToast('Error de conexión con el servidor', 'error');
        } finally {
            window.app.hideLoading();
        }
    }

    async deleteUser(userId) {
        const { isConfirmed } = await Swal.fire({
            title: '¿Eliminar usuario?',
            text: "Esta acción no se puede deshacer.",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#ef4444',
            confirmButtonText: 'Sí, eliminar',
            cancelButtonText: 'Cancelar'
        });

        if (isConfirmed) {
            window.app.showLoading();
            try {
                const result = await this.apiService.delete(`/api/users/${userId}`);
                if (result.success) {
                    window.showToast('Usuario eliminado', 'success');
                    this.load();
                } else {
                    window.showToast(result.message, 'error');
                }
            } catch (error) {
                window.showToast('Error al eliminar usuario', 'error');
            } finally {
                window.app.hideLoading();
            }
        }
    }

    editUser(userId) {
        this.showUserForm(userId);
    }

    showLoading() {
        if (this.tableBody) {
            this.tableBody.innerHTML = '<tr><td colspan="5" class="text-center"><i class="fas fa-spinner fa-spin"></i> Cargando...</td></tr>';
        }
    }

    hideLoading() {
        // Handled by renderUsers or error states
    }
}
