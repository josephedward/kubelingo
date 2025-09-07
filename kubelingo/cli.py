#!/usr/bin/env python3
"""
CLI entry point for Kubelingo application.
Displays the main menu as per requirements.md specifications.
"""
import sys

# ASCII art banner for Kubelingo (disabled for now)
ASCII_ART = r"""
                                        bbbbbbb
KKKKKKKKK    KKKKKKK                    b:::::b                                  lllllll   iiii
K:::::::K    K:::::K                    b:::::b                                  l:::::l  i::::i
K:::::::K    K:::::K                    b:::::b                                  l:::::l   iiii
K:::::::K   K::::::K                    b:::::b                                  l:::::l
KK::::::K  K:::::KKK uuuuuu    uuuuuu   b:::::bbbbbbbbb         eeeeeeeeeeee     l:::::l  iiiiii  nnnn  nnnnnnnn      ggggggggg   gggg   ooooooooooo
  K:::::K K:::::K    u::::u    u::::u   b::::::::::::::bb     ee::::::::::::ee   l:::::l  i::::i  n::nn::::::::nn    g:::::::::ggg:::g oo:::::::::::oo
  K::::::K:::::K     u::::u    u::::u   b::::::::::::::::b   e::::::eeeee:::::ee l:::::l  i::::i  n:::::::::::::nn  g::::::::::::::::g o:::::::::::::::o
  K:::::::::::K      u::::u    u::::u   b:::::bbbbb:::::::b e::::::e     e:::::e l:::::l  i:::::i  n::::::::::::::n g::::::ggggg::::::g go:::::ooooo::::o
  K:::::::::::K      u::::u    u::::u   b:::::b    b::::::b e:::::::eeeee::::::e l:::::l  i:::::i  n:::::nnnn:::::n g:::::g     g:::::g o::::o     o::::o
  K::::::K:::::K     u::::u    u::::u   b:::::b     b:::::b e:::::::::::::::::e  l:::::l  i:::::i  n::::n    n::::n g:::::g     g:::::g o::::o     o::::o
  K:::::K K:::::K    u::::u    u::::u   b:::::b     b:::::b e::::::eeeeeeeeeee   l:::::l  i:::::i  n::::n    n::::n g:::::g     g:::::g o::::o     o::::o
KK::::::K  K:::::KKK u:::::uuuu:::::u   b:::::b     b:::::b e:::::::e            l:::::l i:::::i  n::::n    n::::n g::::::g    g:::::g o:::::ooooo:::::o
K:::::::K   K::::::K u:::::::::::::::uu b:::::bbbbbb::::::b e::::::::e           l:::::l i:::::i  n::::n    n::::n g:::::::ggggg:::::g o:::::ooooo:::::o
K:::::::K    K:::::K  u:::::::::::::::u b:::::::::::::::b     ee:::::::::::::e   l:::::l i:::::i  n::::n    n::::n  g::::::::::::::::g o:::::::::::::::o
K:::::::K    K:::::K   uu::::::::uu:::u b:::::::::::::::b     ee:::::::::::::e   l:::::l i:::::i  n::::n    n::::n   gg::::::::::::::g  oo:::::::::::oo
KKKKKKKKK    KKKKKKK     uuuuuuuu  uuuu bbbbbbbbbbbbbbbb        eeeeeeeeeeeeee   lllllll iiiiiii  nnnnnn    nnnnnn     gggggggg::::::g    ooooooooooo
                                                                                                                               g:::::g
                                                                                                                   gggggg      g:::::g
                                                                                                                   g:::::gg   gg:::::g
                                                                                                                    g::::::ggg:::::::g
                                                                                                                     gg:::::::::::::g
                                                                                                                       ggg::::::ggg
                                                                                                                          gggggg
"""

def colorize_ascii_art(art: str) -> str:
    """Apply any color/styling to the ASCII art (no-op placeholder)."""
    return art

def main() -> None:
    """Display the main menu."""
    # Banner disabled
    # print(colorize_ascii_art(ASCII_ART))
    print("- Main Menu")
    print("  + quiz")
    print("  + import")
    print("  + settings")

if __name__ == "__main__":
    main()