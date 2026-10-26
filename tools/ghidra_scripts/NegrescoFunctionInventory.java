// @category NegrescoDroid
// PE-A2: bounded metadata export after Ghidra Headless auto-analysis.
// The imported program is not run. Generated function names are not guaranteed
// to be original names. A full decompiler or call graph comes in PE-A3.
import ghidra.app.util.headless.HeadlessScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;

public class NegrescoFunctionInventory extends HeadlessScript {
    private static final int MAX_FUNCTIONS = 256;
    private static final int MAX_NAME_CHARS = 160;

    private static String json(String text) {
        StringBuilder out = new StringBuilder("\"");
        if (text == null) text = "";
        for (int i = 0; i < text.length() && i < MAX_NAME_CHARS; i++) {
            char ch = text.charAt(i);
            if (ch == '"' || ch == '\\') {
                out.append('\\').append(ch);
            } else if (ch < 32 || ch > 126) {
                String hex = Integer.toHexString(ch);
                out.append("\\u");
                for (int zeroes = hex.length(); zeroes < 4; zeroes++)
                    out.append('0');
                out.append(hex);
            } else {
                out.append(ch);
            }
        }
        return out.append('"').toString();
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args == null || args.length != 1 || currentProgram == null)
            throw new IllegalArgumentException("Expected one output path and a loaded program");
        if (analysisTimeoutOccurred())
            throw new IllegalStateException("Ghidra automatic analysis timed out; reject partial function report");

        File target = new File(args[0]);
        // The Python runner creates a unique private directory and owns the
        // output path. No user supplied postScript filename is ever accepted.
        int discovered = currentProgram.getFunctionManager().getFunctionCount();
        FunctionIterator iterator = currentProgram.getFunctionManager().getFunctions(true);
        int emitted = 0;
        try (BufferedWriter writer = new BufferedWriter(
                new OutputStreamWriter(new FileOutputStream(target),
                                       StandardCharsets.UTF_8))) {
            writer.write("{\"schema\":\"ghidra_function_preview_v1\",");
            writer.write("\"total_discovered\":" + discovered + ",");
            writer.write("\"functions\":[");
            while (iterator.hasNext() && emitted < MAX_FUNCTIONS) {
                monitor.checkCancelled();
                Function function = iterator.next();
                if (emitted != 0) writer.write(",");
                writer.write("{\"entry_point\":");
                writer.write(json(function.getEntryPoint().toString()));
                writer.write(",\"name\":");
                writer.write(json(function.getName()));
                writer.write(",\"is_thunk\":");
                writer.write(Boolean.toString(function.isThunk()));
                writer.write("}");
                emitted++;
            }
            writer.write("],\"preview_truncated\":");
            writer.write(Boolean.toString(discovered > emitted));
            writer.write(",\"name_provenance\":\"original_or_generated_not_verified\"}");
        }
    }
}
