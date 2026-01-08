// Admin Dashboard JavaScript
// DigiCard App Owner Dashboard

// State management
const state = {
    token: null,
    userData: null,
    users: [],
    usersFilter: 'all',
    usersSearch: ''
};

// DOM Elements
const els = {
    loginPage: document.getElementById('login-page'),
    dashboardPage: document.getElementById('dashboard-page'),
    loginForm: document.getElementById('login-form'),
    loginError: document.getElementById('login-error'),
    btnLogin: document.getElementById('btn-login'),
    btnLogout: document.getElementById('btn-logout'),
    btnRefresh: document.getElementById('btn-refresh'),
    userName: document.getElementById('user-name'),
    distributorsContainer: document.getElementById('distributors-container'),
    statTotalUsers: document.getElementById('stat-total-users'),
    statLicensedUsers: document.getElementById('stat-licensed-users'),
    statDistributors: document.getElementById('stat-distributors'),
    statNewAccounts: document.getElementById('stat-new-accounts'),
    userTypeFilter: document.getElementById('user-type-filter'),
    userSearch: document.getElementById('user-search'),
    btnRefreshUsers: document.getElementById('btn-refresh-users'),
    usersContainer: document.getElementById('users-container')
};

// ==========================================
// AUTHENTICATION
// ==========================================

function checkAuth() {
    const token = localStorage.getItem('admin_token');
    if (token) {
        state.token = token;
        loadDashboard();
    } else {
        showLogin();
    }
}

function showLogin() {
    els.loginPage.classList.remove('hidden');
    els.dashboardPage.classList.remove('active');
}

function showDashboard() {
    els.loginPage.classList.add('hidden');
    els.dashboardPage.classList.add('active');
}

async function login(email, password) {
    try {
        els.btnLogin.disabled = true;
        els.btnLogin.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Logging in...';
        els.loginError.classList.add('hidden');

        const response = await fetch('/api/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }

        const data = await response.json();
        state.token = data.access_token;
        state.userData = { full_name: data.full_name };
        localStorage.setItem('admin_token', data.access_token);

        showDashboard();
        loadDashboard();

    } catch (error) {
        els.loginError.textContent = error.message;
        els.loginError.classList.remove('hidden');
    } finally {
        els.btnLogin.disabled = false;
        els.btnLogin.innerHTML = '<i class="fa-solid fa-right-to-bracket"></i> Login';
    }
}

function logout() {
    state.token = null;
    state.userData = null;
    localStorage.removeItem('admin_token');
    showLogin();
}

// ==========================================
// DASHBOARD LOADING
// ==========================================

async function loadDashboard() {
    try {
        // Load profile
        await loadProfile();

        // Load system stats
        await loadSystemStats();

        // Load distributor activity
        await loadDistributorActivity();

        // Load users
        await loadUsers();

    } catch (error) {
        console.error('Dashboard load error:', error);
        if (error.message.includes('401') || error.message.includes('Session expired')) {
            logout();
        }
    }
}

async function loadProfile() {
    try {
        const response = await fetch(`/api/admin/profile?token=${state.token}`);

        if (!response.ok) {
            throw new Error('Failed to load profile');
        }

        const data = await response.json();
        els.userName.textContent = data.full_name;

    } catch (error) {
        console.error('Profile load error:', error);
        throw error;
    }
}

async function loadSystemStats() {
    try {
        const response = await fetch(`/api/admin/system-stats?token=${state.token}`);

        if (!response.ok) {
            throw new Error('Failed to load system stats');
        }

        const data = await response.json();

        // Update stats
        els.statTotalUsers.textContent = data.users.total_all_users.toLocaleString();
        els.statLicensedUsers.textContent = data.users.licensed.toLocaleString();
        els.statDistributors.textContent = data.distributors.total_active.toLocaleString();
        els.statNewAccounts.textContent = data.recent_activity_30_days.total_new_accounts.toLocaleString();

    } catch (error) {
        console.error('System stats load error:', error);
        throw error;
    }
}

async function loadDistributorActivity() {
    try {
        els.distributorsContainer.innerHTML = `
            <div class="loading">
                <i class="fa-solid fa-spinner"></i>
                <p>Loading distributor activity...</p>
            </div>
        `;

        const response = await fetch(`/api/admin/distributor-activity?token=${state.token}`);

        if (!response.ok) {
            throw new Error('Failed to load distributor activity');
        }

        const data = await response.json();

        if (data.total_distributors === 0) {
            els.distributorsContainer.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #888;">
                    <i class="fa-solid fa-inbox" style="font-size: 48px; margin-bottom: 15px; opacity: 0.3;"></i>
                    <p>No distributors found</p>
                </div>
            `;
            return;
        }

        // Render distributors
        let html = '';
        data.distributors.forEach(dist => {
            html += renderDistributor(dist);
        });

        els.distributorsContainer.innerHTML = html;

    } catch (error) {
        console.error('Distributor activity load error:', error);
        els.distributorsContainer.innerHTML = `
            <div class="error-message">
                <i class="fa-solid fa-triangle-exclamation"></i>
                Failed to load distributor activity: ${error.message}
            </div>
        `;
        throw error;
    }
}

function renderDistributor(dist) {
    const createdDate = new Date(dist.created_at).toLocaleDateString();
    const accountsListId = `accounts-${dist.distributor_id}`;

    let accountsHtml = '';
    if (dist.accounts && dist.accounts.length > 0) {
        accountsHtml = `
            <div class="accounts-list" id="${accountsListId}">
                <table class="accounts-table">
                    <thead>
                        <tr>
                            <th>Email</th>
                            <th>Type</th>
                            <th>Created</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${dist.accounts.map(acc => `
                            <tr>
                                <td>${acc.email}</td>
                                <td><span class="badge badge-${acc.account_type}">${acc.account_type}</span></td>
                                <td>${new Date(acc.created_at).toLocaleString()}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    }

    return `
        <div class="distributor-card">
            <div class="distributor-header">
                <div class="distributor-info">
                    <h3><i class="fa-solid fa-briefcase"></i> ${dist.distributor_email}</h3>
                    <p>Distributor ID: ${dist.distributor_id} • Type: ${dist.distributor_type} • Since: ${createdDate}</p>
                </div>
                <div class="distributor-stats">
                    <div class="distributor-stat">
                        <div class="distributor-stat-value">${dist.total_accounts_created}</div>
                        <div class="distributor-stat-label">Total</div>
                    </div>
                    <div class="distributor-stat">
                        <div class="distributor-stat-value">${dist.single_accounts_count}</div>
                        <div class="distributor-stat-label">Single</div>
                    </div>
                    <div class="distributor-stat">
                        <div class="distributor-stat-value">${dist.enterprise_accounts_count}</div>
                        <div class="distributor-stat-label">Enterprise</div>
                    </div>
                </div>
            </div>
            ${dist.accounts && dist.accounts.length > 0 ? `
                <button class="toggle-accounts" onclick="toggleAccounts('${accountsListId}')">
                    <i class="fa-solid fa-eye"></i> View ${dist.accounts.length} Account${dist.accounts.length > 1 ? 's' : ''}
                </button>
                ${accountsHtml}
            ` : '<p style="color: #888; font-size: 14px;">No accounts created yet</p>'}
        </div>
    `;
}

function toggleAccounts(listId) {
    const list = document.getElementById(listId);
    if (list) {
        list.classList.toggle('expanded');
    }
}

// Make toggleAccounts globally available
window.toggleAccounts = toggleAccounts;

// ==========================================
// USER MANAGEMENT
// ==========================================

async function loadUsers() {
    try {
        els.usersContainer.innerHTML = `
            <div class="loading">
                <i class="fa-solid fa-spinner"></i>
                <p>Loading users...</p>
            </div>
        `;

        const params = new URLSearchParams({
            token: state.token,
            user_type: state.usersFilter === 'non_distributors' ? 'all' : state.usersFilter,
            only_non_distributors: state.usersFilter === 'non_distributors' ? 'true' : 'false'
        });

        const response = await fetch(`/api/admin/all-users?${params}`);

        if (!response.ok) {
            throw new Error('Failed to load users');
        }

        const data = await response.json();
        state.users = data.users;

        renderUsers();

    } catch (error) {
        console.error('Users load error:', error);
        els.usersContainer.innerHTML = `
            <div class="error-message">
                <i class="fa-solid fa-triangle-exclamation"></i>
                Failed to load users: ${error.message}
            </div>
        `;
    }
}

function renderUsers() {
    // Filter users based on search
    let filteredUsers = state.users;

    if (state.usersSearch) {
        const search = state.usersSearch.toLowerCase();
        filteredUsers = filteredUsers.filter(user =>
            user.email.toLowerCase().includes(search)
        );
    }

    if (filteredUsers.length === 0) {
        els.usersContainer.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #888;">
                <i class="fa-solid fa-inbox" style="font-size: 48px; margin-bottom: 15px; opacity: 0.3;"></i>
                <p>No users found</p>
            </div>
        `;
        return;
    }

    let html = `
        <table class="users-table">
            <thead>
                <tr>
                    <th>Email</th>
                    <th>User Type</th>
                    <th>Created</th>
                    <th>Distributor Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
    `;

    filteredUsers.forEach(user => {
        const createdDate = new Date(user.created_at).toLocaleDateString();

        let distributorBadge = '<span class="badge badge-inactive">Not Distributor</span>';
        let actionButton = `
            <button class="btn-promote" onclick="promoteToDistributor('${user.email}', '${user.user_type}')">
                <i class="fa-solid fa-arrow-up"></i> Promote
            </button>
        `;

        if (user.is_distributor) {
            if (user.distributor_active) {
                distributorBadge = '<span class="badge badge-distributor">Active Distributor</span>';
                actionButton = `
                    <button class="btn-revoke" onclick="revokeDistributor('${user.email}', '${user.user_type}')">
                        <i class="fa-solid fa-ban"></i> Revoke
                    </button>
                `;
            } else {
                distributorBadge = '<span class="badge badge-inactive">Inactive Distributor</span>';
                actionButton = `
                    <button class="btn-promote" onclick="promoteToDistributor('${user.email}', '${user.user_type}')">
                        <i class="fa-solid fa-arrow-up"></i> Reactivate
                    </button>
                `;
            }
        }

        const userTypeBadge = user.user_type === 'enterprise_admin' ? 'enterprise' : 'single';
        const userTypeLabel = user.user_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());

        html += `
            <tr>
                <td>${user.email}</td>
                <td><span class="badge badge-${userTypeBadge}">${userTypeLabel}</span></td>
                <td>${createdDate}</td>
                <td>${distributorBadge}</td>
                <td>${actionButton}</td>
            </tr>
        `;
    });

    html += `
            </tbody>
        </table>
    `;

    els.usersContainer.innerHTML = html;
}

async function promoteToDistributor(email, userType) {
    if (!confirm(`Are you sure you want to promote ${email} to distributor role?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/admin/promote-distributor?token=${state.token}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, user_type: userType })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Promotion failed');
        }

        const data = await response.json();

        // Show success message
        showSuccessMessage(data.message);

        // Reload users table
        await loadUsers();

    } catch (error) {
        showErrorMessage(error.message);
    }
}

async function revokeDistributor(email, userType) {
    if (!confirm(`Are you sure you want to revoke distributor role from ${email}?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/admin/revoke-distributor?token=${state.token}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, user_type: userType })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Revocation failed');
        }

        const data = await response.json();

        // Show success message
        showSuccessMessage(data.message);

        // Reload users table
        await loadUsers();

    } catch (error) {
        showErrorMessage(error.message);
    }
}

function showSuccessMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'success-message';
    messageDiv.innerHTML = `
        <i class="fa-solid fa-check-circle"></i>
        ${message}
    `;

    els.usersContainer.insertBefore(messageDiv, els.usersContainer.firstChild);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        messageDiv.remove();
    }, 5000);
}

function showErrorMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'error-message';
    messageDiv.innerHTML = `
        <i class="fa-solid fa-triangle-exclamation"></i>
        ${message}
    `;

    els.usersContainer.insertBefore(messageDiv, els.usersContainer.firstChild);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        messageDiv.remove();
    }, 5000);
}

// Make functions globally available for onclick handlers
window.promoteToDistributor = promoteToDistributor;
window.revokeDistributor = revokeDistributor;

// ==========================================
// EVENT LISTENERS
// ==========================================

els.loginForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    login(email, password);
});

els.btnLogout.addEventListener('click', () => {
    if (confirm('Are you sure you want to logout?')) {
        logout();
    }
});

els.btnRefresh.addEventListener('click', async () => {
    els.btnRefresh.disabled = true;
    els.btnRefresh.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Refreshing...';

    try {
        await loadSystemStats();
        await loadDistributorActivity();
    } finally {
        els.btnRefresh.disabled = false;
        els.btnRefresh.innerHTML = '<i class="fa-solid fa-rotate"></i> Refresh';
    }
});

// User type filter
els.userTypeFilter.addEventListener('change', (e) => {
    state.usersFilter = e.target.value;
    loadUsers();
});

// Search input
els.userSearch.addEventListener('input', (e) => {
    state.usersSearch = e.target.value;
    renderUsers();
});

// Refresh users button
els.btnRefreshUsers.addEventListener('click', async () => {
    els.btnRefreshUsers.disabled = true;
    els.btnRefreshUsers.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Refreshing...';

    try {
        await loadUsers();
    } finally {
        els.btnRefreshUsers.disabled = false;
        els.btnRefreshUsers.innerHTML = '<i class="fa-solid fa-rotate"></i> Refresh';
    }
});

// ==========================================
// INITIALIZATION
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
});
