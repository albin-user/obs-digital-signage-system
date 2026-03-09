// OBS Digital Signage - Admin Panel JavaScript

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

// In-memory schedule cache for event delegation lookups
let _schedules = [];

// Active schedule name from status polling
let _activeScheduleName = "";

// Connection lost tracking
let _statusFailCount = 0;

// Unsaved changes tracking
let _formDirty = false;

// -- Toast notifications --

function showToast(message, type) {
    type = type || "success";
    var container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.className = "toast-container";
        document.body.appendChild(container);
    }
    var toast = document.createElement("div");
    toast.className = "toast toast-" + type;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function() {
        toast.classList.add("toast-out");
        toast.addEventListener("animationend", function() {
            toast.remove();
        });
    }, 4000);
}

// -- Button loading state --

function setLoading(btn, loading) {
    if (!btn) return;
    if (loading) {
        btn.classList.add("btn-loading");
        btn.disabled = true;
    } else {
        btn.classList.remove("btn-loading");
        btn.disabled = false;
    }
}

// -- Status polling --

function refreshStatus() {
    fetch("/api/status")
        .then(r => r.json())
        .then(data => {
            _statusFailCount = 0;
            var banner = document.getElementById("connection-lost");
            if (banner) banner.style.display = "none";

            const obsEl = document.getElementById("obs-status");
            if (data.obs_connected) {
                obsEl.textContent = "Connected";
                obsEl.className = "status-value connected";
            } else {
                obsEl.textContent = "Disconnected";
                obsEl.className = "status-value disconnected";
            }
            document.getElementById("playing-status").textContent = data.current_playing || "--";
            document.getElementById("schedule-status").textContent = data.active_schedule || "--";
            document.getElementById("sync-status").textContent = data.last_sync || "--";
            document.getElementById("uptime-status").textContent = data.uptime || "--";
            var countEl = document.getElementById("media-count");
            if (countEl) countEl.textContent = data.media_count != null ? data.media_count : "--";

            // Track active schedule and re-render if it changed
            var newActive = data.active_schedule || "";
            if (newActive !== _activeScheduleName) {
                _activeScheduleName = newActive;
                renderScheduleList(_schedules);
                renderDefaultBadge();
            }
        })
        .catch(() => {
            _statusFailCount++;
            if (_statusFailCount >= 2) {
                var banner = document.getElementById("connection-lost");
                if (banner) banner.style.display = "block";
            }
            document.getElementById("obs-status").textContent = "Error";
            document.getElementById("obs-status").className = "status-value disconnected";
        });
}

// -- Schedule rendering --

function loadSchedules() {
    fetch("/api/schedules")
        .then(r => r.json())
        .then(data => {
            _schedules = data.schedules || [];
            renderScheduleList(_schedules);
            renderDefault(data.default_schedule || {});
        })
        .catch(err => console.error("Failed to load schedules:", err));
    checkConflicts();
}

function renderScheduleList(schedules) {
    const container = document.getElementById("schedule-list");
    if (schedules.length === 0) {
        container.innerHTML = '<p style="color:var(--text-muted);font-size:0.85rem;margin-bottom:12px;">No custom schedules yet. Click "+ Add Schedule" to create one.</p>';
        return;
    }
    container.innerHTML = schedules.map(s => {
        const typeInfo = s.type === "recurring"
            ? `Recurring: Every ${DAYS[s.day_of_week] || "?"}`
            : `One-time: ${s.date || "?"}`;
        const isLive = s.name === _activeScheduleName;
        const liveBadge = isLive ? '<span class="badge badge-live">LIVE</span>' : '';
        const toggleChecked = s.enabled ? "checked" : "";
        const toggleText = s.enabled ? "Enabled" : "Disabled";
        const folder = s.folder || "--";
        return `
        <div class="schedule-card${isLive ? ' schedule-active' : ''}">
            <div class="card-header">
                <h3>${esc(s.name)} ${liveBadge}</h3>
                <label class="card-toggle">
                    <input type="checkbox" ${toggleChecked} data-action="toggle" data-id="${esc(s.id)}">
                    <span class="toggle-track"><span class="toggle-thumb"></span></span>
                    ${toggleText}
                </label>
            </div>
            <div class="card-details">
                <span>${typeInfo}</span>
                <span>Time: ${s.start_time} - ${s.end_time}</span><br>
                <span>Folder: ${esc(folder)}</span><br>
                <span>Transition: ${esc(s.transition)} (${s.transition_offset}s offset)</span>
                <span>Images: ${s.image_display_time}s each</span>
                <span>Volume: ${s.audio_volume}%</span>
            </div>
            <div class="card-actions">
                <button class="btn btn-small" data-action="edit" data-id="${esc(s.id)}">Edit</button>
                <button class="btn btn-small btn-danger" data-action="delete" data-id="${esc(s.id)}">Delete</button>
            </div>
        </div>`;
    }).join("");
}

function renderDefault(def) {
    const el = document.getElementById("default-details");
    el.innerHTML = `
        <span>Folder: ${esc(def.folder || "--")}</span><br>
        <span>Transition: ${esc(def.transition || "Fade")} (${def.transition_offset || 0.5}s offset)</span>
        <span>Images: ${def.image_display_time || 15}s each</span>
        <span>Volume: ${def.audio_volume || 80}%</span>
    `;
    renderDefaultBadge();
}

function renderDefaultBadge() {
    var card = document.getElementById("default-schedule");
    var header = card ? card.querySelector(".card-header") : null;
    if (!header) return;
    // Remove existing live badge if any
    var existing = header.querySelector(".badge-live");
    if (existing) existing.remove();
    var isDefaultLive = _activeScheduleName === "Default" || _activeScheduleName === "default";
    // Toggle accent border
    if (card) card.classList.toggle("schedule-active", isDefaultLive);
    // Add LIVE badge if default is the active schedule
    if (isDefaultLive) {
        var badge = document.createElement("span");
        badge.className = "badge badge-live";
        badge.textContent = "LIVE";
        header.querySelector("h3").appendChild(document.createTextNode(" "));
        header.querySelector("h3").appendChild(badge);
    }
}

// -- Conflict checking --

function checkConflicts() {
    fetch("/api/schedules/conflicts")
        .then(r => r.json())
        .then(conflicts => {
            const el = document.getElementById("conflict-alerts");
            if (!conflicts.length) {
                el.innerHTML = "";
                return;
            }
            el.innerHTML = conflicts.map(c => {
                const cls = c.type === "error" ? "alert-error" : "alert-warning";
                return `<div class="alert ${cls}">${esc(c.message)}</div>`;
            }).join("") + '<p class="conflict-priority">Priority: one-time events &gt; recurring schedules &gt; default</p>';
        })
        .catch(err => console.error("Failed to check conflicts:", err));
}

// -- Modal management --

let editingDefault = false;

function openModal(schedule) {
    editingDefault = false;
    document.getElementById("modal-title").textContent = schedule ? "Edit Schedule" : "Add Schedule";
    document.getElementById("edit-id").value = schedule ? schedule.id : "";

    if (schedule) {
        document.getElementById("f-name").value = schedule.name || "";
        document.querySelector(`input[name="type"][value="${schedule.type}"]`).checked = true;
        document.getElementById("f-day").value = schedule.day_of_week ?? 6;
        document.getElementById("f-date").value = schedule.date || "";
        document.getElementById("f-start").value = schedule.start_time || "08:00";
        document.getElementById("f-end").value = schedule.end_time || "13:30";
        setFolderValue(schedule.folder || "");
        document.getElementById("f-transition").value = schedule.transition || "Fade";
        document.getElementById("f-offset").value = schedule.transition_offset ?? 2.0;
        document.getElementById("f-imgtime").value = schedule.image_display_time ?? 15;
        document.getElementById("f-volume").value = schedule.audio_volume ?? 80;
        document.getElementById("f-enabled").checked = schedule.enabled !== false;
    } else {
        document.getElementById("schedule-form").reset();
        document.getElementById("f-day").value = 6;
        document.getElementById("f-volume").value = 80;
    }

    document.getElementById("advanced-settings").removeAttribute("open");
    document.getElementById("folder-preview").style.display = "none";
    hideNewFolderInput();
    clearTimeError();
    toggleType();
    updateVolumeDisplay();
    _formDirty = false;
    var overlay = document.getElementById("modal-overlay");
    overlay.classList.remove("closing");
    overlay.classList.add("active");
    overlay.style.display = "flex";
    loadFolders();
    setTimeout(function() { document.getElementById("f-name").focus(); }, 50);
}

function editDefault() {
    fetch("/api/schedules")
        .then(r => r.json())
        .then(data => {
            const def = data.default_schedule || {};
            editingDefault = true;
            document.getElementById("modal-title").textContent = "Edit Default Schedule";
            document.getElementById("edit-id").value = "default";
            document.getElementById("f-name").value = "Default";
            document.getElementById("f-name").disabled = true;

            // Hide type/day/date/time/enabled fields for default
            document.querySelectorAll("#group-day, #group-date").forEach(el => el.style.display = "none");
            document.querySelector(".radio-group").closest(".form-group").style.display = "none";
            document.querySelectorAll("#f-start, #f-end").forEach(el => el.closest(".form-group").style.display = "none");
            document.getElementById("f-enabled").closest(".form-group").style.display = "none";

            setFolderValue(def.folder || "");
            document.getElementById("f-transition").value = def.transition || "Fade";
            document.getElementById("f-offset").value = def.transition_offset ?? 0.5;
            document.getElementById("f-imgtime").value = def.image_display_time ?? 15;
            document.getElementById("f-volume").value = def.audio_volume ?? 80;

            document.getElementById("advanced-settings").setAttribute("open", "");
            document.getElementById("folder-preview").style.display = "none";
            hideNewFolderInput();
            clearTimeError();
            updateVolumeDisplay();
            _formDirty = false;
            var overlay = document.getElementById("modal-overlay");
            overlay.classList.remove("closing");
            overlay.classList.add("active");
            overlay.style.display = "flex";
            loadFolders();
            setTimeout(function() { document.getElementById("f-folder").focus(); }, 50);
        })
        .catch(err => showToast("Failed to load default schedule: " + err.message, "error"));
}

function closeModal() {
    if (_formDirty) {
        showConfirm("Discard unsaved changes?").then(function(ok) {
            if (ok) {
                _formDirty = false;
                _doCloseModal();
            }
        });
        return;
    }
    _doCloseModal();
}

function _doCloseModal() {
    var overlay = document.getElementById("modal-overlay");
    overlay.classList.add("closing");
    setTimeout(function() {
        overlay.style.display = "none";
        overlay.classList.remove("active", "closing");
    }, 150);

    document.getElementById("f-name").disabled = false;
    document.getElementById("folder-preview").style.display = "none";
    hideNewFolderInput();
    clearTimeError();
    editingDefault = false;

    // Restore hidden fields
    document.querySelectorAll("#group-day, #group-date").forEach(el => el.style.display = "");
    document.querySelector(".radio-group").closest(".form-group").style.display = "";
    document.querySelectorAll("#f-start, #f-end").forEach(el => el.closest(".form-group").style.display = "");
    document.getElementById("f-enabled").closest(".form-group").style.display = "";
    toggleType();
}

function closeModalOverlay(e) {
    if (e.target === document.getElementById("modal-overlay")) closeModal();
}

function toggleType() {
    const type = document.querySelector('input[name="type"]:checked').value;
    document.getElementById("group-day").style.display = type === "recurring" ? "" : "none";
    document.getElementById("group-date").style.display = type === "one-time" ? "" : "none";
}

function updateVolumeDisplay() {
    document.getElementById("volume-display").textContent = document.getElementById("f-volume").value + "%";
}

// -- Folder loading --

function loadFolders() {
    var sel = document.getElementById("f-folder");
    var current = sel.value;
    sel.innerHTML = '<option value="">Loading folders\u2026</option>';
    sel.disabled = true;

    fetch("/api/folders")
        .then(function(r) { return r.json(); })
        .then(function(folders) {
            if (!folders.length) {
                sel.innerHTML = '<option value="">No folders found</option>';
                return;
            }
            sel.innerHTML = '<option value="">-- Select folder --</option>';
            folders.forEach(function(f) {
                var opt = document.createElement("option");
                opt.value = f.path;
                opt.textContent = f.path;
                sel.appendChild(opt);
            });
            if (current) sel.value = current;
        })
        .catch(function() {
            sel.innerHTML = '<option value="">Failed to load folders</option>';
        })
        .finally(function() {
            sel.disabled = false;
        });
}

function setFolderValue(folder) {
    document.getElementById("f-folder").value = folder;
    document.getElementById("f-folder-manual").value = folder;
}

function getFolderValue() {
    const manual = document.getElementById("f-folder-manual").value.trim();
    if (manual) return manual;
    return document.getElementById("f-folder").value;
}

// -- New folder creation --

function showNewFolderInput() {
    var container = document.getElementById("new-folder-container");
    if (container) {
        container.style.display = "flex";
        var input = container.querySelector("input[type='text']");
        if (input) { input.value = ""; input.focus(); }
        return;
    }
    // Build the row dynamically
    var folderGroup = document.getElementById("f-folder").closest(".form-group");
    container = document.createElement("div");
    container.id = "new-folder-container";
    container.className = "new-folder-row";
    container.innerHTML =
        '<input type="text" placeholder="Folder name" id="new-folder-name">' +
        '<button type="button" class="btn btn-primary" id="btn-create-folder">Create</button>' +
        '<button type="button" class="btn" id="btn-cancel-folder">Cancel</button>';
    // Insert after the folder select
    var preview = document.getElementById("folder-preview");
    folderGroup.insertBefore(container, preview);

    document.getElementById("btn-create-folder").addEventListener("click", createFolder);
    document.getElementById("btn-cancel-folder").addEventListener("click", hideNewFolderInput);
    document.getElementById("new-folder-name").focus();
}

function hideNewFolderInput() {
    var container = document.getElementById("new-folder-container");
    if (container) container.style.display = "none";
}

function createFolder() {
    var nameInput = document.getElementById("new-folder-name");
    var name = (nameInput.value || "").trim();
    if (!name) {
        showToast("Enter a folder name", "error");
        nameInput.focus();
        return;
    }

    var btn = document.getElementById("btn-create-folder");
    setLoading(btn, true);

    // Parent is currently "/" (root relative to WEBDAV_ROOT_PATH)
    fetch("/api/folders", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ path: "/", name: name }),
    })
    .then(function(r) {
        if (!r.ok) return r.json().then(function(d) { throw new Error(d.error || "Create failed"); });
        return r.json();
    })
    .then(function() {
        showToast("Folder created: " + name);
        hideNewFolderInput();
        // Reload folders and auto-select the new one
        var sel = document.getElementById("f-folder");
        sel.innerHTML = '<option value="">Loading folders\u2026</option>';
        fetch("/api/folders")
            .then(function(r) { return r.json(); })
            .then(function(folders) {
                sel.innerHTML = '<option value="">-- Select folder --</option>';
                folders.forEach(function(f) {
                    var opt = document.createElement("option");
                    opt.value = f.path;
                    opt.textContent = f.path;
                    sel.appendChild(opt);
                });
                // Auto-select the newly created folder
                sel.value = name;
                previewFolder(name);
            });
    })
    .catch(function(err) {
        showToast("Failed to create folder: " + err.message, "error");
    })
    .finally(function() {
        setLoading(btn, false);
    });
}

// -- Toggle schedule enabled/disabled --

function toggleSchedule(id, checkbox) {
    fetch("/api/schedules/" + id + "/toggle", { method: "PATCH" })
        .then(function(r) {
            if (!r.ok) return r.json().then(function(d) { throw new Error(d.error || "Toggle failed"); });
            return r.json();
        })
        .then(function(updated) {
            // Update the cached schedule
            for (var i = 0; i < _schedules.length; i++) {
                if (_schedules[i].id === id) {
                    _schedules[i].enabled = updated.enabled;
                    break;
                }
            }
            renderScheduleList(_schedules);
            showToast(updated.name + " " + (updated.enabled ? "enabled" : "disabled"));
        })
        .catch(function(err) {
            // Revert checkbox on error
            checkbox.checked = !checkbox.checked;
            showToast(err.message, "error");
        });
}

// -- CRUD operations --

function saveSchedule(e) {
    e.preventDefault();
    var submitBtn = e.target.querySelector('button[type="submit"]');

    if (editingDefault) {
        const data = {
            folder: getFolderValue(),
            transition: document.getElementById("f-transition").value,
            transition_offset: parseFloat(document.getElementById("f-offset").value),
            image_display_time: parseInt(document.getElementById("f-imgtime").value),
            audio_volume: parseInt(document.getElementById("f-volume").value),
        };
        setLoading(submitBtn, true);
        fetch("/api/schedules/default", {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(data),
        })
        .then(r => {
            if (!r.ok) return r.json().then(d => { throw new Error(d.error || "Save failed"); });
            var isLive = _activeScheduleName === "Default" || _activeScheduleName === "default";
            _formDirty = false;
            closeModal();
            loadSchedules();
            showToast("Default schedule saved");
            if (isLive) {
                setTimeout(function() { showToast("Live settings applied", "success"); }, 10000);
            }
        })
        .catch(err => showToast("Failed to save default schedule: " + err.message, "error"))
        .finally(() => setLoading(submitBtn, false));
        return;
    }

    const type = document.querySelector('input[name="type"]:checked').value;
    const data = {
        name: document.getElementById("f-name").value,
        type: type,
        folder: getFolderValue(),
        transition: document.getElementById("f-transition").value,
        transition_offset: parseFloat(document.getElementById("f-offset").value),
        image_display_time: parseInt(document.getElementById("f-imgtime").value),
        audio_volume: parseInt(document.getElementById("f-volume").value),
        start_time: document.getElementById("f-start").value,
        end_time: document.getElementById("f-end").value,
        enabled: document.getElementById("f-enabled").checked,
    };

    if (type === "recurring") {
        data.day_of_week = parseInt(document.getElementById("f-day").value);
    } else {
        data.date = document.getElementById("f-date").value;
    }

    // Client-side time validation
    if (data.start_time && data.end_time && data.end_time <= data.start_time) {
        document.getElementById("time-error").textContent = "End time must be after start time";
        return;
    }
    clearTimeError();

    const editId = document.getElementById("edit-id").value;
    const method = editId ? "PUT" : "POST";
    const url = editId ? `/api/schedules/${editId}` : "/api/schedules";

    setLoading(submitBtn, true);
    fetch(url, {
        method,
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(data),
    })
    .then(r => {
        if (!r.ok) return r.json().then(d => { throw new Error(d.error || "Save failed"); });
        return r.json();
    })
    .then(() => {
        var isLive = data.name === _activeScheduleName;
        _formDirty = false;
        closeModal();
        loadSchedules();
        showToast("Schedule saved");
        if (isLive) {
            setTimeout(function() { showToast("Live settings applied", "success"); }, 10000);
        }
    })
    .catch(err => showToast(err.message, "error"))
    .finally(() => setLoading(submitBtn, false));
}

function editSchedule(id) {
    // Use cached schedules to avoid extra fetch; fall back to API if cache is empty
    const cached = _schedules.find(s => s.id === id);
    if (cached) {
        openModal(cached);
        return;
    }
    fetch("/api/schedules")
        .then(r => r.json())
        .then(data => {
            const schedule = (data.schedules || []).find(s => s.id === id);
            if (schedule) openModal(schedule);
        })
        .catch(err => showToast("Failed to load schedule: " + err.message, "error"));
}

function deleteSchedule(id, name, btn) {
    showConfirm('Delete schedule "' + name + '"?').then(function(ok) {
        if (!ok) return;
        setLoading(btn, true);
        fetch("/api/schedules/" + id, {method: "DELETE"})
            .then(function() {
                loadSchedules();
                showToast("Schedule deleted");
            })
            .catch(function(err) { showToast("Delete failed: " + err.message, "error"); })
            .finally(function() { setLoading(btn, false); });
    });
}

// -- Confirm dialog --

function showConfirm(message) {
    return new Promise(function(resolve) {
        var overlay = document.getElementById("confirm-overlay");
        document.getElementById("confirm-message").textContent = message;
        overlay.style.display = "flex";

        function cleanup(result) {
            overlay.style.display = "none";
            document.getElementById("confirm-ok").removeEventListener("click", onOk);
            document.getElementById("confirm-cancel").removeEventListener("click", onCancel);
            overlay.removeEventListener("click", onBg);
            resolve(result);
        }
        function onOk() { cleanup(true); }
        function onCancel() { cleanup(false); }
        function onBg(e) { if (e.target === overlay) cleanup(false); }

        document.getElementById("confirm-ok").addEventListener("click", onOk);
        document.getElementById("confirm-cancel").addEventListener("click", onCancel);
        overlay.addEventListener("click", onBg);
    });
}

// -- Folder preview --

function previewFolder(folder) {
    var box = document.getElementById("folder-preview");
    if (!folder) {
        box.style.display = "none";
        return;
    }
    box.style.display = "block";
    box.innerHTML = "Loading\u2026";

    fetch("/api/folders/files/" + encodeURIComponent(folder))
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data.files || !data.files.length) {
                box.innerHTML = "<em>No media files in this folder</em>";
                return;
            }
            var images = data.files.filter(function(f) { return f.type === "image"; }).length;
            var videos = data.files.filter(function(f) { return f.type === "video"; }).length;
            var summary = data.files.length + " files";
            if (images || videos) {
                var parts = [];
                if (images) parts.push(images + " image" + (images !== 1 ? "s" : ""));
                if (videos) parts.push(videos + " video" + (videos !== 1 ? "s" : ""));
                summary += " (" + parts.join(", ") + ")";
            }
            var shown = data.files.slice(0, 10);
            var html = '<div class="preview-summary">' + esc(summary) + '</div>';
            html += '<ul class="preview-files">';
            shown.forEach(function(f) { html += "<li>" + esc(f.name) + "</li>"; });
            if (data.files.length > 10) html += "<li>\u2026 and " + (data.files.length - 10) + " more</li>";
            html += "</ul>";
            box.innerHTML = html;
        })
        .catch(function() {
            box.innerHTML = "<em>Could not load folder contents</em>";
        });
}

// -- Time validation --

function clearTimeError() {
    var el = document.getElementById("time-error");
    if (el) el.textContent = "";
}

// -- Helpers --

function esc(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML.replace(/'/g, "&#39;");
}

// -- Init --

document.getElementById("f-volume").addEventListener("input", updateVolumeDisplay);

// Dirty tracking for unsaved changes warning
document.getElementById("schedule-form").addEventListener("input", function() { _formDirty = true; });
document.getElementById("schedule-form").addEventListener("change", function() { _formDirty = true; });

// Clear time error on input
document.getElementById("f-start").addEventListener("input", clearTimeError);
document.getElementById("f-end").addEventListener("input", clearTimeError);

// Header buttons
document.getElementById("btn-add").addEventListener("click", function() { openModal(); });
document.getElementById("btn-edit-default").addEventListener("click", editDefault);
document.getElementById("btn-new-folder").addEventListener("click", showNewFolderInput);

// Sync Now button
document.getElementById("btn-sync").addEventListener("click", function() {
    var btn = this;
    setLoading(btn, true);
    fetch("/api/sync/trigger", {method: "POST"})
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, "error");
            } else if (data.changes) {
                showToast("Sync complete - new content found");
            } else {
                showToast("Sync complete - no changes");
            }
            refreshStatus();
        })
        .catch(err => showToast("Sync failed: " + err.message, "error"))
        .finally(() => setLoading(btn, false));
});

// ESC key closes confirm dialog or modal
document.addEventListener("keydown", function(e) {
    if (e.key === "Escape") {
        var confirmOverlay = document.getElementById("confirm-overlay");
        if (confirmOverlay && confirmOverlay.style.display !== "none") {
            document.getElementById("confirm-cancel").click();
            return;
        }
        var overlay = document.getElementById("modal-overlay");
        if (overlay && overlay.style.display !== "none") {
            closeModal();
        }
    }
});

// Folder preview on selection change
document.getElementById("f-folder").addEventListener("change", function() {
    previewFolder(this.value);
});
document.getElementById("f-folder-manual").addEventListener("blur", function() {
    previewFolder(this.value.trim());
});

// Event delegation for schedule card buttons and toggles
document.getElementById("schedule-list").addEventListener("click", function(e) {
    // Handle toggle switches
    var toggle = e.target.closest("[data-action='toggle']");
    if (toggle) {
        e.stopPropagation();
        toggleSchedule(toggle.getAttribute("data-id"), toggle);
        return;
    }
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const action = btn.getAttribute("data-action");
    const id = btn.getAttribute("data-id");
    if (action === "edit") {
        editSchedule(id);
    } else if (action === "delete") {
        const schedule = _schedules.find(s => s.id === id);
        const name = schedule ? schedule.name : id;
        deleteSchedule(id, name, btn);
    }
});

refreshStatus();
loadSchedules();
setInterval(refreshStatus, 5000);
setInterval(checkConflicts, 30000);
