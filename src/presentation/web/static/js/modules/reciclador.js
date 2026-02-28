/**
 * Reciclador Module - Proactive Error Sentinel Console
 */
export class RecicladorModule {
    constructor(api, eventBus, viewManager) {
        this.api = api;
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.incidents = [];
        this.stats = { new: 0, critical: 0, resolved: 0 };

        console.log('🛡️ Reciclador Sentinel Module initialized');
        this.initEventListeners();
    }

    initEventListeners() {
        // Escuchar nuevos incidentes en tiempo real
        this.eventBus.subscribe('data_refresh', (data) => {
            if (data.event_type === 'system.incident_reported') {
                console.warn('🚨 NEW INCIDENT CAPTURED BY RECICLADOR:', data.incident);
                this.incidents.unshift(data.incident);
                this.updateStats();

                if (this.viewManager.currentSubView === 'system-reciclador') {
                    this.renderIncidents();
                } else {
                    // Notificación tipo Toast si el admin está en otra parte
                    if (window.toast) {
                        window.toast.error(`Centinela: Error detectado en ${data.incident.module}`, 'Ver Consola');
                    }
                }
            }
        });
    }

    async load() {
        console.log('🛡️ Loading Reciclador Console...');

        try {
            await Promise.all([
                this.loadIncidents(),
                this.loadStats()
            ]);
        } catch (e) {
            console.error('Error loading Reciclador data:', e);
        }
    }

    async loadIncidents() {
        try {
            this.incidents = await this.api.get('/api/reciclador/incidents?status=new&limit=50');
            this.renderIncidents();
        } catch (e) {
            console.error(e);
        }
    }

    async loadStats() {
        try {
            const data = await this.api.get('/api/reciclador/stats');
            this.stats = data;
            this.updateStatsUI();
        } catch (e) {
            console.error(e);
        }
    }

    updateStats() {
        this.stats.new_incidents++;
        this.updateStatsUI();
    }

    updateStatsUI() {
        const newEl = document.getElementById('reciclador-stat-new');
        const critEl = document.getElementById('reciclador-stat-critical');
        if (newEl) newEl.textContent = this.stats.new_incidents || 0;
        if (critEl) critEl.textContent = this.stats.critical_incidents || 0;
    }

    renderIncidents() {
        const tbody = document.getElementById('reciclador-incidents-body');
        if (!tbody) return;

        if (this.incidents.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 6rem; opacity:0.3;">El centinela no ha detectado errores recientes.</td></tr>';
            return;
        }

        let html = '';
        let lastDateLabel = '';

        this.incidents.forEach(i => {
            const dateObj = new Date(i.created_at);
            const now = new Date();

            // Normalize dates to midnight for accurate day comparison
            const dateNormalized = new Date(dateObj.getFullYear(), dateObj.getMonth(), dateObj.getDate());
            const todayNormalized = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            const yesterdayNormalized = new Date(todayNormalized);
            yesterdayNormalized.setDate(yesterdayNormalized.getDate() - 1);

            let dateLabel = '';
            if (dateNormalized.getTime() === todayNormalized.getTime()) {
                dateLabel = 'HOY';
            } else if (dateNormalized.getTime() === yesterdayNormalized.getTime()) {
                dateLabel = 'AYER';
            } else {
                dateLabel = dateObj.toLocaleDateString('es-ES', { day: '2-digit', month: 'long', year: 'numeric' }).toUpperCase();
            }

            if (dateLabel !== lastDateLabel) {
                html += `
                    <tr>
                        <td colspan="4" class="date-group-header">
                            <i class="far fa-calendar-alt"></i> ${dateLabel}
                        </td>
                    </tr>
                `;
                lastDateLabel = dateLabel;
            }

            const dateStr = dateObj.toLocaleDateString('es-ES', { day: '2-digit', month: 'short' });
            const hourStr = dateObj.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });

            html += `
                <tr class="incident-row ${i.severity}" onclick="app.modules.reciclador.showIncidentDetail(${i.id})">
                    <td>
                        <span class="severity-badge ${i.severity}">${i.severity}</span>
                    </td>
                    <td>
                        <span class="module-breadcrumb">${i.module}</span>
                        <div class="error-tag">${i.error_type}</div>
                    </td>
                    <td>
                        <div style="font-size: 0.9rem; color: #475569; max-width: 500px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight:500;">
                            ${i.message}
                        </div>
                    </td>
                    <td class="time-cell">
                        <span class="hour">${hourStr}</span>
                        <span class="date">${dateStr}</span>
                    </td>
                </tr>
            `;
        });

        tbody.innerHTML = html;
    }

    async showIncidentDetail(id) {
        try {
            const incident = await this.api.get(`/api/reciclador/incidents/${id}`);

            // Parse AI Analysis
            let aiAnalysis = { diagnosis: "Analizando...", solution_steps: [], risk_level: 'medium' };
            try {
                if (incident.ai_analysis) {
                    aiAnalysis = typeof incident.ai_analysis === 'string' ? JSON.parse(incident.ai_analysis) : incident.ai_analysis;
                }
            } catch (e) { console.error("Error parsing AI analysis", e); }

            const riskColors = { high: '#ef4444', medium: '#f59e0b', low: '#10b981' };

            const aiBoxHtml = `
                <div style="background: rgba(99, 102, 241, 0.05); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 16px; padding: 20px; margin-bottom: 20px; position: relative; overflow: hidden;">
                    <div style="position: absolute; top: -10px; right: -10px; font-size: 4rem; opacity: 0.05; color: #6366f1;">
                        <i class="fas fa-brain"></i>
                    </div>
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
                        <span style="background: #6366f1; color: white; padding: 4px 10px; border-radius: 8px; font-size: 0.7rem; font-weight: 800; letter-spacing: 1px;">DIAGNÓSTICO IA</span>
                        <span style="font-size: 0.7rem; font-weight: 700; color: ${riskColors[aiAnalysis.risk_level] || '#64748b'}">NIVEL DE RIESGO: ${aiAnalysis.risk_level?.toUpperCase()}</span>
                    </div>
                    <div style="font-size: 1rem; font-weight: 700; color: #1e293b; margin-bottom: 15px; line-height: 1.4;">
                        ${aiAnalysis.diagnosis}
                    </div>
                    <div style="color: #475569; font-size: 0.85rem; font-weight: 600; margin-bottom: 8px;">PLAN DE ACCIÓN SUGERIDO:</div>
                    <ul style="margin: 0; padding-left: 20px; color: #64748b; font-size: 0.85rem; line-height: 1.6;">
                        ${aiAnalysis.solution_steps.map(step => `<li>${step}</li>`).join('')}
                    </ul>
                </div>
            `;

            const stackHtml = `
                <div style="text-align: left; font-family: 'Inter', sans-serif;">
                    ${aiBoxHtml}
                    
                    <div style="margin-bottom: 15px;">
                        <div style="font-weight: 800; font-size: 0.75rem; color: #94a3b8; margin-bottom: 8px; letter-spacing: 1px; text-transform: uppercase;">Trazabilidad Técnica (Stack Trace)</div>
                        <div style="background: #0f172a; color: #38bdf8; padding: 1.5rem; border-radius: 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; max-height: 250px; overflow-y: auto; box-shadow: inset 0 2px 10px rgba(0,0,0,0.5);">
                            <pre style="margin:0; white-space: pre-wrap;">${incident.stack_trace}</pre>
                        </div>
                    </div>

                    <div style="background: #f8fafc; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0; display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                        <div>
                            <div style="font-size: 0.65rem; font-weight: 800; color: #94a3b8; margin-bottom: 4px;">REQUEST URL</div>
                            <div style="font-family: monospace; font-size: 0.7rem; color: #475569;">${incident.url || 'N/A'}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.65rem; font-weight: 800; color: #94a3b8; margin-bottom: 4px;">AUTHENTICATED USER</div>
                            <div style="font-family: monospace; font-size: 0.7rem; color: #475569;">${incident.username || 'Anonymous'} (${incident.ip_address || 'Unknown IP'})</div>
                        </div>
                    </div>
                </div>
            `;

            if (window.Swal) {
                Swal.fire({
                    title: `<div style="font-weight:900; letter-spacing:-0.02em;">ANALIZADOR CENTINELA</div>`,
                    html: stackHtml,
                    width: '850px',
                    showCancelButton: true,
                    confirmButtonText: '<i class="fas fa-check-circle"></i> Aplicar Solución y Cerrar',
                    cancelButtonText: 'Mantener Abierto',
                    confirmButtonColor: '#10b981',
                    background: '#ffffff',
                    customClass: {
                        popup: 'premium-swal-popup',
                        title: 'premium-swal-title',
                        confirmButton: 'premium-swal-confirm'
                    }
                }).then(result => {
                    if (result.isConfirmed) {
                        this.resolveIncident(id);
                    }
                });
            }
        } catch (e) {
            console.error(e);
        }
    }

    async resolveIncident(id) {
        try {
            const { value: notes } = await Swal.fire({
                title: 'Confirmar Resolución',
                input: 'text',
                inputLabel: 'Notas de reparación aplicada:',
                inputValue: 'Solución sugerida por IA aplicada correctamente.',
                showCancelButton: true,
                confirmButtonColor: '#10b981'
            });

            if (notes) {
                await this.api.put(`/api/reciclador/incidents/${id}/resolve`, { notes });
                if (window.toast) window.toast.success('Incidente resuelto y archivado.');
                this.loadIncidents();
                this.loadStats();
            }
        } catch (e) {
            console.error(e);
        }
    }
}
