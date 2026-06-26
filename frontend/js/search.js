// Cross-Meeting Search Screen Logic

let debounceTimer = null;

// Format Date Utility
function formatDate(isoString) {
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  } catch (e) {
    return isoString;
  }
}

// Check Profile
async function fetchUserProfile() {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/profile`);
    if (response.ok) {
      const data = await response.json();
      const userDisplay = document.getElementById('user-display');
      if (userDisplay) {
        userDisplay.textContent = data.email || 'User';
      }
    }
  } catch (err) {
    console.error("Error checking profile:", err);
  }
}

// Perform Search Request
async function performSearch(query) {
  const resultsContainer = document.getElementById('search-results');
  const emptyState = document.getElementById('search-empty-state');
  const messageEl = document.getElementById('search-message');
  
  if (!query || query.trim().length === 0) {
    resultsContainer.innerHTML = '';
    emptyState.style.display = 'block';
    messageEl.textContent = 'Enter query keywords to search across your workspace.';
    return;
  }
  
  messageEl.textContent = 'Searching workspace...';
  emptyState.style.display = 'block';
  resultsContainer.innerHTML = '';
  
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/meetings/search?q=${encodeURIComponent(query)}`);
    if (!response.ok) {
      throw new Error('Search failed');
    }
    
    const results = await response.json();
    
    if (results.length === 0) {
      messageEl.textContent = `No matches found for "${query}".`;
      emptyState.style.display = 'block';
      return;
    }
    
    emptyState.style.display = 'none';
    renderSearchResults(results, query);
    
  } catch (err) {
    console.error("Search error:", err);
    messageEl.textContent = 'Search failed. Please try again.';
    emptyState.style.display = 'block';
  }
}

// Render Results with Query Highlights
function renderSearchResults(results, query) {
  const container = document.getElementById('search-results');
  container.innerHTML = '';
  
  results.forEach(item => {
    const card = document.createElement('div');
    card.className = 'glass-card search-result-card';
    
    // Highlight helper
    const snippetHtml = highlightText(item.snippet || '', query);
    const titleHtml = highlightText(item.title || 'Untitled Meeting', query);
    
    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
        <h4 style="font-size: 1.2rem; font-weight: 700; color: white;">${titleHtml}</h4>
        <span style="font-size: 0.8rem; color: var(--text-secondary);">${formatDate(item.created_at)}</span>
      </div>
      <div class="match-snippet">
        ${snippetHtml}
      </div>
    `;
    
    card.addEventListener('click', () => {
      window.location.href = `meeting.html?id=${item.id}`;
    });
    
    container.appendChild(card);
  });
}

// Highlight matching words
function highlightText(text, query) {
  if (!text || !query) return text;
  
  // Escape special regex characters in query
  const escapedQuery = query.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
  const regex = new RegExp(`(${escapedQuery})`, 'gi');
  
  return text.replace(regex, '<mark>$1</mark>');
}

// Setup input key listeners
const searchInput = document.getElementById('search-input');
if (searchInput) {
  searchInput.addEventListener('input', (e) => {
    clearTimeout(debounceTimer);
    const query = e.target.value.trim();
    debounceTimer = setTimeout(() => {
      performSearch(query);
    }, 300); // 300ms debounce
  });
}

// Logout event
const logoutBtn = document.getElementById('logout-btn');
if (logoutBtn) {
  logoutBtn.addEventListener('click', (e) => {
    e.preventDefault();
    logout();
  });
}

function logout() {
  localStorage.removeItem('meetmind_token');
  localStorage.removeItem('meetmind_user');
  localStorage.removeItem('meetmind_is_pro');
  localStorage.removeItem('mock_token');
  
  fetch(`${API_BASE_URL}/api/v1/auth/logout`, { method: 'POST', credentials: 'include' })
    .finally(() => {
      window.location.href = 'login.html';
    });
}

// Initial load
document.addEventListener('DOMContentLoaded', () => {
  fetchUserProfile();
});
