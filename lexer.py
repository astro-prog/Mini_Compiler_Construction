import re

# ---------------- Token definitions ---------------- #

TOKEN_TYPES = [
    ("FLOAT_LITERAL", r"\d+\.\d+"),
    ("INT_LITERAL",   r"\d+"),

    ("AND",           r"&&"),
    ("OR",            r"\|\|"),

    ("LEQ",           r"<="),
    ("GEQ",           r">="),
    ("EQ",            r"=="),
    ("NEQ",           r"!="),

    ("NOT",           r"!"),
    ("LT",            r"<"),
    ("GT",            r">"),

    ("ASSIGN",        r"="),

    ("PLUS",          r"\+"),
    ("MINUS",         r"-"),
    ("STAR",          r"\*"),
    ("SLASH",         r"/"),
    ("PERCENT",       r"%"),

    ("LPAREN",        r"\("),
    ("RPAREN",        r"\)"),
    ("LBRACE",        r"\{"),
    ("RBRACE",        r"\}"),
    ("SEMICOLON",     r";"),
    ("COLON",         r":"),  # Added specifically for Point 4: float avg:

    ("IDENTIFIER",    r"[A-Za-z_][A-Za-z0-9_]*"),

    ("NEWLINE",       r"\n"),
    ("SKIP",          r"[ \t\r]+"),

    # Optional: single-line and block comments
    ("COMMENT",       r"//[^\n]*"),
    ("MCOMMENT",      r"/\*[\s\S]*?\*/"),

    ("UNKNOWN",       r"."),
]

KEYWORDS = {"int", "float", "if", "else", "while", "print"}

MASTER_PATTERN = re.compile(
    "|".join("(?P<%s>%s)" % (name, pattern) for name, pattern in TOKEN_TYPES)
)


class Token:
    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.tokens = []
        self.errors = []

    def tokenize(self):
        line = 1
        line_start = 0

        for mo in MASTER_PATTERN.finditer(self.source):
            kind = mo.lastgroup
            value = mo.group()
            col = mo.start() - line_start + 1

            if kind == "NEWLINE":
                line += 1
                line_start = mo.end()
                continue

            if kind in ("SKIP", "COMMENT", "MCOMMENT"):
                # Count newlines inside comments/whitespace to keep track of line numbers
                line += value.count("\n")
                if "\n" in value:
                    last_nl = value.rfind("\n")
                    line_start = mo.start() + last_nl + 1
                continue

            if kind == "UNKNOWN":
                # Reporting lexical errors as required by Question 1 [cite: 79]
                self.errors.append(
                    f"Lexical error at line {line}, column {col}: unexpected character '{value}'"
                )
                continue

            if kind == "IDENTIFIER" and value in KEYWORDS:
                kind = value.upper()  # Maps to INT, FLOAT, IF, ELSE, WHILE, PRINT

            self.tokens.append(Token(kind, value, line, col))

        self.tokens.append(Token("EOF", "", line, 0))
        return self.tokens

    def print_tokens(self):
        """Generates the token stream output required for the assignment report[cite: 79]."""
        print("TOKEN STREAM")
        print("-" * 50)
        for tok in self.tokens:
            if tok.type == "EOF":
                print(f"{tok.type:15} (end)          Line:{tok.line} Col:{tok.col}")
            else:
                print(f"{tok.type:15} {tok.value:15} Line:{tok.line} Col:{tok.col}")

        if self.errors:
            print("\nLEXICAL ERRORS:")
            for err in self.errors:
                print(err)
        else:
            print("\nNo lexical errors found.")


def main():
    filename = "program.txt"

    try:
        with open(filename, "r") as f:
            source = f.read()

        lexer = Lexer(source)
        lexer.tokenize()
        lexer.print_tokens()
    except FileNotFoundError:
        print(f"Error: {filename} not found.")


if __name__ == "__main__":
    main()