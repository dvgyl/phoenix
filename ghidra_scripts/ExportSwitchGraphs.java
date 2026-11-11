// Export the optional normalized switch graphs.
// @category Phoenix

import com.google.gson.FieldNamingPolicy;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.pcode.PcodeBlockBasic;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.Varnode;

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
import java.util.Objects;

public class ExportSwitchGraphs extends GhidraScript {
    private static final int MAX_INSTRUCTIONS = 1_000_000;
    private static final int MAX_CANDIDATES = 32;
    private static final int MAX_BLOCKS = 512;
    private static final int MAX_OPERATIONS = 4096;
    private static final int MAX_INPUTS = 256;
    private static final int MAX_OPERANDS = 16_384;
    private static final int MAX_GRAPH_BYTES = 4 * 1024 * 1024;
    private static final int MAX_TOTAL_BYTES = 16 * 1024 * 1024;
    private static final int MAX_LIFT_BYTES = 64 * 1024 * 1024;

    private record Location(String space, String offset) {}
    private record Sequence(Location address, int index) {}
    private record Operand(Location address, int size, Sequence definition) {}
    private record Operation(Sequence sequence, String opcode, Operand output,
                             List<Operand> inputs) {}
    private record Block(int index, Location start, List<Integer> successors,
                         Integer trueOut, Integer falseOut, List<Operation> operations) {}
    private record Graph(int schemaVersion, String binarySha256, String liftSha256,
                         String style, int memorySpaceId, Location function, List<Block> blocks) {}
    private record GraphFile(Location function, String file, String sha256) {}
    private record Gap(Location function, String reason) {}
    private record Manifest(int schemaVersion, String binarySha256, String liftSha256,
                            List<GraphFile> graphs, List<Gap> gaps) {}

    private static final class UnavailableGraph extends Exception {
        UnavailableGraph(String reason) {
            super(reason);
        }
    }

    private static Location location(Address address) {
        return address == null || address.equals(Address.NO_ADDRESS) ? null
                : new Location(address.getAddressSpace().getName(),
                        "0x" + Long.toUnsignedString(address.getOffset(), 16));
    }

    private static Sequence sequence(PcodeOp operation) {
        return operation == null ? null
                : new Sequence(location(operation.getSeqnum().getTarget()),
                        operation.getSeqnum().getTime());
    }

    private static Operand operand(Varnode node) {
        return node == null ? null
                : new Operand(location(node.getAddress()), node.getSize(), sequence(node.getDef()));
    }

    private static Operation boundedOperation(PcodeOp op) throws UnavailableGraph {
        if (op.getNumInputs() > MAX_INPUTS
                || location(op.getSeqnum().getTarget()) == null
                || Arrays.stream(op.getInputs()).anyMatch(Objects::isNull)) {
            throw new UnavailableGraph("unsupported_operation");
        }
        return new Operation(sequence(op), op.getMnemonic(), operand(op.getOutput()),
                Arrays.stream(op.getInputs()).map(ExportSwitchGraphs::operand).toList());
    }

    private static String liftDigest(Path lift) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        int bytes = 0;
        try (InputStream input = Files.newInputStream(lift)) {
            byte[] chunk = new byte[8192];
            int count;
            while ((count = input.read(chunk)) != -1) {
                bytes += count;
                if (bytes > MAX_LIFT_BYTES) {
                    throw new IllegalArgumentException("The ordinary lift exceeds its size limit.");
                }
                digest.update(chunk, 0, count);
            }
        }
        if (bytes == 0) {
            throw new IllegalArgumentException("The ordinary lift is empty.");
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private List<Function> candidates() throws Exception {
        List<Function> selected = new ArrayList<>();
        int inspected = 0;
        for (Function function : currentProgram.getFunctionManager().getFunctions(true)) {
            if (function.isThunk()) {
                continue;
            }
            var instructions = currentProgram.getListing().getInstructions(function.getBody(), true);
            while (instructions.hasNext()) {
                monitor.checkCancelled();
                if (++inspected > MAX_INSTRUCTIONS) {
                    throw new IllegalArgumentException("The switch scan exceeds its instruction limit.");
                }
                Instruction instruction = instructions.next();
                if (instruction.getFlowType().isJump() && instruction.getFlowType().isComputed()
                        && Arrays.stream(instruction.getPcode()).anyMatch(
                                op -> op.getOpcode() == PcodeOp.BRANCHIND)) {
                    selected.add(function);
                    if (selected.size() > MAX_CANDIDATES) {
                        throw new IllegalArgumentException("The switch scan exceeds its function limit.");
                    }
                    break;
                }
            }
        }
        return selected;
    }

    private Graph normalize(
            DecompInterface decompiler, Function function, String binary, String lift)
            throws Exception {
        DecompileResults result = decompiler.decompileFunction(function, 5, monitor);
        monitor.checkCancelled();
        if (!result.decompileCompleted() || result.getHighFunction() == null) {
            throw new UnavailableGraph("normalize_unavailable");
        }
        var blocks = result.getHighFunction().getBasicBlocks();
        if (blocks.isEmpty() || blocks.size() > MAX_BLOCKS) {
            throw new UnavailableGraph("block_limit");
        }
        List<Block> converted = new ArrayList<>();
        int operations = 0;
        int operands = 0;
        for (PcodeBlockBasic block : blocks) {
            monitor.checkCancelled();
            if (location(block.getStart()) == null || block.getOutSize() > MAX_OPERATIONS) {
                throw new UnavailableGraph("unsupported_block");
            }
            List<Operation> body = new ArrayList<>();
            var iterator = block.getIterator();
            while (iterator.hasNext()) {
                PcodeOp op = iterator.next();
                operands += op.getNumInputs() + (op.getOutput() == null ? 0 : 1);
                if (++operations > MAX_OPERATIONS || operands > MAX_OPERANDS) {
                    throw new UnavailableGraph("operation_limit");
                }
                body.add(boundedOperation(op));
            }
            List<Integer> successors = new ArrayList<>();
            for (int i = 0; i < block.getOutSize(); i++) {
                successors.add(block.getOut(i).getIndex());
            }
            boolean conditional = !body.isEmpty() && body.getLast().opcode().equals("CBRANCH");
            if (conditional && (successors.size() != 2
                    || block.getTrueOut() == block.getFalseOut())) {
                throw new UnavailableGraph("unsupported_conditional");
            }
            converted.add(new Block(block.getIndex(), location(block.getStart()), successors,
                    conditional ? block.getTrueOut().getIndex() : null,
                    conditional ? block.getFalseOut().getIndex() : null, body));
        }
        int memorySpace = currentProgram.getAddressFactory().getDefaultAddressSpace().getSpaceID();
        return new Graph(1, binary, lift, "normalize", memorySpace,
                location(function.getEntryPoint()), converted);
    }

    @Override
    public void run() throws Exception {
        String[] arguments = getScriptArgs();
        if (arguments.length != 2) {
            throw new IllegalArgumentException("Supply the switch directory and ordinary lift path.");
        }
        Path output = Path.of(arguments[0]);
        String lift = liftDigest(Path.of(arguments[1]));
        String binary = currentProgram.getExecutableSHA256();
        if (binary == null || !binary.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("The binary digest is unavailable.");
        }
        List<Function> selected = candidates();
        Gson gson = new GsonBuilder().serializeNulls()
                .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES).create();
        Files.createDirectory(output);
        List<GraphFile> files = new ArrayList<>();
        List<Gap> gaps = new ArrayList<>();
        DecompInterface decompiler = new DecompInterface();
        int bytes = 0;
        try {
            if (!selected.isEmpty() && (!decompiler.openProgram(currentProgram)
                    || !decompiler.setSimplificationStyle("normalize"))) {
                throw new IllegalStateException("Ghidra normalize mode is unavailable.");
            }
            for (Function function : selected) {
                Location address = location(function.getEntryPoint());
                try {
                    Graph graph = normalize(decompiler, function, binary, lift);
                    byte[] data = gson.toJson(graph).getBytes(StandardCharsets.UTF_8);
                    if (data.length > MAX_GRAPH_BYTES || bytes + data.length > MAX_TOTAL_BYTES) {
                        throw new UnavailableGraph("byte_limit");
                    }
                    String name = "graph-" + address.offset().substring(2) + ".json";
                    Files.write(output.resolve(name), data, StandardOpenOption.CREATE_NEW);
                    String digest = HexFormat.of().formatHex(
                            MessageDigest.getInstance("SHA-256").digest(data));
                    files.add(new GraphFile(address, name, digest));
                    bytes += data.length;
                } catch (UnavailableGraph unavailable) {
                    gaps.add(new Gap(address, unavailable.getMessage()));
                }
            }
        } finally {
            decompiler.dispose();
        }
        byte[] manifest = gson.toJson(new Manifest(1, binary, lift, files, gaps))
                .getBytes(StandardCharsets.UTF_8);
        Files.write(output.resolve("manifest.json"), manifest, StandardOpenOption.CREATE_NEW);
    }
}
