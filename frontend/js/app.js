/**
 * Rinova Pro - Professional Diagnostics & Multi-Vector Engine Controller
 */

const state = {
  activeTab: 'storage',
  activeDevice: null,
  telemetry: null,
  updateInfo: null,
  isScanning: false,
  isRemediating: false,
  findings: [],
  selectedFindings: new Set(),
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
  ['storage', 'debloat', 'wireless', 'tutorial'].forEach(t => {
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

// Telemetry UI Controller
function updateTelemetryUI(info) {
  state.telemetry = info;
  const connEl = document.getElementById('telemetry-connected');
  const disconnEl = document.getElementById('telemetry-disconnected');
  const transportEl = document.getElementById('telemetry-transport');

  if (!info || !info.connected) {
    clearTelemetryUI();
    return;
  }

  connEl.classList.remove('hidden');
  connEl.classList.add('flex');
  disconnEl.classList.add('hidden');
  transportEl.classList.remove('hidden');

  document.getElementById('telemetry-device').textContent = `${info.manufacturer} ${info.model}`;
  document.getElementById('telemetry-os').textContent = `Android ${info.android_version} (SDK ${info.sdk_version})`;
  document.getElementById('telemetry-patch').textContent = info.security_patch || 'N/A';
  document.getElementById('telemetry-battery').textContent = info.battery_level || '--%';
  document.getElementById('telemetry-temp').textContent = info.battery_temp || '--°C';

  const badgeEl = document.getElementById('telemetry-mode-badge');
  badgeEl.textContent = info.is_wireless ? 'WIRELESS ADB' : 'USB DIRECT';
  badgeEl.className = info.is_wireless 
    ? 'px-2 py-0.5 rounded bg-brand-500/10 text-brand-400 border border-brand-500/30 uppercase'
    : 'px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 uppercase';

  document.getElementById('telemetry-serial').textContent = `ID: ${info.serial}`;
}

function clearTelemetryUI() {
  state.telemetry = null;
  const connEl = document.getElementById('telemetry-connected');
  const disconnEl = document.getElementById('telemetry-disconnected');
  const transportEl = document.getElementById('telemetry-transport');

  if (connEl) {
    connEl.classList.add('hidden');
    connEl.classList.remove('flex');
  }
  if (disconnEl) disconnEl.classList.remove('hidden');
  if (transportEl) transportEl.classList.add('hidden');
}

// Refresh Connected Device with Authorization Validation
async function refreshDeviceList() {
  const icon = document.getElementById('refresh-icon');
  if (icon) icon.classList.add('animate-spin');

  try {
    const heartbeat = await callApi('/api/heartbeat');
    if (icon) icon.classList.remove('animate-spin');

    const pillDot = document.getElementById('device-dot');
    const pillText = document.getElementById('device-text');

    if (heartbeat.unauthorized_count > 0 && !heartbeat.connected) {
      state.activeDevice = null;
      pillDot.className = 'w-2 h-2 rounded-full bg-amber-500 animate-pulse';
      pillText.textContent = 'UNAUTHORIZED';
      clearTelemetryUI();
      log('PERINGATAN: Perangkat terhubung tetapi status UNAUTHORIZED. Harap centang [Selalu Izinkan dari Komputer Ini] pada layar HP.', 'warn');
      showToast('Device unauthorized: Izinkan di layar HP', 'warn');
      return;
    }

    if (heartbeat.connected && heartbeat.active_device) {
      const dev = heartbeat.active_device;
      state.activeDevice = dev.serial;

      pillDot.className = 'w-2 h-2 rounded-full bg-emerald-500';
      pillText.textContent = `${dev.model || dev.serial}`;

      const info = await callApi('/api/get-device-info', { serial: dev.serial });
      if (info.connected) {
        updateTelemetryUI(info);
        log(`Attached: ${info.manufacturer} ${info.model} (Android ${info.android_version}, Patch: ${info.security_patch})`, 'success');
      }
    } else {
      state.activeDevice = null;
      pillDot.className = 'w-2 h-2 rounded-full bg-zinc-600';
      pillText.textContent = 'DISCONNECTED';
      clearTelemetryUI();
    }
  } catch (err) {
    if (icon) icon.classList.remove('animate-spin');
    log('Device scan failure: ' + err.message, 'error');
  }
}

// Background Heartbeat Poller (4s interval)
function initHeartbeat() {
  setInterval(async () => {
    try {
      const hb = await callApi('/api/heartbeat');
      const wasConnected = !!state.activeDevice;
      const isNowConnected = hb.connected && !!hb.active_device;

      if (!wasConnected && isNowConnected) {
        log('Perangkat terdeteksi terhubung via ADB. Memperbarui telemetri...', 'info');
        await refreshDeviceList();
      } else if (wasConnected && !isNowConnected) {
        log('Perangkat terputus dari koneksi ADB.', 'warn');
        state.activeDevice = null;
        document.getElementById('device-dot').className = 'w-2 h-2 rounded-full bg-zinc-600';
        document.getElementById('device-text').textContent = 'DISCONNECTED';
        clearTelemetryUI();
      }
    } catch (e) {
      // Silent error during heartbeat
    }
  }, 4000);
}

// ================= MULTI-VECTOR STORAGE ANALYSIS =================
async function runStorageScan() {
  if (state.isScanning) return;
  state.isScanning = true;

  const btn = document.getElementById('btn-scan');
  btn.innerHTML = '<i class="ph-bold ph-spinner animate-spin text-xs"></i><span>Running Audit...</span>';
  btn.disabled = true;

  log('Executing multi-vector storage audit across all sectors...', 'info');

  try {
    const data = await callApi('/api/scan-storage', { serial: state.activeDevice });
    state.isScanning = false;
    btn.innerHTML = '<i class="ph-bold ph-magnifying-glass text-xs"></i><span>Run Full Audit</span>';
    btn.disabled = false;

    const part = data.partition || {};
    state.findings = data.findings || [];

    // Reset selection to all reclaimable findings
    state.selectedFindings.clear();
    state.findings.forEach(f => {
      if (f.reclaimable) state.selectedFindings.add(f.id);
    });

    document.getElementById('stat-total').textContent = `${part.total_gb || '--'} GB`;
    document.getElementById('stat-free').textContent = `${part.free_gb || '--'} GB`;
    document.getElementById('stat-percent').textContent = `Usage: ${part.percent_used || 0}%`;
    document.getElementById('stat-reclaimable').textContent = `${data.total_reclaimable_gb || 0.0} GB`;
    document.getElementById('stat-reclaimable-note').textContent = `${state.selectedFindings.size} anomali dapat dipulihkan`;

    // Linear bar
    const total = part.total_gb || 1;
    const bloatGb = data.total_reclaimable_gb || 0;
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

    // Render Diagnostic Finding Matrix
    renderFindingsMatrix();
    updateSelectedReclaimText();

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

    log(`Multi-vector audit complete: Total ${data.total_reclaimable_gb} GB reclaimable identified.`, 'success');
    showToast('Audit complete');
  } catch (err) {
    state.isScanning = false;
    btn.innerHTML = '<i class="ph-bold ph-magnifying-glass text-xs"></i><span>Run Full Audit</span>';
    btn.disabled = false;
    log('Audit error: ' + err.message, 'error');
    showToast('Audit failed', 'error');
  }
}

function renderFindingsMatrix() {
  const container = document.getElementById('findings-container');
  container.innerHTML = '';

  if (state.findings.length === 0) {
    container.innerHTML = '<div class="text-center py-8 text-zinc-500 text-xs italic">No findings available.</div>';
    return;
  }

  state.findings.forEach(f => {
    const card = document.createElement('div');
    const isSelected = state.selectedFindings.has(f.id);

    let badgeClass = 'bg-zinc-800 text-zinc-400 border-zinc-700';
    if (f.severity === 'CRITICAL') badgeClass = 'bg-rose-500/10 text-rose-400 border-rose-500/30';
    if (f.severity === 'HIGH') badgeClass = 'bg-brand-500/10 text-brand-400 border-brand-500/30';
    if (f.severity === 'MEDIUM') badgeClass = 'bg-amber-500/10 text-amber-400 border-amber-500/30';
    if (f.severity === 'INFO') badgeClass = 'bg-sky-500/10 text-sky-400 border-sky-500/30';

    card.className = `p-3 rounded-md bg-dark-950 border ${f.reclaimable ? 'border-dark-border hover:border-zinc-700' : 'border-dark-border opacity-70'} transition`;

    card.innerHTML = `
      <div class="flex items-start justify-between gap-3">
        <div class="flex items-start gap-3">
          <input type="checkbox" ${isSelected ? 'checked' : ''} ${f.reclaimable ? '' : 'disabled'} onchange="toggleSelectFinding('${f.id}', this.checked)" class="rounded bg-dark-900 border-dark-border text-brand-500 w-3.5 h-3.5 mt-0.5 cursor-pointer accent-orange-500">
          <div class="space-y-0.5">
            <div class="flex items-center gap-2">
              <span class="text-xs font-semibold text-white">${f.title}</span>
              <span class="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium border ${badgeClass}">${f.severity}</span>
            </div>
            <div class="text-[11px] font-mono text-zinc-500">${f.target}</div>
            <div class="text-xs text-zinc-400 pt-0.5">${f.note}</div>
          </div>
        </div>
        <div class="text-right whitespace-nowrap pl-2">
          <div class="text-xs font-mono font-bold ${f.reclaimable ? 'text-brand-400' : 'text-zinc-500'}">
            ${f.size_gb > 0 ? f.size_gb + ' GB' : f.size_mb + ' MB'}
          </div>
          <div class="text-[10px] text-zinc-500 font-mono">${f.reclaimable ? 'Reclaimable' : 'Static'}</div>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

function toggleSelectFinding(findingId, checked) {
  if (checked) {
    state.selectedFindings.add(findingId);
  } else {
    state.selectedFindings.delete(findingId);
  }
  updateSelectedReclaimText();
}

function updateSelectedReclaimText() {
  let selectedMb = 0;
  state.findings.forEach(f => {
    if (state.selectedFindings.has(f.id)) {
      selectedMb += f.size_mb;
    }
  });
  const selectedGb = (selectedMb / 1024).toFixed(2);
  document.getElementById('selected-reclaim-text').textContent = `Selected: ${selectedGb} GB (${state.selectedFindings.size} vectors)`;
}

// Multi-Vector Remediation Flow with Explicit Confirmation Modal
function executeSelectedRemediation() {
  if (state.selectedFindings.size === 0) {
    showToast('Pilih minimal satu vector remediasi', 'warn');
    return;
  }
  openRemediationModal();
}

function openRemediationModal() {
  const modal = document.getElementById('remediation-modal');
  const countEl = document.getElementById('remed-modal-count');
  const spaceEl = document.getElementById('remed-modal-space');
  const listEl = document.getElementById('remed-modal-list');

  let totalMb = 0;
  listEl.innerHTML = '';

  state.findings.forEach(f => {
    if (state.selectedFindings.has(f.id)) {
      totalMb += f.size_mb;
      const row = document.createElement('div');
      row.className = 'flex items-center justify-between p-2 rounded bg-dark-900 border border-dark-border text-xs';
      row.innerHTML = `
        <div class="flex items-center gap-2">
          <i class="ph-bold ph-check-circle text-brand-400"></i>
          <div>
            <div class="font-medium text-white">${f.title}</div>
            <div class="text-[10px] text-zinc-500 font-mono">${f.target}</div>
          </div>
        </div>
        <div class="font-mono font-semibold text-brand-400">${f.size_gb} GB</div>
      `;
      listEl.appendChild(row);
    }
  });

  const totalGb = (totalMb / 1024).toFixed(2);
  countEl.textContent = `${state.selectedFindings.size} Vector`;
  spaceEl.textContent = `${totalGb} GB`;

  modal.classList.remove('hidden');
  setTimeout(() => modal.classList.remove('opacity-0'), 10);
}

function closeRemediationModal() {
  const modal = document.getElementById('remediation-modal');
  modal.classList.add('opacity-0');
  setTimeout(() => modal.classList.add('hidden'), 150);
}

async function executeRemediationConfirmed() {
  closeRemediationModal();
  if (state.isRemediating) return;
  state.isRemediating = true;

  const btn = document.getElementById('btn-remediate');
  btn.innerHTML = '<i class="ph-bold ph-spinner animate-spin text-xs"></i><span>Executing...</span>';
  btn.disabled = true;

  const vectorIds = Array.from(state.selectedFindings);
  log(`Menjalankan remediasi pada ${vectorIds.length} vector terpilih...`, 'info');

  try {
    const res = await callApi('/api/execute-remediation', {
      vector_ids: vectorIds,
      serial: state.activeDevice
    });

    state.isRemediating = false;
    btn.innerHTML = '<i class="ph-bold ph-lightning text-xs"></i><span>Execute Remediation</span>';
    btn.disabled = false;

    if (res.success) {
      log(res.message, 'success');
      showToast(`Remediasi sukses: +${res.reclaimed_gb} GB`, 'success');
      setTimeout(runStorageScan, 1500);
    } else {
      log('Eksekusi remediasi mengalami kendala.', 'error');
      showToast('Remediasi belum lengkap', 'error');
    }
  } catch (err) {
    state.isRemediating = false;
    btn.innerHTML = '<i class="ph-bold ph-lightning text-xs"></i><span>Execute Remediation</span>';
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

// ================= IN-APP UPDATE ENGINE =================
async function checkAppUpdate() {
  try {
    const res = await callApi('/api/check-update');
    if (res && res.success && res.update_available) {
      state.updateInfo = res;
      const pillBtn = document.getElementById('btn-update-pill');
      const pillText = document.getElementById('update-pill-text');
      if (pillBtn && pillText) {
        pillText.textContent = `v${res.latest_version} Ready`;
        pillBtn.classList.remove('hidden');
      }
      log(`Pembaruan rilis baru terdeteksi di GitHub: v${res.latest_version} (Saat ini: v${res.current_version})`, 'brand');
    }
  } catch (e) {
    // Silent fail on update check
  }
}

function openUpdateModal() {
  if (!state.updateInfo) return;
  const info = state.updateInfo;
  const modal = document.getElementById('update-modal');
  document.getElementById('update-modal-ver').textContent = `Versi Baru: v${info.latest_version}`;
  document.getElementById('update-modal-notes').textContent = info.release_notes || 'Pembaruan sistem dan perbaikan performa.';
  document.getElementById('update-modal-file').textContent = info.asset_name || 'RinovaPro-Windows-Portable.zip';
  document.getElementById('update-modal-current').textContent = `Current: v${info.current_version}`;
  document.getElementById('update-modal-download-btn').href = info.download_url;

  modal.classList.remove('hidden');
  setTimeout(() => modal.classList.remove('opacity-0'), 10);
}

function closeUpdateModal() {
  const modal = document.getElementById('update-modal');
  modal.classList.add('opacity-0');
  setTimeout(() => modal.classList.add('hidden'), 150);
}

// Initializer
window.addEventListener('DOMContentLoaded', () => {
  log('Rinova Pro Engine v1.0.0 initialized — Lead Architect: Sahal Arbani (@sahal.arbani)', 'brand');
  refreshDeviceList();
  initHeartbeat();
  checkAppUpdate();
});
