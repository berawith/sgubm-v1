/**
 * ViewManager Service
 * Centraliza toda la lógica de visualización de vistas
 * Responsabilidad única: mostrar/ocultar vistas de manera consistente
 */

export class ViewManager {
    constructor() {
        this.currentView = null;
        this.currentSubView = null;
    }

    /**
     * Muestra una vista principal y oculta todas las demás
     * @param {string} viewId - ID de la vista sin el sufijo '-view'
     */
    showMainView(viewId) {
        console.log(`👁️ ViewManager: Showing main view -> ${viewId}`);

        // Ocultar TODAS las vistas (principales y sub-vistas)
        this.hideAllViews();

        // Mostrar la vista solicitada
        const view = document.getElementById(`${viewId}-view`);
        if (view) {
            view.classList.add('active');
            view.style.display = 'block';
        } else {
            console.warn(`⚠️ ViewManager: View '${viewId}-view' not found`);
        }

        this.currentView = viewId;
        this.currentSubView = null;
    }

    /**
     * Muestra una sub-vista y oculta todas las demás
     * @param {string} subViewId - ID de la sub-vista sin el sufijo '-view'
     */
    showSubView(subViewId) {
        console.log(`👁️ ViewManager: Showing sub-view -> ${subViewId}`);

        // Ocultar todas las vistas
        this.hideAllViews();

        // Mostrar la sub-vista solicitada
        const view = document.getElementById(`${subViewId}-view`);
        if (view) {
            view.classList.add('active');
            view.style.display = 'block';
        } else {
            console.warn(`⚠️ ViewManager: Sub-view '${subViewId}-view' not found`);
        }

        this.currentSubView = subViewId;
    }

    /**
     * Oculta todas las vistas (principales y sub-vistas)
     */
    hideAllViews() {
        document.querySelectorAll('.view, .content-view').forEach(v => {
            v.classList.remove('active');
            v.style.display = 'none';
        });
    }

    /**
     * Obtiene la vista actual
     * @returns {Object} - {main: string|null, sub: string|null}
     */
    getCurrentView() {
        return {
            main: this.currentView,
            sub: this.currentSubView
        };
    }
}
