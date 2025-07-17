use clap::{Parser, Subcommand};
use dialoguer::{Select, theme::ColorfulTheme};

#[derive(Parser, Debug)]
#[command(name = "kubelingo")]
#[command(about = "Kubernetes learning CLI")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Option<Commands>,
}

#[derive(Subcommand, Debug)]
pub enum Commands {
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

pub fn run_interactive_menu() -> Result<Commands, Box<dyn std::error::Error>> {
    let choices = vec!["k8s", "kustom", "help"];
    
    let selection = Select::with_theme(&ColorfulTheme::default())
        .with_prompt("What would you like to do?")
        .items(&choices)
        .default(0)
        .interact()?;
        
    match choices[selection] {
        "k8s" => {
            let k8s_choices = vec!["Command Quiz", "YAML Exercises", "Vim Quiz"];
            let k8s_selection = Select::with_theme(&ColorfulTheme::default())
                .with_prompt("Select Kubernetes exercise:")
                .items(&k8s_choices)
                .interact()?;
                
            let exercise = match k8s_selection {
                0 => K8sExercise::Quiz { num: None, category: None },
                1 => K8sExercise::Yaml,
                2 => K8sExercise::Vim,
                _ => unreachable!(),
            };
            
            Ok(Commands::K8s { exercise })
        }
        "kustom" => Ok(Commands::Kustom { custom_file: None }),
        _ => std::process::exit(0),
    }
}
