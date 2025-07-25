import os
import csv
import random
import tempfile
import subprocess
from datetime import datetime

from kubelingo.modules.base.session import StudySession
import json

try:
    import questionary
except ImportError:
    questionary = None

try:
    from colorama import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = ""
    class Style:
        RESET_ALL = ""
import random


class NewSession(StudySession):
    """Session for Killercoda CKAD CSV-based quiz"""

    def __init__(self, logger):
        super().__init__(logger)

    def initialize(self):
        """No special initialization required"""
        return True

    def run_exercises(self, args):  # pylint: disable=unused-argument
        """Run the CSV-based quiz: open each question in Vim for the user to answer"""
        start_time = datetime.now()
        # If a JSON spec file is provided via KILLERCODA_SPEC, use batch mode
        spec_file = os.environ.get('KILLERCODA_SPEC')
        if spec_file:
            # Load questions from JSON spec
            try:
                with open(spec_file, encoding='utf-8') as sf:
                    questions = json.load(sf)
            except Exception as e:
                print(f"{Fore.RED}Error reading spec JSON: {e}{Style.RESET_ALL}")
                return
            total = len(questions)
            if total == 0:
                print(f"{Fore.YELLOW}No questions found in spec file.{Style.RESET_ALL}")
                return
            correct = 0
            print(f"\n{Fore.CYAN}=== Killercoda CKAD Quiz (Batch Mode) ==={Style.RESET_ALL}")
            print(f"Loaded {Fore.CYAN}{total}{Style.RESET_ALL} questions from spec.")
            # Prepare a temporary file containing all questions
            tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
            tmp_path = tmp.name
            tmp.close()
            try:
                with open(tmp_path, 'w', encoding='utf-8') as tf:
                    for idx, q in enumerate(questions, start=1):
                        tf.write(f"# Question {idx}/{total}\n")
                        tf.write("# Instructions:\n")
                        for ln in q['prompt'].splitlines():
                            if ln.strip():
                                tf.write(f"# {ln.strip()}\n")
                        tf.write("\n# Your YAML manifest below:\n")
                        tf.write("---\n\n")
            except Exception as e:
                print(f"{Fore.RED}Error preparing spec quiz file: {e}{Style.RESET_ALL}")
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                return
            print(f"\nEdit the file {tmp_path} with your answers, for example:")
            print(f"  $ $EDITOR {tmp_path}")
            try:
                input("Press ENTER when done...")
            except (EOFError, KeyboardInterrupt):
                print(f"{Fore.YELLOW}Input cancelled. Aborting.{Style.RESET_ALL}")
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                return
            # Read and evaluate answers
            ans_blocks = [[] for _ in range(total)]
            current = -1
            in_answer = False
            try:
                with open(tmp_path, encoding='utf-8') as uf:
                    for line in uf:
                        if line.startswith("# Question"):
                            current += 1
                            in_answer = False
                            continue
                        if line.startswith("# Instructions:"):
                            continue
                        if line.startswith("# Your YAML manifest below:"):
                            in_answer = True
                            continue
                        if in_answer:
                            if line.startswith("---"):
                                continue
                            if line.lstrip().startswith("#"):
                                continue
                            ans_blocks[current].append(line)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            for idx, q in enumerate(questions, start=1):
                user_ans = ''.join(ans_blocks[idx-1]).strip()
                expected = q.get('answer', '')
                print(f"\n{Fore.YELLOW}Question {idx}/{total}:{Style.RESET_ALL} {q['prompt']}")
                if user_ans == expected:
                    correct += 1
                    print(f"{Fore.GREEN}Correct!{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Incorrect.{Style.RESET_ALL}")
                    print(f"{Fore.GREEN}Expected answer:{Style.RESET_ALL}\n{expected}")
                self.logger.info(
                    f"CKAD Spec Quiz {idx}/{total}: prompt=\"{q['prompt']}\" "
                    f"expected=\"{expected}\" answer=\"{user_ans}\" "
                    f"result=\"{'correct' if user_ans==expected else 'incorrect'}\""
                )
            end_time = datetime.now()
            duration = str(end_time - start_time).split('.')[0]
            print(f"\n{Fore.CYAN}=== Quiz Complete ==={Style.RESET_ALL}")
            print(
                f"You got {Fore.GREEN}{correct}{Style.RESET_ALL} out of "
                f"{Fore.YELLOW}{total}{Style.RESET_ALL} correct."
            )
            print(f"Time taken: {Fore.CYAN}{duration}{Style.RESET_ALL}")
            return
        # Locate the CSV file in the project root (override via KILLERCODA_CSV env var)
        default_csv = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), os.pardir, os.pardir, os.pardir,
                'killercoda-ckad_072425.csv'
            )
        )
        csv_file = os.environ.get('KILLERCODA_CSV', default_csv)
        if not os.path.exists(csv_file):
            print(f"{Fore.RED}CSV file not found at {csv_file}{Style.RESET_ALL}")
            return

        # Parse CSV questions: columns: [category, prompt, answer, ...]
        questions = []
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            # Skip header if present
            try:
                first_row = next(reader)
                if 'prompt' in first_row[1].lower():
                    pass # it was a header
                else:
                    reader = iter([first_row] + list(reader))
            except StopIteration:
                pass # empty file
            
            for row in reader:
                if len(row) < 3:
                    continue
                
                category = row[0].strip()
                if category.startswith("'") and category.endswith("'"):
                    category = category[1:-1].strip()

                raw_prompt = row[1].strip()
                if raw_prompt.startswith("'") and raw_prompt.endswith("'"):
                    raw_prompt = raw_prompt[1:-1].strip()
                
                raw_answer = row[2].strip()
                if raw_answer.startswith("'") and raw_answer.endswith("'"):
                    raw_answer = raw_answer[1:-1].strip()
                
                if not raw_prompt or not raw_answer or not category:
                    continue
                
                questions.append({
                    'category': category,
                    'prompt': raw_prompt,
                    'answer': raw_answer
                })
        if not questions:
            print(f"{Fore.YELLOW}No questions found in CSV file.{Style.RESET_ALL}")
            return

        is_interactive = questionary and not args.category and not args.num
        if is_interactive:
            categories = sorted({q['category'] for q in questions if q.get('category')})
            choices = [{'name': "All Questions", 'value': "all"}]
            for category in categories:
                choices.append({'name': f"{category}", 'value': category})

            selected = questionary.select(
                "Choose a category:",
                choices=choices,
                use_indicator=True
            ).ask()

            if selected is None:
                print(f"\n{Fore.YELLOW}Quiz cancelled.{Style.RESET_ALL}")
                return
            
            if selected != 'all':
                args.category = selected

        if args.category:
            questions = [q for q in questions if q.get('category') == args.category]
            if not questions:
                print(Fore.YELLOW + f"No questions found in category '{args.category}'." + Style.RESET_ALL)
                return

        num_to_ask = args.num if args.num and args.num > 0 else len(questions)
        questions_to_ask = random.sample(questions, min(num_to_ask, len(questions)))
        
        total = len(questions_to_ask)
        if total == 0:
            print(f"{Fore.YELLOW}No questions to ask.{Style.RESET_ALL}")
            return
            
        correct = 0
        print(f"\n{Fore.CYAN}=== Killercoda CKAD Quiz ==={Style.RESET_ALL}")
        print(f"Starting quiz with {Fore.CYAN}{total}{Style.RESET_ALL} questions.")

        for idx, q in enumerate(questions_to_ask, start=1):
            print(f"\n{Fore.YELLOW}Question {idx}/{total}:{Style.RESET_ALL} {q['prompt']}")
            # Prepare a temporary file: display full prompt as single-line instruction and a YAML manifest stub
            lines = [line.strip() for line in q['prompt'].splitlines() if line.strip()]
            single_prompt = " ".join(lines)
            tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
            tmp_path = tmp.name
            tmp.close()
            try:
                with open(tmp_path, 'w', encoding='utf-8') as tf:
                    tf.write("# Instructions:\n")
                    tf.write(f"# {single_prompt}\n\n")
                    tf.write("# Your YAML manifest below:\n")
                    tf.write("---\n\n")
            except Exception as e:
                print(f"{Fore.RED}Error preparing quiz file: {e}{Style.RESET_ALL}")
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                return
            # Allow user to edit YAML; retry once on empty answer, skip if still empty
            user_ans = ''
            attempts = 0
            while True:
                # Launch the editor for user to input their answer
                editor = os.environ.get('EDITOR', 'vim')
                cmd = [editor]
                base = os.path.basename(editor)
                if base in ('vim', 'nvim', 'vi'):
                    cmd += ['-c', 'set tabstop=2 shiftwidth=2 expandtab', '--noplugin']
                cmd.append(tmp_path)
                try:
                    subprocess.call(cmd)
                except Exception as e:
                    print(f"{Fore.RED}Error launching editor: {e}{Style.RESET_ALL}")
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    return
                # Read the user's answer, removing template comment lines
                try:
                    with open(tmp_path, encoding='utf-8') as uf:
                        lines_in = uf.readlines()
                    # Filter out template comment lines and stub delimiter
                    ans_lines = []
                    for l in lines_in:
                        if l.lstrip().startswith('#'):
                            continue
                        if l.strip() == '---':
                            continue
                        ans_lines.append(l)
                    user_ans = ''.join(ans_lines).strip()
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                # If non-empty answer or already retried once, break
                if user_ans or attempts >= 1:
                    break
                # Offer retry on empty
                print(f"{Fore.YELLOW}No answer provided.{Style.RESET_ALL}")
                try:
                    resp = input("Press 'r' to retry, ENTER to skip: ")
                except Exception:
                    break
                if resp.strip().lower() != 'r':
                    break
                # Recreate the template for retry
                tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
                tmp_path = tmp.name
                tmp.close()
                with open(tmp_path, 'w', encoding='utf-8') as tf:
                    tf.write("# Instructions:\n")
                    tf.write(f"# {single_prompt}\n\n")
                    tf.write("# Your YAML manifest below:\n---\n\n")
                attempts += 1
            # If still empty, skip this question
            if not user_ans:
                print(f"{Fore.YELLOW}Skipped question.{Style.RESET_ALL}")
                try:
                    input("Press ENTER to continue to next question...")
                except Exception:
                    pass
                continue

            expected = q['answer']
            # Compare strict or normalize quotes
            ua = user_ans.strip()
            ea = expected.strip()
            # Strip all quotes for a relaxed comparison
            ua_norm = ua.replace('"', '').replace("'", '')
            ea_norm = ea.replace('"', '').replace("'", '')
            if ua == ea or ua_norm == ea_norm:
                correct += 1
                print(f"{Fore.GREEN}Correct!{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Incorrect.{Style.RESET_ALL}")
                print(f"{Fore.GREEN}Expected answer:{Style.RESET_ALL}\n{expected}")
            # Pause before moving on
            try:
                input("Press ENTER to continue to next question...")
            except Exception:
                pass

            self.logger.info(
                f"CKAD CSV Quiz {idx}/{total}: prompt=\"{q['prompt']}\" "
                f"expected=\"{expected}\" answer=\"{user_ans}\" "
                f"result=\"{'correct' if user_ans==expected else 'incorrect'}\""
            )

        end_time = datetime.now()
        duration = str(end_time - start_time).split('.')[0]
        print(f"\n{Fore.CYAN}=== Quiz Complete ==={Style.RESET_ALL}")
        print(
            f"You got {Fore.GREEN}{correct}{Style.RESET_ALL} out of "
            f"{Fore.YELLOW}{total}{Style.RESET_ALL} correct."
        )
        print(f"Time taken: {Fore.CYAN}{duration}{Style.RESET_ALL}")

    def cleanup(self):  # pylint: disable=unused-argument
        """No cleanup required for CSV quiz"""
        pass
