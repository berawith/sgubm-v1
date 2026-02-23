import { BaseModal } from '../shared/base-modal.component.js';

/**
 * Componente para gestionar promesas de pago de clientes
 * Ahora consolidado con funcionalidades de búsqueda y cálculo automático
 */
export class PromiseModal extends BaseModal {
    constructor(api, eventBus) {
        super('promise', api, eventBus);
        this.currentClientId = null;
        this.searchTimeout = null;
        this.selectedClient = null;
    }

    async init() {
        await this.loadResources(
            '/static/js/components/promise-modal/promise-modal.template.html'
        );

        this.setupEventListeners();
    }

    setupEventListeners() {
        // Search input
        const searchInput = this.modalElement.querySelector('#promise-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => this.handleSearch(e.target.value));
        }

        // Back to search button
        const backBtn = this.modalElement.querySelector('#btn-back-to-search');
        if (backBtn) {
            backBtn.addEventListener('click', () => this.showSearchStep());
        }

        // Delete button
        const deleteBtn = this.modalElement.querySelector('#btn-delete-promise');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => this.handleDelete());
        }

        // Days calculation
        const daysInput = this.modalElement.querySelector('#promise_days');
        const dateInput = this.modalElement.querySelector('#promise_date');

        if (daysInput) {
            daysInput.addEventListener('input', (e) => this.calculateDateFromDays(e.target.value));
        }

        if (dateInput) {
            dateInput.addEventListener('change', (e) => this.calculateDaysFromDate(e.target.value));
        }
    }

    /**
     * @param {object} data - { client: {...}, clientId: ID } (optional)
     */
    async open(data = {}) {
        await this._initPromise;

        this.resetUI();

        let client = data.client;
        const clientId = data.clientId;

        if (!client && clientId) {
            try {
                this.showLoading();
                client = await this.api.get(`/api/clients/${clientId}`);
            } catch (error) {
                console.error('Error fetching client for PromiseModal:', error);
                this.showError('Error al cargar datos del cliente');
                return;
            } finally {
                this.hideLoading();
            }
        }

        if (client) {
            this.selectClient(client);
        } else {
            this.showSearchStep();
        }

        super.open();
    }

    resetUI() {
        this.selectedClient = null;
        this.currentClientId = null;

        const searchInput = this.modalElement.querySelector('#promise-search-input');
        if (searchInput) searchInput.value = '';

        const resultsArea = this.modalElement.querySelector('#promise-search-results');
        if (resultsArea) {
            resultsArea.innerHTML = '';
            resultsArea.style.display = 'none';
        }

        this.modalElement.querySelector('#promise-search-step').style.display = 'block';
        this.modalElement.querySelector('#promise-details-step').style.display = 'none';
        this.modalElement.querySelector('#btn-save-promise').style.display = 'none';
        this.modalElement.querySelector('#btn-back-to-search').style.display = 'none';
        this.modalElement.querySelector('#btn-delete-promise').style.display = 'none';
        this.modalElement.querySelector('#promise-status-badge-container').style.display = 'none';

        const subtitle = this.modalElement.querySelector('#promise-client-name-subtitle');
        if (subtitle) subtitle.textContent = 'EXTENSIÓN TEMPORAL DE SERVICIO';
    }

    showSearchStep() {
        this.modalElement.querySelector('#promise-search-step').style.display = 'block';
        this.modalElement.querySelector('#promise-details-step').style.display = 'none';
        this.modalElement.querySelector('#btn-save-promise').style.display = 'none';
        this.modalElement.querySelector('#btn-back-to-search').style.display = 'none';
        this.modalElement.querySelector('#promise-status-badge-container').style.display = 'none';

        const title = this.modalElement.querySelector('#promise-modal-title');
        if (title) title.textContent = 'Registrar Promesa de Pago';

        const subtitle = this.modalElement.querySelector('#promise-client-name-subtitle');
        if (subtitle) subtitle.textContent = 'EXTENSIÓN TEMPORAL DE SERVICIO';

        const searchInput = this.modalElement.querySelector('#promise-search-input');
        if (searchInput) searchInput.focus();
    }

    async handleSearch(query) {
        if (!query || query.length < 2) {
            const resultsArea = this.modalElement.querySelector('#promise-search-results');
            if (resultsArea) {
                resultsArea.innerHTML = '';
                resultsArea.style.display = 'none';
            }
            return;
        }

        if (this.searchTimeout) clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(async () => {
            try {
                const resultsArea = this.modalElement.querySelector('#promise-search-results');
                resultsArea.innerHTML = '<div style="padding:20px; text-align:center; color:#94a3b8;"><i class="fas fa-spinner fa-spin"></i> Buscando...</div>';
                resultsArea.style.display = 'block';

                const clients = await this.api.get(`/api/clients?search=${encodeURIComponent(query)}&limit=10`);

                if (!clients || clients.length === 0) {
                    resultsArea.innerHTML = '<div style="padding:20px; color:#94a3b8; text-align:center;">No se encontraron clientes</div>';
                    return;
                }

                this.renderSearchResults(clients);
            } catch (error) {
                console.error('Error searching clients:', error);
            }
        }, 300);
    }

    renderSearchResults(clients) {
        const resultsArea = this.modalElement.querySelector('#promise-search-results');
        if (!resultsArea) return;

        resultsArea.innerHTML = clients.map(c => `
            <div class="search-result-item-premium" data-id="${c.id}" 
                style="padding: 12px 16px; border-bottom: 1px solid #f1f5f9; cursor: pointer; display: flex; align-items: center; gap: 12px; transition: background 0.2s;">
                <div class="avatar-mini-circle" style="background: ${c.status === 'active' ? '#ecfdf5' : '#fef2f2'}; color: ${c.status === 'active' ? '#10b981' : '#ef4444'}; width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.8rem;">
                    ${(c.legal_name || 'C').charAt(0).toUpperCase()}
                </div>
                <div style="flex: 1;">
                    <div style="font-weight: 700; color: #1e293b; font-size: 0.9rem;">${c.legal_name}</div>
                    <div style="font-size: 0.75rem; color: #64748b; font-weight: 500;">${c.subscriber_code || '---'} | ${c.ip_address || 'Sin IP'}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-weight: 800; color: ${c.account_balance > 0 ? '#ef4444' : '#10b981'}; font-size: 0.85rem;">$${(c.account_balance || 0).toLocaleString()}</div>
                    <div style="font-size: 0.6rem; color: #94a3b8; font-weight: 700; text-transform: uppercase;">Deuda</div>
                </div>
            </div>
        `).join('');

        // Event delegation for clicks
        resultsArea.querySelectorAll('.search-result-item-premium').forEach(item => {
            item.addEventListener('click', async () => {
                const id = item.dataset.id;
                try {
                    this.showLoading();
                    const client = await this.api.get(`/api/clients/${id}`);
                    this.selectClient(client);
                } catch (error) {
                    console.error('Error fetching client details:', error);
                    this.showError('Error al cargar detalles del cliente');
                } finally {
                    this.hideLoading();
                }
            });
        });
    }

    selectClient(client) {
        this.selectedClient = client;
        this.currentClientId = client.id;

        // UI Steps
        this.modalElement.querySelector('#promise-search-step').style.display = 'none';
        this.modalElement.querySelector('#promise-details-step').style.display = 'block';
        this.modalElement.querySelector('#btn-save-promise').style.display = 'block';
        this.modalElement.querySelector('#btn-back-to-search').style.display = 'block';

        // Set Headers
        const title = this.modalElement.querySelector('#promise-modal-title');
        if (title) title.textContent = 'Registrar Promesa';

        const subtitle = this.modalElement.querySelector('#promise-client-name-subtitle');
        if (subtitle) subtitle.textContent = client.legal_name;

        // Fill Details Panel
        this.modalElement.querySelector('#p-display-name').textContent = client.legal_name;
        this.modalElement.querySelector('#p-display-identity').textContent = `${client.identity_document || 'S/D'} | ${client.phone || 'S/T'}`;

        const balanceEl = this.modalElement.querySelector('#p-display-balance');
        balanceEl.textContent = `$${(client.account_balance || 0).toLocaleString()}`;
        balanceEl.style.color = (client.account_balance || 0) > 0 ? '#ef4444' : '#10b981';

        this.modalElement.querySelector('#p-display-due').textContent = client.due_date ? new Date(client.due_date).toLocaleDateString() : 'Pendiente';
        this.modalElement.querySelector('#p-display-router').textContent = client.router || 'Ninguno';

        const brokenCount = client.broken_promises_count || 0;
        this.modalElement.querySelector('#p-display-broken-counter').textContent = brokenCount;

        // Risk Alert
        const alertEl = this.modalElement.querySelector('#p-risk-alert');
        if (alertEl) {
            if (brokenCount >= 2 && (client.account_balance || 0) > 0) {
                alertEl.style.display = 'flex';
                this.modalElement.querySelector('#p-broken-count-alert').textContent = brokenCount;
            } else {
                alertEl.style.display = 'none';
            }
        }

        // Solvent Check Logic
        const solventAlert = this.modalElement.querySelector('#p-solvent-alert');
        const saveBtn = this.modalElement.querySelector('#btn-save-promise');
        const inputs = this.modalElement.querySelectorAll('#promise_date, #promise_days');
        const deleteBtn = this.modalElement.querySelector('#btn-delete-promise'); // Also hide delete if solvent? No, maybe they paid and now are solvent but have an old promise..

        // If balance <= 0, disable creation of NEW promises. 
        // But if they have an existing promise (client.promise_date), maybe they want to edit/delete it?
        // Let's assume: 
        // 1. If solvent AND NO existing promise -> Disable ALL.
        // 2. If solvent AND existing promise -> Allow Delete/View, but maybe warn about solvency? 
        // For simplicity and safety per user request: "bajo que deuda?" -> implies creation is the issue.

        const isSolvent = (client.account_balance || 0) <= 0;
        const hasExistingPromise = !!client.promise_date;

        if (isSolvent && !hasExistingPromise) {
            // Case: Solvent and trying to create new promise -> BLOCK
            if (solventAlert) solventAlert.style.display = 'flex';

            if (saveBtn) {
                saveBtn.disabled = true;
                saveBtn.style.opacity = '0.5';
                saveBtn.style.cursor = 'not-allowed';
                saveBtn.style.display = 'none'; // Better hide it to avoid confusion
            }

            inputs.forEach(input => {
                input.disabled = true;
                input.style.backgroundColor = '#f1f5f9';
            });

        } else {
            // Case: In Debt OR Has Existing Promise (even if solvent now, maybe adjusting?)
            // Actually, if they are solvent, they shouldn't need a promise extension. 
            // The promise is to extend service date. If they are solvent, service should be active.

            if (solventAlert) solventAlert.style.display = 'none';

            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.style.opacity = '1';
                saveBtn.style.cursor = 'pointer';
                // Only show save button if not blocking
                if (!isSolvent || hasExistingPromise) {
                    // Wait, if solvent and has promise, maybe they want to delete it?
                    // So save button (Update) might be weird if solvent.
                    // But let's stick to blocking creation for now.
                    saveBtn.style.display = 'block';
                }
                if (isSolvent && hasExistingPromise) {
                    // If solvent but has promise, they probably paid. 
                    // The promise might be stale.
                    // We should probably allow deleting it?
                    saveBtn.style.display = 'none'; // Don't allow updating promise if solvent
                    if (solventAlert) {
                        solventAlert.style.display = 'flex';
                        solventAlert.querySelector('strong').textContent = 'CLIENTE AL DÍA';
                        solventAlert.querySelector('span').textContent = 'El cliente ya no tiene deuda. Puede eliminar la promesa existente si lo desea.';
                    }
                }
            }

            inputs.forEach(input => {
                input.disabled = (isSolvent && !hasExistingPromise);
                // If solvent and has promise, maybe read-only?
                if (isSolvent && hasExistingPromise) input.disabled = true;
                else input.style.backgroundColor = 'white';
            });
        }

        // Form Fields
        this.modalElement.querySelector('#client_id').value = client.id;

        // Initial Dates
        // const daysInput = ... (already defined above)
        // const dateInput = ...
        // const deleteBtn = ... (already defined above)

        if (client.promise_date) {
            const pDate = new Date(client.promise_date);
            // Fix timezone offset issue for date input? 
            // ISO string takes UTC. If local is behind, it might show previous day.
            // Better to use local YYYY-MM-DD
            const localDate = new Date(pDate.getTime() - (pDate.getTimezoneOffset() * 60000)).toISOString().split('T')[0];

            this.modalElement.querySelector('#promise_date').value = localDate;
            this.calculateDaysFromDate(localDate);
            if (deleteBtn) deleteBtn.style.display = 'block';
        } else {
            this.modalElement.querySelector('#promise_days').value = 3;
            // Calculate date from days (3)
            this.calculateDateFromDays(3);

            if (deleteBtn) deleteBtn.style.display = 'none';
        }

        this.updatePromiseStatusBadge(client);
    }

    updatePromiseStatusBadge(client) {
        const badgeContainer = this.modalElement.querySelector('#promise-status-badge-container');
        const badge = this.modalElement.querySelector('#p-client-status-badge');

        if (!badgeContainer || !badge) return;

        let statusText = 'ACTIVO';
        let bgColor = '#10b981';

        const now = new Date();
        now.setHours(0, 0, 0, 0);

        const promiseDate = client.promise_date ? new Date(client.promise_date) : null;
        if (promiseDate) promiseDate.setHours(0, 0, 0, 0);

        if (client.status === 'suspended') {
            if (promiseDate && promiseDate < now) {
                statusText = 'PROMESA CORTADA';
                bgColor = '#991b1b';
            } else {
                statusText = 'CORTADO';
                bgColor = '#ef4444';
            }
        } else if (client.status === 'active') {
            if (promiseDate && promiseDate >= now) {
                statusText = 'PROMESA VIGENTE';
                bgColor = '#6366f1';
            } else if ((client.account_balance || 0) > 0) {
                statusText = 'PENDIENTE';
                bgColor = '#f59e0b';
            }
        }

        badge.textContent = statusText;
        badge.style.background = bgColor;
        badge.style.color = 'white';
        badgeContainer.style.display = 'block';
    }

    calculateDateFromDays(days) {
        if (!days || days < 0) return;
        const now = new Date();
        const promiseDate = new Date(now);
        promiseDate.setDate(now.getDate() + parseInt(days));

        const dateInput = this.modalElement.querySelector('#promise_date');
        if (dateInput) {
            dateInput.value = promiseDate.toISOString().split('T')[0];
        }
    }

    calculateDaysFromDate(dateStr) {
        if (!dateStr) return;
        const promiseDate = new Date(dateStr);
        const now = new Date();
        now.setHours(0, 0, 0, 0);

        const diffTime = promiseDate - now;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        const daysInput = this.modalElement.querySelector('#promise_days');
        if (daysInput) {
            daysInput.value = diffDays > 0 ? diffDays : 0;
        }
    }

    async handleDelete() {
        if (!confirm('¿Eliminar la promesa de pago? El cliente podría ser suspendido automáticamente.')) return;

        try {
            this.showLoading();
            await this.api.delete(`/api/clients/${this.currentClientId}/promise`);

            this.emit('promise-deleted', { clientId: this.currentClientId });
            this.eventBus.publish('client_updated', { id: this.currentClientId });

            if (window.toast) window.toast.success('Promesa eliminada');
            this.close();
        } catch (error) {
            console.error('Error deleting promise:', error);
            this.showError('Error al eliminar promesa');
        } finally {
            this.hideLoading();
        }
    }

    async handleSubmit(e) {
        e.preventDefault();

        const date = this.modalElement.querySelector('#promise_date').value;
        const days = this.modalElement.querySelector('#promise_days').value;

        if (!date) {
            this.showError('Seleccione una fecha');
            return;
        }

        try {
            this.showLoading();
            // Matching the backend expected field 'promise_date'
            const response = await this.api.post(`/api/clients/${this.currentClientId}/promise`, {
                promise_date: date,
                days: days
            });

            this.emit('promise-saved', { clientId: this.currentClientId, date });
            this.eventBus.publish('client_updated', { id: this.currentClientId });

            if (window.toast) window.toast.success('Promesa de pago guardada y servicio reactivado');
            this.close();
        } catch (error) {
            console.error('Error saving promise:', error);
            const errText = error.data && error.data.error ? error.data.error : error.message;
            this.showError(errText || 'Error al guardar promesa');
        } finally {
            this.hideLoading();
        }
    }
}
