/**
 * Auth Service
 * Maneja la autenticación, sesiones y control de acceso por roles (RBAC)
 */

export class AuthService {
    constructor(apiService) {
        this.api = apiService;
        this.currentUser = null;
        this.tenant = null;
        this.token = localStorage.getItem('auth_token');

        try {
            const userData = localStorage.getItem('user_data');
            if (userData) {
                this.currentUser = JSON.parse(userData);
            }
            const tenantData = localStorage.getItem('tenant_data');
            if (tenantData) {
                this.tenant = JSON.parse(tenantData);
            }
        } catch (e) {
            console.error('Error parsing auth data:', e);
            this.logout();
        }
    }

    /**
     * Intenta iniciar sesión
     */
    async login(username, password) {
        try {
            const response = await this.api.post('/api/auth/login', { username, password });

            if (response.success && response.data && response.data.token) {
                this.token = response.data.token;
                this.currentUser = response.data.user;
                this.tenant = response.tenant || null;

                localStorage.setItem('auth_token', this.token);
                localStorage.setItem('user_data', JSON.stringify(this.currentUser));
                if (this.tenant) {
                    localStorage.setItem('tenant_data', JSON.stringify(this.tenant));
                }

                // Disparar evento de éxito
                window.dispatchEvent(new CustomEvent('auth:login_success', { detail: this.currentUser }));
                return { success: true, user: this.currentUser };
            }
            return { success: false, error: response.message || 'Respuesta invalida del servidor' };
        } catch (error) {
            console.error('Login failed:', error);
            return { success: false, error: error.message || 'Error de conexión' };
        }
    }

    /**
     * Cierra la sesión
     */
    logout() {
        this.token = null;
        this.currentUser = null;
        this.tenant = null;
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_data');
        localStorage.removeItem('tenant_data');

        // Notificar al servidor el logout (fire and forget)
        this.api.post('/api/auth/logout', {}).catch(() => { });

        window.dispatchEvent(new CustomEvent('auth:logout'));
        // Forzar recarga o mostrar login
        window.location.reload();
    }

    /**
     * Verifica si hay una sesión válida
     */
    isAuthenticated() {
        return !!this.token && !!this.currentUser;
    }

    /**
     * Obtiene los datos del usuario actual
     */
    getUser() {
        return this.currentUser;
    }

    /**
     * Verifica si el usuario tiene un rol específico
     */
    hasRole(role) {
        if (!this.currentUser) return false;
        return this.currentUser.role === role;
    }

    /**
     * Shortcut para verificar si es admin
     */
    isAdmin() {
        if (!this.currentUser) return false;
        const role = this.currentUser.role;
        return role === 'admin' || role === 'administradora';
    }

    /**
     * Actualiza los datos del usuario desde el servidor
     */
    async refreshUserData() {
        if (!this.token) return null;

        try {
            const response = await this.api.get('/api/auth/me');
            if (response && response.success && response.data) {
                this.currentUser = response.data;
                this.tenant = response.tenant || null;

                localStorage.setItem('user_data', JSON.stringify(this.currentUser));
                if (this.tenant) {
                    localStorage.setItem('tenant_data', JSON.stringify(this.tenant));
                }
                return this.currentUser;
            }
            return null;
        } catch (error) {
            if (error.status === 401) {
                this.logout();
            }
            return null;
        }
    }
}
