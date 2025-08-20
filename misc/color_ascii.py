import sys
from colorama import Fore, Style, init

init() # Initialize Colorama

ascii_art = r'''                                      bbbbbbbb
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
KK::::::K  K:::::KKKu:::::uuuu:::::u   b:::::b     b:::::be::::::eeeeeeeeeee   l::::l  i::::i   n::::n    n::::ng:::::g     g:::::g o::::o     o::::o
K:::::::K   K::::::Ku:::::::::::::::uu b:::::bbbbbb::::::be:::::::e            l::::l  i::::i   n::::n    n::::ng::::::g    g:::::g o:::::ooooo:::::o
K:::::::K    K:::::K u:::::::::::::::u b::::::::::::::::b  e::::::::eeeeeeee  l::::::li::::::i  n::::n    n::::n g::::::::::::::::g o:::::::::::::::o
K:::::::K    K:::::K  uu::::::::uu:::u b:::::::::::::::b    ee:::::::::::::e  l::::::li::::::i  n::::n    n::::n  gg::::::::::::::g  oo:::::::::::oo
KKKKKKKKK    KKKKKKK    uuuuuuuu  uuuu bbbbbbbbbbbbbbbb       eeeeeeeeeeeeee  lllllllliiiiiiii  nnnnnn    nnnnnn    gggggggg::::::g    ooooooooooo
                                                                                                                            g:::::g
                                                                                                                gggggg      g:::::g
                                                                                                                g:::::gg   gg:::::g
                                                                                                                 g::::::ggg:::::::g
                                                                                                                  gg:::::::::::::g
                                                                                                                    ggg::::::ggg
                                                                                                                       gggggg                    
'''

colors = [
    Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.BLUE, Fore.MAGENTA
]

lines = ascii_art.split('\n')
num_lines = len(lines)

for i, line in enumerate(lines):
    # Calculate color index based on line number to create a vertical gradient
    color_index = int((i / (num_lines - 1)) * (len(colors) - 1)) if num_lines > 1 else 0
    sys.stdout.write(colors[color_index] + line + Style.RESET_ALL + '\n')
sys.stdout.flush()
