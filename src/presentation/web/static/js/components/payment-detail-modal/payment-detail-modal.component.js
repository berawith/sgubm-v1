import { BaseModal } from '../shared/base-modal.component.js';

/**
 * Componente para mostrar un informe detallado de un pago específico
 * Modal de solo lectura con formato profesional
 */
export class PaymentDetailModal extends BaseModal {
    constructor(api, eventBus) {
        super('payment-detail', api, eventBus);
        this.currentPayment = null;
        this.currentClient = null;
    }

    async init() {
        await this.loadResources(
            '/static/js/components/payment-detail-modal/payment-detail-modal.template.html'
        );
    }

    /**
     * @param {object} data - { paymentId: number }
     */
    async open(data = {}) {
        await this._initPromise;
        const paymentId = data.paymentId;

        if (!paymentId) {
            console.error('No payment ID provided to PaymentDetailModal');
            return;
        }

        // Show loading state
        super.open();
        this.showLoading();

        try {
            // Fetch payment data
            this.currentPayment = await this.api.get(`/api/payments/${paymentId}`);

            // Fetch client data
            if (this.currentPayment.client_id) {
                this.currentClient = await this.api.get(`/api/clients/${this.currentPayment.client_id}`);

                // Fetch client's full payment history for analytics (last 100 payments)
                try {
                    this.clientPaymentHistory = await this.api.get(`/api/payments?client_id=${this.currentPayment.client_id}&limit=100`);
                } catch (e) {
                    console.warn('Could not load payment history:', e);
                    this.clientPaymentHistory = [];
                }

                // Fetch client's promise history
                try {
                    this.clientPromises = await this.api.get(`/api/promises?client_id=${this.currentPayment.client_id}`);
                } catch (e) {
                    console.warn('Could not load promises:', e);
                    this.clientPromises = [];
                }
            }

            // Render the payment details
            this.renderPaymentDetails();
        } catch (error) {
            console.error('Error loading payment details:', error);
            this.showError(error.message || 'Error al cargar los detalles del pago');
        }
    }

    showLoading() {
        const container = this.modalElement.querySelector('#payment-detail-content');
        if (container) {
            container.innerHTML = `
                <div style="padding: 80px; text-align:center;">
                    <div class="spinner"></div>
                    <p style="margin-top: 20px; color: #64748b; font-weight: 600;">Cargando detalles del pago...</p>
                </div>
            `;
        }
    }

    showError(message) {
        const container = this.modalElement.querySelector('#payment-detail-content');
        if (container) {
            container.innerHTML = `
                <div style="padding: 60px; text-align:center; color: #ef4444;">
                    <i class="fas fa-exclamation-circle" style="font-size: 3rem; opacity: 0.3; margin-bottom: 20px; display: block;"></i>
                    <p style="font-weight: 600; font-size: 1.1rem; margin-bottom: 10px;">Error al cargar el pago</p>
                    <p style="font-size: 0.9rem; opacity: 0.8;">${message}</p>
                </div>
            `;
        }
    }

    /**
     * Analyze client punctuality based on payment history
     * Returns stats about on-time vs late payments
     */
    analyzePunctuality() {
        if (!this.clientPaymentHistory || this.clientPaymentHistory.length === 0) {
            return { total: 0, onTime: 0, late: 0, latePercentage: 0, timeline: [] };
        }

        const payments = this.clientPaymentHistory;
        const plan = this.currentClient;

        // Assume billing cycle day (e.g., day 5 of each month)
        const billingDay = plan?.billing_cycle_day || 5;

        let onTime = 0;
        let late = 0;
        const timeline = [];

        payments.forEach(payment => {
            const paymentDate = new Date(payment.payment_date);
            const paymentDay = paymentDate.getDate();
            const paymentMonth = paymentDate.getMonth();
            const paymentYear = paymentDate.getFullYear();

            // Calculate expected due date (billing day of payment month)
            const dueDate = new Date(paymentYear, paymentMonth, billingDay);

            // If paid before or on billing day = on time
            const isPunctual = paymentDate <= dueDate;

            if (isPunctual) {
                onTime++;
            } else {
                late++;
            }

            // Calculate days difference
            const daysDiff = Math.floor((paymentDate - dueDate) / (1000 * 60 * 60 * 24));

            timeline.push({
                date: payment.payment_date,
                amount: payment.amount,
                daysLate: daysDiff,
                isPunctual
            });
        });

        const total = payments.length;
        const onTimePercentage = total > 0 ? Math.round((onTime / total) * 100) : 0;

        return {
            total,
            onTime,
            late,
            onTimePercentage,
            timeline: timeline.slice(0, 12) // Last 12 payments
        };
    }

    /**
     * Analyze promise fulfillment
     * Returns stats about kept vs broken promises
     */
    analyzePromises() {
        if (!this.clientPromises || this.clientPromises.length === 0) {
            return { total: 0, kept: 0, broken: 0, keptPercentage: 0, promises: [] };
        }

        const promises = this.clientPromises;
        let kept = 0;
        let broken = 0;

        const promiseDetails = promises.map(promise => {
            const promiseDate = new Date(promise.promise_date);
            const now = new Date();

            // Check if promise was fulfilled
            const wasFulfilled = promise.status === 'fulfilled' || promise.fulfilled === true;

            // If promise date passed and not fulfilled = broken
            const isBroken = promiseDate < now && !wasFulfilled;

            if (wasFulfilled) {
                kept++;
            } else if (isBroken) {
                broken++;
            }

            return {
                date: promise.promise_date,
                amount: promise.amount,
                status: wasFulfilled ? 'kept' : (isBroken ? 'broken' : 'pending'),
                notes: promise.notes
            };
        });

        const total = promises.length;
        const keptPercentage = total > 0 ? Math.round((kept / total) * 100) : 0;

        return {
            total,
            kept,
            broken,
            keptPercentage,
            promises: promiseDetails.slice(0, 10)
        };
    }

    /**
     * Render the analytics section with punctuality and promise tracking
     */
    renderAnalyticsSection() {
        const punctuality = this.analyzePunctuality();
        const promises = this.analyzePromises();

        if (punctuality.total === 0 && promises.total === 0) {
            return ''; // No analytics to show
        }

        let html = '<div style="margin-bottom: 24px;">';

        // Punctuality Section
        if (punctuality.total > 0) {
            const punctualityColor = punctuality.onTimePercentage >= 80 ? '#10b981' : (punctuality.onTimePercentage >= 50 ? '#f59e0b' : '#ef4444');

            html += `
                <div class="info-section glass-panel" style="padding: 24px; border-radius: 12px; margin-bottom: 24px;">
                    <h4 style="margin: 0 0 20px 0; color: #1e293b; font-size: 1rem; font-weight: 800; display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-chart-line" style="color: #6366f1;"></i>
                        ANÁLISIS DE PUNTUALIDAD
                    </h4>
                    
                    <!-- Stats Summary -->
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px;">
                        <div style="text-align: center; padding: 15px; background: #f8fafc; border-radius: 8px;">
                            <div style="font-size: 2rem; font-weight: 900; color: #1e293b; font-family: 'JetBrains Mono', monospace;">${punctuality.total}</div>
                            <div style="font-size: 0.75rem; color: #64748b; font-weight: 600; margin-top: 5px;">TOTAL PAGOS</div>
                        </div>
                        <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, #10b98120 0%, #10b98105 100%); border-radius: 8px; border: 2px solid #10b98130;">
                            <div style="font-size: 2rem; font-weight: 900; color: #10b981; font-family: 'JetBrains Mono', monospace;">${punctuality.onTime}</div>
                            <div style="font-size: 0.75rem; color: #059669; font-weight: 600; margin-top: 5px;">A TIEMPO</div>
                        </div>
                        <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, #ef444420 0%, #ef444405 100%); border-radius: 8px; border: 2px solid #ef444430;">
                            <div style="font-size: 2rem; font-weight: 900; color: #ef4444; font-family: 'JetBrains Mono', monospace;">${punctuality.late}</div>
                            <div style="font-size: 0.75rem; color: #dc2626; font-weight: 600; margin-top: 5px;">TARDÍOS</div>
                        </div>
                        <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, ${punctualityColor}20 0%, ${punctualityColor}05 100%); border-radius: 8px; border: 2px solid ${punctualityColor}30;">
                            <div style="font-size: 2rem; font-weight: 900; color: ${punctualityColor}; font-family: 'JetBrains Mono', monospace;">${punctuality.onTimePercentage}%</div>
                            <div style="font-size: 0.75rem; color: ${punctualityColor}; font-weight: 600; margin-top: 5px;">PUNTUALIDAD</div>
                        </div>
                    </div>

                    <!-- Timeline Visualization -->
                    <div style="background: #f8fafc; padding: 20px; border-radius: 12px;">
                        <div style="font-size: 0.85rem; font-weight: 700; color: #64748b; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 0.05em;">Últimos ${punctuality.timeline.length} Pagos</div>
                        <div style="display: flex; gap: 8px; align-items: flex-end; height: 120px;">
                            ${punctuality.timeline.map(payment => {
                const height = payment.isPunctual ? 100 : 60;
                const color = payment.isPunctual ? '#10b981' : '#ef4444';
                const displayDays = Math.abs(payment.daysLate);

                return `
                                    <div style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end;">
                                        <div style="width: 100%; height: ${height}%; background: ${color}; border-radius: 6px 6px 0 0; position: relative; transition: all 0.3s;" title="${payment.isPunctual ? 'A tiempo' : displayDays + ' días tarde'} - $${payment.amount.toLocaleString()}">
                                            ${!payment.isPunctual ? `<div style="position: absolute; top: -20px; left: 50%; transform: translateX(-50%); font-size: 0.65rem; font-weight: 800; color: #ef4444; white-space: nowrap;">+${displayDays}d</div>` : ''}
                                        </div>
                                        <div style="font-size: 0.65rem; color: #94a3b8; margin-top: 5px; font-weight: 600;">${new Date(payment.date).toLocaleDateString('es-ES', { month: 'short' })}</div>
                                    </div>
                                `;
            }).join('')}
                        </div>
                        <div style="display: flex; justify-content: center; gap: 20px; margin-top: 15px; padding-top: 15px; border-top: 1px solid #e2e8f0;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <div style="width: 16px; height: 16px; background: #10b981; border-radius: 4px;"></div>
                                <span style="font-size: 0.8rem; color: #64748b; font-weight: 600;">A Tiempo</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <div style="width: 16px; height: 16px; background: #ef4444; border-radius: 4px;"></div>
                                <span style="font-size: 0.8rem; color: #64748b; font-weight: 600;">Tardío</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        //Promise Tracker Section
        if (promises.total > 0) {
            const promiseColor = promises.keptPercentage >= 80 ? '#10b981' : (promises.keptPercentage >= 50 ? '#f59e0b' : '#ef4444');

            html += `
                <div class="info-section glass-panel" style="padding: 24px; border-radius: 12px; margin-bottom: 24px;">
                    <h4 style="margin: 0 0 20px 0; color: #1e293b; font-size: 1rem; font-weight: 800; display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-handshake" style="color: #6366f1;"></i>
                        SEGUIMIENTO DE PROMESAS DE PAGO
                    </h4>
                    
                    <!-- Promise Stats -->
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px;">
                        <div style="text-align: center; padding: 15px; background: #f8fafc; border-radius: 8px;">
                            <div style="font-size: 2rem; font-weight: 900; color: #1e293b; font-family: 'JetBrains Mono', monospace;">${promises.total}</div>
                            <div style="font-size: 0.75rem; color: #64748b; font-weight: 600; margin-top: 5px;">TOTAL</div>
                        </div>
                        <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, #10b98120 0%, #10b98105 100%); border-radius: 8px; border: 2px solid #10b98130;">
                            <div style="font-size: 2rem; font-weight: 900; color: #10b981; font-family: 'JetBrains Mono', monospace;">${promises.kept}</div>
                            <div style="font-size: 0.75rem; color: #059669; font-weight: 600; margin-top: 5px;">CUMPLIDAS</div>
                        </div>
                        <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, #ef444420 0%, #ef444405 100%); border-radius: 8px; border: 2px solid #ef444430;">
                            <div style="font-size: 2rem; font-weight: 900; color: #ef4444; font-family: 'JetBrains Mono', monospace;">${promises.broken}</div>
                            <div style="font-size: 0.75rem; color: #dc2626; font-weight: 600; margin-top: 5px;">INCUMPLIDAS</div>
                        </div>
                        <div style="text-align: center; padding: 15px; background: linear-gradient(135deg, ${promiseColor}20 0%, ${promiseColor}05 100%); border-radius: 8px; border: 2px solid ${promiseColor}30;">
                            <div style="font-size: 2rem; font-weight: 900; color: ${promiseColor}; font-family: 'JetBrains Mono', monospace;">${promises.keptPercentage}%</div>
                            <div style="font-size: 0.75rem; color: ${promiseColor}; font-weight: 600; margin-top: 5px;">CUMPLIMIENTO</div>
                        </div>
                    </div>

                    <!-- Risk Badge -->
                    <div style="text-align: center; padding: 15px; background: ${promiseColor}10; border-radius: 12px; border: 2px solid ${promiseColor}30;">
                        <div style="display: inline-flex; align-items: center; gap: 10px; padding: 10px 20px; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                            <i class="fas ${promises.keptPercentage >= 80 ? 'fa-check-circle' : (promises.keptPercentage >= 50 ? 'fa-exclamation-triangle' : 'fa-times-circle')}" style="color: ${promiseColor}; font-size: 1.5rem;"></i>
                            <div style="text-align: left;">
                                <div style="font-size: 0.75rem; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Nivel de Riesgo</div>
                                <div style="font-size: 1.1rem; font-weight: 800; color: ${promiseColor};">${promises.keptPercentage >= 80 ? 'BAJO - Cliente Confiable' : (promises.keptPercentage >= 50 ? 'MEDIO - Monitorear' : 'ALTO - Requiere Atención')}</div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        html += '</div>';
        return html;
    }

    renderPaymentDetails() {
        const container = this.modalElement.querySelector('#payment-detail-content');
        if (!container || !this.currentPayment) return;

        const p = this.currentPayment;
        const c = this.currentClient || {};
        const details = p.details || [];

        // Method map
        const methodMap = {
            'cash': { name: 'Efectivo', icon: 'fa-wallet', color: '#10b981' },
            'efectivo': { name: 'Efectivo', icon: 'fa-wallet', color: '#10b981' },
            'transfer': { name: 'Transferencia', icon: 'fa-university', color: '#3b82f6' },
            'transferencia': { name: 'Transferencia', icon: 'fa-university', color: '#3b82f6' },
            'card': { name: 'Tarjeta', icon: 'fa-credit-card', color: '#8b5cf6' },
            'zelle': { name: 'Zelle', icon: 'fa-dollar-sign', color: '#6366f1' },
            'pago_movil': { name: 'Pago Móvil', icon: 'fa-mobile-alt', color: '#ec4899' },
            'binance': { name: 'Binance', icon: 'fa-bitcoin', color: '#f59e0b' },
            'mixed': { name: 'Mixto', icon: 'fa-layer-group', color: '#8b5cf6' },
            'other': { name: 'Otro', icon: 'fa-money-bill-wave', color: '#64748b' }
        };

        const method = methodMap[p.payment_method] || methodMap['other'];

        // Status map
        const statusMap = {
            'paid': { name: 'PAGADO', class: 'success', icon: 'fa-check-circle', color: '#10b981' },
            'verified': { name: 'VERIFICADO', class: 'success', icon: 'fa-check-double', color: '#10b981' },
            'pending': { name: 'PENDIENTE', class: 'warning', icon: 'fa-clock', color: '#f59e0b' },
            'cancelled': { name: 'ANULADO', class: 'danger', icon: 'fa-times-circle', color: '#ef4444' }
        };

        const status = statusMap[p.status] || statusMap['pending'];

        // Build parts breakdown HTML
        let partsHtml = '';
        if (details.length > 0) {
            partsHtml = `
                <div class="pd-section" style="margin-bottom: 16px;">
                    <div class="pd-section-title">
                        <i class="fas fa-layer-group" style="color: #8b5cf6;"></i>
                        DESGLOSE DE MODALIDADES (${details.length})
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        ${details.map(d => {
                const dm = methodMap[d.method] || methodMap['other'];
                return `
                            <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: ${dm.color}08; border: 1px solid ${dm.color}20; border-radius: 10px; transition: all 0.2s;">
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <div style="width: 32px; height: 32px; border-radius: 8px; background: ${dm.color}15; display: flex; align-items: center; justify-content: center;">
                                        <i class="fas ${dm.icon}" style="color: ${dm.color}; font-size: 0.8rem;"></i>
                                    </div>
                                    <div>
                                        <div style="font-weight: 700; font-size: 0.8rem; color: #1e293b;">${dm.name}</div>
                                        ${d.reference ? `<div style="font-size: 0.7rem; color: #94a3b8; font-family: 'JetBrains Mono', monospace;">Ref: ${d.reference}</div>` : ''}
                                        ${d.currency !== (p.currency || 'COP') ? `<div style="font-size: 0.65rem; color: #94a3b8;">${d.currency} · Tasa: ${d.exchange_rate}</div>` : ''}
                                    </div>
                                </div>
                                <div style="text-align: right;">
                                    <div style="font-family: 'JetBrains Mono', monospace; font-weight: 800; font-size: 0.9rem; color: #1e293b;">$${(d.amount || 0).toLocaleString('es-CO', { minimumFractionDigits: 0 })}</div>
                                    <div style="font-size: 0.65rem; color: #94a3b8; font-weight: 600;">${d.currency || 'COP'}</div>
                                </div>
                            </div>`;
            }).join('')}
                    </div>
                </div>`;
        }

        const html = `
            <div class="payment-detail-report" style="font-size: 0.85rem;">
                <!-- Compact Header -->
                <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); padding: 20px 24px; border-radius: 14px; color: white; margin-bottom: 16px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <div style="display: flex; align-items: center; gap: 12px;">
                            <div style="font-family: 'JetBrains Mono', monospace; font-size: 1.4rem; font-weight: 800; letter-spacing: -0.02em;">#${String(p.id).padStart(4, '0')}</div>
                            <span style="font-size: 0.7rem; padding: 4px 10px; background: ${status.color}30; border: 1px solid ${status.color}60; border-radius: 6px; font-weight: 700; color: ${status.color}; letter-spacing: 0.05em;">
                                <i class="fas ${status.icon}" style="margin-right: 4px;"></i>${status.name}
                            </span>
                        </div>
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 900; color: #4ade80;">
                            $${p.amount.toLocaleString('es-CO', { minimumFractionDigits: 0 })}
                        </div>
                    </div>
                    <div style="display: flex; gap: 20px; font-size: 0.75rem; opacity: 0.7;">
                        <span><i class="far fa-calendar-alt" style="margin-right: 6px;"></i>${new Date(p.payment_date).toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}</span>
                        <span><i class="far fa-clock" style="margin-right: 6px;"></i>${new Date(p.payment_date).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}</span>
                        <span style="margin-left: auto;"><i class="fas fa-coins" style="margin-right: 4px;"></i>${p.currency || 'COP'}</span>
                    </div>
                </div>

                <!-- Client + Method Row -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
                    <div class="pd-section">
                        <div class="pd-section-title">
                            <i class="fas fa-user" style="color: #6366f1;"></i> CLIENTE
                        </div>
                        <div class="pd-row"><span class="pd-label">Nombre</span><span class="pd-val">${c.legal_name || '---'}</span></div>
                        <div class="pd-row"><span class="pd-label">Código</span><span class="pd-val" style="font-family: 'JetBrains Mono', monospace;">${c.subscriber_code || '---'}</span></div>
                        <div class="pd-row"><span class="pd-label">Documento</span><span class="pd-val">${c.identity_document || '---'}</span></div>
                        <div class="pd-row"><span class="pd-label">Plan</span><span class="pd-val">${c.plan_name || '---'}</span></div>
                    </div>
                    <div class="pd-section">
                        <div class="pd-section-title">
                            <i class="fas fa-receipt" style="color: #10b981;"></i> TRANSACCIÓN
                        </div>
                        <div class="pd-row">
                            <span class="pd-label">Método</span>
                            <span style="display: inline-flex; align-items: center; gap: 5px; background: ${method.color}12; color: ${method.color}; padding: 3px 10px; border-radius: 6px; font-weight: 700; font-size: 0.75rem;">
                                <i class="fas ${method.icon}"></i> ${method.name}
                            </span>
                        </div>
                        <div class="pd-row"><span class="pd-label">Referencia</span><span class="pd-val" style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;">${p.reference || 'N/A'}</span></div>
                        ${p.registered_by ? `<div class="pd-row"><span class="pd-label">Registrado por</span><span class="pd-val">${p.registered_by}</span></div>` : ''}
                        ${p.notes ? `<div class="pd-row" style="flex-wrap: wrap;"><span class="pd-label">Notas</span><span class="pd-val" style="font-style: italic; color: #64748b; font-weight: 500;">${p.notes}</span></div>` : ''}
                    </div>
                </div>

                <!-- Payment Parts Breakdown -->
                ${partsHtml}

                ${this.renderAnalyticsSection()}

                <!-- Print Button -->
                <div style="text-align: center; padding: 12px 0 4px;">
                    <button class="btn-primary" onclick="app.modules.payments.printReceipt(${p.id})" style="padding: 10px 28px; font-size: 0.85rem; background: #1e293b; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                        <i class="fas fa-print" style="margin-right: 8px;"></i> Imprimir Recibo
                    </button>
                </div>
            </div>

            <style>
                .pd-section {
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 12px;
                    padding: 16px;
                }
                .pd-section-title {
                    font-size: 0.7rem;
                    font-weight: 800;
                    color: #475569;
                    text-transform: uppercase;
                    letter-spacing: 0.08em;
                    margin-bottom: 12px;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                }
                .pd-row {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 6px 0;
                    border-bottom: 1px solid #f1f5f9;
                }
                .pd-row:last-child { border-bottom: none; }
                .pd-label {
                    font-size: 0.75rem;
                    color: #94a3b8;
                    font-weight: 600;
                }
                .pd-val {
                    font-size: 0.8rem;
                    color: #1e293b;
                    font-weight: 700;
                    text-align: right;
                }
            </style>
        `;

        container.innerHTML = html;
    }
}
