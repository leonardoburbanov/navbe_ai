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

fn health_ok() -> bool {
    reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(1))
        .build()
        .ok()
        .and_then(|c| c.get(HEALTH_URL).send().ok())
        .map(|r| r.status().is_success())
        .unwrap_or(false)
}

fn wait_until_healthy(timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if health_ok() {
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

    // Cold PyInstaller start can exceed 30s on first launch.
    if !wait_until_healthy(Duration::from_secs(60)) {
        if let Some(mut child) = state.child.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        return Err(format!(
            "navbe serve did not become healthy at {HEALTH_URL}; see {}",
            log_path.display()
        ));
    }
    Ok(())
}

fn ensure_daemon(app: &tauri::AppHandle, state: &DaemonState) {
    if health_ok() {
        *state.attached.lock().unwrap() = true;
        *state.error.lock().unwrap() = None;
        *state.log_path.lock().unwrap() = Some(default_log_path().display().to_string());
        *state.booting.lock().unwrap() = false;
        return;
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
    let running = health_ok();
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
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                let state = window.state::<DaemonState>();
                let attached = *state.attached.lock().unwrap();
                if attached {
                    return;
                }
                let mut child_slot = state.child.lock().unwrap();
                if let Some(mut child) = child_slot.take() {
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![daemon_status, api_request])
        .run(tauri::generate_context!())
        .expect("error while running Navbe Desktop");
}
