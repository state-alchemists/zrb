import re

from prompt_toolkit.lexers import Lexer


class CLIStyleLexer(Lexer):
    def lex_document(self, document):
        def get_line(lineno):
            line = document.lines[lineno]
            tokens = []

            # Regex to find ANSI escape sequences
            ansi_escape = re.compile(r"\x1B\[[0-9;]*[mK]")

            last_end = 0
            current_style = ""

            for match in ansi_escape.finditer(line):
                start, end = match.span()

                # Add text before the escape sequence with current style
                if start > last_end:
                    tokens.append((current_style, line[last_end:start]))

                # Parse the escape sequence to update style
                sequence = match.group()
                if sequence == "\x1b[0m":
                    current_style = ""  # Reset
                else:
                    # Simple mapping for common colors/styles used in zrb
                    # This is a basic implementation and might need expansion
                    if "1" in sequence:
                        current_style += "bold "
                    if "2" in sequence:
                        current_style += "class:faint "
                    if "3" in sequence:
                        current_style += "italic "  # Italic is 3 in zrb style
                    if "30" in sequence:
                        current_style += "#000000 "
                    if "31" in sequence:
                        current_style += "#ff0000 "
                    if "32" in sequence:
                        current_style += "#00ff00 "
                    if "33" in sequence:
                        current_style += "#ffff00 "
                    if "34" in sequence:
                        current_style += "#0000ff "
                    if "35" in sequence:
                        current_style += "#ff00ff "
                    if "36" in sequence:
                        current_style += "#00ffff "
                    if "37" in sequence:
                        current_style += "#ffffff "
                    # Bright colors
                    if "90" in sequence:
                        current_style += "#555555 "
                    if "91" in sequence:
                        current_style += "#ff5555 "
                    if "92" in sequence:
                        current_style += "#55ff55 "
                    if "93" in sequence:
                        current_style += "#ffff55 "
                    if "94" in sequence:
                        current_style += "#5555ff "
                    if "95" in sequence:
                        current_style += "#ff55ff "
                    if "96" in sequence:
                        current_style += "#55ffff "
                    if "97" in sequence:
                        current_style += "#ffffff "

                last_end = end

            # Add remaining text
            if last_end < len(line):
                tokens.append((current_style, line[last_end:]))

            return tokens

        return get_line
