mod cli;
use anyhow::Result;
use clap::Parser;
use dialoguer::{theme::ColorfulTheme, Select};
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
                    start_study_mode()?;
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

fn start_study_mode() -> Result<()> {
    let topics = vec![
        "Vim",
        "Helm",
        "Kubectl",
        "Kubernetes Resources",
        "Core workloads (Pods, ReplicaSets, Deployments; rollouts/rollbacks)",
        "Pod design patterns (initContainers, sidecars, lifecycle hooks)",
        "Commands, args, and env (ENTRYPOINT/CMD overrides, env/envFrom)",
        "App configuration (ConfigMaps, Secrets, projected & downwardAPI volumes)",
        "Probes & health (liveness, readiness, startup; graceful shutdown)",
        "Resource management (requests/limits, QoS classes, HPA basics)",
        "Jobs & CronJobs (completions, parallelism, backoff, schedules)",
        "Services (ClusterIP/NodePort/LoadBalancer, selectors, headless)",
        "Ingress & HTTP routing (basic rules, paths, service backends)",
        "Networking utilities (DNS in-cluster, port-forward, exec, curl)",
        "Persistence (PVCs, using existing StorageClasses, common volume types)",
        "Observability & troubleshooting (logs, describe/events, kubectl debug/ephemeral containers)",
        "Labels, annotations & selectors (label ops, field selectors, jsonpath)",
        "Imperative vs declarative (—dry-run, create/apply/edit/replace/patch)",
        "Image & registry use (imagePullPolicy, imagePullSecrets, private registries)",
        "Security basics (securityContext, runAsUser/fsGroup, capabilities, readOnlyRootFilesystem)",
        "ServiceAccounts in apps (mounting SA, minimal RBAC needed for app access)",
        "Scheduling hints (nodeSelector, affinity/anti-affinity, tolerations)",
        "Namespaces & contexts (scoping resources, default namespace, context switching)",
        "API discovery & docs (kubectl explain, api-resources, api-versions)",
        "Vim for YAML editing (modes, navigation, editing commands)",
        "Helm for Package Management (charts, releases, repositories)",
        "Advanced Kubectl Usage (jsonpath, patch, custom columns)",
        "Kubernetes API Resources (exploring objects with explain and api-resources)",
    ];

    let selection = Select::with_theme(&ColorfulTheme::default())
        .with_prompt("Select a topic to study:")
        .items(&topics)
        .default(0)
        .interact()?;

    println!("\nYou selected: {}", topics[selection]);
    // Add logic to start the selected study mode here

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
