// DOM Elements
const meetingTitle = document.getElementById('meeting-title');
const meetingDate = document.getElementById('meeting-date');
const meetingStatusBadge = document.getElementById('meeting-status-badge');
const detailError = document.getElementById('detail-error');
const contentPane = document.getElementById('meeting-content-pane');

const summaryPointsList = document.getElementById('summary-points-list');
const momAttendeesList = document.getElementById('mom-attendees-list');
const momAgendaList = document.getElementById('mom-agenda-list');
const momDecisionsList = document.getElementById('mom-decisions-list');
const momActionsTableBody = document.getElementById('mom-actions-table-body');

const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');

const exportPdfBtn = document.getElementById('export-pdf-btn');
const exportDocxBtn = document.getElementById('export-docx-btn');
const exportUpgradeModal = document.getElementById('export-upgrade-modal');
const exportUpgradeBtn = document.getElementById('export-upgrade-btn');
const exportModalCloseBtn = document.getElementById('export-modal-close-btn');

let meetingId = null;
let pollInterval = null;

// Get meeting ID from Query Params
function getMeetingIdFromURL() {
  const params = new URLSearchParams(window.location.search);
  return params.get('id');
}

// Format Date
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

let pollStartTime = Date.now();

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
    const step4Icon = document.getElementById('step-4-icon');
    const step4Text = document.getElementById('step-4-text');
    
    if (elapsed < 12) {
      if (step2Icon) {
        step2Icon.style.background = 'var(--accent-primary)';
        step2Icon.style.animation = 'pulse 1.5s infinite';
        step2Icon.textContent = '2';
      }
      if (step2Text) step2Text.style.opacity = '1';
      
      if (step3Icon) {
        step3Icon.style.background = 'var(--text-secondary)';
        step3Icon.style.animation = 'none';
        step3Icon.textContent = '3';
      }
      if (step3Text) step3Text.style.opacity = '0.5';
    } else {
      if (step2Icon) {
        step2Icon.style.background = 'var(--accent-success)';
        step2Icon.style.animation = 'none';
        step2Icon.textContent = '✓';
      }
      if (step2Text) step2Text.style.opacity = '1';
      
      if (step3Icon) {
        step3Icon.style.background = 'var(--accent-primary)';
        step3Icon.style.animation = 'pulse 1.5s infinite';
        step3Icon.textContent = '3';
      }
      if (step3Text) step3Text.style.opacity = '1';
    }
    
    if (step4Icon) {
      step4Icon.style.background = 'var(--text-secondary)';
      step4Icon.style.animation = 'none';
      step4Icon.textContent = '4';
    }
    if (step4Text) step4Text.style.opacity = '0.5';
    
  } else if (status === 'done') {
    const step2Icon = document.getElementById('step-2-icon');
    const step2Text = document.getElementById('step-2-text');
    const step3Icon = document.getElementById('step-3-icon');
    const step3Text = document.getElementById('step-3-text');
    const step4Icon = document.getElementById('step-4-icon');
    const step4Text = document.getElementById('step-4-text');
    
    if (step2Icon) {
      step2Icon.style.background = 'var(--accent-success)';
      step2Icon.style.animation = 'none';
      step2Icon.textContent = '✓';
    }
    if (step2Text) step2Text.style.opacity = '1';
    
    if (step3Icon) {
      step3Icon.style.background = 'var(--accent-success)';
      step3Icon.style.animation = 'none';
      step3Icon.textContent = '✓';
    }
    if (step3Text) step3Text.style.opacity = '1';
    
    if (step4Icon) {
      step4Icon.style.background = 'var(--accent-success)';
      step4Icon.style.animation = 'none';
      step4Icon.textContent = '✓';
    }
    if (step4Text) step4Text.style.opacity = '1';
    
    setTimeout(() => {
      panel.style.display = 'none';
    }, 1500);
  } else {
    panel.style.display = 'none';
  }
}

// Fetch Meeting details
async function fetchMeetingDetails() {
  if (!meetingId) {
    showError('Invalid meeting ID.');
    return;
  }

  const elapsed = Math.floor((Date.now() - pollStartTime) / 1000);
  if (elapsed > 600) {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    const panel = document.getElementById('processing-steps-panel');
    if (panel) panel.style.display = 'none';
    showError('Processing timed out. The server took too long to respond. Please try uploading again.');
    return;
  }

  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/meetings/${meetingId}`);

    hideMessage();

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Meeting not found.');
      } else if (response.status === 403) {
        throw new Error('You do not have access to view this meeting.');
      } else {
        throw new Error('Failed to retrieve meeting details.');
      }
    }

    const meeting = await response.json();

    if (meeting.status === 'failed') {
      const panel = document.getElementById('processing-steps-panel');
      if (panel) panel.style.display = 'none';
      throw new Error('Processing failed. Please try again with a valid audio file.');
    }

    displayMeeting(meeting);
    updateProgressUI(meeting.status);
    
    // Auto polling check
    if (meeting.status === 'processing') {
      if (!pollInterval) {
        pollStartTime = Date.now(); // reset timer on fresh start of page
        pollInterval = setInterval(fetchMeetingDetails, 3000); // Poll every 3s
      }
    } else {
      if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
    }

  } catch (err) {
    hideMessage();
    showError(err.message);
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }
}

function showError(msg) {
  detailError.textContent = msg;
  detailError.style.display = 'block';
  contentPane.style.display = 'none';
  meetingTitle.textContent = 'Error';
  meetingStatusBadge.style.display = 'none';
}

// Display meeting details inside tabs
function displayMeeting(meeting) {
  contentPane.style.display = 'block';
  meetingTitle.textContent = meeting.title;
  meetingDate.textContent = formatMeetingDate(meeting.created_at);

  // Status Badge
  meetingStatusBadge.className = 'badge';
  meetingStatusBadge.style.display = 'inline-block';
  
  if (meeting.status === 'done') {
    meetingStatusBadge.classList.add('badge-done');
    meetingStatusBadge.textContent = 'Done';
  } else if (meeting.status === 'processing') {
    meetingStatusBadge.classList.add('badge-processing');
    meetingStatusBadge.textContent = 'Processing...';
  } else {
    meetingStatusBadge.classList.add('badge-failed');
    meetingStatusBadge.textContent = 'Failed';
  }

  // Populate Executive Summary
  summaryPointsList.innerHTML = '';
  if (meeting.summary) {
    const bullets = meeting.summary.split('\n').filter(line => line.trim().length > 0);
    bullets.forEach(bullet => {
      // Clean leading bullet marks
      const cleanBullet = bullet.replace(/^-\s*/, '').replace(/^\*\s*/, '').trim();
      const li = document.createElement('li');
      li.textContent = cleanBullet;
      summaryPointsList.appendChild(li);
    });
  } else if (meeting.status === 'processing') {
    summaryPointsList.innerHTML = `<p style="color: var(--text-secondary); font-style: italic;">Transcribing and analyzing recording. Please wait...</p>`;
  } else {
    summaryPointsList.innerHTML = `<p style="color: var(--text-secondary); font-style: italic;">No summary generated.</p>`;
  }

  // Populate MOM Details
  if (meeting.mom) {
    // Attendees
    momAttendeesList.innerHTML = '';
    if (meeting.mom.attendees && meeting.mom.attendees.length > 0) {
      meeting.mom.attendees.forEach(attendee => {
        const pill = document.createElement('span');
        pill.className = 'mom-pill';
        pill.textContent = attendee;
        momAttendeesList.appendChild(pill);
      });
    } else {
      momAttendeesList.innerHTML = '<span style="color: var(--text-muted); font-size: 0.9rem; font-style: italic;">None specified</span>';
    }

    // Agenda
    momAgendaList.innerHTML = '';
    if (meeting.mom.agenda && meeting.mom.agenda.length > 0) {
      meeting.mom.agenda.forEach(agendaItem => {
        const li = document.createElement('li');
        li.textContent = agendaItem;
        momAgendaList.appendChild(li);
      });
    } else {
      momAgendaList.innerHTML = '<li style="color: var(--text-muted); font-size: 0.9rem; font-style: italic; list-style: none; padding-left: 0;">None specified</li>';
    }

    // Decisions
    momDecisionsList.innerHTML = '';
    if (meeting.mom.decisions && meeting.mom.decisions.length > 0) {
      meeting.mom.decisions.forEach(decision => {
        const li = document.createElement('li');
        li.textContent = decision;
        momDecisionsList.appendChild(li);
      });
    } else {
      momDecisionsList.innerHTML = '<li style="color: var(--text-muted); font-size: 0.9rem; font-style: italic; list-style: none; padding-left: 0;">No decisions recorded</li>';
    }

    // Action items (build securely with DOM methods to prevent XSS)
    momActionsTableBody.innerHTML = '';
    if (meeting.mom.action_items && meeting.mom.action_items.length > 0) {
      meeting.mom.action_items.forEach(item => {
        const tr = document.createElement('tr');
        
        const tdTask = document.createElement('td');
        const strongTask = document.createElement('strong');
        strongTask.textContent = item.task;
        tdTask.appendChild(strongTask);
        
        const tdOwner = document.createElement('td');
        const pillOwner = document.createElement('span');
        pillOwner.className = 'mom-pill';
        pillOwner.textContent = item.owner || 'Unassigned';
        tdOwner.appendChild(pillOwner);
        
        const tdDeadline = document.createElement('td');
        tdDeadline.style.color = 'var(--text-secondary)';
        tdDeadline.textContent = item.deadline || 'N/A';
        
        tr.appendChild(tdTask);
        tr.appendChild(tdOwner);
        tr.appendChild(tdDeadline);
        
        momActionsTableBody.appendChild(tr);
      });
    } else {
      momActionsTableBody.innerHTML = `
        <tr>
          <td colspan="3" style="text-align: center; color: var(--text-muted); font-style: italic;">No action items recorded</td>
        </tr>
      `;
    }
  } else {
    // Empty state MOM
    momAttendeesList.innerHTML = '';
    momAgendaList.innerHTML = '';
    momDecisionsList.innerHTML = '';
    momActionsTableBody.innerHTML = `
      <tr>
        <td colspan="3" style="text-align: center; color: var(--text-muted); font-style: italic;">MOM will populate once processing completes</td>
      </tr>
    `;
  }
}

// Tab Switching
function switchTab(tabName) {
  // Toggle Active Button
  const buttons = document.querySelectorAll('.tab-btn');
  buttons.forEach(btn => {
    btn.classList.remove('active');
    if (btn.getAttribute('onclick').includes(tabName)) {
      btn.classList.add('active');
    }
  });

  // Toggle Active Panel
  const panels = document.querySelectorAll('.tab-panel');
  panels.forEach(panel => {
    panel.classList.remove('active');
  });
  document.getElementById(`tab-${tabName}`).classList.add('active');
}

// Chat integration
chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const question = chatInput.value.trim();
  if (!question) return;

  // Append user bubble
  appendChatBubble(question, 'user');
  chatInput.value = '';
  
  // Disable input during loader
  const inputEl = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send-btn');
  inputEl.disabled = true;
  sendBtn.disabled = true;

  // Append loading placeholder bubble
  const loadingBubble = appendChatBubble('Thinking...', 'assistant');

  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/qa/${meetingId}?q=${encodeURIComponent(question)}`);

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'Q&A request failed.');
    }

    loadingBubble.textContent = data.answer;

  } catch (err) {
    loadingBubble.textContent = `Error: ${err.message}`;
    loadingBubble.style.color = 'var(--accent-danger)';
  } finally {
    inputEl.disabled = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }
});

function appendChatBubble(text, sender) {
  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${sender}`;
  bubble.textContent = text;
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight; // Scroll to bottom
  return bubble;
}

// Export and Upgrade Checking
async function checkExportTier(type) {
  const isPro = localStorage.getItem('meetmind_is_pro') === 'true';
  if (!isPro) {
    exportUpgradeModal.style.display = 'flex';
    return;
  }
  
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/meetings/${meetingId}/export/${type}`);
    
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || `Export to ${type.toUpperCase()} failed.`);
    }
    
    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = `meeting_mom_${meetingId}.${type}`;
    document.body.appendChild(a);
    a.click();
    
    document.body.removeChild(a);
    window.URL.revokeObjectURL(blobUrl);
  } catch (err) {
    alert(`Export failed: ${err.message}`);
  }
}

exportPdfBtn.addEventListener('click', () => checkExportTier('pdf'));
exportDocxBtn.addEventListener('click', () => checkExportTier('docx'));

exportModalCloseBtn.addEventListener('click', () => {
  exportUpgradeModal.style.display = 'none';
});

exportUpgradeBtn.addEventListener('click', async () => {
  exportUpgradeModal.style.display = 'none';
  
  try {
    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/payments/mock-upgrade`, {
      method: 'POST'
    });
    
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || 'Upgrade failed');
    }
    
    localStorage.setItem('meetmind_is_pro', 'true');
    alert('Upgraded to Pro! Try exporting again.');
  } catch (err) {
    alert(`Upgrade failed: ${err.message}`);
  }
});

function showMessage(msg) {
  let msgEl = document.getElementById('cold-start-warning');
  if (!msgEl) {
    msgEl = document.createElement('div');
    msgEl.id = 'cold-start-warning';
    msgEl.style.padding = '0.75rem 1rem';
    msgEl.style.borderRadius = 'var(--radius-sm)';
    msgEl.style.fontSize = '0.9rem';
    msgEl.style.marginBottom = '1.25rem';
    msgEl.style.background = 'rgba(59, 130, 246, 0.15)';
    msgEl.style.border = '1px solid rgba(59, 130, 246, 0.25)';
    msgEl.style.color = '#93C5FD';
    
    const wrapper = document.querySelector('.meeting-detail-wrapper');
    const header = document.querySelector('.meeting-header');
    if (wrapper && header) {
      wrapper.insertBefore(msgEl, header);
    }
  }
  msgEl.textContent = msg;
  msgEl.style.display = 'block';
}

function hideMessage() {
  const msgEl = document.getElementById('cold-start-warning');
  if (msgEl) {
    msgEl.style.display = 'none';
  }
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
  meetingId = getMeetingIdFromURL();
  pollStartTime = Date.now();
  showMessage("Processing your meeting... this may take 30-60 seconds on first load");
  fetchMeetingDetails();
});
