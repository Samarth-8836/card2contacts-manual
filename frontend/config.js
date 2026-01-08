/**
 * FRONTEND CONFIGURATION - SINGLE SOURCE OF TRUTH
 *
 * All environment-specific settings are centralized here.
 * Change these values for different deployment environments.
 *
 * IMPORTANT: When deploying to production, update:
 * 1. API_BASE_URL to your production backend URL
 * 2. GOOGLE_CLIENT_ID to your production Google OAuth client ID (if different)
 */

const CONFIG = {
    // ==========================================
    // DEPLOYMENT & ENVIRONMENT
    // ==========================================
    ENVIRONMENT: 'development',  // Options: 'development', 'staging', 'production'

    // Backend API Configuration
    // For local development: empty string means same origin (relative URLs)
    // For production: set to your backend URL (e.g., 'https://api.yourdomain.com')
    API_BASE_URL: '',  // Change to 'https://your-production-backend-url.com' for production

    // Frontend URL (for redirects, share links, etc.)
    FRONTEND_URL: 'https://192.168.29.234.sslip.io:8000',  // Change to your production domain

    // ==========================================
    // GOOGLE OAUTH
    // ==========================================
    // This should match your backend's GOOGLE_CLIENT_ID
    // For production, ensure this matches your Google Cloud Console OAuth client
    GOOGLE_CLIENT_ID: '',  // Set if needed for client-side Google integrations

    // ==========================================
    // UI/UX SETTINGS
    // ==========================================
    // Maximum file size for uploads (in bytes)
    MAX_FILE_SIZE: 10 * 1024 * 1024,  // 10MB

    // Allowed image types for business card scanning
    ALLOWED_IMAGE_TYPES: ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'],

    // Bulk scan limits (should match backend BULK_SCAN_MAX_FILES)
    MAX_BULK_FILES: 100,

    // ==========================================
    // FEATURE FLAGS (for gradual rollout)
    // ==========================================
    FEATURES: {
        enableBulkScan: true,
        enableGoogleIntegration: true,
        enableEmailNotifications: true,
        enableAdvancedExport: true,
    },

    // ==========================================
    // DEBUG & LOGGING
    // ==========================================
    ENABLE_CONSOLE_LOGS: true,  // Set to false in production to reduce console noise
    ENABLE_ERROR_REPORTING: false,  // Set to true to enable error reporting service
};

// ==========================================
// HELPER FUNCTIONS
// ==========================================

/**
 * Get the full API URL for a given endpoint
 * @param {string} endpoint - API endpoint (e.g., '/api/scan')
 * @returns {string} Full API URL
 */
CONFIG.getApiUrl = function(endpoint) {
    // Ensure endpoint starts with /
    if (!endpoint.startsWith('/')) {
        endpoint = '/' + endpoint;
    }
    return this.API_BASE_URL + endpoint;
};

/**
 * Check if a feature is enabled
 * @param {string} featureName - Name of the feature
 * @returns {boolean} True if feature is enabled
 */
CONFIG.isFeatureEnabled = function(featureName) {
    return this.FEATURES[featureName] === true;
};

/**
 * Log to console if logging is enabled
 * @param {...any} args - Arguments to log
 */
CONFIG.log = function(...args) {
    if (this.ENABLE_CONSOLE_LOGS) {
        console.log('[DigiCard]', ...args);
    }
};

/**
 * Log error to console if logging is enabled
 * @param {...any} args - Arguments to log
 */
CONFIG.logError = function(...args) {
    if (this.ENABLE_CONSOLE_LOGS) {
        console.error('[DigiCard Error]', ...args);
    }

    // If error reporting is enabled, send to error reporting service
    if (this.ENABLE_ERROR_REPORTING) {
        // TODO: Implement error reporting service integration
        // Example: Sentry, LogRocket, etc.
    }
};

// Freeze the config object to prevent accidental modifications
// Comment this out if you need to modify config at runtime for testing
Object.freeze(CONFIG.FEATURES);

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CONFIG;
}
