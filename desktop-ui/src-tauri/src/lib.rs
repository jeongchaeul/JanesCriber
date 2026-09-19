use std::{
    fs,
    io::{BufRead, BufReader, Write},
    path::{Path, PathBuf},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{Arc, Mutex},
    thread,
};

use serde_json::{json, Value};
use tauri::{Emitter, Manager, State};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

struct BackendProcess {
    child: Arc<Mutex<Child>>,
    stdin: Arc<Mutex<ChildStdin>>,
}

#[derive(Default)]
struct BackendState {
    process: Mutex<Option<BackendProcess>>,
}

fn configure_background_command(command: &mut Command) {
    #[cfg(windows)]
    command.creation_flags(0x08000000);
}

fn source_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
}

fn preference_candidates(app: Option<&tauri::AppHandle>) -> Vec<PathBuf> {
    let mut roots = Vec::new();
    if let Ok(data_dir) = std::env::var("JANESCRIBER_DATA_DIR") {
        roots.push(PathBuf::from(data_dir));
    }
    roots.push(source_root());
    if let Ok(executable) = std::env::current_exe() {
        if let Some(parent) = executable.parent() {
            roots.push(parent.to_path_buf());
        }
    }
    if let Some(app) = app {
        if let Ok(resource) = app.path().resource_dir() {
            roots.push(resource);
        }
    }
    roots.dedup();
    roots.into_iter().map(|root| root.join("frontend.preference")).collect()
}

fn launcher_candidates(app: &tauri::AppHandle) -> Vec<PathBuf> {
    let mut roots = Vec::new();
    roots.push(source_root());
    if let Ok(executable) = std::env::current_exe() {
        if let Some(parent) = executable.parent() {
            roots.push(parent.to_path_buf());
        }
    }
    if let Ok(resource) = app.path().resource_dir() {
        roots.push(resource.clone());
        roots.push(resource.join("JanesCriber"));
    }
    roots.dedup();
    roots.into_iter().map(|root| root.join("JanesCriber.exe")).collect()
}

fn candidate_backend(app: &tauri::AppHandle) -> (PathBuf, Vec<String>, PathBuf) {
    let source = source_root();
    let mut roots = Vec::new();
    if let Ok(resource) = app.path().resource_dir() {
        roots.push(resource);
    }
    if let Ok(executable) = std::env::current_exe() {
        if let Some(parent) = executable.parent() {
            roots.push(parent.to_path_buf());
        }
    }
    roots.push(source.clone());

    for root in &roots {
        let mut relatives = vec![
            "backend/JanesCriberBackend.exe",
            "JanesCriberBackend.exe",
            "backend/JanesCriber.exe",
            "JanesCriber/JanesCriber.exe",
        ];
        // The source checkout's root JanesCriber.exe is the legacy C# launcher,
        // not the backend. Only accept a root-level executable from packaged
        // layouts where it is the PyInstaller service runtime.
        if root != &source {
            relatives.push("JanesCriber.exe");
        }
        for relative in relatives {
            let path = root.join(relative);
            if path.is_file() {
                return (path, vec!["--service".into()], root.clone());
            }
        }
    }

    let python = source.join(".venv").join("Scripts").join("python.exe");
    if python.is_file() {
        return (
            python,
            vec!["-u".into(), "-m".into(), "janescriber".into(), "--service".into()],
            source.clone(),
        );
    }
    (
        PathBuf::from("python"),
        vec!["-u".into(), "-m".into(), "janescriber".into(), "--service".into()],
        source,
    )
}

fn emit_system_log(app: &tauri::AppHandle, message: impl Into<String>) {
    let _ = app.emit(
        "backend-event",
        json!({
            "type": "event",
            "id": "system",
            "event": "log",
            "message": message.into(),
        }),
    );
}

fn ensure_backend(app: &tauri::AppHandle, state: &BackendState) -> Result<BackendProcess, String> {
    let mut slot = state.process.lock().map_err(|_| "Backend state is unavailable.")?;
    if let Some(process) = slot.as_ref() {
        let alive = process
            .child
            .lock()
            .map_err(|_| "Backend process state is unavailable.")?
            .try_wait()
            .map_err(|error| format!("Could not inspect backend process: {error}"))?
            .is_none();
        if alive {
            return Ok(BackendProcess {
                child: process.child.clone(),
                stdin: process.stdin.clone(),
            });
        }
        *slot = None;
    }

    let (program, args, working_directory) = candidate_backend(app);
    let mut command = Command::new(&program);
    configure_background_command(&mut command);
    command
        .args(args)
        .current_dir(&working_directory)
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONPATH", working_directory.join("src"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let mut child = command
        .spawn()
        .map_err(|error| format!("Could not start the local Python engine at {}: {error}", program.display()))?;
    let stdin = child.stdin.take().ok_or_else(|| "The backend did not expose an input stream.".to_owned())?;
    let stdout = child.stdout.take().ok_or_else(|| "The backend did not expose an output stream.".to_owned())?;
    let stderr = child.stderr.take().ok_or_else(|| "The backend did not expose an error stream.".to_owned())?;
    let child = Arc::new(Mutex::new(child));
    let stdin = Arc::new(Mutex::new(stdin));

    let reader_app = app.clone();
    thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            match line {
                Ok(line) if !line.trim().is_empty() => {
                    match serde_json::from_str::<Value>(&line) {
                        Ok(payload) => {
                            let _ = reader_app.emit("backend-event", payload);
                        }
                        Err(_) => emit_system_log(&reader_app, line),
                    }
                }
                Ok(_) => {}
                Err(error) => emit_system_log(&reader_app, format!("Backend output error: {error}")),
            }
        }
        emit_system_log(&reader_app, "The local engine connection closed.");
    });

    let stderr_app = app.clone();
    thread::spawn(move || {
        for line in BufReader::new(stderr).lines() {
            if let Ok(line) = line {
                if !line.trim().is_empty() {
                    emit_system_log(&stderr_app, line);
                }
            }
        }
    });

    let process = BackendProcess { child, stdin };
    *slot = Some(BackendProcess {
        child: process.child.clone(),
        stdin: process.stdin.clone(),
    });
    emit_system_log(app, format!("Local engine connected through {}.", program.display()));
    Ok(process)
}

#[tauri::command]
fn backend_request(
    app: tauri::AppHandle,
    state: State<'_, BackendState>,
    request_id: String,
    operation: String,
    payload: Value,
) -> Result<(), String> {
    let process = ensure_backend(&app, &state)?;
    let body = json!({
        "id": request_id,
        "operation": operation,
        "payload": payload,
    });
    let mut stdin = process.stdin.lock().map_err(|_| "The backend input stream is unavailable.")?;
    writeln!(stdin, "{}", serde_json::to_string(&body).map_err(|error| format!("Could not encode backend request: {error}"))?)
        .map_err(|error| format!("Could not send request to the local engine: {error}"))?;
    stdin.flush().map_err(|error| format!("Could not flush the local engine request: {error}"))?;
    Ok(())
}

#[tauri::command]
fn backend_stop(state: State<'_, BackendState>) -> Result<(), String> {
    let process = state.process.lock().map_err(|_| "Backend state is unavailable.")?.take();
    if let Some(process) = process {
        let mut child = process.child.lock().map_err(|_| "Backend process state is unavailable.")?;
        let _ = child.kill();
        let _ = child.wait();
    }
    Ok(())
}

#[tauri::command]
fn set_frontend_preference(app: tauri::AppHandle, preference: String) -> Result<(), String> {
    if preference != "tauri" && preference != "python" {
        return Err("Unsupported interface preference.".to_owned());
    }
    let mut last_error = None;
    for candidate in preference_candidates(Some(&app)) {
        if let Some(parent) = candidate.parent() {
            if let Err(error) = fs::create_dir_all(parent) {
                last_error = Some(error);
                continue;
            }
        }
        match fs::write(&candidate, format!("{preference}\n")) {
            Ok(()) => return Ok(()),
            Err(error) => last_error = Some(error),
        }
    }
    Err(format!("Could not save the interface preference: {}", last_error.map(|error| error.to_string()).unwrap_or_else(|| "no writable project folder was found".to_owned())))
}

#[tauri::command]
fn relaunch_launcher(app: tauri::AppHandle, state: State<'_, BackendState>) -> Result<(), String> {
    let launcher = launcher_candidates(&app)
        .into_iter()
        .find(|candidate| candidate.is_file())
        .ok_or_else(|| "JanesCriber.exe was not found beside the application.".to_owned())?;
    backend_stop(state)?;
    let working_directory = launcher.parent().unwrap_or_else(|| Path::new("."));
    let mut command = Command::new(&launcher);
    configure_background_command(&mut command);
    command
        .current_dir(working_directory)
        .env("JANESCRIBER_DATA_DIR", working_directory)
        .spawn()
        .map_err(|error| format!("Could not relaunch JanesCriber: {error}"))?;
    app.exit(0);
    Ok(())
}

#[tauri::command]
fn open_path(path: String) -> Result<(), String> {
    let candidate = PathBuf::from(path);
    if !candidate.exists() {
        return Err(format!("Path does not exist: {}", candidate.display()));
    }
    #[cfg(windows)]
    {
        let mut command = Command::new("explorer.exe");
        configure_background_command(&mut command);
        command.arg(candidate).spawn().map_err(|error| format!("Could not open the folder: {error}"))?;
        return Ok(());
    }
    #[cfg(not(windows))]
    {
        Command::new("xdg-open").arg(candidate).spawn().map_err(|error| format!("Could not open the folder: {error}"))?;
        Ok(())
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(BackendState::default())
        .invoke_handler(tauri::generate_handler![backend_request, backend_stop, open_path, set_frontend_preference, relaunch_launcher])
        .build(tauri::generate_context!())
        .expect("error while building JanesCriber Studio")
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                let state = app.state::<BackendState>();
                let _ = backend_stop(state);
            }
        });
}
