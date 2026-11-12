// Export Phoenix lift evidence as JSON.
// @category Phoenix

import java.io.BufferedWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.Map;

import com.google.gson.FieldNamingPolicy;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import ghidra.app.decompiler.ClangNode;
import ghidra.app.decompiler.ClangStatement;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.block.BasicBlockModel;
import ghidra.program.model.block.CodeBlock;
import ghidra.program.model.block.CodeBlockIterator;
import ghidra.program.model.block.CodeBlockReference;
import ghidra.program.model.block.CodeBlockReferenceIterator;
import ghidra.program.model.data.StringDataInstance;
import ghidra.program.model.data.DataType;
import ghidra.program.model.data.Pointer;
import ghidra.program.model.data.Array;
import ghidra.program.model.data.TypeDef;
import ghidra.program.model.data.Structure;
import ghidra.program.model.data.Union;
import ghidra.program.model.data.FunctionDefinition;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.VariableStorage;
import ghidra.program.model.pcode.HighFunction;
import ghidra.program.model.pcode.FunctionPrototype;
import ghidra.program.model.pcode.HighSymbol;
import ghidra.program.model.pcode.JumpTable;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.Varnode;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.symbol.ExternalLocation;
import ghidra.program.model.symbol.ExternalLocationIterator;
import ghidra.program.model.symbol.ExternalManager;
import ghidra.program.model.symbol.FlowType;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceManager;

public class ExportLift extends GhidraScript {
    private record Location(String space, String offset) {}
    private record Range(Location start, Location end) {}
    private record Operand(Location address, int size, Sequence definition) {}
    private record Sequence(Location address, int index) {}
    private record Operation(Sequence sequence, String opcode, Operand output,
            List<Operand> inputs) {}
    private record DecodedInstruction(Location address, int size, String text,
            List<Operation> pcode) {}
    private record Statement(String text, Location start, Location end, Sequence operation) {}
    private record Decompilation(String rawC, String status, String diagnostic,
            List<Operation> analyzedPcode, List<Statement> statements) {}
    private record Parameter(String name, String type) {}
    private record Signature(String callingConvention, String returnType,
            List<Parameter> parameters, boolean variadic) {}
    private record Block(Location entry, List<Range> ranges) {}
    private record FlowEdge(Location fromBlock, Location toBlock, Location site,
            Location target, String kind) {}
    private record CallEdge(Location caller, Location site, Location target, String kind,
            boolean indirect) {}
    private record LiftedFunction(Location entry, String name, Signature signature,
            Location thunkTarget, List<Range> ranges, Decompilation decompilation,
            List<DecodedInstruction> instructions, List<Block> blocks, List<FlowEdge> flowEdges,
            StaticEvidence staticEvidence) {}
    private record Import(Location address, String library, String name, Location libraryAddress) {}
    private record DefinedString(Location address, String value, String type, int size) {}
    private record DataReference(Location from, Location to, String kind, int operandIndex) {}
    private record MainEvidence(Location entry, Location startup, Location setup, Location call) {}
    private record LiftExport(int schemaVersion, Location imageBase, MainEvidence main,
            List<LiftedFunction> functions,
            List<Import> imports, List<DefinedString> strings, List<DataReference> dataReferences,
            List<CallEdge> callEdges) {}

    private record TypeEvidence(String id, String path, String name, String kind,
            int size, String target, Integer count) {}
    private record RegisterEvidence(String name, Location address, int bits,
            String base, int leastBit) {}
    private record StoragePiece(Location address, int size, String register, Long stackOffset) {}
    private record StorageEvidence(String state, int size, boolean forcedIndirect,
            String autoParameter, List<StoragePiece> pieces) {}
    private record Slot(String name, String type, StorageEvidence storage) {}
    private record PrototypeEvidence(String source, String callingConvention,
            Boolean customStorage, boolean variadic, boolean noReturn,
            List<Slot> parameters, Slot result) {}
    private record JumpEvidence(Location site, List<Location> targets, List<Integer> labels) {}
    private record StaticEvidence(int schemaVersion, String status, PrototypeEvidence listing,
            PrototypeEvidence decompiler, List<TypeEvidence> types,
            List<RegisterEvidence> registers, List<JumpEvidence> jumpTables) {}
    private record Decompiled(Decompilation code, HighFunction high) {}

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        boolean byteDiagnostic = args.length == 4 && args[1].equals("--byte-diagnostic");
        if (!byteDiagnostic && (args.length < 1 || args.length > 2)) {
            throw new IllegalArgumentException(
                    "Supply the lift path and an optional ordinary switch evidence path.");
        }
        Path output = Path.of(args[0]).toAbsolutePath();
        Gson gson = new GsonBuilder()
                .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
                .serializeNulls().disableHtmlEscaping().create();
        OrdinarySwitchEvidence switches = args.length == 2 ? new OrdinarySwitchEvidence(gson) : null;
        OrdinaryByteEvidence bytes = byteDiagnostic ? new OrdinaryByteEvidence(currentProgram,
                getSourceFile().getFile(false).toPath().getParent(), Path.of(args[3])) : null;
        LiftExport export = collectEvidence(switches, bytes);
        Path partial = Files.createTempFile(output.getParent(), ".lift-", ".json");
        try {
            try (BufferedWriter writer = Files.newBufferedWriter(partial)) {
                gson.toJson(export, writer);
            }
            monitor.checkCancelled();
            Files.move(partial, output, StandardCopyOption.ATOMIC_MOVE);
        } finally {
            Files.deleteIfExists(partial);
        }
        if (bytes != null) {
            bytes.write(Path.of(args[2]));
        }
        if (switches != null) {
            switches.write(Path.of(args[1]), output, currentProgram.getExecutableSHA256());
        }
    }

    private LiftExport collectEvidence(OrdinarySwitchEvidence switches, OrdinaryByteEvidence bytes) throws Exception {
        Listing listing = currentProgram.getListing();
        FunctionManager functions = currentProgram.getFunctionManager();
        BasicBlockModel blockModel = new BasicBlockModel(currentProgram);
        List<LiftedFunction> lifted = new ArrayList<>();
        MainEvidence main = recoverGlibcMain(listing, functions);
        if (bytes != null) { bytes.checkRoster(functions); }
        DecompInterface decompiler = new DecompInterface();
        try {
            if (!decompiler.openProgram(currentProgram)) {
                throw new IllegalStateException(decompiler.getLastMessage());
            }
            for (Function function : functions.getFunctions(true)) {
                monitor.checkCancelled();
                lifted.add(liftFunction(function, listing, blockModel, decompiler, switches, bytes));
            }
        } finally {
            decompiler.dispose();
        }
        return new LiftExport(1, location(currentProgram.getImageBase()), main, lifted,
                imports(), strings(listing), dataReferences(), calls(listing, functions));
    }

    private MainEvidence recoverGlibcMain(Listing listing, FunctionManager functions)
            throws Exception {
        for (Address entry : currentProgram.getSymbolTable().getExternalEntryPointIterator()) {
            monitor.checkCancelled();
            Function startup = functions.getFunctionAt(entry);
            if (startup == null || startup.isExternal()) {
                continue;
            }
            for (Instruction call : listing.getInstructions(startup.getBody(), true)) {
                if (!callsGlibcStartup(call, functions)) {
                    continue;
                }
                // The first System V AMD64 argument is in RDI.
                Instruction setup = listing.getInstructionBefore(call.getAddress());
                if (setup == null || !startup.getBody().contains(setup.getAddress())
                        || !call.getAddress().equals(setup.getFallThrough())
                        || setup.getRegister(0) == null
                        || !setup.getRegister(0).getName().equals("RDI")) {
                    continue;
                }
                Object[] source = setup.getOpObjects(1);
                boolean immediate = setup.getMnemonicString().equals("MOV")
                        && source.length == 1 && source[0] instanceof Scalar;
                if (!immediate && !setup.getMnemonicString().equals("LEA")) {
                    continue;
                }
                for (Reference reference : setup.getOperandReferences(1)) {
                    Address main = reference.getToAddress();
                    if (!reference.getReferenceType().isData()
                            || !currentProgram.getMemory().getExecuteSet().contains(main)) {
                        continue;
                    }
                    Function target = functions.getFunctionContaining(main);
                    if (target == null
                            && (listing.getInstructionAt(main) != null || disassemble(main))) {
                        target = createFunction(main, null);
                    }
                    if (target != null && target.getEntryPoint().equals(main)) {
                        return new MainEvidence(location(main), location(entry),
                                location(setup.getAddress()), location(call.getAddress()));
                    }
                }
            }
        }
        return null;
    }

    private static boolean callsGlibcStartup(Instruction instruction, FunctionManager functions) {
        if (!instruction.getFlowType().isCall()) {
            return false;
        }
        Address[] targets = instruction.getFlows();
        if (targets != null) {
            for (Address target : targets) {
                Function function = functions.getFunctionAt(target);
                if (function != null && function.isThunk()) {
                    function = function.getThunkedFunction(true);
                }
                if (function != null && function.isExternal()
                        && function.getName().equals("__libc_start_main")) {
                    return true;
                }
            }
        }
        return false;
    }

    private LiftedFunction liftFunction(Function function, Listing listing, BasicBlockModel model,
            DecompInterface decompiler, OrdinarySwitchEvidence switches, OrdinaryByteEvidence bytes) throws Exception {
        AddressSetView body = function.getBody();
        List<DecodedInstruction> instructions = new ArrayList<>();
        boolean switchCandidate = false;
        for (Instruction instruction : listing.getInstructions(body, true)) {
            monitor.checkCancelled();
            List<Operation> pcode = Arrays.stream(instruction.getPcode())
                    .map(ExportLift::operation).toList();
            instructions.add(new DecodedInstruction(location(instruction.getAddress()),
                    instruction.getLength(), instruction.toString(), pcode));
            if (switches != null && instruction.getFlowType().isJump()
                    && instruction.getFlowType().isComputed()
                    && pcode.stream().anyMatch(op -> op.opcode().equals("BRANCHIND"))) {
                switchCandidate = true;
            }
        }

        List<Block> blocks = new ArrayList<>();
        List<FlowEdge> edges = new ArrayList<>();
        CodeBlockIterator blockIterator = model.getCodeBlocksContaining(body, monitor);
        while (blockIterator.hasNext()) {
            CodeBlock block = blockIterator.next();
            Location entry = location(block.getFirstStartAddress());
            blocks.add(new Block(entry, ranges(block.intersect(body))));
            CodeBlockReferenceIterator destinations = block.getDestinations(monitor);
            while (destinations.hasNext()) {
                CodeBlockReference edge = destinations.next();
                if (!edge.getFlowType().isCall() && body.contains(edge.getReferent())) {
                    edges.add(new FlowEdge(entry, location(edge.getDestinationAddress()),
                            location(edge.getReferent()), location(edge.getReference()),
                            edge.getFlowType().toString()));
                }
            }
        }

        List<Parameter> parameters = Arrays.stream(function.getParameters())
                .map(parameter -> new Parameter(parameter.getName(),
                        parameter.getDataType().getPathName())).toList();
        Signature signature = new Signature(function.getCallingConventionName(),
                function.getReturnType().getPathName(), parameters, function.hasVarArgs());
        Function thunk = function.getThunkedFunction(true);
        Decompiled decoded = decompile(function, decompiler,
                switchCandidate && !function.isThunk() ? switches : null, bytes);
        return new LiftedFunction(location(function.getEntryPoint()), function.getName(), signature,
                thunk == null ? null : location(thunk.getEntryPoint()), ranges(body),
                decoded.code(), instructions, blocks, edges, staticEvidence(function, decoded.high()));
    }

    private Decompiled decompile(Function function, DecompInterface decompiler,
            OrdinarySwitchEvidence switches, OrdinaryByteEvidence bytes) throws Exception {
        DecompileResults result = decompiler.decompileFunction(function, 60, monitor);
        var code = result.getDecompiledFunction();
        var high = result.getHighFunction();
        List<Operation> analyzed = new ArrayList<>();
        if (high != null) {
            high.getPcodeOps().forEachRemaining(op -> analyzed.add(operation(op)));
        }
        List<Statement> statements = new ArrayList<>();
        if (result.getCCodeMarkup() != null) {
            collectStatements(result.getCCodeMarkup(), statements);
        }
        String status = result.isTimedOut() ? "timeout"
                : code != null && high != null ? "ok" : "incomplete";
        if (switches != null) {
            switches.capture(function, result);
        }
        if (bytes != null) {
            bytes.capture(function, result, decompiler);
        }
        return new Decompiled(new Decompilation(code == null ? null : code.getC(), status,
                result.getErrorMessage(), analyzed, statements), high);
    }

    private static int bounded(int value, int min, int max, String field) {
        if (value < min || value > max) {
            throw new IllegalArgumentException("Static evidence exceeds the limit for " + field);
        }
        return value;
    }

    private static String boundedText(String value) {
        if (value != null) {
            bounded(value.length(), 0, 1024, "text");
        }
        return value;
    }

    private final class EvidenceBuilder {
        private final Map<DataType, String> typeIds = new IdentityHashMap<>();
        private final List<TypeEvidence> types = new ArrayList<>();
        private final Map<String, RegisterEvidence> registers = new LinkedHashMap<>();

        private String typeId(DataType data, int depth) {
            if (data == null) {
                return null;
            }
            String known = typeIds.get(data);
            if (known != null) {
                return known;
            }
            bounded(depth, 0, 31, "type depth");
            bounded(types.size(), 0, 255, "types");
            int index = types.size();
            String id = "t" + index;
            typeIds.put(data, id);
            types.add(null);
            String kind = "opaque";
            DataType target = null;
            Integer count = null;
            if (data instanceof Pointer pointer) {
                kind = "pointer";
                target = pointer.getDataType();
            } else if (data instanceof TypeDef alias) {
                kind = "typedef";
                target = alias.getDataType();
            } else if (data instanceof Array array) {
                kind = "array";
                target = array.getDataType();
                count = bounded(array.getNumElements(), 0, Integer.MAX_VALUE, "array count");
            } else if (data instanceof Structure) {
                kind = "structure";
            } else if (data instanceof Union) {
                kind = "union";
            } else if (data instanceof FunctionDefinition) {
                kind = "function";
            }
            types.set(index, new TypeEvidence(id, boundedText(data.getPathName()),
                    boundedText(data.getName()), kind,
                    bounded(data.getLength(), -1, Integer.MAX_VALUE, "type size"),
                    typeId(target, depth + 1), count));
            return id;
        }

        private String register(Register register) {
            if (register == null) {
                return null;
            }
            String name = boundedText(register.getName());
            if (!registers.containsKey(name)) {
                bounded(registers.size(), 0, 511, "registers");
                Register base = register.getBaseRegister();
                registers.put(name, new RegisterEvidence(name, location(register.getAddress()),
                        bounded(register.getBitLength(), 1, 65536, "register width"),
                        boundedText(base.getName()), register.getLeastSignificantBitInBaseRegister()));
                if (!base.equals(register)) {
                    register(base);
                }
            }
            return name;
        }

        private StorageEvidence storage(VariableStorage storage) {
            if (storage == null) {
                return new StorageEvidence("unknown", 0, false, null, List.of());
            }
            String state = storage.isBadStorage() ? "bad"
                    : storage.isUnassignedStorage() ? "unassigned"
                    : storage.isVoidStorage() ? "void" : "assigned";
            List<StoragePiece> pieces = new ArrayList<>();
            bounded(storage.getVarnodeCount(), 0, 32, "storage pieces");
            for (Varnode node : storage.getVarnodes()) {
                int size = bounded(node.getSize(), 1, 8192, "storage width");
                Register reg = currentProgram.getRegister(node.getAddress(), size);
                pieces.add(new StoragePiece(location(node.getAddress()), size, register(reg),
                        node.getAddress().isStackAddress() ? node.getAddress().getOffset() : null));
            }
            return new StorageEvidence(state, bounded(storage.size(), 0, 8192, "storage size"),
                    storage.isForcedIndirect(), storage.getAutoParameterType() == null ? null
                            : boundedText(storage.getAutoParameterType().name()), pieces);
        }

        private Slot slot(String name, DataType data, VariableStorage storage) {
            return new Slot(boundedText(name), typeId(data, 0), storage(storage));
        }

        private void validateTypes() {
            for (TypeEvidence first : types) {
                List<TypeEvidence> path = new ArrayList<>();
                TypeEvidence current = first;
                while (!path.contains(current)) {
                    path.add(current);
                    bounded(path.size(), 1, 32, "type reference depth");
                    if (current.target() == null) {
                        break;
                    }
                    current = types.get(Integer.parseInt(current.target().substring(1)));
                }
                if (current.target() != null) {
                    boolean pointer = path.subList(path.indexOf(current), path.size()).stream()
                            .anyMatch(item -> item.kind().equals("pointer"));
                    if (!pointer) {
                        throw new IllegalArgumentException("A recursive type needs a pointer.");
                    }
                }
            }
        }
    }

    private StaticEvidence staticEvidence(Function function, HighFunction high) {
        EvidenceBuilder builder = new EvidenceBuilder();
        List<Slot> parameters = new ArrayList<>();
        bounded(function.getParameterCount(), 0, 128, "listing parameters");
        for (var parameter : function.getParameters()) {
            parameters.add(builder.slot(parameter.getName(), parameter.getDataType(),
                    parameter.getVariableStorage()));
        }
        PrototypeEvidence listing = new PrototypeEvidence("listing",
                boundedText(function.getCallingConventionName()), function.hasCustomVariableStorage(),
                function.hasVarArgs(), function.hasNoReturn(), parameters,
                builder.slot(null, function.getReturnType(), function.getReturn().getVariableStorage()));
        PrototypeEvidence decompiler = null;
        List<JumpEvidence> jumps = new ArrayList<>();
        if (high != null) {
            FunctionPrototype prototype = high.getFunctionPrototype();
            List<Slot> highParameters = new ArrayList<>();
            bounded(prototype.getNumParams(), 0, 128, "decompiler parameters");
            for (int index = 0; index < prototype.getNumParams(); index++) {
                HighSymbol parameter = prototype.getParam(index);
                highParameters.add(builder.slot(parameter.getName(), parameter.getDataType(),
                        parameter.getStorage()));
            }
            decompiler = new PrototypeEvidence("decompiler", boundedText(prototype.getModelName()),
                    null, prototype.isVarArg(), prototype.hasNoReturn(), highParameters,
                    builder.slot(null, prototype.getReturnType(), prototype.getReturnStorage()));
            JumpTable[] tables = high.getJumpTables();
            bounded(tables.length, 0, 256, "jump tables");
            int jumpItems = 0;
            for (JumpTable table : tables) {
                Address[] cases = table.getCases();
                Integer[] labels = table.getLabelValues();
                bounded(cases == null ? 0 : cases.length, 0, 4096, "jump targets");
                bounded(labels == null ? 0 : labels.length, 0, 4096, "jump labels");
                jumpItems += (cases == null ? 0 : cases.length)
                        + (labels == null ? 0 : labels.length);
                bounded(jumpItems, 0, 16384, "total jump items");
                // Ghidra can omit labels. Keep both API arrays without inventing pairs.
                jumps.add(new JumpEvidence(location(table.getSwitchAddress()),
                        cases == null ? List.of()
                                : Arrays.stream(cases).map(ExportLift::location).toList(),
                        labels == null ? List.of() : Arrays.asList(labels)));
            }
        }
        builder.validateTypes();
        return new StaticEvidence(1, "proposal", listing, decompiler, builder.types,
                new ArrayList<>(builder.registers.values()), jumps);
    }

    private static void collectStatements(ClangNode node, List<Statement> statements) {
        if (node instanceof ClangStatement statement) {
            statements.add(new Statement(statement.toString(), location(statement.getMinAddress()),
                    location(statement.getMaxAddress()), sequence(statement.getPcodeOp())));
        }
        for (int index = 0; index < node.numChildren(); index++) {
            collectStatements(node.Child(index), statements);
        }
    }

    private List<Import> imports() {
        ExternalManager manager = currentProgram.getExternalManager();
        List<Import> imports = new ArrayList<>();
        for (String library : manager.getExternalLibraryNames()) {
            ExternalLocationIterator locations = manager.getExternalLocations(library);
            while (locations.hasNext()) {
                ExternalLocation imported = locations.next();
                imports.add(new Import(location(imported.getExternalSpaceAddress()), library,
                        imported.getLabel(), location(imported.getAddress())));
            }
        }
        return imports;
    }

    private List<DefinedString> strings(Listing listing) throws Exception {
        List<DefinedString> strings = new ArrayList<>();
        for (Data data : listing.getDefinedData(true)) {
            monitor.checkCancelled();
            if (StringDataInstance.isString(data)) {
                String value = StringDataInstance.getStringDataInstance(data).getStringValue();
                if (value != null) {
                    strings.add(new DefinedString(location(data.getAddress()), value,
                            data.getDataType().getPathName(), data.getLength()));
                }
            }
        }
        return strings;
    }

    private List<DataReference> dataReferences() throws Exception {
        ReferenceManager references = currentProgram.getReferenceManager();
        List<DataReference> data = new ArrayList<>();
        for (Address from : references.getReferenceSourceIterator(currentProgram.getMemory(), true)) {
            monitor.checkCancelled();
            for (Reference reference : references.getReferencesFrom(from)) {
                if (reference.getReferenceType().isData()) {
                    data.add(new DataReference(location(from), location(reference.getToAddress()),
                            reference.getReferenceType().toString(), reference.getOperandIndex()));
                }
            }
        }
        return data;
    }

    private List<CallEdge> calls(Listing listing, FunctionManager functions) throws Exception {
        List<CallEdge> calls = new ArrayList<>();
        for (Instruction instruction : listing.getInstructions(true)) {
            monitor.checkCancelled();
            FlowType type = instruction.getFlowType();
            if (!type.isCall()) {
                continue;
            }
            Address address = instruction.getAddress();
            Location site = location(address);
            Function function = functions.getFunctionContaining(address);
            Location caller = function == null ? null : location(function.getEntryPoint());
            Address[] flows = instruction.getFlows();
            if ((flows == null || flows.length == 0) && !type.isComputed()) {
                flows = instruction.getDefaultFlows();
            }
            if (flows == null || flows.length == 0) {
                calls.add(new CallEdge(caller, site, null, type.toString(), type.isComputed()));
            } else {
                Arrays.sort(flows);
                for (Address target : flows) {
                    calls.add(new CallEdge(caller, site, location(target), type.toString(),
                            type.isComputed()));
                }
            }
        }
        return calls;
    }

    private static List<Range> ranges(AddressSetView addresses) {
        List<Range> result = new ArrayList<>();
        for (AddressRange range : addresses.getAddressRanges()) {
            result.add(new Range(location(range.getMinAddress()), location(range.getMaxAddress())));
        }
        return result;
    }

    private static Operation operation(PcodeOp op) {
        return new Operation(sequence(op), op.getMnemonic(), operand(op.getOutput()),
                Arrays.stream(op.getInputs()).map(ExportLift::operand).toList());
    }

    private static Sequence sequence(PcodeOp op) {
        return op == null ? null
                : new Sequence(location(op.getSeqnum().getTarget()), op.getSeqnum().getTime());
    }

    private static Operand operand(Varnode node) {
        return node == null ? null
                : new Operand(location(node.getAddress()), node.getSize(), sequence(node.getDef()));
    }

    private static Location location(Address address) {
        return address == null || address.equals(Address.NO_ADDRESS) ? null
                : new Location(address.getAddressSpace().getName(),
                        "0x" + Long.toUnsignedString(address.getOffset(), 16));
    }
}
