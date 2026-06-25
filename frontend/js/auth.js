const PUBLIC_PAGES = ['index.html', 'login.html', 'signup.html', ''];

function isPublicPage() {
  const page = window.location.pathname.split('/').pop();
  return PUBLIC_PAGES.includes(page);
}

function isAuthPage() {
  const page = window.location.pathname.split('/').pop();
  return ['login.html', 'signup.html'].includes(page);
}

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

// Auth guard — only runs on protected pages
function requireAuth() {
  if (isPublicPage()) return; // ← never redirect on public pages
  
  const token = getCookie("token") || getCookie("access_token") || localStorage.getItem("token") || localStorage.getItem("mock_token") || localStorage.getItem("meetmind_user");
  if (!token) {
    window.location.href = "/login.html";
    return;
  }

  // Asynchronously verify session details and populate username on protected pages
  fetchWithAuth(`${API_BASE_URL}/api/v1/auth/profile`).then(async (res) => {
    if (res.ok) {
      const data = await res.json();
      localStorage.setItem('meetmind_user', JSON.stringify({ email: data.email }));
      const userDisplayEl = document.getElementById('user-display');
      if (userDisplayEl) {
        userDisplayEl.textContent = data.email;
      }
    } else {
      logout();
    }
  }).catch(() => {
    logout();
  });
}

// Redirect logged-in users away from login/signup
function redirectIfLoggedIn() {
  if (!isAuthPage()) return;
  
  const token = getCookie("token") || getCookie("access_token") || localStorage.getItem("token") || localStorage.getItem("mock_token") || localStorage.getItem("meetmind_user");
  if (token) {
    window.location.href = "/dashboard.html";
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

// Run auth redirects immediately to prevent page flash/loop
requireAuth();
redirectIfLoggedIn();

// Set up logout button listener on DOM load
document.addEventListener('DOMContentLoaded', () => {
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', logout);
  }
});
