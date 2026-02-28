/**
 * API Service
 * Servicio centralizado para todas las llamadas HTTP
 */

export class ApiService {
    constructor(baseURL = '') {
        this.baseURL = baseURL;
        this.defaultHeaders = {
            'Content-Type': 'application/json'
        };
    }

    async request(endpoint, options = {}) {
        // Asegurar que el endpoint no tenga espacios accidentales
        const cleanEndpoint = endpoint.trim();
        const url = `${this.baseURL}${cleanEndpoint}`;

        // Inject Authorization header if token exists
        const token = localStorage.getItem('auth_token');
        const authHeaders = token ? { 'Authorization': `Bearer ${token}` } : {};

        const config = {
            ...options,
            headers: {
                ...this.defaultHeaders,
                ...authHeaders,
                ...options.headers
            }
        };

        try {
            const response = await fetch(url, config);

            if (response.status === 401) {
                // Unauthorized: clear token and redirect/trigger login
                localStorage.removeItem('auth_token');
                localStorage.removeItem('user_data');
                if (!window.location.pathname.includes('/login')) {
                    window.dispatchEvent(new CustomEvent('auth:required'));
                }
            }

            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                let errorBody = null;

                // Professional RBAC message for 403
                if (response.status === 403) {
                    errorMessage = "Este procedimiento no se puede procesar porque no posee los privilegios necesarios.";
                }

                try {
                    const contentType = response.headers.get("content-type");
                    if (contentType && contentType.includes("application/json")) {
                        errorBody = await response.json();
                        // Only overwrite errorMessage if it wasn't already set (e.g., for 403)
                        if (errorBody && response.status !== 403) {
                            errorMessage = errorBody.message || errorBody.error || errorMessage;
                        }
                    }
                } catch (e) {
                    console.warn("Could not parse error body as JSON");
                }

                const error = new Error(errorMessage);
                error.data = errorBody || { message: errorMessage };
                error.status = response.status;
                throw error;
            }

            return await response.json();
        } catch (error) {
            // Log for developers, but quiet for expected 403 cases
            if (error.status !== 403) {
                console.error(`API Error [${options.method || 'GET'}] ${endpoint}:`, error);
            }

            // Toast feedback
            if (typeof toast !== 'undefined') {
                if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                    toast.error('Error de red: No se pudo contactar al servidor.');
                } else {
                    // Show a clean error message (like the 403 one or other simplified messages)
                    toast.error(error.message || 'Error en la petición.');
                }
            }
            throw error;
        }
    }

    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;

        return this.request(url, {
            method: 'GET'
        });
    }

    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async patch(endpoint, data) {
        return this.request(endpoint, {
            method: 'PATCH',
            body: JSON.stringify(data)
        });
    }

    async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE'
        });
    }
}
