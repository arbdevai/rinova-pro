/**
 * Rinova Pro - Professional Diagnostics & Package Manager Controller
 */

const state = {
  activeTab: 'storage',
  activeDevice: null,
  isScanning: false,
  isFixing: false,
  packages: [],
  filteredPackages: [],
  selectedPackages: new Set(),
  activeFilter: 'all',
  pendingAction: null
};

// API Bridge
async function callApi(endpoint, payload = {}) {
  if (window.pywebview && window.pywebview.api) {
    const fnName = endpoint.replace('/api/', '').replace(/-/g, '_');
    if (typeof window.pywebview.api[fnName] === 'function') {
      try {
        return await window.pywebview.api[fnName](payload);
      } catch (err) {
        console.error("PyWebView Error:", err);
        throw err;
      }
    }
  }

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return await res.json();
  } catch (err) {
    console.error(`API [${endpoint}] Error:`, err);
    throw err;
  }
}

// Logger
function log(msg, type = 'info') {
  const consoleEl = document.getElementById('log-console');
  if (!consoleEl) return;
  const line = document.createElement('div');
  const now = new Date().toLocaleTimeString();

  let colorClass = 'text-zinc-400';
  if (type === 'success') colorClass = 'text-emerald-400';
  if (type === 'error') colorClass = 'text-rose-400';
  if (type === 'warn') colorClass = 'text-amber-400';
  if (type === 'brand') colorClass = 'text-brand-400';

  line.className = colorClass;
  line.textContent = `[${now}] ${msg}`;
  consoleEl.appendChild(line);
  consoleEl.scrollTop = consoleEl.scrollHeight;
}

function clearLogs() {
  const consoleEl = document.getElementById('log-console');
  if (consoleEl) consoleEl.innerHTML = '';
  log('Console cleared.', 'info');
}

// Toast
function showToast(message, type = 'success') {
  const toast = document.getElementById('toast');
  const msgEl = document.getElementById('toast-msg');
  const iconEl = document.getElementById('toast-icon');

  msgEl.textContent = message;
  iconEl.className = 'ph-bold ' + (
    type === 'success' ? 'ph-check text-emerald-400' :
    type === 'error' ? 'ph-x text-rose-400' :
    type === 'warn' ? 'ph-warning text-amber-400' : 'ph-info text-brand-400'
  );

  toast.classList.remove('translate-y-16', 'opacity-0');
  setTimeout(() => {
    toast.classList.add('translate-y-16', 'opacity-0');
  }, 2500);
}

// Tab navigation
function switchTab(tabName) {
  state.activeTab = tabName;
  ['storage', 'debloat', 'wireless'].forEach(t => {
    const pane = document.getElementById(`tab-${t}`);
    const nav = document.getElementById(`nav-${t}`);
    const isSelected = (t === tabName);

    if (isSelected) {
      pane.classList.remove('hidden');
      nav.className = 'nav-tab px-3.5 py-1.5 rounded-md text-xs font-medium transition-colors duration-150 text-brand-400 bg-dark-800 border border-brand-500/30';
    } else {
      pane.classList.add('hidden');
      nav.className = 'nav-tab px-3.5 py-1.5 rounded-md text-xs font-medium transition-colors duration-150 text-zinc-400 hover:text-zinc-200 hover:bg-dark-800/50 border border-transparent';
    }
  });

  if (tabName === 'debloat' && state.packages.length === 0) {
    loadDevicePackages();
  }
}

// Refresh Connected Device
async function refreshDeviceList() {
  const icon = document.getElementById('refresh-icon');
  if (icon) icon.classList.add('animate-spin');
  log('Scanning ADB interfaces...', 'info');

  try {
    const devices = await callApi('/api/get-devices');
    if (icon) icon.classList.remove('animate-spin');

    const pillDot = document.getElementById('device-dot');
    const pillText = document.getElementById('device-text');

    if (devices && devices.length > 0) {
      const dev = devices[0];
      state.activeDevice = dev.serial;
      await callApi('/api/select-device', { serial: dev.serial });

      pillDot.className = 'w-2 h-2 rounded-full bg-emerald-500';
      pillText.textContent = `${dev.model || dev.serial}`;

      const info = await callApi('/api/get-device-info', { serial: dev.serial });
      if (info.connected) {
        log(`Attached: ${info.manufacturer} ${info.model} (Android ${info.android_version})`, 'success');
      }
    } else {
      state.activeDevice = null;
      pillDot.className = 'w-2 h-2 rounded-full bg-zinc-600';
      pillText.textContent = 'DISCONNECTED';
      log('No devices attached. Check USB connection or Wireless ADB status.', 'warn');
    }
  } catch (err) {
    if (icon) icon.classList.remove('animate-spin');
    log('Device scan failure: ' + err.message, 'error');
  }
}

// ================= STORAGE ANALYSIS =================
async function runStorageScan() {
  if (state.isScanning) return;
  state.isScanning = true;

  const btn = document.getElementById('btn-scan');
  btn.innerHTML = '<i class="ph-bold ph-spinner animate-spin text-xs"></i><span>Scanning...</span>';
  btn.disabled = true;

  log('Executing df and dumpsys diskstats queries...', 'info');

  try {
    const data = await callApi('/api/scan-storage', { serial: state.activeDevice });
    state.isScanning = false;
    btn.innerHTML = '<i class="ph-bold ph-magnifying-glass text-xs"></i><span>Scan Partition</span>';
    btn.disabled = false;

    const part = data.partition || {};
    const mediaBloat = data.media_bloat || {};

    document.getElementById('stat-total').textContent = `${part.total_gb || '--'} GB`;
    document.getElementById('stat-free').textContent = `${part.free_gb || '--'} GB`;
    document.getElementById('stat-percent').textContent = `Usage: ${part.percent_used || 0}%`;

    const bloatStat = document.getElementById('stat-media-bloat');
    const bloatNote = document.getElementById('stat-bloat-note');

    if (mediaBloat.detected) {
      bloatStat.className = 'text-2xl font-bold font-mono text-brand-400';
      bloatStat.textContent = `${mediaBloat.reclaimable_gb} GB`;
      bloatNote.textContent = 'Status: Anomaly Detected (Reclaimable)';
      log(`Diagnostic: external.db anomaly identified (${mediaBloat.reclaimable_gb} GB).`, 'warn');
    } else {
      bloatStat.className = 'text-2xl font-bold font-mono text-emerald-400';
      bloatStat.textContent = `${mediaBloat.details?.external_db_mb || 0} MB`;
      bloatNote.textContent = 'Status: Normal';
    }

    // Allocation bar
    const total = part.total_gb || 1;
    const bloatGb = mediaBloat.reclaimable_gb || 0;
    const usedGb = Math.max(0, (part.used_gb || 0) - bloatGb);
    const freeGb = part.free_gb || 0;

    const usedPct = (usedGb / total) * 100;
    const bloatPct = (bloatGb / total) * 100;
    const freePct = (freeGb / total) * 100;

    document.getElementById('bar-used').style.width = `${usedPct}%`;
    document.getElementById('bar-bloat').style.width = `${bloatPct}%`;
    document.getElementById('bar-free').style.width = `${freePct}%`;

    document.getElementById('bar-summary-text').textContent = 
      `Used: ${(part.used_gb || 0).toFixed(1)} GB | Free: ${freeGb.toFixed(1)} GB`;

    // Render top apps
    const tbody = document.getElementById('top-apps-tbody');
    tbody.innerHTML = '';
    const topApps = data.top_apps || [];
    if (topApps.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" class="py-4 text-center text-zinc-500">No data returned.</td></tr>';
    } else {
      topApps.forEach(app => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-dark-850';
        const isMedia = app.package.includes('providers.media');
        tr.innerHTML = `
          <td class="py-2 px-4 font-mono flex items-center gap-2">
            ${isMedia ? '<span class="w-1.5 h-1.5 rounded-full bg-brand-500"></span>' : ''}
            <span class="${isMedia ? 'text-brand-400 font-semibold' : 'text-zinc-300'}">${app.package}</span>
          </td>
          <td class="py-2 px-4 text-right font-mono text-zinc-400">${app.size_mb.toLocaleString()} MB</td>
          <td class="py-2 px-4 text-right font-mono font-medium ${isMedia ? 'text-brand-400' : 'text-zinc-200'}">${app.size_gb} GB</td>
        `;
        tbody.appendChild(tr);
      });
    }

    log(`Partition scan complete: ${part.free_gb} GB available.`, 'success');
    showToast('Scan complete');
  } catch (err) {
    state.isScanning = false;
    btn.innerHTML = '<i class="ph-bold ph-magnifying-glass text-xs"></i><span>Scan Partition</span>';
    btn.disabled = false;
    log('Scan failed: ' + err.message, 'error');
    showToast('Scan failed', 'error');
  }
}

// Media Optimization
async function executeSafeFix() {
  if (state.isFixing) return;
  state.isFixing = true;

  const btn = document.getElementById('btn-fix');
  btn.innerHTML = '<i class="ph-bold ph-spinner animate-spin text-xs"></i><span>Optimizing...</span>';
  btn.disabled = true;

  log('Resetting MediaProvider database and dispatching MediaScanner broadcast...', 'info');

  try {
    const res = await callApi('/api/fix-media-storage', { serial: state.activeDevice });
    state.isFixing = false;
    btn.innerHTML = '<i class="ph-bold ph-wrench text-xs"></i><span>Optimize MediaStore</span>';
    btn.disabled = false;

    if (res.success) {
      log(`Operation success: Reclaimed ${res.reclaimed_gb} GB storage space.`, 'success');
      showToast(`Reclaimed +${res.reclaimed_gb} GB`, 'success');
      setTimeout(runStorageScan, 1500);
    } else {
      log('Optimization failure: ' + res.error, 'error');
      showToast('Optimization failed', 'error');
    }
  } catch (err) {
    state.isFixing = false;
    btn.innerHTML = '<i class="ph-bold ph-wrench text-xs"></i><span>Optimize MediaStore</span>';
    btn.disabled = false;
    log('System error: ' + err.message, 'error');
  }
}

// ================= DYNAMIC PACKAGE MANAGEMENT =================
async function loadDevicePackages() {
  const icon = document.getElementById('spin-pkg-icon');
  if (icon) icon.classList.add('animate-spin');

  const listEl = document.getElementById('pkgs-list');
  listEl.innerHTML = '<div class="text-center py-12 text-zinc-500 text-xs italic"><i class="ph-bold ph-spinner animate-spin mr-1"></i> Querying package manager (pm)...</div>';

  log('Fetching package list from target device via pm list packages...', 'info');

  try {
    const pkgs = await callApi('/api/list-device-packages', { serial: state.activeDevice });
    if (icon) icon.classList.remove('animate-spin');

    state.packages = pkgs || [];
    state.selectedPackages.clear();
    updateSelectionCounter();
    filterPackages();

    log(`Query returned ${state.packages.length} installed packages.`, 'success');
  } catch (err) {
    if (icon) icon.classList.remove('animate-spin');
    listEl.innerHTML = `<div class="text-center py-12 text-rose-400 text-xs">Query failed: ${err.message}</div>`;
    log('Failed to fetch packages: ' + err.message, 'error');
  }
}

function setCategoryFilter(filterKey) {
  state.activeFilter = filterKey;
  ['all', 'suggested', 'system', 'disabled'].forEach(f => {
    const btn = document.getElementById(`filter-${f}`);
    const isSelected = (f === filterKey);
    if (isSelected) {
      btn.className = 'filter-chip px-3 py-1 rounded text-xs font-medium transition-colors text-brand-400 bg-dark-800 border border-brand-500/30';
    } else {
      btn.className = 'filter-chip px-3 py-1 rounded text-xs font-medium transition-colors text-zinc-400 hover:text-white border border-transparent';
    }
  });
  filterPackages();
}

function filterPackages() {
  const query = document.getElementById('pkg-search').value.toLowerCase().trim();

  state.filteredPackages = state.packages.filter(p => {
    const matchQuery = !query || p.package.toLowerCase().includes(query) || (p.category && p.category.toLowerCase().includes(query));
    if (!matchQuery) return false;

    if (state.activeFilter === 'suggested') return p.is_suggested;
    if (state.activeFilter === 'system') return p.is_system;
    if (state.activeFilter === 'disabled') return p.is_disabled;
    return true;
  });

  renderPackagesList();
}

function renderPackagesList() {
  const container = document.getElementById('pkgs-list');
  container.innerHTML = '';

  if (state.filteredPackages.length === 0) {
    container.innerHTML = '<div class="text-center py-12 text-zinc-500 text-xs italic">No matching packages found.</div>';
    return;
  }

  state.filteredPackages.forEach(p => {
    const row = document.createElement('div');
    row.className = 'flex items-center justify-between p-2.5 px-4 hover:bg-dark-850';

    const isChecked = state.selectedPackages.has(p.package);

    let badge = '';
    if (p.is_disabled) {
      badge = '<span class="px-2 py-0.5 rounded text-[10px] font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">Disabled</span>';
    } else if (p.is_suggested) {
      badge = '<span class="px-2 py-0.5 rounded text-[10px] font-medium bg-brand-500/10 text-brand-400 border border-brand-500/20">Suggested</span>';
    } else {
      badge = `<span class="px-2 py-0.5 rounded text-[10px] text-zinc-500">${p.type}</span>`;
    }

    row.innerHTML = `
      <div class="flex items-center gap-3">
        <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="toggleSelectPackage('${p.package}', this.checked)" class="rounded bg-dark-950 border-dark-border text-brand-500 w-3.5 h-3.5 cursor-pointer accent-orange-500">
        <div>
          <div class="flex items-center gap-2">
            <span class="text-xs font-mono ${p.is_disabled ? 'line-through text-zinc-500' : 'text-zinc-200'}">${p.package}</span>
            ${badge}
          </div>
          <div class="text-[11px] text-zinc-500 font-sans">${p.category}</div>
        </div>
      </div>
      <div>
        <span class="text-[11px] text-zinc-500 font-mono">${p.is_disabled ? 'Disabled' : 'Enabled'}</span>
      </div>
    `;
    container.appendChild(row);
  });
}

function toggleSelectPackage(pkg, checked) {
  if (checked) {
    state.selectedPackages.add(pkg);
  } else {
    state.selectedPackages.delete(pkg);
  }
  updateSelectionCounter();
}

function toggleSelectAll(checked) {
  state.filteredPackages.forEach(p => {
    if (checked) {
      state.selectedPackages.add(p.package);
    } else {
      state.selectedPackages.delete(p.package);
    }
  });
  renderPackagesList();
  updateSelectionCounter();
}

function updateSelectionCounter() {
  const count = state.selectedPackages.size;
  document.getElementById('selected-counter').textContent = `${count} selected`;
}

// Confirmation Dialog
function promptBatchAction(action) {
  if (state.selectedPackages.size === 0) {
    showToast('Select at least one package', 'warn');
    return;
  }

  state.pendingAction = action;

  const modal = document.getElementById('confirm-modal');
  const title = document.getElementById('modal-title');
  const subtitle = document.getElementById('modal-subtitle');
  const countEl = document.getElementById('modal-pkg-count');
  const previewEl = document.getElementById('modal-pkg-preview');
  const warningText = document.getElementById('modal-warning-text');
  const confirmBtn = document.getElementById('modal-btn-confirm');

  countEl.textContent = state.selectedPackages.size;
  previewEl.innerHTML = Array.from(state.selectedPackages).map(p => `<div>${p}</div>`).join('');

  if (action === 'disable') {
    title.textContent = 'Disable Selected Packages';
    subtitle.textContent = 'Execute pm disable-user --user 0';
    warningText.textContent = 'Disables target applications for primary user. Can be re-enabled at any time.';
    confirmBtn.className = 'h-8 px-4 rounded-md text-xs font-medium bg-brand-500 hover:bg-brand-600 text-white';
    confirmBtn.textContent = 'Disable';
  } else if (action === 'enable') {
    title.textContent = 'Enable Selected Packages';
    subtitle.textContent = 'Execute pm enable';
    warningText.textContent = 'Restores target applications to active state.';
    confirmBtn.className = 'h-8 px-4 rounded-md text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white';
    confirmBtn.textContent = 'Enable';
  } else if (action === 'uninstall') {
    title.textContent = 'Uninstall Packages (User 0)';
    subtitle.textContent = 'Execute pm uninstall -k --user 0';
    warningText.textContent = 'Caution: Do not uninstall core system frameworks to avoid system crash or bootloop.';
    confirmBtn.className = 'h-8 px-4 rounded-md text-xs font-medium bg-rose-600 hover:bg-rose-500 text-white';
    confirmBtn.textContent = 'Uninstall';
  }

  modal.classList.remove('hidden');
  setTimeout(() => modal.classList.remove('opacity-0'), 10);
}

function closeConfirmModal() {
  const modal = document.getElementById('confirm-modal');
  modal.classList.add('opacity-0');
  setTimeout(() => modal.classList.add('hidden'), 150);
  state.pendingAction = null;
}

async function executeBatchActionConfirmed() {
  if (!state.pendingAction || state.selectedPackages.size === 0) return;

  const action = state.pendingAction;
  const packagesList = Array.from(state.selectedPackages);
  closeConfirmModal();

  log(`Executing '${action}' on ${packagesList.length} packages...`, 'info');

  try {
    const res = await callApi('/api/batch-package-action', {
      packages: packagesList,
      action: action,
      serial: state.activeDevice
    });

    log(`Batch complete: ${res.success_count} succeeded, ${res.error_count} failed.`, res.error_count > 0 ? 'warn' : 'success');
    showToast(`Processed ${res.success_count} packages`, 'success');

    await loadDevicePackages();
  } catch (err) {
    log('Batch execution error: ' + err.message, 'error');
    showToast('Execution failed', 'error');
  }
}

// ================= WIRELESS ADB =================
async function executePairing() {
  const addr = document.getElementById('input-pair-address').value.trim();
  const code = document.getElementById('input-pair-code').value.trim();

  if (!addr || !code) {
    showToast('Host IP:Port and Pairing Code required', 'warn');
    return;
  }

  const btn = document.getElementById('btn-pair');
  btn.textContent = 'Pairing...';
  log(`Pairing to ${addr}...`, 'info');

  try {
    const res = await callApi('/api/pair-wireless', { address_port: addr, pairing_code: code });
    btn.textContent = 'Pair Device';
    if (res.success) {
      log('Pair success: ' + res.message, 'success');
      showToast('Device paired successfully', 'success');
    } else {
      log('Pair failed: ' + res.message, 'error');
      showToast('Pairing failed', 'error');
    }
  } catch (err) {
    btn.textContent = 'Pair Device';
    log('Pairing error: ' + err.message, 'error');
  }
}

async function executeConnect() {
  const addr = document.getElementById('input-connect-address').value.trim();
  if (!addr) {
    showToast('Host IP:Port required', 'warn');
    return;
  }

  const btn = document.getElementById('btn-connect');
  btn.textContent = 'Connecting...';
  log(`Connecting to ${addr}...`, 'info');

  try {
    const res = await callApi('/api/connect-wireless', { address_port: addr });
    btn.textContent = 'Connect';
    if (res.success) {
      log('Connected: ' + res.message, 'success');
      showToast('Wireless connection established', 'success');
      refreshDeviceList();
      switchTab('storage');
    } else {
      log('Connection failed: ' + res.message, 'error');
      showToast('Connection failed', 'error');
    }
  } catch (err) {
    btn.textContent = 'Connect';
    log('Connection error: ' + err.message, 'error');
  }
}

async function executeDisconnect() {
  log('Disconnecting ADB sessions...', 'info');
  try {
    await callApi('/api/disconnect-device');
    log('Disconnected.', 'info');
    showToast('Disconnected', 'info');
    refreshDeviceList();
  } catch (err) {
    log('Disconnect error: ' + err.message, 'error');
  }
}

// Initializer
window.addEventListener('DOMContentLoaded', () => {
  log('Rinova Pro initialized.', 'info');
  refreshDeviceList();
});
