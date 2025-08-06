use clap::{Parser, Subcommand};
use portable_pty::{CommandBuilder, native_pty_system, PtySize};
use anyhow::Context;
use std::io::{self};
use std::env;
use std::process::Command;

#[derive(Parser, Debug)]
#[command(name = "kubelingo")]
#[command(about = "Kubernetes learning CLI")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Option<Commands>,
}

#[derive(Subcommand, Debug)]
pub enum Commands {
    /// Spawn a PTY-based shell with custom prompt
    Pty,
    /// Kubernetes exercises
    K8s {
        #[command(subcommand)]
        exercise: K8sExercise,
    },
    /// Custom exercises
    Kustom {
        #[arg(long)]
        custom_file: Option<String>,
    },
}

#[derive(Subcommand, Debug)]
pub enum K8sExercise {
    /// Command quiz
    Quiz {
        #[arg(short, long)]
        num: Option<usize>,
        #[arg(short, long)]
        category: Option<String>,
    },
}

/// Run a PTY-based shell, with optional transcripting via the `script` utility.
pub fn run_pty_shell() -> anyhow::Result<()> {
    if let Ok(transcript_path) = env::var("KUBELINGO_TRANSCRIPT_FILE") {
        // Use `script` for robust transcripting. This captures everything, including
        // what happens inside editors like vim. It is more reliable than custom PTY handling.
        let mut command = Command::new("script");
        if cfg!(target_os = "macos") {
            // BSD `script` (macOS) syntax: `script -q <file> <command> <args...>`
            command.args(["-q", &transcript_path, "bash", "--login"]);
        } else {
            // GNU `script` syntax: `script -q <file> -c <command>`
            command.args(["-q", &transcript_path, "-c", "bash --login"]);
        }

        if let Ok(mut child) = command.spawn() {
            if child.wait().is_ok() {
                return Ok(());
            }
            // If `wait` fails, fall through.
        }
        // If `script` fails to spawn, fall through to direct PTY spawn.
    }

    // Fallback to direct PTY spawn if transcripting is not requested or `script` failed.
    let pty_system = native_pty_system();
    let pair = pty_system
        .openpty(PtySize {
            rows: 24,
            cols: 80,
            pixel_width: 0,
            pixel_height: 0,
        })
        .context("Failed to open PTY")?;

    let mut cmd = CommandBuilder::new("bash");
    cmd.arg("--login");
    cmd.env("PS1", "(kubelingo-sandbox)$ ");

    let mut child = pair
        .slave
        .spawn_command(cmd)
        .context("Failed to spawn shell")?;
    drop(pair.slave);

    let mut reader = pair
        .master
        .try_clone_reader()
        .context("Failed to clone PTY reader")?;
    let mut writer = pair.master.take_writer().context("Failed to get PTY writer")?;

    // Thread to handle user input -> PTY
    let input_thread = std::thread::spawn(move || {
        let mut stdin = io::stdin();
        io::copy(&mut stdin, &mut writer).ok();
    });

    // Main thread handles PTY output -> stdout
    let mut stdout = io::stdout();
    io::copy(&mut reader, &mut stdout)?;

    child.wait().context("PTY child process failed")?;
    input_thread.join().expect("Input thread panicked");
    Ok(())
}
