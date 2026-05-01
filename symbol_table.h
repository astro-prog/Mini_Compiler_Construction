#pragma once
#include "parser.h"

// symbol_table.h — Phase 4 (Compre Q2): stores every declared variable with name, type, scope, offset

// one entry per declared variable
struct Symbol {
    string name;
    string type;    // "int" or "float"
    int    scope;   // 0 = global, 1 = first nested block, 2 = deeper, etc.
    int    offset;  // byte offset within its scope frame, increments by 4 per variable
};

class SymbolTable {
    vector<map<string,Symbol>> scopeStack;  // each element is one scope frame
    int                        currentScope;
    vector<int>                offsetCounter; // tracks next offset for each scope frame
    vector<string>             log;           // records every insert/lookup/scope transition

public:
    SymbolTable() : currentScope(-1) {}

    // called when entering { — pushes a new empty scope frame
    void enterScope() {
        ++currentScope;
        scopeStack.push_back({});
        offsetCounter.push_back(0);
        log.push_back("[Scope] Entered scope level " + to_string(currentScope));
    }

    // called when leaving } — pops the scope frame, variables in it are gone
    void exitScope() {
        log.push_back("[Scope] Exiting scope level " + to_string(currentScope) +
                      "  (" + to_string(scopeStack.back().size()) + " symbol(s) released)");
        scopeStack.pop_back();
        offsetCounter.pop_back();
        --currentScope;
    }

    // inserts variable into current scope — returns false if already declared in this scope
    bool insert(const string& name, const string& type) {
        auto& top = scopeStack.back();
        if (top.count(name)) {
            log.push_back("[Insert] FAILED - '" + name + "' already declared in scope " + to_string(currentScope));
            return false;
        }
        int off = offsetCounter.back();
        top[name] = {name, type, currentScope, off};
        offsetCounter.back() += 4;  // both int and float are 4 bytes
        log.push_back("[Insert] '" + name + "'  type=" + type +
                      "  scope=" + to_string(currentScope) +
                      "  offset=" + to_string(off));
        return true;
    }

    // searches innermost scope outward — returns nullptr if not found anywhere
    const Symbol* lookup(const string& name) {
        for (int i = (int)scopeStack.size()-1; i >= 0; --i) {
            auto it = scopeStack[i].find(name);
            if (it != scopeStack[i].end()) {
                log.push_back("[Lookup] '" + name + "' found  type=" + it->second.type +
                              "  scope=" + to_string(it->second.scope) +
                              "  offset=" + to_string(it->second.offset));
                return &it->second;
            }
        }
        log.push_back("[Lookup] '" + name + "' NOT FOUND");
        return nullptr;
    }

    int scopeLevel() const { return currentScope; }

    // prints every symbol currently visible (all active scope frames)
    void printTable() const {
        cout << "\nSymbol Table  (active scope = " << currentScope << ")\n";
        cout << string(62, '-') << "\n";
        cout << left << setw(15) << "Name" << setw(8) << "Type"
             << setw(8) << "Scope" << setw(10) << "Offset" << "\n";
        cout << string(62, '-') << "\n";
        for (auto& frame : scopeStack)
            for (auto& kv : frame) {
                auto& s = kv.second;
                cout << setw(15) << s.name << setw(8) << s.type
                     << setw(8)  << s.scope << setw(10) << s.offset << "\n";
            }
        cout << string(62, '-') << "\n";
    }

    // prints the full insert/lookup/scope log in order
    void printLog() const {
        cout << "\nSymbol Table Step-by-Step Log:\n";
        for (auto& e : log) cout << "  " << e << "\n";
    }
};
