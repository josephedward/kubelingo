# Kubelingo Usage Guide

This document provides detailed instructions on installing, configuring, and using Kubelingo, a CLI tool for studying for the Certified Kubernetes Application Developer (CKAD) exam.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Setting API Keys](#setting-api-keys)
  - [Selecting an AI Provider](#selecting-an-ai-provider)
- [Running Kubelingo](#running-kubelingo)
  - [Main Menu](#main-menu)
  - [Quiz Menu](#quiz-menu)
    - [Trivia Quiz](#trivia-quiz)
    - [Command Quiz](#command-quiz)
    - [Manifest Quiz](#manifest-quiz)
  - [Post-Answer Menu](#post-answer-menu)
  - [Review Menu](#review-menu)
  - [Import Menu](#import-menu)
- [Command-Line Arguments](#command-line-arguments)
- [Strengths and Limitations](#strengths-and-limitations)
  - [Strengths](#strengths)
  - [Limitations](#limitations)
- [Testing](#testing)

## Overview

Kubelingo is an interactive command-line tool designed to help you prepare for the CKAD exam. It offers various quiz formats, AI-powered grading and feedback, and tools for managing study questions.

## Prerequisites
- Python 3.8 or newer
- `pip` for installation
- An active internet connection for AI features
- Optional: A preferred text editor for manifest questions (defaults to `vim`)

## Installation

You can install Kubelingo directly from the source code:

```bash
git clone https://github.com/josephedward/kubelingo.git
cd kubelingo
pip install -r requirements.txt
```

## Configuration

Kubelingo can leverage AI models from different providers for question generation, grading, and feedback. To use these features, you need to configure API keys.

### Setting API Keys

You can set API keys through the interactive "Settings" menu in the CLI.

1.  Run `python cli.py` and select "Settings".
2.  Choose the API key you want to set (Gemini, OpenAI, or OpenRouter).
3.  Enter your API key when prompted.

The keys are stored in a `.env` file in the project root.

### Selecting an AI Provider

In the "Settings" menu, you can also choose which AI provider to use for AI-powered features. The available options are:

-   `openrouter`
-   `gemini`
-   `openai`
-   `none` (disables AI features)

## Running Kubelingo

To start the interactive CLI, run:

```bash
python cli.py
```

### Main Menu

The main menu provides the following options:

-   **Quiz**: Start a quiz session.
-   **Review**: Review previously answered questions and get AI feedback.
-   **Import**: Import new questions from various sources.
-   **Settings**: Configure API keys and select an AI provider.
-   **Exit**: Exit the application.

### Quiz Menu

The "Quiz" menu allows you to choose from three types of quizzes:

-   **Trivia**: Answer questions about Kubernetes concepts.
-   **Command**: Write `kubectl` commands to solve problems.
-   **Manifest**: Write Kubernetes YAML manifests.

After selecting a quiz type, you'll be prompted to choose a topic.

#### Trivia Quiz

In a Trivia quiz, you are given a description of a Kubernetes resource and asked to name it.

#### Command Quiz

In a Command quiz, you are given a scenario and asked to provide the `kubectl` command to address it. A suggested command is often provided for guidance.

#### Manifest Quiz

In a Manifest quiz, you are given a task and your default text editor opens for you to write the corresponding Kubernetes manifest. Saving and closing the file submits your answer for grading.

### Post-Answer Menu

After answering a question, the post-answer menu appears with the following options:

-   **Again**: Retry the same question.
-   **Correct**: Mark the question as correct.
-   **Missed**: Mark the question as missed.
-   **Remove**: Move the question to a "triage" directory for later review.

### Review Menu

The "Review" menu helps you learn from your past answers. You can choose to review "Correct" or "Incorrect" answers. The tool will then use AI to provide feedback on your performance, highlighting strengths for correct answers and areas for improvement for incorrect ones.

### Import Menu

The "Import" menu allows you to add new questions to your study sessions:

-   **Uncategorized**: Review and save recently generated but unsaved questions.
-   **From URL**: Generate a question from the content of a URL.
-   **From File Path**: Generate a question from a local file.

## Command-Line Arguments

While Kubelingo is primarily an interactive tool, it supports a few command-line arguments for specific actions:

-   `python cli.py generate-question`: Interactively generate a single manifest question.
-   `python cli.py answer-question`: Alias for `generate-question`.
-   `python cli.py generate-manifest`: Interactively generate a manifest from a prompt.

## Strengths and Limitations

### Strengths

-   **Interactive Learning**: The CLI provides an engaging, hands-on learning experience.
-   **Multiple Quiz Formats**: Quizzes for concepts, commands, and manifests cover different aspects of the CKAD exam.
-   **AI-Powered Feedback**: Get detailed feedback on your answers to understand your mistakes and improve.
-   **Flexible Configuration**: Supports multiple AI providers and allows for easy configuration.
-   **Extensible**: You can add your own questions by importing them from files or URLs.

### Limitations

-   **No True "Back" Navigation**: In some quiz modes, "backward" functionality is not implemented, and selecting it may result in a new question being generated.
-   **AI Dependency**: The quality of grading and feedback is dependent on the performance of the configured AI model. Without an AI provider, grading is based on simple string matching against a suggested answer.
-   **Basic UI**: As a text-based CLI, the user interface is simple and may not be as intuitive as a graphical interface.

## Testing

To run the test suite, use `pytest`:

```bash
pytest
```