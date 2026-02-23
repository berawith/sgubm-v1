import toast from '../components/toast.js';

export class MetricsModule {
    constructor(apiService, eventBus, viewManager) {
        this.api = apiService;
        this.events = eventBus;
        this.viewManager = viewManager;
        this.stabilityChart = null;
        this.trafficChart = null;
        this.initialized = false;

        // Variables for LHI and Live Telemetry
        this.currentClientId = null;
        this.socketInitialized = false;
        this.trafficBuffer = [];
        this.lastChartUpdate = 0;
        this.trafficRange = 'live'; // 'live', '24h', '7d'
    }

    async load() {
        console.log('📊 Loading Metrics Module...');
        this.viewManager.showMainView('metrics');

        if (!this.initialized) {
            setTimeout(() => {
                this.bindEvents();
            }, 100);
            this.initialized = true;
        }
    }

    bindEvents() {
        const btnSearch = document.getElementById('btn-metrics-search');
        const inputSearch = document.getElementById('metrics-search-input');
        let searchTimeout;

        if (btnSearch && inputSearch) {
            btnSearch.addEventListener('click', () => {
                const resultsContainer = document.getElementById('metrics-search-results');
                if (resultsContainer) resultsContainer.style.display = 'none';
                this.performSearch(inputSearch.value, false);
            });

            inputSearch.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    clearTimeout(searchTimeout);
                    const resultsContainer = document.getElementById('metrics-search-results');
                    if (resultsContainer) resultsContainer.style.display = 'none';
                    this.performSearch(inputSearch.value, false);
                }
            });

            // Autocomplete functionality
            inputSearch.addEventListener('input', (e) => {
                const term = e.target.value;
                clearTimeout(searchTimeout);

                const resultsContainer = document.getElementById('metrics-search-results');

                if (term && term.trim().length >= 2) {
                    if (resultsContainer) {
                        resultsContainer.style.display = 'block';
                        resultsContainer.innerHTML = '<div style="padding: 16px; text-align: center; color: #94a3b8; font-size: 0.85rem;"><i class="fas fa-circle-notch fa-spin"></i> Buscando...</div>';
                    }
                    searchTimeout = setTimeout(() => {
                        this.performSearch(term, true);
                    }, 350);
                } else {
                    if (resultsContainer) resultsContainer.style.display = 'none';
                }
            });
        }

        // Range selector for traffic (Live, 24h, 7d)
        document.querySelectorAll('.traffic-range-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const range = e.target.closest('button').dataset.range;
                this.updateTrafficRange(range);
            });
        });

        // LHI Modal Events (Clean and simple with onclick)
        const btnLhiDetail = document.getElementById('btn-metrics-lhi-detail');
        const lhiModal = document.getElementById('lhi-detail-modal');

        if (btnLhiDetail && lhiModal) {
            btnLhiDetail.onclick = (e) => {
                e.preventDefault();
                lhiModal.classList.add('active');
                lhiModal.style.setProperty('display', 'flex', 'important');
                lhiModal.style.setProperty('z-index', '999999', 'important');
            };

            // Close when clicking outside
            lhiModal.onclick = (e) => {
                if (e.target === lhiModal) {
                    lhiModal.classList.remove('active');
                    lhiModal.style.setProperty('display', 'none', 'important');
                }
            };

            // Close on close buttons
            const closeBtns = lhiModal.querySelectorAll('.btn-close-modal');
            closeBtns.forEach(btn => {
                btn.onclick = () => {
                    lhiModal.classList.remove('active');
                    lhiModal.style.setProperty('display', 'none', 'important');
                };
            });
        }

        // Inicializar Telemetría en Vivo
        if (window.app && window.app.socket && !this.socketInitialized) {
            window.app.socket.on('client_traffic', (data) => {
                if (!data || !this.currentClientId || !data[this.currentClientId]) return;

                // Validar que la vista actual sea metrics
                const currentView = this.viewManager.currentView;
                if (currentView !== 'metrics' || document.hidden) return;

                const info = data[this.currentClientId];
                const liveContainer = document.getElementById('metrics-live-consumption');

                if (info && info.status === 'online') {
                    if (liveContainer) {
                        liveContainer.style.setProperty('display', 'flex', 'important');
                        liveContainer.style.opacity = '1';
                        liveContainer.style.filter = 'none';
                    }
                    this.updateLiveConsumptionUI(info.download, info.upload);

                    // Solo actualizar el gráfico si estamos en modo LIVE
                    if (this.trafficRange !== 'live') return;

                    // Actualizar gráfico en vivo (Throttled a 2s)
                    const now = Date.now();
                    this.trafficBuffer.push({
                        timestamp: now,
                        download_bps: info.download,
                        upload_bps: info.upload
                    });

                    // Mantener solo los últimos 30 puntos (aprox 1 minuto a 2s/p)
                    if (this.trafficBuffer.length > 30) this.trafficBuffer.shift();

                    if (now - this.lastChartUpdate > 2000) {
                        this.renderTrafficChart(this.trafficBuffer, true);
                        this.lastChartUpdate = now;
                    }
                } else {
                    if (liveContainer) {
                        liveContainer.style.setProperty('display', 'flex', 'important');
                        liveContainer.style.opacity = '0.3';
                        liveContainer.style.filter = 'grayscale(100%)';
                        this.updateLiveConsumptionUI(0, 0);
                    }
                }
            });
            this.socketInitialized = true;
        }
    }

    async performSearch(term, isAutocomplete = false) {
        if (!term || term.trim() === '') {
            if (!isAutocomplete) toast.warning('Ingrese un término de búsqueda');
            return;
        }

        const placeholder = document.getElementById('metrics-placeholder');
        const dashboard = document.getElementById('metrics-dashboard');
        const resultsContainer = document.getElementById('metrics-search-results');

        if (!isAutocomplete && window.app) window.app.showLoading(true);

        try {
            // Ampliamos el límite para permitir seleccionar entre coincidencias
            const response = await this.api.get(`/api/clients?search=${encodeURIComponent(term)}&limit=10`);

            let clientList = [];
            if (response && response.clients) {
                clientList = response.clients;
            } else if (Array.isArray(response)) {
                clientList = response;
            } else if (response && response.items) {
                clientList = response.items;
            }

            if (clientList && clientList.length > 0) {
                this.renderSearchResults(clientList);
            } else {
                if (isAutocomplete) {
                    if (resultsContainer) {
                        resultsContainer.innerHTML = '<div style="padding: 16px; text-align: center; color: #94a3b8; font-size: 0.85rem;">No se encontraron objetivos</div>';
                        resultsContainer.style.display = 'block';
                    }
                } else {
                    if (resultsContainer) resultsContainer.style.display = 'none';
                    toast.warning('No se encontraron objetivos coincidentes');
                    placeholder.style.display = 'flex';
                    dashboard.style.display = 'none';
                }
            }
        } catch (error) {
            console.error('Error searching metrics target:', error);
            if (!isAutocomplete) toast.error('Error al consultar telemetría');
            placeholder.style.display = 'flex';
            dashboard.style.display = 'none';
            if (resultsContainer) resultsContainer.style.display = 'none';
        } finally {
            if (!isAutocomplete && window.app) window.app.showLoading(false);
        }
    }

    renderSearchResults(clients) {
        const resultsContainer = document.getElementById('metrics-search-results');
        if (!resultsContainer) return;

        resultsContainer.innerHTML = clients.map(c => `
            <div class="metrics-search-item" style="padding: 16px; margin-bottom: 4px; border-radius: 12px; cursor: pointer; display: flex; align-items: center; gap: 16px; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); background: transparent;" onmouseover="this.style.background='#f8fafc'; this.style.transform='translateX(6px)';" onmouseout="this.style.background='transparent'; this.style.transform='translateX(0)';">
                <!-- Avatar -->
                <div style="background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%); width: 44px; height: 44px; min-width: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1.1rem; color: #4338ca; box-shadow: inset 0 2px 4px rgba(255,255,255,0.5);">
                    ${(c.legal_name || '?').charAt(0).toUpperCase()}
                </div>
                <!-- Info -->
                <div style="flex: 1; overflow: hidden;">
                    <div style="font-weight: 800; color: #0f172a; font-size: 1.05rem; letter-spacing: -0.01em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${c.legal_name}</div>
                    <div style="display: flex; gap: 8px; align-items: center; margin-top: 6px; flex-wrap: wrap;">
                        <span style="font-size: 0.70rem; font-weight: 700; color: #475569; background: #f1f5f9; padding: 2px 8px; border-radius: 6px; display: inline-flex; align-items: center; gap: 4px;">
                            <i class="fas fa-network-wired" style="color: #64748b;"></i>${c.ip_address || 'Sin IP'}
                        </span>
                        <span style="font-size: 0.70rem; font-weight: 700; color: #475569; background: #f8fafc; padding: 2px 8px; border-radius: 6px; border: 1px solid #e2e8f0; display: inline-flex; align-items: center; gap: 4px;">
                            <i class="fas fa-server" style="color: #64748b;"></i>${c.router ? c.router : 'Nodo ' + c.router_id}
                        </span>
                        ${c.status === 'suspended' ? '<span style="font-size: 0.70rem; font-weight: 800; color: #ef4444; background: #fee2e2; padding: 2px 8px; border-radius: 6px; border: 1px solid #fecaca; text-transform: uppercase;">Suspendido</span>' : ''}
                    </div>
                </div>
                <!-- Action Icon -->
                <div style="color: #8b5cf6; padding: 8px; background: #ede9fe; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; opacity: 0.8; transition: all 0.2s;" class="action-btn">
                    <i class="fas fa-arrow-right"></i>
                </div>
            </div>
        `).join('');

        // Adjuntar eventos
        const items = resultsContainer.querySelectorAll('.metrics-search-item');
        items.forEach((item, index) => {
            item.addEventListener('click', () => {
                const client = clients[index];
                document.getElementById('metrics-search-input').value = client.legal_name;
                resultsContainer.style.display = 'none';

                document.getElementById('metrics-placeholder').style.display = 'none';
                document.getElementById('metrics-dashboard').style.display = 'block';

                if (window.app) window.app.showLoading(true);
                this.loadClientMetrics(client).finally(() => {
                    if (window.app) window.app.showLoading(false);
                });
            });
        });

        resultsContainer.style.display = 'block';

        // Cierra el menu clickeando afuera
        const outsideClickListener = (e) => {
            if (!document.getElementById('metrics-search-input').contains(e.target) && !resultsContainer.contains(e.target)) {
                resultsContainer.style.display = 'none';
                document.removeEventListener('click', outsideClickListener);
            }
        };
        document.addEventListener('click', outsideClickListener);
    }

    async loadClientMetrics(client) {
        // Desuscribirse del anterior si existía
        if (this.currentClientId && window.app && window.app.socket) {
            window.app.socket.emit('unsubscribe_clients', { client_ids: [this.currentClientId] });
        }

        this.currentClientId = client.id;
        this.trafficBuffer = []; // Limpiar buffer de tiempo real

        // Suscribirse al nuevo
        if (window.app && window.app.socket) {
            window.app.socket.emit('subscribe_clients', { router_id: null, client_ids: [client.id] });
        }

        // Set basic data
        document.getElementById('metrics-target-name').textContent = client.legal_name || 'Desconocido';
        document.getElementById('metrics-target-type').textContent = `CLIENTE: ${client.ip_address || 'Sin IP'} - ${client.service_type || 'N/A'}`;

        // Limpiar widgets live por defecto hasta recibir datos
        const liveContainer = document.getElementById('metrics-live-consumption');
        if (liveContainer) {
            liveContainer.style.setProperty('display', 'none', 'important');
            liveContainer.style.opacity = '1';
            liveContainer.style.filter = 'none';
        }

        const now = new Date();
        document.getElementById('metrics-last-sync').textContent = now.toLocaleTimeString();

        // Limpiar gráfico previo visualmente
        this.renderTrafficChart([], false);

        // Obtener historial analítico
        try {
            const usageData = await this.api.get(`/api/clients/${client.id}/usage-report?days=7`);

            this.updateIntelligencePanel(usageData.intelligence || {});

            if (usageData.history_raw) {
                this.renderStabilityChart(usageData.history_raw);
                this.renderTelemetryTable(usageData.history_raw);
            } else {
                this.renderStabilityChart([]);
                this.renderTelemetryTable([]);
            }

            // Para tráfico usamos traffic-history (Default 24h para inicializar cache)
            await this.fetchTrafficHistory();

        } catch (e) {
            console.error('Error loading detailed metrics:', e);
            toast.error('Fallo al obtener métricas avanzadas (LHI)');
        }
    }

    updateLiveConsumptionUI(rxBits, txBits) {
        const rxEl = document.getElementById('metrics-live-rx');
        const txEl = document.getElementById('metrics-live-tx');

        if (rxEl) rxEl.innerHTML = this.formatSpeedHTML(rxBits);
        if (txEl) txEl.innerHTML = this.formatSpeedHTML(txBits);
    }

    formatSpeedHTML(bits) {
        const b = parseInt(bits);
        if (isNaN(b) || b === 0) return `0.00 <span style="font-size: 0.75rem; color: #64748b; font-weight: 700;">Kbps</span>`;

        if (b < 1000) return `${b} <span style="font-size: 0.75rem; color: #64748b; font-weight: 700;">bps</span>`;
        if (b < 1000000) return `${(b / 1000).toFixed(1)} <span style="font-size: 0.75rem; color: #64748b; font-weight: 700;">Kbps</span>`;
        return `${(b / 1000000).toFixed(2)} <span style="font-size: 0.75rem; color: #64748b; font-weight: 700;">Mbps</span>`;
    }

    updateIntelligencePanel(intel) {
        document.getElementById('metrics-profile').textContent = intel.user_profile || 'Normal';
        document.getElementById('metrics-estimated-gb').textContent = (intel.predicted_monthly_gb || 0) + ' GB';
        document.getElementById('metrics-peak-hour').textContent = intel.peak_hour || '--:--';

        const recomEl = document.getElementById('metrics-ai-recommendation');
        if (recomEl) {
            recomEl.textContent = intel.recommended_plan || 'Plan Óptimo';
            recomEl.style.color = (intel.recommended_plan && intel.recommended_plan.toLowerCase().includes('upgrade')) ? '#f59e0b' : '#10b981';
        }
    }

    renderStabilityChart(history) {
        let canvas = document.getElementById('metrics-stability-chart');
        if (!canvas) return;

        const container = canvas.parentElement;

        if (this.stabilityChart) {
            this.stabilityChart.destroy();
            this.stabilityChart = null;
        }

        const lhiBadge = document.getElementById('metrics-lhi-badge');
        const btnLhiDetail = document.getElementById('btn-metrics-lhi-detail');

        if (!history || history.length === 0) {
            canvas.style.display = 'none';
            if (btnLhiDetail) btnLhiDetail.style.display = 'none';
            container.innerHTML = `<div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #94a3b8; font-weight: 700; font-family: 'JetBrains Mono', 'Courier New', monospace;"><i class="fas fa-satellite-dish" style="font-size: 3rem; margin-bottom: 16px; opacity: 0.3;"></i><span style="letter-spacing: 0.1em; font-size: 0.8rem;">TELEMETRÍA OFFLINE</span></div>`;
            return;
        }

        if (btnLhiDetail) btnLhiDetail.style.display = 'flex';

        // Re-establish canvas if it was destroyed by innerHTML
        if (!document.getElementById('metrics-stability-chart')) {
            container.innerHTML = '<canvas id="metrics-stability-chart"></canvas>';
            canvas = document.getElementById('metrics-stability-chart');
        }

        canvas.style.display = 'block';
        canvas.style.width = '100%';
        canvas.style.height = '100%';

        const ctx = canvas.getContext('2d');

        // Calcular LHI Global
        let totalScore = 0;
        let validSamples = 0;
        let sumPing = 0, sumJitter = 0, sumLoss = 0;

        history.forEach(h => {
            if (!h.is_online) return;
            validSamples++;
            sumPing += h.latency_ms || 0;
            sumJitter += h.jitter_ms || 0;
            sumLoss += h.packet_loss_pct || 0;

            let sampleScore = 100;
            if (h.latency_ms > 40) sampleScore -= Math.min(30, (h.latency_ms - 40) * 0.25);
            if (h.jitter_ms > 8) sampleScore -= Math.min(25, (h.jitter_ms - 8) * 0.8);
            if (h.packet_loss_pct > 0) sampleScore -= Math.min(100, h.packet_loss_pct * 8);
            totalScore += Math.max(0, sampleScore);
        });

        const finalLhi = validSamples > 0 ? Math.round(totalScore / validSamples) : 0;
        const avgPing = validSamples > 0 ? Math.round(sumPing / validSamples) : 0;
        const avgJitter = validSamples > 0 ? (sumJitter / validSamples).toFixed(1) : 0;
        const avgLoss = validSamples > 0 ? (sumLoss / validSamples).toFixed(1) : 0;

        // Renderizar LHI Badge
        if (lhiBadge) {
            const lhiColor = finalLhi >= 90 ? '#10b981' : (finalLhi >= 70 ? '#f59e0b' : '#ef4444');
            const lhiBgColor = finalLhi >= 90 ? '16, 185, 129' : (finalLhi >= 70 ? '245, 158, 11' : '239, 68, 68');
            const lhiStatus = finalLhi >= 90 ? 'OPTIMAL' : (finalLhi >= 70 ? 'DEGRADED' : 'CRITICAL');

            lhiBadge.innerHTML = `
                <div style="background: rgba(${lhiBgColor}, 0.1); border: 1px solid rgba(${lhiBgColor}, 0.3); border-radius: 8px; padding: 4px 12px; display: flex; align-items: center; gap: 8px; font-family: 'JetBrains Mono', monospace;">
                    <span style="font-size: 1.15rem; font-weight: 900; color: ${lhiColor};">${finalLhi}<span style="font-size: 0.7rem; opacity:0.6;">/100</span></span>
                    <div style="width: 1px; height: 16px; background: ${lhiColor}; opacity: 0.3;"></div>
                    <span style="font-size: 0.65rem; font-weight: 900; letter-spacing: 0.1em; color: ${lhiColor};">${lhiStatus}</span>
                </div>
            `;

            // Populate Detail Modal
            const elPing = document.getElementById('lhi-detail-ping');
            const elJitter = document.getElementById('lhi-detail-jitter');
            const elLoss = document.getElementById('lhi-detail-loss');
            const elStatusTitle = document.getElementById('lhi-detail-status-title');
            const elStatusDesc = document.getElementById('lhi-detail-status-desc');
            const elStatusBox = document.getElementById('lhi-detail-status-box');

            if (elPing) elPing.textContent = avgPing + ' ms';
            if (elJitter) elJitter.textContent = avgJitter + ' ms';
            if (elLoss) elLoss.textContent = avgLoss + ' %';

            if (elStatusTitle && elStatusBox) {
                const elRecs = document.getElementById('lhi-detail-recommendations');
                let recHtml = '';

                if (finalLhi >= 90) {
                    elStatusTitle.textContent = 'Estado: Óptimo';
                    elStatusTitle.style.color = '#065f46';
                    elStatusBox.style.background = '#d1fae5';
                    elStatusBox.style.borderLeftColor = '#10b981';
                    if (elStatusDesc) elStatusDesc.textContent = 'El enlace de red mantiene una calidad premium. Las latencias son imperceptibles y no hay indicios de sobrecarga en el canal RF.';

                    recHtml = `
                        <li><i class="fas fa-check-circle" style="color: #10b981; margin-right: 6px;"></i> Ninguna acción correctiva necesaria.</li>
                        <li><i class="fas fa-info-circle" style="color: #3b82f6; margin-right: 6px;"></i> El cliente tiene margen suficiente para un plan de mayor capacidad si lo desea.</li>
                    `;
                } else if (finalLhi >= 70) {
                    elStatusTitle.textContent = 'Estado: Degradado';
                    elStatusTitle.style.color = '#92400e';
                    elStatusBox.style.background = '#fef3c7';
                    elStatusBox.style.borderLeftColor = '#f59e0b';
                    if (elStatusDesc) elStatusDesc.textContent = 'Se han detectado variaciones notables en el tiempo de respuesta. Podría tratarse de ráfagas de consumo pesado durante horas pico o algo de interferencia leve en la zona.';

                    recHtml = `
                        <li><i class="fas fa-exclamation-triangle" style="color: #f59e0b; margin-right: 6px;"></i> Monitorear el consumo concurrente del cliente (posible cuello de botella en su router WiFi).</li>
                        <li><i class="fas fa-search" style="color: #6366f1; margin-right: 6px;"></i> Verificar la señal inalámbrica (CCQ) en la antena en caso de ser enlace por radio.</li>
                    `;
                } else {
                    elStatusTitle.textContent = 'Estado: Crítico';
                    elStatusTitle.style.color = '#991b1b';
                    elStatusBox.style.background = '#fee2e2';
                    elStatusBox.style.borderLeftColor = '#ef4444';
                    if (elStatusDesc) elStatusDesc.textContent = 'Atención. El rendimiento está significativamente afectado. Existe una alta probabilidad de pérdida de paquetes o tiempos de respuesta que estropearán servicios en tiempo real (VoIP, Gaming).';

                    recHtml = `
                        <li><i class="fas fa-tools" style="color: #ef4444; margin-right: 6px;"></i> <b>Prioridad Alta:</b> Inspeccionar alineación de antena y niveles de ruido (SNR).</li>
                        <li><i class="fas fa-route" style="color: #ef4444; margin-right: 6px;"></i> Confirmar que no haya un bucle de red o saturación masiva de tráfico de subida (Upload p2p).</li>
                        <li><i class="fas fa-phone" style="color: #8b5cf6; margin-right: 6px;"></i> Contactar al cliente para descartar desconexión de energía recurrente o daño físico en el cable de red.</li>
                    `;
                }

                if (elRecs) elRecs.innerHTML = recHtml;
            }
        }

        const labels = history.map(h => {
            const d = new Date(h.timestamp);
            return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
        });

        const latencyData = history.map(h => h.latency_ms);
        const jitterData = history.map(h => h.jitter_ms || 0);
        const lossData = history.map(h => h.packet_loss_pct || 0);

        const gradientLatency = ctx.createLinearGradient(0, 0, 0, 400);
        gradientLatency.addColorStop(0, 'rgba(99, 102, 241, 0.45)');
        gradientLatency.addColorStop(1, 'rgba(99, 102, 241, 0.0)');

        const gradientLoss = ctx.createLinearGradient(0, 0, 0, 400);
        gradientLoss.addColorStop(0, 'rgba(239, 68, 68, 0.35)');
        gradientLoss.addColorStop(1, 'rgba(239, 68, 68, 0.0)');

        try {
            this.stabilityChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        { label: 'LATENCIA (ms)', data: latencyData, borderColor: '#6366f1', backgroundColor: gradientLatency, fill: true, tension: 0.4, yAxisID: 'y', borderWidth: 2, pointRadius: 0 },
                        { label: 'JITTER (ms)', data: jitterData, borderColor: '#10b981', borderDash: [5, 5], fill: false, tension: 0.4, yAxisID: 'y', borderWidth: 2, pointRadius: 0 },
                        { label: 'LOSS (%)', data: lossData, borderColor: '#ef4444', backgroundColor: gradientLoss, fill: true, stepped: 'middle', yAxisID: 'y1', borderWidth: 2, pointRadius: history.map(h => h.packet_loss_pct > 0 ? 3 : 0) }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { position: 'top', labels: { font: { family: "'JetBrains Mono', monospace", size: 10, weight: 'bold' } } },
                        tooltip: { backgroundColor: 'rgba(15, 23, 42, 0.95)', titleFont: { family: "'JetBrains Mono', monospace" }, bodyFont: { family: "'JetBrains Mono', monospace" } }
                    },
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(226, 232, 240, 0.6)' }, ticks: { font: { family: "'JetBrains Mono', monospace", size: 9 } } },
                        y1: { beginAtZero: true, max: 100, position: 'right', grid: { drawOnChartArea: false }, ticks: { font: { family: "'JetBrains Mono', monospace", size: 9 }, color: '#ef4444' } },
                        x: { grid: { display: false }, ticks: { font: { family: "'JetBrains Mono', monospace", size: 9 }, autoSkip: true, maxTicksLimit: 12 } }
                    }
                }
            });
        } catch (e) {
            console.error("Metrical Chart Error:", e);
        }
    }

    renderTrafficChart(history, isLive = false) {
        let canvas = document.getElementById('metrics-traffic-chart');
        if (!canvas) return;
        const container = canvas.parentElement;

        // Si es live y ya existe el chart, solo actualizamos datos
        if (isLive && this.trafficChart && history.length > 0) {
            const labels = history.map(h => {
                const d = new Date(h.timestamp);
                return `${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
            });
            const downloadData = history.map(h => (h.download_bps / 1000000).toFixed(2));
            const uploadData = history.map(h => (h.upload_bps / 1000000).toFixed(2));

            this.trafficChart.data.labels = labels;
            this.trafficChart.data.datasets[0].data = downloadData;
            this.trafficChart.data.datasets[1].data = uploadData;
            this.trafficChart.update('none'); // Update smoothly without full redraw
            return;
        }

        if (this.trafficChart) {
            this.trafficChart.destroy();
            this.trafficChart = null;
        }

        if (!history || history.length === 0) {
            canvas.style.display = 'none';
            if (container) {
                // Solo mostrar mensaje si NO es live (o sea, carga inicial)
                container.innerHTML = `<canvas id="metrics-traffic-chart"></canvas>
                                      <div id="traffic-placeholder" style="position: absolute; top:0; left:0; width:100%; height:100%; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-weight: 600;">Esperando telemetría en vivo...</div>`;
            }
            return;
        }

        // Remover placeholder si existe
        const placeholder = document.getElementById('traffic-placeholder');
        if (placeholder) placeholder.remove();

        if (!document.getElementById('metrics-traffic-chart')) {
            container.innerHTML = '<canvas id="metrics-traffic-chart"></canvas>';
            canvas = document.getElementById('metrics-traffic-chart');
        }

        canvas.style.display = 'block';
        canvas.style.width = '100%';
        canvas.style.height = '100%';

        const ctx = canvas.getContext('2d');

        const labels = history.map(h => {
            const d = new Date(h.timestamp);
            return `${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`;
        });

        const downloadData = history.map(h => (h.download_bps / 1000000).toFixed(2));
        const uploadData = history.map(h => (h.upload_bps / 1000000).toFixed(2));

        const gradDown = ctx.createLinearGradient(0, 0, 0, 300);
        gradDown.addColorStop(0, 'rgba(0, 212, 255, 0.4)');
        gradDown.addColorStop(1, 'rgba(0, 212, 255, 0)');

        const gradUp = ctx.createLinearGradient(0, 0, 0, 300);
        gradUp.addColorStop(0, 'rgba(168, 85, 247, 0.4)');
        gradUp.addColorStop(1, 'rgba(168, 85, 247, 0)');

        try {
            this.trafficChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        { label: 'Descarga (Mbps)', data: downloadData, borderColor: '#00D4FF', backgroundColor: gradDown, fill: true, tension: 0.4, borderWidth: 3, pointRadius: 0 },
                        { label: 'Subida (Mbps)', data: uploadData, borderColor: '#A855F7', backgroundColor: gradUp, fill: true, tension: 0.4, borderWidth: 3, pointRadius: 0 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: { legend: { position: 'top', labels: { font: { size: 11, weight: 'bold' } } } },
                    scales: {
                        x: { grid: { display: false }, ticks: { autoSkip: true, maxTicksLimit: 8, font: { size: 10 } } },
                        y: { beginAtZero: true, grid: { color: 'rgba(226, 232, 240, 0.5)' }, ticks: { callback: v => v + 'M', font: { size: 10 } } }
                    }
                }
            });
        } catch (e) {
            console.error(e);
        }
    }

    renderTelemetryTable(history) {
        const container = document.getElementById('metrics-history-table');
        if (!container) return;

        if (!history || history.length === 0) {
            container.innerHTML = `<p style="padding: 24px; text-align: center; color: #94a3b8; font-weight: 600;">No existen incidencias ni métricas en el período evaluado</p>`;
            return;
        }

        // Vamos a resaltar anomalías (caídas, jitter alto, etc)
        // Tomamos los últimos 100 pero solo mostramos los interesantes
        let html = `
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead style="background: rgba(248, 250, 252, 0.95); position: sticky; top: 0; z-index: 1;">
                    <tr>
                        <th style="padding: 12px 24px; font-size: 0.7rem; font-weight: 800; color: #64748b; border-bottom: 2px solid #e2e8f0; text-transform: uppercase;">Evento / Fecha</th>
                        <th style="padding: 12px 24px; font-size: 0.7rem; font-weight: 800; color: #64748b; border-bottom: 2px solid #e2e8f0; text-transform: uppercase;">Latencia</th>
                        <th style="padding: 12px 24px; font-size: 0.7rem; font-weight: 800; color: #64748b; border-bottom: 2px solid #e2e8f0; text-transform: uppercase;">Jitter</th>
                        <th style="padding: 12px 24px; font-size: 0.7rem; font-weight: 800; color: #64748b; border-bottom: 2px solid #e2e8f0; text-transform: uppercase;">Pérdida</th>
                        <th style="padding: 12px 24px; font-size: 0.7rem; font-weight: 800; color: #64748b; border-bottom: 2px solid #e2e8f0; text-transform: uppercase;">Estado Vital</th>
                    </tr>
                </thead>
                <tbody>
        `;

        // Mostrar solo últimos 50 invertidos
        history.slice().reverse().slice(0, 50).forEach(h => {
            const d = new Date(h.timestamp);
            const dateStr = `${d.getDate().toString().padStart(2, '0')}/${(d.getMonth() + 1).toString().padStart(2, '0')} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;

            const isOnline = h.is_online;

            let statusBadge = isOnline ?
                '<span style="padding: 4px 10px; background: rgba(16, 185, 129, 0.1); color: #10b981; border-radius: 12px; font-size: 0.7rem; font-weight: 800;">ACTIVO</span>' :
                '<span style="padding: 4px 10px; background: rgba(239, 68, 68, 0.1); color: #ef4444; border-radius: 12px; font-size: 0.7rem; font-weight: 800; display: inline-flex; align-items: center; gap: 4px;"><i class="fas fa-exclamation-triangle"></i> CAÍDA</span>';

            const isNa = h.latency_ms === -1;
            const latColor = h.latency_ms > 100 ? '#ef4444' : (h.latency_ms > 50 ? '#f59e0b' : '#334155');
            const jitColor = h.jitter_ms > 20 ? '#ef4444' : (h.jitter_ms > 10 ? '#f59e0b' : '#334155');

            const latDisplay = isNa ? '<span style="opacity:0.5">N/A</span>' : `${h.latency_ms} <span style="font-size:0.6rem; opacity:0.6;">ms</span>`;
            const jitDisplay = isNa ? '--' : `±${h.jitter_ms || 0}`;
            const lossDisplay = isNa ? '--' : `${h.packet_loss_pct > 0 ? h.packet_loss_pct : '0'}%`;

            html += `
                <tr style="border-bottom: 1px solid rgba(226, 232, 240, 0.4); transition: background 0.2s;" onmouseover="this.style.background='rgba(248,250,252,1)'" onmouseout="this.style.background='transparent'">
                    <td style="padding: 12px 24px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; font-weight: 600; color: #64748b;">${dateStr}</td>
                    <td style="padding: 12px 24px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 800; color: ${latColor};">${latDisplay}</td>
                    <td style="padding: 12px 24px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; font-weight: 700; color: ${jitColor}; text-shadow: ${h.jitter_ms > 20 ? '0 0 4px rgba(239, 68, 68, 0.3)' : 'none'};">${jitDisplay}</td>
                    <td style="padding: 12px 24px; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 900; color: ${h.packet_loss_pct > 0 ? '#ef4444' : '#10b981'};">${lossDisplay}</td>
                    <td style="padding: 12px 24px;">${statusBadge}</td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        container.innerHTML = html;
    }

    async updateTrafficRange(range) {
        if (this.trafficRange === range) return;
        this.trafficRange = range;

        // UI Update
        document.querySelectorAll('.traffic-range-btn').forEach(btn => {
            const dataRange = btn.dataset.range;
            if (dataRange === range) {
                btn.classList.add('active');
                btn.style.background = '#ffffff';
                btn.style.color = '#6366f1';
                btn.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
                btn.style.fontWeight = '700';
            } else {
                btn.classList.remove('active');
                btn.style.background = 'transparent';
                btn.style.color = '#64748b';
                btn.style.boxShadow = 'none';
                btn.style.fontWeight = '600';
            }
        });

        if (range === 'live') {
            this.renderTrafficChart(this.trafficBuffer, true);
        } else {
            await this.fetchTrafficHistory();
        }
    }

    async fetchTrafficHistory() {
        if (!this.currentClientId) return;

        const hours = this.trafficRange === '7d' ? 168 : 24;
        try {
            const history = await this.api.get(`/api/clients/${this.currentClientId}/traffic-history?hours=${hours}`);

            // Agregación cada 30 min (como pidió el usuario) para vistas históricas
            let displayData = history || [];
            if (this.trafficRange === '7d' || this.trafficRange === '24h') {
                displayData = this.aggregateTrafficData(displayData, 30);
            }

            this.renderTrafficChart(displayData, false);
        } catch (e) {
            console.error("Error fetching history:", e);
        }
    }

    aggregateTrafficData(data, minutes) {
        if (!data || data.length < 2) return data;

        const aggregated = [];
        const intervalMs = minutes * 60 * 1000;
        const buckets = {};

        data.forEach(point => {
            const ts = new Date(point.timestamp).getTime();
            const bucketTs = Math.floor(ts / intervalMs) * intervalMs;

            if (!buckets[bucketTs]) {
                buckets[bucketTs] = { download: [], upload: [] };
            }
            buckets[bucketTs].download.push(point.download_bps);
            buckets[bucketTs].upload.push(point.upload_bps);
        });

        Object.keys(buckets).sort().forEach(ts => {
            const b = buckets[ts];
            aggregated.push({
                timestamp: parseInt(ts),
                download_bps: b.download.reduce((a, b) => a + b, 0) / b.download.length,
                upload_bps: b.upload.reduce((a, b) => a + b, 0) / b.upload.length
            });
        });

        return aggregated;
    }
}
