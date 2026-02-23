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
            'COP_VES': 0.009
        };
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
        const form = this.modalElement.querySelector('form');
        if (form) form.reset();

        // Limpiar cliente seleccionado
        this.selectedClient = null;
        this.clearSelectedClient();
    }

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

        // Toggle de campos según método de pago
        const methodSelect = this.modalElement.querySelector('#pay-method');
        if (methodSelect) {
            this.addEventListener(methodSelect, 'change', () => this.toggleMethodFields());
        }

        // NUEVO: Cálculos ERP en tiempo real
        const amountInput = this.modalElement.querySelector('#pay-amount');
        const currencySelect = this.modalElement.querySelector('#pay-currency');

        if (amountInput) {
            this.addEventListener(amountInput, 'input', (e) => {
                this.formatCurrencyInput(e.target);
                this.calculateERP();
            });
        }
        if (currencySelect) {
            this.addEventListener(currencySelect, 'change', (e) => {
                this.updateAmountPrefix();

                // Mostrar/Ocultar selector de tasa VES
                const vesSelector = this.container.querySelector('#ves-rate-selector');
                if (vesSelector) {
                    vesSelector.style.display = e.target.value === 'VES' ? 'block' : 'none';
                }

                // Mostrar/Ocultar nota de conversión COP/USD
                const copNote = this.container.querySelector('#cop-conversion-note');
                if (copNote) {
                    copNote.style.display = (e.target.value === 'USD' || e.target.value === 'VES') ? 'block' : 'none';
                }

                // RE-REPRESENTAR DEUDA: Actualizar los montos sugeridos según la nueva moneda
                this.displayClientDebt();
                this.calculateERP();
            });
        }

        // NUEVO: Manejo de tarjetas de tasa VES
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

                // RE-REPRESENTAR DEUDA: Si cambió de BCV a COM, actualizamos los montos sugeridos
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

        // Submit del formulario se maneja en BaseModal vía handleSubmit
        this._eventsAttached = true;
        console.log('✅ Payment Modal events attached');
    }

    /**
     * Abre el modal en modo crear o editar
     */
    async open(data = {}) {
        await this._initPromise;

        this.editMode = !!data.payment;
        this.paymentId = data.payment?.id || null;

        // Actualizar título
        const title = this.modalElement.querySelector('#payment-modal-title');
        if (title) {
            title.textContent = this.editMode ? 'Editar Pago' : 'Registrar Nuevo Pago';
        }

        // Si hay cliente preseleccionado
        if (data.clientId) {
            await this.selectClientById(data.clientId);
        }

        // Si estamos editando, poblar formulario
        if (this.editMode && data.payment) {
            await this.populatePaymentData(data.payment);
        }

        // Resetear formulario si es nuevo
        if (!this.editMode && !data.clientId) {
            this.resetForm();
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
                    
                    ${hasProrate ? `
                        <div id="prorate-suggest-box" style="background: #ecfdf5; border: 1px solid #10b981; padding: 6px 12px; border-radius: 10px; display: flex; align-items: center; gap: 10px; cursor: pointer; transition: all 0.2s; box-shadow: 0 4px 6px rgba(16, 185, 129, 0.1);" 
                             onclick="this.classList.toggle('selected-prorate'); const input = this.closest('form').querySelector('#pay-amount'); const check = this.querySelector('#apply-prorate-check'); if(this.classList.contains('selected-prorate')) { input.value = '${displayProrated.toLocaleString('en-US', { minimumFractionDigits: 2 })}'; check.checked = true; this.style.background='#059669'; this.style.color='white'; this.querySelectorAll('span, i').forEach(el=>el.style.color='white'); } else { input.value = '${displayBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}'; check.checked = false; this.style.background='#ecfdf5'; this.style.color='#059669'; this.querySelectorAll('span, i').forEach(el=>el.style.color='#059669'); } input.dispatchEvent(new Event('input'));">
                            
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
     * Calcula impuestos y conversiones en tiempo real (Lógica ERP)
     */
    async calculateERP() {
        const rawVal = this.container.querySelector('#pay-amount')?.value || '0';
        const amount = this.parseCurrencyValue(rawVal);
        const currency = this.container.querySelector('#pay-currency')?.value || 'COP';

        const summaryContainer = this.container.querySelector('#fiscal-summary-container');
        const taxEl = this.container.querySelector('#fiscal-tax-value');
        const baseEl = this.container.querySelector('#fiscal-base-value');
        const totalEl = this.container.querySelector('#fiscal-total-value');
        const rateEl = this.container.querySelector('#fiscal-rate-value');

        if (amount <= 0) {
            if (summaryContainer) summaryContainer.style.display = 'none';
            return;
        }

        // Usar tasas dinámicas cargadas en el componente
        const rates = this.rates || {
            'USD_COP': 4000,
            'USD_VES': 36.5,
            'COP_VES': 0.009
        };

        let taxAmount = 0;
        let baseAmount = amount;
        let currentRate = 1.0;

        // Regla IGTF (Venezuela): 3% si es USD o VES
        if (currency === 'USD' || currency === 'VES') {
            if (currency === 'USD') {
                taxAmount = amount * 0.03;
                baseAmount = amount;
                currentRate = 1.0;
            } else {
                // VES -> USD
                const rateType = this.container.querySelector('#selected-ves-rate-type')?.value || 'BCV';
                const vesRate = rateType === 'BCV' ? rates.USD_VES_BCV : rates.USD_VES_COM;

                currentRate = 1 / vesRate;
                baseAmount = amount * currentRate;
                taxAmount = 0; // Dejamos IGTF para USD por ahora según ley
            }
        } else if (currency === 'COP') {
            currentRate = 1 / rates.USD_COP;
            baseAmount = amount * currentRate;
        }

        const totalCharged = amount + taxAmount;

        // Actualizar UI
        if (summaryContainer) summaryContainer.style.display = 'flex';

        const symb = currency === 'VES' ? 'Bs' : '$';
        if (taxEl) taxEl.textContent = `${symb}${taxAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        if (baseEl) baseEl.textContent = `USD ${baseAmount.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        if (totalEl) totalEl.textContent = `${symb}${totalCharged.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        if (rateEl) rateEl.textContent = currentRate.toLocaleString('en-US', { minimumFractionDigits: 4 });

        // Estilización condicional si hay impuestos
        if (summaryContainer) {
            summaryContainer.style.borderColor = taxAmount > 0 ? '#f87171' : '#cbd5e1';
            summaryContainer.style.background = taxAmount > 0 ? '#fdf2f2' : '#f8fafc';
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

        // Poblar campos
        const fields = {
            'pay-amount': (payment.amount || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 }),
            'pay-currency': payment.currency || 'COP',
            'pay-method': payment.payment_method || 'cash',
            'pay-origin': payment.origin || 'national',
            'pay-reference': payment.reference || '',
            'pay-date': datePart || '',
            'pay-hour': hour12.toString(),
            'pay-minute': minute,
            'pay-period': period,
            'pay-notes': payment.notes || ''
        };

        Object.entries(fields).forEach(([id, value]) => {
            const field = this.container.querySelector(`#${id}`);
            if (field) field.value = value;
        });

        // Mostrar info de auditoría
        if (payment.id) {
            this.displayAuditInfo(payment);
        }

        // Toggle de campos
        this.toggleMethodFields();

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

        const rawAmount = this.container.querySelector('#pay-amount')?.value || '0';
        const amount = this.parseCurrencyValue(rawAmount);
        if (!amount || amount <= 0) {
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

        const rawAmount = this.container.querySelector('#pay-amount')?.value || '0';

        return {
            client_id: this.selectedClient?.id,
            amount: this.parseCurrencyValue(rawAmount),
            currency: this.container.querySelector('#pay-currency')?.value,
            payment_method: this.container.querySelector('#pay-method')?.value,
            origin: this.container.querySelector('#pay-origin')?.value,
            reference: this.container.querySelector('#pay-reference')?.value,
            payment_date: payment_datetime,
            notes: this.container.querySelector('#pay-notes')?.value,
            apply_prorating: !!this.container.querySelector('#apply-prorate-check')?.checked
        };
    }

    /**
     * Maneja el submit del formulario
     */

    async handleSubmit(e) {
        e.preventDefault();

        if (!this.validate()) return;

        const formData = this.getFormData();
        const amount = formData.amount;
        const rates = this.rates || { 'USD_COP': 4000, 'USD_VES_BCV': 36.5, 'USD_VES_COM': 40.0 };

        // Deuda original en COP
        const balanceCOP = Math.abs(this.selectedClient?.account_balance || 0);

        // --- CONVERTIR DEUDA A MONEDA DE PAGO PARA COMPARACIÓN ---
        const balanceUSD = balanceCOP / (rates.USD_COP || 4000);
        let debtInPaymentCurrency = balanceCOP; // Por defecto COP

        if (formData.currency === 'USD') {
            debtInPaymentCurrency = balanceUSD;
        } else if (formData.currency === 'VES') {
            const rateType = this.container.querySelector('#selected-ves-rate-type')?.value || 'BCV';
            const vesRate = rateType === 'BCV' ? rates.USD_VES_BCV : rates.USD_VES_COM;
            debtInPaymentCurrency = balanceUSD * vesRate;
        }

        // Si aplica prorrateo, la "deuda esperada" es el monto prorrateado
        if (formData.apply_prorating) {
            const prorated = this.calculateProrate(balanceCOP);
            if (formData.currency === 'COP') {
                debtInPaymentCurrency = prorated.amount;
            } else if (formData.currency === 'USD') {
                debtInPaymentCurrency = prorated.amount / rates.USD_COP;
            } else if (formData.currency === 'VES') {
                const rateType = this.container.querySelector('#selected-ves-rate-type')?.value || 'BCV';
                const vesRate = rateType === 'BCV' ? rates.USD_VES_BCV : rates.USD_VES_COM;
                debtInPaymentCurrency = (prorated.amount / rates.USD_COP) * vesRate;
            }
        }

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
        const diff = amount - debtInPaymentCurrency;

        // Caso A: PAGO PARCIAL (menor a la deuda por más de 0.05 de margen por redondeo)
        if (diff < -0.05) {
            const currencySymbol = formData.currency === 'VES' ? 'Bs' : (formData.currency === 'USD' ? 'USD ' : '$');
            const proceed = await this.confirmDialog(
                'Confirmar Abono Parcial',
                `El monto ${currencySymbol}${amount.toLocaleString()} es menor a la deuda total de ${currencySymbol}${debtInPaymentCurrency.toLocaleString()}.\n\n¿Desea registrar este abono a la cuenta del cliente?`,
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
        // Caso B: PAGO EXACTO o dentro del margen
        else if (Math.abs(diff) <= 0.05) {
            const currencySymbol = formData.currency === 'VES' ? 'Bs' : (formData.currency === 'USD' ? 'USD ' : '$');
            const activate = await this.confirmDialog(
                'Confirmar Pago Total',
                `El monto cubre la deuda de ${currencySymbol}${debtInPaymentCurrency.toLocaleString()}.\n\n¿Desea procesar el pago y reactivar el servicio automáticamente?`,
                'Sí, pagar y activar',
                'Cancelar'
            );

            if (!activate) return;

            formData.activate_service = true;
        }
        // Caso C: SOBREPAGO (mayor a la deuda)
        else {
            const excess = amount - debtInPaymentCurrency;
            const currencySymbol = formData.currency === 'VES' ? 'Bs' : (formData.currency === 'USD' ? 'USD ' : '$');
            const applyCredit = await this.confirmDialog(
                'Sobrepago Detectado',
                `El monto ${currencySymbol}${amount.toLocaleString()} es superior a la deuda actual (${currencySymbol}${debtInPaymentCurrency.toLocaleString()}).\n\n¿Desea aplicar el excedente de ${currencySymbol}${excess.toLocaleString()} como saldo a favor para el próximo mes?`,
                'Sí, aplicar saldo',
                'Cancelar y Corregir',
                '#f59e0b' // Warning color
            );

            if (!applyCredit) return;

            formData.apply_credit = true;
            formData.activate_service = true;
        }

        // Enviar pago al servidor si pasó todas las confirmaciones
        await this.submitPayment(formData);
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
                window.Swal.fire({
                    icon: 'success',
                    title: 'Pago Registrado',
                    text: 'La transacción se ha guardado correctamente.',
                    timer: 2000,
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
    resetForm() {
        const form = this.container.querySelector('#payment-form');
        if (form) form.reset();

        this.clearSelectedClient();
        this.setDefaultDate();
        this.editMode = false;
        this.paymentId = null;

        // Ocultar audit box
        const auditBox = this.container.querySelector('#payment-audit-box');
        if (auditBox) auditBox.style.display = 'none';

        // Resetear texto del botón
        const submitText = this.container.querySelector('#payment-submit-text');
        if (submitText) submitText.textContent = 'Confirmar Pago';
    }

    /**
     * Hook al cerrar
     */
    onClose() {
        this.stopLiveClock();
        this.resetForm();
        if (window.app) app.showLoading(false);
    }

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
}
