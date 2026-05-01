#pragma once
#include "symbol_table.h"

// semantic.h — Phase 5 (Compre Q3): walks the AST and catches type/scope errors

class SemanticAnalyzer {
    SymbolTable&   symTab;
    vector<string> errors;

    void err(const string& msg) { errors.push_back("[SEMANTIC ERROR] " + msg); }

    // recursively figures out the type of an expression node — returns "int", "float", "bool", or "" on error
    string typeOf(Node* n) {
        if (!n) return "";

        if (n->label == "NUMBER")    return "int";
        if (n->label == "FLOAT_LIT") return "float";

        // look up variable type from symbol table
        if (n->label == "ID") {
            const Symbol* s = symTab.lookup(n->value);
            if (!s) { err("Use of undeclared variable '" + n->value + "'"); return ""; }
            return s->type;
        }

        // unary minus — same type as its operand
        if (n->label == "unary_expr")
            return typeOf(n->kids.size() > 1 ? n->kids[1] : nullptr);

        // arithmetic: int op int = int, float op float = float, mixed widens to float
        if (n->label == "add_expr" || n->label == "mul_expr") {
            string l = typeOf(n->kids[0]);
            string r = typeOf(n->kids[2]);
            if (l.empty() || r.empty()) return "";
            if (l == r) return l;
            if ((l=="int"&&r=="float") || (l=="float"&&r=="int")) return "float";
            err("Type mismatch in arithmetic: '" + l + "' vs '" + r + "'");
            return "";
        }

        // relational operators always produce a bool result
        if (n->label == "rel_expr") {
            string l = typeOf(n->kids[0]);
            string r = typeOf(n->kids[2]);
            if (!l.empty() && !r.empty() && l != r)
                if (!((l=="int"&&r=="float")||(l=="float"&&r=="int")))
                    err("Type mismatch in comparison: '" + l + "' vs '" + r + "'");
            return "bool";
        }

        // logical operators — just recurse into operands, result is bool
        if (n->label == "or_expr" || n->label == "and_expr") {
            typeOf(n->kids[0]); typeOf(n->kids[2]); return "bool";
        }

        // logical NOT
        if (n->label == "not_expr") {
            typeOf(n->kids.size() > 1 ? n->kids[1] : n->kids[0]); return "bool";
        }

        // parenthesised expression — look inside
        if (n->label == "paren_expr") return typeOf(n->kids[1]);

        return "";
    }

    void check(Node* n) {
        if (!n) return;

        // declaration: insert into symbol table, flag duplicate
        if (n->label == "decl_stmt") {
            // kids[0]=type  kids[1]=ID  (optional: kids[2]=ASSIGN kids[3]=expr)  last=SEMI
            string typeName = n->kids[0]->value;
            string varName  = n->kids[1]->value;
            if (!symTab.insert(varName, typeName))
                err("Multiple declaration of '" + varName +
                    "' in scope " + to_string(symTab.scopeLevel()));
            // if there's an initializer, type-check the RHS expression
            if (n->kids.size() >= 4 && n->kids[2]->label == "ASSIGN") {
                string t = typeOf(n->kids[3]);
                if (!t.empty() && t != "bool" && typeName == "int" && t == "float")
                    err("Type mismatch: cannot assign float to int variable '" + varName + "'");
            }
            symTab.printTable(); // show table state after every declaration
            return;
        }

        // assignment: check variable exists, then check RHS type matches LHS type
        if (n->label == "assign_stmt") {
            const Symbol* s = symTab.lookup(n->kids[0]->value);
            if (!s) {
                err("Assignment to undeclared variable '" + n->kids[0]->value + "'");
            } else {
                string t = typeOf(n->kids[2]);
                if (!t.empty() && t != "bool" && s->type == "int" && t == "float")
                    err("Type mismatch: cannot assign float to int variable '" + n->kids[0]->value + "'");
            }
            return;
        }

        // if/while: check condition is not a plain int (must be relational/bool)
        if (n->label == "if_stmt" || n->label == "while_stmt") {
            Node* cond = nullptr;
            for (auto* k : n->kids)
                if (k->label!="IF" && k->label!="WHILE" && k->label!="ELSE" &&
                    k->label!="LPAREN" && k->label!="RPAREN" && k->label!="block")
                { cond = k; break; }
            string kw = (n->label == "if_stmt") ? "if" : "while";
            if (typeOf(cond) == "int")
                err("Invalid boolean condition in '" + kw +
                    "': expression has type 'int' (expected relational/bool)");
            // recurse into the body blocks with a new scope each
            for (auto* k : n->kids) if (k->label == "block") checkBlock(k);
            return;
        }

        // print: just validate the expression inside
        if (n->label == "print_stmt") {
            for (auto* k : n->kids)
                if (k->label!="PRINT"&&k->label!="LPAREN"&&k->label!="RPAREN"&&k->label!="SEMI")
                    typeOf(k);
            return;
        }

        // block: push a new scope, check all statements inside, then pop
        if (n->label == "block") { checkBlock(n); return; }

        // program / stmt_list: just recurse
        for (auto* k : n->kids) check(k);
    }

    // enter a new scope, check everything inside the block, exit scope
    void checkBlock(Node* blk) {
        symTab.enterScope();
        for (auto* k : blk->kids) check(k);
        symTab.exitScope();
    }

public:
    explicit SemanticAnalyzer(SymbolTable& st) : symTab(st) {}

    // entry point — call this with the root node from the parser
    void analyze(Node* root) {
        symTab.enterScope(); // scope 0 = global
        for (auto* k : root->kids) check(k);
        symTab.exitScope();
    }

    bool                   hasErrors() const { return !errors.empty(); }
    const vector<string>&  getErrors() const { return errors; }
};
