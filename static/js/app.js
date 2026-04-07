/* ═══════════════════════════════════════════════════════
   TaskFlow — Main JS
   Handles: modal, task form, notifications, sidebar, toasts
═══════════════════════════════════════════════════════ */
 
// ── Sidebar Toggle (mobile) ──────────────────────────
document.getElementById('menuToggle')?.addEventListener('click', () => {
  document.getElementById('sidebar').classList.toggle('open');
});
document.addEventListener('click', (e) => {
  const sb = document.getElementById('sidebar');
  if (sb.classList.contains('open') && !sb.contains(e.target) && e.target.id !== 'menuToggle') {
    sb.classList.remove('open');
  }
});
 
// ── Notification Bell ────────────────────────────────
document.getElementById('notifBtn')?.addEventListener('click', (e) => {
  e.stopPropagation();
  document.getElementById('notifDropdown')?.classList.toggle('open');
});
document.addEventListener('click', (e) => {
  const dd = document.getElementById('notifDropdown');
  if (dd && !dd.contains(e.target) && e.target.id !== 'notifBtn') {
    dd.classList.remove('open');
  }
});

// ── Theme Toggle (Dark Mode) ────────────────────────
function initTheme() {
  const savedTheme = localStorage.getItem('taskflow-theme') || 'light';
  applyTheme(savedTheme);
}

function applyTheme(theme) {
  const isDark = theme === 'dark' || 
                (theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  
  if (isDark) {
    document.body.classList.add('dark-mode');
  } else {
    document.body.classList.remove('dark-mode');
  }
  
  const themeToggle = document.getElementById('themeToggle');
  if (themeToggle) {
    themeToggle.innerHTML = isDark ? 
      '<i class="fa-solid fa-sun"></i>' : 
      '<i class="fa-solid fa-moon"></i>';
  }
}

document.getElementById('themeToggle')?.addEventListener('click', () => {
  const currentTheme = localStorage.getItem('taskflow-theme') || 'light';
  const newTheme = currentTheme === 'light' ? 'dark' : 'light';
  localStorage.setItem('taskflow-theme', newTheme);
  applyTheme(newTheme);
});

window.applyTheme = applyTheme;
initTheme();

// ── Load Notifications ───────────────────────────────
async function loadNotifications() {
  try {
    const reminders = await fetch('/api/reminders').then(r => r.json());
    const badge = document.getElementById('notifBadge');
    const list = document.getElementById('notifList');
    const stats = await fetch('/api/stats').then(r => r.json());
 
    // sidebar counts
    document.getElementById('sb-pending').textContent = stats.pending;
    document.getElementById('sb-done').textContent = stats.completed;
 
    if (!reminders.length) {
      badge.style.display = 'none';
      list.innerHTML = '<p class="no-notif">No upcoming deadlines 🎉</p>';
      return;
    }
 
    badge.style.display = 'flex';
    badge.textContent = reminders.length;
 
    list.innerHTML = reminders.map(r => {
      const type = r.reminder_type === 0 ? 'today' : r.reminder_type < 0 ? 'overdue' : 'soon';
      const msg = r.reminder_type < 0 ? 'Overdue!' : r.reminder_type === 0 ? 'Due today!' : `Due in ${r.reminder_type} day${r.reminder_type > 1 ? 's' : ''}`;
      return `
      <div class="notif-item ${type}">
        <div class="ni-title">${r.title}</div>
        <div class="ni-meta">${msg} · ${r.category_name || 'General'}</div>
      </div>`;
    }).join('');
 
    // Browser notification (request permission once)
    if (Notification.permission === 'default') Notification.requestPermission();
    if (Notification.permission === 'granted') {
      reminders.forEach(r => {
        if (r.reminder_type <= 1) {
          const msg = r.reminder_type === 0 ? 'due TODAY' : r.reminder_type < 0 ? 'OVERDUE' : 'due tomorrow';
          new Notification(`TaskFlow: "${r.title}" is ${msg}`, { icon: '/static/favicon.ico' });
        }
      });
    }
  } catch (err) {
    console.warn('Notification load failed:', err);
  }
}
 
window.loadNotifications = loadNotifications;
loadNotifications();
setInterval(loadNotifications, 5 * 60 * 1000); // refresh every 5 min
 
// ── Toast System ─────────────────────────────────────
function showToast(message, type = 'success') {
  const container = document.getElementById('toastContainer');
  const icons = { success: 'circle-check', error: 'circle-xmark', info: 'circle-info' };
  const div = document.createElement('div');
  div.className = `toast ${type}`;
  div.innerHTML = `<i class="fa-solid fa-${icons[type]}"></i> ${message}`;
  container.appendChild(div);
  setTimeout(() => div.remove(), 3200);
}
window.showToast = showToast;
 
// ── Modal ─────────────────────────────────────────────
const modalOverlay = document.getElementById('modalOverlay');
const modal = document.getElementById('modal');
const modalTitle = document.getElementById('modalTitle');
const modalBody = document.getElementById('modalBody');
const modalClose = document.getElementById('modalClose');
 
function closeModal() {
  modalOverlay.classList.remove('open');
}
modalClose?.addEventListener('click', closeModal);
modalOverlay?.addEventListener('click', (e) => { if (e.target === modalOverlay) closeModal(); });
window.closeModal = closeModal;
 
// ── Task Form ─────────────────────────────────────────
async function openTaskModal(task = null) {
  const cats = await fetch('/api/categories').then(r => r.json());
  modalTitle.textContent = task ? 'Edit Task' : 'New Task';
 
  const priorityVal = task?.priority || 'medium';
  const fileInfo = task?.file_name
    ? `<div class="file-preview"><i class="fa-solid fa-paperclip"></i> ${task.file_name}</div>` : '';
 
  modalBody.innerHTML = `
    <form id="taskForm" enctype="multipart/form-data">
      <input type="hidden" id="tf-id" value="${task?.id || ''}"/>
 
      <div class="form-group">
        <label>Task Title *</label>
        <input type="text" class="form-input" id="tf-title" placeholder="What needs to be done?" value="${task?.title || ''}" required/>
      </div>
 
      <div class="form-row">
        <div class="form-group">
          <label>Category</label>
          <select class="form-input" id="tf-cat">
            <option value="">— General (no category) —</option>
            ${cats.map(c => `<option value="${c.id}" ${task?.category_id == c.id ? 'selected' : ''}>${c.name}</option>`).join('')}
          </select>
        </div>
        <div class="form-group">
          <label>Deadline</label>
          <input type="date" class="form-input" id="tf-deadline" value="${task?.deadline || ''}"/>
        </div>
      </div>
 
      <div class="form-group">
        <label>Priority</label>
        <div class="priority-select">
          ${['high','medium','low'].map(p => `
          <div class="priority-opt ${p}">
            <input type="radio" name="priority" id="pr-${p}" value="${p}" ${priorityVal===p?'checked':''}/>
            <label for="pr-${p}"><span class="priority-dot ${p}"></span>${p.charAt(0).toUpperCase()+p.slice(1)}</label>
          </div>`).join('')}
        </div>
      </div>
 
      <div class="form-group">
        <label>Description</label>
        <textarea class="form-input" id="tf-desc" placeholder="Add notes or details…">${task?.description || ''}</textarea>
      </div>
 
      <div class="form-group">
        <label>Attachment</label>
        ${fileInfo}
        <div class="file-upload" onclick="document.getElementById('tf-file').click()">
          <input type="file" id="tf-file" accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.xlsx,.pptx,.zip"/>
          <i class="fa-solid fa-cloud-arrow-up" style="font-size:22px;margin-bottom:6px"></i>
          <div>Click to upload a file</div>
          <div style="font-size:12px;opacity:.6">PDF, DOC, images, ZIP (max 16MB)</div>
        </div>
        <div id="tf-file-preview"></div>
      </div>
 
      <button type="button" class="btn-primary full" onclick="submitTask()">
        <i class="fa-solid fa-${task ? 'floppy-disk' : 'plus'}"></i>
        ${task ? 'Save Changes' : 'Create Task'}
      </button>
    </form>`;
 
  // Live file name preview
  document.getElementById('tf-file').addEventListener('change', (e) => {
    const f = e.target.files[0];
    if (f) document.getElementById('tf-file-preview').innerHTML =
      `<div class="file-preview"><i class="fa-solid fa-paperclip"></i> ${f.name}</div>`;
  });
 
  modalOverlay.classList.add('open');
}
window.openTaskModal = openTaskModal;
 
async function submitTask() {
  const id = document.getElementById('tf-id').value;
  const title = document.getElementById('tf-title').value.trim();
  if (!title) { showToast('Task title is required', 'error'); return; }
 
  const formData = new FormData();
  formData.append('title', title);
  formData.append('description', document.getElementById('tf-desc').value);
  formData.append('priority', document.querySelector('input[name="priority"]:checked').value);
  formData.append('deadline', document.getElementById('tf-deadline').value);
  formData.append('category_id', document.getElementById('tf-cat').value || 'null');
  const fileInput = document.getElementById('tf-file');
  if (fileInput.files[0]) formData.append('file', fileInput.files[0]);
 
  const url = id ? `/api/tasks/${id}` : '/api/tasks';
  const method = id ? 'PUT' : 'POST';
 
  const res = await fetch(url, { method, body: formData });
  if (!res.ok) { showToast('Something went wrong', 'error'); return; }
 
  closeModal();
  showToast(id ? 'Task updated!' : 'Task created!', 'success');
 
  // Refresh whichever function is on the current page
  if (typeof loadDashboard === 'function') loadDashboard();
  if (typeof loadTasks === 'function') loadTasks();
  loadNotifications();
}
window.submitTask = submitTask;
 