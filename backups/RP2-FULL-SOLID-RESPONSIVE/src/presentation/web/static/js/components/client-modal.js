/**
 * Client Modal Component
 * Modal profesional para CRUD de clientes con tabs y validación
 */

import toast from './toast.js';
import { ApiService } from '../services/api.service.js';

// Crear instancia de API service
const apiService = new ApiService();

class ClientModal {
    constructor() {
        this.modal = null;
        this.currentClient = null;
        this.routers = [];
        this.init();
    }

    init() {
        // Crear modal
        this.createModal();
        // Cargar routers para el select
        this.loadRouters();
    }

    createModal() {
        const modalHTML = `
            <div id="client-modal" class="modal">
                <div class="modal-content large-modal">
                    <div class="modal-header">
                        <h3 id="modal-title">Nuevo Cliente</h3>
                        <button class="close-btn" onclick="window.clientModal.close()">&times;</button>
                    </div>
                    
                    <div class="modal-body">
                        <!-- Tabs -->
                        <div class="modal-tabs">
                            <button class="tab-btn active" data-tab="personal">
                                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                                    <circle cx="12" cy="7" r="4"/>
                                </svg>
                                Datos Personales
                            </button>
                            <button class="tab-btn" data-tab="service">
                                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                                    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
                                </svg>
                                Servicio
                            </button>
                            <button class="tab-btn" data-tab="billing">
                                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="2" y="5" width="20" height="14" rx="2"/>
                                    <line x1="2" y1="10" x2="22" y2="10"/>
                                </svg>
                                Facturación
                            </button>
                        </div>

                        <!-- Tab: Datos Personales -->
                        <div class="tab-content active" data-tab="personal">
                            <div class="form-grid">
                                <div class="form-group span-2">
                                    <label for="legal_name">Nombre Completo *</label>
                                    <input type="text" id="legal_name" class="form-control" placeholder="Juan Pérez" required>
                                </div>
                                
                                <div class="form-group">
                                    <label for="identity_document">Documento de Identidad</label>
                                    <input type="text" id="identity_document" class="form-control" placeholder="12345678">
                                </div>
                                
                                <div class="form-group">
                                    <label for="phone">Teléfono</label>
                                    <input type="tel" id="phone" class="form-control" placeholder="+58 414 123 4567">
                                </div>
                                
                                <div class="form-group span-2">
                                    <label for="email">Email</label>
                                    <input type="email" id="email" class="form-control" placeholder="cliente@example.com">
                                </div>
                                
                                <div class="form-group span-2">
                                    <label for="address">Dirección</label>
                                    <textarea id="address" class="form-control" rows="2" placeholder="Calle, Sector, Ciudad"></textarea>
                                </div>
                            </div>
                        </div>

                        <!-- Tab: Servicio -->
                        <div class="tab-content" data-tab="service">
                            <div class="form-grid">
                                <div class="form-group">
                                    <label for="router_id">Router *</label>
                                    <select id="router_id" class="form-control" required>
                                        <option value="">Seleccione un router...</option>
                                    </select>
                                </div>
                                
                                <div class="form-group">
                                    <label for="subscriber_code">Código de Suscriptor</label>
                                    <input type="text" id="subscriber_code" class="form-control" placeholder="CLI-001" readonly>
                                    <small class="form-text">Se genera automáticamente</small>
                                </div>
                                
                                <div class="form-group">
                                    <label for="username">Usuario PPPoE *</label>
                                    <input type="text" id="username" class="form-control" placeholder="usuario123" required>
                                </div>
                                
                                <div class="form-group">
                                    <label for="password">Contraseña</label>
                                    <input type="text" id="password" class="form-control" placeholder="********">
                                </div>
                                
                                <div class="form-group">
                                    <label for="ip_address">Dirección IP</label>
                                    <input type="text" id="ip_address" class="form-control" placeholder="10.0.0.100">
                                    <small class="form-text">Dejar vacío para IP dinámica</small>
                                </div>
                                
                                <div class="form-group">
                                    <label for="plan_name">Plan</label>
                                    <input type="text" id="plan_name" class="form-control" placeholder="30 Mbps">
                                </div>
                                
                                <div class="form-group">
                                    <label for="download_speed">Descarga</label>
                                    <input type="text" id="download_speed" class="form-control" placeholder="30M">
                                </div>
                                
                                <div class="form-group">
                                    <label for="upload_speed">Subida</label>
                                    <input type="text" id="upload_speed" class="form-control" placeholder="15M">
                                </div>
                                
                                <div class="form-group">
                                    <label for="service_type">Tipo de Servicio</label>
                                    <select id="service_type" class="form-control">
                                        <option value="pppoe">PPPoE</option>
                                        <option value="simple_queue">Simple Queue</option>
                                        <option value="hotspot">Hotspot</option>
                                    </select>
                                </div>
                                
                                <div class="form-group">
                                    <label for="status">Estado</label>
                                    <select id="status" class="form-control">
                                        <option value="ACTIVE">Activo</option>
                                        <option value="SUSPENDED">Suspendido</option>
                                        <option value="INACTIVE">Inactivo</option>
                                    </select>
                                </div>
                            </div>
                        </div>

                        <!-- Tab: Facturación -->
                        <div class="tab-content" data-tab="billing">
                            <div class="form-grid">
                                <div class="form-group">
                                    <label for="monthly_fee">Cuota Mensual</label>
                                    <div class="input-with-addon">
                                        <span class="addon">$</span>
                                        <input type="number" id="monthly_fee" class="form-control" placeholder="50.00" step="0.01">
                                    </div>
                                </div>
                                
                                <div class="form-group">
                                    <label for="account_balance">Balance de Cuenta</label>
                                    <div class="input-with-addon">
                                        <span class="addon">$</span>
                                        <input type="number" id="account_balance" class="form-control" placeholder="0.00" step="0.01">
                                    </div>
                                    <small class="form-text">Negativo = debe, Positivo = crédito a favor</small>
                                </div>
                                
                                <div class="form-group">
                                    <label for="due_date">Fecha de Vencimiento</label>
                                    <input type="date" id="due_date" class="form-control">
                                </div>
                                
                                <div class="form-group">
                                    <label for="last_payment_date">Último Pago</label>
                                    <input type="date" id="last_payment_date" class="form-control" readonly>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="modal-footer">
                        <button type="button" class="btn-secondary" onclick="window.clientModal.close()">
                            Cancelar
                        </button>
                        <button type="button" class="btn-primary" onclick="window.clientModal.save()">
                            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
                                <polyline points="17 21 17 13 7 13 7 21"/>
                                <polyline points="7 3 7 8 15 8"/>
                            </svg>
                            Guardar Cliente
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Agregar al DOM
        const container = document.createElement('div');
        container.innerHTML = modalHTML;
        document.body.appendChild(container.firstElementChild);

        this.modal = document.getElementById('client-modal');

        // Setup tab switching
        this.setupTabs();
    }

    setupTabs() {
        const tabBtns = this.modal.querySelectorAll('.tab-btn');
        const tabContents = this.modal.querySelectorAll('.tab-content');

        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const tabName = btn.dataset.tab;

                // Update buttons
                tabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // Update content
                tabContents.forEach(c => c.classList.remove('active'));
                this.modal.querySelector(`.tab-content[data-tab="${tabName}"]`).classList.add('active');
            });
        });
    }

    async loadRouters() {
        try {
            const data = await apiService.get('/api/routers');
            this.routers = data;

            // Actualizar select
            const select = this.modal.querySelector('#router_id');
            select.innerHTML = '<option value="">Seleccione un router...</option>';

            this.routers.forEach(router => {
                const option = document.createElement('option');
                option.value = router.id;
                option.textContent = router.alias;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Error loading routers:', error);
            toast.error('Error al cargar routers');
        }
    }

    /**
     * Abre el modal para crear un nuevo cliente
     */
    showCreate() {
        this.currentClient = null;
        this.modal.querySelector('#modal-title').textContent = 'Nuevo Cliente';
        this.resetForm();
        this.modal.classList.add('active');

        // Focus en primer campo
        setTimeout(() => {
            this.modal.querySelector('#legal_name').focus();
        }, 100);
    }

    /**
     * Abre el modal para editar un cliente existente
     * @param {object} client - Datos del cliente
     */
    showEdit(client) {
        this.currentClient = client;
        this.modal.querySelector('#modal-title').textContent = 'Editar Cliente';
        this.loadClientData(client);
        this.modal.classList.add('active');
    }

    /**
     * Carga los datos del cliente en el formulario
     */
    loadClientData(client) {
        // Datos personales
        this.modal.querySelector('#legal_name').value = client.legal_name || '';
        this.modal.querySelector('#identity_document').value = client.identity_document || '';
        this.modal.querySelector('#phone').value = client.phone || '';
        this.modal.querySelector('#email').value = client.email || '';
        this.modal.querySelector('#address').value = client.address || '';

        // Servicio
        this.modal.querySelector('#router_id').value = client.router_id || '';
        this.modal.querySelector('#subscriber_code').value = client.subscriber_code || '';
        this.modal.querySelector('#username').value = client.username || '';
        this.modal.querySelector('#password').value = client.password || '';
        this.modal.querySelector('#ip_address').value = client.ip_address || '';
        this.modal.querySelector('#plan_name').value = client.plan_name || '';
        this.modal.querySelector('#download_speed').value = client.download_speed || '';
        this.modal.querySelector('#upload_speed').value = client.upload_speed || '';
        this.modal.querySelector('#service_type').value = client.service_type || 'pppoe';
        this.modal.querySelector('#status').value = client.status || 'ACTIVE';

        // Facturación
        this.modal.querySelector('#monthly_fee').value = client.monthly_fee || '';
        this.modal.querySelector('#account_balance').value = client.account_balance || '0';
        this.modal.querySelector('#due_date').value = client.due_date ? client.due_date.split('T')[0] : '';
        this.modal.querySelector('#last_payment_date').value = client.last_payment_date ? client.last_payment_date.split('T')[0] : '';
    }

    /**
     * Resetea el formulario
     */
    resetForm() {
        const form = this.modal.querySelector('.modal-body');
        form.querySelectorAll('input, textarea, select').forEach(field => {
            if (field.type === 'checkbox') {
                field.checked = false;
            } else if (field.id !== 'router_id' && field.id !== 'service_type' && field.id !== 'status') {
                field.value = '';
            }
        });

        // Valores por defecto
        this.modal.querySelector('#service_type').value = 'pppoe';
        this.modal.querySelector('#status').value = 'ACTIVE';
        this.modal.querySelector('#account_balance').value = '0';

        // Volver al primer tab
        this.modal.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        this.modal.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        this.modal.querySelector('.tab-btn').classList.add('active');
        this.modal.querySelector('.tab-content').classList.add('active');
    }

    /**
     * Valida el formulario
     */
    validate() {
        const legal_name = this.modal.querySelector('#legal_name').value.trim();
        const router_id = this.modal.querySelector('#router_id').value;
        const username = this.modal.querySelector('#username').value.trim();

        if (!legal_name) {
            toast.warning('Por favor ingrese el nombre del cliente');
            this.modal.querySelector('#legal_name').focus();
            return false;
        }

        if (!router_id) {
            toast.warning('Por favor seleccione un router');
            // Cambiar a tab de servicio
            this.modal.querySelector('.tab-btn[data-tab="service"]').click();
            this.modal.querySelector('#router_id').focus();
            return false;
        }

        if (!username) {
            toast.warning('Por favor ingrese el usuario PPPoE');
            this.modal.querySelector('.tab-btn[data-tab="service"]').click();
            this.modal.querySelector('#username').focus();
            return false;
        }

        return true;
    }

    /**
     * Recopila los datos del formulario
     */
    getFormData() {
        return {
            legal_name: this.modal.querySelector('#legal_name').value.trim(),
            identity_document: this.modal.querySelector('#identity_document').value.trim(),
            phone: this.modal.querySelector('#phone').value.trim(),
            email: this.modal.querySelector('#email').value.trim(),
            address: this.modal.querySelector('#address').value.trim(),
            router_id: parseInt(this.modal.querySelector('#router_id').value),
            subscriber_code: this.modal.querySelector('#subscriber_code').value.trim(),
            username: this.modal.querySelector('#username').value.trim(),
            password: this.modal.querySelector('#password').value.trim(),
            ip_address: this.modal.querySelector('#ip_address').value.trim(),
            plan_name: this.modal.querySelector('#plan_name').value.trim(),
            download_speed: this.modal.querySelector('#download_speed').value.trim(),
            upload_speed: this.modal.querySelector('#upload_speed').value.trim(),
            service_type: this.modal.querySelector('#service_type').value,
            status: this.modal.querySelector('#status').value,
            monthly_fee: parseFloat(this.modal.querySelector('#monthly_fee').value) || 0,
            account_balance: parseFloat(this.modal.querySelector('#account_balance').value) || 0,
            due_date: this.modal.querySelector('#due_date').value || null,
        };
    }

    /**
     * Guarda el cliente
     */
    async save() {
        if (!this.validate()) {
            return;
        }

        const data = this.getFormData();

        try {
            if (this.currentClient) {
                // Actualizar existente
                await apiService.put(`/api/clients/${this.currentClient.id}`, data);
                toast.success('Cliente actualizado correctamente');
            } else {
                // Crear nuevo
                await apiService.post('/api/clients', data);
                toast.success('Cliente creado correctamente');
            }

            this.close();

            // Recargar lista de clientes
            if (window.app && window.app.modules && window.app.modules.clients) {
                window.app.modules.clients.loadClients();
            }
        } catch (error) {
            console.error('Error saving client:', error);
            toast.error(error.error || 'Error al guardar cliente');
        }
    }

    /**
     * Cierra el modal
     */
    close() {
        this.modal.classList.remove('active');
        this.resetForm();
    }
}

// Crear instancia global
window.clientModal = new ClientModal();

export default window.clientModal;
