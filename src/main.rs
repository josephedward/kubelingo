mod cli;
use anyhow::Result;
use clap::Parser;
use crate::cli::{Cli, Commands};

fn main() -> Result<()> {
    let cli = Cli::parse();

    if let Some(command) = cli.command {
        match command {
            Commands::Pty => {
                cli::run_pty_shell()?;
            }
            Commands::Kustom { .. } => {
                println!("Custom exercises not yet implemented in Rust CLI.");
            }
        }
    } else {
        // It's assumed the Python wrapper handles the interactive menu.
        // This binary can print a help message or do nothing.
        println!("Welcome to Kubelingo (Rust core). Use --help for commands.");
    }
    Ok(())
}
