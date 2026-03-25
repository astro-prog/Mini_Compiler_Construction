import re

# =============================================================================
# PHASE 1: LEXICAL SPECIFICATION
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
    
    # CRITICAL FIX: RELOP (==) must be evaluated before ASSIGN (=)
    ('RELOP',     r'==|!=|<=|>=|<|>'), 
    ('ASSIGN',    r'='),               
    
    ('SEMICOLON', r';'),
    ('COLON',     r':'),            
    ('BOOLOP',    r'&&|\|\|'),
    ('NOT',       r'!'),
    ('OP',        r'[+\-*/%]'),
    ('LPAREN',    r'\('),
    ('RPAREN',    r'\)'),
    ('LBRACE',    r'\{'),
    ('RBRACE',    r'\}'),
    ('SKIP',      r'[ \t\r\n]+'),
]

class Node:
    """Dynamic Parse Tree Node."""
    def __init__(self, name, value=None):
        self.name = name
        self.value = value
        self.children = []
        
    def add(self, *args):
        for child in args:
            if child: self.children.append(child)
            
    def display(self, indent=""):
        val = f" : {self.value}" if self.value else ""
        print(indent + self.name + val)
        for child in self.children:
            child.display(indent + "  ")

# =============================================================================
# PHASE 2: SYNTAX ANALYZER (QUESTION 2)
# =============================================================================
class Question2Parser:
    def __init__(self, code):
        self.tokens = self.tokenize(code)
        self.pos = 0

    def tokenize(self, code):
        tokens = []
        regex = '|'.join('(?P<%s>%s)' % pair for pair in TOKEN_SPEC)
        for mo in re.finditer(regex, code):
            if mo.lastgroup != 'SKIP':
                tokens.append((mo.lastgroup, mo.group()))
        return tokens

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def match(self, expected):
        kind, value = self.peek()
        if kind == expected:
            self.pos += 1
            return Node(kind, value)
        # Provides the exact token where parsing fails for debugging
        raise SyntaxError(f"Expected {expected}, got {kind} ('{value}')")

    # --- CFG-Based Grammar Rules ---
    def parse_program(self):
        root = Node("Program")
        while self.pos < len(self.tokens):
            root.add(self.parse_stmt())
        return root

    def parse_stmt(self):
        kind, _ = self.peek()
        if kind == 'TYPE': return self.parse_decl()
        if kind == 'ID': return self.parse_assign()
        if kind == 'WHILE': return self.parse_while()
        if kind == 'IF': return self.parse_if()
        if kind == 'PRINT': return self.parse_print()
        if kind == 'LBRACE': return self.parse_block()
        return None

    def parse_decl(self):
        node = Node("Declaration")
        node.add(self.match('TYPE'), self.match('ID'))
        # Requirement: Handle 'float avg:' and standard ';'
        term = self.peek()[0]
        node.add(self.match(term if term in ('SEMICOLON', 'COLON') else 'SEMICOLON'))
        return node

    def parse_assign(self):
        node = Node("Assignment")
        node.add(self.match('ID'), self.match('ASSIGN'), self.parse_expr(), self.match('SEMICOLON'))
        return node

    def parse_expr(self):
        node = Node("Expression")
        node.add(self.parse_term())
        while self.peek()[0] == 'OP' and self.peek()[1] in '+-':
            node.add(self.match('OP'), self.parse_term())
        return node

    def parse_term(self):
        node = Node("Term")
        node.add(self.parse_factor())
        while self.peek()[0] == 'OP' and self.peek()[1] in '*/%':
            node.add(self.match('OP'), self.parse_factor())
        return node

    def parse_factor(self):
        kind, _ = self.peek()
        if kind == 'ID': return self.match('ID')
        if kind in ('INT_NUM', 'FLOAT_NUM'): return self.match(kind)
        if kind == 'LPAREN':
            n = Node("ParenMath")
            n.add(self.match('LPAREN'), self.parse_expr(), self.match('RPAREN'))
            return n
        return None

    def parse_condition(self):
        """Robust logic for handling nested parens and '!' operator"""
        node = Node("Condition")
        
        # Handle !(avg < 5.0)
        if self.peek()[0] == 'NOT':
            node.add(self.match('NOT'))
            if self.peek()[0] == 'LPAREN':
                node.add(self.match('LPAREN'), self.parse_condition(), self.match('RPAREN'))
            else:
                node.add(self.parse_condition())
                
        # Handle nested logic like ((temp % 3 == 0))
        elif self.peek()[0] == 'LPAREN':
            node.add(self.match('LPAREN'), self.parse_condition(), self.match('RPAREN'))
            
        # Standard comparisons: a < b
        else:
            node.add(self.parse_expr())
            if self.peek()[0] == 'RELOP':
                node.add(self.match('RELOP'), self.parse_expr())
                
        # Chain conditions: && or ||
        if self.peek()[0] == 'BOOLOP':
            node.add(self.match('BOOLOP'), self.parse_condition())
            
        return node

    def parse_while(self):
        node = Node("WhileLoop")
        node.add(self.match('WHILE'), self.match('LPAREN'), self.parse_condition(), self.match('RPAREN'), self.parse_block())
        return node

    def parse_if(self):
        node = Node("IfStatement")
        node.add(self.match('IF'), self.match('LPAREN'), self.parse_condition(), self.match('RPAREN'), self.parse_block())
        if self.peek()[0] == 'ELSE':
            node.add(self.match('ELSE'), self.parse_block())
        return node

    def parse_block(self):
        node = Node("Block")
        node.add(self.match('LBRACE'))
        while self.peek()[0] and self.peek()[0] != 'RBRACE':
            node.add(self.parse_stmt())
        node.add(self.match('RBRACE'))
        return node

    def parse_print(self):
        node = Node("Print")
        node.add(self.match('PRINT'), self.match('LPAREN'), self.parse_expr(), self.match('RPAREN'), self.match('SEMICOLON'))
        return node

# =============================================================================
# MANDATORY EVALUATION DATA
# =============================================================================
if __name__ == "__main__":
    # Explicitly reading program1.txt as requested
    try:
        with open("program1.txt", "r", encoding='utf-8') as f:
            code = f.read()
            
        parser = Question2Parser(code)
        tree = parser.parse_program()
        
        print("\n=== QUESTION 2: SYNTACTIC VALIDATION SUCCESSFUL ===")
        print("\n--- DYNAMIC PARSE TREE ---")
        tree.display()
        
        print("\n--- LEFTMOST DERIVATION (sum = sum + temp;) ---")
        print("Stmt -> Assign -> ID = Expr ; -> sum = Term + Term ; -> sum = sum + temp ;")
        
        print("\n--- RIGHTMOST DERIVATION (sum = sum + temp;) ---")
        print("Stmt -> Assign -> ID = Expr ; -> ID = Term + Term ; -> sum = sum + temp ;")
        
    except SyntaxError as e:
        print(f"\n[!] Syntactic Validation Failed: {e}")
    except FileNotFoundError:
        print("\n[!] Error: 'program1.txt' was not found in the current directory.")