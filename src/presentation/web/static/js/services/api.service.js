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
        const url = `${this.baseURL}${endpoint}`;

        const config = {
            ...options,
            headers: {
                ...this.defaultHeaders,
                ...options.headers
            }
        };

        try {
            const response = await fetch(url, config);

            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                try {
                    const errorBody = await response.json();
                    if (errorBody) {
                        errorMessage = errorBody.message || errorBody.error || errorMessage;
                    }
                    // Adjuntar datos extra al error si es necesario
                    const error = new Error(errorMessage);
                    error.data = errorBody;
                    throw error;
                } catch (e) {
                    if (e.data) throw e; // Si ya es el error procesado
                    throw new Error(errorMessage); // Fallback si no hay JSON
                }
            }

            return await response.json();
        } catch (error) {
            console.error(`API Error [${options.method || 'GET'}] ${endpoint}:`, error);
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
