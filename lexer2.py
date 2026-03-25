import re

# =============================================================================
# PHASE 1: LEXICAL ANALYZER (QUESTION 1)
# =============================================================================
TOKEN_SPEC = [
    ('TYPE',      r'\b(int|float)\b'),
    ('IF',        r'\bif\b'),
    ('ELSE',      r'\belse\b'),
    ('WHILE',     r'\bwhile\b'),
    ('PRINT',     r'\bprint\b'),
    ('ID',        r'[a-zA-Z_][a-zA-Z0-9_]*'),
    ('FLOAT_NUM', r'\d+\.\d+'),
    ('INT_NUM',   r'\d+'),
    ('ASSIGN',    r'='),
    ('SEMICOLON', r';'),
    ('COLON',     r':'), 
    ('OP',        r'[+\-*/%]'),
    ('RELOP',     r'==|!=|<=|>=|<|>'),
    ('BOOLOP',    r'&&|\|\|'),
    ('NOT',       r'!'),
    ('LPAREN',    r'\('),
    ('RPAREN',    r'\)'),
    ('LBRACE',    r'\{'),
    ('RBRACE',    r'\}'),
    ('SKIP',      r'[ \t\r]+'),
    ('NEWLINE',   r'\n'),
    ('MISMATCH',  r'.'),
]

class Token:
    def __init__(self, type, value, line, col):
        self.type = type
        self.value = value
        self.line = line
        self.col = col

def get_tokens(code):
    tokens = []
    line_num = 1
    line_start = 0
    regex = '|'.join('(?P<%s>%s)' % pair for pair in TOKEN_SPEC)
    
    for mo in re.finditer(regex, code):
        kind = mo.lastgroup
        value = mo.group()
        column = mo.start() - line_start + 1
        
        if kind == 'SKIP': continue
        elif kind == 'NEWLINE':
            line_num += 1
            line_start = mo.end()
            continue
        elif kind == 'MISMATCH':
            print(f"Lexical Error: Unexpected '{value}' at line {line_num}, col {column}")
            continue
        tokens.append(Token(kind, value, line_num, column))
    return tokens

# =============================================================================
# PHASE 2 & 3: PARSER & ERROR DETECTION (QUESTION 2 & 3)
# =============================================================================
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def match(self, expected_type):
        token = self.peek()
        if token and token.type == expected_type:
            self.pos += 1
            return token
        # QUESTION 3: Specific Error Reporting
        actual = token.value if token else "EOF"
        line = token.line if token else "end"
        raise SyntaxError(f"Error at line {line}: Expected '{expected_type}', found '{actual}'")

    def parse_program(self):
        print("Starting Syntactic Validation...")
        while self.pos < len(self.tokens):
            try:
                self.parse_stmt()
            except SyntaxError as e:
                # QUESTION 3: Catch error, report, and attempt to synchronize
                print(f"SYNTAX ERROR DETECTED: {e}")
                self.synchronize()

    def synchronize(self):
        """Skip tokens until we find a semicolon or brace to continue parsing."""
        while self.pos < len(self.tokens):
            if self.tokens[self.pos].type in ('SEMICOLON', 'RBRACE'):
                self.pos += 1
                return
            self.pos += 1

    def parse_stmt(self):
        token = self.peek()
        if not token: return
        
        if token.type == 'TYPE':
            self.match('TYPE')
            self.match('ID')
            # The assignment's program.txt uses both ':' and ';' 
            if self.peek().type == 'COLON': self.match('COLON')
            else: self.match('SEMICOLON')
        elif token.type == 'ID':
            self.match('ID')
            self.match('ASSIGN')
            self.parse_expr()
            self.match('SEMICOLON')
        elif token.type == 'WHILE':
            self.match('WHILE')
            self.match('LPAREN')
            self.parse_bool()
            self.match('RPAREN') # This will fail for Error 2 in program.txt
            self.parse_block()
        elif token.type == 'IF':
            self.match('IF')
            self.match('LPAREN')
            self.parse_bool()
            self.match('RPAREN')
            self.parse_block()
            if self.peek() and self.peek().type == 'ELSE':
                self.match('ELSE')
                self.parse_block()
        elif token.type == 'PRINT':
            self.match('PRINT')
            self.match('LPAREN')
            self.parse_expr()
            self.match('RPAREN')
            self.match('SEMICOLON')

    def parse_block(self):
        self.match('LBRACE')
        while self.peek() and self.peek().type != 'RBRACE':
            self.parse_stmt()
        self.match('RBRACE')

    def parse_expr(self):
        self.parse_term()
        while self.peek() and self.peek().type == 'OP' and self.peek().value in '+-':
            self.match('OP')
            self.parse_term()

    def parse_term(self):
        self.parse_factor()
        while self.peek() and self.peek().type == 'OP' and self.peek().value in '*/%':
            self.match('OP')
            self.parse_factor()

    def parse_factor(self):
        t = self.peek()
        if t.type == 'ID': self.match('ID')
        elif t.type in ('INT_NUM', 'FLOAT_NUM'): self.pos += 1
        elif t.type == 'LPAREN':
            self.match('LPAREN')
            self.parse_expr()
            self.match('RPAREN')

    def parse_bool(self):
        self.parse_expr()
        if self.peek().type == 'RELOP':
            self.match('RELOP')
            self.parse_expr()
        if self.peek().type == 'BOOLOP':
            self.match('BOOLOP')
            self.parse_bool()

# =============================================================================
# MAIN RUNNER
# =============================================================================
if __name__ == "__main__":
    with open("program2.txt", "r") as f:
        code = f.read()

    print("--- Phase 1: Lexical Analysis ---")
    tokens = get_tokens(code)
    
    print("\n--- Phase 2 & 3: Syntax Analysis & Error Detection ---")
    parser = Parser(tokens)
    parser.parse_program()