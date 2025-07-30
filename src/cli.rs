use clap::{Parser, Subcommand};
use portable_pty::{CommandBuilder, native_pty_system, PtySize};
use anyhow::Context;
use std::io::{self, Read, Write};
use std::fs::File;
use std::env;
use tempfile::NamedTempFile;

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

/// Run a PTY-based shell with custom PS1 prompt and optional transcripting.
pub fn run_pty_shell() -> anyhow::Result<()> {
    // Check for environment variables to enable transcripting
    let transcript_file_path = env::var("KUBELINGO_TRANSCRIPT_FILE").ok();
    let vim_log_path = env::var("KUBELINGO_VIM_LOG").ok();

    let mut transcript_file = transcript_file_path
        .map(|path| File::create(path).expect("Failed to create transcript file"));

    // Create a temporary rcfile to alias vim for command logging
    let mut rc_file = NamedTempFile::new().context("Failed to create temp rcfile")?;
    if let Some(log_path) = &vim_log_path {
        writeln!(rc_file, "alias vim='vim -W {}'", log_path)
            .context("Failed to write vim alias to rcfile")?;
    }

    let pty_system = native_pty_system();
    let pair = pty_system
        .openpty(PtySize { rows: 24, cols: 80, pixel_width: 0, pixel_height: 0 })
        .context("Failed to open PTY")?;
    
    let mut cmd = CommandBuilder::new("bash");
    cmd.env("PS1", "(kubelingo-sandbox)$ ");
    cmd.arg("--rcfile");
    cmd.arg(rc_file.path());

    let mut child = pair.slave.spawn_command(cmd).context("Failed to spawn shell")?;
    drop(pair.slave);

    let mut reader = pair.master.try_clone_reader().context("Failed to clone PTY reader")?;
    let mut writer = pair.master.take_writer().context("Failed to get PTY writer")?;

    let mut transcript_writer_for_input = transcript_file.as_ref().map(|f| f.try_clone().unwrap());

    // Thread to handle user input -> PTY (and transcript)
    let input_thread = std::thread::spawn(move || {
        let mut stdin = io::stdin();
        let mut buffer = [0u8; 1024];
        loop {
            match stdin.read(&mut buffer) {
                Ok(0) => break,
                Ok(n) => {
                    let data = &buffer[..n];
                    if writer.write_all(data).is_err() { break; }
                    if let Some(transcript) = transcript_writer_for_input.as_mut() {
                        let _ = transcript.write_all(data);
                    }
                }
                Err(_) => break,
            }
        }
    });

    // Main thread handles PTY output -> stdout (and transcript)
    let mut stdout = io::stdout();
    let mut buffer = [0u8; 1024];
    loop {
        match reader.read(&mut buffer) {
            Ok(0) => break,
            Ok(n) => {
                let data = &buffer[..n];
                if stdout.write_all(data).is_err() { break; }
                let _ = stdout.flush();
                if let Some(transcript) = transcript_file.as_mut() {
                    let _ = transcript.write_all(data);
                }
            }
            Err(_) => break,
        }
    }

    child.wait().context("PTY child process failed")?;
    input_thread.join().expect("Input thread panicked");
    Ok(())
}
