// Meeting Details Screen Logic

let meetingId = null;
let pollInterval = null;
let pollStartTime = Date.now();
let currentMeeting = null;

// Get meeting ID from URL
function getMeetingIdFromURL() {
  const params = new URLSearchParams(window.location.search);
  return params.get('id');
}

// Toast Helper
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

// Format date
function formatMeetingDate(isoString) {
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  } catch (e) {
    return isoString;
  }
}

// Tab Switching
function switchTab(tabName) {
  document.querySelectorAll('.tab-trigger').forEach(btn => {
    btn.classList.remove('active');
    if (btn.getAttribute('onclick').includes(tabName)) {
      btn.classList.add('active');
    }
  });

  document.querySelectorAll('.tab-content-panel').forEach(panel => {
    panel.classList.remove('active');
  });
  document.getElementById(`tab-${tabName}`).classList.add('active');
}

// Fetch details
async function fetchMeetingDetails() {
  if (!meetingId) {
    showError('Invalid meeting ID.');
    return;
  }

  // Prevent infinite polling (10 min timeout)
  const elapsed = Math.floor((Date.now() - pollStartTime) / 1000);
  if (elapsed > 600) {
    stopPolling();
    showError('Processing timed out. Server took too long.');
    return;
  }

  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/meetings/${meetingId}`);
    if (!response.ok) {
      if (response.status === 404) throw new Error('Meeting not found.');
      if (response.status === 403) throw new Error('Access denied.');
      throw new Error('Failed to retrieve meeting details.');
    }

    const meeting = await response.json();
    currentMeeting = meeting;

    if (meeting.status === 'failed') {
      stopPolling();
      throw new Error('Analysis failed. Please upload a clear audio recording.');
    }

    displayMeeting(meeting);
    updateProgressUI(meeting.status);

    if (meeting.status === 'processing') {
      if (!pollInterval) {
        pollInterval = setInterval(fetchMeetingDetails, 3000);
      }
    } else {
      stopPolling();
      // Load interactive action items once done
      fetchInteractiveActionItems();
    }
  } catch (err) {
    showError(err.message);
    stopPolling();
  }
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
  const stepsPanel = document.getElementById('processing-steps-panel');
  if (stepsPanel) stepsPanel.style.display = 'none';
}

function showError(msg) {
  const errEl = document.getElementById('detail-error');
  errEl.textContent = msg;
  errEl.style.display = 'block';
  document.getElementById('meeting-content-pane').style.display = 'none';
  document.getElementById('meeting-title').textContent = 'Error';
  document.getElementById('meeting-status-badge').style.display = 'none';
}

// Update polling steps UI
function updateProgressUI(status) {
  const panel = document.getElementById('processing-steps-panel');
  if (!panel) return;

  if (status === 'processing') {
    panel.style.display = 'block';
    const elapsed = Math.floor((Date.now() - pollStartTime) / 1000);
    
    const step2Icon = document.getElementById('step-2-icon');
    const step2Text = document.getElementById('step-2-text');
    const step3Icon = document.getElementById('step-3-icon');
    const step3Text = document.getElementById('step-3-text');

    if (elapsed < 12) {
      step2Icon.style.background = 'var(--accent)';
      step2Icon.style.boxShadow = 'var(--accent-glow)';
      step2Text.style.opacity = '1';
    } else {
      step2Icon.style.background = '#10B981';
      step2Icon.style.boxShadow = 'none';
      step2Icon.textContent = '✓';
      step2Text.style.opacity = '1';

      step3Icon.style.background = 'var(--accent)';
      step3Icon.style.boxShadow = 'var(--accent-glow)';
      step3Text.style.opacity = '1';
    }
  } else if (status === 'done') {
    const step2Icon = document.getElementById('step-2-icon');
    const step3Icon = document.getElementById('step-3-icon');
    if (step2Icon) {
      step2Icon.style.background = '#10B981';
      step2Icon.textContent = '✓';
    }
    if (step3Icon) {
      step3Icon.style.background = '#10B981';
      step3Icon.textContent = '✓';
    }
    setTimeout(() => {
      panel.style.display = 'none';
    }, 1500);
  } else {
    panel.style.display = 'none';
  }
}

// Render meeting fields
function displayMeeting(meeting) {
  document.getElementById('meeting-content-pane').style.display = 'block';
  document.getElementById('meeting-title').textContent = meeting.title;
  document.getElementById('meeting-title-input').value = meeting.title;
  document.getElementById('meeting-date').textContent = formatMeetingDate(meeting.created_at);

  const badge = document.getElementById('meeting-status-badge');
  badge.className = 'badge';
  badge.style.display = 'inline-block';

  if (meeting.status === 'done') {
    badge.classList.add('badge-done');
    badge.textContent = 'Done';
  } else if (meeting.status === 'processing') {
    badge.classList.add('badge-processing');
    badge.textContent = 'Processing...';
  } else {
    badge.classList.add('badge-failed');
    badge.textContent = 'Failed';
  }

  // Render Executive Summary Cards
  const summaryList = document.getElementById('summary-points-list');
  summaryList.innerHTML = '';

  if (meeting.summary) {
    const bullets = meeting.summary.split('\n').filter(line => line.trim().length > 0);
    bullets.forEach((bullet, index) => {
      const cleanBullet = bullet.replace(/^-\s*/, '').replace(/^\*\s*/, '').trim();
      const card = document.createElement('div');
      card.className = 'summary-point-card';
      
      card.innerHTML = `
        <div class="summary-point-icon">📌</div>
        <div style="font-family: var(--font-secondary); font-size: 0.95rem; line-height: 1.5; color: var(--text-primary);">${cleanBullet}</div>
      `;
      summaryList.appendChild(card);
    });
  } else if (meeting.status === 'processing') {
    summaryList.innerHTML = `<p style="color: var(--text-secondary); font-style: italic; text-align: center;">Transcribing audio & analyzing. MOM details will render shortly...</p>`;
  } else {
    summaryList.innerHTML = `<p style="color: var(--text-secondary); font-style: italic;">No summary generated.</p>`;
  }

  // Render static MOM values first
  if (meeting.mom) {
    // Attendees
    const attList = document.getElementById('mom-attendees-list');
    attList.innerHTML = '';
    if (meeting.mom.attendees && meeting.mom.attendees.length > 0) {
      meeting.mom.attendees.forEach(att => {
        const pill = document.createElement('span');
        pill.className = 'mom-pill';
        pill.textContent = att;
        attList.appendChild(pill);
      });
    } else {
      attList.innerHTML = '<span style="color: var(--text-secondary); font-style: italic;">None specified</span>';
    }

    // Agenda
    const agendaList = document.getElementById('mom-agenda-list');
    agendaList.innerHTML = '';
    if (meeting.mom.agenda && meeting.mom.agenda.length > 0) {
      meeting.mom.agenda.forEach(item => {
        const li = document.createElement('li');
        li.textContent = item;
        agendaList.appendChild(li);
      });
    } else {
      agendaList.innerHTML = '<li style="color: var(--text-secondary); font-style: italic; list-style: none;">None specified</li>';
    }

    // Decisions
    const decList = document.getElementById('mom-decisions-list');
    decList.innerHTML = '';
    if (meeting.mom.decisions && meeting.mom.decisions.length > 0) {
      meeting.mom.decisions.forEach(item => {
        const li = document.createElement('li');
        li.textContent = item;
        decList.appendChild(li);
      });
    } else {
      decList.innerHTML = '<li style="color: var(--text-secondary); font-style: italic; list-style: none;">No decisions recorded</li>';
    }

    // Prepopulate static action items fallback
    renderStaticActionItemsTable(meeting.mom.action_items);
  }
}

// Pre-render static table fallback
function renderStaticActionItemsTable(items) {
  const tbody = document.getElementById('mom-actions-table-body');
  tbody.innerHTML = '';
  if (items && items.length > 0) {
    items.forEach(item => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><input type="checkbox" disabled style="width: 18px; height: 18px;"></td>
        <td><strong>${item.task}</strong></td>
        <td><span class="mom-pill">${item.owner || 'Unassigned'}</span></td>
        <td style="color: var(--text-secondary);">${item.deadline || 'N/A'}</td>
      `;
      tbody.appendChild(tr);
    });
  } else {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-secondary); font-style: italic;">No action items found</td></tr>`;
  }
}

// Fetch interactive action items with DB status & database ids
async function fetchInteractiveActionItems() {
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/action-items?meeting_id=${meetingId}`);
    if (res.ok) {
      const items = await res.json();
      if (items.length > 0) {
        renderInteractiveActionItemsTable(items);
      }
    }
  } catch (err) {
    console.error("Failed to load interactive action items:", err);
  }
}

// Render action items list with live toggles
function renderInteractiveActionItemsTable(items) {
  const tbody = document.getElementById('mom-actions-table-body');
  tbody.innerHTML = '';

  items.forEach(item => {
    const tr = document.createElement('tr');
    const isChecked = item.status === 'done';
    
    tr.innerHTML = `
      <td><input type="checkbox" class="task-toggle" data-id="${item.id}" ${isChecked ? 'checked' : ''} style="width: 18px; height: 18px; cursor: pointer;"></td>
      <td class="task-text" style="${isChecked ? 'text-decoration: line-through; opacity: 0.6;' : ''}"><strong>${item.task}</strong></td>
      <td><span class="mom-pill">${item.owner || 'Unassigned'}</span></td>
      <td style="color: var(--text-secondary);">${item.deadline || 'N/A'}</td>
    `;

    const checkbox = tr.querySelector('.task-toggle');
    const textCell = tr.querySelector('.task-text');

    checkbox.addEventListener('change', async () => {
      const newStatus = checkbox.checked ? 'done' : 'pending';
      textCell.style.textDecoration = checkbox.checked ? 'line-through' : 'none';
      textCell.style.opacity = checkbox.checked ? '0.6' : '1';

      try {
        const patchRes = await fetchWithAuth(`${API_BASE_URL}/api/v1/action-items/${item.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: newStatus })
        });
        if (patchRes.ok) {
          showToast(newStatus === 'done' ? "Task marked done!" : "Task marked pending.");
        } else {
          throw new Error();
        }
      } catch (err) {
        showToast("Error updating task status.");
        checkbox.checked = !checkbox.checked;
        textCell.style.textDecoration = checkbox.checked ? 'line-through' : 'none';
        textCell.style.opacity = checkbox.checked ? '0.6' : '1';
      }
    });

    tbody.appendChild(tr);
  });
}

// Rename Meeting Title
function toggleEditTitle(show) {
  document.getElementById('title-display-container').style.display = show ? 'none' : 'flex';
  document.getElementById('title-edit-container').style.display = show ? 'flex' : 'none';
}

async function saveMeetingTitle() {
  const newTitle = document.getElementById('meeting-title-input').value.trim();
  if (!newTitle) {
    showToast("Title cannot be empty.");
    return;
  }

  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/meetings/${meetingId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newTitle })
    });
    if (res.ok) {
      document.getElementById('meeting-title').textContent = newTitle;
      currentMeeting.title = newTitle;
      toggleEditTitle(false);
      showToast("Meeting renamed successfully.");
    } else {
      throw new Error();
    }
  } catch (err) {
    showToast("Failed to rename meeting.");
  }
}

// Share Modal Operations
function openShareModal() {
  if (!currentMeeting) return;
  
  const modal = document.getElementById('share-modal');
  const toggle = document.getElementById('public-toggle');
  
  toggle.checked = currentMeeting.is_public || false;
  updateShareUI();
  modal.style.display = 'flex';
}

function closeShareModal() {
  document.getElementById('share-modal').style.display = 'none';
}

function updateShareUI() {
  const toggle = document.getElementById('public-toggle');
  const container = document.getElementById('public-link-container');
  
  if (toggle.checked) {
    container.style.display = 'block';
    
    // Generate public URL
    const slug = currentMeeting.public_slug || '';
    const shareUrl = `${window.location.origin}/share.html?slug=${slug}`;
    document.getElementById('share-url-input').value = shareUrl;
    
    // WhatsApp social configuration
    const waBtn = document.getElementById('share-whatsapp-btn');
    const waText = encodeURIComponent(`Here are the AI minutes & action items for "${currentMeeting.title}": ${shareUrl}`);
    waBtn.onclick = () => window.open(`https://api.whatsapp.com/send?text=${waText}`, '_blank');
    
    // Email configuration
    const mailBtn = document.getElementById('share-email-btn');
    const mailSubject = encodeURIComponent(`Meeting MOM: ${currentMeeting.title}`);
    const mailBody = encodeURIComponent(`Hi team,\n\nI have generated the Minutes of Meeting (MOM) and action items using MeetMind AI. You can access the complete breakdown here:\n${shareUrl}`);
    mailBtn.onclick = () => window.location.href = `mailto:?subject=${mailSubject}&body=${mailBody}`;
    
  } else {
    container.style.display = 'none';
  }
}

// Toggle public share state
document.getElementById('public-toggle').addEventListener('change', async () => {
  const toggle = document.getElementById('public-toggle');
  const isPublic = toggle.checked;
  
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/meetings/${meetingId}/public`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_public: isPublic })
    });
    
    if (res.ok) {
      const data = await res.json();
      currentMeeting.is_public = data.is_public;
      currentMeeting.public_slug = data.public_slug;
      updateShareUI();
      showToast(isPublic ? "Meeting summary is now public!" : "Meeting summary is now private.");
    } else {
      throw new Error();
    }
  } catch (err) {
    showToast("Error updating public accessibility.");
    toggle.checked = !isPublic;
  }
});

// Copy link click handler
document.getElementById('copy-share-url-btn').addEventListener('click', () => {
  const urlInput = document.getElementById('share-url-input');
  navigator.clipboard.writeText(urlInput.value).then(() => {
    const btn = document.getElementById('copy-share-url-btn');
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy Link', 2000);
  });
});

// Chat submission
document.getElementById('chat-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = document.getElementById('chat-input');
  const query = input.value.trim();
  if (!query) return;

  appendChatBubble(query, 'user');
  input.value = '';

  const sendBtn = document.getElementById('chat-send-btn');
  input.disabled = true;
  sendBtn.disabled = true;

  const thinking = appendChatBubble('Thinking...', 'assistant');

  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/qa/${meetingId}?q=${encodeURIComponent(query)}`);
    const data = await response.json();
    if (response.ok) {
      thinking.textContent = data.answer;
    } else {
      throw new Error(data.detail || "Request failed.");
    }
  } catch (err) {
    thinking.textContent = `Error getting answer: ${err.message}`;
    thinking.style.color = 'var(--error)';
  } finally {
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
  }
});

function appendChatBubble(text, sender) {
  const container = document.getElementById('chat-messages');
  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${sender}`;
  bubble.textContent = text;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
  return bubble;
}

// Export functions
async function exportReport(type) {
  const btn = document.getElementById(`export-${type}-btn`);
  btn.disabled = true;
  btn.textContent = 'Exporting...';
  
  try {
    const res = await fetchWithAuth(`${API_BASE_URL}/api/v1/meetings/${meetingId}/export/${type}`);
    if (!res.ok) throw new Error();
    
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentMeeting.title.replace(/\s+/g, '_')}_MOM.${type}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    showToast(`${type.toUpperCase()} file downloaded successfully.`);
  } catch (err) {
    showToast(`Failed to export ${type.toUpperCase()}.`);
  } finally {
    btn.disabled = false;
    btn.textContent = `Export ${type.toUpperCase()}`;
  }
}

document.getElementById('export-pdf-btn').addEventListener('click', () => exportReport('pdf'));
document.getElementById('export-docx-btn').addEventListener('click', () => exportReport('docx'));

// Check user profile
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
  } catch (e) {}
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
  meetingId = getMeetingIdFromURL();
  fetchUserProfile();
  fetchMeetingDetails();
});
