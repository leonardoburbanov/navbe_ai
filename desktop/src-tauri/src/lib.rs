#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::Manager;
use tauri::State;

const BASE_URL: &str = "http://127.0.0.1:8000";
const HEALTH_URL: &str = "http://127.0.0.1:8000/health";
const VERSION_URL: &str = "http://127.0.0.1:8000/api/v1/version";
const MCP_URL: &str = "http://127.0.0.1:8000/mcp";
const LISTEN_PORT: u16 = 8000;

struct DaemonState {
    child: Mutex<Option<Child>>,
    attached: Mutex<bool>,
    error: Mutex<Option<String>>,
    log_path: Mutex<Option<String>>,
    /// False until the first ensure_daemon attempt finishes.
    booting: Mutex<bool>,
}

#[derive(Serialize, Clone)]
struct DaemonStatus {
    running: bool,
    attached: bool,
    booting: bool,
    base_url: String,
    mcp_url: String,
    log_path: Option<String>,
    error: Option<String>,
}

#[derive(Serialize)]
struct ApiProxyResponse {
    status: u16,
    body: String,
}

#[derive(serde::Deserialize)]
struct VersionPayload {
    features: Option<Vec<String>>,
}

fn http_get_ok(url: &str) -> bool {
    reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .ok()
        .and_then(|c| c.get(url).send().ok())
        .map(|r| r.status().is_success())
        .unwrap_or(false)
}

fn health_ok() -> bool {
    http_get_ok(HEALTH_URL)
}

/// True when the daemon exposes the features this desktop build needs.
fn version_ok() -> bool {
    let client = match reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
    {
        Ok(c) => c,
        Err(_) => return false,
    };
    let Ok(resp) = client.get(VERSION_URL).send() else {
        return false;
    };
    if !resp.status().is_success() {
        return false;
    }
    let Ok(body) = resp.json::<VersionPayload>() else {
        return false;
    };
    body.features
        .unwrap_or_default()
        .iter()
        .any(|f| f == "catalog")
}

fn daemon_ready() -> bool {
    health_ok() && version_ok()
}

fn wait_until_ready(timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if daemon_ready() {
            return true;
        }
        thread::sleep(Duration::from_millis(250));
    }
    false
}

fn wait_until_unhealthy(timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if !health_ok() {
            return true;
        }
        thread::sleep(Duration::from_millis(200));
    }
    false
}

fn default_log_path() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".navbe")
        .join("serve.log")
}

fn bundled_sidecar_path(app: &tauri::AppHandle) -> Option<PathBuf> {
    let resource_dir = app.path().resource_dir().ok()?;
    let bundled = resource_dir.join("navbe").join(if cfg!(windows) {
        "navbe.exe"
    } else {
        "navbe"
    });
    if bundled.exists() {
        Some(bundled)
    } else {
        None
    }
}

/// Packaged app when the installer-bundled sidecar is present.
fn is_packaged(app: &tauri::AppHandle) -> bool {
    bundled_sidecar_path(app).is_some()
}

fn resolve_sidecar_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    if let Some(bundled) = bundled_sidecar_path(app) {
        return Ok(bundled);
    }

    if let Ok(path) = which_navbe() {
        return Ok(path);
    }

    Err(
        "Bundled navbe sidecar not found. Run scripts/build_sidecar.ps1 \
         or ensure `navbe` is on PATH for development."
            .into(),
    )
}

fn which_navbe() -> Result<PathBuf, String> {
    let candidates = if cfg!(windows) {
        vec!["navbe.exe", "navbe.cmd", "navbe"]
    } else {
        vec!["navbe"]
    };
    for name in candidates {
        if let Ok(output) = Command::new(if cfg!(windows) { "where" } else { "which" })
            .arg(name)
            .output()
        {
            if output.status.success() {
                let text = String::from_utf8_lossy(&output.stdout);
                if let Some(line) = text.lines().next() {
                    let path = PathBuf::from(line.trim());
                    if path.exists() {
                        return Ok(path);
                    }
                }
            }
        }
    }
    Err("navbe not found on PATH".into())
}

/// PIDs listening on TCP LISTEN for ``127.0.0.1:port`` / ``0.0.0.0:port`` (Windows).
#[cfg(windows)]
fn pids_listening_on_port(port: u16) -> Vec<u32> {
    let output = Command::new("netstat")
        .args(["-ano", "-p", "tcp"])
        .output();
    let Ok(output) = output else {
        return Vec::new();
    };
    if !output.status.success() {
        return Vec::new();
    }
    let text = String::from_utf8_lossy(&output.stdout);
    let mut pids = Vec::new();
    let suffixes = [
        format!("127.0.0.1:{port}"),
        format!("0.0.0.0:{port}"),
        format!("[::1]:{port}"),
        format!("[::]:{port}"),
    ];
    for line in text.lines() {
        let line = line.trim();
        if !line.contains("LISTENING") {
            continue;
        }
        let parts: Vec<&str> = line.split_whitespace().collect();
        // Proto  Local  Foreign  State  PID
        if parts.len() < 5 {
            continue;
        }
        let local = parts[1];
        if !suffixes.iter().any(|s| local.eq_ignore_ascii_case(s)) {
            continue;
        }
        if let Ok(pid) = parts[parts.len() - 1].parse::<u32>() {
            if pid > 0 && !pids.contains(&pid) {
                pids.push(pid);
            }
        }
    }
    pids
}

#[cfg(not(windows))]
fn pids_listening_on_port(_port: u16) -> Vec<u32> {
    Vec::new()
}

fn kill_pid(pid: u32) {
    #[cfg(windows)]
    {
        let _ = Command::new("taskkill")
            .args(["/F", "/PID", &pid.to_string(), "/T"])
            .output();
    }
    #[cfg(not(windows))]
    {
        let _ = Command::new("kill").args(["-9", &pid.to_string()]).output();
    }
}

/// Stop anything on :8000 so the bundled/dev sidecar can bind.
fn reclaim_port(app: &tauri::AppHandle) {
    if let Ok(bundled) = resolve_sidecar_path(app) {
        let _ = Command::new(&bundled).arg("stop").output();
    }
    if let Ok(path) = which_navbe() {
        let _ = Command::new(&path).arg("stop").output();
    }

    for pid in pids_listening_on_port(LISTEN_PORT) {
        kill_pid(pid);
    }

    #[cfg(windows)]
    {
        // Last resort: any leftover navbe serve binary.
        let _ = Command::new("taskkill")
            .args(["/F", "/IM", "navbe.exe", "/T"])
            .output();
    }

    let _ = wait_until_unhealthy(Duration::from_secs(10));
}

fn spawn_sidecar(app: &tauri::AppHandle, state: &DaemonState) -> Result<(), String> {
    if health_ok() {
        reclaim_port(app);
        if health_ok() {
            return Err(format!(
                "port {LISTEN_PORT} is still busy after reclaim; stop the other \
                 process (see netstat) or run uninstall stop-all"
            ));
        }
    }

    let exe = resolve_sidecar_path(app)?;
    let log_path = default_log_path();
    if let Some(parent) = log_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let log_file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| format!("failed to open log {}: {e}", log_path.display()))?;
    let log_err = log_file
        .try_clone()
        .map_err(|e| format!("failed to clone log handle: {e}"))?;

    let mut cmd = Command::new(&exe);
    cmd.args(["serve", "--host", "127.0.0.1", "--port", "8000"])
        .stdin(Stdio::null())
        .stdout(Stdio::from(log_file))
        .stderr(Stdio::from(log_err));

    if let Some(dir) = exe.parent() {
        cmd.current_dir(dir);
    }

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        const CREATE_NEW_PROCESS_GROUP: u32 = 0x00000200;
        cmd.creation_flags(CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP);
    }

    let child = cmd
        .spawn()
        .map_err(|e| format!("failed to spawn {}: {e}", exe.display()))?;

    *state.child.lock().unwrap() = Some(child);
    *state.attached.lock().unwrap() = false;
    *state.log_path.lock().unwrap() = Some(log_path.display().to_string());

    if !wait_until_ready(Duration::from_secs(60)) {
        if let Some(mut child) = state.child.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        return Err(format!(
            "navbe serve did not become ready (need /health + /api/v1/version \
             features=[catalog]); see {}",
            log_path.display()
        ));
    }
    Ok(())
}

fn ensure_daemon(app: &tauri::AppHandle, state: &DaemonState) {
    let packaged = is_packaged(app);

    // Packaged desktop always owns the engine — never attach to a random CLI.
    if !packaged && daemon_ready() {
        *state.attached.lock().unwrap() = true;
        *state.error.lock().unwrap() = None;
        *state.log_path.lock().unwrap() = Some(default_log_path().display().to_string());
        *state.booting.lock().unwrap() = false;
        return;
    }

    if packaged && daemon_ready() {
        // Fast relaunch: engine we left running after last close is fine.
        *state.attached.lock().unwrap() = true;
        *state.error.lock().unwrap() = None;
        *state.log_path.lock().unwrap() = Some(default_log_path().display().to_string());
        *state.booting.lock().unwrap() = false;
        return;
    }

    // Stale/foreign or nothing listening → reclaim (if needed) and spawn ours.
    if health_ok() {
        reclaim_port(app);
    }

    match spawn_sidecar(app, state) {
        Ok(()) => {
            *state.error.lock().unwrap() = None;
        }
        Err(err) => {
            *state.error.lock().unwrap() = Some(err);
        }
    }
    *state.booting.lock().unwrap() = false;
}

#[tauri::command]
fn daemon_status(state: State<'_, DaemonState>) -> DaemonStatus {
    let attached = *state.attached.lock().unwrap();
    let booting = *state.booting.lock().unwrap();
    let running = daemon_ready();
    DaemonStatus {
        running,
        attached,
        booting,
        base_url: BASE_URL.into(),
        mcp_url: MCP_URL.into(),
        log_path: state.log_path.lock().unwrap().clone(),
        error: state.error.lock().unwrap().clone(),
    }
}

/// Proxy REST to the local daemon from Rust so the webview never hits CORS.
#[tauri::command]
fn api_request(method: String, path: String, body: Option<String>) -> Result<ApiProxyResponse, String> {
    let path = path.trim();
    if !path.starts_with('/') {
        return Err("path must start with /".into());
    }
    let url = format!("{BASE_URL}{path}");
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(60))
        .build()
        .map_err(|e| format!("http client: {e}"))?;

    let mut builder = match method.to_uppercase().as_str() {
        "GET" => client.get(&url),
        "POST" => client.post(&url),
        "PUT" => client.put(&url),
        "DELETE" => client.delete(&url),
        "PATCH" => client.patch(&url),
        other => return Err(format!("unsupported method {other}")),
    };

    if let Some(payload) = body {
        builder = builder
            .header("Content-Type", "application/json")
            .body(payload);
    }

    let response = builder.send().map_err(|e| format!("request failed: {e}"))?;
    let status = response.status().as_u16();
    let body = response.text().map_err(|e| format!("read body: {e}"))?;
    Ok(ApiProxyResponse { status, body })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(DaemonState {
            child: Mutex::new(None),
            attached: Mutex::new(false),
            error: Mutex::new(None),
            log_path: Mutex::new(None),
            booting: Mutex::new(true),
        })
        .setup(|app| {
            let handle = app.handle().clone();
            thread::spawn(move || {
                let state = handle.state::<DaemonState>();
                ensure_daemon(&handle, &state);
            });
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.set_focus();
            }
            Ok(())
        })
        .on_window_event(|_window, event| {
            // Keep the daemon running after the window closes (faster relaunch).
            // Uninstall hooks stop navbe.exe via resources/stop-all.cmd.
            if let tauri::WindowEvent::Destroyed = event {}
        })
        .invoke_handler(tauri::generate_handler![daemon_status, api_request])
        .run(tauri::generate_context!())
        .expect("error while running Navbe Desktop");
}
