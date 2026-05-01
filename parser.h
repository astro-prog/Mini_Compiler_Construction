#pragma once
#include "lexer.h"

//  PARSER  —  Phase 2: Recursive-Descent Parser
//  Builds a parse tree (AST) from the token stream.

struct Node {
    string        label;
    string        value;
    vector<Node*> kids;

    Node(const string& lbl, const string& val = "") : label(lbl), value(val) {}
    ~Node() { for (Node* k : kids) delete k; }
    void add(Node* k) { if (k) kids.push_back(k); }
};

void printTree(const Node* n, const string& pfx = "", bool last = true) {
    if (!n) return;
    cout << pfx << (last ? "\\--- " : "+--- ");
    cout << n->label;
    if (!n->value.empty()) cout << " [" << n->value << "]";
    cout << "\n";
    string np = pfx + (last ? "     " : "|    ");
    for (size_t i = 0; i < n->kids.size(); ++i)
        printTree(n->kids[i], np, i == n->kids.size() - 1);
}

class Parser {
    const vector<Token>& toks;
    size_t               pos;
    vector<string>       errs;

    Token cur() const { return pos < toks.size() ? toks[pos] : Token{TokenType::END_OF_FILE,"$",0}; }
    Token eat()       { return pos < toks.size() ? toks[pos++] : Token{TokenType::END_OF_FILE,"$",0}; }
    bool  check(TokenType t) const { return cur().type == t; }

    Node* expect(TokenType t, const string& what) {
        if (cur().type == t) { Token tk = eat(); return new Node(tokenName(t), tk.text); }
        errs.push_back("Line " + to_string(cur().line) +
                       ": Expected '" + what + "' but got '" + cur().text + "'");
        return new Node("SYNTAX_ERROR", "?");
    }

    void sync() {
        while (!check(TokenType::SEMI) && !check(TokenType::RBRACE) && !check(TokenType::END_OF_FILE)) eat();
        if (check(TokenType::SEMI)) eat();
    }

    Node* parseProgram() {
        Node* n = new Node("program");
        n->add(parseStmtList());
        n->add(expect(TokenType::END_OF_FILE, "$"));
        return n;
    }

    Node* parseStmtList() {
        Node* n = new Node("stmt_list");
        while (!check(TokenType::END_OF_FILE) && !check(TokenType::RBRACE)) {
            Node* s = parseStmt(); if (s) n->add(s); else sync();
        }
        return n;
    }

    Node* parseStmt() {
        if (check(TokenType::INT)   || check(TokenType::FLOAT)) return parseDeclStmt();
        if (check(TokenType::ID))                               return parseAssignStmt();
        if (check(TokenType::IF))                               return parseIfStmt();
        if (check(TokenType::WHILE))                            return parseWhileStmt();
        if (check(TokenType::PRINT))                            return parsePrintStmt();
        if (check(TokenType::LBRACE))                           return parseBlock();
        errs.push_back("Line " + to_string(cur().line) + ": Unexpected token '" + cur().text + "'");
        eat(); return nullptr;
    }

    Node* parseDeclStmt() {
        Node* n = new Node("decl_stmt");
        Token t = eat();
        n->add(new Node("type", t.text));
        n->add(expect(TokenType::ID,   "identifier"));
        if (check(TokenType::ASSIGN)) {
            n->add(new Node("ASSIGN", eat().text));
            n->add(parseExpr());
        }
        n->add(expect(TokenType::SEMI, ";"));
        return n;
    }

    Node* parseAssignStmt() {
        Node* n = new Node("assign_stmt");
        Token id = eat();
        n->add(new Node("ID", id.text));
        n->add(expect(TokenType::ASSIGN, "="));
        n->add(parseExpr());
        n->add(expect(TokenType::SEMI, ";"));
        return n;
    }

    Node* parseIfStmt() {
        Node* n = new Node("if_stmt");
        n->add(new Node("IF", eat().text));
        n->add(expect(TokenType::LPAREN, "("));
        n->add(parseExpr());
        n->add(expect(TokenType::RPAREN, ")"));
        n->add(parseBlock());
        if (check(TokenType::ELSE)) { n->add(new Node("ELSE", eat().text)); n->add(parseBlock()); }
        return n;
    }

    Node* parseWhileStmt() {
        Node* n = new Node("while_stmt");
        n->add(new Node("WHILE", eat().text));
        n->add(expect(TokenType::LPAREN, "("));
        n->add(parseExpr());
        n->add(expect(TokenType::RPAREN, ")"));
        n->add(parseBlock());
        return n;
    }

    Node* parsePrintStmt() {
        Node* n = new Node("print_stmt");
        n->add(new Node("PRINT", eat().text));
        n->add(expect(TokenType::LPAREN, "("));
        n->add(parseExpr());
        n->add(expect(TokenType::RPAREN, ")"));
        n->add(expect(TokenType::SEMI, ";"));
        return n;
    }

    Node* parseBlock() {
        Node* n = new Node("block");
        n->add(expect(TokenType::LBRACE, "{"));
        n->add(parseStmtList());
        n->add(expect(TokenType::RBRACE, "}"));
        return n;
    }

    Node* parseExpr() { return parseOrExpr(); }

    Node* parseOrExpr() {
        Node* left = parseAndExpr();
        while (check(TokenType::OR)) {
            Node* n = new Node("or_expr");
            n->add(left); n->add(new Node("OR", eat().text)); n->add(parseAndExpr()); left = n;
        }
        return left;
    }

    Node* parseAndExpr() {
        Node* left = parseNotExpr();
        while (check(TokenType::AND)) {
            Node* n = new Node("and_expr");
            n->add(left); n->add(new Node("AND", eat().text)); n->add(parseNotExpr()); left = n;
        }
        return left;
    }

    Node* parseNotExpr() {
        if (check(TokenType::NOT)) {
            Node* n = new Node("not_expr");
            n->add(new Node("NOT", eat().text)); n->add(parseNotExpr()); return n;
        }
        return parseRelExpr();
    }

    Node* parseRelExpr() {
        Node* left = parseAddExpr();
        while (check(TokenType::EQ)||check(TokenType::NEQ)||check(TokenType::LT)||
               check(TokenType::GT)||check(TokenType::LTE)||check(TokenType::GTE)) {
            Node* n = new Node("rel_expr"); n->add(left);
            Token op = eat(); n->add(new Node("rel_op", op.text)); n->add(parseAddExpr()); left = n;
        }
        return left;
    }

    Node* parseAddExpr() {
        Node* left = parseMulExpr();
        while (check(TokenType::PLUS)||check(TokenType::MINUS)) {
            Node* n = new Node("add_expr"); n->add(left);
            Token op = eat(); n->add(new Node("add_op", op.text)); n->add(parseMulExpr()); left = n;
        }
        return left;
    }

    Node* parseMulExpr() {
        Node* left = parseUnary();
        while (check(TokenType::STAR)||check(TokenType::SLASH)||check(TokenType::MODULO)) {
            Node* n = new Node("mul_expr"); n->add(left);
            Token op = eat(); n->add(new Node("mul_op", op.text)); n->add(parseUnary()); left = n;
        }
        return left;
    }

    Node* parseUnary() {
        if (check(TokenType::MINUS)) {
            Node* n = new Node("unary_expr");
            n->add(new Node("MINUS", eat().text)); n->add(parseUnary()); return n;
        }
        return parsePrimary();
    }

    Node* parsePrimary() {
        if (check(TokenType::NUMBER))    { Token t = eat(); return new Node("NUMBER",    t.text); }
        if (check(TokenType::FLOAT_LIT)) { Token t = eat(); return new Node("FLOAT_LIT", t.text); }
        if (check(TokenType::ID))        { Token t = eat(); return new Node("ID",        t.text); }
        if (check(TokenType::LPAREN)) {
            Node* n = new Node("paren_expr");
            n->add(new Node("LPAREN", eat().text)); n->add(parseExpr()); n->add(expect(TokenType::RPAREN, ")")); return n;
        }
        errs.push_back("Line " + to_string(cur().line) + ": Expected primary expression but got '" + cur().text + "'");
        eat(); return new Node("SYNTAX_ERROR", "?");
    }

public:
    explicit Parser(const vector<Token>& t) : toks(t), pos(0) {}

    Node*                  parse()   { return parseProgram(); }
    const vector<string>&  errors()  const { return errs; }
    bool                   ok()      const { return errs.empty(); }
};
