// @category NegrescoDroid
// PE-A3: BOUNDED local static evidence. Ghidra identifies potential functions,
// but never executes the Windows input. Generated C is an approximation;
// function names, control flow and intent are NOT guaranteed to match source.
import ghidra.app.util.headless.HeadlessScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.decompiler.DecompiledFunction;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import java.io.BufferedWriter;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Set;

public class NegrescoDeepPreview extends HeadlessScript {
    private static final int MAX_SCANNED = 256;
    private static final int MAX_DECOMPILED = 8;
    private static final int MAX_CALLEES = 12;
    private static final int MAX_PSEUDOCODE_CHARS = 1800;
    private static final int MAX_NAME_CHARS = 160;
    private static final int DECOMPILE_SECONDS = 12;

    private static String json(String input, int limit) {
        if (input == null) input = "";
        StringBuilder out = new StringBuilder("\"");
        for (int i = 0; i < input.length() && i < limit; i++) {
            char ch = input.charAt(i);
            if (ch == '\\' || ch == '"') out.append('\\').append(ch);
            else if (ch == '\n') out.append("\\n");
            else if (ch == '\r') out.append("\\r");
            else if (ch == '\t') out.append("\\t");
            else if (ch < 32 || ch > 126) {
                out.append(String.format("\\u%04x", (int) ch));
            } else out.append(ch);
        }
        return out.append('"').toString();
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (currentProgram == null || args == null || args.length != 1)
            throw new IllegalArgumentException("Expected exactly one private JSON output path");
        if (analysisTimeoutOccurred())
            throw new IllegalStateException("Autoanalysis expired: refuse incomplete call graph");

        // Inspect at most 256 functions; do not traverse the whole binary for
        // expensive decompilation. Prefer non-thunks; imported library stubs
        // are usually not useful explanations of an application.
        FunctionIterator iter = currentProgram.getFunctionManager().getFunctions(true);
        List<Function> sample = new ArrayList<>();
        int scanned = 0, eligible = 0;
        while (iter.hasNext() && scanned < MAX_SCANNED) {
            monitor.checkCancelled();
            Function fn = iter.next();
            scanned++;
            if (fn.isThunk()) continue;
            eligible++;
            if (sample.size() < MAX_DECOMPILED) sample.add(fn);
        }

        DecompInterface decompiler = new DecompInterface();
        decompiler.toggleCCode(true);
        try {
            boolean ready = decompiler.openProgram(currentProgram);
            try (BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(
                    new FileOutputStream(args[0]), StandardCharsets.UTF_8))) {
                writer.write("{\"schema\":\"ghidra_deep_preview_v1\",");
                writer.write("\"functions\":[");
                int emitted = 0;
                for (Function fn : sample) {
                    monitor.checkCancelled();
                    if (emitted++ != 0) writer.write(",");
                    writer.write("{\"entry_point\":");
                    writer.write(json(fn.getEntryPoint().toString(), 32));
                    writer.write(",\"name\":");
                    writer.write(json(fn.getName(), MAX_NAME_CHARS));
                    writer.write(",\"calls\":[");
                    List<Function> called = new ArrayList<>();
                    try {
                        Set<Function> callSet = fn.getCalledFunctions(monitor);
                        if (callSet != null) called.addAll(callSet);
                        Collections.sort(called, Comparator.comparing(
                            x -> x.getEntryPoint().toString()));
                    } catch (Exception error) {
                        // No guessed edges when xrefs are unavailable.
                        called.clear();
                    }
                    for (int j = 0; j < Math.min(MAX_CALLEES, called.size()); j++) {
                        if (j > 0) writer.write(",");
                        writer.write(json(called.get(j).getEntryPoint().toString(), 32));
                    }
                    writer.write("],\"calls_truncated\":");
                    writer.write(Boolean.toString(called.size() > MAX_CALLEES));
                    String status = "unavailable";
                    String c = "";
                    if (ready) {
                        try {
                            DecompileResults result = decompiler.decompileFunction(
                                fn, DECOMPILE_SECONDS, monitor);
                            if (result != null && result.decompileCompleted()) {
                                DecompiledFunction decompiled = result.getDecompiledFunction();
                                if (decompiled != null && decompiled.getC() != null) {
                                    c = decompiled.getC();
                                    status = "ok";
                                }
                            } else if (result != null && result.isTimedOut()) {
                                status = "timed_out";
                            }
                        } catch (Exception failed) {
                            if (monitor.isCancelled()) throw failed;
                            status = "unavailable";
                        }
                    }
                    writer.write(",\"decompile_status\":");
                    writer.write(json(status, 16));
                    writer.write(",\"pseudocode\":");
                    writer.write(json(c, MAX_PSEUDOCODE_CHARS));
                    writer.write(",\"pseudocode_truncated\":");
                    writer.write(Boolean.toString(c.length() > MAX_PSEUDOCODE_CHARS));
                    writer.write("}");
                }
                writer.write("],\"candidates_scanned\":");
                writer.write(Integer.toString(scanned));
                writer.write(",\"eligible_non_thunks\":");
                writer.write(Integer.toString(eligible));
                writer.write(",\"sample_truncated\":");
                writer.write(Boolean.toString(eligible > sample.size() || iter.hasNext()));
                writer.write(",\"provenance\":\"ghidra_heuristic_not_original_source\"}");
            }
        } finally {
            decompiler.dispose();
        }
    }
}
