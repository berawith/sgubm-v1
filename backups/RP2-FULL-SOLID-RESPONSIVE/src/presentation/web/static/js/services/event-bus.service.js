/**
 * Event Bus Service
 * Sistema de eventos pub/sub para comunicación desacoplada entre módulos
 */

export class EventBus {
    constructor() {
        this.events = {};
    }

    subscribe(eventName, callback) {
        if (!this.events[eventName]) {
            this.events[eventName] = [];
        }

        this.events[eventName].push(callback);

        // Retornar función para desuscribirse
        return () => {
            this.unsubscribe(eventName, callback);
        };
    }

    unsubscribe(eventName, callback) {
        if (!this.events[eventName]) return;

        this.events[eventName] = this.events[eventName].filter(cb => cb !== callback);
    }

    publish(eventName, data = {}) {
        if (!this.events[eventName]) return;

        console.log(`📡 Event published: ${eventName}`, data);

        this.events[eventName].forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                console.error(`Error in event handler for ${eventName}:`, error);
            }
        });
    }

    clear(eventName) {
        if (eventName) {
            delete this.events[eventName];
        } else {
            this.events = {};
        }
    }
}
