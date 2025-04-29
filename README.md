 # kubectl-quiz
A simple CLI tool to quiz yourself on `kubectl` commands.  


This project is licensed under the MIT License – see the LICENSE file for details.
 Every Kubernetes practitioner needs to know `kubectl` commands by heart. This tool helps you memorize and practice common `kubectl` operations via an interactive quiz.

 ## Features

 - Categorized questions (Pods, Deployments, Namespaces, etc.)
 - Randomized order
 - Filter by category
 - Specify number of questions
 - Load questions from an external JSON file

 ## Requirements

 - Python 3.6+

 ## Setup

 1. Clone the repository:

    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

 2. Ensure the quiz data JSON file exists:

    ```bash
    ls quiz_data.json
    ```

 3. Make the quiz script executable (optional):

    ```bash
    chmod +x kubectl_quiz.py
    ```

 ## Usage

 - List available categories:

   ```bash
   python3 kubectl_quiz.py --list-categories
   ```

 - Start a quiz with all questions:

   ```bash
   python3 kubectl_quiz.py
   ```

 - Use a specific JSON file for questions:

   ```bash
   python3 kubectl_quiz.py -f quiz_data.json
   ```

 - Ask 5 questions from a specific category:

   ```bash
   python3 kubectl_quiz.py -n 5 -c "Pod Management"
   ```

 ## Custom Data

 Add your own questions by editing `quiz_data.json` or specifying a different JSON file with the same format:

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