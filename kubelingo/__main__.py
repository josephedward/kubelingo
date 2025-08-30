import os
import sys
import argparse
from kubelingo.kubelingo import cli, load_questions, run_topic, _CLI_ANSWER_OVERRIDE, save_performance_data, backup_performance_yaml, load_performance_data, Fore, Style, USER_DATA_DIR

if __name__ == "__main__":
    # Check if any of the special CLI answer arguments are present
    is_cli_answer_mode = any(arg.startswith('--cli-answer') or arg.startswith('--cli-question-topic') or arg.startswith('--cli-question-index') for arg in sys.argv)

    if is_cli_answer_mode:
        parser = argparse.ArgumentParser(description="Kubelingo CLI tool for CKAD exam study.")
        parser.add_argument('--cli-answer', type=str, help='Provide an answer directly for a single question in non-interactive mode.')
        parser.add_argument('--cli-question-topic', type=str, help='Specify the topic for --cli-answer mode.')
        parser.add_argument('--cli-question-index', type=int, help='Specify the 0-based index of the question within the topic for --cli-answer mode.')
        args = parser.parse_args()

        # Mark CLI mode for run_topic to detect piped input
        os.environ['KUBELINGO_CLI_MODE'] = '1'

        if args.cli_answer and args.cli_question_topic is not None and args.cli_question_index is not None:
            # Non-interactive mode for answering a single question
            performance_data, perf_loaded_ok = load_performance_data()
            topic_data = load_questions(args.cli_question_topic, Fore, Style)
            if topic_data and 'questions' in topic_data:
                questions_to_study = [topic_data['questions'][args.cli_question_index]]
                # Temporarily override get_user_input for this specific run
                _CLI_ANSWER_OVERRIDE = args.cli_answer # Set the global override variable
                
                print(f"Processing question from topic '{args.cli_question_topic}' at index {args.cli_question_index} with answer: '{args.cli_answer}'")
                run_topic(args.cli_question_topic, questions_to_study, performance_data)
                if perf_loaded_ok:
                    save_performance_data(performance_data)
                    backup_performance_yaml()
                sys.exit(0) # Exit after processing the single question
            else:
                print(f"Error: Topic '{args.cli_question_topic}' not found or has no questions.", file=sys.stderr)
                sys.exit(1)
        else:
            # If cli-answer mode was intended but arguments are incomplete
            parser.print_help()
            sys.exit(1)
    else:
        # Original interactive CLI mode, let click handle all arguments
        cli()
