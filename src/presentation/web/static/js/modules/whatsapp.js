/**
 * WhatsApp Module
 * Responsabilidad: Gestionar la interfaz de mensajería inteligente
 */

export class WhatsAppModule {
    constructor(apiService, eventBus, viewManager, modalManager = null) {
        this.api = apiService;
        this.eventBus = eventBus;
        this.viewManager = viewManager;
        this.modalManager = modalManager;
        this.conversations = [];
        this.activePhone = null;
        this.globalSearchResults = [];
        this.searchTimeout = null;
        this.activeFilter = 'clients';
        this.init();
    }

    init() {
        console.log('📱 WhatsApp Module initialized');
        this.attachEvents();
        this.setupEventListeners();
        this.initSocket();
    }

    initSocket() {
        if (window.app && window.app.socket) {
            window.app.socket.on('whatsapp_message', (data) => {
                console.log('📨 New WhatsApp message received via socket', data);

                // Efecto visual de "La secretaria está analizando" brevemente si es entrante
                if (!data.is_outgoing) {
                    this.setAITyping(true, 'Secretaria analizando mensaje secundario...');
                    setTimeout(() => this.setAITyping(false), 2000);
                }

                this.loadConversations();
                if (this.activePhone === data.phone) {
                    this.addMessageToHistory(data);
                }
            });
        }
    }

    attachEvents() {
        this.eventBus.subscribe('navigate', (data) => {
            if (data.view === 'whatsapp') {
                this.loadConversations();
            }
        });

        const btnSend = document.getElementById('btn-whatsapp-send');
        if (btnSend) {
            btnSend.addEventListener('click', () => this.sendMessage());
        }

        const btnConfig = document.getElementById('btn-whatsapp-config');
        if (btnConfig) {
            btnConfig.addEventListener('click', () => {
                if (this.modalManager) {
                    this.modalManager.open('whatsapp-config');
                } else {
                    this.openConfig();
                }
            });
        }
    }

    setupEventListeners() {
        const textarea = document.getElementById('whatsapp-reply'); // Changed from whatsapp-message-input to whatsapp-reply based on original
        if (textarea) {
            textarea.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }

        const searchInput = document.getElementById('whatsapp-search');
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                this.renderConversations();
                this.debounceGlobalSearch(searchInput.value);
            });
        }
    }

    debounceGlobalSearch(search) {
        if (this.searchTimeout) clearTimeout(this.searchTimeout);
        if (!search || search.length < 2) {
            this.globalSearchResults = [];
            this.renderConversations();
            return;
        }

        this.searchTimeout = setTimeout(async () => {
            try {
                const response = await fetch(`/api/clients?search=${encodeURIComponent(search)}`);
                const clients = await response.json();

                // Filtrar clientes que ya tienen conversación activa para no duplicar
                const existingPhones = new Set(this.conversations.map(c => c.phone));
                this.globalSearchResults = clients.filter(c => !existingPhones.has(c.phone));

                this.renderConversations();
            } catch (e) {
                console.error('Error in global search:', e);
            }
        }, 400);
    }

    /**
     * Carga los datos de configuración desde el servidor sin abrir el modal.
     * Útil para cuando el modal ya está abriéndose vía ModalManager.
     */
    async loadConfigData() {
        try {
            const response = await fetch('/api/whatsapp/config');
            const data = await response.json();

            const keyEl = document.getElementById('config-gemini-key');
            const nameEl = document.getElementById('config-agent-name');
            const phoneEl = document.getElementById('config-agent-phone');
            const urlEl = document.getElementById('config-webhook-url');
            const autoReplyToggle = document.getElementById('config-auto-reply');

            if (keyEl) keyEl.value = data.gemini_key || '';
            if (nameEl) nameEl.value = data.agent_name || '';
            if (phoneEl) phoneEl.value = data.agent_phone || '';
            if (urlEl) urlEl.innerText = data.webhook_url || 'N/A';
            if (autoReplyToggle) autoReplyToggle.checked = data.auto_reply !== false;

            // Iniciar chequeo de estado
            this.checkStatus();
            if (this.statusInterval) clearInterval(this.statusInterval);
            this.statusInterval = setInterval(() => this.checkStatus(), 5000);

            return data;
        } catch (e) {
            console.error('Error loading config data:', e);
        }
    }

    async openConfig() {
        await this.loadConfigData();
        if (this.modalManager) {
            this.modalManager.open('whatsapp-config');
        } else {
            const modal = document.getElementById('whatsapp-config-modal');
            if (modal) modal.classList.add('active');
        }
    }

    // Alias para compatibilidad con ModalManager (que llama a loadConfig por defecto si existe)
    loadConfig() {
        return this.loadConfigData();
    }

    closeConfig() {
        if (this.statusInterval) clearInterval(this.statusInterval);
        this.statusInterval = null;

        // Si ya estamos cerrando vía ModalManager, no lo volvemos a llamar
        const modal = document.getElementById('whatsapp-config-modal');
        if (modal && modal.classList.contains('active')) {
            modal.classList.remove('active');
        }
    }

    async checkStatus() {
        try {
            const response = await fetch('/api/whatsapp/status');
            const data = await response.json();

            const badge = document.getElementById('wa-status-badge');
            const qrContainer = document.getElementById('wa-qr-container');
            const connMsg = document.getElementById('wa-connected-msg');
            const qrPlaceholder = document.getElementById('wa-qr-image-placeholder');

            if (!badge) return; // Not in config modal

            if (data.connected) {
                badge.innerText = 'Conectado';
                badge.style.background = 'rgba(34, 197, 94, 0.2)';
                badge.style.color = '#22c55e';
                badge.style.border = '1px solid rgba(34, 197, 94, 0.3)';
                qrContainer.style.display = 'none';
                if (connMsg) connMsg.style.display = 'block';
            } else {
                badge.innerText = 'Desconectado';
                badge.style.background = 'rgba(251, 191, 36, 0.2)';
                badge.style.color = '#fbbf24';
                badge.style.border = '1px solid rgba(251, 191, 36, 0.3)';
                if (connMsg) connMsg.style.display = 'none';

                if (data.pairing_code) {
                    qrContainer.style.display = 'block';
                    qrPlaceholder.innerHTML = `
                        <div style="padding: 10px; background: rgba(0,0,0,0.2); border-radius: 8px;">
                            <p style="font-size: 10px; color: var(--wa-text-muted); margin-bottom: 8px; text-transform: uppercase;">Código de Vinculación:</p>
                            <div style="font-family: monospace; font-size: 20px; font-weight: 800; color: var(--wa-accent); letter-spacing: 4px; border: 1px solid var(--wa-border); padding: 10px; border-radius: 6px;">
                                ${data.pairing_code}
                            </div>
                        </div>
                    `;
                } else if (data.qr) {
                    qrContainer.style.display = 'block';
                    const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(data.qr)}`;
                    qrPlaceholder.innerHTML = `<img src="${qrUrl}" alt="QR Code" style="width: 150px; height: 150px; border-radius: 4px; border: 4px solid white;">`;
                } else {
                    qrContainer.style.display = 'block';
                    qrPlaceholder.innerHTML = '<div style="text-align:center; padding: 20px;"><div class="spinner-quantum" style="width:20px; height:20px; margin: 0 auto;"></div><p style="font-size:10px; margin-top:5px; color: #94a3b8;">Esperando bridge...</p></div>';
                }
            }
        } catch (e) {
            console.error('Error checking status:', e);
        }
    }

    async requestPairing() {
        const phone = document.getElementById('config-agent-phone').value;
        if (!phone || phone === 'Desconocido') {
            alert('Por favor, ingresa un número de teléfono válido primero.');
            return;
        }

        const btn = event?.currentTarget || event?.target;
        const originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i>';

        try {
            const response = await fetch('/api/whatsapp/pair', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ phone: phone })
            });

            const result = await response.json();
            if (result.success) {
                console.log('✅ Pairing request sent');
                setTimeout(() => this.checkStatus(), 1000);
            } else {
                alert('Error: ' + result.error);
            }
        } catch (e) {
            console.error('Error in requestPairing:', e);
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    }

    async saveConfig() {
        const btnSave = event?.submitter || document.querySelector('button[type="submit"]');
        if (btnSave) btnSave.disabled = true;

        const data = {
            gemini_key: document.getElementById('config-gemini-key').value,
            agent_name: document.getElementById('config-agent-name').value,
            agent_phone: document.getElementById('config-agent-phone').value,
            auto_reply: document.getElementById('config-auto-reply').checked
        };

        try {
            const response = await fetch('/api/whatsapp/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();
            if (result.success) {
                this.closeConfig(); // Cerrar modal después de guardar exitosamente
                console.log('✅ WhatsApp Config saved');
            }
        } catch (e) {
            alert('Error al guardar la configuración.');
        } finally {
            if (btnSave) btnSave.disabled = false;
        }
    }


    copyWebhook() {
        const url = document.getElementById('config-webhook-url').innerText;
        navigator.clipboard.writeText(url).then(() => {
            const btn = event?.currentTarget || document.querySelector('[onclick*="copyWebhook"]');
            if (btn) {
                const icon = btn.querySelector('i');
                const originalClass = icon.className;
                icon.className = 'fas fa-check';
                setTimeout(() => icon.className = originalClass, 2000);
            }
        });
    }

    setAITyping(active, text = 'Secretaria redactando...') {
        const el = document.getElementById('ai-status');
        const textEl = document.getElementById('ai-status-text');
        if (!el) return;

        el.style.visibility = active ? 'visible' : 'hidden';
        if (text) textEl.textContent = text;
    }

    async sendQuickInfo(action) {
        if (!this.activePhone) return;

        const actionMap = {
            'balance': 'Por favor, ¿podría indicarme mi saldo actual?',
            'support': 'Tengo problemas técnicos con mi servicio de internet.',
            'promise': 'Necesito un compromiso de pago para unos días después.'
        };

        const message = actionMap[action];
        if (message) {
            const input = document.getElementById('whatsapp-reply');
            input.value = message;
            this.sendMessage();
        }
    }

    async loadConversations() {
        try {
            const listContainer = document.getElementById('whatsapp-conversation-list');
            if (listContainer) {
                // No mostrar loading si ya tenemos items (actualización suave)
                if (this.conversations.length === 0) {
                    listContainer.innerHTML = '<div class="placeholder-loading"><span class="spinner-quantum"></span> Cargando secretaria virtual...</div>';
                }
            }

            const response = await fetch('/api/whatsapp/conversations');
            const data = await response.json();

            if (Array.isArray(data)) {
                this.conversations = data;
                this.renderConversations();
            }
        } catch (error) {
            console.error('Error loading conversations:', error);
        }
    }

    setFilter(filter) {
        this.activeFilter = filter;
        document.querySelectorAll('.filter-tab-btn').forEach(btn => {
            const onclick = btn.getAttribute('onclick');
            if (onclick) {
                btn.classList.toggle('active', onclick.includes(filter));
            }
        });
        this.renderConversations();
    }

    renderConversations() {
        const listContainer = document.getElementById('whatsapp-conversation-list');
        if (!listContainer) return;

        let filtered = this.conversations;

        // Filtro por búsqueda
        const search = document.getElementById('whatsapp-search')?.value.toLowerCase();
        if (search) {
            filtered = filtered.filter(c =>
                (c.client_name || '').toLowerCase().includes(search) ||
                (c.client_cedula || '').toLowerCase().includes(search) ||
                (c.client_code || '').toLowerCase().includes(search) ||
                c.phone.includes(search)
            );
        }

        // Filtro por pestaña (Entrantes/Pendientes/Clientes)
        if (this.activeFilter === 'incoming') {
            // Asumimos que "incoming" son mensajes donde el último no es saliente
            filtered = filtered.filter(c => !c.is_outgoing);
        } else if (this.activeFilter === 'clients') {
            // Filtrar solo los que tienen nombre de cliente (no son externos puros ni desconocidos)
            filtered = filtered.filter(c => c.client_name && c.client_name !== 'Unknown' && c.client_name !== 'undefined' && !c.is_external);
        }

        if (filtered.length === 0 && this.globalSearchResults.length === 0) {
            listContainer.innerHTML = `<div class="empty-list" style="padding:40px; text-align:center; opacity:0.3; font-weight:700;">No hay resultados para "${search || ''}".</div>`;
            return;
        }

        let html = '';

        if (filtered.length > 0) {
            html += filtered.map(conv => this.generateConvItemHTML(conv)).join('');
        }

        // Mostrar resultados globales si hay búsqueda
        if (search && this.globalSearchResults.length > 0) {
            html += `
                <div style="padding: 15px 15px 5px; font-size: 10px; font-weight: 800; color: var(--wa-accent); text-transform: uppercase; letter-spacing: 1px; border-top: 1px solid var(--wa-border); margin-top: 10px;">
                    Clientes Disponibles en el Sistema
                </div>
            `;
            html += this.globalSearchResults.map(client => this.generateGlobalItemHTML(client)).join('');
        }

        // Actualizar contador de pendientes
        const pendingCount = this.conversations.filter(c => !c.is_outgoing).length;
        const badge = document.getElementById('wa-pending-count');
        if (badge) {
            badge.textContent = pendingCount;
            badge.style.display = pendingCount > 0 ? 'inline-block' : 'none';
        }

        listContainer.innerHTML = html;
    }

    generateConvItemHTML(conv) {
        const isActive = this.activePhone === conv.phone;
        const isClient = conv.client_name && conv.client_name !== 'Unknown' && conv.client_name !== 'undefined';
        const isExternal = conv.is_external === true;
        const initial = isClient ? conv.client_name.substring(0, 1).toUpperCase() : (isExternal ? 'W' : '#');

        return `
            <div class="conv-item-premium ${isActive ? 'active' : ''} ${isExternal ? 'is-external' : ''}" 
                 onclick="app.modules.whatsapp.selectConversation('${conv.phone}', '${conv.client_name}')">
                <div class="conv-avatar-mini" style="background: ${isClient ? 'rgba(99,102,241,0.15)' : (isExternal ? 'rgba(34,197,94,0.1)' : 'rgba(255,255,255,0.05)')}; 
                                                   color: ${isClient ? 'var(--wa-accent)' : (isExternal ? '#22c55e' : 'var(--wa-text-muted)')}">
                    ${initial}
                </div>
                <div class="conv-content">
                    <div class="conv-header">
                        <span class="conv-name text-truncate">${conv.phone}</span>
                        <span class="conv-time">${this.formatTime(conv.timestamp)}</span>
                    </div>
                    <div class="conv-preview" style="display: flex; flex-direction: column; gap: 2px;">
                        <div style="display: flex; align-items: center; gap: 5px;">
                            <span style="font-size: 10px; font-weight: 800; color: ${isClient ? '#22c55e' : (isExternal ? '#22c55e' : '#94a3b8')}; text-transform: uppercase;">
                                ${isClient ? '✓ Cliente' : (isExternal ? '<i class="fab fa-whatsapp"></i> Externo' : '👤 Desconocido')}
                            </span>
                            ${isClient ? `<span class="text-truncate" style="font-size: 11px; opacity: 0.8;"> - ${conv.client_name}</span>` : ''}
                        </div>
                        <p>${conv.message_text.substring(0, 45)}${conv.message_text.length > 45 ? '...' : ''}</p>
                    </div>
                </div>
            </div>
        `;
    }

    generateGlobalItemHTML(client) {
        return `
            <div class="conv-item-premium" style="opacity: 0.8; border-color: rgba(99, 102, 241, 0.1);"
                 onclick="app.modules.whatsapp.selectConversation('${client.phone}', '${client.legal_name}')">
                <div class="conv-avatar-mini" style="background: rgba(99, 102, 241, 0.1); color: var(--wa-accent)">
                    ${client.legal_name.substring(0, 1).toUpperCase()}
                </div>
                <div class="conv-content">
                    <div class="conv-header">
                        <span class="conv-name text-truncate">${client.legal_name}</span>
                        <span class="conv-time" style="color: var(--wa-accent); font-weight: 700;">NUEVO CHAT</span>
                    </div>
                    <div class="conv-preview">
                        <p style="font-size: 10px; color: var(--wa-text-muted);">
                            ${client.identity_document || 'S/D'} • ${client.subscriber_code} • ${client.phone}
                        </p>
                    </div>
                </div>
            </div>
        `;
    }

    async selectConversation(phone, name) {
        this.activePhone = phone;
        const placeholder = document.getElementById('no-chat-selected');
        const chatWindow = document.getElementById('chat-window');

        if (placeholder) placeholder.style.display = 'none';
        if (chatWindow) {
            chatWindow.style.display = 'flex';
            chatWindow.classList.add('viewport-entered');
        }

        const isClient = name && name !== 'Unknown' && name !== 'undefined';
        const nameEl = document.getElementById('chat-client-name');
        const avatarEl = document.getElementById('chat-avatar');

        if (nameEl) {
            nameEl.innerHTML = `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span>${phone}</span>
                    <span class="badge-quantum" style="background: ${isClient ? 'rgba(34, 197, 94, 0.2)' : 'rgba(255, 255, 255, 0.05)'}; 
                          color: ${isClient ? '#22c55e' : '#94a3b8'}; border: 1px solid ${isClient ? 'rgba(34, 197, 94, 0.3)' : 'rgba(255, 255, 255, 0.1)'};">
                        ${isClient ? 'CLIENTE' : 'DESCONOCIDO'}
                    </span>
                </div>
                ${isClient ? `<div style="font-size: 11px; font-weight: 400; opacity: 0.6; margin-top: 2px;">Titular: ${name}</div>` : ''}
            `;
        }
        if (avatarEl) {
            avatarEl.textContent = isClient ? name.substring(0, 1).toUpperCase() : '#';
            avatarEl.style.background = isClient ? 'var(--wa-accent)' : '#1e293b';
        }

        this.renderConversations();
        this.loadHistory(phone);
    }

    async loadHistory(phone) {
        try {
            const container = document.getElementById('chat-messages');
            container.innerHTML = `
                <div class="chat-preloader" style="text-align:center; padding: 40px; color: var(--quantum-primary);">
                    <div class="spinner-quantum" style="width: 30px; height: 30px; margin: 0 auto 15px;"></div>
                    <p style="font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.7;">
                        Sincronizando con base de datos SGUBM...
                    </p>
                </div>
            `;

            const response = await fetch(`/api/whatsapp/history/${phone}`);
            const history = await response.json();

            if (!Array.isArray(history)) return;

            container.innerHTML = history.map(msg => this.generateMessageHTML(msg)).join('');
            container.scrollTop = container.scrollHeight;
        } catch (error) {
            console.error('Error loading history:', error);
        }
    }

    generateMessageHTML(msg) {
        const time = this.formatTime(msg.timestamp);
        const intentHtml = !msg.is_outgoing && msg.intent ?
            `<div class="intent-tag"><i class="fas fa-brain"></i> IA DETECTÓ: ${msg.intent.toUpperCase().replace('_', ' ')}</div>` : '';

        return `
            <div class="msg-bubble-quantum ${msg.is_outgoing ? 'msg-outbound' : 'msg-inbound'}">
                ${intentHtml}
                <div class="text">${msg.message_text}</div>
                <span class="time-quantum">${time}</span>
            </div>
        `;
    }

    async sendMessage() {
        const input = document.getElementById('whatsapp-reply');
        const text = input.value.trim();
        if (!text || !this.activePhone) return;

        // Visual feedback
        this.setAITyping(true, 'Enviando mensaje...');
        const originalText = text;
        input.value = '';

        try {
            const response = await fetch('/api/whatsapp/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    phone: this.activePhone,
                    message: text
                })
            });

            const result = await response.json();

            if (result.success) {
                console.log('✅ Message sent');
                this.loadHistory(this.activePhone);
                this.loadConversations();
            } else {
                alert('Error al enviar: ' + (result.error || 'Desconocido'));
                input.value = originalText; // Restaurar si falla
            }
        } catch (e) {
            console.error('Error in sendMessage:', e);
            alert('Error crítico de conexión.');
            input.value = originalText;
        } finally {
            this.setAITyping(false);
        }
    }

    addMessageToHistory(msg) {
        const container = document.getElementById('chat-messages');
        if (!container) return;

        const html = this.generateMessageHTML(msg);
        container.insertAdjacentHTML('beforeend', html);
        container.scrollTop = container.scrollHeight;
    }

    formatTime(isoString) {
        const date = new Date(isoString);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    filterConversations(query) {
        const lowerQuery = query.toLowerCase();
        const filtered = this.conversations.filter(c =>
            (c.client_name || '').toLowerCase().includes(lowerQuery) ||
            c.phone.includes(query)
        );
        // Podríamos filtrar visualmente aquí
    }

    load() {
        console.log('💎 Loading Super Agent Console...');
        this.showView();
        this.loadConversations();
    }

    showView() {
        this.viewManager.showMainView('whatsapp');
    }
}
