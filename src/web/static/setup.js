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
    var host = document.getElementById("webdav-host").value;
    var username = document.getElementById("webdav-username").value;
    var password = document.getElementById("webdav-password").value;

    result.textContent = "";
    result.className = "test-result";

    if (!host.trim()) {
        showTestResult(result, false, "Enter a host URL first");
        return;
    }

    setLoading(btn, true);

    fetch("/api/setup/test-webdav", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ host: host, username: username, password: password }),
    })
        .then(function (resp) { return resp.json(); })
        .then(function (data) {
            setLoading(btn, false);
            if (data.ok) {
                showTestResult(result, true, "Connected!");
            } else {
                showTestResult(result, false, data.error || "Connection failed");
            }
        })
        .catch(function (err) {
            setLoading(btn, false);
            showTestResult(result, false, "Network error: " + err.message);
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
