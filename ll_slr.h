#pragma once
#include "lexer.h"

//  LL(1) + SLR PARSERS  —  Phase 3: Table-Driven Parsing
//  Includes: Grammar, FIRST/FOLLOW, LL(1) table, SLR table,
//            LR(0) automaton, parse traces.


struct Production {
    string         lhs;
    vector<string> rhs;
};

struct Grammar {
    vector<string>          nonterms;
    vector<string>          terms;
    string                  start;
    vector<Production>      prods;
    map<string,vector<int>> byLhs;
    unordered_set<string>   ntSet;

    void finalize() {
        byLhs.clear(); ntSet.clear();
        for (auto& nt : nonterms) ntSet.insert(nt);
        for (int i = 0; i < (int)prods.size(); ++i) byLhs[prods[i].lhs].push_back(i);
    }
    bool isNonTerm(const string& s) const { return ntSet.count(s) != 0; }
};

string joinToks(const vector<string>& v, size_t from = 0) {
    string out;
    for (size_t i = from; i < v.size(); ++i) { if (i > from) out += " "; out += v[i]; }
    return out;
}

string rhsStr(const vector<string>& rhs) {
    return (rhs.size()==1 && rhs[0]=="eps") ? "eps" : joinToks(rhs);
}

// ---- two grammars ----

Grammar buildLL1Grammar() {
    Grammar g;
    g.nonterms = {"S","S'","T","T'","E","E'","F","F'","G"};
    g.terms    = {"id","num","=","+","-","*","/","(",")",";","$"};
    g.start    = "S";
    g.prods    = {
        {"S",  {"T","S'"}},
        {"S'", {";","T","S'"}},
        {"S'", {"eps"}},
        {"T",  {"id","T'"}},
        {"T'", {"=","E"}},
        {"T'", {"eps"}},
        {"E",  {"F","E'"}},
        {"E'", {"+","F","E'"}},
        {"E'", {"-","F","E'"}},
        {"E'", {"eps"}},
        {"F",  {"G","F'"}},
        {"F'", {"*","G","F'"}},
        {"F'", {"/","G","F'"}},
        {"F'", {"eps"}},
        {"G",  {"(","E",")"}},
        {"G",  {"id"}},
        {"G",  {"num"}},
    };
    g.finalize(); return g;
}

Grammar buildSLRGrammar() {
    Grammar g;
    g.nonterms = {"S0","S","T","E","F","G"};
    g.terms    = {"id","num","=","+","-","*","/","(",")",";","$"};
    g.start    = "S0";
    g.prods    = {
        {"S0", {"S"}},
        {"S",  {"S",";","T"}},
        {"S",  {"T"}},
        {"T",  {"id","=","E"}},
        {"T",  {"id"}},
        {"E",  {"E","+","F"}},
        {"E",  {"E","-","F"}},
        {"E",  {"F"}},
        {"F",  {"F","*","G"}},
        {"F",  {"F","/","G"}},
        {"F",  {"G"}},
        {"G",  {"(","E",")"}},
        {"G",  {"id"}},
        {"G",  {"num"}},
    };
    g.finalize(); return g;
}

// ---- FIRST / FOLLOW ----

set<string> firstOfSeq(const vector<string>& seq, const map<string,set<string>>& first) {
    set<string> res;
    if (seq.empty() || (seq.size()==1 && seq[0]=="eps")) { res.insert("eps"); return res; }
    bool nullable = true;
    for (auto& sym : seq) {
        auto it = first.find(sym);
        if (it == first.end()) { res.insert(sym); nullable = false; break; }
        for (auto& x : it->second) if (x != "eps") res.insert(x);
        if (!it->second.count("eps")) { nullable = false; break; }
    }
    if (nullable) res.insert("eps");
    return res;
}

map<string,set<string>> computeFirst(const Grammar& g) {
    map<string,set<string>> first;
    first["eps"].insert("eps");
    for (auto& t  : g.terms)    first[t].insert(t);
    for (auto& nt : g.nonterms) first[nt];
    bool changed = true;
    while (changed) {
        changed = false;
        for (auto& p : g.prods)
            for (auto& x : firstOfSeq(p.rhs, first))
                if (first[p.lhs].insert(x).second) changed = true;
    }
    return first;
}

map<string,set<string>> computeFollow(const Grammar& g, const map<string,set<string>>& first) {
    map<string,set<string>> follow;
    for (auto& nt : g.nonterms) follow[nt];
    follow[g.start].insert("$");
    bool changed = true;
    while (changed) {
        changed = false;
        for (auto& p : g.prods) {
            for (size_t i = 0; i < p.rhs.size(); ++i) {
                if (!g.isNonTerm(p.rhs[i])) continue;
                vector<string> beta(p.rhs.begin()+i+1, p.rhs.end());
                set<string> fb = firstOfSeq(beta, first);
                for (auto& x : fb) if (x!="eps" && follow[p.rhs[i]].insert(x).second) changed = true;
                if (beta.empty() || fb.count("eps"))
                    for (auto& x : follow[p.lhs])
                        if (follow[p.rhs[i]].insert(x).second) changed = true;
            }
        }
    }
    return follow;
}

void printFirstFollow(const Grammar& g,
                      const map<string,set<string>>& first,
                      const map<string,set<string>>& follow) {
    cout << "FIRST Sets:\n";
    for (auto& nt : g.nonterms) {
        cout << "  FIRST(" << nt << ") = { ";
        bool f = true;
        for (auto& x : first.at(nt)) { if (!f) cout << ", "; cout << x; f = false; }
        cout << " }\n";
    }
    cout << "\nFOLLOW Sets:\n";
    for (auto& nt : g.nonterms) {
        cout << "  FOLLOW(" << nt << ") = { ";
        bool f = true;
        for (auto& x : follow.at(nt)) { if (!f) cout << ", "; cout << x; f = false; }
        cout << " }\n";
    }
    cout << "\n";
}

// ---- LL(1) table + parse ----

struct LL1Table {
    map<string,map<string,int>> cell;
    vector<string>              conflicts;
};

LL1Table buildLL1Table(const Grammar& g,
                       const map<string,set<string>>& first,
                       const map<string,set<string>>& follow) {
    LL1Table tab;
    auto set = [&](const string& A, const string& a, int idx) {
        if (!tab.cell[A].count(a)) { tab.cell[A][a] = idx; return; }
        if (tab.cell[A][a] != idx)
            tab.conflicts.push_back("Conflict M["+A+","+a+"]: L"+to_string(tab.cell[A][a]+1)+" vs L"+to_string(idx+1));
    };
    for (int i = 0; i < (int)g.prods.size(); ++i) {
        auto f = firstOfSeq(g.prods[i].rhs, first);
        for (auto& a : f) if (a!="eps") set(g.prods[i].lhs, a, i);
        if (f.count("eps")) for (auto& b : follow.at(g.prods[i].lhs)) set(g.prods[i].lhs, b, i);
    }
    return tab;
}

void printLL1Table(const Grammar& g, const LL1Table& tab) {
    cout << "LL(1) Parsing Table:\n\n";
    cout << left << setw(6) << "NT";
    for (auto& c : g.terms) cout << setw(8) << c;
    cout << "\n" << string(6 + (int)g.terms.size()*8, '-') << "\n";
    for (auto& nt : g.nonterms) {
        cout << setw(6) << nt;
        for (auto& c : g.terms) {
            string val;
            auto r = tab.cell.find(nt);
            if (r != tab.cell.end()) { auto col = r->second.find(c); if (col!=r->second.end()) val="L"+to_string(col->second+1); }
            cout << setw(8) << val;
        }
        cout << "\n";
    }
    cout << "\n";
    if (tab.conflicts.empty()) cout << "LL(1) Table: No conflicts\n\n";
    else { cout << "LL(1) Table: Conflicts found\n"; for (auto& c : tab.conflicts) cout << "  " << c << "\n"; cout << "\n"; }
}

struct LL1Step   { string stack, input, action; };
struct LL1Result { bool ok; vector<LL1Step> trace; string error; };

LL1Result parseLL1(const Grammar& g, const LL1Table& tab, const vector<string>& input) {
    LL1Result res{false,{},""};
    vector<string> st = {"$", g.start};
    size_t ip = 0; int guard = 0;
    while (!st.empty() && guard++ < 2000) {
        string top = st.back();
        string la  = (ip < input.size()) ? input[ip] : "$";
        LL1Step step;
        vector<string> tmp; for (int i=(int)st.size()-1;i>=0;--i) tmp.push_back(st[i]);
        step.stack = joinToks(tmp);
        step.input = joinToks(input, ip);
        if (top=="$" && la=="$") { step.action="ACCEPT"; res.trace.push_back(step); res.ok=true; return res; }
        if (!g.isNonTerm(top)) {
            if (top==la) { st.pop_back(); ++ip; step.action="Match "+la; res.trace.push_back(step); continue; }
            step.action="ERROR"; res.trace.push_back(step);
            res.error="LL(1) mismatch: expected '"+top+"' got '"+la+"'"; return res;
        }
        auto row = tab.cell.find(top);
        if (row==tab.cell.end() || !row->second.count(la)) {
            step.action="ERROR"; res.trace.push_back(step);
            res.error="LL(1) no entry for M["+top+","+la+"]"; return res;
        }
        int pid = row->second.at(la);
        const Production& p = g.prods[pid];
        st.pop_back();
        if (!(p.rhs.size()==1 && p.rhs[0]=="eps"))
            for (int i=(int)p.rhs.size()-1;i>=0;--i) st.push_back(p.rhs[i]);
        step.action = p.lhs+" -> "+rhsStr(p.rhs)+" (L"+to_string(pid+1)+")";
        res.trace.push_back(step);
    }
    res.error = "LL(1) aborted"; return res;
}

void printLL1Trace(const LL1Result& r) {
    cout << "LL(1) Parse Trace:\n\n";
    cout << left << setw(38) << "Stack (top->)" << setw(34) << "Remaining Input" << "Action\n";
    cout << string(102,'-') << "\n";
    for (auto& s : r.trace) cout << setw(38) << s.stack << setw(34) << s.input << s.action << "\n";
    cout << "\nLL(1) Result: " << (r.ok ? "ACCEPT" : "REJECT") << "\n";
    if (!r.ok) cout << "  Reason: " << r.error << "\n";
    cout << "\n";
}

// ---- LR(0) automaton ----

struct LR0Item {
    int prod, dot;
    bool operator<(const LR0Item& o) const { return prod!=o.prod ? prod<o.prod : dot<o.dot; }
};
using ItemSet = set<LR0Item>;

ItemSet closure(const ItemSet& I, const Grammar& g) {
    ItemSet C = I; bool changed = true;
    while (changed) {
        changed = false;
        for (auto& it : vector<LR0Item>(C.begin(),C.end())) {
            auto& p = g.prods[it.prod];
            if (it.dot >= (int)p.rhs.size()) continue;
            if (!g.isNonTerm(p.rhs[it.dot])) continue;
            for (int pid : g.byLhs.at(p.rhs[it.dot]))
                if (C.insert({pid,0}).second) changed = true;
        }
    }
    return C;
}

ItemSet goTo(const ItemSet& I, const string& X, const Grammar& g) {
    ItemSet J;
    for (auto& it : I) {
        auto& p = g.prods[it.prod];
        if (it.dot < (int)p.rhs.size() && p.rhs[it.dot]==X) J.insert({it.prod, it.dot+1});
    }
    return J.empty() ? J : closure(J, g);
}

struct LR0Machine { vector<ItemSet> states; map<int,map<string,int>> trans; };

LR0Machine buildLR0(const Grammar& g) {
    LR0Machine m;
    ItemSet I0 = closure({{0,0}}, g);
    m.states.push_back(I0);
    map<ItemSet,int> id; id[I0]=0;
    queue<int> q; q.push(0);
    vector<string> syms;
    for (auto& t : g.terms)    if (t!="$") syms.push_back(t);
    for (auto& nt: g.nonterms) syms.push_back(nt);
    while (!q.empty()) {
        int i = q.front(); q.pop();
        for (auto& X : syms) {
            ItemSet J = goTo(m.states[i], X, g);
            if (J.empty()) continue;
            if (!id.count(J)) { id[J]=(int)m.states.size(); m.states.push_back(J); q.push(id[J]); }
            m.trans[i][X] = id[J];
        }
    }
    return m;
}

// ---- SLR table + parse ----

enum class ActType { NONE, SHIFT, REDUCE, ACCEPT };
struct Action { ActType type=ActType::NONE; int val=-1; };

string actStr(const Action& a) {
    if (a.type==ActType::SHIFT)  return "s"+to_string(a.val);
    if (a.type==ActType::REDUCE) return "r"+to_string(a.val);
    if (a.type==ActType::ACCEPT) return "acc";
    return "";
}

struct SLRTable {
    map<int,map<string,Action>> action;
    map<int,map<string,int>>    goTo;
    vector<string>              conflicts;
};

SLRTable buildSLRTable(const Grammar& g, const LR0Machine& m, const map<string,set<string>>& follow) {
    SLRTable tab;
    auto setAct = [&](int st, const string& sym, const Action& a) {
        if (!tab.action[st].count(sym)) { tab.action[st][sym]=a; return; }
        Action& prev = tab.action[st][sym];
        if (prev.type!=a.type || prev.val!=a.val)
            tab.conflicts.push_back("Conflict ACTION[I"+to_string(st)+","+sym+"]: "+actStr(prev)+" vs "+actStr(a));
    };
    for (int i=0; i<(int)m.states.size(); ++i) {
        for (auto& it : m.states[i]) {
            auto& p = g.prods[it.prod];
            if (it.dot < (int)p.rhs.size()) {
                string X = p.rhs[it.dot];
                if (g.isNonTerm(X)) { if (m.trans.count(i)&&m.trans.at(i).count(X)) tab.goTo[i][X]=m.trans.at(i).at(X); }
                else { if (m.trans.count(i)&&m.trans.at(i).count(X)) setAct(i,X,{ActType::SHIFT,m.trans.at(i).at(X)}); }
            } else {
                if (p.lhs==g.start) setAct(i,"$",{ActType::ACCEPT,-1});
                else for (auto& a : follow.at(p.lhs)) setAct(i,a,{ActType::REDUCE,it.prod});
            }
        }
    }
    return tab;
}

void printSLRTable(const Grammar& g, const SLRTable& tab, int nStates) {
    cout << "SLR(1) Parsing Table:\n\n";
    vector<string> nts; for (auto& nt : g.nonterms) if (nt!=g.start) nts.push_back(nt);
    cout << left << setw(7) << "State";
    for (auto& t : g.terms) cout << setw(7) << t;
    cout << "| ";
    for (auto& nt : nts) cout << setw(7) << nt;
    cout << "\n" << string(7+(int)g.terms.size()*7+2+(int)nts.size()*7,'-') << "\n";
    for (int i=0; i<nStates; ++i) {
        cout << setw(7) << ("I"+to_string(i));
        for (auto& t : g.terms) {
            string c; if (tab.action.count(i)&&tab.action.at(i).count(t)) c=actStr(tab.action.at(i).at(t));
            cout << setw(7) << c;
        }
        cout << "| ";
        for (auto& nt : nts) {
            string c; if (tab.goTo.count(i)&&tab.goTo.at(i).count(nt)) c=to_string(tab.goTo.at(i).at(nt));
            cout << setw(7) << c;
        }
        cout << "\n";
    }
    cout << "\n";
    if (tab.conflicts.empty()) cout << "SLR Table: No conflicts\n\n";
    else { cout << "SLR Table: Conflicts\n"; for (auto& c : tab.conflicts) cout << "  " << c << "\n"; cout << "\n"; }
}

struct SLRStep   { string states, syms, input, action; };
struct SLRResult { bool ok; vector<SLRStep> trace; string error; };

SLRResult parseSLR(const Grammar& g, const SLRTable& tab, const vector<string>& input) {
    SLRResult res{false,{},""};
    vector<int>    stateSt = {0};
    vector<string> symSt   = {"$"};
    size_t ip=0; int guard=0;
    while (guard++ < 4000) {
        int s = stateSt.back();
        string a = (ip<input.size()) ? input[ip] : "$";
        SLRStep step;
        string ss; for (int x:stateSt) ss+=(ss.empty()?"":" ")+to_string(x);
        step.states = ss; step.syms = joinToks(symSt); step.input = joinToks(input,ip);
        if (!tab.action.count(s)||!tab.action.at(s).count(a)) {
            step.action="ERROR"; res.trace.push_back(step);
            res.error="SLR no action for I"+to_string(s)+" on '"+a+"'"; return res;
        }
        Action act = tab.action.at(s).at(a);
        if (act.type==ActType::SHIFT) {
            stateSt.push_back(act.val); symSt.push_back(a); ++ip;
            step.action="Shift "+a+" (s"+to_string(act.val)+")"; res.trace.push_back(step); continue;
        }
        if (act.type==ActType::REDUCE) {
            auto& p = g.prods[act.val];
            int popN = (p.rhs.size()==1&&p.rhs[0]=="eps") ? 0 : (int)p.rhs.size();
            for (int k=0;k<popN;++k) { stateSt.pop_back(); symSt.pop_back(); }
            int ns = tab.goTo.at(stateSt.back()).at(p.lhs);
            symSt.push_back(p.lhs); stateSt.push_back(ns);
            step.action="Reduce P"+to_string(act.val)+": "+p.lhs+" -> "+rhsStr(p.rhs);
            res.trace.push_back(step); continue;
        }
        if (act.type==ActType::ACCEPT) { step.action="ACCEPT"; res.trace.push_back(step); res.ok=true; return res; }
    }
    res.error="SLR aborted"; return res;
}

void printSLRTrace(const SLRResult& r) {
    cout << "SLR Parse Trace:\n\n";
    cout << left << setw(28) << "State Stack" << setw(24) << "Symbol Stack" << setw(34) << "Remaining Input" << "Action\n";
    cout << string(112,'-') << "\n";
    for (auto& s : r.trace) cout << setw(28)<<s.states << setw(24)<<s.syms << setw(34)<<s.input << s.action << "\n";
    cout << "\nSLR Result: " << (r.ok?"ACCEPT":"REJECT") << "\n";
    if (!r.ok) cout << "  Reason: " << r.error << "\n";
    cout << "\n";
}

// ---- token → grammar terminal mapping ----

bool tokenToTerm(const Token& t, string& out) {
    switch (t.type) {
        case TokenType::ID:          out="id";  return true;
        case TokenType::NUMBER:
        case TokenType::FLOAT_LIT:   out="num"; return true;
        case TokenType::ASSIGN:      out="=";   return true;
        case TokenType::PLUS:        out="+";   return true;
        case TokenType::MINUS:       out="-";   return true;
        case TokenType::STAR:        out="*";   return true;
        case TokenType::SLASH:       out="/";   return true;
        case TokenType::LPAREN:      out="(";   return true;
        case TokenType::RPAREN:      out=")";   return true;
        case TokenType::SEMI:        out=";";   return true;
        case TokenType::END_OF_FILE: out="$";   return true;
        default:                     return false;
    }
}

vector<string> toTermStream(const vector<Token>& toks, bool& ok, string& err) {
    vector<string> out; ok=true; err.clear();
    for (auto& t : toks) {
        string m;
        if (!tokenToTerm(t,m)) { ok=false; err="Unsupported token '"+t.text+"' (line "+to_string(t.line)+")"; return out; }
        out.push_back(m);
        if (t.type==TokenType::END_OF_FILE) break;
    }
    return out;
}
