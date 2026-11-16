/**
 * Copyright (C) 2026 Keshavanarayan and contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

/**
 * LAN File Distributor - Web Manager Script (ES6)
 * Handles client-side API requests, DOM updates, URL auto-parsing, and modal controls.
 */

let appConfig = null;
let pendingUpdates = [];
const selectedItemIds = new Set();

const toastElement = document.getElementById('toast');
const alertBanner = document.getElementById('alertBanner');
const alertUpdateList = document.getElementById('alertUpdateList');
const inputLanFolder = document.getElementById('inputLanFolder');
const repoTableBody = document.getElementById('repoTableBody');
const selectAllCheckbox = document.getElementById('selectAllCheckbox');
const btnPullSelected = document.getElementById('btnPullSelected');
const pullSelectedLabel = document.getElementById('pullSelectedLabel');
const clientsTableBody = document.getElementById('clientsTableBody');
const btnRefreshClients = document.getElementById('btnRefreshClients');

const addModal = document.getElementById('addModal');
const formAddRepo = document.getElementById('formAddRepo');
const inputAddUrl = document.getElementById('addUrl');
const inputAddName = document.getElementById('addName');
const selectAddType = document.getElementById('addType');
const inputAddPattern = document.getElementById('addPattern');
const parentAppGroup = document.getElementById('parentAppGroup');

/**
 * Display a temporary toast notification.
 * @param {string} message
 */
function showToast(message) {
  toastElement.textContent = message;
  toastElement.classList.add('visible');
  setTimeout(() => {
    toastElement.classList.remove('visible');
  }, 4000);
}

/**
 * Capitalize string for application names (e.g. 'opencadstudio' -> 'OpenCADStudio').
 * @param {string} str
 * @returns {string}
 */
function formatAppName(str) {
  if (!str) return '';
  const lower = str.toLowerCase();
  if (lower === 'opencadstudio') return 'OpenCADStudio';
  if (lower === 'ingetrazo') return 'Ingetrazo';
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * Automatically parse GitHub URL on paste or typing.
 * @param {string} url
 */
function autoParseGitHubUrl(url) {
  const cleanUrl = url.trim().replace(/\.git$/, '');
  let owner = '';
  let repo = '';

  if (cleanUrl.includes('github.com/')) {
    const parts = cleanUrl.split('github.com/')[1].split('/');
    if (parts.length >= 2) {
      owner = parts[0];
      repo = parts[1];
    }
  } else if (cleanUrl.includes('/')) {
    const parts = cleanUrl.split('/');
    if (parts.length === 2) {
      owner = parts[0];
      repo = parts[1];
    }
  }

  if (repo && !inputAddName.value.trim()) {
    inputAddName.value = formatAppName(repo);
  }
}

/**
 * Fetch and render configuration from server.
 */
async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    if (!res.ok) throw new Error('Failed to load configuration');
    appConfig = await res.json();
    inputLanFolder.value = appConfig.lan_folder || '';
    renderRepoTable();
  } catch (err) {
    showToast('Error loading configuration.');
  }
}

/**
 * Update selection state and action buttons.
 */
function updateSelectionState() {
  const totalCount = selectedItemIds.size;
  pullSelectedLabel.textContent = `Pull Selected (${totalCount})`;
  btnPullSelected.disabled = totalCount === 0;

  const allCheckboxes = document.querySelectorAll('.repo-select-checkbox');
  if (allCheckboxes.length > 0) {
    const allChecked = Array.from(allCheckboxes).every((cb) => cb.checked);
    selectAllCheckbox.checked = allChecked;
  } else {
    selectAllCheckbox.checked = false;
  }
}

/**
 * Render tracked repositories table rows.
 */
function renderRepoTable() {
  repoTableBody.innerHTML = '';
  selectedItemIds.clear();

  const repos = appConfig?.repositories || [];
  if (repos.length === 0) {
    repoTableBody.innerHTML = `
      <tr>
        <td colspan="7" class="table-empty-cell">
          No repositories configured yet. Paste a GitHub URL to start tracking.
        </td>
      </tr>
    `;
    updateSelectionState();
    return;
  }

  repos.forEach((item) => {
    // Select all by default
    selectedItemIds.add(item.id);

    const tr = document.createElement('tr');
    const isUpdateAvailable = item.last_known_tag && item.last_known_tag !== item.last_downloaded_tag;
    const typeBadgeClass = item.type === 'app' ? 'badge-app' : 'badge-extension';

    let testStatusHtml = '<span class="repo-sub-text">Up to date</span>';
    if (item.staging_status === 'downloaded') {
      testStatusHtml = `<span class="badge badge-staging" title="Downloaded to local staging folder">Staged (${escapeHtml(item.staging_tag)})</span>`;
    } else if (item.staging_status === 'tested') {
      testStatusHtml = `<span class="badge badge-staging" title="Installer launched and tested on host">Tested (${escapeHtml(item.staging_tag)})</span>`;
    } else if (item.staging_status === 'approved') {
      testStatusHtml = '<span class="badge badge-approved" title="Approved and live in LAN folder">Cleared & Live</span>';
    } else if (isUpdateAvailable) {
      testStatusHtml = '<span class="repo-sub-text" style="color: var(--accent-amber);">Update Available</span>';
    }

    let actionsHtml = '';
    if (item.staging_status === 'downloaded') {
      actionsHtml += `<button class="btn btn-secondary btn-sm btn-run-test" data-id="${escapeHtml(item.id)}" title="Launch installer on this PC to test">Run Test</button>`;
      actionsHtml += `<button class="btn btn-emerald btn-sm btn-approve-fleet" data-id="${escapeHtml(item.id)}" title="Clear test and push to LAN folder for offline workstations">Push to Fleet</button>`;
    } else if (item.staging_status === 'tested') {
      actionsHtml += `<button class="btn btn-secondary btn-sm btn-run-test" data-id="${escapeHtml(item.id)}" title="Run installer again on this PC">Run Again</button>`;
      actionsHtml += `<button class="btn btn-emerald btn-sm btn-approve-fleet" data-id="${escapeHtml(item.id)}" title="Clear test and push to LAN folder for offline workstations">Approve & Push</button>`;
    } else if (isUpdateAvailable) {
      actionsHtml += `<button class="btn btn-amber btn-sm btn-stage-test" data-id="${escapeHtml(item.id)}" title="Download to local staging to test on this PC first">Test on Host</button>`;
      actionsHtml += `<button class="btn btn-emerald btn-sm btn-direct-push" data-id="${escapeHtml(item.id)}" title="Push directly to LAN folder without local test">Direct Push</button>`;
    }
    actionsHtml += `<button class="btn btn-danger btn-sm btn-delete-repo" data-id="${escapeHtml(item.id)}" title="Remove repository">Delete</button>`;

    tr.innerHTML = `
      <td class="td-checkbox">
        <input type="checkbox" class="custom-checkbox repo-select-checkbox" data-id="${escapeHtml(item.id)}" checked>
      </td>
      <td>
        <div class="repo-name-text">${escapeHtml(item.name)}</div>
        ${item.parent_app ? `<div class="repo-sub-text">Extension of ${escapeHtml(item.parent_app)}</div>` : ''}
      </td>
      <td>
        <span class="badge ${typeBadgeClass}">${escapeHtml(item.type)}</span>
      </td>
      <td class="repo-url-cell">${escapeHtml(item.repo_url)}</td>
      <td>${escapeHtml(item.last_downloaded_tag || 'None')}</td>
      <td>
        <span>${escapeHtml(item.last_known_tag || 'Unchecked')}</span>
        ${isUpdateAvailable ? '<span class="badge badge-update">New</span>' : ''}
      </td>
      <td>${testStatusHtml}</td>
      <td>
        <div class="cell-actions-flex">
          ${actionsHtml}
        </div>
      </td>
    `;
    repoTableBody.appendChild(tr);
  });

  // Attach row checkbox listeners
  document.querySelectorAll('.repo-select-checkbox').forEach((cb) => {
    cb.addEventListener('change', (e) => {
      const id = e.target.dataset.id;
      if (e.target.checked) {
        selectedItemIds.add(id);
      } else {
        selectedItemIds.delete(id);
      }
      updateSelectionState();
    });
  });

  // Attach staged test and approve listeners
  document.querySelectorAll('.btn-stage-test').forEach((btn) => {
    btn.addEventListener('click', () => handleStageTest(btn.dataset.id));
  });

  document.querySelectorAll('.btn-run-test').forEach((btn) => {
    btn.addEventListener('click', () => handleRunTest(btn.dataset.id));
  });

  document.querySelectorAll('.btn-approve-fleet').forEach((btn) => {
    btn.addEventListener('click', () => handleApprovePush(btn.dataset.id));
  });

  document.querySelectorAll('.btn-direct-push').forEach((btn) => {
    btn.addEventListener('click', () => handleDirectPush(btn.dataset.id));
  });

  // Attach delete listeners
  document.querySelectorAll('.btn-delete-repo').forEach((btn) => {
    btn.addEventListener('click', () => handleDeleteRepo(btn.dataset.id));
  });

  updateSelectionState();
}

/**
 * Escape HTML to prevent XSS.
 * @param {string} text
 * @returns {string}
 */
function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Save target LAN folder path.
 */
async function handleSaveLanFolder() {
  const path = inputLanFolder.value.trim();
  if (!path) {
    showToast('Please enter a valid directory path.');
    return;
  }

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lan_folder: path })
    });
    if (res.ok) {
      showToast('LAN folder path updated successfully.');
      loadConfig();
    }
  } catch (err) {
    showToast('Failed to update LAN folder path.');
  }
}

/**
 * Trigger GitHub update check.
 */
async function handleCheckUpdates() {
  showToast('Checking GitHub for new releases...');
  try {
    const res = await fetch('/api/check');
    if (!res.ok) throw new Error('Failed to check updates');
    const updates = await res.json();
    pendingUpdates = updates;

    if (updates.length > 0) {
      alertUpdateList.innerHTML = '';
      updates.forEach((u) => {
        const li = document.createElement('li');
        li.textContent = `${u.name} [${u.type}]: ${u.current_tag} ➔ ${u.latest_tag} (${u.asset_name || 'No asset'})`;
        alertUpdateList.appendChild(li);
      });
      alertBanner.classList.add('visible');
      showToast(`Found ${updates.length} available update(s)!`);
    } else {
      alertBanner.classList.remove('visible');
      showToast('All repositories and extensions are up to date.');
    }
    loadConfig();
  } catch (err) {
    showToast('Update check failed.');
  }
}

/**
 * Download updates into LAN folder.
 * @param {Array} items
 */
async function executePull(items) {
  if (!items.length) {
    showToast('No items available to pull.');
    return;
  }

  showToast('Downloading releases to LAN folder...');
  try {
    const res = await fetch('/api/pull', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items })
    });
    if (!res.ok) throw new Error('Download failed');
    const result = await res.json();
    alertBanner.classList.remove('visible');
    showToast(`Successfully downloaded ${result.count} package(s) and version file(s).`);
    pendingUpdates = [];
    loadConfig();
  } catch (err) {
    showToast('Download failed. Check network connection.');
  }
}

/**
 * Download a single repository package to staging for local testing on host PC.
 * @param {string} id
 */
async function handleStageTest(id) {
  showToast('Downloading package to staging folder for host testing...');
  try {
    const res = await fetch('/api/test/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`Package ${data.result.file} staged. Ready to run local test!`);
      loadConfig();
    } else {
      showToast(`Error: ${data.message || 'Download failed'}`);
    }
  } catch (err) {
    showToast('Failed to download for testing.');
  }
}

/**
 * Launch the staged installer locally on the host PC.
 * @param {string} id
 */
async function handleRunTest(id) {
  showToast('Launching installer for local testing on host...');
  try {
    const res = await fetch('/api/test/launch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`Launched ${data.result.file} on host PC. Verify it now!`);
      loadConfig();
    } else {
      showToast(`Error: ${data.message || 'Launch failed'}`);
    }
  } catch (err) {
    showToast('Failed to launch test installer.');
  }
}

/**
 * Clear test and approve pushing to offline LAN folder.
 * @param {string} id
 */
async function handleApprovePush(id) {
  if (!confirm('Test cleared on host? Approve and push this update to the LAN folder for all offline workstations?')) return;
  showToast('Pushing verified package to LAN shared folder...');
  try {
    const res = await fetch('/api/test/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`Test cleared! ${data.result.name} ${data.result.tag} is now live for offline PCs.`);
      alertBanner.classList.remove('visible');
      loadConfig();
    } else {
      showToast(`Error: ${data.message || 'Push failed'}`);
    }
  } catch (err) {
    showToast('Failed to push to offline fleet.');
  }
}

/**
 * Push an application directly without local testing.
 * @param {string} id
 */
async function handleDirectPush(id) {
  showToast('Checking package details for direct LAN push...');
  try {
    const res = await fetch('/api/check');
    const updates = await res.json();
    const item = updates.find((u) => u.id === id);
    if (item && item.download_url) {
      executePull([item]);
    } else {
      showToast('Could not find download asset for this update.');
    }
  } catch (err) {
    showToast('Direct push failed.');
  }
}

/**
 * Download all updates to staging for testing on the host PC.
 */
async function handleTestAll() {
  if (!pendingUpdates.length) return;
  showToast('Downloading all updates to staging folder for host testing...');
  try {
    const res = await fetch('/api/test/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: pendingUpdates })
    });
    const data = await res.json();
    showToast(`Downloaded ${data.count} package(s) to staging. Ready to test!`);
    alertBanner.classList.remove('visible');
    loadConfig();
  } catch (err) {
    showToast('Staging download failed.');
  }
}

/**
 * Pull all detected updates.
 */
function handlePullAll() {
  executePull(pendingUpdates);
}

/**
 * Pull only selected applications.
 */
function handlePullSelected() {
  // If we have pending updates, filter by selected IDs
  if (pendingUpdates.length > 0) {
    const filtered = pendingUpdates.filter((u) => selectedItemIds.has(u.id));
    executePull(filtered);
  } else {
    // If no check was run yet, trigger a check first then pull selected
    showToast('Checking updates for selected items...');
    fetch('/api/check')
      .then((res) => res.json())
      .then((updates) => {
        pendingUpdates = updates;
        const filtered = updates.filter((u) => selectedItemIds.has(u.id));
        if (filtered.length > 0) {
          executePull(filtered);
        } else {
          showToast('Selected applications are already up to date.');
        }
      })
      .catch(() => showToast('Check failed.'));
  }
}

/**
 * Delete a repository from tracking.
 * @param {string} id
 */
async function handleDeleteRepo(id) {
  if (!confirm('Remove this repository from tracking?')) return;
  try {
    const res = await fetch(`/api/repos?id=${encodeURIComponent(id)}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('Repository removed.');
      loadConfig();
    }
  } catch (err) {
    showToast('Failed to delete repository.');
  }
}

/**
 * Handle Add Repository form submit.
 * @param {Event} event
 */
async function handleAddRepoSubmit(event) {
  event.preventDefault();
  const payload = {
    name: inputAddName.value.trim(),
    type: selectAddType.value,
    parent_app: document.getElementById('addParentApp').value.trim() || null,
    repo_url: inputAddUrl.value.trim(),
    asset_pattern: inputAddPattern.value.trim() || '.*\\.(exe|msi|zip)$'
  };

  try {
    const res = await fetch('/api/repos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      if (addModal) {
        addModal.classList.remove('visible');
      }
      formAddRepo.reset();
      inputAddPattern.value = '.*\\.(exe|msi|zip)$';
      showToast('Repository added successfully.');
      loadConfig();
    }
  } catch (err) {
    showToast('Failed to add repository.');
  }
}

/**
 * Terminate server and close application to free RAM.
 */
async function handleShutdown() {
  if (!confirm('Close the UI and free all system memory now?')) return;
  try {
    await fetch('/api/shutdown', { method: 'POST' });
  } catch (err) {}
  document.body.innerHTML = `
    <div class="terminated-container">
      <h2 class="terminated-title">Application Terminated</h2>
      <p class="terminated-text">The local server has stopped. All system memory is completely freed.</p>
      <p class="terminated-subtext">You can now close this browser tab.</p>
    </div>
  `;
}

// Preset Handlers
document.getElementById('presetIngetrazo').addEventListener('click', () => {
  inputAddUrl.value = 'https://github.com/ingetrazo/ingetrazo';
  inputAddName.value = 'Ingetrazo';
  selectAddType.value = 'app';
  inputAddPattern.value = '.*\\.(exe|msi|zip)$';
  parentAppGroup.classList.add('hidden-element');
});

document.getElementById('presetOpenCAD').addEventListener('click', () => {
  inputAddUrl.value = 'https://github.com/opencadstudio/opencadstudio';
  inputAddName.value = 'OpenCADStudio';
  selectAddType.value = 'app';
  inputAddPattern.value = '.*\\.(exe|msi|zip)$';
  parentAppGroup.classList.add('hidden-element');
});

// Auto-parse on paste or input in URL field
inputAddUrl.addEventListener('input', (e) => autoParseGitHubUrl(e.target.value));
inputAddUrl.addEventListener('paste', (e) => {
  setTimeout(() => autoParseGitHubUrl(inputAddUrl.value), 50);
});

// Select All Toggle
selectAllCheckbox.addEventListener('change', (e) => {
  const isChecked = e.target.checked;
  const allCheckboxes = document.querySelectorAll('.repo-select-checkbox');
  allCheckboxes.forEach((cb) => {
    cb.checked = isChecked;
    const id = cb.dataset.id;
    if (isChecked) {
      selectedItemIds.add(id);
    } else {
      selectedItemIds.delete(id);
    }
  });
  updateSelectionState();
});

// Copy snippet button
document.getElementById('btnCopySnippet').addEventListener('click', () => {
  const snippet = document.getElementById('clientScriptSnippet').textContent;
  navigator.clipboard.writeText(snippet);
  showToast('Copied client script command to clipboard.');
});

/**
 * Fetch and render connected offline clients.
 */
async function loadConnectedClients() {
  try {
    const res = await fetch('/api/clients');
    if (!res.ok) throw new Error('Failed to load clients');
    const clients = await res.json();
    renderClientsTable(clients);
  } catch (err) {
    // Silently continue if not ready
  }
}

/**
 * Render connected offline workstations in table.
 * @param {Array} clients
 */
function renderClientsTable(clients) {
  if (!clientsTableBody) return;
  clientsTableBody.innerHTML = '';

  if (!clients || clients.length === 0) {
    clientsTableBody.innerHTML = `
      <tr>
        <td colspan="5" class="table-empty-cell">
          No offline workstations have reported yet. Run pull_update.ps1 on client PCs to register automatically.
        </td>
      </tr>
    `;
    return;
  }

  clients.forEach((c) => {
    const tr = document.createElement('tr');
    let versionsHtml = '';
    const versions = c.installed_versions || {};
    const keys = Object.keys(versions);
    if (keys.length === 0) {
      versionsHtml = '<span class="repo-sub-text">None</span>';
    } else {
      keys.forEach((appKey) => {
        versionsHtml += `<span class="badge badge-extension client-version-tag">${escapeHtml(appKey)}: ${escapeHtml(versions[appKey])}</span>`;
      });
    }

    const isCurrent = c.status === 'Current' || c.status === 'Updated';
    const statusBadgeClass = isCurrent ? 'badge-app' : 'badge-update';

    tr.innerHTML = `
      <td><strong>${escapeHtml(c.computer_name || 'Unknown')}</strong></td>
      <td class="repo-url-cell">${escapeHtml(c.ip_address || 'Unknown')}</td>
      <td>${versionsHtml}</td>
      <td class="repo-sub-text">${escapeHtml(c.last_seen || 'Unknown')}</td>
      <td><span class="badge ${statusBadgeClass}">${escapeHtml(c.status || 'Active')}</span></td>
    `;
    clientsTableBody.appendChild(tr);
  });
}

// Refresh Clients Button
if (btnRefreshClients) {
  btnRefreshClients.addEventListener('click', () => {
    loadConnectedClients();
    showToast('Refreshed connected client list.');
  });
}

// Event Listeners
document.getElementById('btnSaveLanFolder').addEventListener('click', handleSaveLanFolder);
document.getElementById('btnCheckUpdates').addEventListener('click', handleCheckUpdates);
const btnTestAll = document.getElementById('btnTestAll');
if (btnTestAll) {
  btnTestAll.addEventListener('click', handleTestAll);
}
document.getElementById('btnPullAll').addEventListener('click', handlePullAll);
document.getElementById('btnPullSelected').addEventListener('click', handlePullSelected);
document.getElementById('btnDismissAlert').addEventListener('click', () => alertBanner.classList.remove('visible'));
document.getElementById('btnShutdown').addEventListener('click', handleShutdown);

const btnOpenAddModal = document.getElementById('btnOpenAddModal');
if (btnOpenAddModal) {
  btnOpenAddModal.addEventListener('click', () => {
    inputAddPattern.value = '.*\\.(exe|msi|zip)$';
    if (addModal) addModal.classList.add('visible');
    inputAddUrl.focus();
  });
}

const btnCloseModal = document.getElementById('btnCloseModal');
if (btnCloseModal && addModal) {
  btnCloseModal.addEventListener('click', () => addModal.classList.remove('visible'));
}

const btnCancelAdd = document.getElementById('btnCancelAdd');
if (btnCancelAdd && addModal) {
  btnCancelAdd.addEventListener('click', () => addModal.classList.remove('visible'));
}

selectAddType.addEventListener('change', (e) => {
  if (e.target.value === 'extension') {
    parentAppGroup.classList.remove('hidden-element');
  } else {
    parentAppGroup.classList.add('hidden-element');
  }
});

formAddRepo.addEventListener('submit', handleAddRepoSubmit);

// Initial Load
loadConfig();
loadConnectedClients();
