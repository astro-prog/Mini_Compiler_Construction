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
# 2. AST NODES
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
# 3. PARSER (Recursive Descent)
# ==========================================
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current_token(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ('EOF', '')

    def match(self, expected_kind):
        kind, value = self.current_token()
        if kind == expected_kind:
            self.pos += 1
            return value
        raise SyntaxError(f"Expected {expected_kind}, got {kind} ('{value}')")

    def parse(self):
        statements = []
        while self.current_token()[0] != 'EOF':
            statements.append(self.parse_statement())
        return statements

    def parse_statement(self):
        kind = self.current_token()[0]
        if kind == 'IF': return self.parse_if()
        elif kind == 'WHILE': return self.parse_while()
        elif kind == 'ID': return self.parse_assign()
        else: raise SyntaxError(f"Unexpected token in statement: {self.current_token()}")

    def parse_assign(self):
        var_name = self.match('ID')
        self.match('ASSIGN')
        expr = self.parse_expression()
        self.match('SEMI')
        return Assign(var_name, expr)

    def parse_if(self):
        self.match('IF')
        self.match('LPAREN')
        cond = self.parse_expression()
        self.match('RPAREN')
        self.match('LBRACE')
        true_branch = self.parse_block()
        self.match('RBRACE')
        false_branch = []
        if self.current_token()[0] == 'ELSE':
            self.match('ELSE')
            self.match('LBRACE')
            false_branch = self.parse_block()
            self.match('RBRACE')
        return IfStmt(cond, true_branch, false_branch)

    def parse_while(self):
        self.match('WHILE')
        self.match('LPAREN')
        cond = self.parse_expression()
        self.match('RPAREN')
        self.match('LBRACE')
        body = self.parse_block()
        self.match('RBRACE')
        return WhileStmt(cond, body)

    def parse_block(self):
        stmts = []
        while self.current_token()[0] not in ('RBRACE', 'EOF'):
            stmts.append(self.parse_statement())
        return stmts

    def parse_expression(self):
        # Parses math and relational expressions
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
            self.pos += 1
            return Var(val)
        raise SyntaxError(f"Expected Number or ID, got {kind}")

# ==========================================
# 4. TAC GENERATOR (Intermediate Code)
# ==========================================
class TACGenerator:
    def __init__(self):
        self.tac_code = []
        self.temp_count = 0
        self.label_count = 0

    def new_temp(self):
        self.temp_count += 1
        return f"t{self.temp_count}"

    def new_label(self):
        self.label_count += 1
        return f"L{self.label_count}"

    def emit(self, instruction):
        self.tac_code.append(instruction)

    def generate(self, node):
        if isinstance(node, list):
            for stmt in node:
                self.generate(stmt)
        
        elif isinstance(node, Assign):
            expr_temp = self.generate(node.expr)
            self.emit(f"{node.target} = {expr_temp}")

        elif isinstance(node, BinOp):
            left_temp = self.generate(node.left)
            right_temp = self.generate(node.right)
            temp = self.new_temp()
            self.emit(f"{temp} = {left_temp} {node.op} {right_temp}")
            return temp

        elif isinstance(node, Num):
            return node.val

        elif isinstance(node, Var):
            return node.name

        elif isinstance(node, IfStmt):
            cond_temp = self.generate(node.cond)
            label_false = self.new_label()
            label_end = self.new_label()
            
            self.emit(f"ifFalse {cond_temp} goto {label_false}")
            self.generate(node.true_branch)
            self.emit(f"goto {label_end}")
            self.emit(f"{label_false}:")
            self.generate(node.false_branch)
            self.emit(f"{label_end}:")

        elif isinstance(node, WhileStmt):
            label_start = self.new_label()
            label_end = self.new_label()
            
            self.emit(f"{label_start}:")
            cond_temp = self.generate(node.cond)
            self.emit(f"ifFalse {cond_temp} goto {label_end}")
            self.generate(node.body)
            self.emit(f"goto {label_start}")
            self.emit(f"{label_end}:")

# ==========================================
# 5. DRIVER (Menu & File Handling)
# ==========================================
def main():
    while True:
        print("\n=== Mini Compiler: TAC Generation ===")
        print("1. Load and Generate TAC from test_program.txt")
        print("2. Exit")
        choice = input("Enter choice: ")

        if choice == '1':
            filename = 'test_program2.txt'
            try:
                with open(filename, 'r') as file:
                    source_code = file.read()
                
                print("\n--- Source Code ---")
                print(source_code.strip())

                tokens = tokenize(source_code)
                parser = Parser(tokens)
                ast = parser.parse()

                tac_gen = TACGenerator()
                tac_gen.generate(ast)

                print("\n--- Three-Address Code (TAC) ---")
                for line in tac_gen.tac_code:
                    print(line)

            except FileNotFoundError:
                print(f"\nError: File '{filename}' not found. Please create it.")
            except Exception as e:
                print(f"\nCompilation Error: {e}")
        
        elif choice == '2':
            print("Exiting...")
            sys.exit(0)
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    main()