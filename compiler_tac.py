"""
Compiler Phase II — Symbol Table & Semantic Analysis
======================================================
Q2: Symbol Table with Scope Handling  (5 Marks)
Q3: Semantic Analysis                  (5 Marks)

Pipeline:
  source → Lexer → token stream → Parser → AST
         → SymbolTable (Q2) + SemanticAnalyzer (Q3)

Q2 — Symbol Table stores:
  - Variable name, data type, scope level, scope name, memory offset, line

Q2 — Operations:
  - insert(name, type, line)  → adds entry to current scope
  - lookup(name, line)        → walks stack innermost → outermost

Q2 — Scope handling:
  - enter_scope() on every {
  - exit_scope()  on every }
  - Stack of dicts: each dict = one scope

Q3 — Semantic checks:
  - Undeclared variable use
  - Multiple declarations in same scope (redeclaration)
  - Type mismatch in assignment (int vs float)
  - Invalid boolean conditions (non-comparison used as bool)
"""

import sys
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from lexer import Lexer
from parser import Parser
from ast_nodes import *


# ═══════════════════════════════════════════════════════════════════════
#  Q2 — SYMBOL TABLE
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SymbolEntry:
    name:        str
    data_type:   str      # 'int' or 'float'
    scope_level: int      # 0 = global, 1 = first nested block, etc.
    scope_name:  str      # 'global', 'while_body', 'if_then', 'if_else'
    offset:      int      # memory offset in bytes within its scope
    line:        int      # source line number of declaration


class SymbolTable:
    """
    Stack-based symbol table.
    Each element of the stack is one scope (a dict: name → SymbolEntry).
    ENTER SCOPE  → push new dict
    EXIT  SCOPE  → pop dict (variables go out of scope)
    LOOKUP       → search from top (innermost) to bottom (global)
    """
    TYPE_SIZE = {'int': 4, 'float': 4}

    def __init__(self):
        self.scope_stack:  List[Dict[str, SymbolEntry]] = []
        self.scope_names:  List[str]  = []
        self.offset_stack: List[int]  = []
        self.level:        int        = -1
        self.all_entries:  List[SymbolEntry] = []   # full history
        self.errors:       List[str]  = []

    # ── Scope ─────────────────────────────────────────────────────────

    def enter_scope(self, name: str = "block"):
        self.level += 1
        self.scope_stack.append({})
        self.scope_names.append(name)
        self.offset_stack.append(0)
        indent = "  " * self.level
        print(f"\n{indent}┌─ ENTER SCOPE [{name}]  (level {self.level})")

    def exit_scope(self):
        name  = self.scope_names[-1]
        level = self.level
        indent = "  " * level
        scope  = self.scope_stack[-1]

        # Print what was in this scope before removing it
        if scope:
            print(f"{indent}│  Scope [{name}] variables going out of scope:")
            print(f"{indent}│  {'NAME':<12} {'TYPE':<8} {'OFFSET':<8} LINE")
            print(f"{indent}│  {'─'*35}")
            for e in scope.values():
                print(f"{indent}│  {e.name:<12} {e.data_type:<8} {e.offset:<8} {e.line}")
        print(f"{indent}└─ EXIT  SCOPE [{name}]  (back to level {level - 1})")

        self.scope_stack.pop()
        self.scope_names.pop()
        self.offset_stack.pop()
        self.level -= 1

    # ── Insert ────────────────────────────────────────────────────────

    def insert(self, name: str, dtype: str, line: int) -> Optional[SymbolEntry]:
        indent = "  " * self.level

        # Q3 check: redeclaration in same scope
        if name in self.scope_stack[-1]:
            existing = self.scope_stack[-1][name]
            msg = (f"[SEMANTIC ERROR] Line {line}: "
                   f"'{name}' already declared in this scope "
                   f"(first declared at line {existing.line})")
            self.errors.append(msg)
            print(f"{indent}│  ✗ {msg}")
            return None

        # Check shadowing
        outer = self._find_in_outer(name)
        offset = self.offset_stack[-1]
        self.offset_stack[-1] += self.TYPE_SIZE.get(dtype, 4)

        entry = SymbolEntry(
            name        = name,
            data_type   = dtype,
            scope_level = self.level,
            scope_name  = self.scope_names[-1],
            offset      = offset,
            line        = line,
        )
        self.scope_stack[-1][name] = entry
        self.all_entries.append(entry)

        shadow = ""
        if outer:
            shadow = f"  ⚠ shadows '{name}' from [{outer.scope_name}] level {outer.scope_level}"

        print(f"{indent}│  INSERT  {name:<12} type={dtype:<6} "
              f"offset={offset:<4} line={line}{shadow}")
        return entry

    # ── Lookup ────────────────────────────────────────────────────────

    def lookup(self, name: str, line: int = 0) -> Optional[SymbolEntry]:
        """Walk from innermost (top) to outermost (bottom) scope."""
        for scope, sname in zip(reversed(self.scope_stack),
                                 reversed(self.scope_names)):
            if name in scope:
                return scope[name]
        # Q3 check: undeclared variable
        msg = f"[SEMANTIC ERROR] Line {line}: '{name}' used but not declared"
        self.errors.append(msg)
        return None

    def lookup_type(self, name: str, line: int = 0) -> Optional[str]:
        entry = self.lookup(name, line)
        return entry.data_type if entry else None

    def _find_in_outer(self, name: str) -> Optional[SymbolEntry]:
        for scope in list(reversed(self.scope_stack))[1:]:
            if name in scope:
                return scope[name]
        return None

    # ── Display ───────────────────────────────────────────────────────

    def print_full_table(self):
        print("\n" + "="*72)
        print("  Q2 — COMPLETE SYMBOL TABLE  (all declarations, all scopes)")
        print("="*72)
        print(f"  {'NAME':<12} {'TYPE':<8} {'LEVEL':<7} {'SCOPE':<16} {'OFFSET':<8} LINE")
        print(f"  {'─'*65}")
        for e in self.all_entries:
            print(f"  {e.name:<12} {e.data_type:<8} {e.scope_level:<7} "
                  f"{e.scope_name:<16} {e.offset:<8} {e.line}")
        print("="*72)


# ═══════════════════════════════════════════════════════════════════════
#  Q3 — SEMANTIC ANALYZER
# ═══════════════════════════════════════════════════════════════════════

class SemanticAnalyzer:
    """
    Walks the AST and performs:
      1. Undeclared variable detection
      2. Redeclaration in same scope
      3. Type mismatch in assignment
      4. Invalid boolean condition (missing relop)
    Also drives the symbol table (Q2).
    """

    def __init__(self, symbol_table: SymbolTable):
        self.st      = symbol_table
        self.errors  = symbol_table.errors   # share the same list
        self.warnings: List[str] = []

    # ── Entry point ───────────────────────────────────────────────────

    def analyze(self, node: Node):
        method = f"_visit_{type(node).__name__}"
        getattr(self, method, self._noop)(node)

    def _noop(self, node):
        pass

    # ── Program / Block ───────────────────────────────────────────────

    def _visit_Program(self, node: Program):
        self.st.enter_scope("global")
        for s in node.stmts:
            self.analyze(s)
        self.st.exit_scope()

    def _visit_Block(self, node: Block):
        for s in node.stmts:
            self.analyze(s)

    # ── Declarations ──────────────────────────────────────────────────

    def _visit_DeclStmt(self, node: DeclStmt):
        self.st.insert(node.name, node.dtype, node.line)

    # ── Assignment ────────────────────────────────────────────────────

    def _visit_AssignStmt(self, node: AssignStmt):
        # Lookup LHS
        entry = self.st.lookup(node.name, node.line)
        if entry:
            indent = "  " * self.st.level
            print(f"{indent}│  LOOKUP  {node.name:<12} → found "
                  f"type={entry.data_type} scope=[{entry.scope_name}] "
                  f"level={entry.scope_level} offset={entry.offset}")

        # Infer RHS type
        rhs_type = self._infer_type(node.expr)

        # Q3 check: type mismatch
        if entry and rhs_type:
            lhs_type = entry.data_type
            if lhs_type == 'int' and rhs_type == 'float':
                msg = (f"[SEMANTIC ERROR] Line {node.line}: "
                       f"type mismatch — cannot assign float to int '{node.name}'")
                self.errors.append(msg)
                indent = "  " * self.st.level
                print(f"{indent}│  ✗ {msg}")
            elif lhs_type == 'float' and rhs_type == 'int':
                # int → float is allowed (implicit widening)
                pass

    # ── If / While ────────────────────────────────────────────────────

    def _visit_IfStmt(self, node: IfStmt):
        self._check_bool_condition(node.condition, node.line)

        self.st.enter_scope("if_then")
        if isinstance(node.then_block, Block):
            self._visit_Block(node.then_block)
        else:
            self.analyze(node.then_block)
        self.st.exit_scope()

        if node.else_block:
            self.st.enter_scope("if_else")
            if isinstance(node.else_block, Block):
                self._visit_Block(node.else_block)
            else:
                self.analyze(node.else_block)
            self.st.exit_scope()

    def _visit_WhileStmt(self, node: WhileStmt):
        self._check_bool_condition(node.condition, node.line)

        self.st.enter_scope("while_body")
        if isinstance(node.body, Block):
            self._visit_Block(node.body)
        else:
            self.analyze(node.body)
        self.st.exit_scope()

    def _visit_PrintStmt(self, node: PrintStmt):
        self._infer_type(node.expr)

    # ── Boolean condition check ───────────────────────────────────────

    RELOPS = {'<', '>', '<=', '>=', '==', '!=', '&&', '||'}

    def _check_bool_condition(self, node: Node, line: int):
        """
        Q3: A valid boolean condition must contain at least one
        relational or logical operator, or a NOT.
        A bare arithmetic expression used as condition is invalid.
        """
        if self._has_bool_op(node):
            return   # valid
        # bare expression — not a valid boolean condition
        msg = (f"[SEMANTIC ERROR] Line {line}: "
               f"invalid boolean condition — no relational operator found")
        self.errors.append(msg)
        indent = "  " * self.st.level
        print(f"{indent}│  ✗ {msg}")

    def _has_bool_op(self, node: Node) -> bool:
        if isinstance(node, BinOp):
            if node.op in self.RELOPS:
                return True
            return self._has_bool_op(node.left) or self._has_bool_op(node.right)
        if isinstance(node, UnaryOp) and node.op == '!':
            return True
        return False

    # ── Type inference ────────────────────────────────────────────────

    def _infer_type(self, node: Node) -> Optional[str]:
        """
        Infer the type of an expression.
        Returns 'int', 'float', or None on error.
        Also does lookup for identifiers and undeclared-var checking.
        """
        if isinstance(node, IntLiteral):
            return 'int'

        if isinstance(node, FloatLiteral):
            return 'float'

        if isinstance(node, Identifier):
            entry = self.st.lookup(node.name, node.line)
            if entry:
                indent = "  " * self.st.level
                print(f"{indent}│  LOOKUP  {node.name:<12} → found "
                      f"type={entry.data_type} scope=[{entry.scope_name}] "
                      f"level={entry.scope_level} offset={entry.offset}")
                return entry.data_type
            return None

        if isinstance(node, UnaryOp):
            t = self._infer_type(node.operand)
            return t

        if isinstance(node, BinOp):
            lt = self._infer_type(node.left)
            rt = self._infer_type(node.right)
            if lt is None or rt is None:
                return None
            # bool ops return int (0/1)
            if node.op in self.RELOPS:
                return 'int'
            # arithmetic: if either side is float → result is float
            if 'float' in (lt, rt):
                return 'float'
            return 'int'

        return None


# ═══════════════════════════════════════════════════════════════════════
#  Runner
# ═══════════════════════════════════════════════════════════════════════

def run(source: str, label: str):
    print("\n" + "█"*70)
    print(f"  SOURCE: {label}")
    print("█"*70)

    # Step 1: Lex
    lex = Lexer(source)
    tokens = lex.tokenize()
    if lex.errors:
        for e in lex.errors:
            print(f"  LEXICAL ERROR: {e}")
        return

    # Step 2: Parse → AST
    p = Parser(tokens)
    ast = p.parse()
    if p.errors:
        print("  PARSER ERRORS:")
        for e in p.errors:
            print(f"    {e}")
        return

    print(f"\n  ✔ Lexer: {len(tokens)} tokens   ✔ Parser: AST built\n")
    print("  ─── Q2: Symbol Table + Q3: Semantic Analysis ───\n")

    # Step 3: Symbol table + semantic analysis
    st       = SymbolTable()
    analyzer = SemanticAnalyzer(st)
    analyzer.analyze(ast)

    # Step 4: Print full symbol table
    st.print_full_table()

    # Step 5: Summary
    print("\n" + "="*72)
    print("  Q3 — SEMANTIC ANALYSIS RESULTS")
    print("="*72)
    if st.errors:
        print(f"  {len(st.errors)} error(s) found:\n")
        for e in st.errors:
            print(f"  ✗ {e}")
    else:
        print("  ✔  No semantic errors — program is semantically valid.")
    print("="*72)


# ═══════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    files = [a for a in sys.argv[1:] if not a.startswith("--")]

    if "--demo" in sys.argv:
        # ── Demo 1: redeclaration ────────────────────────────────────
        run("""int x;
int x;
x = 1;
""", "Demo 1 — redeclaration in same scope")

        # ── Demo 2: undeclared variable ──────────────────────────────
        run("""int a;
a = b + 1;
""", "Demo 2 — undeclared variable 'b'")

        # ── Demo 3: type mismatch ────────────────────────────────────
        run("""int a;
float b;
b = 3.14;
a = b;
""", "Demo 3 — type mismatch: assigning float to int")

        # ── Demo 4: invalid boolean condition ────────────────────────
        run("""int a;
int b;
a = 5;
b = 3;
if (a) {
    b = 1;
}
""", "Demo 4 — invalid boolean condition (no relop)")

    elif files:
        for fname in files:
            try:
                with open(fname) as f:
                    src = f.read()
                run(src, fname)
            except FileNotFoundError:
                print(f"\nError: File not found: {fname}")
    else:
        print("\nUsage:")
        print("  python semantic_analyzer.py test_program.src")
        print("  python semantic_analyzer.py --demo   (show all error cases)")
        print("\nOr enter source code (type END when done):")
        lines = []
        try:
            while True:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
        except EOFError:
            pass
        if lines:
            run("\n".join(lines), "<stdin>")
        else:
            try:
                with open("test_program.src") as f:
                    src = f.read()
                run(src, "test_program.src")
            except FileNotFoundError:
                print("No input. Pass a filename or type END after your code.")
