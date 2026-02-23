/**
 * BaseModal - Clase base robusta para componentes modales independientes.
 * Soporta carga asíncrona de recursos (HTML/CSS), gestión de eventos
 * y comunicación con API/EventBus.
 */
export class BaseModal {
    /**
     * @param {string} modalId - ID único para el contenedor del modal
     * @param {object} api - Instancia del ApiService
     * @param {object} eventBus - Instancia del EventBus (opcional)
     */
    constructor(modalId, api = null, eventBus = null) {
        this.modalId = modalId;
        this.api = api;
        this.eventBus = eventBus;

        this.container = null; // Legacy alias
        this.modalElement = null; // Unified element reference
        this.isRendered = false;
        this.isInitialized = false;
        this.eventListeners = [];

        // Inicializar automáticamente si se desea, o llamar init() manualmente
        this._initPromise = this.init();
    }

    /**
     * Hook de inicialización asíncrona.
     * Debe ser implementado por subclases para cargar recursos.
     */
    async init() {
        return Promise.resolve();
    }

    /**
     * Carga el template HTML y el CSS asociado si se proporcionan.
     * @param {string} templateUrl - Ruta al archivo .template.html
     * @param {string} stylesUrl - Ruta al archivo .styles.css (opcional)
     */
    async loadResources(templateUrl, stylesUrl = null) {
        try {
            // 1. Cargar estilos si existen
            if (stylesUrl) {
                this._injectStyles(stylesUrl);
            }

            // 2. Cargar template
            const response = await fetch(templateUrl);
            const html = await response.text();

            // 3. Crear el contenedor raíz del modal si no existe
            let modalRoot = document.getElementById(this.modalId);

            if (modalRoot) {
                console.warn(`[BaseModal:${this.modalId}] El modal ya existe en el DOM. Reutilizando instancia.`);
                // Limpiar contenido previo para asegurar que el template sea el más reciente
                modalRoot.innerHTML = html.trim();
            } else {
                modalRoot = document.createElement('div');
                modalRoot.id = this.modalId;
                modalRoot.className = 'modal'; // Clase base para ocultar/mostrar

                // Inyectar el contenido del template
                modalRoot.innerHTML = html.trim();

                // 4. Renderizar en el DOM (append al final del body)
                document.body.appendChild(modalRoot);
            }

            this.modalElement = modalRoot;
            this.modalElement._component = this;
            this.container = modalRoot; // Compatibilidad legacy

            this.isRendered = true;
            this.isInitialized = true;

            this.attachBaseEvents();
            return modalRoot;
        } catch (error) {
            console.error(`[BaseModal:${this.modalId}] Error loading resources:`, error);
            throw error;
        }
    }

    /**
     * Inyecta link de estilos en el head si no existe
     */
    _injectStyles(url) {
        if (document.querySelector(`link[href="${url}"]`)) return;

        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = url;
        document.head.appendChild(link);
    }

    /**
     * Adjunta eventos base (como cerrar con [data-close])
     * Usa delegación de eventos para mayor robustez.
     */
    attachBaseEvents() {
        if (!this.modalElement) return;

        // Backdrop click (específico de esta instancia)
        let isBackdropMousedown = false;

        this.addEventListener(this.modalElement, 'mousedown', (e) => {
            isBackdropMousedown = (e.target === this.modalElement);
        });

        this.addEventListener(this.modalElement, 'click', (e) => {
            if (e.target === this.modalElement && isBackdropMousedown) {
                // 🛡️ Prevent closing on backdrop click
                // if (window.getSelection().toString().length > 0) return;
                // this.close();
            }
            // Reset for safety
            isBackdropMousedown = false;
        });

        // Close buttons (data-close or data-action="close")
        const closeButtons = this.modalElement.querySelectorAll('[data-close], [data-action="close"]');
        closeButtons.forEach(btn => {
            this.addEventListener(btn, 'click', (e) => {
                e.preventDefault();
                this.close();
            });
        });

        // Submit de formularios automático
        const form = this.modalElement.querySelector('form');
        if (form) {
            this.addEventListener(form, 'submit', (e) => {
                if (typeof this.handleSubmit === 'function') {
                    this.handleSubmit(e);
                }
            });
        }
    }

    /**
     * Abre el modal
     */
    async open(data = {}) {
        // Asegurar que los recursos estén cargados
        await this._initPromise;

        if (!this.modalElement) {
            console.error(`[BaseModal:${this.modalId}] modalElement not found after init.`);
            return;
        }

        this.modalElement.classList.add('active');
        this.emit('opened', data);
    }

    /**
     * Cierra el modal
     */
    close() {
        if (!this.modalElement) return;

        this.modalElement.classList.remove('active');
        this.emit('closed');

        // Clean up all attached listeners to prevent memory leaks and stray calls
        this.removeAllListeners();

        if (typeof this.onClose === 'function') {
            this.onClose();
        }
    }

    /**
     * Hook llamado cuando el modal se cierra.
     * Las subclases pueden sobrescribir esto para realizar limpieza específica.
     */
    onClose() {
        // Default implementation hides global loader to prevent UI freeze.
        if (window.app) app.showLoading(false);
    }

    /**
     * Helper para añadir listeners y trackearlos para limpieza
     */
    addEventListener(element, event, handler) {
        if (!element) return;
        element.addEventListener(event, handler);
        this.eventListeners.push({ element, event, handler });
    }

    /**
     * Limpia listeners trackeados
     */
    removeAllListeners() {
        this.eventListeners.forEach(({ element, event, handler }) => {
            element.removeEventListener(event, handler);
        });
        this.eventListeners = [];
    }

    /**
     * Helper para popular campos de formulario
     */
    setFormValues(values) {
        if (!this.modalElement) return;

        Object.entries(values).forEach(([id, value]) => {
            const el = this.modalElement.querySelector(`#${id}`);
            if (el) {
                if (el.type === 'checkbox') {
                    el.checked = !!value;
                } else {
                    el.value = value !== null && value !== undefined ? value : '';
                }
            }
        });
    }

    /**
     * Obtiene datos de un formulario
     */
    getFormData(formSelector = 'form') {
        const form = this.modalElement.querySelector(formSelector);
        if (!form) return {};

        const formData = new FormData(form);
        return Object.fromEntries(formData.entries());
    }

    /**
     * Emite eventos vía CustomEvent
     */
    emit(eventName, detail = {}) {
        const event = new CustomEvent(`modal:${this.modalId}:${eventName}`, {
            detail: { modalId: this.modalId, ...detail }
        });
        document.dispatchEvent(event);
    }

    /**
     * Suscribirse a eventos del modal
     */
    on(eventName, callback) {
        const handler = (e) => callback(e.detail);
        document.addEventListener(`modal:${this.modalId}:${eventName}`, handler);
        return () => document.removeEventListener(`modal:${this.modalId}:${eventName}`, handler);
    }

    /**
     * UI Helpers
     */
    showLoading() {
        this.modalElement?.classList.add('loading');
    }

    hideLoading() {
        this.modalElement?.classList.remove('loading');
    }

    showError(message) {
        if (window.toast) window.toast.error(message);
        else console.error(`[${this.modalId}] Error:`, message);
    }

    destroy() {
        this.removeAllListeners();
        this.modalElement?.remove();
        this.isRendered = false;
        this.isInitialized = false;
    }
}

