/**
 * Toast Notification System
 * Sistema de notificaciones estilo toast con diseño premium
 */

class ToastNotification {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Crear contenedor de toasts
        this.container = document.createElement('div');
        this.container.id = 'toast-container';
        this.container.className = 'toast-container';
        document.body.appendChild(this.container);
    }

    /**
     * Muestra un toast de éxito
     * @param {string} message - Mensaje a mostrar
     * @param {number} duration - Duración en ms (default: 3000)
     */
    success(message, duration = 3000) {
        this.show(message, 'success', duration);
    }

    /**
     * Muestra un toast de error
     * @param {string} message - Mensaje a mostrar
     * @param {number} duration - Duración en ms (default: 4000)
     */
    error(message, duration = 4000) {
        this.show(message, 'error', duration);
    }

    /**
     * Muestra un toast de advertencia
     * @param {string} message - Mensaje a mostrar
     * @param {number} duration - Duración en ms (default: 3500)
     */
    warning(message, duration = 3500) {
        this.show(message, 'warning', duration);
    }

    /**
     * Muestra un toast de información
     * @param {string} message - Mensaje a mostrar
     * @param {number} duration - Duración en ms (default: 3000)
     */
    info(message, duration = 3000) {
        this.show(message, 'info', duration);
    }

    /**
     * Muestra un toast
     * @param {string} message - Mensaje
     * @param {string} type - Tipo: success, error, warning, info
     * @param {number} duration - Duración en ms
     */
    show(message, type = 'info', duration = 3000) {
        // Crear elemento toast
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        // Icono según el tipo
        const icons = {
            success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                        <polyline points="22 4 12 14.01 9 11.01"/>
                     </svg>`,
            error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"/>
                      <line x1="15" y1="9" x2="9" y2="15"/>
                      <line x1="9" y1="9" x2="15" y2="15"/>
                   </svg>`,
            warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                        <line x1="12" y1="9" x2="12" y2="13"/>
                        <line x1="12" y1="17" x2="12.01" y2="17"/>
                     </svg>`,
            info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                     <circle cx="12" cy="12" r="10"/>
                     <line x1="12" y1="16" x2="12" y2="12"/>
                     <line x1="12" y1="8" x2="12.01" y2="8"/>
                  </svg>`
        };

        toast.innerHTML = `
            <div class="toast-icon">${icons[type]}</div>
            <div class="toast-content">
                <p class="toast-message">${message}</p>
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        `;

        // Agregar al contenedor
        this.container.appendChild(toast);

        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 10);

        // Auto-dismiss
        if (duration > 0) {
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }
    }

    /**
     * Limpia todos los toasts
     */
    clearAll() {
        const toasts = this.container.querySelectorAll('.toast');
        toasts.forEach(toast => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        });
    }
}

// Exportar como singleton
const toast = new ToastNotification();
export default toast;
