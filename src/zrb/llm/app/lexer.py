import re

from prompt_toolkit.lexers import Lexer


class CLIStyleLexer(Lexer):
    def lex_document(self, document):
        lines = document.lines
        line_tokens = {}  # Cache for tokens per line

        # Global state for the document
        current_attrs = set()
        current_fg = ""
        current_bg = ""

        # Pre-process all lines to handle state across newlines
        # Regex to find ANSI escape sequences (CSI)
        ansi_escape = re.compile(r"\x1B\[([0-9;]*)m")

        for lineno, line in enumerate(lines):
            tokens = []
            last_end = 0

            def build_style():
                parts = list(current_attrs)
                if current_fg:
                    parts.append(current_fg)
                if current_bg:
                    parts.append(current_bg)
                return " ".join(parts)

            for match in ansi_escape.finditer(line):
                start, end = match.span()

                # Add text before the escape sequence with current style
                if start > last_end:
                    tokens.append((build_style(), line[last_end:start]))

                # Parse codes
                codes = match.group(1).split(";")
                if not codes or codes == [""]:
                    codes = ["0"]

                # Convert to integers
                int_codes = []
                for c in codes:
                    if c.isdigit():
                        int_codes.append(int(c))

                i = 0
                while i < len(int_codes):
                    c = int_codes[i]
                    i += 1

                    if c == 0:
                        current_attrs.clear()
                        current_fg = ""
                        current_bg = ""
                    elif c == 1:
                        current_attrs.add("bold")
                    elif c == 2:
                        current_attrs.add("class:faint")
                    elif c == 3:
                        current_attrs.add("italic")
                    elif c == 4:
                        current_attrs.add("underline")
                    elif c == 22:
                        current_attrs.discard("bold")
                        current_attrs.discard("class:faint")
                    elif c == 23:
                        current_attrs.discard("italic")
                    elif c == 24:
                        current_attrs.discard("underline")
                    elif 30 <= c <= 37:
                        colors = [
                            "#000000",
                            "#ff0000",
                            "#00ff00",
                            "#ffff00",
                            "#0000ff",
                            "#ff00ff",
                            "#00ffff",
                            "#ffffff",
                        ]
                        current_fg = colors[c - 30]
                    elif c == 38:
                        if i < len(int_codes):
                            mode = int_codes[i]
                            i += 1
                            if mode == 5 and i < len(int_codes):
                                i += 1  # Skip 256 color
                            elif mode == 2 and i + 2 < len(int_codes):
                                r, g, b = (
                                    int_codes[i],
                                    int_codes[i + 1],
                                    int_codes[i + 2],
                                )
                                i += 3
                                current_fg = f"#{r:02x}{g:02x}{b:02x}"
                    elif c == 39:
                        current_fg = ""
                    elif 40 <= c <= 47:
                        colors = [
                            "#000000",
                            "#ff0000",
                            "#00ff00",
                            "#ffff00",
                            "#0000ff",
                            "#ff00ff",
                            "#00ffff",
                            "#ffffff",
                        ]
                        current_bg = f"bg:{colors[c - 40]}"
                    elif c == 48:
                        if i < len(int_codes):
                            mode = int_codes[i]
                            i += 1
                            if mode == 5 and i < len(int_codes):
                                i += 1
                            elif mode == 2 and i + 2 < len(int_codes):
                                r, g, b = (
                                    int_codes[i],
                                    int_codes[i + 1],
                                    int_codes[i + 2],
                                )
                                i += 3
                                current_bg = f"bg:#{r:02x}{g:02x}{b:02x}"
                    elif c == 49:
                        current_bg = ""
                    elif 90 <= c <= 97:
                        colors = [
                            "#555555",
                            "#ff5555",
                            "#55ff55",
                            "#ffff55",
                            "#5555ff",
                            "#ff55ff",
                            "#55ffff",
                            "#ffffff",
                        ]
                        current_fg = colors[c - 90]

                last_end = end

            # Add remaining text
            if last_end < len(line):
                tokens.append((build_style(), line[last_end:]))

            # Store tokens for this line
            line_tokens[lineno] = tokens

        def get_line(lineno):
            return line_tokens.get(lineno, [])

        return get_line
