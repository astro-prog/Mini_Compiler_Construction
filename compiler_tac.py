import re
import sys

# ==========================================
# 1. LEXER (Tokenization)
# ==========================================
TOKEN_SPECIFICATION = [
    ('NUMBER',   r'\d+'),
    ('IF',       r'\bif\b'),
    ('ELSE',     r'\belse\b'),
    ('WHILE',    r'\bwhile\b'),
    ('ID',       r'[A-Za-z_]\w*'),
    ('RELOP',    r'==|!=|<=|>=|<|>'),
    ('OP',       r'[+\-*/]'),
    ('ASSIGN',   r'='),
    ('SEMI',     r';'),
    ('LPAREN',   r'\('),
    ('RPAREN',   r'\)'),
    ('LBRACE',   r'\{'),
    ('RBRACE',   r'\}'),
    ('SKIP',     r'[ \t\n]+'),
    ('MISMATCH', r'.'),
]

def tokenize(code):
    tokens = []
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in TOKEN_SPECIFICATION)
    for mo in re.finditer(tok_regex, code):
        kind = mo.lastgroup
        value = mo.group()
        if kind == 'SKIP':
            continue
        elif kind == 'MISMATCH':
            raise RuntimeError(f"Unexpected character: {value}")
        tokens.append((kind, value))
    return tokens

# ==========================================
# 2. SYMBOL TABLE
# ==========================================
class SymbolTable:
    def __init__(self):
        self.scopes = [{}]

    def enter_scope(self):
        self.scopes.append({})

    def exit_scope(self):
        self.scopes.pop()

    def insert(self, name):
        self.scopes[-1][name] = True

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return True
        return False

    def display(self):
        print("\n--- Symbol Table ---")
        for i, scope in enumerate(self.scopes):
            print(f"Scope {i}: {list(scope.keys())}")

# ==========================================
# 3. AST NODES
# ==========================================
class ASTNode: pass
class Assign(ASTNode):
    def __init__(self, target, expr): self.target, self.expr = target, expr
class BinOp(ASTNode):
    def __init__(self, left, op, right): self.left, self.op, self.right = left, op, right
class Num(ASTNode):
    def __init__(self, val): self.val = val
class Var(ASTNode):
    def __init__(self, name): self.name = name
class IfStmt(ASTNode):
    def __init__(self, cond, true_branch, false_branch):
        self.cond, self.true_branch, self.false_branch = cond, true_branch, false_branch
class WhileStmt(ASTNode):
    def __init__(self, cond, body):
        self.cond, self.body = cond, body

# ==========================================
# 4. PARSER
# ==========================================
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.symtab = SymbolTable()

    def current_token(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ('EOF', '')

    def match(self, expected_kind):
        kind, value = self.current_token()
        if kind == expected_kind:
            self.pos += 1
            return value
        raise SyntaxError(f"Expected {expected_kind}, got {kind}")

    def parse(self):
        stmts = []
        while self.current_token()[0] != 'EOF':
            stmts.append(self.parse_statement())
        return stmts

    def parse_statement(self):
        kind = self.current_token()[0]
        if kind == 'IF': return self.parse_if()
        elif kind == 'WHILE': return self.parse_while()
        elif kind == 'ID': return self.parse_assign()
        else: raise SyntaxError("Invalid statement")

    def parse_assign(self):
        var = self.match('ID')
        self.match('ASSIGN')
        expr = self.parse_expression()
        self.match('SEMI')

        if not self.symtab.lookup(var):
            self.symtab.insert(var)

        return Assign(var, expr)

    def parse_if(self):
        self.match('IF')
        self.match('LPAREN')
        cond = self.parse_expression()
        self.match('RPAREN')

        self.match('LBRACE')
        self.symtab.enter_scope()
        true_branch = self.parse_block()
        self.symtab.exit_scope()
        self.match('RBRACE')

        false_branch = []
        if self.current_token()[0] == 'ELSE':
            self.match('ELSE')
            self.match('LBRACE')
            self.symtab.enter_scope()
            false_branch = self.parse_block()
            self.symtab.exit_scope()
            self.match('RBRACE')

        return IfStmt(cond, true_branch, false_branch)

    def parse_while(self):
        self.match('WHILE')
        self.match('LPAREN')
        cond = self.parse_expression()
        self.match('RPAREN')

        self.match('LBRACE')
        self.symtab.enter_scope()
        body = self.parse_block()
        self.symtab.exit_scope()
        self.match('RBRACE')

        return WhileStmt(cond, body)

    def parse_block(self):
        stmts = []
        while self.current_token()[0] not in ('RBRACE', 'EOF'):
            stmts.append(self.parse_statement())
        return stmts

    def parse_expression(self):
        left = self.parse_term()
        while self.current_token()[0] in ('OP', 'RELOP'):
            op = self.match(self.current_token()[0])
            right = self.parse_term()
            left = BinOp(left, op, right)
        return left

    def parse_term(self):
        kind, val = self.current_token()
        if kind == 'NUMBER':
            self.pos += 1
            return Num(val)
        elif kind == 'ID':
            if not self.symtab.lookup(val):
                raise NameError(f"Variable '{val}' not declared")
            self.pos += 1
            return Var(val)
        raise SyntaxError("Invalid expression")

# ==========================================
# 5. TAC GENERATOR
# ==========================================
class TACGenerator:
    def __init__(self):
        self.code = []
        self.temp = 0
        self.label = 0

    def new_temp(self):
        self.temp += 1
        return f"t{self.temp}"

    def new_label(self):
        self.label += 1
        return f"L{self.label}"

    def emit(self, line):
        self.code.append(line)

    def generate(self, node):
        if isinstance(node, list):
            for stmt in node:
                self.generate(stmt)

        elif isinstance(node, Assign):
            val = self.generate(node.expr)
            self.emit(f"{node.target} = {val}")

        elif isinstance(node, BinOp):
            l = self.generate(node.left)
            r = self.generate(node.right)
            t = self.new_temp()
            self.emit(f"{t} = {l} {node.op} {r}")
            return t

        elif isinstance(node, Num): return node.val
        elif isinstance(node, Var): return node.name

        elif isinstance(node, IfStmt):
            c = self.generate(node.cond)
            l1, l2 = self.new_label(), self.new_label()
            self.emit(f"ifFalse {c} goto {l1}")
            self.generate(node.true_branch)
            self.emit(f"goto {l2}")
            self.emit(f"{l1}:")
            self.generate(node.false_branch)
            self.emit(f"{l2}:")

        elif isinstance(node, WhileStmt):
            l1, l2 = self.new_label(), self.new_label()
            self.emit(f"{l1}:")
            c = self.generate(node.cond)
            self.emit(f"ifFalse {c} goto {l2}")
            self.generate(node.body)
            self.emit(f"goto {l1}")
            self.emit(f"{l2}:")

# ==========================================
# 6. DRIVER (MENU DRIVEN)
# ==========================================
def main():
    while True:
        print("\n===== MINI COMPILER MENU =====")
        print("1. Enter program manually")
        print("2. Load program from file")
        print("3. Exit")

        choice = input("Enter choice: ")

        if choice == '1':
            print("\nEnter your program (end with blank line):")
            lines = []
            while True:
                line = input()
                if line.strip() == "": break
                lines.append(line)
            code = "\n".join(lines)

        elif choice == '2':
            filename = input("Enter filename: ")
            try:
                with open(filename, 'r') as f:
                    code = f.read()
            except:
                print("File not found!")
                continue

        elif choice == '3':
            print("Exiting...")
            sys.exit()
        else:
            print("Invalid choice!")
            continue

        try:
            print("\n--- Source Code ---")
            print(code)

            tokens = tokenize(code)
            parser = Parser(tokens)
            ast = parser.parse()

            parser.symtab.display()

            tac = TACGenerator()
            tac.generate(ast)

            print("\n--- TAC ---")
            for line in tac.code:
                print(line)

        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    main()
