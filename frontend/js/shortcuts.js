// Keyboard Shortcuts for MeetMind v2.0

document.addEventListener('keydown', (e) => {
  const activeEl = document.activeElement;
  const isInput = activeEl && (
    activeEl.tagName === 'INPUT' || 
    activeEl.tagName === 'TEXTAREA' || 
    activeEl.tagName === 'SELECT' || 
    activeEl.isContentEditable
  );
  
  // 1. Escape key to close modal overlays (even when inside an input)
  if (e.key === 'Escape') {
    const overlays = document.querySelectorAll('.modal-overlay');
    let closed = false;
    overlays.forEach(overlay => {
      if (overlay.style.display === 'flex' || overlay.style.display === 'block') {
        overlay.style.display = 'none';
        closed = true;
      }
    });
    if (closed) {
      e.preventDefault();
      if (activeEl) activeEl.blur();
    }
    return;
  }
  
  // Avoid triggering navigation shortcuts if the user is currently typing
  if (isInput) return;
  
  const key = e.key.toLowerCase();
  
  // 2. 'n' key -> Redirect to recorder.html
  if (key === 'n') {
    e.preventDefault();
    window.location.href = 'recorder.html';
  }
  
  // 3. 'u' key -> Trigger upload modal on dashboard
  if (key === 'u') {
    e.preventDefault();
    const currentPage = window.location.pathname.split('/').pop();
    if (currentPage === 'dashboard.html') {
      if (typeof triggerUploadModal === 'function') {
        triggerUploadModal();
      }
    } else {
      window.location.href = 'dashboard.html?action=upload';
    }
  }
  
  // 4. '/' key -> Focus search box or redirect to search.html
  if (e.key === '/') {
    e.preventDefault();
    const currentPage = window.location.pathname.split('/').pop();
    if (currentPage === 'search.html') {
      const searchBox = document.getElementById('search-input');
      if (searchBox) {
        searchBox.focus();
        searchBox.select();
      }
    } else {
      window.location.href = 'search.html';
    }
  }
});
