 # Kubelingo Usage Guide

 This document provides detailed instructions on installing, configuring, and using Kubelingo, a CLI tool for studying the Certified Kubernetes Application Developer (CKAD) exam.

 ## Table of Contents
 - [Prerequisites](#prerequisites)
 - [Installation](#installation)
   - [From PyPI](#from-pypi)
   - [From Source](#from-source)
 - [Configuration](#configuration)
 - [Running Kubelingo](#running-kubelingo)
   - [Interactive CLI](#interactive-cli)
   - [Command-Line Options](#command-line-options)
 - [Source Management](#source-management)
 - [Testing & Coverage](#testing--coverage)

 ## Prerequisites
 - Python 3.7 or newer (3.11+ recommended)
 - `kubectl` installed and configured in your `PATH`
 - Optional: `vim` (for manifest editing)
 - Optional: API keys for AI feedback (see [Configuration](#configuration))

 ## Installation

 ### From PyPI
 ```bash
 pip install kubelingo
 ```

 ### From Source
 ```bash
 git clone https://github.com/josephedward/kubelingo.git
 cd kubelingo
 pip install -r requirements.txt
 pip install .
 ```

 ## Configuration

 Kubelingo can provide AI-powered feedback and question generation if you supply API keys.
 Create a file named `.env` in the project root with one or both of the following:
 ```dotenv
 GEMINI_API_KEY=<your_google_gemini_key>
 OPENAI_API_KEY=<your_openai_key>
 ```
 The tool will load this file automatically on startup.

 ## Running Kubelingo

 ### Interactive CLI
 Launch the study interface:
 ```bash
 kubelingo
 ```
 1. The ASCII-art logo is displayed.
 2. Select a topic and the number of questions to practice.
3. For **command** questions, type your `kubectl` (or `helm`) command and press Enter. To submit your answer, either press Enter on a blank line or type `done` and press Enter.
 4. For **manifest** questions, Kubelingo will open a temporary file in `vim` (or your default editor).
    - Write or paste your YAML manifest.
    - Save and close the editor to submit.
 5. Review the colored diff, AI feedback (if configured), and performance summary.

 ### Command-Line Options
 Run `kubelingo --help` to see all options:
 ```bash
 Usage: kubelingo [OPTIONS]

Options:
  --add-sources             Add missing sources from a consolidated YAML file
  --consolidated PATH       Path to consolidated YAML (required with --add-sources)
  --check-sources           Check all question files for missing sources
  --interactive-sources     Interactively search and assign sources
  --auto-approve            Auto-approve first result (use with --interactive-sources)
  --help                    Show this message and exit
 ```

 ## Source Management

 - **Check sources**: `kubelingo --check-sources` verifies that each question YAML has a `source` URL.
 - **Interactive sources**: `kubelingo --interactive-sources` lets you search and assign sources using Google or Bing.
 - **Bulk add**: `kubelingo --add-sources --consolidated PATH` automatically inserts missing `source` fields from a consolidated file.

 ## Testing & Coverage

 Run the test suite with pytest:
 ```bash
 pytest
 ```

 Generate a coverage report:
 ```bash
 pip install pytest-cov
 pytest --cov=kubelingo --cov-report=term-missing
 ```

 ## Further Reading
 - [Official CKAD Exam Curriculum](https://github.com/cncf/curriculum/blob/master/exams/ckad/)
 - [Kubernetes Documentation](https://kubernetes.io/docs/)