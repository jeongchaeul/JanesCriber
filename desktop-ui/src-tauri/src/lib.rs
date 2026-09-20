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

fn resource_root(app: &tauri::AppHandle) -> PathBuf {
    if let Ok(resource) = std::env::var("JANESCRIBER_RESOURCE_DIR") {
        let resource = PathBuf::from(resource);
        if resource.is_dir() {
            return resource;
        }
    }
    if let Ok(resource) = app.path().resource_dir() {
        return resource;
    }
    if let Ok(executable) = std::env::current_exe() {
        if let Some(parent) = executable.parent() {
            return parent.to_path_buf();
        }
    }
    source_root()
}

fn data_location_path(app: &tauri::AppHandle) -> PathBuf {
    app.path()
        .app_config_dir()
        .unwrap_or_else(|_| source_root().join(".config"))
        .join("data.location")
}

fn data_root(app: &tauri::AppHandle) -> PathBuf {
    if let Ok(data_dir) = std::env::var("JANESCRIBER_DATA_DIR") {
        let data_dir = data_dir.trim();
        if !data_dir.is_empty() {
            return PathBuf::from(data_dir);
        }
    }
    if let Ok(saved) = fs::read_to_string(data_location_path(app)) {
        let saved = saved.trim();
        if !saved.is_empty() {
            return PathBuf::from(saved);
        }
    }
    if cfg!(debug_assertions) {
        source_root()
    } else {
        app.path().app_data_dir().unwrap_or_else(|_| source_root())
    }
}

fn preference_candidates(app: Option<&tauri::AppHandle>) -> Vec<PathBuf> {
    let mut roots = Vec::new();
    if let Some(app) = app {
        roots.push(data_root(app));
    }
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

fn candidate_backend(app: &tauri::AppHandle) -> (PathBuf, Vec<String>, PathBuf) {
    let source = source_root();
    let mut roots = Vec::new();
    roots.push(resource_root(app));
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

fn candidate_legacy_gui(app: &tauri::AppHandle) -> (PathBuf, Vec<String>, PathBuf) {
    let source = source_root();
    let mut roots = vec![resource_root(app)];
    if let Ok(executable) = std::env::current_exe() {
        if let Some(parent) = executable.parent() {
            roots.push(parent.to_path_buf());
        }
    }
    roots.push(source.clone());
    roots.dedup();

    for root in &roots {
        let relatives = if root == &source {
            vec!["JanesCriberBackend.exe", "backend/JanesCriberBackend.exe"]
        } else {
            vec![
                "backend/JanesCriber.exe",
                "JanesCriberBackend.exe",
                "JanesCriber/JanesCriber.exe",
                "JanesCriber.exe",
            ]
        };
        for relative in relatives {
            let path = root.join(relative);
            if path.is_file() {
                return (path, vec!["--gui".into()], root.clone());
            }
        }
    }

    let python = source.join(".venv").join("Scripts").join("python.exe");
    if python.is_file() {
        return (
            python,
            vec!["-u".into(), "-m".into(), "janescriber".into(), "--gui".into()],
            source,
        );
    }
    (
        PathBuf::from("python"),
        vec!["-u".into(), "-m".into(), "janescriber".into(), "--gui".into()],
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
    let data_directory = data_root(app);
    let resource_directory = resource_root(app);
    fs::create_dir_all(&data_directory)
        .map_err(|error| format!("Could not prepare JanesCriber data directory: {error}"))?;
    let mut command = Command::new(&program);
    configure_background_command(&mut command);
    command
        .args(args)
        .current_dir(&working_directory)
        .env("PYTHONUNBUFFERED", "1")
        .env("PYTHONPATH", working_directory.join("src"))
        .env("JANESCRIBER_DATA_DIR", &data_directory)
        .env("JANESCRIBER_RESOURCE_DIR", &resource_directory)
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
fn get_data_directory(app: tauri::AppHandle) -> Result<String, String> {
    let directory = data_root(&app);
    fs::create_dir_all(&directory)
        .map_err(|error| format!("Could not prepare the data directory: {error}"))?;
    Ok(directory.to_string_lossy().into_owned())
}

#[tauri::command]
fn set_data_directory(app: tauri::AppHandle, directory: String) -> Result<String, String> {
    let raw = directory.trim();
    if raw.is_empty() {
        return Err("Choose a data folder first.".to_owned());
    }
    let candidate = PathBuf::from(raw);
    fs::create_dir_all(&candidate)
        .map_err(|error| format!("Could not create the selected data folder: {error}"))?;
    if !candidate.is_dir() {
        return Err("The selected data path is not a folder.".to_owned());
    }
    let resolved = fs::canonicalize(&candidate)
        .map_err(|error| format!("Could not resolve the selected data folder: {error}"))?;
    let location = data_location_path(&app);
    if let Some(parent) = location.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("Could not prepare the settings folder: {error}"))?;
    }
    fs::write(&location, format!("{}\n", resolved.display()))
        .map_err(|error| format!("Could not save the data folder setting: {error}"))?;
    Ok(resolved.to_string_lossy().into_owned())
}

#[tauri::command]
fn relaunch_launcher(app: tauri::AppHandle, state: State<'_, BackendState>) -> Result<(), String> {
    let data_directory = data_root(&app);
    let resource_directory = resource_root(&app);
    let preference = preference_candidates(Some(&app))
        .into_iter()
        .find_map(|candidate| fs::read_to_string(candidate).ok())
        .map(|value| value.trim().to_owned())
        .filter(|value| value == "python" || value == "tauri")
        .unwrap_or_else(|| "tauri".to_owned());
    backend_stop(state)?;
    let (program, args, working_directory) = if preference == "python" {
        candidate_legacy_gui(&app)
    } else {
        let current = std::env::current_exe().map_err(|error| format!("Could not locate JanesCriber Studio: {error}"))?;
        let working_directory = current.parent().unwrap_or_else(|| Path::new(".")).to_path_buf();
        (current, Vec::new(), working_directory)
    };
    let mut command = Command::new(&program);
    configure_background_command(&mut command);
    command
        .current_dir(working_directory)
        .env("JANESCRIBER_DATA_DIR", &data_directory)
        .env("JANESCRIBER_RESOURCE_DIR", &resource_directory)
        .args(args)
        .spawn()
        .map_err(|error| format!("Could not relaunch JanesCriber through {}: {error}", program.display()))?;
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
        .invoke_handler(tauri::generate_handler![backend_request, backend_stop, open_path, set_frontend_preference, get_data_directory, set_data_directory, relaunch_launcher])
        .build(tauri::generate_context!())
        .expect("error while building JanesCriber Studio")
        .run(|app, event| {
            if matches!(event, tauri::RunEvent::Exit) {
                let state = app.state::<BackendState>();
                let _ = backend_stop(state);
            }
        });
}
