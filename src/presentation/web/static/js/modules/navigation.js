/**
 * Navigation Module
 * Maneja la navegación entre vistas
 */

export class NavigationModule {
    constructor(eventBus) {
        this.eventBus = eventBus;
        this.init();
    }

    init() {
        console.log('🧭 Navigation Module initialized');
        this.attachEvents();
    }

    attachEvents() {
        // Escuchar clicks en nav items
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const view = item.dataset.view;
                if (view) {
                    this.navigate(view);
                }
            });
        });
    }

    navigate(view, params = {}) {
        console.log(`🧭 Navigating to: ${view}`);

        // Actualizar UI del sidebar
        document.querySelectorAll('.nav-item').forEach(item => {
            if (item.dataset.view === view) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        // Publicar evento de navegación
        this.eventBus.publish('navigate', { view, ...params });

        // Actualizar URL sin recargar
        const url = view === 'dashboard' ? '/' : `/${view}`;
        window.history.pushState({ view, params }, '', url);

        // Actualizar título de la página
        document.title = `SGUBM - ${view.charAt(0).toUpperCase() + view.slice(1)}`;
    }
}
