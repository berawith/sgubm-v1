/**
 * Routers Module - Gestión de Routers MikroTik
 */
export class RoutersModule {
    constructor(api, eventBus, viewManager, modalManager = null) {
        this.api = api;
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.modalManager = modalManager;
        this.routers = [];

        console.log('🌐 Routers Module initialized');
    }

    async load() {
        console.log('🌐 Loading Routers...');

        // Mostrar vista
        this.showView();

        // Cargar routers
        await this.loadRouters();
    }

    formatUptime(uptime) {
        if (!uptime || uptime === 'N/A') return 'N/A';
        // Traducir unidades crudas de MikroTik a versión corta: 2w5d -> 2sem 5d
        return uptime
            .replace(/(\d+)w/g, '$1sem ')
            .replace(/(\d+)d/g, '$1d ')
            .replace(/(\d+)h/g, '$1h ')
            .replace(/(\d+)m/g, '$1m ')
            .replace(/(\d+)s/g, '$1s ')
            .trim();
    }

    showView() {
        // Delegar visualización a ViewManager
        this.viewManager.showMainView('routers');
    }

    async loadRouters() {
        try {
            this.routers = await this.api.get('/api/routers');
            this.renderRouters();

            // Iniciar monitoreo en vivo (Keep-Alive)
            this.startLiveMonitor();

        } catch (error) {
            console.error('Error loading routers:', error);
            this.routers = [];
            this.renderRouters();
        }
    }

    startLiveMonitor() {
        if (this.monitorInterval) clearInterval(this.monitorInterval);

        // Polling cada 2 segundos (Casi tiempo real)
        this.monitorInterval = setInterval(async () => {
            // Detener si no estamos viendo routers
            const view = document.getElementById('routers-view');
            if (!view || !view.classList.contains('active')) return;

            try {
                // Llamar al endpoint optimizado de monitoreo
                const liveData = await this.api.get('/api/routers/monitor');
                this.updateRouterCards(liveData);
            } catch (e) {
                // Silencioso para no saturar consola en errores de red
            }
        }, 2000);
    }

    updateRouterCards(liveData) {
        liveData.forEach(data => {
            // Encontrar la tarjeta correspondiente
            // Buscamos el botón de sync que tiene el ID más fiable
            const syncBtn = document.querySelector(`button[onclick="app.modules.routers.syncRouter(${data.id})"]`);
            if (!syncBtn) return;

            const card = syncBtn.closest('.router-card');
            if (!card) return;

            // Actualizar estado visual (borde/punto)
            const statusDot = card.querySelector('.status-dot-mini');
            const statusBar = card.querySelector('.card-status-bar');

            card.classList.remove('online', 'offline');
            card.classList.add(data.status);

            // Actualizar valores numéricos
            if (data.status === 'online') {
                // CPU
                const cpuVal = card.querySelector('.stat-group:first-child .stat-value');
                const cpuBar = card.querySelector('.stat-group:first-child .bar');
                if (cpuVal) cpuVal.textContent = `${data.cpu_usage}%`;
                if (cpuBar) {
                    cpuBar.style.width = `${data.cpu_usage}%`;
                    cpuBar.style.backgroundColor = data.cpu_usage > 80 ? '#ef4444' : data.cpu_usage > 50 ? '#f59e0b' : '#10b981';
                }

                // RAM
                const ramVal = card.querySelector('.stat-group:nth-child(2) .stat-value');
                const ramBar = card.querySelector('.stat-group:nth-child(2) .bar');
                if (ramVal) ramVal.textContent = `${data.memory_usage}%`;
                if (ramBar) ramBar.style.width = `${data.memory_usage}%`;

                // Clientes
                const clientsVal = card.querySelector('.meta-item:first-child .meta-value');
                if (clientsVal) clientsVal.textContent = data.clients_connected;

                // Uptime
                const uptimeVal = card.querySelector('.uptime-value');
                if (uptimeVal && data.uptime) {
                    uptimeVal.textContent = this.formatUptime(data.uptime);
                }
            }
        });
    }

    renderRouters() {
        const grid = document.getElementById('routers-grid');
        if (!grid) return;

        if (this.routers.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <rect x="2" y="2" width="20" height="8" rx="2"/>
                            <rect x="2" y="14" width="20" height="8" rx="2"/>
                            <line x1="6" y1="6" x2="6.01" y2="6"/>
                            <line x1="6" y1="18" x2="6.01" y2="18"/>
                        </svg>
                    </div>
                    <h3>No hay routers configurados</h3>
                    <p>Agrega tu primer router MikroTik para comenzar a gestionar tu red.</p>
                    <button onclick="app.modules.routers.showCreateModal()" class="btn-primary glow-effect">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
                        Agregar Router
                    </button>
                </div>
            `;
            return;
        }

        grid.innerHTML = this.routers.map(router => {
            // Calcular colores de estado
            const statusClass = router.status ? router.status.toLowerCase() : 'offline';
            const isOnline = statusClass === 'online';

            // Formatear uptime
            let uptimeDisplay = router.uptime || 'N/A';

            // Calcular uso de recursos para barras de progreso
            const cpu = parseInt(router.cpu_usage || 0);
            const ram = parseInt(router.memory_usage || 0);
            const cpuColor = cpu > 80 ? '#ef4444' : cpu > 50 ? '#f59e0b' : '#10b981';
            const ramColor = ram > 80 ? '#ef4444' : ram > 50 ? '#f59e0b' : '#3b82f6';

            return `
            <div class="router-card ${statusClass}">
                <div class="card-status-bar"></div>
                <div class="router-main">
                    <div class="router-header">
                        <div class="router-identity">
                            <div class="router-name-row">
                                <span class="status-dot-mini"></span>
                                <h3 class="router-alias" title="${router.alias}">${router.alias || 'Router Sin Nombre'}</h3>
                            </div>
                            <span class="router-ip">${router.host_address}</span>
                        </div>
                        <div class="router-actions">
                            <button onclick="app.modules.routers.syncRouter(${router.id})" class="action-btn minimal" title="Sincronizar">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3"/></svg>
                            </button>
                            <button onclick="app.modules.routers.showEditModal(${router.id})" class="action-btn minimal" title="Configurar">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                            </button>
                            <button onclick="app.modules.routers.deleteRouter(${router.id})" class="action-btn minimal delete" title="Eliminar">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                            </button>
                        </div>
                    </div>
                
                    <div class="router-stats-minimal">
                        <div class="stat-group">
                            <div class="stat-info">
                                <span class="stat-label">CPU</span>
                                <span class="stat-value">${cpu}%</span>
                            </div>
                            <div class="progress-bar-minimal">
                                <div class="bar" style="width: ${cpu}%; background-color: ${cpuColor}"></div>
                            </div>
                        </div>
                        <div class="stat-group">
                            <div class="stat-info">
                                <span class="stat-label">RAM</span>
                                <span class="stat-value">${ram}%</span>
                            </div>
                            <div class="progress-bar-minimal">
                                <div class="bar" style="width: ${ram}%; background-color: ${ramColor}"></div>
                            </div>
                        </div>
                    </div>

                    <div class="router-meta-grid">
                        <div class="meta-item">
                            <span class="meta-label">Clientes</span>
                            <span class="meta-value">${router.clients_connected || 0}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Uptime</span>
                            <span class="meta-value uptime-value">${this.formatUptime(uptimeDisplay)}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Zona</span>
                            <span class="meta-value">${router.zone || '-'}</span>
                        </div>
                    </div>
                </div>
            </div>
            `;
        }).join('');
    }

    async syncRouter(routerId) {
        const btn = document.querySelector(`button[onclick="app.modules.routers.syncRouter(${routerId})"]`);
        const originalContent = btn ? btn.innerHTML : '';

        if (btn) {
            btn.innerHTML = '<div class="spinner-mini"></div>';
            btn.disabled = true;
            btn.style.opacity = '0.7';
        }

        try {
            console.log('Syncing router (discovery phase)', routerId);
            // Paso 1: Descubrir candidatos sin provisionar
            const discoveryResult = await this.api.post(`/api/routers/${routerId}/sync`, { confirm: false });

            if (discoveryResult.success) {
                // Si requiere confirmación, mostrar diálogo
                // Si requiere confirmación, abrir Smart Import Modal
                if (discoveryResult.requires_confirmation) {
                    const candidatesToAdd = discoveryResult.candidates_to_add || 0;

                    // Guardar ID y datos para el proceso de confirmación
                    this.pendingSyncRouterId = routerId;
                    this.pendingSyncCandidates = candidatesToAdd;

                    // Actualizar UI del Modal
                    const summaryText = document.getElementById('import-summary-text');
                    if (summaryText) {
                        summaryText.innerHTML = `Se han detectado <strong style="color: #0f172a;">${candidatesToAdd} clientes nuevos</strong>.`;
                    }

                    // Cargar planes
                    this.loadPlansForImport();

                    // Abrir Modal
                    if (this.modalManager) {
                        this.modalManager.open('import-clients-modal');
                    } else {
                        // Fallback por si acaso
                        document.getElementById('import-clients-modal').classList.add('active');
                    }

                    // Resetear formulario
                    document.getElementById('import-clients-form').reset();
                    this.selectImportStrategy('clean'); // Default

                } else {
                    // No hay candidatos para aprovisionar
                    alert('Sincronización completada. No se encontraron clientes nuevos para auto-provisionar.');
                    await this.loadRouters();
                }
            } else {
                alert(`Error: ${discoveryResult.message}`);
            }
        } catch (error) {
            console.error('Error syncing router:', error);
            // Intentar extraer mensaje del backend si existe
            let msg = error.message;
            if (error.response && error.response.data && error.response.data.message) {
                msg = error.response.data.message;
            }
            alert(`Fallo en sincronización: ${msg}\n\nVerifica que la IP sea accesible desde este servidor.`);
        } finally {
            if (btn) {
                btn.innerHTML = originalContent;
                btn.disabled = false;
                btn.style.opacity = '1';
            }
        }
    }

    switchTab(tabName) {
        const modal = document.getElementById('router-form-modal');
        if (!modal) return;

        // Buttons
        modal.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        if (tabName === 'connection') document.getElementById('tab-btn-r-conn').classList.add('active');
        if (tabName === 'billing') document.getElementById('tab-btn-r-bill').classList.add('active');
        if (tabName === 'management') document.getElementById('tab-btn-r-mgmt').classList.add('active');

        // Content
        modal.querySelectorAll('.tab-content-router').forEach(c => c.style.display = 'none');
        document.getElementById(`tab-router-${tabName}`).style.display = 'block';
    }

    showCreateModal() {
        if (this.modalManager) {
            this.modalManager.open('router');
        } else {
            this.showNewRouterModal();
        }
    }

    showEditModal(routerId) {
        const router = this.routers.find(r => r.id === routerId);
        if (!router) return;

        if (this.modalManager) {
            this.modalManager.open('router', { router });
        } else {
            this.showEditRouter(router);
        }
    }

    async showEditRouter(router) {
        const modal = document.getElementById('router-form-modal');
        if (!modal) return;

        document.getElementById('router-id').value = router.id || '';
        document.getElementById('router-alias').value = router.alias || '';
        document.getElementById('router-host').value = router.host_address || '';
        document.getElementById('router-user').value = router.api_username || '';
        document.getElementById('router-pass').value = router.api_password || '';
        document.getElementById('router-port').value = router.api_port || 8728;
        document.getElementById('router-zone').value = router.zone || '';
        document.getElementById('router-billing-day').value = router.billing_day || 1;
        document.getElementById('router-grace-period').value = router.grace_period || 5;
        document.getElementById('router-cut-day').value = router.cut_day || 10;

        // Gestión
        document.getElementById('router-mgmt-method').value = router.management_method || 'mixed';
        document.getElementById('router-pppoe-ranges').value = router.pppoe_ranges || '';
        document.getElementById('router-dhcp-ranges').value = router.dhcp_ranges || '';

        const titleEl = document.getElementById('router-modal-title');
        if (titleEl) titleEl.textContent = 'Configurar Router';

        this.switchTab('connection');

        // Cargar Planes asociados
        this.loadRouterPlans(router.id);

        // Mostrar el modal directamente
        modal.classList.add('active');
    }

    showNewRouterModal() {
        const modal = document.getElementById('router-form-modal');
        if (!modal) return;

        document.getElementById('router-id').value = '';
        document.getElementById('router-alias').value = '';
        document.getElementById('router-host').value = '';
        document.getElementById('router-user').value = '';
        document.getElementById('router-pass').value = '';
        document.getElementById('router-port').value = 8728;
        document.getElementById('router-zone').value = '';
        document.getElementById('router-billing-day').value = 1;
        document.getElementById('router-grace-period').value = 5;
        document.getElementById('router-cut-day').value = 10;

        // Gestión Reset
        document.getElementById('router-mgmt-method').value = 'mixed';
        document.getElementById('router-pppoe-ranges').value = '';
        document.getElementById('router-dhcp-ranges').value = '';
        document.getElementById('router-plans-container').innerHTML = '<p style="text-align:center; margin: 10px 0; font-style:italic;">Guarde el router primero para gestionar sus planes.</p>';

        const titleEl = document.getElementById('router-modal-title');
        if (titleEl) titleEl.textContent = 'Nuevo Router';

        this.switchTab('connection');
        modal.classList.add('active');
    }

    async loadRouterPlans(routerId) {
        const container = document.getElementById('router-plans-container');
        if (!container) return;

        container.innerHTML = '<div class="spinner-mini" style="margin: 10px auto;"></div>';

        try {
            // Fetch plans filtered by router (Assuming API supports filtering, or fetch all and filter client-side)
            // Since we don't have a specific endpoint yet, we'll fetch all and filter in JS for now or ask backend
            // Let's assume we can fetch all plans first. Ideally backend should support /api/routers/:id/plans
            // For now, let's use the generic /api/plans and filter.
            const allPlans = await this.api.get('/api/plans');
            const routerPlans = allPlans.filter(p => p.router_id == routerId);

            if (routerPlans.length === 0) {
                container.innerHTML = '<p style="text-align:center; margin: 10px 0; font-style:italic;">No hay planes asociados a este router.</p>';
                return;
            }

            let html = '<ul style="list-style:none; padding:0; margin:0;">';
            routerPlans.forEach(plan => {
                html += `
                <li style="display:flex; justify-content:space-between; align-items:center; padding: 8px 0; border-bottom: 1px solid #f1f5f9;">
                    <div>
                        <strong style="color:#0f172a;">${plan.name}</strong>
                        <span style="font-size:0.75rem; color:#64748b; margin-left: 8px;">${plan.download_speed / 1000}M / ${plan.upload_speed / 1000}M</span>
                    </div>
                    <div>
                         <span class="badge" style="font-size:0.7em; background:#e0f2fe; color:#0369a1;">${plan.service_type || 'N/A'}</span>
                    </div>
                </li>`;
            });
            html += '</ul>';
            container.innerHTML = html;

        } catch (e) {
            console.error('Error loading plans for router:', e);
            if (container) container.innerHTML = '<p style="color:red; text-align:center;">Error cargando planes.</p>';
        }
    }

    // --- Smart Import Logic ---

    async loadPlansForImport() {
        const select = document.getElementById('import-default-plan');
        if (!select) return;

        select.innerHTML = '<option value="">Cargando planes...</option>';

        try {
            const plans = await this.api.get('/api/plans');
            let html = '<option value="">Detectar Automáticamente (Recomendado)</option>';
            plans.forEach(p => {
                html += `<option value="${p.id}">${p.name} (${(p.download_speed / 1000).toFixed(0)}M)</option>`;
            });
            select.innerHTML = html;
        } catch (e) {
            console.error('Error loading plans:', e);
            select.innerHTML = '<option value="">Error cargando planes</option>';
        }
    }

    selectImportStrategy(strategy) {
        // Visual Update for Segmented Control (New Compact UI)
        document.querySelectorAll('.switch-option').forEach(opt => opt.classList.remove('active'));
        // Also support legacy if referenced elsewhere (unlikely but safe)
        document.querySelectorAll('.radio-card-premium').forEach(card => card.classList.remove('selected'));

        const cleanOption = document.querySelector('label[onclick*="selectImportStrategy(\'clean\')"]');
        const debtOption = document.querySelector('label[onclick*="selectImportStrategy(\'debt\')"]');

        const cleanOptions = document.getElementById('clean-options');
        const debtOptions = document.getElementById('debt-options');

        if (strategy === 'clean') {
            if (cleanOption) {
                cleanOption.classList.add('active'); // New UI
                cleanOption.classList.add('selected'); // Legacy UI fallback
            }
            const cleanInput = document.querySelector('input[value="clean"]');
            if (cleanInput) cleanInput.checked = true;

            if (cleanOptions) cleanOptions.style.display = 'block';
            if (debtOptions) debtOptions.style.display = 'none';
        } else {
            if (debtOption) {
                debtOption.classList.add('active'); // New UI
                debtOption.classList.add('selected'); // Legacy UI fallback
            }
            const debtInput = document.querySelector('input[value="debt"]');
            if (debtInput) debtInput.checked = true;

            if (cleanOptions) cleanOptions.style.display = 'none';
            if (debtOptions) debtOptions.style.display = 'block';
        }
    }

    updateCleanOptionHint(selectElement) {
        const hintElement = document.getElementById('clean-option-hint');
        if (!hintElement) return;

        const hints = {
            'prorate': 'Se cobrará solo los días restantes del mes actual. La factura se generará al corte.',
            'full': 'Se cobrará el valor total del plan inmediatamente. Factura generada al instante.',
            'grace': 'El cliente disfrutará del servicio sin costo hasta el próximo ciclo de facturación.'
        };

        // Update text
        hintElement.textContent = hints[selectElement.value] || 'El cliente iniciará sin deuda vencida en el sistema.';

        // Add subtle highlight effect
        hintElement.style.color = '#4f46e5';
        setTimeout(() => hintElement.style.color = '', 300);
    }

    async confirmImport() {
        if (!this.pendingSyncRouterId) return;

        const routerId = this.pendingSyncRouterId;
        const btn = document.querySelector('#import-clients-modal .btn-premium');
        if (btn) {
            btn.innerHTML = '<div class="spinner-mini"></div> Importando...';
            btn.disabled = true;
        }

        // Collect Options
        const strategy = document.querySelector('input[name="import_strategy"]:checked').value;
        const options = {
            confirm: true,
            import_strategy: strategy,
            default_plan_id: document.getElementById('import-default-plan').value || null
        };

        if (strategy === 'clean') {
            options.clean_type = document.getElementById('import-clean-type').value; // prorate, full, grace
        } else {
            const debtAmount = document.getElementById('import-initial-debt').value;
            if (!debtAmount) {
                alert('Por favor ingrese un monto de deuda válido.');
                if (btn) {
                    btn.innerHTML = '<i class="fas fa-file-import" style="margin-right: 8px;"></i> Importar Clientes';
                    btn.disabled = false;
                }
                return;
            }
            options.initial_debt = this.parseCurrencyValue(debtAmount);
        }

        try {
            console.log('Confirming import with options:', options);
            const provisionResult = await this.api.post(`/api/routers/${routerId}/sync`, options);

            if (provisionResult.success) {
                // Close modal
                if (this.modalManager) {
                    this.modalManager.closeAll(); // Or specifically close import modal
                } else {
                    document.getElementById('import-clients-modal').classList.remove('active');
                }

                alert(`✅ Importación Exitosa\n\nSe han registrado ${provisionResult.details.provisioned} clientes nuevos bajo el esquema seleccionado.`);
                await this.loadRouters();
            } else {
                alert(`Error en importación: ${provisionResult.message}`);
            }
        } catch (error) {
            console.error('Import error:', error);
            alert('Error al procesar la importación: ' + (error.message || 'Error desconocido'));
        } finally {
            if (btn) {
                btn.innerHTML = '<i class="fas fa-file-import" style="margin-right: 8px;"></i> Importar Clientes';
                btn.disabled = false;
            }
            this.pendingSyncRouterId = null;
        }
    }

    createPlanForRouter() {
        const routerId = document.getElementById('router-id').value;
        if (!routerId) {
            alert('Debe guardar el router antes de crear planes asociados.');
            return;
        }
        // Llamar al modulo de planes
        if (app.modules.plans && app.modules.plans.openPlanModal) {
            // Close current modal temporarily or keep it open? Modals stack might be tricky.
            // Usually we might want to close router modal.
            // document.getElementById('router-form-modal').classList.remove('active'); 
            // Reuse openPlanModal signature if modified to accept routerID
            // I need to modify PlansManagerModule.openPlanModal to accept a pre-filled router ID or handled via plan object.
            // Let's pass a partial plan object
            app.modules.plans.openPlanModal({ router_id: routerId });
        }
    }

    async saveRouter() {
        const id = document.getElementById('router-id').value;
        const data = {
            alias: document.getElementById('router-alias').value,
            host_address: document.getElementById('router-host').value,
            api_username: document.getElementById('router-user').value,
            api_password: document.getElementById('router-pass').value,
            api_port: parseInt(document.getElementById('router-port').value || 8728),
            zone: document.getElementById('router-zone').value,
            billing_day: parseInt(document.getElementById('router-billing-day').value || 1),
            grace_period: parseInt(document.getElementById('router-grace-period').value || 5),
            cut_day: parseInt(document.getElementById('router-cut-day').value || 10),

            // Gestión
            management_method: document.getElementById('router-mgmt-method').value,
            pppoe_ranges: document.getElementById('router-pppoe-ranges').value,
            dhcp_ranges: document.getElementById('router-dhcp-ranges').value
        };

        if (!data.alias || !data.host_address || !data.api_username) {
            alert('Por favor complete los campos obligatorios (*)');
            return;
        }

        try {
            if (id) {
                // Update
                await this.api.put(`/api/routers/${id}`, data);
                alert('Router actualizado correctamente');
            } else {
                // Create
                await this.api.post('/api/routers', data);
                alert('Router creado correctamente');
            }

            if (this.modalManager) {
                this.modalManager.close('router');
            } else {
                document.getElementById('router-form-modal').classList.remove('active');
            }

            await this.loadRouters();

        } catch (error) {
            console.error('Error saving router:', error);
            alert('Error al guardar el router: ' + error.message);
        }
    }

    async deleteRouter(routerId) {
        if (!confirm('¿Está seguro de que desea eliminar este router? Esta acción no se puede deshacer.')) {
            return;
        }

        const btn = document.querySelector(`button[onclick="app.modules.routers.deleteRouter(${routerId})"]`);
        const originalContent = btn ? btn.innerHTML : '';

        if (btn) {
            btn.innerHTML = '<div class="spinner-mini"></div>';
            btn.disabled = true;
            btn.style.opacity = '0.7';
        }

        try {
            await this.api.delete(`/api/routers/${routerId}`);
            alert('Router eliminado correctamente');
            await this.loadRouters();
        } catch (error) {
            console.error('Error deleting router:', error);

            let msg = error.message;
            if (error.response && error.response.data && error.response.data.message) {
                msg = error.response.data.message;
            }
            alert(`Error al eliminar router: ${msg}`);

            if (btn) {
                btn.innerHTML = originalContent;
                btn.disabled = false;
                btn.style.opacity = '1';
            }
        }
    }

    /**
     * Formats an input value with thousands separators while typing
     */
    formatCurrencyInput(input) {
        if (!input) return;
        let value = input.value.replace(/[^\d.]/g, '');
        const parts = value.split('.');
        if (parts.length > 2) value = parts[0] + '.' + parts.slice(1).join('');
        if (value === '') { input.value = ''; return; }
        let integerPart = parts[0];
        let decimalPart = parts.length > 1 ? '.' + parts[1].substring(0, 2) : '';
        integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        input.value = integerPart + decimalPart;
    }

    /**
     * Parses a formatted currency string back to a float
     */
    parseCurrencyValue(value) {
        if (typeof value !== 'string') return parseFloat(value) || 0;
        return parseFloat(value.replace(/,/g, '')) || 0;
    }
}
