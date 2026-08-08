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
const CATALOG_URL: &str = "http://127.0.0.1:8000/api/v1/catalog/full";
const MCP_URL: &str = "http://127.0.0.1:8000/mcp";

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

/// True when the daemon is new enough for the desktop UI (has catalog routes).
fn catalog_ok() -> bool {
    http_get_ok(CATALOG_URL)
}

fn daemon_ready() -> bool {
    health_ok() && catalog_ok()
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

fn default_log_path() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".navbe")
        .join("serve.log")
}

fn resolve_sidecar_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    // Prefer bundled resources (packaged app).
    if let Ok(resource_dir) = app.path().resource_dir() {
        let bundled = resource_dir.join("navbe").join(if cfg!(windows) {
            "navbe.exe"
        } else {
            "navbe"
        });
        if bundled.exists() {
            return Ok(bundled);
        }
    }

    // Dev fallback: use `navbe` from PATH in a checkout.
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

/// Stop an outdated / foreign serve on :8000 so the bundled sidecar can take over.
fn reclaim_port(app: &tauri::AppHandle) {
    // Graceful stop via any available navbe CLI (clears serve.pid).
    if let Ok(bundled) = resolve_sidecar_path(app) {
        let _ = Command::new(&bundled).arg("stop").output();
    }
    if let Ok(path) = which_navbe() {
        let _ = Command::new(&path).arg("stop").output();
    }

    #[cfg(windows)]
    {
        let _ = Command::new("taskkill")
            .args(["/F", "/IM", "navbe.exe", "/T"])
            .output();
    }

    let deadline = Instant::now() + Duration::from_secs(10);
    while Instant::now() < deadline && health_ok() {
        thread::sleep(Duration::from_millis(200));
    }
}

fn spawn_sidecar(app: &tauri::AppHandle, state: &DaemonState) -> Result<(), String> {
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

    // PyInstaller onedir resolves _internal next to the exe; keep cwd there.
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

    // Cold PyInstaller start can be slow; also wait for catalog (not just /health).
    if !wait_until_ready(Duration::from_secs(60)) {
        if let Some(mut child) = state.child.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        return Err(format!(
            "navbe serve did not become ready at {HEALTH_URL} (catalog missing); see {}",
            log_path.display()
        ));
    }
    Ok(())
}

fn ensure_daemon(app: &tauri::AppHandle, state: &DaemonState) {
    // Compatible daemon already up (relaunch is fast).
    if daemon_ready() {
        *state.attached.lock().unwrap() = true;
        *state.error.lock().unwrap() = None;
        *state.log_path.lock().unwrap() = Some(default_log_path().display().to_string());
        *state.booting.lock().unwrap() = false;
        return;
    }

    // Old CLI / incomplete serve on :8000 → reclaim, then start bundled sidecar.
    if health_ok() && !catalog_ok() {
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
            // Keep setup non-blocking: reqwest::blocking on the UI thread can
            // stall/fail window creation on Windows.
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
            if let tauri::WindowEvent::Destroyed = event {
                // Intentionally do not kill the sidecar.
            }
        })
        .invoke_handler(tauri::generate_handler![daemon_status, api_request])
        .run(tauri::generate_context!())
        .expect("error while running Navbe Desktop");
}
