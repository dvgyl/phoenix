import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.JsonPrimitive;
import ghidra.app.decompiler.ClangToken;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.decompiler.PrettyPrinter;
import ghidra.framework.Application;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.block.BasicBlockModel;
import ghidra.util.task.TaskMonitor;
import ghidra.program.model.listing.Program;
import ghidra.program.model.pcode.HighFunction;
import ghidra.program.model.pcode.PcodeBlock;
import ghidra.program.model.pcode.PcodeBlockBasic;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.PcodeOpAST;
import ghidra.program.model.pcode.Varnode;
import ghidra.program.model.pcode.VarnodeAST;
import ghidra.util.StringUtilities;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Collect unpublished proposals from the ordinary DecompileResults object. */
final class OrdinaryByteEvidence {
    private static final int MAX_DRAFT_BYTES = 16 * 1024 * 1024;
    private static final Set<String> KNOWN_OPS = Set.of(
            "COPY", "LOAD", "STORE", "BRANCH", "CBRANCH", "BRANCHIND", "CALL", "CALLIND",
            "RETURN", "INT_EQUAL", "INT_NOTEQUAL", "INT_SLESS", "INT_SLESSEQUAL", "INT_LESS",
            "INT_LESSEQUAL", "INT_ZEXT", "INT_SEXT", "INT_ADD", "INT_SUB", "INT_CARRY",
            "INT_SCARRY", "INT_SBORROW", "INT_2COMP", "INT_NEGATE", "INT_XOR", "INT_AND",
            "INT_OR", "INT_LEFT", "INT_RIGHT", "INT_SRIGHT", "INT_MULT", "INT_DIV", "INT_SDIV",
            "INT_REM", "INT_SREM", "BOOL_NEGATE", "BOOL_XOR", "BOOL_AND", "BOOL_OR",
            "MULTIEQUAL", "PIECE", "SUBPIECE", "CAST", "PTRADD", "PTRSUB", "POPCOUNT",
            "LZCOUNT");

    private static final class Gap extends Exception {
        Gap(String code) { super(code); }
    }

    private final Program program;
    private final JsonObject context;
    private final JsonArray functions = new JsonArray();
    private final JsonArray roster = new JsonArray();
    private int totalBytes;

    OrdinaryByteEvidence(Program program, Path scripts, Path contextPath) throws Exception {
        this.program = program;
        if (Files.size(contextPath) > 1024 * 1024) {
            throw new IOException("The byte context exceeds its limit.");
        }
        byte[] raw = Files.readAllBytes(contextPath);
        context = JsonParser.parseString(new String(raw, StandardCharsets.UTF_8)).getAsJsonObject();
        if (!java.util.Arrays.equals(raw, canonical(context, 1024 * 1024))) {
            throw new IOException("The byte context is not canonical.");
        }
        validateLimits();
        for (String name : List.of("ExportLift.java", "OrdinarySwitchEvidence.java",
                "OrdinaryByteEvidence.java", "ExportMapping.java")) {
            String expected = context.getAsJsonObject("sources").get("ghidra_scripts/" + name)
                    .getAsString();
            if (!expected.equals(hash(Files.readAllBytes(scripts.resolve(name))))) {
                throw new IOException("The running exporter source differs from its context.");
            }
        }
        if (!Application.getApplicationVersion().equals(context.get("ghidra_version").getAsString())
                || !Application.getApplicationProperty("application.revision.ghidra")
                    .equals(context.get("ghidra_revision").getAsString())
                || !System.getProperty("java.runtime.version")
                    .equals(context.get("java_runtime_version").getAsString())) {
            throw new IOException("The running tools differ from the byte context.");
        }
        if (!program.getExecutableSHA256().equals(context.get("binary_sha256").getAsString())) {
            throw new IOException("The program differs from the byte context.");
        }
    }

    private void validateLimits() throws IOException {
        JsonObject limits = context.getAsJsonObject("limits");
        checkLimits(limits, Map.of(
                "max_program_bytes", 16 * 1024 * 1024, "max_lift_bytes", 64 * 1024 * 1024,
                "max_mapping_bytes", 64 * 1024 * 1024, "max_companion_bytes", MAX_DRAFT_BYTES,
                "max_bundle_bytes", 160 * 1024 * 1024, "max_functions", 32), Set.of("graph", "source"));
        checkLimits(limits.getAsJsonObject("graph"), Map.of(
                "max_bytes", MAX_DRAFT_BYTES, "max_blocks", 32, "max_operations", 256,
                "max_raw_operations", 256, "max_raw_instructions", 256, "max_inputs", 256,
                "max_values", 256 * 257, "max_references", 256 * 257, "max_gaps", 256), Set.of());
        checkLimits(limits.getAsJsonObject("source"), Map.of(
                "max_bytes", MAX_DRAFT_BYTES, "max_source_bytes", 1024 * 1024,
                "max_tokens", 65536, "max_storage_pieces", 4, "max_gaps", 256), Set.of());
    }

    private static void checkLimits(JsonObject values, Map<String, Integer> maxima,
            Set<String> children) throws IOException {
        Set<String> expected = new HashSet<>(maxima.keySet());
        expected.addAll(children);
        if (!values.keySet().equals(expected)) { throw new IOException("Invalid byte limit fields."); }
        for (var bound : maxima.entrySet()) {
            JsonElement raw = values.get(bound.getKey());
            if (!raw.isJsonPrimitive() || !raw.getAsJsonPrimitive().isNumber()
                    || !raw.toString().matches("[1-9][0-9]{0,8}")
                    || raw.getAsLong() > bound.getValue()) {
                throw new IOException("Invalid byte limit value.");
            }
        }
    }

    private int limit(String group, String name) {
        return context.getAsJsonObject("limits").getAsJsonObject(group).get(name).getAsInt();
    }

    void checkRoster(FunctionManager manager) throws IOException {
        int maximum = context.getAsJsonObject("limits").get("max_functions").getAsInt();
        for (Function function : manager.getFunctions(true)) {
            if (roster.size() == maximum) {
                throw new IOException("The complete function roster exceeds its limit.");
            }
            roster.add(address(function.getEntryPoint()));
        }
    }

    void capture(Function function, DecompileResults result, DecompInterface decompiler)
            throws Exception {
        if (functions.size() >= roster.size()
                || !roster.get(functions.size()).getAsString().equals(address(function.getEntryPoint()))) {
            throw new IOException("The ordinary function roster changed.");
        }
        if (decompiler.getOptions() != null) {
            throw new IOException("This profile requires the ordinary unset options object.");
        }
        JsonObject key = object("binary_sha256", program.getExecutableSHA256(),
                "ghidra_entry", address(function.getEntryPoint()));
        JsonObject pass = object("schema", 1, "function", key,
                "call_ordinal", functions.size(),
                "ghidra_version", Application.getApplicationVersion(),
                "ghidra_revision", Application.getApplicationProperty("application.revision.ghidra"),
                "language_id", program.getLanguageID().getIdAsString(),
                "compiler_spec_id", program.getCompilerSpec().getCompilerSpecID().getIdAsString(),
                "simplification_style", decompiler.getSimplificationStyle(),
                "configured_options", null, "timeout_seconds", 60,
                "source_manifest_sha256", hash(canonical(context.get("sources"), MAX_DRAFT_BYTES)),
                "tool_manifest_sha256", hash(canonical(context.get("tools"), MAX_DRAFT_BYTES)));
        String passId = hash(canonical(pass, MAX_DRAFT_BYTES));
        JsonObject graph = null;
        JsonObject source = null;
        JsonObject facts = null;
        String reason = null;
        try {
            if (!result.decompileCompleted() || result.getHighFunction() == null
                    || result.getDecompiledFunction() == null || result.getCCodeMarkup() == null) {
                throw new Gap("decompile_unavailable");
            }
            String raw = result.getDecompiledFunction().getC();
            byte[] rawBytes = utf8(raw, limit("source", "max_source_bytes"));
            Capture capture = new Capture(function, result.getHighFunction(), key, passId);
            graph = capture.graph(hash(rawBytes));
            facts = object("value_flags", capture.valueFlags, "operation_states", capture.operationStates);
            try {
                source = capture.source(result, rawBytes);
            } catch (Gap gap) {
                reason = gap.getMessage();
                source = object("schema", 1, "function", key, "pass_id", passId,
                        "raw_c_sha256", hash(rawBytes), "raw_c_bytes", rawBytes.length,
                        "tokens", new JsonArray(), "source_status", "unavailable",
                        "gaps", array(gap("source_unbound", null)));
            }
            if (reason == null && (!graph.getAsJsonArray("export_gaps").isEmpty()
                    || !source.getAsJsonArray("gaps").isEmpty())) {
                reason = "evidence_gap";
            }
        } catch (Gap gap) {
            reason = gap.getMessage();
            graph = null;
            source = null;
            facts = null;
        }
        JsonObject record = object("function", key, "pass", pass, "pass_id", passId,
                "status", reason == null ? "complete" : "gap", "reason", reason,
                "graph", graph, "source", source, "facts", facts);
        byte[] encoded = canonical(record, MAX_DRAFT_BYTES);
        totalBytes += encoded.length;
        if (totalBytes > context.getAsJsonObject("limits").get("max_companion_bytes").getAsInt()) {
            throw new IOException("The complete byte companion exceeds its limit.");
        }
        functions.add(record);
    }

    void write(Path output) throws Exception {
        if (functions.size() != roster.size()) {
            throw new IOException("The byte function roster is incomplete.");
        }
        byte[] raw = canonical(object("schema", 1, "status", "UNPUBLISHED",
                "context", context, "functions", functions),
                context.getAsJsonObject("limits").get("max_companion_bytes").getAsInt());
        Files.write(output, raw, StandardOpenOption.CREATE_NEW);
    }

    private final class Capture {
        private final Function function;
        private final HighFunction high;
        private final JsonObject key;
        private final String passId;
        private final Set<PcodeOp> bank = Collections.newSetFromMap(new IdentityHashMap<>());
        private final Set<PcodeOp> active = Collections.newSetFromMap(new IdentityHashMap<>());
        private final Map<Varnode, JsonObject> values = new IdentityHashMap<>();
        private final Map<Integer, Varnode> localIds = new HashMap<>();
        private final JsonArray valueRecords = new JsonArray();
        private final JsonArray valueFlags = new JsonArray();
        private final JsonArray operationStates = new JsonArray();
        private final JsonArray gaps = new JsonArray();
        private final JsonArray volatileSites = new JsonArray();
        private final Set<String> volatileKeys = new HashSet<>();
        private final Set<String> gapKeys = new HashSet<>();
        private int references;

        Capture(Function function, HighFunction high, JsonObject key, String passId) {
            this.function = function;
            this.high = high;
            this.key = key;
            this.passId = passId;
        }

        private JsonObject opKey(PcodeOp op, String domain) throws Gap {
            if (op == null || op.getSeqnum().getTime() < 0 || op.getSeqnum().getTime() > 1_000_000) {
                throw new Gap("sequence_unrepresentable");
            }
            return object("function", key, "domain", domain, "pass_id", passId,
                    "sequence", object("address", location(op.getSeqnum().getTarget()),
                            "index", op.getSeqnum().getTime()));
        }

        private JsonObject blockKey(PcodeBlock block) throws Gap {
            if (block == null || block.getIndex() < 0) {
                throw new Gap("block_unrepresentable");
            }
            return object("function", key, "pass_id", passId, "index", block.getIndex());
        }

        private void addGap(String code, JsonObject operation) throws Gap {
            JsonObject item = gap(code, operation);
            if (gapKeys.add(item.toString())) {
                if (gaps.size() == limit("graph", "max_gaps")) {
                    throw new Gap("region_limit");
                }
                gaps.add(item);
            }
        }

        private JsonObject value(Varnode node) throws Gap {
            JsonObject known = values.get(node);
            if (known != null) { return known; }
            if (!(node instanceof VarnodeAST ast) || node.getSize() <= 0 || node.getSize() > 65536
                    || values.size() >= Math.min(limit("graph", "max_values"),
                        limit("graph", "max_operations") * (limit("graph", "max_inputs") + 1))) {
                throw new Gap("value_unrepresentable");
            }
            Varnode previous = localIds.putIfAbsent(ast.getUniqueId(), node);
            if (previous != null && previous != node) { throw new Gap("value_id_conflict"); }
            JsonObject id = object("function", key, "pass_id", passId,
                    "local_id", Integer.toUnsignedLong(ast.getUniqueId()));
            PcodeOp definition = node.getDef();
            if (definition != null && (!active.contains(definition) || definition.getOutput() != node)) {
                throw new Gap("definition_unrepresentable");
            }
            String kind = node.isConstant() ? "constant" : definition != null ? "defined"
                    : ast.isInput() ? "input" : ast.isFree() ? "free" : "unexplained";
            if (node.isConstant() && (definition != null || (node.getSize() < 8
                    && (node.getOffset() >>> (node.getSize() * 8)) != 0))) {
                throw new Gap("constant_unrepresentable");
            }
            if (!node.isConstant() && ((definition != null && (ast.isInput() || ast.isFree()))
                    || (ast.isInput() && ast.isFree()))) {
                throw new Gap("value_flags_conflict");
            }
            values.put(node, id);
            valueFlags.add(object("id", id, "is_input", ast.isInput(), "is_free", ast.isFree()));
            valueRecords.add(object("id", id, "storage", location(node.getAddress()),
                    "size_bytes", node.getSize(),
                    "definition", definition == null ? null : opKey(definition, "analyzed"),
                    "kind", kind, "bits", node.isConstant() ? hex(node.getOffset()) : null,
                    "address_tied", ast.isAddrTied(), "persistent", ast.isPersistent(),
                    "unaffected", ast.isUnaffected()));
            if (kind.equals("free") || kind.equals("unexplained")) { addGap("ssa_unbound", null); }
            return id;
        }

        private JsonObject operation(PcodeOp op) throws Gap {
            if (op.getNumInputs() > limit("graph", "max_inputs")) { throw new Gap("region_limit"); }
            references += op.getNumInputs() + (op.getOutput() == null ? 0 : 1);
            if (references > limit("graph", "max_references")) { throw new Gap("region_limit"); }
            JsonArray inputs = new JsonArray();
            for (int i = 0; i < op.getNumInputs(); i++) { inputs.add(value(op.getInput(i))); }
            return object("id", opKey(op, "analyzed"), "opcode", op.getMnemonic(),
                    "output", op.getOutput() == null ? null : value(op.getOutput()), "inputs", inputs);
        }

        private void evidence(PcodeOp op, String domain) throws Gap {
            JsonObject id = opKey(op, domain);
            if (!KNOWN_OPS.contains(op.getMnemonic())) { addGap("unsupported_opcode", id); }
            boolean knownVolatile = false;
            if (op.getOpcode() == PcodeOp.CALLOTHER) { addGap("volatile_or_unknown_memory", id); }
            List<Varnode> operands = new ArrayList<>();
            if (op.getOutput() != null) { operands.add(op.getOutput()); }
            for (int i = 0; i < op.getNumInputs(); i++) { operands.add(op.getInput(i)); }
            for (Varnode node : operands) {
                var block = program.getMemory().getBlock(node.getAddress());
                knownVolatile |= block != null && block.isVolatile();
            }
            if ((op.getOpcode() == PcodeOp.LOAD || op.getOpcode() == PcodeOp.STORE)
                    && op.getNumInputs() >= 2 && op.getInput(1).isConstant()) {
                var space = program.getAddressFactory().getAddressSpace((int) op.getInput(0).getOffset());
                if (space != null) {
                    var block = program.getMemory().getBlock(space.getAddress(op.getInput(1).getOffset()));
                    knownVolatile |= block != null && block.isVolatile();
                }
            }
            if (knownVolatile) {
                if (volatileKeys.add(id.toString())) { volatileSites.add(id); }
                addGap("volatile_or_unknown_memory", id);
            }
        }

        JsonObject graph(String sourceHash) throws Exception {
            int listingBlocks = 0;
            var listingIterator = new BasicBlockModel(program).getCodeBlocksContaining(function.getBody(), TaskMonitor.DUMMY);
            while (listingIterator.hasNext()) {
                listingIterator.next();
                if (++listingBlocks > limit("graph", "max_blocks")) { throw new Gap("region_limit"); }
            }
            var ram = program.getAddressFactory().getDefaultAddressSpace();
            if (!ram.getName().equals("ram") || ram.getSize() != 64 || ram.getAddressableUnitSize() != 1
                    || program.getLanguage().isBigEndian()) { throw new Gap("unsupported_profile"); }
            var blocks = high.getBasicBlocks();
            if (blocks.size() > limit("graph", "max_blocks")) { throw new Gap("region_limit"); }
            Set<PcodeBlock> owners = Collections.newSetFromMap(new IdentityHashMap<>());
            Set<Integer> indices = new HashSet<>();
            JsonObject entry = null;
            for (PcodeBlockBasic block : blocks) {
                if (!owners.add(block) || !indices.add(block.getIndex())
                        || !function.getBody().contains(block.getStart())) { throw new Gap("block_unrepresentable"); }
                if (block.getIndex() == 0) { entry = blockKey(block); }
                var it = block.getIterator();
                while (it.hasNext()) {
                    PcodeOp op = it.next();
                    if (!(op instanceof PcodeOpAST ast) || ast.getParent() != block
                            || !active.add(op)) { throw new Gap("operation_ownership_conflict"); }
                    if (ast.isDead()) { addGap("cfg_unclosed", opKey(op, "analyzed")); }
                    if (active.size() > limit("graph", "max_operations")) { throw new Gap("region_limit"); }
                }
            }
            if (entry == null || blocks.stream().noneMatch(b -> b.getIndex() == 0
                    && b.getStart().equals(function.getEntryPoint()))) { throw new Gap("entry_unrepresentable"); }
            JsonArray dead = new JsonArray();
            var it = high.getPcodeOps();
            Set<String> sequences = new HashSet<>();
            while (it.hasNext()) {
                PcodeOpAST op = it.next();
                if (bank.size() == limit("graph", "max_operations")) { throw new Gap("region_limit"); }
                if (!bank.add(op) || !sequences.add(opKey(op, "analyzed").toString())) {
                    throw new Gap("operation_id_conflict");
                }
                if (op.getNumInputs() > limit("graph", "max_inputs")) { throw new Gap("region_limit"); }
                if (!active.contains(op)) {
                    if (!op.isDead() || op.getParent() != null) { throw new Gap("dead_partition_conflict"); }
                    dead.add(opKey(op, "analyzed"));
                }
                operationStates.add(object("id", opKey(op, "analyzed"), "is_dead", op.isDead(),
                        "parent", op.getParent() == null ? null : blockKey(op.getParent())));
                evidence(op, "analyzed");
            }
            if (!bank.containsAll(active)) { throw new Gap("operation_inventory_conflict"); }
            JsonArray sites = new JsonArray();
            int rawCount = 0;
            for (var instruction : program.getListing().getInstructions(function.getBody(), true)) {
                if (sites.size() == limit("graph", "max_raw_instructions")) { throw new Gap("region_limit"); }
                sites.add(address(instruction.getAddress()));
                for (PcodeOp op : instruction.getPcode()) {
                    if (++rawCount > limit("graph", "max_raw_operations")
                            || op.getNumInputs() > limit("graph", "max_inputs")) { throw new Gap("region_limit"); }
                    evidence(op, "raw");
                }
            }
            JsonArray output = new JsonArray();
            for (PcodeBlockBasic block : blocks) {
                JsonArray operations = new JsonArray();
                boolean pastPhi = false;
                boolean conditional = false;
                var ops = block.getIterator();
                while (ops.hasNext()) {
                    PcodeOp op = ops.next();
                    if (conditional) { throw new Gap("conditional_unrepresentable"); }
                    if (op.getOpcode() == PcodeOp.MULTIEQUAL) {
                        if (pastPhi || block.getInSize() == 0 || op.getNumInputs() != block.getInSize()
                                || op.getOutput() == null) { throw new Gap("phi_unrepresentable"); }
                    } else { pastPhi = true; }
                    conditional = op.getOpcode() == PcodeOp.CBRANCH;
                    if (conditional && (block.getOutSize() != 2 || op.getNumInputs() != 2
                            || op.getOutput() != null || block.getFalseOut() != block.getOut(0)
                            || block.getTrueOut() != block.getOut(1))) { throw new Gap("conditional_unrepresentable"); }
                    operations.add(operation(op));
                }
                output.add(object("id", blockKey(block), "start", address(block.getStart()),
                        "incoming", edges(block, true, owners), "outgoing", edges(block, false, owners),
                        "false_slot", conditional ? 0 : null, "true_slot", conditional ? 1 : null,
                        "operations", operations));
            }
            return object("schema", 1, "binary_sha256", program.getExecutableSHA256(),
                    "function", key, "pass_id", passId, "raw_c_sha256", sourceHash,
                    "ram_space_id", Integer.toUnsignedLong(ram.getSpaceID()), "ram_word_bytes", 1,
                    "address_bits", 64, "byte_bits", 8, "endian", "little", "entry", entry,
                    "blocks", output, "values", valueRecords, "excluded_dead", dead,
                    "raw_instruction_sites", sites, "explicit_volatile_sites", volatileSites,
                    "export_gaps", gaps);
        }

        private JsonArray edges(PcodeBlock block, boolean incoming, Set<PcodeBlock> owners) throws Gap {
            int count = incoming ? block.getInSize() : block.getOutSize();
            if (count > limit("graph", "max_blocks")) { throw new Gap("region_limit"); }
            JsonArray result = new JsonArray();
            Set<PcodeBlock> seen = Collections.newSetFromMap(new IdentityHashMap<>());
            for (int i = 0; i < count; i++) {
                var other = incoming ? block.getIn(i) : block.getOut(i);
                int reverse = incoming ? block.getInRevIndex(i) : block.getOutRevIndex(i);
                if (!owners.contains(other) || !seen.add(other) || reverse < 0
                        || reverse >= (incoming ? other.getOutSize() : other.getInSize())
                        || (incoming ? other.getOut(reverse) : other.getIn(reverse)) != block
                        || (incoming ? other.getOutRevIndex(reverse) : other.getInRevIndex(reverse)) != i) {
                    throw new Gap("edge_unrepresentable");
                }
                result.add(object("other", blockKey(other), "reciprocal_slot", reverse));
            }
            return result;
        }

        JsonObject source(DecompileResults result, byte[] raw) throws Exception {
            var printer = new PrettyPrinter(function, result.getCCodeMarkup(), null);
            JsonArray tokens = new JsonArray();
            JsonArray sourceGaps = new JsonArray();
            int offset = 0;
            for (var line : printer.getLines()) {
                offset = match(raw, offset, line.getIndentString());
                for (ClangToken token : line.getAllTokens()) {
                    if (tokens.size() == limit("source", "max_tokens")) { throw new Gap("region_limit"); }
                    int start = offset;
                    offset = match(raw, offset, token.getText());
                    if (offset == start) { throw new Gap("empty_printer_token"); }
                    PcodeOp op = token.getPcodeOp();
                    Varnode node = token.getVarnode();
                    if ((op != null && !bank.contains(op)) || (node != null && !values.containsKey(node))) {
                        throw new Gap("source_link_unavailable");
                    }
                    // A null high function disables the API's storage-address fallback.
                    var symbol = token.getHighSymbol(null);
                    Integer formal = null;
                    JsonArray storage = new JsonArray();
                    if (symbol != null) {
                        if (symbol.isParameter()) {
                            formal = symbol.getCategoryIndex();
                            if (formal < 0 || formal > 127) { throw new Gap("source_link_unavailable"); }
                        }
                        var pieces = symbol.getStorage();
                        if (pieces == null || pieces.isBadStorage() || pieces.isUnassignedStorage()
                                || pieces.isVoidStorage()) { throw new Gap("source_link_unavailable"); }
                        if (pieces.getVarnodeCount() > limit("source", "max_storage_pieces")) {
                            throw new Gap("region_limit");
                        }
                        for (Varnode piece : pieces.getVarnodes()) {
                            if (piece.getSize() <= 0 || piece.getSize() > 8192) { throw new Gap("source_link_unavailable"); }
                            var reg = program.getRegister(piece.getAddress(), piece.getSize());
                            storage.add(object("address", location(piece.getAddress()), "size", piece.getSize(),
                                    "register", reg == null ? null : reg.getName(),
                                    "stack_offset", piece.getAddress().isStackAddress() ? piece.getOffset() : null));
                        }
                    }
                    tokens.add(object("ordinal", tokens.size(), "span", object("start", start, "end", offset),
                            "kind", token.getClass().getSimpleName(),
                            "text_sha256", hash(java.util.Arrays.copyOfRange(raw, start, offset)),
                            "operation", op == null ? null : opKey(op, "analyzed"),
                            "value", node == null ? null : values.get(node),
                            "formal_ordinal", formal, "symbol_storage", storage));
                }
                offset = match(raw, offset, StringUtilities.LINE_SEPARATOR);
            }
            if (offset != raw.length) { throw new Gap("printer_bytes_differ"); }
            return object("schema", 1, "function", key, "pass_id", passId,
                    "raw_c_sha256", hash(raw), "raw_c_bytes", raw.length, "tokens", tokens,
                    "source_status", "exact_printer_bytes", "gaps", sourceGaps);
        }
    }

    private static int match(byte[] raw, int offset, String text) throws Gap {
        byte[] part = utf8(text, raw.length);
        if (offset > raw.length - part.length) { throw new Gap("printer_bytes_differ"); }
        for (int i = 0; i < part.length; i++) {
            if (raw[offset + i] != part[i]) { throw new Gap("printer_bytes_differ"); }
        }
        return offset + part.length;
    }

    private static byte[] utf8(String text, int maximum) throws Gap {
        if (text == null || text.length() > maximum) { throw new Gap("region_limit"); }
        for (int i = 0; i < text.length(); i++) {
            char ch = text.charAt(i);
            if (Character.isHighSurrogate(ch)) {
                if (++i == text.length() || !Character.isLowSurrogate(text.charAt(i))) {
                    throw new Gap("source_link_unavailable");
                }
            } else if (Character.isLowSurrogate(ch)) { throw new Gap("source_link_unavailable"); }
        }
        byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
        if (bytes.length > maximum) { throw new Gap("region_limit"); }
        return bytes;
    }

    private static String address(Address address) {
        return hex(address.getOffset());
    }

    private static String hex(long value) { return "0x" + Long.toUnsignedString(value, 16); }

    private static JsonObject location(Address address) throws Gap {
        if (address == null || address.equals(Address.NO_ADDRESS)) { throw new Gap("address_unrepresentable"); }
        return object("space", address.getAddressSpace().getName(), "offset", hex(address.getOffset()));
    }

    private static JsonObject gap(String code, JsonObject operation) {
        return object("code", code, "block", null, "operation", operation, "value", null);
    }

    private static JsonArray array(JsonElement element) {
        JsonArray result = new JsonArray();
        result.add(element);
        return result;
    }

    private static JsonObject object(Object... pairs) {
        JsonObject object = new JsonObject();
        for (int i = 0; i < pairs.length; i += 2) {
            Object value = pairs[i + 1];
            JsonElement element = value == null ? JsonNull.INSTANCE : value instanceof JsonElement e ? e
                    : value instanceof Number n ? new JsonPrimitive(n)
                    : value instanceof Boolean b ? new JsonPrimitive(b) : new JsonPrimitive((String) value);
            object.add((String) pairs[i], element);
        }
        return object;
    }

    private static String hash(byte[] bytes) throws NoSuchAlgorithmException {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    static byte[] canonical(JsonElement value, int maximum) throws IOException {
        StringBuilder out = new StringBuilder();
        canonical(value, out, maximum);
        if (out.length() >= maximum) { throw new IOException("The canonical byte limit was exceeded."); }
        return out.append('\n').toString().getBytes(StandardCharsets.US_ASCII);
    }

    private static void canonical(JsonElement value, StringBuilder out, int maximum) throws IOException {
        if (value.isJsonObject()) {
            out.append('{');
            boolean comma = false;
            for (String key : value.getAsJsonObject().keySet().stream().sorted().toList()) {
                if (comma) { out.append(','); }
                quote(key, out, maximum);
                out.append(':');
                canonical(value.getAsJsonObject().get(key), out, maximum);
                comma = true;
            }
            out.append('}');
        } else if (value.isJsonArray()) {
            out.append('[');
            boolean comma = false;
            for (JsonElement child : value.getAsJsonArray()) {
                if (comma) { out.append(','); }
                canonical(child, out, maximum);
                comma = true;
            }
            out.append(']');
        } else if (value.isJsonPrimitive() && value.getAsJsonPrimitive().isString()) {
            quote(value.getAsString(), out, maximum);
        } else { out.append(value); }
        if (out.length() > maximum) { throw new IOException("The canonical byte limit was exceeded."); }
    }

    private static void quote(String value, StringBuilder out, int maximum) throws IOException {
        out.append('"');
        for (int i = 0; i < value.length(); i++) {
            char ch = value.charAt(i);
            switch (ch) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\b' -> out.append("\\b");
                case '\f' -> out.append("\\f");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (ch < 32 || ch > 126) {
                        out.append("\\u");
                        for (int shift = 12; shift >= 0; shift -= 4) {
                            out.append("0123456789abcdef".charAt((ch >> shift) & 15));
                        }
                    } else { out.append(ch); }
                }
            }
            if (out.length() > maximum) { throw new IOException("The canonical byte limit was exceeded."); }
        }
        out.append('"');
    }
}
