 # kubelingo
A simple CLI tool to quiz yourself on `kubectl` commands.  


This project is licensed under the MIT License – see the LICENSE file for details.
 Every Kubernetes practitioner needs to know `kubectl` commands by heart. This tool helps you memorize and practice common `kubectl` operations via an interactive quiz.

 ## Features

 - Categorized questions (Pods, Deployments, Namespaces, etc.)
 - Randomized order
 - Filter by category
 - Specify number of questions
 - Load questions from an external JSON file
 - Optional LLM-based detailed explanations after each question (requires $OPENAI_API_KEY and the 'llm' CLI tool)
 - If $OPENAI_API_KEY is not set, the app will prompt you at startup to enter it (or press Enter to skip and continue without LLM support)
 - Displays elapsed time during the quiz and reports total time taken at completion
 - Persists each session's duration and performance history, viewable with `--history`
 - Each quiz session logs question-by-question results and overall score to a timestamped file under a `logs/` directory

 ## Requirements

 - Python 3.6+

 ## Setup

 1. Clone the repository:

    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

 2. Create a Python virtual environment and install dependencies:

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate        # On Windows: .\\.venv\\Scripts\\activate
    pip install -r requirements.txt
    ```

 3. Ensure the quiz data JSON file exists (you'll be prompted to select one):

    ```bash
    ls *.json
    ```

 4. Make the quiz script executable (optional):

    ```bash
    chmod +x cli_quiz.py
    ```

 ## Usage
 After answering each question, you may be prompted to query an external LLM for a more detailed explanation. Type 'y' when asked to enable this (requires $OPENAI_API_KEY and the 'llm' CLI tool).

 - List available categories:

   ```bash
   python3 cli_quiz.py --list-categories
   ```

 - Start a quiz with all questions:

   ```bash
   python3 cli_quiz.py
   ```

After completing the quiz, the tool displays your total time taken for the session.

 
 - Use a specific JSON file for questions:

   ```bash
   python3 cli_quiz.py -f ckad_quiz_data.json
   ```
  (Or specify another JSON file: `-f <your_file.json>`)

 - Ask 5 questions from a specific category:

   ```bash
   python3 cli_quiz.py -n 5 -c "Pod Management"
   ```
  
 - Show quiz history and performance statistics:

   ```bash
   python3 cli_quiz.py --history
   ```

 ## Custom Data

 Add your own questions by editing `ckad_quiz_data.json` or specifying a different JSON file with the same format:

 ```json
 [
   {
     "category": "Your Category",
     "prompts": [
       {
         "prompt": "Your question here",
         "response": "Your expected answer here"
       }
     ]
   }
 ]
 ```

 ## License

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
