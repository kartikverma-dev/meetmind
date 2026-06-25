// Global Configurations
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : 'https://meetmind-backend-90u7.onrender.com';

// Cookie Helper
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

// Fetch wrapper to handle httpOnly cookies, CSRF tokens, and 401 refresh token flow.
async function fetchWithAuth(url, options = {}) {
  options.credentials = 'include';
  options.headers = options.headers || {};
  
  // Inject mock token if present (for mock mode backward compatibility)
  const mockToken = localStorage.getItem('mock_token');
  if (mockToken) {
    options.headers['Authorization'] = `Bearer ${mockToken}`;
  }

  // Inject CSRF token on state-changing requests
  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'DELETE'].includes(method)) {
    const csrfToken = getCookie('csrf_token');
    if (csrfToken) {
      options.headers['X-CSRF-Token'] = csrfToken;
    }
  }

  let response = await fetch(url, options);
  
  if (response.status === 401) {
    // Attempt to refresh the session
    try {
      const refreshRes = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: 'POST',
        credentials: 'include'
      });
      if (refreshRes.ok) {
        // Retry the original request
        response = await fetch(url, options);
      } else {
        // Refresh failed, redirect to login
        logout();
      }
    } catch (err) {
      logout();
    }
  }
  return response;
}

function getLoggedInUser() {
  const userStr = localStorage.getItem('meetmind_user');
  return userStr ? JSON.parse(userStr) : null;
}

// Check route protection using profile endpoint verification
async function checkAuth() {
  const currentPath = window.location.pathname;
  const isAuthPage = currentPath.includes('login.html') || currentPath.includes('signup.html');
  const isLandingPage = currentPath.endsWith('/') || currentPath.includes('index.html') || currentPath === '';
  
  if (isAuthPage || isLandingPage) {
    // Check if logged in on public landing page to show dashboard links
    try {
      const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/profile`);
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('meetmind_user', JSON.stringify({ email: data.email }));
        const userDisplayEl = document.getElementById('user-display');
        if (userDisplayEl) {
          userDisplayEl.textContent = data.email;
        }
      }
    } catch (e) {}
    return;
  }

  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/profile`);
    if (!res.ok) {
      window.location.href = 'login.html';
    } else {
      const data = await res.json();
      localStorage.setItem('meetmind_user', JSON.stringify({ email: data.email }));
      const userDisplayEl = document.getElementById('user-display');
      if (userDisplayEl) {
        userDisplayEl.textContent = data.email;
      }
    }
  } catch (err) {
    window.location.href = 'login.html';
  }
}

// Perform logout
async function logout() {
  try {
    await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
      method: 'POST',
      credentials: 'include'
    });
  } catch (e) {
    console.error('Logout request failed:', e);
  }
  localStorage.removeItem('mock_token');
  localStorage.removeItem('meetmind_user');
  window.location.href = 'index.html';
}

// Initialize Auth Checking & UI displays
document.addEventListener('DOMContentLoaded', () => {
  checkAuth();
  
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', logout);
  }
});
