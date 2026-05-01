#include "semantic.h"
#include "ll_slr.h"
#include "tac.h"
#include "codegen.h"
#include <fstream>
#include <sstream>

// LL(1) and SLR use a simpler expression-only grammar, this is their demo input
const string LL_SLR_INPUT = "a = b + c * d ; x = ( y - 2 ) / z";

static void banner(const string& t) {
    cout << "\n" << string(64,'=') << "\n  " << t << "\n" << string(64,'=') << "\n\n";
}

static void section(const string& t) {
    cout << "\n" << string(64,'-') << "\n  " << t << "\n" << string(64,'-') << "\n\n";
}

// reads source from file, defaults to eval_program.txt, or pass any file as argv[1]
string readFile(const string& path) {
    ifstream f(path);
    if (!f.is_open()) { cerr << "ERROR: cannot open '" << path << "'\n"; exit(1); }
    ostringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

int main(int argc, char* argv[]) {

    string srcPath = (argc > 1) ? argv[1] : "eval_program.txt";
    string src     = readFile(srcPath);

    // Phase 1: tokenize the source file
    banner("Phase 1: Lexical Analysis");
    cout << "File: " << srcPath << "\n\nSource Code:\n" << src << "\nToken Stream:\n";
    bool lexOk;
    vector<Token> tokens = runLexer(src, lexOk);
    for (auto& t : tokens)
        cout << "  " << left << setw(12) << tokenName(t.type) << t.text << "\n";
    cout << "\nResult: " << (lexOk
        ? "SUCCESS — " + to_string((int)tokens.size()-1) + " tokens generated"
        : "FAILED — lexical errors detected") << "\n";

    // Phase 2: parse tokens into an AST, this tree is used by phases 4 and 5
    banner("Phase 2: Syntax Analysis");
    Parser parser(tokens);
    Node* tree = parser.parse();
    cout << "Parse Tree:\n\n";
    printTree(tree);
    cout << "\nResult: ";
    if (parser.ok()) {
        cout << "SUCCESS — program is syntactically correct\n";
    } else {
        cout << "FAILED\n";
        for (auto& e : parser.errors()) cout << "  SYNTAX ERROR: " << e << "\n";
    }

    // Phase 3: LL(1) and SLR table-driven parsers with FIRST/FOLLOW and stack traces
    banner("Phase 3: LL(1) and SLR Table-Driven Parsers");
    bool exprOk; string exprErr;
    vector<Token> exprToks    = runLexer(LL_SLR_INPUT, exprOk);
    vector<string> termStream = toTermStream(exprToks, exprOk, exprErr);
    cout << "Input: " << LL_SLR_INPUT << "\n";
    cout << "Terminal stream: " << joinToks(termStream) << "\n";

    section("Part A: LL(1) Parser");
    Grammar ll1g    = buildLL1Grammar();
    auto ll1First   = computeFirst(ll1g);
    auto ll1Follow  = computeFollow(ll1g, ll1First);
    LL1Table ll1Tab = buildLL1Table(ll1g, ll1First, ll1Follow);
    cout << "Grammar:\n";
    for (int i = 0; i < (int)ll1g.prods.size(); ++i)
        cout << "  L" << i+1 << ": " << ll1g.prods[i].lhs << " -> " << rhsStr(ll1g.prods[i].rhs) << "\n";
    cout << "\n";
    printFirstFollow(ll1g, ll1First, ll1Follow);
    printLL1Table(ll1g, ll1Tab);
    LL1Result ll1Res = parseLL1(ll1g, ll1Tab, termStream);
    printLL1Trace(ll1Res);

    section("Part B: SLR(1) Parser");
    Grammar slrg    = buildSLRGrammar();
    auto slrFirst   = computeFirst(slrg);
    auto slrFollow  = computeFollow(slrg, slrFirst);
    LR0Machine lr0  = buildLR0(slrg);
    SLRTable slrTab = buildSLRTable(slrg, lr0, slrFollow);
    cout << "Grammar:\n";
    for (int i = 0; i < (int)slrg.prods.size(); ++i)
        cout << "  P" << i << ": " << slrg.prods[i].lhs << " -> " << rhsStr(slrg.prods[i].rhs) << "\n";
    cout << "\n";
    printFirstFollow(slrg, slrFirst, slrFollow);
    printSLRTable(slrg, slrTab, (int)lr0.states.size());
    SLRResult slrRes = parseSLR(slrg, slrTab, termStream);
    printSLRTrace(slrRes);

    section("Part C: Rejection Demo");
    string badSrc = "a = b + ; x";
    bool bOk; string bErr;
    vector<Token> badToks    = runLexer(badSrc, bOk);
    vector<string> badStream = toTermStream(badToks, bOk, bErr);
    cout << "Invalid input   : " << badSrc << "\n";
    cout << "Terminal stream : " << joinToks(badStream) << "\n\n";
    LL1Result ll1Bad = parseLL1(ll1g, ll1Tab, badStream);
    SLRResult slrBad = parseSLR(slrg, slrTab, badStream);
    cout << "LL(1) : " << (ll1Bad.ok ? "ACCEPT" : "REJECT — " + ll1Bad.error) << "\n";
    cout << "SLR   : " << (slrBad.ok ? "ACCEPT" : "REJECT — " + slrBad.error) << "\n";

    // Phase 4: walk the AST and build the symbol table with scope and offset info
    banner("Phase 4: Symbol Table & Scope Handling");
    SymbolTable symTab;
    SemanticAnalyzer sem(symTab);
    sem.analyze(tree);
    section("Final Symbol Table");
    symTab.printTable();
    section("Step-by-Step Insert / Lookup / Scope Log");
    symTab.printLog();

    // Phase 5: semantic errors collected during analyze() above, just print them here
    banner("Phase 5: Semantic Analysis");
    if (!sem.hasErrors()) {
        cout << "Result: SUCCESS — no semantic errors detected\n";
    } else {
        cout << "Result: FAILED — semantic errors found:\n";
        for (auto& e : sem.getErrors()) cout << "  " << e << "\n";
    }

    // Phase 6: generate intermediate code from AST using quadruple representation
    banner("Phase 6: Intermediate Code Generation (TAC)");
    TACGenerator tac;
    tac.generate(tree);
    tac.print();

    // Phase 7: optimize the TAC, then translate to pseudo-assembly target code
    banner("Phase 7: Optimization & Target Code Generation");

    section("Unoptimized TAC (Quadruples)");
    printQuads(tac.getQuads());

    Optimizer opt;
    opt.load(tac.getQuads());
    opt.run();

    section("Optimized TAC (after constant folding, propagation, algebraic simp., DCE)");
    printQuads(opt.getQuads());

    cout << "\nOptimizations applied:\n"
         << "  1. Constant Folding         — fold constant arithmetic at compile time\n"
         << "  2. Constant Propagation     — replace uses of vars proven constant\n"
         << "  3. Algebraic Simplification — x+0, x-0, x*1, x*0 reductions\n"
         << "  4. Dead Code Elimination    — drop unused temporary assignments\n";

    section("Target Code (pseudo-assembly)");
    TargetCodeGen tgt;
    tgt.generate(opt.getQuads());
    tgt.print();

    banner("Compilation Pipeline Summary");
    cout << left;
    cout << setw(40) << "Phase 1  Lexical Analysis"  << (lexOk            ? "PASS"   : "FAIL")   << "\n";
    cout << setw(40) << "Phase 2  Syntax Analysis"   << (parser.ok()      ? "PASS"   : "FAIL")   << "\n";
    cout << setw(40) << "Phase 3  LL(1) Parser"      << (ll1Res.ok        ? "ACCEPT" : "REJECT") << "\n";
    cout << setw(40) << "Phase 3  SLR Parser"        << (slrRes.ok        ? "ACCEPT" : "REJECT") << "\n";
    cout << setw(40) << "Phase 4  Symbol Table"      << "PASS"                                    << "\n";
    cout << setw(40) << "Phase 5  Semantic Analysis" << (!sem.hasErrors() ? "PASS"   : "FAIL")   << "\n";
    cout << setw(40) << "Phase 6  TAC (Quadruples)"  << "PASS"                                    << "\n";
    cout << setw(40) << "Phase 7  Optimization + Target Code" << "PASS"                            << "\n";

    delete tree;
    return 0;
}
