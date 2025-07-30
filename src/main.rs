mod cli;
use anyhow::Result;
use clap::Parser;
use crate::cli::{Cli, Commands, K8sExercise};

fn main() -> Result<()> {
    let cli = Cli::parse();

    if let Some(command) = cli.command {
        match command {
            Commands::Pty => {
                cli::run_pty_shell()?;
            }
            Commands::K8s { exercise } => {
                run_k8s_exercise(exercise)?;
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

fn run_k8s_exercise(exercise: K8sExercise) -> Result<()> {
    match exercise {
        K8sExercise::Quiz { num, category } => {
            println!("Running K8s quiz...");
            if let Some(n) = num {
                println!("- Number of questions: {}", n);
            }
            if let Some(c) = category {
                println!("- Category: {}", c);
            }
            // TODO: Implement quiz logic here
        }
    }
    Ok(())
}
