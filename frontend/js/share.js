// Public Share Screen Logic

function getSlugFromURL() {
  const params = new URLSearchParams(window.location.search);
  return params.get('slug');
}

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

// Fetch public share details
async function fetchPublicMeeting() {
  const slug = getSlugFromURL();
  const errorEl = document.getElementById('share-error');
  const contentEl = document.getElementById('share-content');
  
  if (!slug) {
    showError("Invalid or missing sharing slug.");
    return;
  }
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/share/${slug}`);
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error("Shared meeting report not found or has been made private.");
      }
      throw new Error("Failed to load shared meeting report.");
    }
    
    const meeting = await response.json();
    displayPublicMeeting(meeting);
    
  } catch (err) {
    showError(err.message);
  }
}

function showError(msg) {
  const errorEl = document.getElementById('share-error');
  errorEl.textContent = msg;
  errorEl.style.display = 'block';
  document.getElementById('share-content').style.display = 'none';
  document.getElementById('meeting-title').textContent = 'Error';
}

function displayPublicMeeting(meeting) {
  document.getElementById('share-content').style.display = 'block';
  document.getElementById('meeting-title').textContent = meeting.title;
  document.getElementById('meeting-date').textContent = formatMeetingDate(meeting.created_at);

  // Render Executive Summary Cards
  const summaryList = document.getElementById('summary-points-list');
  summaryList.innerHTML = '';

  if (meeting.summary) {
    const bullets = meeting.summary.split('\n').filter(line => line.trim().length > 0);
    bullets.forEach(bullet => {
      const cleanBullet = bullet.replace(/^-\s*/, '').replace(/^\*\s*/, '').trim();
      const card = document.createElement('div');
      card.className = 'summary-point-card';
      card.innerHTML = `
        <div class="summary-point-icon">📌</div>
        <div style="font-family: var(--font-secondary); font-size: 0.95rem; line-height: 1.5; color: var(--text-primary);">${cleanBullet}</div>
      `;
      summaryList.appendChild(card);
    });
  } else {
    summaryList.innerHTML = `<p style="color: var(--text-secondary); font-style: italic;">No summary generated.</p>`;
  }

  // Render MOM Details
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

    // Read-only Action items
    const tbody = document.getElementById('mom-actions-table-body');
    tbody.innerHTML = '';
    
    if (meeting.mom.action_items && meeting.mom.action_items.length > 0) {
      meeting.mom.action_items.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${item.task}</strong></td>
          <td><span class="mom-pill">${item.owner || 'Unassigned'}</span></td>
          <td style="color: var(--text-secondary);">${item.deadline || 'N/A'}</td>
        `;
        tbody.appendChild(tr);
      });
    } else {
      tbody.innerHTML = `
        <tr>
          <td colspan="3" style="text-align: center; color: var(--text-secondary); font-style: italic;">No action items recorded</td>
        </tr>
      `;
    }
  }
}

// Initial load
document.addEventListener('DOMContentLoaded', () => {
  fetchPublicMeeting();
});
