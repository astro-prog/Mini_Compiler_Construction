#pragma once
#include <bits/stdc++.h>
using namespace std;

//  LEXER  —  Phase 1: Lexical Analysis
//  Reads source code and produces a stream of tokens.

enum class TokenType {
    INT, FLOAT, IF, ELSE, WHILE, RETURN, PRINT,
    ID, NUMBER, FLOAT_LIT,
    PLUS, MINUS, STAR, SLASH, MODULO,
    ASSIGN, EQ, LT, GT, LTE, GTE, NEQ,
    AND, OR, NOT,
    LPAREN, RPAREN, LBRACE, RBRACE, SEMI, COMMA,
    ERROR, END_OF_FILE
};

struct Token {
    TokenType type;
    string    text;
    int       line;
};

string tokenName(TokenType t) {
    switch (t) {
        case TokenType::INT:         return "INT";
        case TokenType::FLOAT:       return "FLOAT";
        case TokenType::IF:          return "IF";
        case TokenType::ELSE:        return "ELSE";
        case TokenType::WHILE:       return "WHILE";
        case TokenType::RETURN:      return "RETURN";
        case TokenType::PRINT:       return "PRINT";
        case TokenType::ID:          return "ID";
        case TokenType::NUMBER:      return "NUMBER";
        case TokenType::FLOAT_LIT:   return "FLOAT_LIT";
        case TokenType::PLUS:        return "PLUS";
        case TokenType::MINUS:       return "MINUS";
        case TokenType::STAR:        return "STAR";
        case TokenType::SLASH:       return "SLASH";
        case TokenType::MODULO:      return "MODULO";
        case TokenType::ASSIGN:      return "ASSIGN";
        case TokenType::EQ:          return "EQ";
        case TokenType::LT:          return "LT";
        case TokenType::GT:          return "GT";
        case TokenType::LTE:         return "LTE";
        case TokenType::GTE:         return "GTE";
        case TokenType::NEQ:         return "NEQ";
        case TokenType::AND:         return "AND";
        case TokenType::OR:          return "OR";
        case TokenType::NOT:         return "NOT";
        case TokenType::LPAREN:      return "LPAREN";
        case TokenType::RPAREN:      return "RPAREN";
        case TokenType::LBRACE:      return "LBRACE";
        case TokenType::RBRACE:      return "RBRACE";
        case TokenType::SEMI:        return "SEMI";
        case TokenType::COMMA:       return "COMMA";
        case TokenType::ERROR:       return "ERROR";
        case TokenType::END_OF_FILE: return "$";
        default:                     return "UNKNOWN";
    }
}

class Lexer {
    string src;
    size_t pos;
    int    line;

    void advance() { if (pos < src.size() && src[pos] == '\n') ++line; ++pos; }
    char peek() const { return pos < src.size() ? src[pos] : '\0'; }
    void skipWS()     { while (isspace(peek())) advance(); }

    TokenType toKeyword(const string& w) {
        if (w == "int")    return TokenType::INT;
        if (w == "float")  return TokenType::FLOAT;
        if (w == "if")     return TokenType::IF;
        if (w == "else")   return TokenType::ELSE;
        if (w == "while")  return TokenType::WHILE;
        if (w == "return") return TokenType::RETURN;
        if (w == "print")  return TokenType::PRINT;
        return TokenType::ID;
    }

public:
    Lexer(const string& s) : src(s), pos(0), line(1) {}

    Token next() {
        skipWS();
        int  l = line;
        char c = peek();

        if (c == '\0') return {TokenType::END_OF_FILE, "$", l};

        if (isalpha(c) || c == '_') {
            string b;
            while (isalnum(peek()) || peek() == '_') { b += peek(); advance(); }
            return {toKeyword(b), b, l};
        }

        if (isdigit(c)) {
            string b; bool flt = false;
            while (isdigit(peek()) || peek() == '.') {
                if (peek() == '.') flt = true;
                b += peek(); advance();
            }
            return flt ? Token{TokenType::FLOAT_LIT, b, l}
                       : Token{TokenType::NUMBER,    b, l};
        }

        advance();
        string s1(1, c);
        switch (c) {
            case '+': return {TokenType::PLUS,   "+", l};
            case '-': return {TokenType::MINUS,  "-", l};
            case '*': return {TokenType::STAR,   "*", l};
            case '/': return {TokenType::SLASH,  "/", l};
            case '%': return {TokenType::MODULO, "%", l};
            case '(': return {TokenType::LPAREN, "(", l};
            case ')': return {TokenType::RPAREN, ")", l};
            case '{': return {TokenType::LBRACE, "{", l};
            case '}': return {TokenType::RBRACE, "}", l};
            case ';': return {TokenType::SEMI,   ";", l};
            case ',': return {TokenType::COMMA,  ",", l};
            case '=': if (peek()=='='){advance();return{TokenType::EQ,  "==",l};} return{TokenType::ASSIGN,"=",l};
            case '!': if (peek()=='='){advance();return{TokenType::NEQ, "!=",l};} return{TokenType::NOT,   "!",l};
            case '<': if (peek()=='='){advance();return{TokenType::LTE, "<=",l};} return{TokenType::LT,    "<",l};
            case '>': if (peek()=='='){advance();return{TokenType::GTE, ">=",l};} return{TokenType::GT,    ">",l};
            case '&': if (peek()=='&'){advance();return{TokenType::AND, "&&",l};} return{TokenType::ERROR, s1, l};
            case '|': if (peek()=='|'){advance();return{TokenType::OR,  "||",l};} return{TokenType::ERROR, s1, l};
            default:  return {TokenType::ERROR, s1, l};
        }
    }
};

// Helper: lex entire source, print errors, return token list
vector<Token> runLexer(const string& src, bool& ok) {
    Lexer lx(src);
    vector<Token> toks;
    ok = true;
    while (true) {
        Token t = lx.next();
        if (t.type == TokenType::ERROR) {
            cout << "LEXICAL ERROR (line " << t.line << "): unrecognized character '" << t.text << "'\n";
            ok = false;
        } else {
            toks.push_back(t);
        }
        if (t.type == TokenType::END_OF_FILE) break;
    }
    return toks;
}
