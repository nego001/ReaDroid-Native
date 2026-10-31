// @category NegrescoDroid
// PE-S1.11: evidence from the ACTUAL Ghidra headless JVM, never from a
// separate Python sandbox process. Synthetic PE acceptance only.
// Linux /proc/self/status is kernel-provided, not a statement that this
// application is secure against kernel vulnerabilities.
import ghidra.app.util.headless.HeadlessScript;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.List;

public class NegrescoSeccompRuntimeProof extends HeadlessScript {
    private static final String SCHEMA = "negresco_ghidra_seccomp_runtime_v1";

    private static int statusField(List<String> lines, String key) {
        Integer found = null;
        for (String line : lines) {
            if (!line.startsWith(key + ":")) continue;
            if (found != null)
                throw new IllegalStateException("Duplicate kernel status field: " + key);
            String value = line.substring(key.length() + 1).trim();
            if (!value.matches("[0-9]{1,9}"))
                throw new IllegalStateException("Invalid kernel status field: " + key);
            found = Integer.valueOf(value);
        }
        if (found == null)
            throw new IllegalStateException("Missing kernel status field: " + key);
        return found.intValue();
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (currentProgram == null || args == null || args.length != 1)
            throw new IllegalArgumentException("Required private seccomp proof path");
        if (analysisTimeoutOccurred())
            throw new IllegalStateException("Analysis timeout: no runtime proof");

        List<String> lines = Files.readAllLines(
            Path.of("/proc/self/status"), StandardCharsets.US_ASCII);
        int mode = statusField(lines, "Seccomp");
        int filters = statusField(lines, "Seccomp_filters");
        if (mode != 2 || filters < 1)
            throw new IllegalStateException(
                "Ghidra headless JVM is not running with seccomp filters");
        // CREATE_NEW ensures stale preexisting output does not become proof.
        String json = "{\"schema\":\"" + SCHEMA +
            "\",\"seccomp_mode\":2,\"seccomp_filters\":" + filters +
            ",\"measurement_source\":\"/proc/self/status\"," +
            "\"measured_process\":\"ghidra_headless_jvm\"}";
        Files.writeString(Path.of(args[0]), json, StandardCharsets.UTF_8,
            StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
    }
}
