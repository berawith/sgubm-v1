/**
 * SGUBM-V1 - Webpack Entry Point
 * This file bootstraps the application by importing existing modules
 * and integrating Tailwind CSS.
 */

// Import CSS
console.log('🔴 Index.js (Bundle Entry) executing...');
import '../css/core.css';
import '../css/dashboard.css';
import '../css/routers.css';
import '../css/clients.css';
import '../css/toast.css';
import '../css/modal.css';
import '../css/payments.css';
import '../css/plans.css';
import '../css/compact.css';

// Import existing app logic
import './app.js';

console.log('✨ SGUBM Premium Build Initialized with Tailwind CSS');
