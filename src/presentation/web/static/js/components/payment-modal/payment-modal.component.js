import { BaseModal } from '../shared/base-modal.component.js';

/**
 * PaymentModal Component
 * Modal independiente para registro y edición de pagos
 */
export class PaymentModal extends BaseModal {
    constructor(api, eventBus) {
        super('payment-modal', api, eventBus);

        // Estado interno
        this.selectedClient = null;
        this.clients = [];
        this.currentMode = 'create'; // 'create' o 'edit'
        this.currentPaymentId = null;
        this.searchTimeout = null;
        this.liveClockInterval = null;

        // Tasas de cambio (ERP)
        this.rates = {
            'USD_COP': 4000,
            'USD_VES': 36.5,
            'USD_VES_BCV': 36.5,
            'USD_VES_COM': 40.0,
            'COP_VES': 0.009
        };

        this.partCount = 1;
    }

    /**
     * Inicializa componentes y carga recursos
     */
    async init() {
        if (this.isInitialized) {
            console.warn('⚠️ PaymentModal already initialized, skipping re-init.');
            return;
        }

        console.log('💳 PaymentModal: Initializing component...');
        await this.loadResources(
            '/static/js/components/payment-modal/payment-modal.template.html'
        );
        this.populateTimeSelectors();
        // this.attachBaseEvents(); // Called internally by loadResources
        this.attachEvents();

        // Cargar tasas iniciales
        await this.fetchExchangeRates();
        console.log('✅ Payment Modal initialized');
    }

    /**
     * Obtiene las tasas de cambio vigentes del backend
     */
    async fetchExchangeRates() {
        try {
            const data = await this.api.get('/api/payments/rates');
            if (data) {
                this.rates = {
                    'USD_COP': data.USD_COP || 4000,
                    'USD_VES': data.USD_VES || 36.5,
                    'USD_VES_BCV': data.USD_VES_BCV || 36.5,
                    'USD_VES_COM': data.USD_VES_COM || 40.0,
                    'COP_VES': data.COP_VES || 0.009
                };

                // Actualizar labels en el selector si existen
                const bcvLabel = this.container.querySelector('#val-rate-bcv');
                const comLabel = this.container.querySelector('#val-rate-com');
                if (bcvLabel) bcvLabel.textContent = this.rates.USD_VES_BCV.toFixed(2);
                if (comLabel) comLabel.textContent = this.rates.USD_VES_COM.toFixed(2);
            }
        } catch (error) {
            console.error('❌ Error fetching rates in PaymentModal:', error);
        }
    }

    /**
     * Puebla el selector de minutos con 00-59
     */
    /**
     * Puebla el selector de minutos con 00-59
     * DEPRECADO: Se usa HTML estático para garantizar estabilidad.
     */
    populateTimeSelectors() {
        // NO-OP: HTML estático maneja las opciones.
    }

    /**
     * Resetea el formulario a su estado inicial
     */
    resetForm() {
        console.log('🔄 [PaymentModal] resetForm called');
        const form = this.modalElement.querySelector('form');
        if (form) form.reset();

        // Limpiar estado de edición
        this.editMode = false;
        this.paymentId = null;

        // Limpiar cliente seleccionado
        this.selectedClient = null;
        this.clearSelectedClient();

        // Configurar fecha por defecto
        if (typeof this.setDefaultDate === 'function') {
            this.setDefaultDate();
        }

        // Limpiar partes dinámicas y dejar solo una
        const container = this.modalElement.querySelector('#payment-parts-container');
        if (container) {
            console.log('🧹 Clearing payment-parts-container');
            container.innerHTML = '';
            this.partCount = 0;
            this.addPaymentPart(); // Agrega la primera fila por defecto
        }

        // Ocultar audit box si existe
        const auditBox = this.modalElement.querySelector('#payment-audit-box');
        if (auditBox) auditBox.style.display = 'none';

        // Resetear texto del botón de envío
        const submitText = this.modalElement.querySelector('#payment-submit-text');
        if (submitText) submitText.textContent = 'Confirmar Pago';

        // Resetear resumen ERP
        try {
            if (typeof this.calculateERP === 'function') {
                this.calculateERP();
            }
        } catch (e) {
            console.error('❌ Error in resetForm.calculateERP:', e);
        }
    }

    /**
     * Adjunta event listeners (sobrescribe attachEvents de BaseModal si es necesario, 
     * pero BaseModal ya llama a attachBaseEvents)
     */
    /**
     * Adjunta event listeners (sobrescribe attachEvents de BaseModal si es necesario, 
     * pero BaseModal ya llama a attachBaseEvents)
     */
    attachEvents() {
        if (!this.modalElement) return;
        if (this._eventsAttached) {
            console.warn('⚠️ PaymentModal events already attached, skipping.');
            return;
        }

        console.log('🔗 [PaymentModal] attachEvents called');

        // Búsqueda de cliente
        const searchBtn = this.modalElement.querySelector('[data-action="search"]');
        const searchInput = this.modalElement.querySelector('#payment-client-query');

        if (searchBtn) {
            this.addEventListener(searchBtn, 'click', () => {
                this.searchClients(searchInput.value);
            });
        }

        if (searchInput) {
            // Búsqueda en tiempo real
            this.addEventListener(searchInput, 'input', (e) => {
                clearTimeout(this.searchTimeout);
                const query = e.target.value;

                if (query.length >= 2) {
                    this.searchTimeout = setTimeout(() => {
                        this.searchClients(query);
                    }, 300);
                } else {
                    this.clearSearchResults();
                }
            });

            // Búsqueda con ENTER
            this.addEventListener(searchInput, 'keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.searchClients(searchInput.value);
                }
            });
        }

        // Event listeners para acciones de cliente seleccionado
        const historyBtn = this.modalElement.querySelector('[data-action="show-history"]');
        if (historyBtn) {
            this.addEventListener(historyBtn, 'click', () => this.showClientHistory());
        }

        const clearClientBtn = this.modalElement.querySelector('[data-action="clear-client"]');
        if (clearClientBtn) {
            this.addEventListener(clearClientBtn, 'click', () => this.clearSelectedClient());
        }

        // NUEVO: Listener para el cuadro de prorrateo
        const debtDisplay = this.container.querySelector('#payment-client-debt-display');
        if (debtDisplay) {
            this.addEventListener(debtDisplay, 'click', (e) => {
                const prorateBox = e.target.closest('#prorate-suggest-box');
                if (prorateBox) {
                    this.toggleProrate(prorateBox);
                }
            });
        }

        // Event Delegation para partes de pago
        const partsContainer = this.modalElement.querySelector('#payment-parts-container');
        if (partsContainer) {
            // Escuchar cambios en montos, monedas, métodos
            this.addEventListener(partsContainer, 'input', (e) => {
                if (e.target.classList.contains('part-amount')) {
                    this.formatCurrencyInput(e.target);
                    this.calculateERP();
                }
            });

            this.addEventListener(partsContainer, 'change', (e) => {
                if (e.target.classList.contains('part-currency')) {
                    this.handleCurrencyChange(e.target);
                }
                if (e.target.classList.contains('part-method') || e.target.classList.contains('part-currency')) {
                    this.calculateERP();
                }
            });

            // Botón eliminar parte y Botón Conversión Mágica
            this.addEventListener(partsContainer, 'click', (e) => {
                const removeBtn = e.target.closest('.remove-part');
                if (removeBtn) {
                    const row = removeBtn.closest('.payment-part-row');
                    if (row) {
                        row.style.animation = 'fadeOut 0.2s ease-in forwards';
                        setTimeout(() => {
                            row.remove();
                            this.calculateERP();
                        }, 200);
                    }
                }

                const magicBtn = e.target.closest('.btn-magic-convert');
                if (magicBtn) {
                    const row = magicBtn.closest('.payment-part-row');
                    if (row) {
                        this.fillRemainingBalance(row);
                    }
                }

                // Toggles de tasa VES
                const rateBtn = e.target.closest('.rate-btn');
                if (rateBtn) {
                    this.handleVesRateToggle(rateBtn);
                }
            });
        }

        // Botón agregar parte
        const addPartBtn = this.modalElement.querySelector('#btn-add-payment-part');
        if (addPartBtn) {
            this.addEventListener(addPartBtn, 'click', () => this.addPaymentPart());
        }

        // NUEVO: Manejo de tarjetas de tasa VES (Legacy / Global)
        const rateCards = this.container.querySelectorAll('.rate-type-card');
        rateCards.forEach(card => {
            this.addEventListener(card, 'click', () => {
                rateCards.forEach(c => {
                    c.classList.remove('active');
                    c.style.borderColor = '#e2e8f0';
                    c.style.background = 'white';
                    c.querySelector('div:first-child').style.color = '#64748b';
                });

                card.classList.add('active');
                card.style.borderColor = 'var(--primary)';
                card.style.background = '#f5f3ff';
                card.querySelector('div:first-child').style.color = '#6d28d9';

                const hiddenType = this.container.querySelector('#selected-ves-rate-type');
                if (hiddenType) hiddenType.value = card.dataset.rate;

                this.displayClientDebt();
                this.calculateERP();
            });
        });

        // NUEVO: Botón de actualización rápida de tasas
        const btnQuickUpdate = this.container.querySelector('#btn-update-rates-quick');
        if (btnQuickUpdate) {
            this.addEventListener(btnQuickUpdate, 'click', async () => {
                const newCOP = prompt('Tasa COP -> USD (ej. 3700 o 3650):', this.rates.USD_COP);
                const newBCV = prompt('Tasa USD -> VES BCV (Oficial):', this.rates.USD_VES_BCV);
                const newCOM = prompt('Tasa USD -> VES COMER (Paralela):', this.rates.USD_VES_COM);

                if (newCOP || newBCV || newCOM) {
                    const updateData = {};
                    if (newCOP) updateData.USD_COP = parseFloat(newCOP);
                    if (newBCV) updateData.USD_VES_BCV = parseFloat(newBCV);
                    if (newCOM) updateData.USD_VES_COM = parseFloat(newCOM);

                    try {
                        this.showLoading();
                        await this.api.post('/api/payments/rates', updateData);
                        await this.fetchExchangeRates(); // Recargar
                        this.displayClientDebt(); // Refrescar deuda
                        this.calculateERP(); // Refrescar totales
                        this.showSuccess('Tasas actualizadas para esta sesión');
                    } catch (error) {
                        this.showError('Error actualizando tasas');
                    } finally {
                        this.hideLoading();
                    }
                }
            });
        }

        this._eventsAttached = true;
        console.log('✅ Payment Modal events attached');
    }

    /**
     * Hook llamado al cerrar el modal (BaseModal.close)
     */
    onClose() {
        super.onClose();
        this._eventsAttached = false;
        this.stopLiveClock();
        this.resetForm();

        console.log('🔒 [PaymentModal] onClose - Flag reset & state cleared');
    }

    /**
     * Abre el modal en modo crear o editar
     */
    async open(data = {}) {
        await this._initPromise;

        this.editMode = !!data.payment;
        this.paymentId = data.payment?.id || null;

        console.log('📂 [PaymentModal] open()', { editMode: this.editMode, paymentId: this.paymentId });

        // Actualizar título y botón según rol
        const title = this.modalElement.querySelector('#payment-modal-title');
        const submitBtn = this.modalElement.querySelector('#payment-submit-btn');
        const isCollector = window.app?.authService?.getUser()?.role === 'collector';

        if (title) {
            title.textContent = this.editMode ? 'Editar Pago' : (isCollector ? 'Reportar Pago' : 'Registrar Nuevo Pago');
        }
        if (submitBtn) {
            submitBtn.textContent = 'Procesando...'; // Default loading text, handled by template/CSS usually but let's rest assure
            // Assuming the template has an icon inside the button, we better replace innerHTML entirely or just text
            submitBtn.innerHTML = isCollector
                ? '<i class="fas fa-paper-plane mr-2"></i> Reportar Pago'
                : '<i class="fas fa-check-circle mr-2"></i> Registrar Pago';
        }

        // Resetear formulario si es nuevo (siempre que no estemos en editMode)
        if (!this.editMode) {
            this.resetForm();
        } else {
            // Si estamos en editMode, al menos limpiar el contenedor antes de populate
            const container = this.modalElement.querySelector('#payment-parts-container');
            if (container) {
                container.innerHTML = '';
            }
            this.partCount = 0;
        }

        // IMPORTANTE: NO forzar re-adjuntar eventos aquí. 
        // attachEvents() ya tiene un guard interno (this._eventsAttached).
        this.attachEvents();

        // Si hay cliente preseleccionado (después del reset para no perderlo)
        if (data.clientId) {
            await this.selectClientById(data.clientId);
        }

        // Si estamos editando, poblar formulario
        if (this.editMode && data.payment) {
            await this.populatePaymentData(data.payment);
        }

        // Asegurar que los selectores de tiempo estén poblados correctamente
        this.populateTimeSelectors();

        if (!this.editMode) {
            // Configurar fecha por defecto solo si es nuevo
            this.setDefaultDate();
            // Iniciar reloj en tiempo real
            this.startLiveClock();
        } else {
            // Detener reloj si estamos editando para no sobrescribir
            this.stopLiveClock();
        }

        // Mostrar modal
        super.open(data);

        // DEFENSA: Asegurar que siempre haya al menos una fila de pago
        if (!this.editMode) {
            const container = this.modalElement.querySelector('#payment-parts-container');
            if (container && container.children.length === 0) {
                this.partCount = 0;
                this.addPaymentPart();
            }
        }

        // Focus en búsqueda si no hay cliente
        if (!this.selectedClient) {
            setTimeout(() => {
                this.modalElement.querySelector('#payment-client-query')?.focus();
            }, 300);
        }
    }


    /**
     * Busca clientes
     */
    async searchClients(query) {
        if (!query || query.length < 2) return;

        try {
            this.showLoading();
            const results = await this.api.get(`/api/clients?search=${encodeURIComponent(query)}`);
            this.renderSearchResults(results);
        } catch (error) {
            console.error('Error searching clients:', error);
            this.showError('Error buscando clientes');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Renderiza resultados de búsqueda
     */
    renderSearchResults(clients) {
        const resultsContainer = this.container.querySelector('#payment-search-results');
        if (!resultsContainer) return;

        if (clients.length === 0) {
            resultsContainer.innerHTML = `
                <div style="padding: 20px; text-align: center; color: #64748b;">
                    <i class="fas fa-search" style="font-size: 2rem; opacity: 0.3; margin-bottom: 10px;"></i>
                    <p>No se encontraron clientes</p>
                </div>
            `;
            resultsContainer.style.display = 'block';
            return;
        }

        resultsContainer.innerHTML = clients.map(client => `
            <div class="search-result-item" data-client-id="${client.id}">
                <div class="result-avatar">
                    <i class="fas fa-user"></i>
                </div>
                <div class="result-info">
                    <div class="result-name">${client.legal_name}</div>
                    <div class="result-details">
                        <span>${client.subscriber_code || 'N/A'}</span>
                        <span>${client.ip_address || 'Sin IP'}</span>
                    </div>
                </div>
                <div class="result-balance ${client.account_balance > 0 ? 'debt' : 'paid'}">
                    $${Math.abs(client.account_balance || 0).toFixed(2)}
                </div>
            </div>
        `).join('');

        resultsContainer.style.display = 'block';

        // Attach click events a resultados
        resultsContainer.querySelectorAll('.search-result-item').forEach(item => {
            item.addEventListener('click', () => {
                const clientId = parseInt(item.dataset.clientId);
                const client = clients.find(c => c.id === clientId);
                if (client) this.selectClient(client);
            });
        });
    }

    /**
     * Limpia resultados de búsqueda
     */
    clearSearchResults() {
        const resultsContainer = this.container.querySelector('#payment-search-results');
        if (resultsContainer) {
            resultsContainer.innerHTML = '';
            resultsContainer.style.display = 'none';
        }
    }

    /**
     * Selecciona un cliente
     */
    selectClient(client) {
        this.selectedClient = client;

        // Ocultar búsqueda
        const searchStep = this.container.querySelector('#payment-client-search-step');
        if (searchStep) searchStep.style.display = 'none';

        // Mostrar info de cliente
        this.displaySelectedClient();

        // Mostrar campos de pago
        const detailsFields = this.container.querySelector('#payment-details-fields');
        if (detailsFields) detailsFields.style.display = 'block';

        // Limpiar búsqueda
        this.clearSearchResults();
        const searchInput = this.container.querySelector('#payment-client-query');
        if (searchInput) searchInput.value = '';

        // Enfocar en monto
        setTimeout(() => {
            this.container.querySelector('#pay-amount')?.focus();
        }, 100);

        // Mostrar footer con botones de acción
        const footer = this.container.querySelector('.modal-footer');
        if (footer) footer.style.display = 'flex';
    }

    /**
     * Selecciona cliente por ID
     */
    async selectClientById(clientId) {
        try {
            const client = await this.api.get(`/api/clients/${clientId}`);
            this.selectClient(client);
        } catch (error) {
            console.error('Error loading client:', error);
            this.showError('Error cargando cliente');
        }
    }

    /**
     * Muestra información del cliente seleccionado
     */
    displaySelectedClient() {
        if (!this.selectedClient) return;

        const display = this.container.querySelector('#selected-client-display');
        if (!display) return;

        display.style.display = 'block';

        // Nombre
        const nameEl = this.container.querySelector('#display-client-name');
        if (nameEl) nameEl.textContent = this.selectedClient.legal_name;

        // Código
        const codeEl = this.container.querySelector('#display-client-code');
        if (codeEl) codeEl.textContent = `#${this.selectedClient.subscriber_code || this.selectedClient.id}`;

        // IP
        const ipEl = this.container.querySelector('#display-client-ip');
        if (ipEl) ipEl.textContent = this.selectedClient.ip_address || 'Sin IP';

        // Documento
        const docEl = this.container.querySelector('#display-client-document');
        if (docEl && this.selectedClient.document_id) {
            docEl.textContent = this.selectedClient.document_id;
        }

        // Deuda
        this.displayClientDebt();

        // ID oculto
        const clientIdInput = this.container.querySelector('#payment-client-id');
        if (clientIdInput) clientIdInput.value = this.selectedClient.id;
    }

    /**
     * Muestra información de deuda del cliente
     */
    displayClientDebt() {
        if (!this.selectedClient) return;

        const container = this.container.querySelector('#payment-client-debt-display');
        if (!container) return;

        // Moneda seleccionada en el formulario
        const targetCurrency = this.container.querySelector('#pay-currency')?.value || 'COP';
        const rates = this.rates || { 'USD_COP': 4000, 'USD_VES_BCV': 36.5, 'USD_VES_COM': 40.0 };

        // Deuda original siempre está en COP (Balance del Cliente)
        const balanceCOP = Math.abs(this.selectedClient.account_balance || 0);
        const hasDebt = balanceCOP > 0;

        if (!hasDebt) {
            container.innerHTML = `<div style="color: #64748b; font-size: 0.85rem; font-style: italic;">Sin deuda pendiente</div>`;
            return;
        }

        // --- CALCULO TRIANGULADO SEGÚN REGLA DEL USUARIO ---
        // 1. Convertir COP -> USD
        const balanceUSD = balanceCOP / (rates.USD_COP || 4000);

        // 2. Convertir USD -> Target Currency
        let displayBalance = balanceCOP; // Por defecto COP
        let vesRate = 1.0;

        if (targetCurrency === 'USD') {
            displayBalance = balanceUSD;
        } else if (targetCurrency === 'VES') {
            const rateType = this.container.querySelector('#selected-ves-rate-type')?.value || 'BCV';
            vesRate = rateType === 'BCV' ? rates.USD_VES_BCV : rates.USD_VES_COM;
            displayBalance = balanceUSD * vesRate;
        }

        const prorated = this.calculateProrate(balanceCOP); // Prorrateo se calcula sobre el monto COP original
        const hasProrate = prorated.isApplicable;

        // Convertir prorrateo también
        let displayProrated = prorated.amount;
        if (targetCurrency === 'USD') {
            displayProrated = prorated.amount / rates.USD_COP;
        } else if (targetCurrency === 'VES') {
            displayProrated = (prorated.amount / rates.USD_COP) * vesRate;
        }

        const currencySymbol = targetCurrency === 'VES' ? 'Bs' : (targetCurrency === 'USD' ? 'USD ' : '$');

        const isCollector = window.app?.authService?.getUser()?.role === 'collector';
        const showProrate = hasProrate && !isCollector;

        container.innerHTML = `
            <div style="background: ${hasDebt ? '#fff1f2' : '#ecfdf5'}; border: 1.5px solid ${hasDebt ? '#fda4af' : '#6ee7b7'}; border-radius: 16px; padding: 12px 18px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 12px ${hasDebt ? 'rgba(244, 63, 94, 0.08)' : 'rgba(16, 185, 129, 0.08)'};">
                <div style="display: flex; align-items: center; gap: 15px;">
                    <div style="background: ${hasDebt ? '#fb7185' : '#10b981'}; color: white; width: 42px; height: 42px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">
                        <i class="fas ${hasDebt ? 'fa-file-invoice-dollar' : 'fa-check-circle'}"></i>
                    </div>
                    <div>
                        <span style="font-size: 0.65rem; font-weight: 850; color: ${hasDebt ? '#be123c' : '#047857'}; text-transform: uppercase; letter-spacing: 0.05em; display: block; margin-bottom: 2px;">
                            ${hasDebt ? 'Deuda Pendiente' : 'Cliente Solvente'}
                        </span>
                        <div style="display: flex; flex-direction: column;">
                             <span style="font-size: 1.25rem; font-weight: 950; color: #1e293b;">${currencySymbol}${displayBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                             ${targetCurrency !== 'COP' ? `
                                 <div style="display: flex; gap: 5px; align-items: center; font-size: 0.6rem; color: #64748b; font-weight: 700;">
                                     <span>($${balanceCOP.toLocaleString('en-US')} COP)</span>
                                     <i class="fas fa-arrow-right" style="font-size: 0.5rem; opacity: 0.5;"></i>
                                     <span>$${balanceUSD.toLocaleString('en-US', { minimumFractionDigits: 2 })} USD</span>
                                     ${targetCurrency === 'VES' ? `
                                         <i class="fas fa-arrow-right" style="font-size: 0.5rem; opacity: 0.5;"></i>
                                         <span>${vesRate.toLocaleString('en-US', { minimumFractionDigits: 2 })} Bs/USD</span>
                                     ` : ''}
                                 </div>
                             ` : ''}
                        </div>
                    </div>
                </div>
                
                <div style="display: flex; flex-direction: column; align-items: flex-end;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 2px;">
                        <span style="font-size: 0.85rem; font-weight: 800; color: #64748b;">TOTAL REAL:</span>
                        <span style="font-size: 1rem; font-weight: 900; color: #1e293b; ${hasProrate ? 'text-decoration: line-through; opacity: 0.5;' : ''}">
                            ${currencySymbol}${displayBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                        </span>
                    </div>
                    
                    ${showProrate ? `
                        <div id="prorate-suggest-box" style="background: #ecfdf5; border: 1px solid #10b981; padding: 6px 12px; border-radius: 10px; display: flex; align-items: center; gap: 10px; cursor: pointer; transition: all 0.2s; box-shadow: 0 4px 6px rgba(16, 185, 129, 0.1);">
                            
                            <input type="checkbox" id="apply-prorate-check" style="width: 16px; height: 16px; pointer-events: none;">
                            
                            <div style="display: flex; flex-direction: column;">
                                <div style="display: flex; align-items: center; gap: 6px;">
                                    <i class="fas fa-magic" style="color: #059669; font-size: 0.75rem;"></i>
                                    <span style="font-size: 1.15rem; font-weight: 950; color: #059669;">${currencySymbol}${displayProrated.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                                </div>
                                <span style="font-size: 0.55rem; font-weight: 800; color: #059669; text-transform: uppercase; letter-spacing: 0.05em;">APLICAR DESCUENTO PRORRATEO</span>
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;

        // Si es la primera vez que se carga el cliente, sugerimos el balance
        const amountInput = this.container.querySelector('#pay-amount');
        if (amountInput && !amountInput.value) {
            amountInput.value = displayBalance.toLocaleString('en-US', { minimumFractionDigits: 2 });
            this.calculateERP();
        }
    }

    /**
     * Calcula el monto prorrateado si aplica (Día 16+)
     */
    calculateProrate(originalBalance) {
        const now = new Date();
        const currentDay = now.getDate();
        const startDay = 15; // Por defecto según BillingService

        // Solo aplica si sobrepasa el día de gracia y es el mes actual
        // Simplificamos: si es del día 15 en adelante, sugerimos prorrateo del total adeudado

        const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
        const daysRemaining = daysInMonth - currentDay + 1;

        if (currentDay > startDay && originalBalance > 0) {
            const denominator = daysInMonth - 5; // Caso 30 días -> 25 (Empieza desde día 5)
            const proratedAmount = Math.ceil((originalBalance * daysRemaining) / denominator);
            return {
                isApplicable: true,
                amount: Math.max(0, proratedAmount),
                daysRemaining
            };
        }

        return { isApplicable: false, amount: originalBalance };
    }

    /**
     * Limpia cliente seleccionado
     */
    clearSelectedClient() {
        this.selectedClient = null;

        // Mostrar búsqueda
        const searchStep = this.container.querySelector('#payment-client-search-step');
        if (searchStep) searchStep.style.display = 'block';

        // Ocultar info de cliente
        const display = this.container.querySelector('#selected-client-display');
        if (display) display.style.display = 'none';

        // Ocultar campos de pago
        const detailsFields = this.container.querySelector('#payment-details-fields');
        if (detailsFields) detailsFields.style.display = 'none';

        // Focus en búsqueda
        setTimeout(() => {
            this.container.querySelector('#payment-client-query')?.focus();
        }, 100);

        // Ocultar footer hasta que se seleccione cliente
        const footer = this.container.querySelector('.modal-footer');
        if (footer) footer.style.display = 'none';
    }

    /**
     * Muestra historial del cliente
     */
    showClientHistory() {
        if (!this.selectedClient) return;

        // Emitir evento para que el módulo de clientes muestre el modal de historial
        this.emit('show-client-history', { client: this.selectedClient });
    }

    /**
     * Toggle de campos según método de pago
     */
    toggleMethodFields() {
        const method = this.container.querySelector('#pay-method')?.value;

        const originGroup = this.container.querySelector('#group-origin');
        const referenceGroup = this.container.querySelector('#group-reference');

        if (method === 'transfer' || method === 'card') {
            if (originGroup) originGroup.style.display = 'flex';
            if (referenceGroup) referenceGroup.style.display = 'flex';
        } else {
            if (originGroup) originGroup.style.display = 'none';
            if (referenceGroup) referenceGroup.style.display = 'none';
        }
    }

    /**
     * Actualiza el prefijo de moneda ($ / Bs)
     */
    updateAmountPrefix() {
        const currency = this.container.querySelector('#pay-currency')?.value;
        const prefix = this.container.querySelector('#amount-prefix');
        if (prefix) {
            prefix.textContent = currency === 'VES' ? 'Bs' : '$';
        }
    }

    /**
     * Agrega un nuevo componente de pago (Método Mixto)
     * Con auto-completado inteligente del monto faltante
     */
    addPaymentPart() {
        console.log('➕ [PaymentModal] addPaymentPart called');
        const container = this.modalElement.querySelector('#payment-parts-container');
        if (!container) return;

        // Calcular monto sugerido (Lo que falta para cubrir la deuda)
        let suggestedAmount = 0;
        try {
            if (this.selectedClient) {
                const balanceCOP = Math.abs(this.selectedClient.account_balance || 0);

                // Sumar lo que ya hay en las filas actuales
                let currentTotalCOP = 0;
                const rows = container.querySelectorAll('.payment-part-row');
                rows.forEach(row => {
                    const amountInput = row.querySelector('.part-amount');
                    if (amountInput) {
                        const val = this.parseCurrencyValue(amountInput.value || '0');
                        const curr = row.querySelector('.part-currency')?.value || 'COP';
                        const rateType = row.querySelector('.selected-rate-type')?.value || 'BCV';
                        currentTotalCOP += this.convertToCOP(val, curr, rateType);
                    }
                });

                suggestedAmount = Math.max(0, balanceCOP - currentTotalCOP);
            }
        } catch (e) {
            console.error('❌ Error in addPaymentPart calculation:', e);
        }

        this.partCount++;
        const newPart = document.createElement('div');
        newPart.className = 'payment-part-row';
        newPart.dataset.partIndex = this.partCount - 1;
        newPart.style.cssText = 'background: white; padding: 16px; border-radius: 16px; border: 1px solid #e2e8f0; display: grid; grid-template-columns: 140px 120px 1fr 1fr 40px; gap: 12px; align-items: end; animation: fadeIn 0.3s ease-out;';

        const bcvRate = this.rates?.USD_VES_BCV || 36.5;

        newPart.innerHTML = `
            <div style="position: relative;">
                <label class="modal-subtitle-text" style="font-size: 0.6rem; margin-bottom: 4px; display: block;">MONTO</label>
                <div style="display: flex; gap: 4px; align-items: center;">
                    <input type="text" class="form-control part-amount" placeholder="0.00" 
                        value="${suggestedAmount > 0 ? suggestedAmount.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 }) : ''}"
                        style="font-weight: 800; font-size: 1rem; height: 38px; flex: 1;">
                    <button type="button" class="btn-magic-convert" title="Completar Saldo Restante" 
                        style="background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 8px; width: 34px; height: 38px; color: #6366f1; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s;">
                        <i class="fas fa-magic" style="font-size: 0.8rem;"></i>
                    </button>
                </div>
            </div>
            <div>
                <label class="modal-subtitle-text" style="font-size: 0.6rem; margin-bottom: 4px; display: block;">MONEDA</label>
                <select class="form-control part-currency" style="font-size: 0.75rem; height: 38px;">
                    <option value="COP">COP</option>
                    <option value="USD">USD</option>
                    <option value="VES">VES</option>
                </select>
            </div>
            <div>
                <label class="modal-subtitle-text" style="font-size: 0.6rem; margin-bottom: 4px; display: block;">MÉTODO</label>
                <select class="form-control part-method" style="font-size: 0.75rem; height: 38px;">
                    <option value="cash">Efectivo</option>
                    <option value="transfer">Transferencia</option>
                    <option value="card">Tarjeta / Digital</option>
                </select>
            </div>
            <div>
                <label class="modal-subtitle-text" style="font-size: 0.6rem; margin-bottom: 4px; display: block;">REFERENCIA</label>
                <input type="text" class="form-control part-reference" placeholder="Opcional" 
                    style="font-size: 0.75rem; height: 38px;">
            </div>
            <div style="text-align: center;">
                <button type="button" class="btn-icon-only remove-part" style="color: #ef4444;">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
            
            <div class="ves-rate-context span-full" style="display: none; grid-column: span 5; margin-top: 8px; padding-top: 8px; border-top: 1px dashed #f1f5f9;">
               <div style="display: flex; gap: 12px; align-items: center;">
                   <span style="font-size: 0.6rem; font-weight: 800; color: #64748b;">TASA BS:</span>
                   <div class="rate-toggle-group" style="display: flex; background: #f1f5f9; padding: 2px; border-radius: 8px;">
                       <button type="button" class="rate-btn active" data-rate="BCV" style="padding: 2px 8px; font-size: 0.6rem; border-radius: 6px; border: none; font-weight: 700;">BCV</button>
                       <button type="button" class="rate-btn" data-rate="COM" style="padding: 2px 8px; font-size: 0.6rem; border-radius: 6px; border: none; font-weight: 700; background: transparent;">COM</button>
                   </div>
                   <input type="hidden" class="selected-rate-type" value="BCV">
                   <span class="current-rate-value" style="font-family: 'JetBrains Mono'; font-size: 0.7rem; font-weight: 800; color: #1e293b;">${bcvRate.toFixed(2)}</span>
               </div>
            </div>
        `;

        container.appendChild(newPart);

        // Actualizar totales generales
        this.calculateERP();

        // Habilitar todos los botones de eliminar si hay más de uno
        const removeBtns = container.querySelectorAll('.remove-part');
        if (removeBtns.length > 1) {
            removeBtns.forEach(btn => {
                btn.disabled = false;
                btn.style.color = '#ef4444';
                btn.style.cursor = 'pointer';
            });
        }
    }

    /**
     * Elimina una parte del pago
     */
    removePaymentPart(btn) {
        const row = btn.closest('.payment-part-row');
        if (!row) return;

        row.style.animation = 'fadeOut 0.2s ease-in forwards';
        setTimeout(() => {
            row.remove();

            // Deshabilitar el último botón de eliminar si solo queda uno
            const container = this.modalElement.querySelector('#payment-parts-container');
            const remaining = container.querySelectorAll('.payment-part-row');
            if (remaining.length === 1) {
                const lastBtn = remaining[0].querySelector('.remove-part');
                lastBtn.disabled = true;
                lastBtn.style.color = '#cbd5e1';
                lastBtn.style.cursor = 'not-allowed';
            }

            this.calculateERP();
        }, 200);
    }

    /**
     * Maneja el cambio de moneda en una fila
     */
    handleCurrencyChange(select) {
        const row = select.closest('.payment-part-row');
        const vesContext = row.querySelector('.ves-rate-context');
        if (vesContext) {
            vesContext.style.display = select.value === 'VES' ? 'block' : 'none';
        }
    }

    /**
     * Maneja el toggle de tasa BCV/COMER en una fila
     */
    handleVesRateToggle(btn) {
        const group = btn.closest('.rate-toggle-group');
        const row = btn.closest('.payment-part-row');
        const rateType = btn.dataset.rate;

        group.querySelectorAll('.rate-btn').forEach(b => {
            b.classList.remove('active');
            b.style.background = 'transparent';
        });

        btn.classList.add('active');
        btn.style.background = 'white';

        const hiddenInput = row.querySelector('.selected-rate-type') || row.querySelector('#selected-ves-rate-type');
        if (hiddenInput) hiddenInput.value = rateType;

        const rateVal = row.querySelector('.current-rate-value');
        if (rateVal) {
            rateVal.textContent = rateType === 'BCV' ?
                this.rates.USD_VES_BCV.toFixed(2) :
                this.rates.USD_VES_COM.toFixed(2);
        }

        this.calculateERP();
    }

    /**
     * Calcula impuestos y conversiones en tiempo real (Lógica ERP con Soporte Mixto)
     */
    async calculateERP() {
        try {
            const parts = this.modalElement.querySelectorAll('.payment-part-row');
            let totalCOP = 0;
            let totalUSD = 0;
            let totalTaxUSD = 0;

            const rates = this.rates || { 'USD_COP': 4000, 'USD_VES_BCV': 36.5, 'USD_VES_COM': 40.0 };

            parts.forEach(row => {
                const amountInput = row.querySelector('.part-amount');
                if (!amountInput) return;

                const amount = this.parseCurrencyValue(amountInput.value || '0');
                if (amount <= 0) return;

                const currency = row.querySelector('.part-currency')?.value || 'COP';
                const rateTypeInput = row.querySelector('.selected-rate-type') || row.querySelector('#selected-ves-rate-type');
                const rateType = rateTypeInput?.value || 'BCV';

                let rowCOP = this.convertToCOP(amount, currency, rateType);
                let rowUSD = 0;
                let rowTaxUSD = 0;

                if (currency === 'USD') {
                    rowUSD = amount;
                    rowTaxUSD = amount * 0.03;
                } else if (currency === 'VES') {
                    const vesRate = rateType === 'BCV' ? (rates.USD_VES_BCV || 36.5) : (rates.USD_VES_COM || 40.0);
                    rowUSD = amount / vesRate;
                } else {
                    rowUSD = amount / (rates.USD_COP || 4000);
                }

                totalUSD += rowUSD;
                totalTaxUSD += rowTaxUSD;
                totalCOP += rowCOP;
            });

            // Redondear totalCOP al entero más cercano (COP no usa céntimos en la práctica)
            totalCOP = Math.round(totalCOP);

            // Actualizar UI del Resumen
            const mainTotalEl = this.container.querySelector('#summary-total-main');
            const usdTotalEl = this.container.querySelector('#summary-total-usd');
            const taxTotalEl = this.container.querySelector('#summary-total-tax');

            if (mainTotalEl) {
                mainTotalEl.textContent = `$${totalCOP.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
            }
            if (usdTotalEl) {
                usdTotalEl.textContent = `USD ${(totalUSD + totalTaxUSD).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
            }
            if (taxTotalEl) {
                const taxCOP = totalTaxUSD * (rates.USD_COP || 4000);
                taxTotalEl.textContent = `$${taxCOP.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
            }
        } catch (e) {
            console.error('❌ Error in calculateERP:', e);
        }
    }

    /**
     * Establece fecha por defecto (hoy)
     */
    setDefaultDate() {
        const dateInput = this.container.querySelector('#pay-date');

        if (dateInput && !dateInput.value) {
            const today = new Date().toISOString().split('T')[0];
            dateInput.value = today;
        }

        // Establecer hora actual en formato 12 horas
        const hourSelect = this.container.querySelector('#pay-hour');

        // RE-QUERY minuteSelect para tener referencia fresca
        const freshMinuteSelect = this.container.querySelector('#pay-minute');
        const periodSelect = this.container.querySelector('#pay-period');

        if (hourSelect && !hourSelect.value) {
            const now = new Date();
            let hour = now.getHours();
            const minute = now.getMinutes();

            // Determinar AM/PM
            const period = hour >= 12 ? 'PM' : 'AM';

            // Convertir a formato 12 horas
            if (hour === 0) {
                hour = 12;
            } else if (hour > 12) {
                hour = hour - 12;
            }

            hourSelect.value = hour.toString();

            // Usar minutos exactos
            const minuteStr = String(minute).padStart(2, '0');
            if (freshMinuteSelect) freshMinuteSelect.value = minuteStr;

            periodSelect.value = period;
        }
    }

    /**
     * Inicia el reloj en tiempo real
     */
    startLiveClock() {
        // Detener reloj anterior si existe
        this.stopLiveClock();

        // Actualizar inmediatamente
        this.updateClock();

        // Actualizar cada segundo
        this.clockInterval = setInterval(() => {
            this.updateClock();
        }, 1000);
    }

    /**
     * Actualiza los selectores de hora con el tiempo actual
     */
    updateClock() {
        const hourSelect = this.container.querySelector('#pay-hour');
        const minuteSelect = this.container.querySelector('#pay-minute');
        const periodSelect = this.container.querySelector('#pay-period');

        if (!hourSelect || !minuteSelect || !periodSelect) return;

        const now = new Date();
        let hour = now.getHours();
        const minute = now.getMinutes();

        // Determinar AM/PM
        const period = hour >= 12 ? 'PM' : 'AM';

        // Convertir a formato 12 horas
        if (hour === 0) {
            hour = 12;
        } else if (hour > 12) {
            hour = hour - 12;
        }

        // Actualizar selectores con valores EXACTOS
        const minuteStr = String(minute).padStart(2, '0');
        const second = now.getSeconds();

        hourSelect.value = hour.toString();
        minuteSelect.value = minuteStr;
        periodSelect.value = period;

        // Log para debugging (reducido a cada 10s para no saturar)
        if (second % 10 === 0) {
            console.log(`🕐 Reloj actualizado: ${hour}:${minuteStr} ${period}`);
        }
    }

    /**
     * Detiene el reloj en tiempo real
     */
    stopLiveClock() {
        if (this.clockInterval) {
            clearInterval(this.clockInterval);
            this.clockInterval = null;
        }
    }

    /**
     * Puebla datos de pago al editar
     */
    async populatePaymentData(payment) {
        // Seleccionar cliente
        await this.selectClientById(payment.client_id);

        // Extraer fecha y hora
        const datetime = payment.payment_date || '';
        const [datePart, timePart] = datetime.split('T');

        // Convertir hora de 24h a 12h
        let hour12 = 12, minute = '00', period = 'AM';
        if (timePart) {
            const [hourStr, minuteStr] = timePart.split(':');
            let hour24 = parseInt(hourStr);
            minute = minuteStr;

            // Determinar AM/PM
            period = hour24 >= 12 ? 'PM' : 'AM';

            // Convertir a 12 horas
            if (hour24 === 0) {
                hour12 = 12;
            } else if (hour24 > 12) {
                hour12 = hour24 - 12;
            } else {
                hour12 = hour24;
            }
        }

        // Limpiar y poblar partes del pago
        const container = this.modalElement.querySelector('#payment-parts-container');
        if (container) {
            container.innerHTML = '';
            this.partCount = 0;

            if (payment.details && payment.details.length > 0) {
                payment.details.forEach(detail => {
                    this.addPaymentPart();
                    const lastRow = container.querySelector('.payment-part-row:last-child');
                    if (lastRow) {
                        lastRow.querySelector('.part-amount').value = detail.amount.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
                        lastRow.querySelector('.part-currency').value = detail.currency;
                        lastRow.querySelector('.part-method').value = detail.method;
                        lastRow.querySelector('.part-reference').value = detail.reference || '';

                        // Si es VES, mostrar contexto de tasa
                        if (detail.currency === 'VES') {
                            this.handleCurrencyChange(lastRow.querySelector('.part-currency'));
                            // Podríamos intentar inferir si era BCV o COM basándonos en amount/base_amount, 
                            // pero por ahora lo dejamos por defecto
                        }
                    }
                });
            } else {
                // Fallback legacy
                this.addPaymentPart();
                const row = container.querySelector('.payment-part-row');
                if (row) {
                    row.querySelector('.part-amount').value = (payment.amount || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
                    row.querySelector('.part-currency').value = payment.currency || 'COP';
                    row.querySelector('.part-method').value = payment.payment_method || 'cash';
                    row.querySelector('.part-reference').value = payment.reference || '';
                }
            }
        }

        // Poblar metadata
        const metadataFields = {
            'pay-date': datePart || '',
            'pay-hour': hour12.toString(),
            'pay-minute': minute,
            'pay-period': period,
            'pay-notes': payment.notes || ''
        };

        Object.entries(metadataFields).forEach(([id, value]) => {
            const field = this.container.querySelector(`#${id}`);
            if (field) field.value = value;
        });

        // Mostrar info de auditoría
        if (payment.id) {
            this.displayAuditInfo(payment);
        }

        // Calcular totales
        this.calculateERP();

        // Cambiar texto del botón
        const submitText = this.container.querySelector('#payment-submit-text');
        if (submitText) submitText.textContent = 'Guardar Cambios';
    }

    /**
     * Muestra información de auditoría
     */
    displayAuditInfo(payment) {
        const auditBox = this.container.querySelector('#payment-audit-box');
        if (!auditBox) return;

        auditBox.style.display = 'block';

        const idEl = this.container.querySelector('#audit-payment-id');
        if (idEl) idEl.textContent = `#${payment.id}`;

        if (payment.created_at) {
            const date = new Date(payment.created_at);
            const dateEl = this.container.querySelector('#audit-payment-date');
            const timeEl = this.container.querySelector('#audit-payment-time');

            if (dateEl) dateEl.textContent = date.toLocaleDateString();
            if (timeEl) timeEl.textContent = date.toLocaleTimeString();
        }
    }

    /**
     * Valida el formulario
     */
    validate() {
        if (!this.selectedClient) {
            this.showError('Debe seleccionar un cliente');
            return false;
        }

        // Validar que al menos una fila de pago tenga monto > 0
        const partRows = this.modalElement.querySelectorAll('.payment-part-row');
        let totalAmount = 0;
        partRows.forEach(row => {
            const rawVal = row.querySelector('.part-amount')?.value || '0';
            totalAmount += this.parseCurrencyValue(rawVal);
        });

        if (!totalAmount || totalAmount <= 0) {
            this.showError('El monto debe ser mayor a 0');
            return false;
        }

        const date = this.container.querySelector('#pay-date')?.value;
        if (!date) {
            this.showError('Debe seleccionar una fecha');
            return false;
        }

        // Validar hora
        const hour = this.container.querySelector('#pay-hour')?.value;
        const minute = this.container.querySelector('#pay-minute')?.value;
        const period = this.container.querySelector('#pay-period')?.value;

        if (!hour || !minute || !period) {
            this.showError('Debe seleccionar la hora completa (hora, minutos y AM/PM)');
            return false;
        }

        return true;
    }

    /**
     * Obtiene datos del formulario
     */
    getFormData() {
        const date = this.container.querySelector('#pay-date')?.value;

        // Obtener hora en formato 12 horas
        const hour12 = parseInt(this.container.querySelector('#pay-hour')?.value) || 0;
        const minute = this.container.querySelector('#pay-minute')?.value || '00';
        const period = this.container.querySelector('#pay-period')?.value || 'AM';

        // Convertir a formato 24 horas
        let hour24 = hour12;
        if (period === 'PM' && hour12 !== 12) {
            hour24 = hour12 + 12;
        } else if (period === 'AM' && hour12 === 12) {
            hour24 = 0;
        }

        const hour24Str = String(hour24).padStart(2, '0');
        const payment_datetime = date ? `${date}T${hour24Str}:${minute}:00` : null;

        // Recolectar partes del pago
        const parts = [];
        const partRows = this.modalElement.querySelectorAll('.payment-part-row');

        partRows.forEach(row => {
            const amount = this.parseCurrencyValue(row.querySelector('.part-amount')?.value || '0');
            if (amount > 0) {
                parts.push({
                    amount: amount,
                    currency: row.querySelector('.part-currency')?.value || 'COP',
                    method: row.querySelector('.part-method')?.value || 'cash',
                    rate_type: row.querySelector('.selected-rate-type')?.value || 'BCV',
                    reference: row.querySelector('.part-reference')?.value || '',
                    notes: '' // Individual notes could be added if needed
                });
            }
        });

        return {
            client_id: this.selectedClient?.id,
            parts: parts,
            payment_method: parts.length > 1 ? 'mixed' : (parts[0]?.method || 'cash'),
            payment_date: payment_datetime,
            notes: this.container.querySelector('#pay-notes')?.value,
            apply_prorating: !!this.container.querySelector('#apply-prorate-check')?.checked
        };
    }

    /**
     * Maneja el submit del formulario
     */

    /**
     * Convierte un monto a COP usando las tasas del modal
     */
    convertToCOP(amount, currency, rateType = 'BCV') {
        const rates = this.rates || { 'USD_COP': 4000, 'USD_VES_BCV': 36.5, 'USD_VES_COM': 40.0 };
        if (currency === 'COP') return amount;
        if (currency === 'USD') return amount * (rates.USD_COP || 4000);
        if (currency === 'VES') {
            const vesRate = rateType === 'BCV' ? rates.USD_VES_BCV : rates.USD_VES_COM;
            return (amount / vesRate) * (rates.USD_COP || 4000);
        }
        return amount;
    }

    /**
     * Alterna la aplicación del prorrateo sobre el primer monto del formulario
     */
    toggleProrate(element) {
        if (!this.selectedClient) return;

        const container = element.closest('#prorate-suggest-box');
        const check = container.querySelector('#apply-prorate-check');
        const firstRow = this.modalElement.querySelector('.payment-part-row');
        const amountInput = firstRow ? firstRow.querySelector('.part-amount') : null;

        if (!amountInput || !check) return;

        const balanceCOP = Math.abs(this.selectedClient.account_balance || 0);
        const prorated = this.calculateProrate(balanceCOP);

        // Determinar moneda de la primera fila para convertir el sugerido
        const currency = firstRow.querySelector('.part-currency')?.value || 'COP';
        const rates = this.rates || { 'USD_COP': 4000, 'USD_VES_BCV': 36.5, 'USD_VES_COM': 40.0 };
        const rateType = (firstRow.querySelector('.selected-rate-type') || this.container.querySelector('#selected-ves-rate-type'))?.value || 'BCV';

        let targetValue = balanceCOP;
        if (container.classList.contains('selected-prorate')) {
            // Desactivar
            container.classList.remove('selected-prorate');
            check.checked = false;
            container.style.background = '#ecfdf5';
            container.style.color = '#059669';
            container.querySelectorAll('span, i').forEach(el => el.style.color = '#059669');
            targetValue = balanceCOP;
        } else {
            // Activar
            container.classList.add('selected-prorate');
            check.checked = true;
            container.style.background = '#059669';
            container.style.color = 'white';
            container.querySelectorAll('span, i').forEach(el => el.style.color = 'white');
            targetValue = prorated.amount;
        }

        // Convertir el valor a la moneda de la fila
        let displayValue = targetValue;
        if (currency === 'USD') {
            displayValue = targetValue / (rates.USD_COP || 4000);
        } else if (currency === 'VES') {
            const vesRate = rateType === 'BCV' ? rates.USD_VES_BCV : rates.USD_VES_COM;
            displayValue = (targetValue / (rates.USD_COP || 4000)) * vesRate;
        }

        amountInput.value = displayValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
        this.calculateERP();
    }

    async handleSubmit(e) {
        e.preventDefault();

        if (this.isSubmitting) return;
        this.isSubmitting = true;

        const submitBtn = this.modalElement.querySelector('#payment-submit-btn');
        if (submitBtn) submitBtn.disabled = true;

        try {
            if (!this.validate()) return;

            const formData = this.getFormData();
            const parts = formData.parts;

            if (parts.length === 0) {
                this.showError('Debe ingresar al menos un monto válido');
                return;
            }

            // ─── EDIT MODE: Skip debt validations, go directly to update ───
            if (this.editMode && this.paymentId) {
                const confirmEdit = await this.confirmDialog(
                    'Confirmar Actualización',
                    '¿Está seguro de guardar los cambios en este pago?',
                    'Sí, guardar cambios',
                    'Cancelar'
                );
                if (!confirmEdit) return;

                await this.submitPayment(formData);
                return;
            }

            // ─── NEW PAYMENT: Full debt validation flow ───
            const rates = this.rates || { 'USD_COP': 4000, 'USD_VES_BCV': 36.5, 'USD_VES_COM': 40.0 };

            // Deuda original en COP
            const balanceCOP = Math.abs(this.selectedClient?.account_balance || 0);

            // Calcular reducción de deuda TOTAL en COP
            let totalReductionCOP = 0;
            parts.forEach(p => {
                // Sincronizado: Usar la tasa específica capturada para cada parte
                totalReductionCOP += this.convertToCOP(p.amount, p.currency, p.rate_type);
            });

            const isCollector = window.app?.authService?.getUser()?.role === 'collector';

            if (isCollector) {
                const proceed = await this.confirmDialog(
                    'Confirmar Reporte',
                    `¿Desea enviar este reporte de pago por un total de $${totalReductionCOP.toLocaleString()} COP para su respectiva autorización administrativa?`,
                    'Sí, enviar reporte',
                    'Cancelar'
                );

                if (!proceed) return;
            } else {
                // 1. CLIENTE SIN DEUDA (O CON SALDO A FAVOR)
                if (balanceCOP <= 0) {
                    await this.showErrorDialog(
                        'Cliente Al Día',
                        `El cliente ${this.selectedClient.legal_name} no tiene deuda pendiente.\n\n` +
                        `Para procesar un pago debe:\n` +
                        `• Generar una factura manual\n` +
                        `• Crear un cargo adicional\n` +
                        `• Esperar al próximo ciclo de facturación`
                    );
                    return;
                }

                // 2. LÓGICA DE VALIDACIÓN SEGÚN MONTO VS DEUDA (CON TOLERANCIA DE CÉNTIMOS)
                const diff = totalReductionCOP - balanceCOP;

                // Caso A: PAGO PARCIAL (menor a la deuda por más de 0.05 de margen por redondeo)
                if (diff < -0.05) {
                    const proceed = await this.confirmDialog(
                        'Confirmar Abono Parcial',
                        `El pago total equivalente a $${totalReductionCOP.toLocaleString()} COP es menor a la deuda total de $${balanceCOP.toLocaleString()} COP.\n\n¿Desea registrar este abono a la cuenta del cliente?`,
                        'Sí, registrar abono',
                        'Cancelar y Corregir'
                    );

                    if (!proceed) return;

                    formData.authorized = true;

                    // Preguntar por promesa de pago
                    const createPromise = await this.confirmDialog(
                        'Promesa de Pago',
                        '¿Desea crear una promesa de pago por el saldo restante?'
                    );

                    if (createPromise) {
                        const promiseDate = await this.promptDateDialog(
                            'Fecha de Promesa',
                            '¿Para qué fecha se compromete a pagar el saldo?'
                        );
                        if (promiseDate) {
                            formData.create_promise = true;
                            formData.promise_date = promiseDate;
                        }
                    }
                }
                // Caso B: PAGO EXACTO o dentro del margen (Tolerancia de 2 COP para evitar ruidos de redondeo)
                else if (Math.abs(diff) <= 2.0) {
                    const activate = await this.confirmDialog(
                        'Confirmar Pago Total',
                        `El monto cubre la deuda de $${balanceCOP.toLocaleString()} COP.\n\n¿Desea procesar el pago y reactivar el servicio automáticamente?`,
                        'Sí, pagar y activar',
                        'Cancelar'
                    );

                    if (!activate) return;

                    formData.activate_service = true;
                }
                // Caso C: SOBREPAGO (mayor a la deuda)
                else {
                    const excess = totalReductionCOP - balanceCOP;
                    const applyCredit = await this.confirmDialog(
                        'Sobrepago Detectado',
                        `El monto total equivalente ($${totalReductionCOP.toLocaleString()} COP) es superior a la deuda actual ($${balanceCOP.toLocaleString()} COP).\n\n¿Desea aplicar el excedente de $${excess.toLocaleString()} como saldo a favor para el próximo mes?`,
                        'Sí, aplicar saldo',
                        'Cancelar y Corregir',
                        '#f59e0b' // Warning color
                    );

                    if (!applyCredit) return;

                    formData.is_overpayment = true;
                    formData.activate_service = true;
                }
            }

            // Enviar pago al servidor si pasó todas las confirmaciones
            await this.submitPayment(formData);

        } catch (error) {
            console.error('Error in handleSubmit:', error);
            this.showError('Error al procesar el formulario');
        } finally {
            this.isSubmitting = false;
            if (submitBtn) submitBtn.disabled = false;
        }
    }

    /**
     * Envía el pago al servidor
     */
    async submitPayment(formData) {
        try {
            this.showLoading();

            let response;
            if (this.editMode && this.paymentId) {
                response = await this.api.put(`/api/payments/${this.paymentId}`, formData);
            } else {
                response = await this.api.post('/api/payments', formData);
            }

            // Emitir evento de éxito
            this.emit('payment-saved', { payment: response });

            // Publicar en EventBus global
            this.eventBus.publish('payment_saved', response);

            // Cerrar modal
            this.close();

            // Mostrar éxito
            if (window.Swal) {
                const isCollector = window.app?.authService?.getUser()?.role === 'collector';
                window.Swal.fire({
                    icon: 'success',
                    title: isCollector ? 'Pago Reportado' : 'Pago Registrado',
                    text: isCollector
                        ? 'El reporte ha sido enviado y está pendiente de autorización.'
                        : 'La transacción se ha guardado correctamente.',
                    timer: 2500,
                    showConfirmButton: false
                });
            }

        } catch (error) {
            console.error('Error saving payment:', error);
            const errorMsg = error.message || 'Error guardando pago';

            // MANEJO INTELIGENTE DE ERRORES DE VALIDACIÓN
            if (errorMsg.includes('DUPLICATE_PAYMENT|')) {
                const cleanMsg = errorMsg.split('|')[1];
                const confirmDuplicate = await this.confirmDialog(
                    'Posible Pago Duplicado',
                    cleanMsg,
                    'Sí, registrar de todos modos',
                    'Cancelar',
                    '#f59e0b' // Warning color
                );

                if (confirmDuplicate) {
                    formData.allow_duplicate = true;
                    await this.submitPayment(formData); // Reintentar
                }
            }
            else if (errorMsg.includes('PARTIAL_PAYMENT_REQUIRED|')) {
                const cleanMsg = errorMsg.split('|')[1];
                const authorizePartial = await this.confirmDialog(
                    'Pago Parcial',
                    cleanMsg,
                    'Autorizar Abono',
                    'Corregir Monto',
                    '#3b82f6' // Info color
                );

                if (authorizePartial) {
                    formData.authorized = true;

                    // Preguntar por promesa de pago si es parcial
                    const createPromise = await this.confirmDialog(
                        'Promesa de Pago',
                        '¿Desea crear una promesa de pago por el saldo restante?'
                    );

                    if (createPromise) {
                        const promiseDate = await this.promptDateDialog(
                            'Fecha de Promesa',
                            '¿Para qué fecha se compromete a pagar?'
                        );
                        if (promiseDate) {
                            formData.create_promise = true;
                            formData.promise_date = promiseDate;
                        }
                    }

                    await this.submitPayment(formData); // Reintentar
                }
            }
            else if (errorMsg.includes('PAYMENT_PENDING') || (error.data && error.data.error === 'PAYMENT_PENDING') || errorMsg.includes('El cliente ya tiene un pago en proceso de confirmación')) {
                // Nuevo flujo para pago pendiente
                const pendingPaymentId = error.pending_payment_id || error.response?.pending_payment_id || error.data?.pending_payment_id;

                const sendAlert = await this.confirmDialog(
                    'Pago Pendiente',
                    'Este cliente ya posee un pago en verificación o esperando aprobación.\n\n¿Desea enviar una nueva alerta?',
                    'Sí, enviar alerta',
                    'No, cancelar',
                    '#f59e0b'
                );

                if (sendAlert && pendingPaymentId) {
                    try {
                        this.showLoading();
                        const alertResponse = await this.api.post(`/api/payments/${pendingPaymentId}/alert`, {});
                        if (window.Swal) {
                            window.Swal.fire({
                                icon: 'success',
                                title: 'Alerta Enviada',
                                text: alertResponse.message || 'La alerta fue enviada a los administradores.',
                                timer: 2500,
                                showConfirmButton: false
                            });
                        }
                    } catch (alertError) {
                        this.showError('Error al enviar la alerta: ' + (alertError.message || alertError));
                    } finally {
                        this.hideLoading();
                        this.close(); // Cerrar el modal después
                    }
                }
            }
            else {
                this.showError(errorMsg);
            }
        } finally {
            this.hideLoading();
        }
    }




    /**
     * Muestra un diálogo de error
     */
    async showErrorDialog(title, message) {
        return new Promise(resolve => {
            // Usar SweetAlert2 si está disponible, sino alert
            if (window.Swal) {
                window.Swal.fire({
                    title: title,
                    text: message,
                    icon: 'error',
                    confirmButtonText: 'Entendido',
                    confirmButtonColor: '#ef4444'
                }).then(() => resolve());
            } else {
                alert(`${title}\n\n${message}`);
                resolve();
            }
        });
    }

    /**
     * Muestra un diálogo de confirmación
     */
    /**
     * Muestra un diálogo de confirmación
     */
    async confirmDialog(title, message, confirmText = 'Sí, continuar', cancelText = 'Cancelar', confirmColor = '#3b82f6') {
        return new Promise(resolve => {
            if (window.Swal) {
                window.Swal.fire({
                    title: title,
                    text: message,
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonText: confirmText,
                    cancelButtonText: cancelText,
                    confirmButtonColor: confirmColor,
                    cancelButtonColor: '#64748b'
                }).then((result) => {
                    resolve(result.isConfirmed);
                });
            } else {
                resolve(confirm(`${title}\n\n${message}`));
            }
        });
    }

    /**
     * Pide una fecha
     */
    async promptDateDialog(title, message) {
        if (window.Swal) {
            const { value: date } = await window.Swal.fire({
                title: title,
                text: message,
                input: 'date',
                showCancelButton: true,
                confirmButtonText: 'Aceptar',
                cancelButtonText: 'Cancelar'
            });
            return date;
        } else {
            return prompt(`${title}\n\n${message} (YYYY-MM-DD)`);
        }
    }

    /**
     * Resetea el formulario
     */


    /**
     * Formats an input value with thousands separators while typing
     */
    formatCurrencyInput(input) {
        if (!input) return;
        // Remove everything except numbers and decimal point
        let value = input.value.replace(/[^\d.]/g, '');

        // Ensure only one decimal point
        const parts = value.split('.');
        if (parts.length > 2) value = parts[0] + '.' + parts.slice(1).join('');

        if (value === '') {
            input.value = '';
            return;
        }

        // Format integer part with thousands separators
        let integerPart = parts[0];
        let decimalPart = parts.length > 1 ? '.' + parts[1].substring(0, 2) : '';

        // Add separators (commas)
        integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');

        input.value = integerPart + decimalPart;
    }

    /**
     * Parses a formatted currency string back to a float
     */
    parseCurrencyValue(value) {
        if (typeof value !== 'string') return parseFloat(value) || 0;
        // Remove thousands separators (commas)
        return parseFloat(value.replace(/,/g, '')) || 0;
    }

    /**
     * Completa el saldo restante en la fila actual
     */
    fillRemainingBalance(row) {
        if (!this.selectedClient) return;

        const balanceCOP = Math.abs(this.selectedClient.account_balance || 0);

        // Sumar lo que hay en las OTRAS filas
        let otherTotalCOP = 0;
        const allRows = this.modalElement.querySelectorAll('.payment-part-row');
        allRows.forEach(r => {
            if (r !== row) {
                const val = this.parseCurrencyValue(r.querySelector('.part-amount')?.value || '0');
                const curr = r.querySelector('.part-currency')?.value || 'COP';
                const rateType = r.querySelector('.selected-rate-type')?.value || 'BCV';
                otherTotalCOP += this.convertToCOP(val, curr, rateType);
            }
        });

        const pendingCOP = Math.max(0, balanceCOP - otherTotalCOP);

        // Convertir pendingCOP a la moneda de la fila actual
        const currency = row.querySelector('.part-currency')?.value || 'COP';
        const rateType = row.querySelector('.selected-rate-type')?.value || 'BCV';
        const rates = this.rates || { 'USD_COP': 4000, 'USD_VES_BCV': 36.5, 'USD_VES_COM': 40.0 };

        let displayValue = pendingCOP;
        if (currency === 'USD') {
            displayValue = pendingCOP / (rates.USD_COP || 4000);
            // Redondear AL ALZA al 2do decimal para asegurar que cubra la deuda
            displayValue = Math.ceil(displayValue * 100) / 100;
        } else if (currency === 'VES') {
            const vesRate = rateType === 'BCV' ? rates.USD_VES_BCV : rates.USD_VES_COM;
            displayValue = (pendingCOP / (rates.USD_COP || 4000)) * vesRate;
            // Redondear AL ALZA al 2do decimal
            displayValue = Math.ceil(displayValue * 100) / 100;
        }

        const amountInput = row.querySelector('.part-amount');
        if (amountInput) {
            amountInput.value = displayValue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
            // Disparar input para que calculateERP se actualice
            amountInput.dispatchEvent(new Event('input', { bubbles: true }));
        }

        // Efecto visual en el botón
        const btn = row.querySelector('.btn-magic-convert');
        if (btn) {
            btn.style.background = '#6366f1';
            btn.style.color = 'white';
            const icon = btn.querySelector('i');
            if (icon) icon.className = 'fas fa-check';

            setTimeout(() => {
                btn.style.background = '#f1f5f9';
                btn.style.color = '#6366f1';
                if (icon) icon.className = 'fas fa-magic';
            }, 1000);
        }
    }
}
