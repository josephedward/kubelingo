use clap::{Parser, Subcommand};
use portable_pty::{CommandBuilder, native_pty_system, PtySize};
use anyhow::Context;
use std::io::{self, Read, Write};

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
    /// YAML editing exercises
    Yaml,
    /// Vim commands quiz
    Vim,
}

/// Run a PTY-based shell with custom PS1 prompt.
pub fn run_pty_shell() -> anyhow::Result<()> {
    let pty_system = native_pty_system();
    let pair = pty_system
        .openpty(PtySize { rows: 24, cols: 80, pixel_width: 0, pixel_height: 0 })
        .context("Failed to open PTY")?;
    let mut cmd = CommandBuilder::new("bash");
    cmd.env("PS1", "(kubelingo-sandbox)$ ");
    let mut child = pair.slave.spawn_command(cmd).context("Failed to spawn shell")?;
    drop(pair.slave);
    let mut reader = pair.master.try_clone_reader().context("Failed to clone PTY reader")?;
    let mut writer = pair.master.take_writer().context("Failed to get PTY writer")?;
    let mut stdin = io::stdin();
    let mut stdout = io::stdout();
    let input_thread = std::thread::spawn(move || {
        let _ = io::copy(&mut stdin, &mut writer);
    });
    io::copy(&mut reader, &mut stdout).context("Failed to copy PTY output to stdout")?;
    child.wait().context("PTY child process failed")?;
    input_thread.join().expect("Input thread panicked");
    Ok(())
}
