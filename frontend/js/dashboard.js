// Workspace Dashboard Logic

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

// Toast System Helper
function showToast(message) {
  const toast = document.getElementById('toast');
  if (toast) {
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 4000);
  }
}

// Fetch Profile
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

// Fetch and calculate all dashboard data
async function loadDashboardData() {
  try {
    // 1. Fetch meetings
    const meetingsRes = await fetchWithAuth(`${API_BASE_URL}/api/v1/meetings`);
    let meetings = [];
    if (meetingsRes.ok) {
      meetings = await meetingsRes.json();
    }
    
    // 2. Fetch action items
    const actionItemsRes = await fetchWithAuth(`${API_BASE_URL}/api/v1/action-items`);
    let actionItems = [];
    if (actionItemsRes.ok) {
      actionItems = await actionItemsRes.json();
    }
    
    // Render Stats
    renderStats(meetings, actionItems);
    
    // Render Action Items list
    renderActionItems(actionItems);
    
    // Render Meetings grid
    renderMeetings(meetings);
    
  } catch (err) {
    console.error("Error loading dashboard data:", err);
    showToast("Failed to load workspace data.");
  }
}

// Calculate and render stats
function renderStats(meetings, actionItems) {
  // Total processed
  document.getElementById('stat-total-meetings').textContent = meetings.length;
  
  // Pending action items
  const pendingCount = actionItems.filter(item => item.status === 'pending').length;
  document.getElementById('stat-pending-tasks').textContent = pendingCount;
  
  // Total duration
  let totalSeconds = 0;
  meetings.forEach(m => {
    if (m.duration) {
      totalSeconds += parseInt(m.duration);
    } else {
      // Estimate based on characters if column is null
      const textLen = (m.transcript || '').length;
      totalSeconds += Math.round(textLen / 15); // ~15 chars per second average
    }
  });
  
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.round((totalSeconds % 3600) / 60);
  
  let durationStr = '';
  if (hours > 0) {
    durationStr = `${hours}h ${minutes}m`;
  } else {
    durationStr = `${minutes} mins`;
  }
  document.getElementById('stat-total-duration').textContent = durationStr;
}

// Render Action Items Tracker Panel
function renderActionItems(actionItems) {
  const listEl = document.getElementById('tracker-list');
  const emptyEl = document.getElementById('tracker-empty-state');
  listEl.innerHTML = '';
  
  const pendingItems = actionItems.filter(item => item.status === 'pending');
  
  if (pendingItems.length === 0) {
    emptyEl.style.display = 'block';
    return;
  }
  
  emptyEl.style.display = 'none';
  
  // Sort by deadline
  pendingItems.sort((a, b) => {
    if (!a.deadline) return 1;
    if (!b.deadline) return -1;
    return new Date(a.deadline) - new Date(b.deadline);
  });
  
  pendingItems.forEach(item => {
    const trackerRow = document.createElement('div');
    trackerRow.className = 'tracker-item';
    
    // Check if deadline is overdue
    let deadlineClass = '';
    let deadlineLabel = 'No deadline';
    
    if (item.deadline) {
      const today = new Date();
      today.setHours(0,0,0,0);
      const deadlineDate = new Date(item.deadline);
      
      deadlineLabel = deadlineDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      
      if (deadlineDate < today) {
        deadlineClass = 'deadline-overdue';
        deadlineLabel += ' (Overdue)';
      } else {
        // upcoming in next 3 days
        const diffTime = Math.abs(deadlineDate - today);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        if (diffDays <= 3) {
          deadlineClass = 'deadline-upcoming';
        }
      }
    }
    
    trackerRow.innerHTML = `
      <div class="tracker-left">
        <input type="checkbox" class="tracker-checkbox" data-id="${item.id}">
        <div class="tracker-info">
          <h5>${item.task}</h5>
          <p>Meeting: <a href="meeting.html?id=${item.meeting_id}">${item.meeting_title || 'View Meeting'}</a></p>
        </div>
      </div>
      <div class="tracker-meta">
        <span class="tracker-owner">${item.owner || 'Unassigned'}</span>
        <span class="tracker-deadline ${deadlineClass}">${deadlineLabel}</span>
      </div>
    `;
    
    // Add checkbox event listener
    const checkbox = trackerRow.querySelector('.tracker-checkbox');
    checkbox.addEventListener('change', async () => {
      if (checkbox.checked) {
        trackerRow.style.opacity = '0.5';
        try {
          const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/action-items/${item.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'done' })
          });
          if (res.ok) {
            showToast("Action item marked complete!");
            // Reload dashboard
            loadDashboardData();
          } else {
            throw new Error("Failed to update status");
          }
        } catch (err) {
          showToast("Error updating task.");
          checkbox.checked = false;
          trackerRow.style.opacity = '1';
        }
      }
    });
    
    listEl.appendChild(trackerRow);
  });
}

// Render Meetings Grid
function renderMeetings(meetings) {
  const gridEl = document.getElementById('meetings-grid');
  const emptyEl = document.getElementById('meetings-empty-state');
  gridEl.innerHTML = '';
  
  if (meetings.length === 0) {
    emptyEl.style.display = 'block';
    return;
  }
  
  emptyEl.style.display = 'none';
  
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
    
    // Build badges count from MOM
    let momBadgesHtml = '';
    if (meeting.status === 'done' && meeting.mom) {
      const attCount = (meeting.mom.attendees || []).length;
      const decCount = (meeting.mom.decisions || []).length;
      const actCount = (meeting.mom.action_items || []).length;
      
      momBadgesHtml = `
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 1rem;">
          <span style="font-size: 0.75rem; background: rgba(79, 142, 247, 0.1); border: 1px solid rgba(79, 142, 247, 0.2); padding: 2px 8px; border-radius: 4px;">👥 ${attCount}</span>
          <span style="font-size: 0.75rem; background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.2); padding: 2px 8px; border-radius: 4px;">🎯 ${decCount} Decisions</span>
          <span style="font-size: 0.75rem; background: rgba(52, 211, 153, 0.1); border: 1px solid rgba(52, 211, 153, 0.2); padding: 2px 8px; border-radius: 4px;">✅ ${actCount} Tasks</span>
        </div>
      `;
    }
    
    // Determine length label
    let durationLabel = '';
    if (meeting.duration) {
      const mins = Math.floor(meeting.duration / 60);
      const secs = meeting.duration % 60;
      durationLabel = `${mins}:${secs.toString().padStart(2, '0')}`;
    } else {
      const wordCount = (meeting.transcript || '').split(' ').length;
      const minsEst = Math.max(1, Math.round(wordCount / 150));
      durationLabel = `~${minsEst} min`;
    }

    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; width: 100%;">
        <h4 style="font-size: 1.15rem; font-weight: 700; word-break: break-word;" class="meeting-card-title"></h4>
        <button class="delete-btn" style="background: none; border: none; color: var(--text-secondary); cursor: pointer; padding: 6px; border-radius: 6px; display: flex; align-items: center; justify-content: center; transition: var(--transition);" title="Delete Meeting">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="pointer-events: none;">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      </div>
      ${momBadgesHtml}
      <div class="meeting-meta" style="margin-top: 1.5rem; display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 0.8rem; color: var(--text-secondary);">${formatDate(meeting.created_at)} • ⏱️ ${durationLabel}</span>
        <span class="badge ${badgeClass}">${statusText}</span>
      </div>
    `;
    
    // Set title text safely
    card.querySelector('.meeting-card-title').textContent = meeting.title;
    
    // Delete handler
    card.querySelector('.delete-btn').addEventListener('click', async (e) => {
      e.stopPropagation();
      if (confirm(`Are you sure you want to delete "${meeting.title}"?`)) {
        try {
          const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/meetings/${meeting.id}`, {
            method: 'DELETE'
          });
          if (res.ok) {
            showToast("Meeting deleted successfully.");
            card.remove();
            loadDashboardData();
          } else {
            throw new Error("Failed to delete");
          }
        } catch (err) {
          showToast("Error deleting meeting.");
        }
      }
    });
    
    // Redirect to detail page
    card.addEventListener('click', () => {
      window.location.href = `meeting.html?id=${meeting.id}`;
    });
    
    gridEl.appendChild(card);
  });
}

// Drag & Drop for upload modal
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const uploadTitleInput = document.getElementById('upload-title');
const uploadLanguageSelect = document.getElementById('upload-language');
const processBtn = document.getElementById('process-btn');
const uploadAlert = document.getElementById('upload-alert');

if (dropZone) {
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
}

if (fileInput) {
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      handleFileSelect(fileInput.files[0]);
    }
  });
}

function handleFileSelect(file) {
  selectedFile = file;
  dropZone.querySelector('h4').textContent = file.name;
  dropZone.querySelector('p').textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
  
  // Set default title based on filename
  if (!uploadTitleInput.value.trim()) {
    const baseName = file.name.substring(0, file.name.lastIndexOf('.')) || file.name;
    uploadTitleInput.value = baseName;
  }
  
  processBtn.disabled = false;
}

// Handle Process Upload
if (processBtn) {
  processBtn.addEventListener('click', async () => {
    if (!selectedFile) return;
    
    const title = uploadTitleInput.value.trim() || 'Untitled Meeting';
    const language = uploadLanguageSelect.value;
    
    uploadAlert.style.display = 'none';
    const progressBar = document.getElementById('progress-bar');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    
    progressBar.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.style.display = 'block';
    progressText.textContent = 'Uploading recording file...';
    processBtn.disabled = true;
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('title', title);
    formData.append('language', language);
    
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE_URL}/api/v1/meetings/upload`);
    
    const token = localStorage.getItem('meetmind_token');
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }
    
    const csrfToken = getCookie('csrf_token');
    if (csrfToken) {
      xhr.setRequestHeader('X-CSRF-Token', csrfToken);
    }
    
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const percent = Math.round((event.loaded / event.total) * 100);
        progressFill.style.width = percent + '%';
        progressPercentLabel = percent + '%';
        if (percent >= 100) {
          progressText.textContent = 'AI Summarizing & extracting MOM (takes 1-2 mins)...';
        } else {
          progressText.textContent = `Uploading... ${percent}%`;
        }
      }
    };
    
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        progressFill.style.width = '100%';
        progressText.textContent = 'Processing complete!';
        
        // Trigger browser notification
        if (Notification.permission === "granted") {
          new Notification("Meeting Processed Successfully", {
            body: `MOM summary for "${title}" is ready.`
          });
        }
        
        setTimeout(() => {
          closeModal('upload-modal');
          // Reset UI
          progressBar.style.display = 'none';
          progressText.style.display = 'none';
          uploadTitleInput.value = '';
          selectedFile = null;
          dropZone.querySelector('h4').textContent = 'Drag & drop your file here';
          dropZone.querySelector('p').textContent = 'or click to browse local files';
          
          loadDashboardData();
        }, 1200);
      } else {
        let errMsg = 'Failed to upload recording';
        try {
          const data = JSON.parse(xhr.responseText);
          errMsg = data.detail || errMsg;
        } catch(e) {}
        uploadAlert.textContent = errMsg;
        uploadAlert.style.display = 'block';
        resetUploadUI();
      }
    };
    
    xhr.onerror = () => {
      uploadAlert.textContent = 'Network connection failed during upload.';
      uploadAlert.style.display = 'block';
      resetUploadUI();
    };
    
    xhr.send(formData);
  });
}

function resetUploadUI() {
  processBtn.disabled = false;
  document.getElementById('progress-bar').style.display = 'none';
  document.getElementById('progress-text').style.display = 'none';
}

// Paste Transcript Submit Handlers
const pasteSubmitBtn = document.getElementById('paste-submit-btn');
if (pasteSubmitBtn) {
  pasteSubmitBtn.addEventListener('click', async () => {
    const title = document.getElementById('paste-title').value.trim();
    const transcript = document.getElementById('paste-transcript').value.trim();
    const alertEl = document.getElementById('paste-alert');
    
    if (!title || !transcript) {
      alertEl.textContent = "Please fill in all required fields.";
      alertEl.style.display = 'block';
      return;
    }
    
    alertEl.style.display = 'none';
    pasteSubmitBtn.disabled = true;
    pasteSubmitBtn.textContent = 'Processing...';
    
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/meetings/paste`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, transcript })
      });
      
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to process pasted transcript');
      }
      
      showToast("Transcript processed successfully!");
      closeModal('paste-modal');
      document.getElementById('paste-title').value = '';
      document.getElementById('paste-transcript').value = '';
      
      loadDashboardData();
    } catch (err) {
      alertEl.textContent = err.message;
      alertEl.style.display = 'block';
    } finally {
      pasteSubmitBtn.disabled = false;
      pasteSubmitBtn.textContent = 'Generate MOM';
    }
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

// Start
document.addEventListener('DOMContentLoaded', () => {
  fetchUserProfile();
  loadDashboardData();
  
  // Check if keyboard shortcut requested opening upload modal
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('action') === 'upload') {
    if (typeof triggerUploadModal === 'function') {
      triggerUploadModal();
    }
  }
});
