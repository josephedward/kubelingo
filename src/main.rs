mod cli;
use clap::Parser;
use crate::cli::{Commands, run_pty_shell};

fn main() {
    let cli = cli::Cli::parse();

    // The logic to handle commands would go here.
    // For now, this is a skeleton.
    if cli.command.is_none() {
        // If no command-line arguments are given, it's assumed the Python wrapper
        // is handling the interactive menu. This binary does nothing in that case.
        return;
    }
    if let Some(command) = cli.command {
        match command {
            Commands::Pty => {
                if let Err(e) = run_pty_shell() {
                    eprintln!("Error launching PTY shell: {}", e);
                    std::process::exit(1);
                }
            }
            Commands::K8s { exercise } => {
                // Kubernetes exercises not yet implemented in Rust
                println!("Kubernetes exercises not yet implemented in Rust CLI.");
            }
            Commands::Kustom { custom_file } => {
                // Custom exercises not yet implemented in Rust
                println!("Custom exercises not yet implemented in Rust CLI.");
            }
        }
        return;
    }
}
