# Kubelingo

[![CI Status](https://github.com/josephedward/kubelingo/actions/workflows/ci.yml/badge.svg)](https://github.com/josephedward/kubelingo/actions/workflows/ci.yml)


## CKAD Studying Tool




Kubelingo is a command-line interface (CLI) tool designed to help you study for the Certified Kubernetes Application Developer (CKAD) exam. It provides interactive questions and scenarios to test your knowledge of Kubernetes concepts and `kubectl` commands.

## Features

*   **Interactive Quizzes:** Test your knowledge with a variety of Kubernetes-related questions.
*   **Scenario-Based Learning:** Practice common `kubectl` operations in simulated environments.
*   **Comprehensive Coverage:** Questions cover key CKAD exam topics.
*   **User-Friendly Interface:** Simple and intuitive CLI for an efficient study experience.

## Installation

Kubelingo can be installed directly from PyPI using `pip`:

```bash
pip install kubelingo
```

## Usage

Once installed, you can run Kubelingo from your terminal:

```bash
kubelingo
```

## Managing Question Sources

You can manage `source` fields directly via the `kubelingo` CLI using the following options:

### Add sources from a consolidated file
```bash
kubelingo --add-sources --consolidated /path/to/consolidated_questions.yaml
```

### Check for missing sources
```bash
kubelingo --check-sources
```

### Interactively find and assign sources
```bash
kubelingo --interactive-sources
```

### Auto-approve first search result
```bash
kubelingo --interactive-sources --auto-approve
```

Follow the on-screen prompts to navigate through the questions and scenarios.

## Contributing

Contributions are welcome! If you have suggestions for new questions, features, or improvements, please feel free to open an issue or submit a pull request on the [GitHub repository](https://github.com/josephedward/kubelingo).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
  
## Demo

[![asciicast](https://asciinema.org/a/HUZGlo91A8SfUPplgiPeQUDxJ.svg)](https://asciinema.org/a/HUZGlo91A8SfUPplgiPeQUDxJ)



