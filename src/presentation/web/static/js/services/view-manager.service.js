/**
 * ViewManager Service
 * Centraliza toda la lógica de visualización de vistas
 * Responsabilidad única: mostrar/ocultar vistas de manera consistente
 */

export class ViewManager {
    constructor() {
        this.currentView = null;
        this.currentSubView = null;
        this.activeMainElement = null;
        this.activeSubElement = null;
    }

    /**
     * Muestra una vista principal y oculta todas las demás
     * @param {string} viewId - ID de la vista sin el sufijo '-view'
     */
    showMainView(viewId) {
        if (this._isSwitching) return;
        if (this.currentView === viewId && !this.currentSubView) {
            console.log(`👁️ ViewManager: View ${viewId} is already active, skipping.`);
            return;
        }
        this._isSwitching = true;

        console.log(`👁️ ViewManager: Showing main view -> ${viewId}`);

        try {
            // Ocultar vistas activas anteriores (Optimizado)
            if (!this.activeMainElement) {
                // Si es la primera navegación, ocultar cualquier vista que venga 'active' por defecto del HTML
                this.hideAllViews();
            } else {
                this._hideActiveElements();
            }

            // Mostrar la vista solicitada
            const view = document.getElementById(`${viewId}-view`);
            if (view) {
                this._showElement(view);
                console.log(`✅ ViewManager: View '${viewId}-view' is now active.`);
                this.activeMainElement = view;
            } else {
                console.warn(`⚠️ ViewManager: Main view '${viewId}-view' NOT FOUND in DOM`);
                this.hideAllViews(); // Fallback si el estado se corrompe
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
        if (this.currentSubView === subViewId) {
            console.log(`👁️ ViewManager: Sub-view ${subViewId} is already active, skipping.`);
            return;
        }
        this._isSwitching = true;

        console.log(`👁️ ViewManager: Showing sub-view -> ${subViewId}`);

        try {
            // Ocultar sub-vista anterior si existe
            if (this.activeSubElement) {
                this._hideElement(this.activeSubElement);
            } else {
                // Si no hay referencia, por seguridad ocultamos todas las sub-vistas
                this.hideAllViews();
            }

            // Mostrar la sub-vista solicitada
            const view = document.getElementById(`${subViewId}-view`);
            if (view) {
                this._showElement(view);
                console.log(`✅ ViewManager: Sub-view '${subViewId}-view' is now active.`);
                this.activeSubElement = view;

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
     * Oculta todas las vistas (principales y sub-vistas) como fallback
     */
    hideAllViews() {
        console.log('🙈 ViewManager: Hiding all views (Brute force)...');
        const views = document.querySelectorAll('.view, .content-view');
        views.forEach(v => this._hideElement(v));
        this.activeMainElement = null;
        this.activeSubElement = null;
        console.log(`   (Successfully hid ${views.length} views)`);
    }

    /**
     * Métodos privados de ayuda para consistencia
     */
    _hideActiveElements() {
        if (this.activeMainElement) this._hideElement(this.activeMainElement);
        if (this.activeSubElement) this._hideElement(this.activeSubElement);

        // Limpiar referencias
        this.activeMainElement = null;
        this.activeSubElement = null;
    }

    _hideElement(el) {
        if (!el) return;
        el.classList.remove('active');
        el.style.setProperty('display', 'none', 'important');
    }

    _showElement(el) {
        if (!el) return;
        el.classList.add('active');
        el.style.setProperty('display', 'block', 'important');
        el.style.setProperty('visibility', 'visible', 'important');
        el.style.setProperty('opacity', '1', 'important');
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
