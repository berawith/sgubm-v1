/**
 * ModalManager - Servicio centralizado para gestión de modales
 * 
 * Responsabilidades:
 * - Registro de instancias de modales
 * - Apertura/cierre centralizado
 * - Gestión de overlay
 * - Prevenir apertura múltiple
 */
export class ModalManager {
    constructor() {
        this.modals = new Map();
        this.currentModal = null;
        this.overlay = null;

        this.init();
    }

    /**
     * Inicializa el manager
     */
    init() {
        // Crear overlay global si no existe
        if (!document.querySelector('.modal-overlay')) {
            this.createOverlay();
        }

        // Listener global para ESC key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.currentModal) {
                this.close(this.currentModal);
            }
        });

        // Listener global para clics de cierre (Delegación Maestra)
        document.addEventListener('click', (e) => {
            // 🛡️ Prevent closing if user is selecting text (Highlighting)
            if (window.getSelection().toString().length > 0) {
                return;
            }

            const target = e.target;

            // 🛡️ IGNORAR interacciones con SweetAlert2
            if (target.closest('.swal2-container')) {
                return;
            }

            // 🛡️ IGNORAR clics dentro del contenido del modal que NO sean botones de cierre explícitos
            const insideContent = target.closest('.modal-content, .modal-body, .premium-compact-modal');
            const closeTrigger = target.closest('[data-close], .close-btn, [data-action="close"], [data-action="cancel"]');

            if (insideContent && !closeTrigger) {
                return;
            }

            if (closeTrigger && this.currentModal) {
                console.log(`🔌 [ModalManager] Global close triggered for: ${this.currentModal} by:`, closeTrigger);
                e.preventDefault();
                e.stopPropagation();
                this.close(this.currentModal);
            }
        });

        console.log('✅ ModalManager initialized');
    }

    /**
     * Crea overlay global para modales
     */
    createOverlay() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'modal-overlay';
        this.overlay.addEventListener('click', () => {
            // 🛡️ Prevent accidental closing. Only close button should close modal.
            // if (this.currentModal) {
            //     this.close(this.currentModal);
            // }
        });
        document.body.appendChild(this.overlay);
    }

    /**
     * Registra un modal en el manager
     */
    register(name, modalInstance) {
        if (this.modals.has(name)) {
            console.warn(`⚠️ Modal '${name}' ya está registrado. Sobrescribiendo...`);
        }

        this.modals.set(name, modalInstance);
        console.log(`📦 Modal registrado: ${name}`);

        const modalId = modalInstance.modalId || name;

        // 🛡️ ESCUCHAR CIERRE INTERNO:
        // Si el modal se cierra a sí mismo (p.ej. tras guardar), el manager debe saberlo
        // para ocultar el overlay y liberar el estado.
        const handleInternalClose = () => {
            if (this.currentModal === name) {
                console.log(`🔌 [ModalManager] Detectado cierre interno de: ${name}`);
                this.currentModal = null;
                if (this.overlay) {
                    this.overlay.classList.remove('active');
                }
            }
        };

        // Escuchar por modalId y por nombre de registro para máxima compatibilidad
        document.addEventListener(`modal:${modalId}:closed`, handleInternalClose);
        if (modalId !== name) {
            document.addEventListener(`modal:${name}:closed`, handleInternalClose);
        }

        return this;
    }

    /**
     * Des-registra un modal
     */
    unregister(name) {
        const modal = this.modals.get(name);
        if (modal) {
            // Nota: En un sistema real deberíamos remover los listeners aquí
            modal.destroy();
            this.modals.delete(name);
            console.log(`🗑️ Modal eliminado: ${name}`);
        }
    }

    /**
     * Abre un modal por nombre
     */
    async open(name, data = {}) {
        const modal = this.modals.get(name);

        if (!modal) {
            console.error(`❌ Modal '${name}' no encontrado. Modales disponibles:`, Array.from(this.modals.keys()));
            return;
        }

        // Cerrar modal actual si existe
        if (this.currentModal && this.currentModal !== name) {
            await this.close(this.currentModal);
        }

        // Abrir nuevo modal
        try {
            await modal.open(data);
            this.currentModal = name;

            // Mostrar overlay
            if (this.overlay) {
                this.overlay.classList.add('active');
            }

            console.log(`👁️ Modal abierto: ${name}`);
        } catch (error) {
            console.error(`❌ Error abriendo modal '${name}':`, error);
        }
    }

    closeUnregistered() {
        // Enforce cleanup if a modal was destroyed but overlay remained
        if (this.overlay) {
            this.overlay.classList.remove('active');
        }
        this.currentModal = null;
    }

    /**
     * Cierra un modal por nombre
     */
    close(name) {
        const modal = this.modals.get(name);

        if (!modal) {
            console.warn(`⚠️ Modal '${name}' no encontrado para cerrar. Forzando limpieza...`);
            this.closeUnregistered();
            return;
        }

        try {
            modal.close();
            console.log(`❌ Modal cerrado: ${name}`);
        } catch (error) {
            console.error(`❌ Error al cerrar modal '${name}':`, error);
        } finally {
            if (this.currentModal === name) {
                this.currentModal = null;
            }

            // Ocultar overlay si no hay modales abiertos o si forzamos limpieza
            if (this.overlay) {
                // Verificación extra: ¿hay algún modal con clase 'active' en el DOM?
                const activeModals = document.querySelectorAll('.modal.active');
                if (activeModals.length === 0 || !this.currentModal) {
                    this.overlay.classList.remove('active');
                    console.log('🔌 [ModalManager] Overlay forzado a inactivo (Safe Close)');
                }
            }
        }
    }

    /**
     * Cierra todos los modales
     */
    closeAll() {
        this.modals.forEach((modal, name) => {
            modal.close();
        });

        this.currentModal = null;

        if (this.overlay) {
            this.overlay.classList.remove('active');
        }

        console.log('❌ Todos los modales cerrados');
    }

    /**
     * Verifica si un modal está abierto
     */
    isOpen(name) {
        return this.currentModal === name;
    }

    /**
     * Obtiene instancia de un modal
     */
    get(name) {
        return this.modals.get(name);
    }

    /**
     * Lista todos los modales registrados
     */
    list() {
        return Array.from(this.modals.keys());
    }

    /**
     * Destruye el manager y todos los modales
     */
    destroy() {
        this.modals.forEach((modal, name) => {
            modal.destroy();
        });

        this.modals.clear();

        if (this.overlay) {
            this.overlay.remove();
            this.overlay = null;
        }

        this.currentModal = null;
        console.log('🗑️ ModalManager destruido');
    }
}
