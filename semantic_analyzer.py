import re

# ---------------- TOKEN DEFINITIONS ----------------
TOKEN_SPECIFICATION = [
    ('KEYWORD',   r'\b(int|float|if|else|while)\b'),
    ('IDENTIFIER',r'\b[a-zA-Z_]\w*\b'),
    ('NUMBER',    r'\b\d+(\.\d+)?\b'),
    ('OPERATOR',  r'[=+<>]'),
    ('SYMBOL',    r'[{}();]'),
    ('SKIP',      r'[ \t\n]+'),
    ('MISMATCH',  r'.'),
]

token_regex = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in TOKEN_SPECIFICATION)


class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f"{self.type}:{self.value}"


def tokenize(code):
    tokens = []
    for match in re.finditer(token_regex, code):
        kind = match.lastgroup
        value = match.group()

        if kind == 'SKIP':
            continue
        elif kind == 'MISMATCH':
            raise RuntimeError(f"Unexpected token: {value}")
        else:
            tokens.append(Token(kind, value))
    return tokens


# ---------------- SYMBOL TABLE ----------------
class Symbol:
    def __init__(self, name, var_type, scope):
        self.name = name
        self.type = var_type
        self.scope = scope

    def __repr__(self):
        return f"{self.name} | {self.type} | Scope {self.scope}"


class SymbolTable:
    def __init__(self):
        self.symbols = []
        self.scope_stack = [0]
        self.current_scope = 0
        self.errors = []

    def enter_scope(self):
        self.current_scope += 1
        self.scope_stack.append(self.current_scope)

    def exit_scope(self):
        scope = self.scope_stack.pop()
        self.symbols = [s for s in self.symbols if s.scope != scope]
        self.current_scope -= 1

    def insert(self, name, var_type):
        for sym in self.symbols:
            if sym.name == name and sym.scope == self.current_scope:
                self.errors.append(f"Error: Redeclaration of '{name}'")
                return
        self.symbols.append(Symbol(name, var_type, self.current_scope))

    def lookup(self, name):
        for scope in reversed(self.scope_stack):
            for sym in self.symbols:
                if sym.name == name and sym.scope == scope:
                    return sym
        return None

    def display(self):
        print("\nSymbol Table:")
        print("Name | Type | Scope")
        print("---------------------")
        for sym in self.symbols:
            print(sym)


# ---------------- PARSER ----------------
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.st = SymbolTable()

    def current_token(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def eat(self, token_type):
        token = self.current_token()
        if token and token.type == token_type:
            self.pos += 1
            return token
        else:
            raise RuntimeError(f"Expected {token_type}, got {token}")

    # 🔥 NEW: Single statement parser
    def parse_statement(self):
        token = self.current_token()

        if token.type == 'KEYWORD':
            if token.value in ['int', 'float']:
                self.parse_declaration()
            elif token.value == 'if':
                self.parse_if()
            elif token.value == 'while':
                self.parse_while()
            elif token.value == 'else':
                self.parse_else()

        elif token.type == 'IDENTIFIER':
            self.parse_assignment()

        elif token.value == '{':
            self.st.enter_scope()
            self.eat('SYMBOL')

        elif token.value == '}':
            self.st.exit_scope()
            self.eat('SYMBOL')

        else:
            self.pos += 1

    def parse(self):
        while self.current_token():
            self.parse_statement()
        return self.st

    def parse_declaration(self):
        var_type = self.eat('KEYWORD').value
        var_name = self.eat('IDENTIFIER').value
        self.st.insert(var_name, var_type)
        self.eat('SYMBOL')

    # -------- EXPRESSION --------
    def parse_expression(self):
        result_type = None

        while True:
            token = self.current_token()

            if token.type == 'NUMBER':
                self.eat('NUMBER')
                current_type = 'float' if '.' in token.value else 'int'

            elif token.type == 'IDENTIFIER':
                var_name = self.eat('IDENTIFIER').value
                symbol = self.st.lookup(var_name)

                if not symbol:
                    self.st.errors.append(f"Error: Undeclared variable '{var_name}'")
                    current_type = None
                else:
                    current_type = symbol.type

            else:
                break

            if result_type is None:
                result_type = current_type
            else:
                result_type = 'float' if 'float' in (result_type, current_type) else 'int'

            if self.current_token() and self.current_token().value in ['+', '<', '>']:
                self.eat('OPERATOR')
            else:
                break

        return result_type

    def parse_assignment(self):
        var_name = self.eat('IDENTIFIER').value
        self.eat('OPERATOR')

        expr_type = self.parse_expression()
        lhs_symbol = self.st.lookup(var_name)

        if not lhs_symbol:
            self.st.errors.append(f"Error: Undeclared variable '{var_name}'")
        elif expr_type and lhs_symbol.type != expr_type:
            self.st.errors.append(
                f"Type Error: Cannot assign {expr_type} to {lhs_symbol.type} '{var_name}'"
            )

        self.eat('SYMBOL')

    # -------- IF --------
    def parse_if(self):
        self.eat('KEYWORD')  # if
        self.eat('SYMBOL')   # (
        self.parse_expression()
        self.eat('SYMBOL')   # )
        self.eat('SYMBOL')   # {

        self.st.enter_scope()
        while self.current_token() and self.current_token().value != '}':
            self.parse_statement()
        self.st.exit_scope()

        self.eat('SYMBOL')  # }

    # -------- ELSE --------
    def parse_else(self):
        self.eat('KEYWORD')  # else
        self.eat('SYMBOL')   # {

        self.st.enter_scope()
        while self.current_token() and self.current_token().value != '}':
            self.parse_statement()
        self.st.exit_scope()

        self.eat('SYMBOL')

    # -------- WHILE --------
    def parse_while(self):
        self.eat('KEYWORD')  # while
        self.eat('SYMBOL')   # (
        self.parse_expression()
        self.eat('SYMBOL')   # )
        self.eat('SYMBOL')   # {

        self.st.enter_scope()
        while self.current_token() and self.current_token().value != '}':
            self.parse_statement()
        self.st.exit_scope()

        self.eat('SYMBOL')


# ---------------- MAIN ----------------
def run():
    try:
        with open("testprogram2.txt", "r") as file:
            code = file.read()

        print("===== INPUT =====")
        print(code)

        tokens = tokenize(code)
        print("\n===== TOKENS =====")
        print(tokens)

        parser = Parser(tokens)
        st = parser.parse()

        st.display()

        print("\n===== ERRORS =====")
        if not st.errors:
            print("No semantic errors ✅")
        else:
            for err in st.errors:
                print(err)

    except FileNotFoundError:
        print("Error: 'testprogram2.txt' not found.")


# Run
run()