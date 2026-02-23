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
        if (this._isSwitching) return;
        this._isSwitching = true;

        console.log(`👁️ ViewManager: Showing main view -> ${viewId}`);

        try {
            // Ocultar todas las vistas
            this.hideAllViews();

            // Mostrar la vista solicitada
            const view = document.getElementById(`${viewId}-view`);
            if (view) {
                view.classList.add('active');
                view.style.setProperty('display', 'block', 'important');
                view.style.setProperty('visibility', 'visible', 'important');
                view.style.setProperty('opacity', '1', 'important');

                const computed = window.getComputedStyle(view);
                console.log(`✅ ViewManager: View '${viewId}-view' is now block. Actual display: ${computed.display}, visibility: ${computed.visibility}`);
            } else {
                console.warn(`⚠️ ViewManager: Main view '${viewId}-view' NOT FOUND in DOM`);
            }

            this.currentView = viewId;
            this.currentSubView = null;
        } finally {
            this._isSwitching = false;
        }
    }

    /**
     * Muestra una sub-vista y oculta todas las demás
     * @param {string} subViewId - ID de la sub-vista sin el sufijo '-view'
     */
    showSubView(subViewId) {
        if (this._isSwitching) return;
        this._isSwitching = true;

        console.log(`👁️ ViewManager: Showing sub-view -> ${subViewId}`);

        try {
            // Ocultar todas las vistas
            this.hideAllViews();

            // Mostrar la sub-vista solicitada
            const view = document.getElementById(`${subViewId}-view`);
            if (view) {
                view.classList.add('active');
                view.style.setProperty('display', 'block', 'important');
                view.style.setProperty('visibility', 'visible', 'important');
                view.style.setProperty('opacity', '1', 'important');

                const computed = window.getComputedStyle(view);
                console.log(`✅ ViewManager: Sub-view '${subViewId}-view' is now block. Actual display: ${computed.display}, visibility: ${computed.visibility}`);

                // DIAGNOSTIC: Check if children are visible
                if (view.children.length === 0) {
                    console.error(`❌ ViewManager Warning: Sub-view '${subViewId}-view' HAS NO CHILDREN!`);
                }
            } else {
                console.warn(`⚠️ ViewManager: Sub-view '${subViewId}-view' NOT FOUND in DOM`);
            }

            this.currentSubView = subViewId;
        } finally {
            this._isSwitching = false;
        }
    }

    /**
     * Oculta todas las vistas (principales y sub-vistas)
     */
    hideAllViews() {
        console.log('🙈 ViewManager: Hiding all views...');
        const views = document.querySelectorAll('.view, .content-view');
        views.forEach(v => {
            v.classList.remove('active');
            v.style.setProperty('display', 'none', 'important');
        });
        console.log(`   (Successfully hid ${views.length} views)`);
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
