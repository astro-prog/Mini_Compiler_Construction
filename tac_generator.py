import sys
from dataclasses import dataclass
from typing import List
from lexer1 import Question2Parser, Node


# ============================================================
# QUADRUPLE
# ============================================================

@dataclass
class Quad:
    op: str
    arg1: str
    arg2: str
    result: str

    def __str__(self):
        if self.op == 'label':
            return f"{self.result}:"
        if self.op == 'goto':
            return f"goto {self.result}"
        if self.op == 'ifFalse':
            return f"ifFalse {self.arg1} goto {self.result}"
        if self.op == 'call':
            return f"call print({self.arg1})"
        if self.op == 'decl':
            return f"declare {self.arg1} {self.result}"
        if self.op == '=':
            return f"{self.result} = {self.arg1}"
        if self.op == '!':
            return f"{self.result} = ! {self.arg1}"
        if self.op == 'uminus':
            return f"{self.result} = - {self.arg1}"
        return f"{self.result} = {self.arg1} {self.op} {self.arg2}"


# ============================================================
# TAC GENERATOR FOR YOUR PARSE TREE
# ============================================================

class TACGenerator:
    def __init__(self):
        self.quads: List[Quad] = []
        self.temp_count = 0
        self.label_count = 0

    # ---------------- Helpers ----------------

    def new_temp(self):
        self.temp_count += 1
        return f"t{self.temp_count}"

    def new_label(self):
        self.label_count += 1
        return f"L{self.label_count}"

    def emit(self, op, arg1='', arg2='', result=''):
        self.quads.append(Quad(op, arg1, arg2, result))

    # ---------------- Main dispatch ----------------

    def generate(self, node):
        if node is None:
            return ''

        if node.name == "Program":
            return self.gen_program(node)
        elif node.name == "Declaration":
            return self.gen_declaration(node)
        elif node.name == "Assignment":
            return self.gen_assignment(node)
        elif node.name == "IfStatement":
            return self.gen_if(node)
        elif node.name == "WhileLoop":
            return self.gen_while(node)
        elif node.name == "Block":
            return self.gen_block(node)
        elif node.name == "Print":
            return self.gen_print(node)
        elif node.name == "Expression":
            return self.gen_expression(node)
        elif node.name == "Term":
            return self.gen_term(node)
        elif node.name == "Condition":
            return self.gen_condition(node)
        elif node.name == "ParenMath":
            return self.gen_paren_math(node)
        elif node.name == "ID":
            return node.value
        elif node.name == "INT_NUM":
            return node.value
        elif node.name == "FLOAT_NUM":
            return node.value
        else:
            print(f"[TAC] Warning: no handler for node {node.name}")
            return ''

    # ---------------- Program ----------------

    def gen_program(self, node):
        for child in node.children:
            self.generate(child)

    # ---------------- Declaration ----------------

    def gen_declaration(self, node):
        dtype = node.children[0].value
        name = node.children[1].value
        self.emit('decl', dtype, '', name)

    # ---------------- Assignment ----------------

    def gen_assignment(self, node):
        var_name = node.children[0].value
        expr_node = node.children[2]
        rhs = self.generate(expr_node)
        self.emit('=', rhs, '', var_name)

    # ---------------- Print ----------------

    def gen_print(self, node):
        expr_node = node.children[2]
        val = self.generate(expr_node)
        self.emit('call', val, '', 'print')

    # ---------------- Block ----------------

    def gen_block(self, node):
        for child in node.children:
            if child.name not in ("LBRACE", "RBRACE"):
                self.generate(child)

    # ---------------- If Statement ----------------

    def gen_if(self, node):
        cond_node = node.children[2]
        then_block = node.children[4]

        else_block = None
        if len(node.children) > 5:
            else_block = node.children[6]

        l_else = self.new_label()
        l_end = self.new_label()

        cond = self.generate(cond_node)
        self.emit('ifFalse', cond, '', l_else)

        self.generate(then_block)
        self.emit('goto', '', '', l_end)

        self.emit('label', '', '', l_else)
        if else_block:
            self.generate(else_block)

        self.emit('label', '', '', l_end)

    # ---------------- While Loop ----------------

    def gen_while(self, node):
        cond_node = node.children[2]
        body_node = node.children[4]

        l_start = self.new_label()
        l_end = self.new_label()

        self.emit('label', '', '', l_start)

        cond = self.generate(cond_node)
        self.emit('ifFalse', cond, '', l_end)

        self.generate(body_node)
        self.emit('goto', '', '', l_start)

        self.emit('label', '', '', l_end)

    # ---------------- Expressions ----------------

    def gen_expression(self, node):
        if len(node.children) == 1:
            return self.generate(node.children[0])

        left = self.generate(node.children[0])
        i = 1
        while i < len(node.children):
            op = node.children[i].value
            right = self.generate(node.children[i + 1])
            t = self.new_temp()
            self.emit(op, left, right, t)
            left = t
            i += 2
        return left

    def gen_term(self, node):
        if len(node.children) == 1:
            return self.generate(node.children[0])

        left = self.generate(node.children[0])
        i = 1
        while i < len(node.children):
            op = node.children[i].value
            right = self.generate(node.children[i + 1])
            t = self.new_temp()
            self.emit(op, left, right, t)
            left = t
            i += 2
        return left

    def gen_paren_math(self, node):
        return self.generate(node.children[1])

    # ---------------- Conditions ----------------

    def gen_condition(self, node):
        if len(node.children) == 1:
            return self.generate(node.children[0])

        # Case 1: ! condition
        if node.children[0].name == "NOT":
            operand = None
            if len(node.children) == 2:
                operand = self.generate(node.children[1])
            elif len(node.children) == 4:  # !( ... )
                operand = self.generate(node.children[2])

            t = self.new_temp()
            self.emit('!', operand, '', t)
            return t

        # Case 2: ( condition )
        if (
            len(node.children) == 3
            and node.children[0].name == "LPAREN"
            and node.children[2].name == "RPAREN"
        ):
            return self.generate(node.children[1])

        # Case 3: expr RELOP expr
        if len(node.children) >= 3 and node.children[1].name == "RELOP":
            left = self.generate(node.children[0])
            op = node.children[1].value
            right = self.generate(node.children[2])
            t = self.new_temp()
            self.emit(op, left, right, t)

            # Optional chaining: cond && other / cond || other
            if len(node.children) > 3 and node.children[3].name == "BOOLOP":
                bool_op = node.children[3].value
                next_cond = self.generate(node.children[4])
                t2 = self.new_temp()
                self.emit(bool_op, t, next_cond, t2)
                return t2

            return t

        # Case 4: plain expr or nested form
        left = self.generate(node.children[0])

        if len(node.children) > 1 and node.children[1].name == "BOOLOP":
            bool_op = node.children[1].value
            right = self.generate(node.children[2])
            t = self.new_temp()
            self.emit(bool_op, left, right, t)
            return t

        return left


# ============================================================
# PRETTY PRINTING
# ============================================================

def print_quads(quads: List[Quad]):
    print("\n" + "=" * 72)
    print(" THREE ADDRESS CODE — QUADRUPLES FORMAT")
    print("=" * 72)
    print(f" {'#':<5} {'OP':<10} {'ARG1':<12} {'ARG2':<12} {'RESULT'}")
    print(" " + "-" * 60)

    for i, q in enumerate(quads):
        print(f" {i:<5} {q.op:<10} {q.arg1:<12} {q.arg2:<12} {q.result}")

    print("=" * 72)
    print(f"\n Total quadruples: {len(quads)}")


def print_tac_readable(quads: List[Quad]):
    print("\n" + "=" * 72)
    print(" THREE ADDRESS CODE — READABLE FORMAT")
    print("=" * 72)
    for q in quads:
        print(str(q))
    print("=" * 72)


# ============================================================
# RUNNER
# ============================================================

def run(source: str, label: str):
    print("\n" + "█" * 72)
    print(f" SOURCE: {label}")
    print("█" * 72)

    try:
        parser = Question2Parser(source)
        tree = parser.parse_program()

        print("✔ Parser: Parse tree built successfully")
        print("\nGenerating Three Address Code (Quadruples)...")

        gen = TACGenerator()
        gen.generate(tree)

        print_quads(gen.quads)
        print_tac_readable(gen.quads)

        print(f"\n✔ TAC generation complete")
        print(f"✔ Temporaries used: {gen.temp_count}")
        print(f"✔ Labels used: {gen.label_count}")

    except SyntaxError as e:
        print(f"\n⛔ PARSING FAILED: {e}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    files = [a for a in sys.argv[1:] if not a.startswith("--")]

    if files:
        for fname in files:
            try:
                with open(fname, "r", encoding="utf-8") as f:
                    src = f.read()
                run(src, fname)
            except FileNotFoundError:
                print(f"\n✗ File not found: {fname}")
    else:
        print("\n" + "=" * 72)
        print(" INPUT SOURCE")
        print("=" * 72)
        print(" Options:")
        print(" 1. Enter a source file path")
        print(" 2. Type code directly")
        print()
        choice = input(" Enter choice (1 or 2): ").strip()

        if choice == "1":
            fname = input(" Enter file path: ").strip()
            try:
                with open(fname, "r", encoding="utf-8") as f:
                    src = f.read()
                run(src, fname)
            except FileNotFoundError:
                print(f"\n✗ File not found: {fname}")

        elif choice == "2":
            print(" Type your code below.")
            print(" Press ENTER on an empty line when done.\n")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            src = "\n".join(lines) + "\n"
            run(src, "user input")

        else:
            print(" Invalid choice.")