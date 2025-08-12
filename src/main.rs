mod cli;
use anyhow::Result;
use clap::Parser;
use std::env;
use std::io::{self, Write};
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
            Commands::Settings => {
                handle_settings_menu()?;
            }
        }
    } else {
        // Always show a main menu instead of going directly to study mode
        show_main_menu()?;
    }
    Ok(())
}

fn show_main_menu() -> Result<()> {
    loop {
        println!("\nMain Menu:");
        println!("1. Start Study Mode");
        println!("2. Settings");
        println!("3. Exit");

        print!("Choose an option: ");
        io::stdout().flush()?; // Ensure the prompt is displayed immediately
        let mut choice = String::new();
        io::stdin().read_line(&mut choice)?;
        let choice = choice.trim();

        match choice {
            "1" => {
                // Check if GEMINI_API_KEY is set, otherwise prompt the user
                if env::var("GEMINI_API_KEY").is_err() {
                    println!("Study Mode requires a Gemini API key.");
                    println!("Set the GEMINI_API_KEY environment variable to enable it.");
                    println!("You can generate an API key in your Gemini account settings under 'API Keys'.");
                    prompt_for_api_key()?;
                } else {
                    println!("Starting Study Mode...");
                    // Add logic to start study mode here
                }
            }
            "2" => {
                handle_settings_menu()?;
            }
            "3" => {
                println!("Exiting application.");
                break;
            }
            _ => {
                println!("Invalid option. Please try again.");
            }
        }
    }

    Ok(())
}

fn prompt_for_api_key() -> Result<()> {
    print!("Enter your Gemini API key: ");
    io::stdout().flush()?; // Ensure the prompt is displayed immediately
    let mut api_key = String::new();
    io::stdin().read_line(&mut api_key)?;
    let api_key = api_key.trim();

    if !api_key.is_empty() {
        // Save the API key to the environment (or handle it as needed)
        env::set_var("GEMINI_API_KEY", api_key);
        println!("Gemini API key set successfully.");
    } else {
        println!("No API key entered. Study Mode will remain disabled.");
    }

    Ok(())
}

fn handle_settings_menu() -> Result<()> {
    loop {
        println!("\nSettings Menu:");
        println!("1. View Gemini API key");
        println!("2. Set Gemini API key");
        println!("3. Exit");

        print!("Choose an option: ");
        io::stdout().flush()?; // Ensure the prompt is displayed immediately
        let mut choice = String::new();
        io::stdin().read_line(&mut choice)?;
        let choice = choice.trim();

        match choice {
            "1" => {
                match env::var("GEMINI_API_KEY") {
                    Ok(api_key) => println!("Current Gemini API key: {}", api_key),
                    Err(_) => println!("Gemini API key is not set."),
                }
            }
            "2" => {
                prompt_for_api_key()?;
            }
            "3" => {
                println!("Exiting settings menu.");
                break;
            }
            _ => {
                println!("Invalid option. Please try again.");
            }
        }
    }

    Ok(())
}
