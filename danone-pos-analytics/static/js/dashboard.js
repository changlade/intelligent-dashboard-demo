// Danone POS Analytics - Dashboard JavaScript

// DOM elements
const dashboardContainer = document.getElementById('dashboardContainer');

// Initialize dashboard
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Dashboard initializing...');
    
    try {
        await loadDashboard();
    } catch (error) {
        console.error('Dashboard load error:', error);
        showError('Failed to load dashboard. Please try again later.');
    }
});

// Load dashboard configuration and embed iframe
async function loadDashboard() {
    try {
        // Fetch dashboard configuration from backend
        const response = await fetch('/api/dashboard/config');
        const result = await response.json();
        
        if (result.status === 'success' && result.data) {
            const config = result.data;
            
            // Create iframe with embed URL
            const iframe = document.createElement('iframe');
            iframe.className = 'dashboard-iframe';
            iframe.src = config.embed_url;
            iframe.allow = 'fullscreen';
            iframe.title = 'Danone POS Analytics Dashboard';
            
            // Add load event listener
            iframe.addEventListener('load', () => {
                console.log('Dashboard loaded successfully');
            });
            
            // Add error event listener
            iframe.addEventListener('error', (e) => {
                console.error('Dashboard iframe error:', e);
                showError('Dashboard failed to load. Please check your connection.');
            });
            
            // Clear loading state and add iframe
            dashboardContainer.innerHTML = '';
            dashboardContainer.appendChild(iframe);
            
            console.log('Dashboard iframe created:', config.embed_url);
            
        } else {
            throw new Error(result.error || 'Failed to fetch dashboard configuration');
        }
        
    } catch (error) {
        console.error('Load dashboard error:', error);
        throw error;
    }
}

// Show error message
function showError(message) {
    dashboardContainer.innerHTML = `
        <div class="error-message" style="margin: 2rem;">
            <h3>Dashboard Error</h3>
            <p>${message}</p>
            <button class="btn btn-primary" onclick="location.reload()">Retry</button>
        </div>
    `;
}

// Refresh dashboard
function refreshDashboard() {
    dashboardContainer.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <span>Refreshing dashboard...</span>
        </div>
    `;
    loadDashboard();
}

// Make available globally
window.refreshDashboard = refreshDashboard;

