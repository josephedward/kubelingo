import sys

# Interactive prompts library (optional for arrow-key selection)
try:
    import questionary
except ImportError:
    questionary = None

# YAML library (optional for YAML editing features)
try:
    import yaml
except ImportError:
    yaml = None

# Colorama for cross-platform colored terminal text
try:
    from colorama import Fore, Style, init
    init()
except ImportError:
    # Fallback if colorama is not available
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = ""
    class Style:
        RESET_ALL = ""
        DIM = ""

# Disable ANSI color codes when not writing to a real terminal
if not sys.stdout.isatty():
    Fore.RED = Fore.GREEN = Fore.YELLOW = Fore.CYAN = Fore.MAGENTA = ""
    Style.RESET_ALL = ""
    Style.DIM = ""


def humanize_module(name: str) -> str:
    """Turn a module filename into a human-friendly title."""
    # If prefixed with order 'a.', drop prefix
    if '.' in name:
        disp = name.split('.', 1)[1]
    else:
        disp = name
    return disp.replace('_', ' ').title()


ASCII_ART = r"""                                      bbbbbbbb
KKKKKKKKK    KKKKKKK                  b::::::b                                lllllll   iiii
K:::::::K    K:::::K                  b::::::b                                l:::::l  i::::i
K:::::::K    K:::::K                  b::::::b                                l:::::l   iiii
K:::::::K   K::::::K                   b:::::b                                l:::::l
KK::::::K  K:::::KKKuuuuuu    uuuuuu   b:::::bbbbbbbbb        eeeeeeeeeeee     l::::l iiiiiii nnnn  nnnnnnnn       ggggggggg   ggggg   ooooooooooo
  K:::::K K:::::K   u::::u    u::::u   b::::::::::::::bb    ee::::::::::::ee   l::::l i:::::i n:::nn::::::::nn    g:::::::::ggg::::g oo:::::::::::oo
  K::::::K:::::K    u::::u    u::::u   b::::::::::::::::b  e::::::eeeee:::::ee l::::l  i::::i n::::::::::::::nn  g:::::::::::::::::go:::::::::::::::o
  K:::::::::::K     u::::u    u::::u   b:::::bbbbb:::::::be::::::e     e:::::e l::::l  i::::i nn:::::::::::::::ng::::::ggggg::::::ggo:::::ooooo:::::o
  K:::::::::::K     u::::u    u::::u   b:::::b    b::::::be:::::::eeeee::::::e l::::l  i::::i   n:::::nnnn:::::ng:::::g     g:::::g o::::o     o::::o
  K::::::K:::::K    u::::u    u::::u   b:::::b     b:::::be:::::::::::::::::e  l::::l  i::::i   n::::n    n::::ng:::::g     g:::::g o::::o     o::::o
  K:::::K K:::::K   u::::u    u::::u   b:::::b     b:::::be::::::eeeeeeeeeee   l::::l  i::::i   n::::n    n::::ng:::::g     g:::::g o::::o     o::::o
KK::::::K  K:::::KKKu:::::uuuu:::::u   b:::::b     b:::::be:::::::e            l::::l  i::::i   n::::n    n::::ng::::::g    g:::::g o::::o     o::::o
K:::::::K   K::::::Ku:::::::::::::::uu b:::::bbbbbb::::::be::::::::e          l::::::li::::::i  n::::n    n::::ng:::::::ggggg:::::g o:::::ooooo:::::o
K:::::::K    K:::::K u:::::::::::::::u b::::::::::::::::b  e::::::::eeeeeeee  l::::::li::::::i  n::::n    n::::n g::::::::::::::::g o:::::::::::::::o
K:::::::K    K:::::K  uu::::::::uu:::u b:::::::::::::::b    ee:::::::::::::e  l::::::li::::::i  n::::n    n::::n  gg::::::::::::::g  oo:::::::::::oo
KKKKKKKKK    KKKKKKK    uuuuuuuu  uuuu bbbbbbbbbbbbbbbb       eeeeeeeeeeeeee  lllllllliiiiiiii  nnnnnn    nnnnnn    gggggggg::::::g    ooooooooooo
                                                                                                                            g:::::g
                                                                                                                gggggg      g:::::g
                                                                                                                g:::::gg   gg:::::g
                                                                                                                 g::::::ggg:::::::g
                                                                                                                  gg:::::::::::::g
                                                                                                                    ggg::::::ggg
                                                                                                                       gggggg                    """


def print_banner():
    """Prints the Kubelingo ASCII banner."""
    lines = ASCII_ART.strip('\n').splitlines()
    if not lines:
        return

    center_width = max(len(line) for line in lines)

    # Split point to color 'Kube' and 'Lingo' differently.
    # This is an approximation based on the visual structure of the ASCII art.
    split_point = 82

    for line in lines:
        kube_part = line[:split_point]
        lingo_part = line[split_point:]
        print(f"{Fore.CYAN}{kube_part}{Fore.MAGENTA}{lingo_part}{Style.RESET_ALL}")

    subheader = "Kubernetes Studying Tool"

    # Pimp out the subheader with alternating colors for a vibrant look
    colors = [Fore.CYAN, Fore.GREEN, Fore.MAGENTA, Fore.YELLOW]
    pimped_subheader = "".join(
        f"{colors[i % len(colors)]}{char}" for i, char in enumerate(subheader)
    )

    # Center the pimped subheader manually to handle ANSI color codes
    if center_width > len(subheader):
        padding_total = center_width - len(subheader)
        padding_left = padding_total // 2
        print(f"{' ' * padding_left}{pimped_subheader}{Style.RESET_ALL}")
    else:
        print(f"{pimped_subheader}{Style.RESET_ALL}")


def show_session_type_help():
    """Prints an explanation of the PTY and Docker sandbox environments."""
    print(f"""
{Fore.CYAN}--- Sandbox Environments Help ---{Style.RESET_ALL}

Kubelingo offers two types of sandbox environments for exercises:

{Fore.GREEN}1. PTY Shell (Embedded){Style.RESET_ALL}
   - {Fore.YELLOW}How it works:{Style.RESET_ALL} Spawns a native shell process (like 'bash') directly on your system using a pseudo-terminal (PTY). This is the same technology terminal emulators use.
   - {Fore.YELLOW}Pros:{Style.RESET_ALL} Very fast to start, uses your local environment and tools.
   - {Fore.YELLOW}Cons:{Style.RESET_ALL} Not isolated. Commands run as your user with access to your file system and network. Accidental destructive commands can affect your machine.
   - {Fore.YELLOW}Requirements:{Style.RESET_ALL} None. Works out-of-the-box on Linux and macOS.

{Fore.GREEN}2. Docker Container{Style.RESET_ALL}
   - {Fore.YELLOW}How it works:{Style.RESET_ALL} Launches a pre-built Docker container with a fixed set of tools (bash, vim, kubectl). Your current directory is mounted as a workspace.
   - {Fore.YELLOW}Pros:{Style.RESET_ALL} Fully isolated. Cannot affect your host system. Provides a consistent, clean environment for every exercise.
   - {Fore.YELLOW}Cons:{Style.RESET_ALL} Slower to start, especially the first time. Requires Docker to be installed and running.
   - {Fore.YELLOW}Requirements:{Style.RESET_ALL} Docker must be installed and the Docker daemon must be running. (Tip: run 'docker info' to verify your Docker setup.)

{Fore.CYAN}Which one to choose?{Style.RESET_ALL}
- For quick, simple command quizzes, {Fore.GREEN}PTY Shell{Style.RESET_ALL} is fine.
- For complex YAML editing or live cluster exercises, {Fore.GREEN}Docker Container{Style.RESET_ALL} is recommended for safety and consistency.
""")

def show_quiz_type_help():
    """Prints an explanation of the different quiz modes."""
    print(f"""
{Fore.CYAN}--- Quiz Types Help ---{Style.RESET_ALL}

{Fore.GREEN}1. K8s (preinstalled){Style.RESET_ALL}
   - This section contains quizzes and exercises that come bundled with Kubelingo.
   - They are organized into different files based on the topic (e.g., Command Quizzes, YAML Editing, Vim Practice).
   - You will be presented with a list of these files to choose from.

{Fore.GREEN}2. Kustom (upload your own quiz){Style.RESET_ALL}
   - This allows you to run a quiz from your own custom-made JSON file.
   - The JSON file must follow the same format as the built-in quiz files. It should be a list of sections, where each section has a 'category' and a list of 'prompts'.
   - You will be prompted for the path to your file when you select this option.

{Fore.GREEN}3. Review{Style.RESET_ALL}
   - This mode gathers all questions you have previously 'flagged' for review across all K8s quizzes.
   - During a quiz, if you are unsure about a question, you can flag it.
   - Use this mode for a focused session on topics you find difficult.
   - You can clear all flags from the Kubernetes exercise menu.
""")
