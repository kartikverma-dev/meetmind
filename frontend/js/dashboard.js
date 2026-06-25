// DOM Elements
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const meetingTitleInput = document.getElementById('meeting-title');
const processBtn = document.getElementById('process-btn');
const uploadAlert = document.getElementById('upload-alert');
const progressBar = document.getElementById('progress-bar');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const meetingsGrid = document.getElementById('meetings-grid');
const emptyState = document.getElementById('empty-state');

let selectedFile = null;

// Format Date Utility
function formatDate(isoString) {
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (e) {
    return isoString;
  }
}

// Check Profile & Populate Beta Badges/Referral info
async function fetchUserProfile() {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/profile`);
    if (response.ok) {
      const data = await response.json();
      
      const userDisplay = document.getElementById('user-display');
      if (userDisplay) {
        const user = getLoggedInUser();
        const email = (user && user.email) || data.email || 'User';
        userDisplay.textContent = `${email} [Beta User — Full Access]`;
      }

      // Populate referral link
      const referralLinkInput = document.getElementById('referral-link-input');
      if (referralLinkInput) {
        referralLinkInput.value = `https://meetmind-nine.vercel.app?ref=${data.referral_code}`;
      }

      // Display Share Banner if not dismissed
      const shareBanner = document.getElementById('share-banner');
      if (shareBanner && !localStorage.getItem('dismissed_share_banner')) {
        shareBanner.style.display = 'flex';
      }
    }
  } catch (err) {
    console.error("Error checking profile:", err);
  }
}

// Fetch Meetings List
async function fetchMeetings() {
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/meetings`);
    
    if (!response.ok) {
      if (response.status === 401) {
        logout();
        return;
      }
      throw new Error('Failed to load meetings');
    }
    
    const meetings = await response.json();
    renderMeetings(meetings);
  } catch (err) {
    console.error(err);
    uploadAlert.textContent = 'Failed to load historical meetings.';
    uploadAlert.style.display = 'block';
  }
}

// Render Meetings Grid
function renderMeetings(meetings) {
  meetingsGrid.innerHTML = '';
  
  if (meetings.length === 0) {
    emptyState.style.display = 'block';
    return;
  }
  
  emptyState.style.display = 'none';
  
  meetings.forEach(meeting => {
    const card = document.createElement('div');
    card.className = 'glass-card meeting-card';
    
    let badgeClass = 'badge-processing';
    let statusText = 'Processing';
    if (meeting.status === 'done') {
      badgeClass = 'badge-done';
      statusText = 'Done';
    } else if (meeting.status === 'failed') {
      badgeClass = 'badge-failed';
      statusText = 'Failed';
    }
    
    // Create elements securely using DOM APIs to prevent XSS
    const titleEl = document.createElement('h4');
    titleEl.style.cssText = "font-size: 1.15rem; font-weight: 700; margin-bottom: 0.5rem; word-break: break-word; flex-grow: 1;";
    titleEl.textContent = meeting.title;

    card.innerHTML = `
      <div class="card-header-row" style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; width: 100%;">
        <button class="delete-btn" style="background: none; border: none; color: var(--text-secondary); cursor: pointer; padding: 6px; border-radius: 6px; display: flex; align-items: center; justify-content: center; transition: all 0.2s;" title="Delete Meeting">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="pointer-events: none;">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      </div>
      <div class="meeting-meta" style="margin-top: auto; display: flex; justify-content: space-between; align-items: center;">
        <span class="created-at-display"></span>
        <span class="badge ${badgeClass}">${statusText}</span>
      </div>
    `;
    
    // Insert dynamic title and created date safely
    card.querySelector('.card-header-row').insertBefore(titleEl, card.querySelector('.delete-btn'));
    card.querySelector('.created-at-display').textContent = formatDate(meeting.created_at);
    
    // Add delete event listener
    const deleteBtn = card.querySelector('.delete-btn');
    deleteBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (confirm(`Are you sure you want to delete "${meeting.title}"?`)) {
        try {
          const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/meetings/${meeting.id}`, {
            method: 'DELETE'
          });
          if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'Failed to delete meeting');
          }
          // Remove card from DOM and refresh profile
          card.remove();
          fetchUserProfile();
          
          if (meetingsGrid.children.length === 0) {
            emptyState.style.display = 'block';
          }
        } catch (err) {
          alert(`Error: ${err.message}`);
        }
      }
    });
    
    card.addEventListener('click', () => {
      window.location.href = `meeting.html?id=${meeting.id}`;
    });
    
    meetingsGrid.appendChild(card);
  });
}

// Drag & Drop Handlers
dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  
  if (e.dataTransfer.files.length > 0) {
    handleFileSelect(e.dataTransfer.files[0]);
  }
});

fileInput.addEventListener('change', () => {
  if (fileInput.files.length > 0) {
    handleFileSelect(fileInput.files[0]);
  }
});

function handleFileSelect(file) {
  selectedFile = file;
  
  // Show selected file name securely
  dropZone.querySelector('h4').textContent = file.name;
  dropZone.querySelector('p').textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
  
  // Enable process button
  processBtn.disabled = false;
}

// Handle Process Upload
processBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  
  const title = meetingTitleInput.value.trim() || 'Untitled Meeting';
  
  // Reset alerts & status
  uploadAlert.style.display = 'none';
  progressBar.style.display = 'block';
  progressFill.style.width = '0%';
  progressText.style.display = 'block';
  progressText.textContent = 'Uploading recording file...';
  processBtn.disabled = true;
  
  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('title', title);
  
  try {
    // Simulated upload progress
    let progressVal = 0;
    const progressInterval = setInterval(() => {
      progressVal += 5;
      if (progressVal >= 90) {
        clearInterval(progressInterval);
        progressText.textContent = 'Transcribing audio & extracting MOM (this may take up to a minute)...';
      }
      progressFill.style.width = `${progressVal}%`;
    }, 150);

    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/meetings/upload`, {
      method: 'POST',
      body: formData
    });
    
    clearInterval(progressInterval);
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to process meeting');
    }
    
    progressFill.style.width = '100%';
    progressText.textContent = 'Processing complete!';
    
    // Refresh page/grid
    setTimeout(() => {
      progressBar.style.display = 'none';
      progressText.style.display = 'none';
      meetingTitleInput.value = '';
      
      // Reset drop zone text securely
      dropZone.querySelector('h4').textContent = 'Drag & drop your recording file here';
      dropZone.querySelector('p').textContent = 'or click to select file from your system';
      selectedFile = null;
      
      fetchMeetings();
    }, 1000);
    
  } catch (err) {
    console.error(err);
    uploadAlert.textContent = err.message;
    uploadAlert.style.display = 'block';
    
    progressBar.style.display = 'none';
    progressText.style.display = 'none';
    processBtn.disabled = false;
  }
});

// Dismiss share banner
const closeShareBanner = document.getElementById('close-share-banner');
if (closeShareBanner) {
  closeShareBanner.addEventListener('click', () => {
    document.getElementById('share-banner').style.display = 'none';
    localStorage.setItem('dismissed_share_banner', 'true');
  });
}

// Copy referral link button
const copyRefBtn = document.getElementById('copy-ref-btn');
if (copyRefBtn) {
  copyRefBtn.addEventListener('click', () => {
    const input = document.getElementById('referral-link-input');
    const msg = `Enjoying MeetMind? Share it with your friends and get lifetime priority access! Register here: ${input.value}`;
    navigator.clipboard.writeText(msg).then(() => {
      copyRefBtn.textContent = 'Copied!';
      setTimeout(() => {
        copyRefBtn.textContent = 'Copy Link';
      }, 2000);
    });
  });
}

// Feedback Widget Modal logic
let selectedRating = 0;
const feedbackModal = document.getElementById('feedback-modal');
const feedbackWidgetBtn = document.getElementById('feedback-widget-btn');
const closeFeedbackModal = document.getElementById('close-feedback-modal');
const submitFeedbackBtn = document.getElementById('submit-feedback-btn');
const stars = document.querySelectorAll('.feedback-star');

if (feedbackWidgetBtn) {
  feedbackWidgetBtn.addEventListener('click', () => {
    selectedRating = 0;
    stars.forEach(s => s.style.color = 'var(--text-muted)');
    document.getElementById('feedback-message').value = '';
    document.getElementById('feedback-alert').style.display = 'none';
    document.getElementById('feedback-success').style.display = 'none';
    feedbackModal.style.display = 'flex';
  });
}

if (closeFeedbackModal) {
  closeFeedbackModal.addEventListener('click', () => {
    feedbackModal.style.display = 'none';
  });
}

stars.forEach(star => {
  star.addEventListener('mouseover', () => {
    const rating = parseInt(star.getAttribute('data-rating'));
    stars.forEach(s => {
      if (parseInt(s.getAttribute('data-rating')) <= rating) {
        s.style.color = '#F59E0B';
      } else {
        s.style.color = 'var(--text-muted)';
      }
    });
  });
  star.addEventListener('mouseout', () => {
    stars.forEach(s => {
      if (parseInt(s.getAttribute('data-rating')) <= selectedRating) {
        s.style.color = '#F59E0B';
      } else {
        s.style.color = 'var(--text-muted)';
      }
    });
  });
  star.addEventListener('click', () => {
    selectedRating = parseInt(star.getAttribute('data-rating'));
  });
});

if (submitFeedbackBtn) {
  submitFeedbackBtn.addEventListener('click', async () => {
    if (selectedRating === 0) {
      const alertEl = document.getElementById('feedback-alert');
      alertEl.textContent = 'Please select a star rating.';
      alertEl.style.display = 'block';
      return;
    }
    const message = document.getElementById('feedback-message').value;
    const successEl = document.getElementById('feedback-success');
    const alertEl = document.getElementById('feedback-alert');
    
    alertEl.style.display = 'none';
    submitFeedbackBtn.disabled = true;
    submitFeedbackBtn.textContent = 'Submitting...';
    
    try {
      const url = `${API_BASE_URL}/api/v1/stats/feedback?rating=${selectedRating}&message=${encodeURIComponent(message)}&page=dashboard`;
      const res = await fetchWithAuth(url, { method: 'POST' });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to submit feedback.');
      }
      successEl.textContent = 'Thank you for your feedback!';
      successEl.style.display = 'block';
      setTimeout(() => {
        feedbackModal.style.display = 'none';
      }, 1500);
    } catch (err) {
      alertEl.textContent = err.message;
      alertEl.style.display = 'block';
    } finally {
      submitFeedbackBtn.disabled = false;
      submitFeedbackBtn.textContent = 'Submit Feedback';
    }
  });
}

// Cold Start Health Check
async function checkServerHealth() {
  const bannerId = 'cold-start-banner';
  
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);
  
  let showBanner = false;
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/health`, {
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    if (!response.ok) {
      showBanner = true;
    }
  } catch (err) {
    showBanner = true;
  }
  
  if (showBanner) {
    if (!document.getElementById(bannerId)) {
      const banner = document.createElement('div');
      banner.id = bannerId;
      banner.className = 'cold-start-warning';
      banner.style.cssText = `
        background-color: #fef3c7;
        color: #92400e;
        padding: 0.75rem 1.5rem;
        text-align: center;
        font-size: 0.9rem;
        font-weight: 500;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
        position: relative;
        border-bottom: 1px solid #fde68a;
        z-index: 1000;
      `;
      banner.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0;"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>
        <span>Server is waking up. First request may take 30-60 seconds...</span>
        <button id="close-cold-banner" style="background: none; border: none; font-size: 1.25rem; color: #92400e; cursor: pointer; position: absolute; right: 1rem; top: 50%; transform: translateY(-50%); display: flex; align-items: center; justify-content: center; padding: 4px;">&times;</button>
      `;
      document.body.insertBefore(banner, document.body.firstChild);
      
      document.getElementById('close-cold-banner').addEventListener('click', () => {
        banner.remove();
      });
      
      const pollInterval = setInterval(async () => {
        try {
          const pollResp = await fetch(`${API_BASE_URL}/api/v1/health`);
          if (pollResp.ok) {
            clearInterval(pollInterval);
            const activeBanner = document.getElementById(bannerId);
            if (activeBanner) activeBanner.remove();
          }
        } catch (e) {
          // Keep polling
        }
      }, 3000);
    }
  }
}

// Logout event
const logoutBtn = document.getElementById('logout-btn');
if (logoutBtn) {
  logoutBtn.addEventListener('click', () => {
    logout();
  });
}

function logout() {
  localStorage.removeItem('meetmind_token');
  localStorage.removeItem('meetmind_user');
  localStorage.removeItem('meetmind_is_pro');
  // Clear mock token too
  localStorage.removeItem('mock_token');
  // Trigger cookies clear in backend
  fetch(`${API_BASE_URL}/api/v1/auth/logout`, { method: 'POST', credentials: 'include' })
    .finally(() => {
      window.location.href = 'login.html';
    });
}

// Initial load
document.addEventListener('DOMContentLoaded', () => {
  checkServerHealth();
  fetchUserProfile();
  fetchMeetings();
});
