import com.google.gson.Gson;
import ghidra.app.decompiler.ClangCaseToken;
import ghidra.app.decompiler.ClangOpToken;
import ghidra.app.decompiler.ClangVariableToken;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.decompiler.PrettyPrinter;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.pcode.PcodeBlockBasic;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.Varnode;
import ghidra.util.StringUtilities;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;

final class OrdinarySwitchEvidence {
    private static final int MAX_FUNCTIONS = 32;
    private static final int MAX_SOURCE_BYTES = 1024 * 1024;
    private static final int MAX_TOKENS = 65_536;
    private static final int MAX_MARKERS = 4_100;
    private static final int MAX_NEIGHBORS = 32;
    private static final int MAX_FUNCTION_BYTES = 4 * 1024 * 1024;
    private static final int MAX_TOTAL_BYTES = 16 * 1024 * 1024;
    private static final int MAX_LIFT_BYTES = 64 * 1024 * 1024;

    private record Location(String space, String offset) {}
    private record Storage(Location address, int size) {}
    private record Operation(Location address, int index, String opcode) {}
    private record Parameter(int ordinal, List<Storage> storage,
                             Storage operand, Operation definition) {}
    private record Block(int index, Location entry, List<Operation> indirectEntries,
                         List<Integer> successors) {}
    private record Marker(int start, int end, String kind, String value,
                          Operation operation, Block block, Parameter parameter) {}
    private record Body(Location function, String sourceSha256, int sourceBytes,
                        List<Marker> markers) {}
    private record Gap(Location function, String reason) {}
    private record Manifest(int schemaVersion, String binarySha256, String liftSha256,
                            List<Body> bodies, List<Gap> gaps) {}

    private static final class GapError extends Exception {
        GapError(String reason) {
            super(reason);
        }
    }

    private final Gson gson;
    private final List<Body> bodies = new ArrayList<>();
    private final List<Gap> gaps = new ArrayList<>();
    private int bytes;

    OrdinarySwitchEvidence(Gson gson) {
        this.gson = gson;
    }

    private static Location location(Address address) {
        return new Location(address.getAddressSpace().getName(),
                "0x" + Long.toUnsignedString(address.getOffset(), 16));
    }

    private static Storage storage(Varnode node) {
        return node == null ? null : new Storage(location(node.getAddress()), node.getSize());
    }

    private static Operation operation(PcodeOp op) {
        return op == null ? null : new Operation(location(op.getSeqnum().getTarget()),
                op.getSeqnum().getTime(), op.getMnemonic());
    }

    private static Block block(PcodeOp op) throws GapError {
        if (op == null || op.getParent() == null) {
            throw new GapError("unbound_ordinary_operation");
        }
        var block = op.getParent();
        if (block.getInSize() > MAX_NEIGHBORS || block.getOutSize() > MAX_NEIGHBORS) {
            throw new GapError("ordinary_block_limit");
        }
        List<Operation> incoming = new ArrayList<>();
        for (int index = 0; index < block.getInSize(); index++) {
            if (block.getIn(index) instanceof PcodeBlockBasic predecessor
                    && predecessor.getLastOp() != null
                    && predecessor.getLastOp().getOpcode() == PcodeOp.BRANCHIND) {
                incoming.add(operation(predecessor.getLastOp()));
            }
        }
        List<Integer> outgoing = new ArrayList<>();
        for (int index = 0; index < block.getOutSize(); index++) {
            outgoing.add(block.getOut(index).getIndex());
        }
        return new Block(block.getIndex(), location(block.getStart()), incoming, outgoing);
    }

    private static byte[] utf8(String value) {
        return value.getBytes(StandardCharsets.UTF_8);
    }

    private static Body collect(Function function, DecompileResults result) throws Exception {
        if (!result.decompileCompleted() || result.getCCodeMarkup() == null
                || result.getHighFunction() == null || result.getDecompiledFunction() == null) {
            throw new GapError("ordinary_source_unavailable");
        }
        String raw = result.getDecompiledFunction().getC();
        byte[] rawBytes = utf8(raw);
        if (rawBytes.length == 0 || rawBytes.length > MAX_SOURCE_BYTES) {
            throw new GapError("ordinary_source_limit");
        }
        var printer = new PrettyPrinter(function, result.getCCodeMarkup(), null);
        List<Marker> markers = new ArrayList<>();
        var reconstructed = new StringBuilder();
        int offset = 0;
        int count = 0;
        boolean hasSwitch = false;
        for (var line : printer.getLines()) {
            String indent = line.getIndentString();
            var printed = new StringBuilder(indent);
            offset += utf8(indent).length;
            boolean selectorLine = line.getAllTokens().stream().anyMatch(
                    token -> token instanceof ClangOpToken && token.getText().equals("switch"));
            for (var token : line.getAllTokens()) {
                if (++count > MAX_TOKENS) {
                    throw new GapError("ordinary_token_limit");
                }
                String text = token.getText();
                printed.append(text);
                int next = offset + utf8(text).length;
                if (next > rawBytes.length) {
                    throw new GapError("ordinary_source_mismatch");
                }
                String kind = null;
                String value = null;
                Parameter parameter = null;
                if (token instanceof ClangCaseToken label) {
                    kind = text.equals("default") ? "default" : "case";
                    value = kind.equals("case") ? Long.toUnsignedString(label.getValue()) : null;
                } else if (token instanceof ClangOpToken && text.equals("switch")) {
                    kind = "switch";
                    hasSwitch = true;
                } else if (token instanceof ClangOpToken && text.equals("return")) {
                    kind = "return";
                } else if (selectorLine && token instanceof ClangVariableToken
                        && text.matches("[A-Za-z_][A-Za-z0-9_]*")) {
                    var symbol = token.getHighSymbol(result.getHighFunction());
                    var node = token.getVarnode();
                    if (symbol == null || !symbol.isParameter() || symbol.getStorage() == null
                            || symbol.getStorage().getVarnodeCount() < 1
                            || symbol.getStorage().getVarnodeCount() > 4 || node == null
                            || symbol.getCategoryIndex() < 0 || symbol.getCategoryIndex() > 127) {
                        throw new GapError("unbound_ordinary_selector");
                    }
                    kind = "parameter";
                    parameter = new Parameter(symbol.getCategoryIndex(),
                            Arrays.stream(symbol.getStorage().getVarnodes())
                                    .map(OrdinarySwitchEvidence::storage).toList(),
                            storage(node), operation(node.getDef()));
                }
                if (kind != null) {
                    if (markers.size() == MAX_MARKERS) {
                        throw new GapError("ordinary_marker_limit");
                    }
                    var op = token.getPcodeOp();
                    if (op == null) {
                        throw new GapError("unbound_ordinary_operation");
                    }
                    Block owner = kind.equals("switch") || kind.equals("parameter")
                            ? null : block(op);
                    markers.add(new Marker(offset, next, kind, value, operation(op),
                            owner, parameter));
                }
                offset = next;
            }
            if (!PrettyPrinter.getText(line).contentEquals(printed)) {
                throw new GapError("ordinary_source_mismatch");
            }
            reconstructed.append(printed).append(StringUtilities.LINE_SEPARATOR);
            offset += utf8(StringUtilities.LINE_SEPARATOR).length;
        }
        if (!hasSwitch) {
            throw new GapError("ordinary_switch_unavailable");
        }
        if (!raw.contentEquals(reconstructed) || offset != rawBytes.length) {
            throw new GapError("ordinary_source_mismatch");
        }
        return new Body(location(function.getEntryPoint()), digest(rawBytes), rawBytes.length,
                List.copyOf(markers));
    }

    private static String digest(byte[] raw) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw));
    }

    void capture(Function function, DecompileResults result) throws Exception {
        if (bodies.size() + gaps.size() == MAX_FUNCTIONS) {
            throw new IllegalArgumentException("The ordinary switch scope exceeds 32 functions.");
        }
        try {
            Body body = collect(function, result);
            int size = utf8(gson.toJson(body)).length;
            if (size > MAX_FUNCTION_BYTES || bytes + size > MAX_TOTAL_BYTES) {
                throw new GapError("ordinary_evidence_limit");
            }
            bodies.add(body);
            bytes += size;
        } catch (GapError gap) {
            gaps.add(new Gap(location(function.getEntryPoint()), gap.getMessage()));
        }
    }

    void write(Path output, Path lift, String binary) throws Exception {
        if (binary == null || !binary.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("The binary digest is unavailable.");
        }
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream stream = Files.newInputStream(lift)) {
            byte[] buffer = new byte[8192];
            int count;
            int total = 0;
            while ((count = stream.read(buffer)) != -1) {
                total += count;
                if (total > MAX_LIFT_BYTES) {
                    throw new IllegalArgumentException("The ordinary lift exceeds 64 MiB.");
                }
                digest.update(buffer, 0, count);
            }
        }
        byte[] record = utf8(gson.toJson(new Manifest(1, binary,
                HexFormat.of().formatHex(digest.digest()), bodies, gaps)));
        if (record.length > MAX_TOTAL_BYTES) {
            throw new IllegalArgumentException("The ordinary switch artifact exceeds 16 MiB.");
        }
        Files.write(output, record, StandardOpenOption.CREATE_NEW);
    }
}
