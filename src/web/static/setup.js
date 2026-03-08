/* OBS Digital Signage — Setup Wizard JS */

function showToast(message, type) {
    var container = document.getElementById("toast-container");
    var toast = document.createElement("div");
    toast.className = "toast toast-" + type;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function () {
        toast.classList.add("toast-out");
        setTimeout(function () { toast.remove(); }, 300);
    }, 4000);
}

function setLoading(btn, loading) {
    if (loading) {
        btn.classList.add("btn-loading");
        btn.disabled = true;
    } else {
        btn.classList.remove("btn-loading");
        btn.disabled = false;
    }
}

function showTestResult(el, ok, message) {
    el.textContent = message;
    el.className = "test-result " + (ok ? "pass" : "fail");
}

function getWebDAVCreds() {
    return {
        host: document.getElementById("webdav-host").value.trim(),
        username: document.getElementById("webdav-username").value.trim(),
        password: document.getElementById("webdav-password").value.trim(),
    };
}

function testOBS() {
    var btn = document.getElementById("btn-test-obs");
    var result = document.getElementById("result-obs");
    var password = document.getElementById("obs-password").value;

    result.textContent = "";
    result.className = "test-result";
    setLoading(btn, true);

    fetch("/api/setup/test-obs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: password }),
    })
        .then(function (resp) { return resp.json(); })
        .then(function (data) {
            setLoading(btn, false);
            if (data.ok) {
                showTestResult(result, true, "Connected! OBS " + data.obs_version);
            } else {
                showTestResult(result, false, data.error || "Connection failed");
            }
        })
        .catch(function (err) {
            setLoading(btn, false);
            showTestResult(result, false, "Network error: " + err.message);
        });
}

function testWebDAV() {
    var btn = document.getElementById("btn-test-webdav");
    var result = document.getElementById("result-webdav");
    var creds = getWebDAVCreds();

    result.textContent = "";
    result.className = "test-result";

    if (!creds.host) {
        showTestResult(result, false, "Enter a host URL first");
        return;
    }

    setLoading(btn, true);

    fetch("/api/setup/test-webdav", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(creds),
    })
        .then(function (resp) { return resp.json(); })
        .then(function (data) {
            setLoading(btn, false);
            if (data.ok) {
                showTestResult(result, true, "Connected!");
                browseRootFolders();
            } else {
                showTestResult(result, false, data.error || "Connection failed");
                document.getElementById("webdav-folders").style.display = "none";
            }
        })
        .catch(function (err) {
            setLoading(btn, false);
            showTestResult(result, false, "Network error: " + err.message);
        });
}

function browseRootFolders() {
    var creds = getWebDAVCreds();
    var section = document.getElementById("webdav-folders");
    var sel = document.getElementById("webdav-root-path");
    sel.innerHTML = '<option value="">Loading...</option>';
    section.style.display = "block";

    fetch("/api/setup/browse-folders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ host: creds.host, username: creds.username, password: creds.password, path: "/" }),
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data.ok || !data.folders || !data.folders.length) {
                sel.innerHTML = '<option value="/">/ (root - no subfolders found)</option>';
                return;
            }
            sel.innerHTML = '<option value="/">/ (root)</option>';
            data.folders.forEach(function (f) {
                var opt = document.createElement("option");
                opt.value = f.path;
                opt.textContent = f.name;
                sel.appendChild(opt);
            });
        })
        .catch(function () {
            sel.innerHTML = '<option value="/">/ (root)</option>';
        });
}

function browseSubfolders() {
    var creds = getWebDAVCreds();
    var rootPath = document.getElementById("webdav-root-path").value;
    var sel = document.getElementById("webdav-default-folder");

    if (!rootPath || rootPath === "/") {
        sel.innerHTML = '<option value="">-- No root folder selected --</option>';
        return;
    }

    sel.innerHTML = '<option value="">Loading...</option>';

    fetch("/api/setup/browse-folders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ host: creds.host, username: creds.username, password: creds.password, path: rootPath }),
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data.ok || !data.folders || !data.folders.length) {
                sel.innerHTML = '<option value="">No subfolders found</option>';
                return;
            }
            sel.innerHTML = '<option value="">-- Select subfolder --</option>';
            data.folders.forEach(function (f) {
                var opt = document.createElement("option");
                opt.value = f.name;
                opt.textContent = f.name;
                sel.appendChild(opt);
            });
        })
        .catch(function () {
            sel.innerHTML = '<option value="">Failed to load subfolders</option>';
        });
}

function saveSetup(e) {
    e.preventDefault();

    var obsPassword = document.getElementById("obs-password").value.trim();
    if (!obsPassword) {
        showToast("OBS Password is required", "error");
        document.getElementById("obs-password").focus();
        return;
    }

    var btn = document.getElementById("btn-save");
    setLoading(btn, true);

    var payload = {
        obs_password: obsPassword,
        webdav_host: document.getElementById("webdav-host").value.trim(),
        webdav_username: document.getElementById("webdav-username").value.trim(),
        webdav_password: document.getElementById("webdav-password").value.trim(),
        webdav_root_path: document.getElementById("webdav-root-path").value || "/",
        default_folder: document.getElementById("webdav-default-folder").value || "",
        timezone: document.getElementById("timezone").value,
    };

    fetch("/api/setup/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
        .then(function (resp) { return resp.json().then(function (data) { return { status: resp.status, data: data }; }); })
        .then(function (result) {
            setLoading(btn, false);
            if (result.status === 200 && result.data.ok) {
                document.getElementById("setup-form").style.display = "none";
                document.querySelector("header").style.display = "none";
                document.getElementById("setup-success").style.display = "block";
            } else {
                showToast(result.data.error || "Save failed", "error");
            }
        })
        .catch(function (err) {
            setLoading(btn, false);
            showToast("Network error: " + err.message, "error");
        });
}

/* Wire up event listeners */
document.getElementById("btn-test-obs").addEventListener("click", testOBS);
document.getElementById("btn-test-webdav").addEventListener("click", testWebDAV);
document.getElementById("setup-form").addEventListener("submit", saveSetup);
document.getElementById("webdav-root-path").addEventListener("change", browseSubfolders);
