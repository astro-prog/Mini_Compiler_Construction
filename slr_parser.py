"""
SLR(1) Parser
=============
Implements a table-driven SLR(1) / LR(0) parser for the mini compiler language.

Shows:
  1. Augmented grammar
  2. LR(0) canonical items (states)
  3. FIRST and FOLLOW sets
  4. ACTION and GOTO table construction
  5. Step-by-step stack trace (stack | input | action)
  6. Acceptance of valid input
  7. Rejection of invalid input with error message

Note: Due to the complexity of the full grammar, we implement SLR(1) on a
      representative subset (expressions + declarations + assignments) and
      show the full structure. The full grammar's SLR table is printed.
"""

import sys
from lexer import Lexer, Token
from lexer1 import Question2Parser, Node
from typing import Dict, List, Set, Tuple, Optional, FrozenSet
from collections import defaultdict

# ─────────────────────────────────────────────
#  Augmented Grammar (simplified for SLR demo)
#  We use a clean, non-left-recursive grammar
#  suitable for LR(0) item construction.
# ─────────────────────────────────────────────

EPSILON = 'ε'
EOF_SYM = '$'
DOT = '•'
AUGMENTED_START = "program'"

# Grammar as list of (lhs, rhs_tuple)
# Rule 0 is always the augmented start rule
RAW_GRAMMAR = [
    ("program'",     ("program",)),
    ("program",      ("stmt_list",)),
    ("stmt_list",    ("stmt", "stmt_list")),
    ("stmt_list",    ()),                          # ε
    ("stmt",         ("decl_stmt",)),
    ("stmt",         ("assign_stmt",)),
    ("stmt",         ("if_stmt",)),
    ("stmt",         ("while_stmt",)),
    ("stmt",         ("print_stmt",)),
    ("decl_stmt",    ("type", "id", "SEMICOLON")),
    ("type",         ("INT",)),
    ("type",         ("FLOAT",)),
    ("assign_stmt",  ("id", "ASSIGN", "expr", "SEMICOLON")),
    ("if_stmt",      ("IF", "LPAREN", "bool_expr", "RPAREN", "block", "else_part")),
    ("else_part",    ("ELSE", "block")),
    ("else_part",    ()),                          # ε
    ("while_stmt",   ("WHILE", "LPAREN", "bool_expr", "RPAREN", "block")),
    ("print_stmt",   ("PRINT", "LPAREN", "expr", "RPAREN", "SEMICOLON")),
    ("block",        ("LBRACE", "stmt_list", "RBRACE")),
    ("bool_expr",    ("bool_term", "bool_expr_rest")),
    ("bool_expr_rest", ("OR", "bool_term", "bool_expr_rest")),
    ("bool_expr_rest", ()),
    ("bool_term",    ("bool_factor", "bool_term_rest")),
    ("bool_term_rest", ("AND", "bool_factor", "bool_term_rest")),
    ("bool_term_rest", ()),
    ("bool_factor",  ("NOT", "bool_factor")),
    ("bool_factor",  ("LPAREN", "bool_expr", "RPAREN")),
    ("bool_factor",  ("expr", "relop", "expr")),
    ("relop",        ("LT",)),
    ("relop",        ("GT",)),
    ("relop",        ("LEQ",)),
    ("relop",        ("GEQ",)),
    ("relop",        ("EQ",)),
    ("relop",        ("NEQ",)),
    ("expr",         ("term", "expr_rest")),
    ("expr_rest",    ("PLUS",  "term", "expr_rest")),
    ("expr_rest",    ("MINUS", "term", "expr_rest")),
    ("expr_rest",    ()),
    ("term",         ("factor", "term_rest")),
    ("term_rest",    ("STAR",    "factor", "term_rest")),
    ("term_rest",    ("SLASH",   "factor", "term_rest")),
    ("term_rest",    ("PERCENT", "factor", "term_rest")),
    ("term_rest",    ()),
    ("factor",       ("LPAREN", "expr", "RPAREN")),
    ("factor",       ("MINUS", "factor")),
    ("factor",       ("id",)),
    ("factor",       ("INT_LITERAL",)),
    ("factor",       ("FLOAT_LITERAL",)),
    # id is IDENTIFIER
    ("id",           ("IDENTIFIER",)),
]

ALL_NON_TERMINALS = set(lhs for lhs, _ in RAW_GRAMMAR)
ALL_TERMINALS = set()
for _, rhs in RAW_GRAMMAR:
    for sym in rhs:
        if sym not in ALL_NON_TERMINALS:
            ALL_TERMINALS.add(sym)
ALL_TERMINALS.add(EOF_SYM)

# ─────────────────────────────────────────────
#  FIRST and FOLLOW (reused from LL1 approach)
# ─────────────────────────────────────────────

def compute_first_slr(grammar):
    first = {}
    for nt in ALL_NON_TERMINALS:
        first[nt] = set()
    for t in ALL_TERMINALS:
        first[t] = {t}

    changed = True
    while changed:
        changed = False
        for lhs, rhs in grammar:
            before = len(first.get(lhs, set()))
            if not rhs:  # epsilon
                first.setdefault(lhs, set()).add(EPSILON)
            else:
                all_eps = True
                for sym in rhs:
                    sym_f = first.get(sym, {sym})
                    first.setdefault(lhs, set()).update(sym_f - {EPSILON})
                    if EPSILON not in sym_f:
                        all_eps = False
                        break
                if all_eps:
                    first.setdefault(lhs, set()).add(EPSILON)
            if len(first.get(lhs, set())) != before:
                changed = True
    return first

def first_of_string(symbols, first):
    result = set()
    for sym in symbols:
        sf = first.get(sym, {sym})
        result |= (sf - {EPSILON})
        if EPSILON not in sf:
            return result
    result.add(EPSILON)
    return result

def compute_follow_slr(grammar, first):
    follow = {nt: set() for nt in ALL_NON_TERMINALS}
    follow[AUGMENTED_START].add(EOF_SYM)
    follow['program'].add(EOF_SYM)

    changed = True
    while changed:
        changed = False
        for lhs, rhs in grammar:
            if not rhs:
                continue
            for i, sym in enumerate(rhs):
                if sym not in ALL_NON_TERMINALS:
                    continue
                before = len(follow[sym])
                rest = rhs[i+1:]
                rf = first_of_string(rest, first) if rest else {EPSILON}
                follow[sym] |= (rf - {EPSILON})
                if EPSILON in rf:
                    follow[sym] |= follow[lhs]
                if len(follow[sym]) != before:
                    changed = True
    return follow

# ─────────────────────────────────────────────
#  LR(0) Items and Canonical Collection
# ─────────────────────────────────────────────

class Item:
    """LR(0) item: (rule_index, dot_position)"""
    def __init__(self, rule_idx: int, dot: int):
        self.rule_idx = rule_idx
        self.dot = dot

    def lhs(self):
        return RAW_GRAMMAR[self.rule_idx][0]

    def rhs(self):
        return RAW_GRAMMAR[self.rule_idx][1]

    def after_dot(self):
        rhs = self.rhs()
        if self.dot < len(rhs):
            return rhs[self.dot]
        return None

    def is_complete(self):
        return self.dot >= len(self.rhs())

    def __eq__(self, other):
        return self.rule_idx == other.rule_idx and self.dot == other.dot

    def __hash__(self):
        return hash((self.rule_idx, self.dot))

    def __repr__(self):
        lhs = self.lhs()
        rhs = list(self.rhs())
        rhs.insert(self.dot, DOT)
        return f"[{lhs} → {' '.join(rhs) if rhs else DOT}]"


def closure(items: FrozenSet[Item]) -> FrozenSet[Item]:
    result = set(items)
    changed = True
    while changed:
        changed = False
        for item in list(result):
            sym = item.after_dot()
            if sym and sym in ALL_NON_TERMINALS:
                for idx, (lhs, rhs) in enumerate(RAW_GRAMMAR):
                    if lhs == sym:
                        new_item = Item(idx, 0)
                        if new_item not in result:
                            result.add(new_item)
                            changed = True
    return frozenset(result)


def goto(items: FrozenSet[Item], symbol: str) -> FrozenSet[Item]:
    moved = set()
    for item in items:
        if item.after_dot() == symbol:
            moved.add(Item(item.rule_idx, item.dot + 1))
    return closure(frozenset(moved)) if moved else frozenset()


def canonical_collection(start_rule_idx=0):
    start_item = Item(start_rule_idx, 0)
    start_state = closure(frozenset([start_item]))
    states = [start_state]
    state_map = {start_state: 0}
    transitions = {}  # (state_idx, symbol) -> state_idx

    worklist = [start_state]
    while worklist:
        state = worklist.pop(0)
        state_idx = state_map[state]
        # Find all symbols after dot
        symbols = set()
        for item in state:
            sym = item.after_dot()
            if sym:
                symbols.add(sym)
        for sym in symbols:
            next_state = goto(state, sym)
            if not next_state:
                continue
            if next_state not in state_map:
                state_map[next_state] = len(states)
                states.append(next_state)
                worklist.append(next_state)
            transitions[(state_idx, sym)] = state_map[next_state]

    return states, state_map, transitions

# ─────────────────────────────────────────────
#  SLR(1) Table Construction
# ─────────────────────────────────────────────

def build_slr_table(states, transitions, follow):
    action = {}  # (state, terminal) -> ('shift', state) | ('reduce', rule_idx) | ('accept',)
    goto_table = {}  # (state, non_terminal) -> state
    conflicts = []

    for state_idx, state in enumerate(states):
        for item in state:
            sym = item.after_dot()

            if sym and sym in ALL_TERMINALS:
                # Shift
                if (state_idx, sym) in transitions:
                    next_state = transitions[(state_idx, sym)]
                    key = (state_idx, sym)
                    new_action = ('shift', next_state)
                    if key in action and action[key] != new_action:
                        conflicts.append(f"S/R conflict at state {state_idx} on '{sym}'")
                    action[key] = new_action

            elif sym and sym in ALL_NON_TERMINALS:
                # Goto
                if (state_idx, sym) in transitions:
                    goto_table[(state_idx, sym)] = transitions[(state_idx, sym)]

            elif item.is_complete():
                lhs = item.lhs()
                if lhs == AUGMENTED_START:
                    action[(state_idx, EOF_SYM)] = ('accept',)
                else:
                    rule_idx = item.rule_idx
                    for terminal in follow.get(lhs, set()):
                        key = (state_idx, terminal)
                        new_action = ('reduce', rule_idx)
                        if key in action and action[key] != new_action:
                            conflicts.append(f"Conflict at state {state_idx} on '{terminal}': {action[key]} vs {new_action}")
                        else:
                            action[key] = new_action

    return action, goto_table, conflicts

# ─────────────────────────────────────────────
#  SLR(1) Parser (table-driven)
# ─────────────────────────────────────────────

class SLRParser:
    def __init__(self, tokens: List[Token], action, goto_table, show_trace=True):
        self.tokens = tokens
        self.action = action
        self.goto_table = goto_table
        self.show_trace = show_trace
        self.errors = []

    def token_to_sym(self, tok: Token) -> str:
        """Map token type to grammar symbol."""
        if tok.type == 'IDENTIFIER':
            return 'IDENTIFIER'
        return tok.type if tok.type != 'EOF' else EOF_SYM

    def parse(self):
        stack = [0]           # state stack
        sym_stack = ['$']     # symbol stack (for display)
        token_idx = 0
        tokens = self.tokens
        step = 0

        if self.show_trace:
            print("\n" + "="*90)
            print("  SLR(1) PARSING TRACE")
            print("="*90)
            print(f"  {'STEP':<5} {'STACK':30} {'INPUT':30} {'ACTION'}")
            print("-"*90)

        while True:
            state = stack[-1]
            curr = tokens[token_idx] if token_idx < len(tokens) else Token('EOF','',0,0)
            curr_sym = self.token_to_sym(curr)

            stack_str = ' '.join(str(s) for s in stack[-8:])
            input_str = ' '.join(self.token_to_sym(tokens[i]) for i in range(token_idx, min(token_idx+5, len(tokens))))

            key = (state, curr_sym)
            act = self.action.get(key)

            if act is None:
                err = f"SyntaxError at line {curr.line}, col {curr.col}: unexpected '{curr_sym}' ({curr.value!r}) in state {state}"
                self.errors.append(err)
                if self.show_trace:
                    print(f"  {step:<5} {stack_str:<30} {input_str:<30} ERROR")
                return False

            if act[0] == 'accept':
                if self.show_trace:
                    print(f"  {step:<5} {stack_str:<30} {input_str:<30} ACCEPT ✔")
                return True

            elif act[0] == 'shift':
                next_state = act[1]
                if self.show_trace:
                    print(f"  {step:<5} {stack_str:<30} {input_str:<30} shift → state {next_state}")
                stack.append(next_state)
                sym_stack.append(curr_sym)
                token_idx += 1

            elif act[0] == 'reduce':
                rule_idx = act[1]
                lhs, rhs = RAW_GRAMMAR[rule_idx]
                rhs_len = len(rhs)
                rule_str = f"{lhs} → {' '.join(rhs) if rhs else 'ε'}"
                if self.show_trace:
                    print(f"  {step:<5} {stack_str:<30} {input_str:<30} reduce by rule {rule_idx}: {rule_str}")
                if rhs_len > 0:
                    stack = stack[:-rhs_len]
                    sym_stack = sym_stack[:-rhs_len]
                top_state = stack[-1]
                goto_key = (top_state, lhs)
                if goto_key not in self.goto_table:
                    err = f"No GOTO entry for state {top_state} on '{lhs}'"
                    self.errors.append(err)
                    return False
                stack.append(self.goto_table[goto_key])
                sym_stack.append(lhs)

            step += 1
            if step > 10000:
                self.errors.append("Parser exceeded step limit — possible infinite loop")
                return False

# ─────────────────────────────────────────────
#  Pretty printers
# ─────────────────────────────────────────────

def print_first_follow_slr(first, follow):
    nts = sorted(ALL_NON_TERMINALS)
    print("\n" + "="*70)
    print("  FIRST SETS")
    print("="*70)
    print(f"  {'Non-Terminal':<22} FIRST")
    print("-"*70)
    for nt in nts:
        fs = ', '.join(sorted(first.get(nt, set())))
        print(f"  {nt:<22} {{ {fs} }}")

    print("\n" + "="*70)
    print("  FOLLOW SETS")
    print("="*70)
    print(f"  {'Non-Terminal':<22} FOLLOW")
    print("-"*70)
    for nt in nts:
        fw = ', '.join(sorted(follow.get(nt, set())))
        print(f"  {nt:<22} {{ {fw} }}")

def print_lr0_items(states):
    print("\n" + "="*70)
    print("  LR(0) CANONICAL ITEMS (first 15 states)")
    print("="*70)
    for i, state in enumerate(states[:15]):
        print(f"\n  State {i}:")
        for item in sorted(state, key=lambda x: (x.rule_idx, x.dot)):
            print(f"    {item}")
    if len(states) > 15:
        print(f"\n  ... ({len(states)-15} more states not shown)")
    print(f"\n  Total states: {len(states)}")

def print_slr_table(action, goto_table, states):
    print("\n" + "="*70)
    print("  SLR(1) ACTION TABLE (sample — first 20 states)")
    print("="*70)
    sample_terms = ['INT','FLOAT','IDENTIFIER','ASSIGN','SEMICOLON',
                    'PLUS','MINUS','STAR','LPAREN','RPAREN','IF','WHILE','$']
    header = f"  {'State':<6}" + "".join(f"{t:<12}" for t in sample_terms)
    print(header)
    print("-"*70)
    for s in range(min(20, len(states))):
        row = f"  {s:<6}"
        for t in sample_terms:
            act = action.get((s, t))
            if act is None:
                row += f"{'':12}"
            elif act[0] == 'shift':
                row += f"{'s'+str(act[1]):<12}"
            elif act[0] == 'reduce':
                row += f"{'r'+str(act[1]):<12}"
            elif act[0] == 'accept':
                row += f"{'acc':<12}"
        print(row)

    print("\n" + "="*70)
    print("  SLR(1) GOTO TABLE (sample — first 20 states)")
    print("="*70)
    sample_nts = ['program','stmt_list','stmt','expr','term','factor',
                  'decl_stmt','assign_stmt','bool_expr','type']
    header2 = f"  {'State':<6}" + "".join(f"{nt[:10]:<12}" for nt in sample_nts)
    print(header2)
    print("-"*70)
    for s in range(min(20, len(states))):
        row = f"  {s:<6}"
        for nt in sample_nts:
            g = goto_table.get((s, nt))
            row += f"{str(g) if g is not None else '':<12}"
        print(row)

def print_grammar_slr():
    print("\n" + "="*70)
    print("  AUGMENTED GRAMMAR")
    print("="*70)
    for i, (lhs, rhs) in enumerate(RAW_GRAMMAR):
        rhs_str = ' '.join(rhs) if rhs else 'ε'
        print(f"  {i:>2}. {lhs:<22} → {rhs_str}")

# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def run_slr(source, label, action, goto_table, show_trace=True):
    print(f"\n{'#'*70}")
    print(f"  INPUT: {label}")
    print(f"{'#'*70}")
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    if lexer.errors:
        for e in lexer.errors:
            print(f"  LEXICAL ERROR: {e}")
        return

    parser = SLRParser(tokens, action, goto_table, show_trace=show_trace)
    result = parser.parse()

    if result:
        print("\n  ✔  PARSING SUCCESSFUL")
    else:
        print("\n  ⛔  PARSING FAILED")
        for e in parser.errors:
            print(f"  ✗ {e}")


if __name__ == "__main__":
    print("Building SLR(1) parser...")

    FIRST  = compute_first_slr(RAW_GRAMMAR)
    FOLLOW = compute_follow_slr(RAW_GRAMMAR, FIRST)

    print("Computing LR(0) canonical items...")
    STATES, STATE_MAP, TRANSITIONS = canonical_collection(start_rule_idx=0)
    print(f"  Total LR(0) states: {len(STATES)}")

    ACTION, GOTO_TABLE, CONFLICTS = build_slr_table(STATES, TRANSITIONS, FOLLOW)

    # ── Print everything ──────────────────────
    print_grammar_slr()
    print_first_follow_slr(FIRST, FOLLOW)
    print_lr0_items(STATES)
    print_slr_table(ACTION, GOTO_TABLE, STATES)

    # Separate dangling-else S/R (standard, always resolved by shift)
    # from true ambiguity conflicts
    sr_conflicts = [c for c in CONFLICTS if "S/R" in c]
    rr_conflicts = [c for c in CONFLICTS if "S/R" not in c]

    if rr_conflicts:
        print(f"\n  ⚠  {len(rr_conflicts)} reduce-reduce conflict(s):")
        for c in rr_conflicts[:10]:
            print(f"    {c}")
    else:
        print("\n  ✔  No reduce-reduce conflicts.")

    if sr_conflicts:
        print(f"\n  ℹ  {len(sr_conflicts)} shift-reduce conflict(s) — resolved by preferring shift:")
        for c in sr_conflicts:
            print(f"    {c}")
        print("     (Dangling-else is a classic S/R conflict — shift = attach else to nearest if)")

    # ── Input handling — file or interactive ──────────────────────────
    files = [a for a in sys.argv[1:] if not a.startswith("--")]

    if files:
        # Source file(s) passed as command line argument
        for fname in files:
            try:
                with open(fname) as f:
                    src = f.read()
                run_slr(src, fname, ACTION, GOTO_TABLE, show_trace=True)
            except FileNotFoundError:
                print(f"\n  ✗  File not found: {fname}")
    else:
        # No file given — ask user
        print("\n" + "="*70)
        print("  INPUT SOURCE")
        print("="*70)
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
                run_slr(src, fname, ACTION, GOTO_TABLE, show_trace=True)
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
            run_slr(src, "user input", ACTION, GOTO_TABLE, show_trace=True)

        else:
            print("  Invalid choice.")
