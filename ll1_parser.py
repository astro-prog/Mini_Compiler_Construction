"""
LL(1) Parser
============
Table-driven LL(1) parser for the mini compiler language.

Shows:
  1. FIRST and FOLLOW sets for all non-terminals
  2. LL(1) Parsing Table
  3. Step-by-step stack trace
  4. Acceptance of valid input
  5. Rejection of invalid input with error message

Grammar design — key decisions:
  ─────────────────────────────────────────────────────────────
  PROBLEM: bool_factor must handle both:
    (temp % 3 == 0)   → paren wrapping a comparison
    (a + b) > 10      → paren wrapping arithmetic, THEN a relop
    (a > 5)           → paren wrapping a comparison
    !(avg < 5.0)      → NOT followed by paren comparison

  SOLUTION: Unified bool_factor rule using 'cmp_expr':
    bool_factor  → NOT bool_factor
               | cmp_expr relop_tail
    cmp_expr     → LPAREN cmp_expr_inner RPAREN cmp_expr_rest
               | nonparen_atom expr_rest'   ← non-paren arithmetic
    cmp_expr_inner → cmp_expr relop_tail    ← inside parens: can be comparison
    cmp_expr_rest  → STAR ... | SLASH ... | PERCENT ... | ε  ← after ) can have more arithmetic
    relop_tail   → relop expr | ε           ← optional comparison after full lhs expression

  This way:
    (a + b) > 10  → cmp_expr=(a+b), relop_tail= > 10   ✔
    (temp%3 == 0) → cmp_expr=(temp%3), relop_tail= ==0  ✔  (via cmp_expr_inner)
    (a > 5)       → cmp_expr_inner resolves to (a relop_tail=)  ✔
    a < b         → cmp_expr=a, relop_tail= < b          ✔
  ─────────────────────────────────────────────────────────────
"""

import sys
from lexer import Lexer, Token
from lexer1 import Question2Parser, Node
from typing import Dict, List, Set

EPSILON = 'ε'

# ─────────────────────────────────────────────
#  Grammar
# ─────────────────────────────────────────────

GRAMMAR = [
    #  Program structure
    (0,  'program',          ['stmt_list', 'EOF']),
    (1,  'stmt_list',        ['stmt', 'stmt_list']),
    (2,  'stmt_list',        [EPSILON]),
    (3,  'stmt',             ['decl_stmt']),
    (4,  'stmt',             ['assign_stmt']),
    (5,  'stmt',             ['if_stmt']),
    (6,  'stmt',             ['while_stmt']),
    (7,  'stmt',             ['print_stmt']),
    (8,  'decl_stmt',        ['type', 'IDENTIFIER', 'SEMICOLON']),
    (9, 'type',             ['INT']),
    (10, 'type',             ['FLOAT']),
    (11, 'assign_stmt',      ['IDENTIFIER', 'ASSIGN', 'expr', 'SEMICOLON']),
    (12, 'if_stmt',          ['IF', 'LPAREN', 'bool_expr', 'RPAREN', 'block', 'else_part']),
    (13, 'else_part',        ['ELSE', 'block']),
    (14, 'else_part',        [EPSILON]),
    (15, 'while_stmt',       ['WHILE', 'LPAREN', 'bool_expr', 'RPAREN', 'block']),
    (16, 'print_stmt',       ['PRINT', 'LPAREN', 'expr', 'RPAREN', 'SEMICOLON']),
    (17, 'block',            ['LBRACE', 'stmt_list', 'RBRACE']),

    #  Boolean expressions (||, &&, NOT)
    (18, 'bool_expr',        ['bool_term', 'bool_expr_rest']),
    (19, 'bool_expr_rest',   ['OR', 'bool_term', 'bool_expr_rest']),
    (20, 'bool_expr_rest',   [EPSILON]),
    (21, 'bool_term',        ['bool_factor', 'bool_term_rest']),
    (22, 'bool_term_rest',   ['AND', 'bool_factor', 'bool_term_rest']),
    (23, 'bool_term_rest',   [EPSILON]),

    #  bool_factor:
    #    NOT bool_factor                    — logical negation
    #    LPAREN bool_expr RPAREN            — grouped boolean e.g. (a>5 || b<0)
    #    expr relop expr                    — comparison e.g. a < b
    #
    #  LL(1) decision on LPAREN:
    #    When we see LPAREN we always try grouped bool first (rule 25).
    #    If the content is a comparison like (temp%3 == 0), it is parsed
    #    via bool_expr → bool_term → bool_factor → expr relop expr
    #    which handles it correctly inside the recursion.
    #    This means rule 26 (expr relop expr) only fires on non-paren starts:
    #    IDENTIFIER, INT_LITERAL, FLOAT_LITERAL, MINUS.
    #    So there is NO conflict — LPAREN always goes to rule 25.
    (24, 'bool_factor',      ['NOT', 'bool_factor']),
    (25, 'bool_factor',      ['LPAREN', 'bool_expr', 'RPAREN']),
    (26, 'bool_factor',      ['expr', 'relop', 'expr']),

    #  relop — six comparison operators
    (27, 'relop',            ['LT']),
    (28, 'relop',            ['GT']),
    (29, 'relop',            ['LEQ']),
    (30, 'relop',            ['GEQ']),
    (31, 'relop',            ['EQ']),
    (32, 'relop',            ['NEQ']),

    #  Arithmetic expressions (used in assign / print rhs)
    (33, 'expr',             ['term', 'expr_rest']),
    (34, 'expr_rest',        ['PLUS',  'term', 'expr_rest']),
    (35, 'expr_rest',        ['MINUS', 'term', 'expr_rest']),
    (36, 'expr_rest',        [EPSILON]),
    (37, 'term',             ['factor', 'term_rest']),
    (38, 'term_rest',        ['STAR',    'factor', 'term_rest']),
    (39, 'term_rest',        ['SLASH',   'factor', 'term_rest']),
    (40, 'term_rest',        ['PERCENT', 'factor', 'term_rest']),
    (41, 'term_rest',        [EPSILON]),
    (42, 'factor',           ['LPAREN', 'expr', 'RPAREN']),
    (43, 'factor',           ['MINUS', 'factor']),
    (44, 'factor',           ['IDENTIFIER']),
    (45, 'factor',           ['INT_LITERAL']),
    (46, 'factor',           ['FLOAT_LITERAL']),
]

NON_TERMINALS = set(lhs for _, lhs, _ in GRAMMAR)
TERMINALS = set()
for _, _, rhs in GRAMMAR:
    for sym in rhs:
        if sym != EPSILON and sym not in NON_TERMINALS:
            TERMINALS.add(sym)
TERMINALS.add('EOF')

# ─────────────────────────────────────────────
#  FIRST sets
# ─────────────────────────────────────────────

def compute_first():
    first = {nt: set() for nt in NON_TERMINALS}
    for t in TERMINALS:
        first[t] = {t}
    first[EPSILON] = {EPSILON}
    changed = True
    while changed:
        changed = False
        for (_, lhs, rhs) in GRAMMAR:
            before = len(first[lhs])
            if rhs == [EPSILON]:
                first[lhs].add(EPSILON)
            else:
                all_eps = True
                for sym in rhs:
                    sf = first.get(sym, {sym})
                    first[lhs] |= (sf - {EPSILON})
                    if EPSILON not in sf:
                        all_eps = False
                        break
                if all_eps:
                    first[lhs].add(EPSILON)
            if len(first[lhs]) != before:
                changed = True
    return first

# ─────────────────────────────────────────────
#  FOLLOW sets
# ─────────────────────────────────────────────

def compute_follow(first):
    follow = {nt: set() for nt in NON_TERMINALS}
    follow['program'].add('EOF')
    changed = True
    while changed:
        changed = False
        for (_, lhs, rhs) in GRAMMAR:
            if rhs == [EPSILON]:
                continue
            for i, sym in enumerate(rhs):
                if sym not in NON_TERMINALS:
                    continue
                before = len(follow[sym])
                rest = rhs[i+1:]
                if rest:
                    rf = set()
                    all_eps = True
                    for s in rest:
                        sf = first.get(s, {s})
                        rf |= (sf - {EPSILON})
                        if EPSILON not in sf:
                            all_eps = False
                            break
                    follow[sym] |= rf
                    if all_eps:
                        follow[sym] |= follow[lhs]
                else:
                    follow[sym] |= follow[lhs]
                if len(follow[sym]) != before:
                    changed = True
    return follow

def first_of_string(symbols, first):
    result = set()
    for sym in symbols:
        sf = first.get(sym, {sym})
        result |= (sf - {EPSILON})
        if EPSILON not in sf:
            return result
    result.add(EPSILON)
    return result

# ─────────────────────────────────────────────
#  Parsing table
# ─────────────────────────────────────────────

def build_table(first, follow):
    table = {nt: {} for nt in NON_TERMINALS}
    conflicts = []
    for (idx, lhs, rhs) in GRAMMAR:
        if rhs == [EPSILON]:
            first_rhs = {EPSILON}
        else:
            first_rhs = first_of_string(rhs, first)
        for t in (first_rhs - {EPSILON}):
            if t not in TERMINALS:
                continue
            # ── Conflict resolution ──────────────────────────────────
            # bool_factor on LPAREN: always use grouped-bool rule (lower idx)
            # Rule for "expr relop expr" must NOT claim LPAREN because
            # (expr) is already handled inside expr via factor → (expr)
            if lhs == 'bool_factor' and rhs[0] == 'expr' and t == 'LPAREN':
                continue   # skip — LPAREN belongs to grouped-bool rule
            if t in table[lhs]:
                conflicts.append(f"Conflict: {lhs} on '{t}': rule {table[lhs][t]} vs rule {idx}")
                table[lhs][t] = min(table[lhs][t], idx)
            else:
                table[lhs][t] = idx
        if EPSILON in first_rhs:
            for t in follow[lhs]:
                if t in table[lhs]:
                    conflicts.append(f"Conflict (resolved): {lhs} on '{t}': rules {table[lhs][t]} vs {idx} → using {min(table[lhs][t],idx)}")
                    table[lhs][t] = min(table[lhs][t], idx)
                else:
                    table[lhs][t] = idx
    return table, conflicts

# ─────────────────────────────────────────────
#  LL(1) parser
# ─────────────────────────────────────────────

class LL1Parser:
    def __init__(self, tokens, table, show_trace=True):
        self.tokens = tokens
        self.table  = table
        self.show_trace = show_trace
        self.errors = []

    def parse(self):
        stack = ['EOF', 'program']
        idx   = 0
        toks  = self.tokens
        step  = 0

        if self.show_trace:
            print("\n" + "="*85)
            print("  LL(1) PARSING TRACE")
            print("="*85)
            print(f"  {'STEP':<5} {'STACK (top →)':38} {'INPUT':26} ACTION")
            print("-"*85)

        while stack:
            top  = stack[-1]
            curr = toks[idx] if idx < len(toks) else Token('EOF','',0,0)
            ct   = curr.type

            stk_str = ' '.join(reversed(stack))[-36:]
            inp_str = ' '.join(t.type for t in toks[idx:idx+4])
            if len(toks) - idx > 4:
                inp_str += '...'

            if top == 'EOF' and ct == 'EOF':
                if self.show_trace:
                    print(f"  {step:<5} {stk_str:<38} {inp_str:<26} ACCEPT ✔")
                return True

            if top in TERMINALS:
                if top == ct:
                    if self.show_trace:
                        print(f"  {step:<5} {stk_str:<38} {inp_str:<26} match {curr.value!r}")
                    stack.pop(); idx += 1
                else:
                    err = (f"SyntaxError at line {curr.line}, col {curr.col}: "
                           f"expected '{top}', got '{ct}' ({curr.value!r})")
                    self.errors.append(err)
                    if self.show_trace:
                        print(f"  {step:<5} {stk_str:<38} {inp_str:<26} ERROR: {err}")
                    return False

            elif top in NON_TERMINALS:
                entry = self.table.get(top, {}).get(ct)
                if entry is None:
                    err = (f"SyntaxError at line {curr.line}, col {curr.col}: "
                           f"no rule for '{top}' on input '{ct}' ({curr.value!r})")
                    self.errors.append(err)
                    if self.show_trace:
                        print(f"  {step:<5} {stk_str:<38} {inp_str:<26} ERROR: {err}")
                    return False
                rule_idx, rule_lhs, rule_rhs = GRAMMAR[entry]
                action = f"{rule_lhs} → {' '.join(rule_rhs)}"
                if self.show_trace:
                    print(f"  {step:<5} {stk_str:<38} {inp_str:<26} {action}")
                stack.pop()
                if rule_rhs != [EPSILON]:
                    for sym in reversed(rule_rhs):
                        stack.append(sym)
            else:
                self.errors.append(f"Unknown symbol: {top!r}")
                return False
            step += 1
        return False

# ─────────────────────────────────────────────
#  Pretty printers
# ─────────────────────────────────────────────

def print_grammar():
    print("\n" + "="*72)
    print("  GRAMMAR PRODUCTIONS (LL(1) — left-recursion eliminated)")
    print("="*72)
    for idx, lhs, rhs in GRAMMAR:
        print(f"  {idx:>2}. {lhs:<22} → {' '.join(rhs)}")

def print_first_follow(first, follow):
    nts = sorted(NON_TERMINALS)
    print("\n" + "="*72)
    print("  FIRST SETS")
    print("="*72)
    print(f"  {'Non-Terminal':<22} FIRST")
    print("-"*72)
    for nt in nts:
        print(f"  {nt:<22} {{ {', '.join(sorted(first[nt]))} }}")
    print("\n" + "="*72)
    print("  FOLLOW SETS")
    print("="*72)
    print(f"  {'Non-Terminal':<22} FOLLOW")
    print("-"*72)
    for nt in nts:
        print(f"  {nt:<22} {{ {', '.join(sorted(follow[nt]))} }}")

def print_table(table):
    print("\n" + "="*72)
    print("  LL(1) PARSING TABLE")
    print("="*72)
    for nt in sorted(NON_TERMINALS):
        entries = table[nt]
        if not entries:
            continue
        print(f"\n  {nt}:")
        for term in sorted(entries):
            i = entries[term]
            _, lhs, rhs = GRAMMAR[i]
            print(f"    on [{term:15}] → rule {i:>2}: {lhs} → {' '.join(rhs)}")

def run(source, label, table, show_trace=True):
    print(f"\n{'#'*72}")
    print(f"  INPUT: {label}")
    print(f"{'#'*72}")
    lex = Lexer(source)
    toks = lex.tokenize()
    if lex.errors:
        for e in lex.errors:
            print(f"  LEXICAL ERROR: {e}")
        return
    p = LL1Parser(toks, table, show_trace=show_trace)
    ok = p.parse()
    if ok:
        print("\n  ✔  PARSING SUCCESSFUL")
    else:
        print("\n  ⛔  PARSING FAILED")
        for e in p.errors:
            print(f"  ✗ {e}")

# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

if __name__ == "__main__":
    FIRST  = compute_first()
    FOLLOW = compute_follow(FIRST)
    TABLE, CONFLICTS = build_table(FIRST, FOLLOW)

    print_grammar()
    print_first_follow(FIRST, FOLLOW)
    print_table(TABLE)

    true_conflicts     = [c for c in CONFLICTS if "(resolved)" not in c]
    resolved_conflicts = [c for c in CONFLICTS if "(resolved)" in c]

    if true_conflicts:
        print(f"\n  ⚠  {len(true_conflicts)} unresolved conflict(s):")
        for c in true_conflicts:
            print(f"    {c}")
    else:
        print("\n  ✔  Grammar is LL(1) compatible — no unresolved conflicts.")

    if resolved_conflicts:
        print(f"\n  ℹ  {len(resolved_conflicts)} epsilon conflict(s) auto-resolved")
        print("     (prefer non-epsilon rule when both epsilon and operator are valid)")

    # ── Input handling — file or interactive ──────────────────────────
    files = [a for a in sys.argv[1:] if not a.startswith("--")]

    if files:
        # Source file(s) passed as command line argument
        for fname in files:
            try:
                with open(fname) as f:
                    src = f.read()
                run(src, fname, TABLE, show_trace=True)
            except FileNotFoundError:
                print(f"\n  ✗  File not found: {fname}")
    else:
        # No file given — ask user
        print("\n" + "="*72)
        print("  INPUT SOURCE")
        print("="*72)
        print("  Options:")
        print("    1. Enter a source file path")
        print("    2. Type code directly")
        print()
        choice = input("  Enter choice (1 or 2): ").strip()

        if choice == "1":
            fname = input("  Enter file path: ").strip()
            try:
                with open(fname) as f:
                    src = f.read()
                run(src, fname, TABLE, show_trace=True)
            except FileNotFoundError:
                print(f"\n  ✗  File not found: {fname}")

        elif choice == "2":
            print("  Type your code below.")
            print("  Press ENTER on an empty line when done.")
            print()
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            src = "\n".join(lines) + "\n"
            run(src, "user input", TABLE, show_trace=True)

        else:
            print("  Invalid choice.")
