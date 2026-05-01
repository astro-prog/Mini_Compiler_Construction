#pragma once
#include "parser.h"
#include <iomanip>

//  TAC (Three-Address Code) — Intermediate Code Genration

struct Quad {
    string op;
    string arg1;
    string arg2;
    string result;
};

class TACGenerator {
    vector<Quad> quads;
    int tempCount = 0;
    int labelCount = 0;

    string newTemp() {
        return "t" + to_string(++tempCount);
    }

    string newLabel() {
        return "L" + to_string(++labelCount);
    }

    void emit(const string& op, const string& arg1 = "", const string& arg2 = "", const string& result = "") {
        quads.push_back({op, arg1, arg2, result});
    }

    Node* safeKid(Node* n, size_t idx) {
        if (!n || idx >= n->kids.size()) return nullptr;
        return n->kids[idx];
    }

    string genExpr(Node* n) {
        if (!n) return "";

        if (n->label == "NUMBER" || n->label == "FLOAT_LIT" || n->label == "ID") {
            return n->value;
        }

        if (n->label == "paren_expr") {
            return genExpr(safeKid(n, 1));
        }

        if (n->label == "unary_expr") {
            Node* rhsNode = safeKid(n, 1);
            string rhs = genExpr(rhsNode);
            string t = newTemp();
            emit("uminus", rhs, "", t);
            return t;
        }

        if (n->label == "not_expr") {
            Node* rhsNode = safeKid(n, 1);
            if (!rhsNode) rhsNode = safeKid(n, 0);
            string rhs = genExpr(rhsNode);
            string t = newTemp();
            emit("!", rhs, "", t);
            return t;
        }

        if (n->label == "add_expr" || n->label == "mul_expr" ||
            n->label == "rel_expr" || n->label == "and_expr" || n->label == "or_expr") {
            string lhs = genExpr(safeKid(n, 0));
            string rhs = genExpr(safeKid(n, 2));
            Node* opNode = safeKid(n, 1);
            string op = opNode ? opNode->value : "?";
            string t = newTemp();
            emit(op, lhs, rhs, t);
            return t;
        }

        // Best-effort fallback so simple/partially malformed trees still produce output.
        if (!n->kids.empty()) {
            string last;
            for (Node* k : n->kids) last = genExpr(k);
            return last;
        }

        return n->value;
    }

    void genStmt(Node* n) {
        if (!n) return;

        if (n->label == "decl_stmt") {
            // Optional initializer: type ID = expr ;
            if (n->kids.size() >= 4 && n->kids[2]->label == "ASSIGN") {
                string lhs = n->kids[1]->value;
                string rhs = genExpr(n->kids[3]);
                emit("=", rhs, "", lhs);
            }
            return;
        }

        if (n->label == "assign_stmt") {
            string lhs = safeKid(n, 0) ? n->kids[0]->value : "";
            string rhs = genExpr(safeKid(n, 2));
            emit("=", rhs, "", lhs);
            return;
        }

        if (n->label == "print_stmt") {
            string val = genExpr(safeKid(n, 2));
            emit("print", val, "", "");
            return;
        }

        if (n->label == "if_stmt") {
            // if (cond) block [else block]
            string cond = genExpr(safeKid(n, 2));
            string lElse = newLabel();
            string lEnd = newLabel();

            emit("ifFalse", cond, "", lElse);
            genBlock(safeKid(n, 4));

            if (n->kids.size() > 5) {
                emit("goto", "", "", lEnd);
                emit("label", "", "", lElse);
                genBlock(safeKid(n, 6));
                emit("label", "", "", lEnd);
            } else {
                emit("label", "", "", lElse);
            }
            return;
        }

        if (n->label == "while_stmt") {
            // while (cond) block
            string lStart = newLabel();
            string lEnd = newLabel();

            emit("label", "", "", lStart);
            string cond = genExpr(safeKid(n, 2));
            emit("ifFalse", cond, "", lEnd);
            genBlock(safeKid(n, 4));
            emit("goto", "", "", lStart);
            emit("label", "", "", lEnd);
            return;
        }

        if (n->label == "block") {
            genBlock(n);
            return;
        }

        if (n->label == "stmt_list" || n->label == "program") {
            for (Node* k : n->kids) genStmt(k);
            return;
        }

        // Fallback for any simple extension nodes.
        for (Node* k : n->kids) genStmt(k);
    }

    void genBlock(Node* blockNode) {
        if (!blockNode) return;
        for (Node* k : blockNode->kids) {
            if (k && k->label == "stmt_list") {
                for (Node* stmt : k->kids) genStmt(stmt);
                return;
            }
        }
        for (Node* k : blockNode->kids) genStmt(k);
    }

public:
    void generate(Node* root) {
        quads.clear();
        tempCount = 0;
        labelCount = 0;
        genStmt(root);
    }

    const vector<Quad>& getQuads() const {
        return quads;
    }

    void print() const {
        cout << "Representation: QUADRUPLES\n\n";
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
        if (quads.empty()) cout << "<no TAC emitted>\n";
    }
};
