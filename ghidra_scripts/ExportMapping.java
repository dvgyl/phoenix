// Export source-backed spans for the optional Phoenix evidence companion.
// @category Phoenix

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;

import com.google.gson.FieldNamingPolicy;
import com.google.gson.GsonBuilder;
import ghidra.app.script.GhidraScript;
import ghidra.program.database.mem.FileBytes;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.mem.MemoryBlockSourceInfo;

public class ExportMapping extends GhidraScript {
    private static final int MAX_BYTES = 64 * 1024 * 1024;
    private record Span(String ghidraStart, long length, long sourceFileOffset,
            long sourceSize, String sourceSha256, long sourceStart, long sourceEnd,
            String memorySha256, String originalSha256) {}
    private record Mapping(int schemaVersion, String binarySha256, String liftSha256,
            String imageBase, String startup, List<Span> spans) {}

    private static String hash(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private static String address(ghidra.program.model.address.Address address) {
        return "0x" + Long.toUnsignedString(address.getOffset(), 16);
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) {
            throw new IllegalArgumentException("Supply the mapping path and completed lift path.");
        }
        Path output = Path.of(args[0]);
        Path lift = Path.of(args[1]);
        if (Files.size(lift) > MAX_BYTES) {
            throw new IllegalStateException("The lift exceeds 64 MiB.");
        }
        // Read startup from the completed export. The mapping cannot change lift bytes.
        var liftJson = com.google.gson.JsonParser.parseString(Files.readString(lift)).getAsJsonObject();
        var main = liftJson.getAsJsonObject("main");
        if (main == null || !main.getAsJsonObject("startup").get("space").getAsString().equals("ram")) {
            throw new IllegalStateException("The lift has no RAM startup evidence.");
        }
        List<Span> spans = new ArrayList<>();
        Map<FileBytes, String> sourceHashes = new IdentityHashMap<>();
        long total = 0;
        for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
            if (!block.isInitialized() || !block.getStart().getAddressSpace().getName().equals("ram")) {
                continue;
            }
            for (MemoryBlockSourceInfo info : block.getSourceInfos()) {
                monitor.checkCancelled();
                if (info.getFileBytes().isEmpty()) {
                    continue;
                }
                FileBytes source = info.getFileBytes().get();
                long length = info.getLength();
                if (length <= 0 || length > MAX_BYTES || source.getSize() <= 0
                        || source.getSize() > MAX_BYTES || source.getFileOffset() != 0
                        || spans.size() >= 65536 || (total += length) > MAX_BYTES) {
                    throw new IllegalStateException("The source spans exceed the supported bounds.");
                }
                String sourceHash = sourceHashes.get(source);
                if (sourceHash == null) {
                    if (sourceHashes.size() >= 1) {
                        throw new IllegalStateException("Multiple source files are unsupported.");
                    }
                    byte[] original = new byte[(int) source.getSize()];
                    if (source.getOriginalBytes(0, original) != original.length) {
                        throw new IllegalStateException("The original source is incomplete.");
                    }
                    sourceHash = hash(original);
                    sourceHashes.put(source, sourceHash);
                }
                long first = info.getFileBytesOffset(info.getMinAddress());
                long last = info.getFileBytesOffset(info.getMaxAddress());
                if (first < 0 || first > source.getSize() - length || last != first + length - 1
                        || info.getMinAddress().add(length - 1).compareTo(info.getMaxAddress()) != 0
                        || info.getByteMappingScheme().isPresent()) {
                    throw new IllegalStateException("A source span is not a linear file mapping.");
                }
                byte[] original = new byte[(int) length];
                byte[] memory = new byte[(int) length];
                if (source.getOriginalBytes(first, original) != original.length
                        || currentProgram.getMemory().getBytes(info.getMinAddress(), memory) != memory.length) {
                    throw new IllegalStateException("A source span is incomplete.");
                }
                spans.add(new Span(address(info.getMinAddress()), length, source.getFileOffset(),
                        source.getSize(), sourceHash, first, last, hash(memory), hash(original)));
            }
        }
        Mapping mapping = new Mapping(1, currentProgram.getExecutableSHA256().toLowerCase(),
                hash(Files.readAllBytes(lift)), address(currentProgram.getImageBase()),
                main.getAsJsonObject("startup").get("offset").getAsString(), spans);
        Path partial = Files.createTempFile(output.getParent(), ".mapping-", ".json");
        try {
            Files.writeString(partial, new GsonBuilder()
                    .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
                    .create().toJson(mapping));
            monitor.checkCancelled();
            Files.move(partial, output, StandardCopyOption.ATOMIC_MOVE);
        } finally {
            Files.deleteIfExists(partial);
        }
    }
}
