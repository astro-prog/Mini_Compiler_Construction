#pragma once
#include "tac.h"
#include <sstream>
#include <set>
#include <map>

//  Optimizations applied to the quadruple stream:
//    1. Constant Folding         — compute constant arith at compile time
//    2. Algebraic Simplification — x+0, x*1, x*0, x-0 reductions
//    3. Constant Propagation     — replace uses of vars proven constant
//    4. Dead Code Elimination    — drop assignments whose result is never read
//
//  Target code generator emits a small register-based pseudo-assembly
//  (LOAD / STORE / ADD / SUB / MUL / DIV / MOD / CMP / branches / PRINT)
//  with two scratch registers R1, R2 — enough to demonstrate translation
//  of arithmetic, control flow (if/else, while), and I/O.

class Optimizer {
    vector<Quad> quads;

    static bool isIntLiteral(const string& s) {
        if (s.empty()) return false;
        size_t i = (s[0] == '-' || s[0] == '+') ? 1 : 0;
        if (i >= s.size()) return false;
        for (; i < s.size(); ++i) if (!isdigit((unsigned char)s[i])) return false;
        return true;
    }

    static bool isFloatLiteral(const string& s) {
        if (s.empty()) return false;
        bool dot = false, digit = false;
        size_t i = (s[0] == '-' || s[0] == '+') ? 1 : 0;
        for (; i < s.size(); ++i) {
            if (s[i] == '.') { if (dot) return false; dot = true; }
            else if (isdigit((unsigned char)s[i])) digit = true;
            else return false;
        }
        return dot && digit;
    }

    static bool isNumber(const string& s) {
        return isIntLiteral(s) || isFloatLiteral(s);
    }

    static string foldArith(const string& op, const string& a, const string& b) {
        // Returns "" if not foldable.
        if (!isNumber(a) || !isNumber(b)) return "";
        bool fp = isFloatLiteral(a) || isFloatLiteral(b);
        if (fp) {
            double x = stod(a), y = stod(b), r = 0;
            if (op == "+") r = x + y;
            else if (op == "-") r = x - y;
            else if (op == "*") r = x * y;
            else if (op == "/") { if (y == 0) return ""; r = x / y; }
            else return "";
            ostringstream os; os << r; return os.str();
        }
        long long x = stoll(a), y = stoll(b), r = 0;
        if (op == "+") r = x + y;
        else if (op == "-") r = x - y;
        else if (op == "*") r = x * y;
        else if (op == "/") { if (y == 0) return ""; r = x / y; }
        else if (op == "%") { if (y == 0) return ""; r = x % y; }
        else if (op == "<")  r = (x <  y);
        else if (op == ">")  r = (x >  y);
        else if (op == "<=") r = (x <= y);
        else if (op == ">=") r = (x >= y);
        else if (op == "==") r = (x == y);
        else if (op == "!=") r = (x != y);
        else if (op == "&&") r = (x && y);
        else if (op == "||") r = (x || y);
        else return "";
        return to_string(r);
    }

    static bool isArith(const string& op) {
        return op == "+" || op == "-" || op == "*" || op == "/" || op == "%" ||
               op == "<" || op == ">" || op == "<=" || op == ">=" ||
               op == "==" || op == "!=" || op == "&&" || op == "||";
    }

    // Constant folding + algebraic simplification + simple constant propagation.
    void foldAndPropagate() {
        map<string, string> constEnv;  // var -> constant literal known at this point

        auto resolve = [&](const string& s) -> string {
            if (s.empty() || isNumber(s)) return s;
            auto it = constEnv.find(s);
            return (it != constEnv.end()) ? it->second : s;
        };

        // A label or jump invalidates our linear constant environment because
        // control may re-enter from elsewhere. Conservative: clear at labels.
        for (auto& q : quads) {
            if (q.op == "label") { constEnv.clear(); continue; }

            if (q.op == "=") {
                string r = resolve(q.arg1);
                q.arg1 = r;
                if (isNumber(r)) constEnv[q.result] = r;
                else             constEnv.erase(q.result);
                continue;
            }

            if (isArith(q.op)) {
                string a = resolve(q.arg1);
                string b = resolve(q.arg2);
                q.arg1 = a; q.arg2 = b;

                string folded = foldArith(q.op, a, b);
                if (!folded.empty()) {
                    q.op = "="; q.arg1 = folded; q.arg2 = "";
                    constEnv[q.result] = folded;
                    continue;
                }

                // Algebraic simplifications.
                if (q.op == "+" && a == "0") { q.op = "="; q.arg1 = b; q.arg2 = ""; constEnv.erase(q.result); continue; }
                if (q.op == "+" && b == "0") { q.op = "="; q.arg1 = a; q.arg2 = ""; constEnv.erase(q.result); continue; }
                if (q.op == "-" && b == "0") { q.op = "="; q.arg1 = a; q.arg2 = ""; constEnv.erase(q.result); continue; }
                if (q.op == "*" && (a == "1")) { q.op = "="; q.arg1 = b; q.arg2 = ""; constEnv.erase(q.result); continue; }
                if (q.op == "*" && (b == "1")) { q.op = "="; q.arg1 = a; q.arg2 = ""; constEnv.erase(q.result); continue; }
                if (q.op == "*" && (a == "0" || b == "0")) {
                    q.op = "="; q.arg1 = "0"; q.arg2 = ""; constEnv[q.result] = "0"; continue;
                }
                constEnv.erase(q.result);
                continue;
            }

            if (q.op == "uminus") {
                string a = resolve(q.arg1); q.arg1 = a;
                if (isNumber(a)) {
                    string v = (a[0] == '-') ? a.substr(1) : ("-" + a);
                    q.op = "="; q.arg1 = v; constEnv[q.result] = v;
                } else constEnv.erase(q.result);
                continue;
            }

            if (q.op == "ifFalse" || q.op == "print") {
                q.arg1 = resolve(q.arg1);
                continue;
            }

            if (q.op == "goto") continue;

            if (!q.result.empty()) constEnv.erase(q.result);
        }
    }

    static bool isTemp(const string& s) {
        return !s.empty() && s[0] == 't' && s.size() > 1 &&
               all_of(s.begin()+1, s.end(), [](char c){ return isdigit((unsigned char)c); });
    }

    // Dead code elimination: remove assignments to temps that are never used.
    // Conservative — only eliminates compiler-generated temporaries (t1, t2, ...),
    // never user variables, since those may be observed outside this routine.
    void deadCodeElim() {
        bool changed = true;
        while (changed) {
            changed = false;
            set<string> used;
            for (auto& q : quads) {
                if (!q.arg1.empty()) used.insert(q.arg1);
                if (!q.arg2.empty()) used.insert(q.arg2);
                // For control / sink ops the "result" slot holds a label or is empty.
                if (q.op == "ifFalse" || q.op == "goto" || q.op == "label" ||
                    q.op == "print"   || q.op == "call") {
                    if (!q.result.empty()) used.insert(q.result);
                }
            }
            vector<Quad> kept;
            kept.reserve(quads.size());
            for (auto& q : quads) {
                bool defsTemp = (q.op == "=" || isArith(q.op) || q.op == "uminus" || q.op == "!")
                                && isTemp(q.result);
                if (defsTemp && !used.count(q.result)) { changed = true; continue; }
                kept.push_back(q);
            }
            quads.swap(kept);
        }
    }

public:
    void load(const vector<Quad>& src) { quads = src; }

    void run() {
        foldAndPropagate();
        deadCodeElim();
    }

    const vector<Quad>& getQuads() const { return quads; }
};

//  Target Code Generator

class TargetCodeGen {
    vector<string> code;

    static bool isNumber(const string& s) {
        if (s.empty()) return false;
        size_t i = (s[0] == '-' || s[0] == '+') ? 1 : 0;
        bool dot = false, digit = false;
        for (; i < s.size(); ++i) {
            if (s[i] == '.') { if (dot) return false; dot = true; }
            else if (isdigit((unsigned char)s[i])) digit = true;
            else return false;
        }
        return digit;
    }

    void load(const string& reg, const string& src) {
        if (isNumber(src)) code.push_back("    LOAD   " + reg + ", #" + src);
        else               code.push_back("    LOAD   " + reg + ", " + src);
    }

    static string opMnemonic(const string& op) {
        if (op == "+") return "ADD";
        if (op == "-") return "SUB";
        if (op == "*") return "MUL";
        if (op == "/") return "DIV";
        if (op == "%") return "MOD";
        if (op == "&&") return "AND";
        if (op == "||") return "OR";
        return "";
    }

    static string relBranchTrue(const string& op) {
        // Branch-if-true mnemonics for relational ops (CMP R1, R2 first).
        if (op == "<")  return "BLT";
        if (op == ">")  return "BGT";
        if (op == "<=") return "BLE";
        if (op == ">=") return "BGE";
        if (op == "==") return "BEQ";
        if (op == "!=") return "BNE";
        return "";
    }

    static string relBranchFalse(const string& op) {
        if (op == "<")  return "BGE";
        if (op == ">")  return "BLE";
        if (op == "<=") return "BGT";
        if (op == ">=") return "BLT";
        if (op == "==") return "BNE";
        if (op == "!=") return "BEQ";
        return "";
    }

public:
    void generate(const vector<Quad>& quads) {
        code.clear();
        code.push_back("; pseudo-assembly target code");
        code.push_back("; registers: R1, R2 (scratch)");
        code.push_back("    .text");

        for (size_t i = 0; i < quads.size(); ++i) {
            const Quad& q = quads[i];

            if (q.op == "label") {
                code.push_back(q.result + ":");
                continue;
            }

            if (q.op == "goto") {
                code.push_back("    JMP    " + q.result);
                continue;
            }

            if (q.op == "=") {
                load("R1", q.arg1);
                code.push_back("    STORE  " + q.result + ", R1");
                continue;
            }

            if (q.op == "uminus") {
                load("R1", q.arg1);
                code.push_back("    NEG    R1");
                code.push_back("    STORE  " + q.result + ", R1");
                continue;
            }

            if (q.op == "!") {
                load("R1", q.arg1);
                code.push_back("    NOT    R1");
                code.push_back("    STORE  " + q.result + ", R1");
                continue;
            }

            if (q.op == "print") {
                load("R1", q.arg1);
                code.push_back("    PRINT  R1");
                continue;
            }

            // ifFalse cond goto L  — fuse with the producing relop if possible.
            if (q.op == "ifFalse") {
                // Look back one quad: if it produced q.arg1 from a relop, fuse it.
                if (i > 0) {
                    const Quad& prev = quads[i-1];
                    string mnem = relBranchFalse(prev.op);
                    if (!mnem.empty() && prev.result == q.arg1) {
                        // Replace the previously emitted store-of-temp sequence
                        // with a direct CMP+branch by re-emitting; simplest
                        // approach: emit a redundant CMP here from the stored
                        // operands. We didn't drop prev's emission, so just
                        // emit the conditional jump using prev's operands.
                        load("R1", prev.arg1);
                        load("R2", prev.arg2);
                        code.push_back("    CMP    R1, R2");
                        code.push_back("    " + mnem + "    " + q.result);
                        continue;
                    }
                }
                load("R1", q.arg1);
                code.push_back("    LOAD   R2, #0");
                code.push_back("    CMP    R1, R2");
                code.push_back("    BEQ    " + q.result);
                continue;
            }

            // Relational op producing a boolean temp (used when not fused).
            string rb = relBranchTrue(q.op);
            if (!rb.empty()) {
                load("R1", q.arg1);
                load("R2", q.arg2);
                code.push_back("    CMP    R1, R2");
                code.push_back("    LOAD   R1, #0");
                code.push_back("    " + rb + "    .+2");          // skip next on true
                code.push_back("    JMP    .+1");
                code.push_back("    LOAD   R1, #1");
                code.push_back("    STORE  " + q.result + ", R1");
                continue;
            }

            // Plain arithmetic / logical.
            string m = opMnemonic(q.op);
            if (!m.empty()) {
                load("R1", q.arg1);
                load("R2", q.arg2);
                code.push_back("    " + m + "    R1, R2");
                code.push_back("    STORE  " + q.result + ", R1");
                continue;
            }

            code.push_back("    ; <unhandled op: " + q.op + ">");
        }

        code.push_back("    HALT");
    }

    void print() const {
        for (auto& line : code) cout << line << "\n";
    }
};

// Convenience: print quad table for a given quad list (used to show before/after).
inline void printQuads(const vector<Quad>& quads) {
    cout << left
         << setw(6)  << "#"
         << setw(14) << "op"
         << setw(14) << "arg1"
         << setw(14) << "arg2"
         << setw(14) << "result" << "\n";
    cout << string(62, '-') << "\n";
    for (size_t i = 0; i < quads.size(); ++i) {
        cout << setw(6)  << i
             << setw(14) << quads[i].op
             << setw(14) << quads[i].arg1
             << setw(14) << quads[i].arg2
             << setw(14) << quads[i].result
             << "\n";
    }
    if (quads.empty()) cout << "<no quads>\n";
}
