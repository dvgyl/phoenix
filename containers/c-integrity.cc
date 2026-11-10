#include <clang/AST/ASTContext.h>
#include <clang/AST/RecursiveASTVisitor.h>
#include <clang/Basic/SourceManager.h>
#include <clang/Basic/TargetInfo.h>
#include <clang/Basic/Version.h>
#include <clang/Frontend/CompilerInstance.h>
#include <clang/Frontend/FrontendAction.h>
#include <clang/Lex/PPCallbacks.h>
#include <clang/Lex/Preprocessor.h>
#include <clang/Tooling/Tooling.h>
#include <llvm/ADT/DenseMap.h>
#include <llvm/ADT/DenseSet.h>
#include <llvm/ADT/SmallString.h>
#include <llvm/ADT/SmallVector.h>
#include <llvm/ADT/StringExtras.h>
#include <llvm/Support/FileSystem.h>
#include <llvm/Support/FormatVariadic.h>
#include <llvm/Support/JSON.h>
#include <llvm/Support/VirtualFileSystem.h>
#include <llvm/Support/raw_ostream.h>

#include <cstdlib>
#include <optional>
#include <string>
#include <system_error>
#include <vector>

using namespace clang;
using llvm::StringRef;
namespace json = llvm::json;

namespace {

constexpr size_t maxBytes = 8 * 1024 * 1024;
constexpr size_t maxRecords = 32768;
constexpr StringRef resourceDir = "/usr/lib/llvm-18/lib/clang/18";
constexpr StringRef resourceHeaders = "/usr/lib/llvm-18/lib/clang/18/include";

std::string physicalPath(StringRef path) {
    llvm::SmallString<256> result;
    if (llvm::sys::fs::real_path(path, result))
        return {};
    return result.str().str();
}

bool isUnder(StringRef path, StringRef root) {
    return path.consume_front(root) && path.starts_with("/");
}

bool systemHeader(StringRef name, StringRef path, StringRef root) {
    return !isUnder(name, root) &&
           (isUnder(path, "/usr/include") || isUnder(path, resourceHeaders));
}

struct Location {
    std::string scope;
    std::string file;
    unsigned offset = 0;

    bool project() const { return scope == "project"; }

    json::Object json() const {
        if (file.empty())
            return json::Object{{"scope", scope}};
        return json::Object{{"scope", scope}, {"file", file}, {"offset", offset}};
    }
};

struct Evidence {
    std::string root;
    std::string target;
    std::string unit;
    json::Array records;
    json::Array calls;
    json::Object error;
    size_t byteCount = 0;
    bool walked = false;

    bool fail(StringRef category, StringRef message, const Location &loc = {}) {
        if (error.empty()) {
            error = json::Object{{"category", category.str()}, {"message", message.str()}};
            if (!loc.scope.empty())
                error["location"] = loc.json();
        }
        return false;
    }

    json::Object report() {
        json::Object report{{"schema", 1},
                            {"policy", "m1-v1"},
                            {"clang_version", getClangFullVersion()},
                            {"target", target},
                            {"translation_unit", unit}};
        if (error.empty()) {
            report["status"] = "complete";
            report["record_count"] = records.size();
            report["records"] = std::move(records);
            report["calls"] = std::move(calls);
        } else {
            report["status"] = "unchecked";
            report["error"] = std::move(error);
        }
        return report;
    }
};

class SourceFiles : public llvm::vfs::ProxyFileSystem {
    Evidence &evidence;
    bool restricted = false;

public:
    explicit SourceFiles(Evidence &evidence)
        : ProxyFileSystem(llvm::vfs::getRealFileSystem()), evidence(evidence) {}

    void restrictReads() { restricted = true; }

    llvm::ErrorOr<std::unique_ptr<llvm::vfs::File>>
    openFileForRead(const llvm::Twine &requested) override {
        if (!restricted)
            return ProxyFileSystem::openFileForRead(requested);
        std::string name = requested.str();
        std::string path = physicalPath(name);
        if (path.empty())
            return std::make_error_code(std::errc::no_such_file_or_directory);
        if ((!isUnder(path, evidence.root) && !systemHeader(name, path, evidence.root)) ||
            !llvm::sys::fs::is_regular_file(path)) {
            evidence.fail("unapproved_file", "A source file is outside the approved roots or is not a regular file.");
            return std::make_error_code(std::errc::permission_denied);
        }
        uint64_t size;
        if (llvm::sys::fs::file_size(path, size) || size > maxBytes) {
            evidence.fail("limit", "Source file limit exceeded.");
            return std::make_error_code(std::errc::file_too_large);
        }
        return ProxyFileSystem::openFileForRead(path);
    }
};

class SourcePolicy {
    SourceManager &sm;
    Evidence &evidence;
    llvm::DenseMap<FileID, Location> files;
    size_t projectBytes = 0;

    Location file(FileID id) {
        if (auto it = files.find(id); it != files.end())
            return it->second;
        Location result{"synthetic", {}};
        if (auto entry = sm.getFileEntryRefForID(id)) {
            StringRef name = entry->getName();
            std::string path = physicalPath(name);
            if (isUnder(path, evidence.root) && json::isUTF8(path)) {
                result = {"project", path.substr(evidence.root.size() + 1)};
                auto size = entry->getSize();
                if (size < 0 || static_cast<uint64_t>(size) > maxBytes - projectBytes ||
                    files.size() >= maxRecords)
                    evidence.fail("limit", "Source file limit exceeded.", result);
                else
                    projectBytes += size;
            } else if (systemHeader(name, path, evidence.root)) {
                result = {"system", path};
            } else {
                result = {"unapproved_file", {}};
                evidence.fail("unapproved_file", "A source file is outside the approved roots.");
            }
        }
        files.try_emplace(id, result);
        return result;
    }

    Location at(SourceLocation loc) {
        if (loc.isInvalid())
            return {"synthetic", {}};
        auto [id, offset] = sm.getDecomposedLoc(loc);
        Location result = file(id);
        if (!result.file.empty() && offset > sm.getFileIDSize(id)) {
            evidence.fail("source_location", "A source offset is outside its file.", result);
            return {"invalid", {}};
        }
        result.offset = offset;
        return result;
    }

public:
    SourcePolicy(SourceManager &sm, Evidence &evidence) : sm(sm), evidence(evidence) {}

    Location expansion(SourceLocation loc) { return at(sm.getExpansionLoc(loc)); }
    Location spelling(SourceLocation loc) { return at(sm.getSpellingLoc(loc)); }
};

class Preprocessing : public PPCallbacks {
    SourcePolicy &source;
    Evidence &evidence;

    void reject(SourceLocation loc) {
        auto where = source.expansion(loc);
        if (where.project())
            evidence.fail("unsupported_preprocessing",
                          "This project preprocessing directive is not permitted.", where);
    }

public:
    Preprocessing(SourcePolicy &source, Evidence &evidence)
        : source(source), evidence(evidence) {}

    void FileChanged(SourceLocation loc, FileChangeReason reason,
                     SrcMgr::CharacteristicKind, FileID) override {
        if (reason == EnterFile)
            source.expansion(loc);
        if (reason == RenameFile)
            reject(loc);
    }

    void MacroDefined(const Token &name, const MacroDirective *) override {
        reject(name.getLocation());
    }
    void MacroUndefined(const Token &name, const MacroDefinition &,
                        const MacroDirective *) override {
        reject(name.getLocation());
    }
    void If(SourceLocation loc, SourceRange, ConditionValueKind) override { reject(loc); }
    void Ifdef(SourceLocation loc, const Token &, const MacroDefinition &) override {
        reject(loc);
    }
    void Ifndef(SourceLocation loc, const Token &, const MacroDefinition &) override {
        reject(loc);
    }
    void PragmaDirective(SourceLocation loc, PragmaIntroducerKind) override { reject(loc); }
    void Ident(SourceLocation loc, StringRef) override { reject(loc); }
};

class Inventory : public RecursiveASTVisitor<Inventory> {
    ASTContext &context;
    SourcePolicy &source;
    Evidence &evidence;
    llvm::DenseSet<unsigned> &unseenStrings;
    llvm::DenseSet<unsigned> nonObjectStrings;
    llvm::DenseSet<unsigned> seenStrings;
    std::vector<const StringLiteral *> literals;

    bool record(StringRef kind, SourceLocation loc, StringRef bytes,
                StringRef name = {}, StringRef type = {}, json::Array tokens = {}) {
        auto where = source.expansion(loc);
        if (bytes.size() > maxBytes - evidence.byteCount ||
            evidence.records.size() >= maxRecords)
            return evidence.fail("limit", "Storage evidence limit exceeded.", where);
        evidence.byteCount += bytes.size();
        json::Object item{{"kind", kind.str()},
                          {"file", where.file},
                          {"offset", where.offset},
                          {"spelling", source.spelling(loc).json()},
                          {"bytes_hex", llvm::toHex(bytes, true)}};
        if (!name.empty())
            item["declaration"] = name.str();
        if (!type.empty())
            item["canonical_type"] = type.str();
        if (!tokens.empty())
            item["tokens"] = std::move(tokens);
        evidence.records.push_back(std::move(item));
        return evidence.error.empty();
    }

    bool hasRuntimeInput(const Stmt *stmt) {
        llvm::SmallVector<const Stmt *, 16> pending{stmt};
        while (!pending.empty()) {
            const Stmt *part = pending.pop_back_val();
            if (auto *reference = dyn_cast<DeclRefExpr>(part);
                reference && isa<VarDecl>(reference->getDecl()))
                return true;
            if (isa<CallExpr>(part))
                return true;
            for (auto *child : part->children()) {
                if (child)
                    pending.push_back(child);
            }
        }
        return false;
    }

    bool supported(QualType type) {
        if (auto *array = context.getAsConstantArrayType(type))
            return supported(array->getElementType());
        return type->isIntegerType() && !type->isBitIntType();
    }

    bool serialize(QualType type, const Expr *init, llvm::MutableArrayRef<char> bytes) {
        if (!init || isa<ImplicitValueInitExpr>(init))
            return true;
        init = init->IgnoreParens();
        if (auto *array = context.getAsConstantArrayType(type)) {
            auto *list = dyn_cast<InitListExpr>(init);
            auto *literal = dyn_cast<StringLiteral>(init);
            if (list && list->isSemanticForm() && list->isStringLiteralInit())
                literal = dyn_cast<StringLiteral>(list->getInit(0)->IgnoreParenImpCasts());
            if (literal) {
                if (literal->getCharByteWidth() != 1)
                    return evidence.fail("unsupported_string", "Wide strings are not supported.",
                                         source.expansion(literal->getBeginLoc()));
                if (!array->getElementType()->isCharType() || literal->getByteLength() > bytes.size())
                    return false;
                llvm::copy(literal->getBytes(), bytes.begin());
                nonObjectStrings.insert(literal->getBeginLoc().getRawEncoding());
                return true;
            }
            if (!list || !list->isSemanticForm() ||
                (list->hasArrayFiller() && !isa<ImplicitValueInitExpr>(list->getArrayFiller())))
                return false;
            QualType element = array->getElementType();
            auto stride = context.getTypeSizeInChars(element).getQuantity();
            if (stride <= 0 || list->getNumInits() > bytes.size() / stride)
                return false;
            for (unsigned i = 0; i < list->getNumInits(); ++i) {
                const Expr *child = list->getInit(i);
                if (!child)
                    child = list->getArrayFiller();
                if (!serialize(element, child, bytes.slice(i * stride, stride)))
                    return false;
            }
            return true;
        }

        Expr::EvalResult result;
        if (!init->EvaluateAsInt(result, context) || result.HasUndefinedBehavior)
            return false;
        unsigned width = context.getIntWidth(type);
        if (width == 0 || width > 128 || width > bytes.size() * 8)
            return false;
        llvm::APInt value = result.Val.getInt().extOrTrunc(width);
        value = value.zextOrTrunc(bytes.size() * 8);
        for (size_t i = 0; i < bytes.size(); ++i) {
            size_t index = context.getTargetInfo().isBigEndian() ? bytes.size() - i - 1 : i;
            bytes[index] = static_cast<char>(value.extractBitsAsZExtValue(8, i * 8));
        }
        return true;
    }

public:
    Inventory(ASTContext &context, SourcePolicy &source, Evidence &evidence,
              llvm::DenseSet<unsigned> &unseenStrings)
        : context(context), source(source), evidence(evidence), unseenStrings(unseenStrings) {}

    bool VisitDecl(Decl *decl) {
        if (decl->isImplicit() || !source.expansion(decl->getLocation()).project())
            return evidence.error.empty();
        auto where = source.expansion(decl->getLocation());
        for (const auto *attr : decl->attrs()) {
            if (!attr->isImplicit() && source.expansion(attr->getLocation()).project())
                return evidence.fail("unsupported_attribute",
                                     "Project declaration attributes are not supported.", where);
        }
        if (auto *assertion = dyn_cast<StaticAssertDecl>(decl)) {
            if (auto *message = assertion->getMessage())
                nonObjectStrings.insert(message->getBeginLoc().getRawEncoding());
        }
        if (isa<FileScopeAsmDecl>(decl))
            return evidence.fail("unsupported_assembly", "File-scope assembly is not supported.", where);
        if (auto *field = dyn_cast<FieldDecl>(decl); field && field->isBitField())
            return evidence.fail("unsupported_type", "Bit-fields are not supported.", where);
        return true;
    }

    bool VisitVarDecl(VarDecl *decl) {
        SourceLocation loc = decl->getLocation();
        auto where = source.expansion(loc);
        if (decl->isImplicit() || !where.project() || isa<ParmVarDecl>(decl))
            return evidence.error.empty();
        if (decl->getType()->isVariablyModifiedType())
            return evidence.fail("unsupported_type", "Variable array bounds are not supported.", where);
        auto definition = decl->isThisDeclarationADefinition();
        if (definition == VarDecl::DeclarationOnly ||
            (definition == VarDecl::TentativeDefinition && decl->getActingDefinition() != decl))
            return true;

        const Expr *init = decl->getInit();
        if (!init && !decl->hasGlobalStorage())
            return true;

        QualType type = context.getCanonicalType(decl->getType());
        if (type->isPointerType() && decl->hasLocalStorage() && init &&
            (hasRuntimeInput(init) || isa<StringLiteral>(init->IgnoreParenImpCasts()) ||
             init->isNullPointerConstant(context, Expr::NPC_ValueDependentIsNotNull) !=
                 Expr::NPCK_NotNull))
            return true;
        if (!supported(type))
            return evidence.fail("unsupported_storage",
                                 "Only integer objects and arrays of integers are supported.", where);
        auto size = context.getTypeSizeInChars(type).getQuantity();
        if (size <= 0 || static_cast<uint64_t>(size) > maxBytes - evidence.byteCount)
            return evidence.fail("limit", "Object storage limit exceeded.", where);
        std::string bytes(size, '\0');
        if (!serialize(type, init, llvm::MutableArrayRef<char>(bytes.data(), bytes.size()))) {
            if (type->isIntegerType() && decl->hasLocalStorage() && init && hasRuntimeInput(init))
                return true;
            return evidence.fail("unresolved_initializer",
                                 "Clang could not resolve the initializer storage.", where);
        }
        return record("storage", loc, bytes, decl->getName(), type.getAsString());
    }

    bool VisitVariableArrayTypeLoc(VariableArrayTypeLoc loc) {
        auto where = source.expansion(loc.getBeginLoc());
        return !where.project() ||
               evidence.fail("unsupported_type", "Variable array bounds are not supported.", where);
    }

    bool VisitStmt(Stmt *stmt) {
        auto where = source.expansion(stmt->getBeginLoc());
        if (!where.project())
            return evidence.error.empty();
        if (isa<AsmStmt>(stmt))
            return evidence.fail("unsupported_assembly", "Inline assembly is not supported.", where);
        if (isa<CompoundLiteralExpr>(stmt))
            return evidence.fail("unsupported_storage", "Compound literals are not supported.", where);
        if (isa<AttributedStmt>(stmt))
            return evidence.fail("unsupported_attribute", "Statement attributes are not supported.", where);
        if (auto *cast = dyn_cast<CastExpr>(stmt);
            cast && cast->getCastKind() == CK_IntegralToPointer) {
            Expr::EvalResult result;
            if (cast->getSubExpr()->EvaluateAsInt(result, context) &&
                !result.Val.getInt().isZero())
                return evidence.fail("hardcoded_address", "A fixed nonzero address is not supported.", where);
        }
        return true;
    }

    bool VisitCallExpr(CallExpr *call) {
        auto where = source.expansion(call->getExprLoc());
        if (!where.project())
            return evidence.error.empty();
        const FunctionDecl *callee = call->getDirectCallee();
        if (callee && !callee->isExternallyVisible() && !callee->getBuiltinID())
            return true;
        if (evidence.calls.size() >= maxRecords)
            return evidence.fail("limit", "Call evidence limit exceeded.", where);
        json::Object fact{{"file", where.file}, {"offset", where.offset}};
        if (callee) {
            const auto *definition = callee->getDefinition();
            if (definition && source.expansion(definition->getLocation()).project())
                fact["kind"] = "project";
            else
                fact["kind"] = callee->getBuiltinID() ? "builtin" : "external_linkage";
            fact["name"] = callee->getNameAsString();
        } else {
            fact["kind"] = "indirect";
        }
        evidence.calls.push_back(std::move(fact));
        return true;
    }

    bool VisitStringLiteral(StringLiteral *literal) {
        bool project = false;
        for (unsigned i = 0; i < literal->getNumConcatenated(); ++i) {
            auto loc = literal->getStrTokenLoc(i);
            project |= source.expansion(loc).project() || source.spelling(loc).project();
            unseenStrings.erase(loc.getRawEncoding());
        }
        if (!project || !seenStrings.insert(literal->getBeginLoc().getRawEncoding()).second)
            return evidence.error.empty();
        if (!source.expansion(literal->getBeginLoc()).project())
            return evidence.fail("source_location", "A project literal has no project expansion location.");
        if (literal->getCharByteWidth() != 1)
            return evidence.fail("unsupported_string", "Wide strings are not supported.",
                                 source.expansion(literal->getBeginLoc()));
        literals.push_back(literal);
        return evidence.error.empty();
    }

    bool finish() {
        if (!unseenStrings.empty())
            return evidence.fail("missing_literal",
                                 "A project string token has no string literal in the syntax tree.");
        for (auto *literal : literals) {
            auto loc = literal->getBeginLoc();
            json::Array tokens;
            for (unsigned i = 0; i < literal->getNumConcatenated(); ++i) {
                auto token = literal->getStrTokenLoc(i);
                tokens.push_back(json::Object{{"expansion", source.expansion(token).json()},
                                              {"spelling", source.spelling(token).json()}});
            }
            if (!record("literal", loc, literal->getBytes(), {}, {}, std::move(tokens)))
                return false;
            if (!nonObjectStrings.contains(loc.getRawEncoding())) {
                std::string storage = literal->getBytes().str();
                storage.push_back('\0');
                if (!record("literal_storage", loc, storage))
                    return false;
            }
        }
        return true;
    }
};

class Consumer : public ASTConsumer {
    SourcePolicy &source;
    Evidence &evidence;
    llvm::DenseSet<unsigned> &unseenStrings;

public:
    Consumer(SourcePolicy &source, Evidence &evidence, llvm::DenseSet<unsigned> &unseenStrings)
        : source(source), evidence(evidence), unseenStrings(unseenStrings) {}

    void HandleTranslationUnit(ASTContext &context) override {
        if (!evidence.error.empty() || context.getDiagnostics().hasErrorOccurred())
            return;
        if (context.getTargetInfo().getCharWidth() != 8) {
            evidence.fail("target", "The target must have 8-bit bytes.");
            return;
        }
        Inventory inventory(context, source, evidence, unseenStrings);
        evidence.walked = inventory.TraverseDecl(context.getTranslationUnitDecl()) && inventory.finish();
    }
};

class Action : public ASTFrontendAction {
    Evidence &evidence;
    SourceFiles &files;
    std::optional<SourcePolicy> source;
    llvm::DenseSet<unsigned> unseenStrings;

public:
    Action(Evidence &evidence, SourceFiles &files) : evidence(evidence), files(files) {}

    bool BeginInvocation(CompilerInstance &) override {
        files.restrictReads();
        return true;
    }

    std::unique_ptr<ASTConsumer> CreateASTConsumer(CompilerInstance &ci, StringRef) override {
        source.emplace(ci.getSourceManager(), evidence);
        auto &pp = ci.getPreprocessor();
        pp.addPPCallbacks(std::make_unique<Preprocessing>(*source, evidence));
        pp.setTokenWatcher([this](const Token &token) {
            if (!tok::isStringLiteral(token.getKind()) || !evidence.error.empty())
                return;
            auto loc = token.getLocation();
            if (source->expansion(loc).project() || source->spelling(loc).project()) {
                if (unseenStrings.size() >= maxRecords)
                    evidence.fail("limit", "String token limit exceeded.");
                else
                    unseenStrings.insert(loc.getRawEncoding());
            }
        });
        return std::make_unique<Consumer>(*source, evidence, unseenStrings);
    }
};

int run(int argc, char **argv, Evidence &evidence) {
    if (argc != 10)
        return evidence.fail("arguments", "Specify one project, one C file, and the fixed C11 flags."), 2;
    StringRef root = argv[1];
    StringRef unit = argv[2];
    StringRef target = argv[4];
    if (!root.consume_front("--project=") || !root.starts_with("/") ||
        !target.consume_front("--target=") ||
        (target != "x86_64-linux-gnu" && target != "aarch64-linux-gnu") ||
        StringRef(argv[3]) != "--" || StringRef(argv[5]) != "-std=c11" ||
        StringRef(argv[6]) != "-pedantic-errors" || StringRef(argv[7]) != "-Wall" ||
        StringRef(argv[8]) != "-Wextra" || argv[9] != ("-I" + root + "/include").str())
        return evidence.fail("arguments", "The project, target, or C11 flags are invalid."), 2;

    evidence.root = physicalPath(root);
    evidence.target = target.str();
    std::string path = physicalPath(unit);
    if (evidence.root != root || !llvm::sys::fs::is_directory(root) ||
        !isUnder(path, root) || path != unit || !unit.ends_with(".c") ||
        !llvm::sys::fs::is_regular_file(unit) || !json::isUTF8(path))
        return evidence.fail("arguments", "Use physical paths for the project and its C file."), 2;
    evidence.unit = path.substr(root.size() + 1);
    std::string include = (root + "/include").str();
    if (llvm::sys::fs::exists(include) && physicalPath(include) != include)
        return evidence.fail("unapproved_file", "The project include directory must use its physical path."), 2;
    if (!llvm::sys::fs::is_directory(("/usr/include/" + target).str()))
        return evidence.fail("target", "The image has no system headers for this target."), 2;

    for (const char *name : {"CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH",
                             "DEPENDENCIES_OUTPUT", "SUNPRO_DEPENDENCIES", "CCC_OVERRIDE_OPTIONS"})
        unsetenv(name);
    std::vector<std::string> command{
        "/usr/bin/clang-18", "--no-default-config", argv[4], argv[5], argv[6], argv[7], argv[8],
        argv[9], "-Werror=#warnings", "-Werror=initializer-overrides", "-Werror=division-by-zero",
        "-D_POSIX_C_SOURCE=200809L", "-fsyntax-only", "-x", "c", "-nostdinc",
        ("-resource-dir=" + resourceDir).str(), "-isystem", resourceHeaders.str(),
        "-isystem", ("/usr/include/" + target).str(), "-isystem", "/usr/include", path};
    auto vfs = llvm::makeIntrusiveRefCnt<SourceFiles>(evidence);
    auto files = llvm::makeIntrusiveRefCnt<FileManager>(FileSystemOptions{}, vfs);
    tooling::ToolInvocation invocation(command, std::make_unique<Action>(evidence, *vfs), files.get());
    bool compiled = invocation.run();
    if (!compiled)
        evidence.fail("compiler_error", "Clang rejected the translation unit.");
    if (!evidence.walked)
        evidence.fail("incomplete", "The syntax tree inventory did not finish.");
    return evidence.error.empty() ? 0 : 1;
}

} // namespace

int main(int argc, char **argv) {
    Evidence evidence;
    int status = run(argc, argv, evidence);
    llvm::outs() << llvm::formatv("{0}\n", json::Value(evidence.report()));
    return status;
}
