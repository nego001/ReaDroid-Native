// @category NegrescoDroid
// PE-A3.1: limited call-connectivity ranking, NOT function intent inference.
// All pseudocode and names are heuristics from static analysis. Never runs PE.
import ghidra.app.util.headless.HeadlessScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.decompiler.DecompiledFunction;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.symbol.Reference;
import java.io.BufferedWriter;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

public class NegrescoDeepPreview extends HeadlessScript {
    private static final int MAX_SCANNED = 384;
    private static final int MAX_DECOMPILED = 12;
    private static final int MAX_CALLEES = 24;
    private static final int MAX_API_REFERENCES = 8;
    private static final int MAX_STRING_REFERENCES = 8;
    private static final int MAX_STRING_TEXT_CHARS = 96;
    private static final int MAX_STRING_SCAN_INSTRUCTIONS = 2048;
    private static final int MAX_REFS_PER_INSTRUCTION = 16;
    private static final int MAX_RANKING_EDGES = 64;
    private static final int MAX_PSEUDOCODE_CHARS = 1800;
    private static final int MAX_NAME_CHARS = 160;
    private static final int DECOMPILE_SECONDS = 10;
    private static final String SELECTION_METHOD =
        "bounded_api_references_and_call_connectivity_v2";
    private static final Set<String> WIN_APIS = new HashSet<>(Arrays.asList(
        "getfileattributesa", "getfileattributesw", "findfirstfilea",
        "findfirstfilew", "findnextfilea", "findnextfilew",
        "getfileinformationbyhandle", "deletefilea", "deletefilew",
        "removedirectorya", "removedirectoryw", "movefileexa",
        "movefileexw", "setfileattributesa", "setfileattributesw",
        "copyfilea", "copyfilew", "createdirectorya", "createdirectoryw",
        "regopenkeyexa", "regopenkeyexw", "regqueryvalueexa",
        "regqueryvalueexw", "regenumkeyexa", "regenumkeyexw",
        "reggetvaluea", "reggetvaluew", "regsetvalueexa",
        "regsetvalueexw", "regdeletekeya", "regdeletekeyw",
        "regdeletevaluea", "regdeletevaluew", "regcreatekeyexa",
        "regcreatekeyexw", "openscmanagera", "openscmanagerw",
        "openservicea", "openservicew", "deleteservice",
        "controlservice", "createservicea", "createservicew",
        "startservicea", "startservicew", "createprocessa",
        "createprocessw", "terminateprocess", "openprocess",
        "enumprocesses", "winhttpconnect", "winhttpsendrequest",
        "winhttpreceiveresponse", "internetconnecta", "internetconnectw",
        "httpsendrequesta", "httpsendrequestw", "msiconfigureproducta",
        "msiconfigureproductw", "msiconfigureproductexa",
        "msiconfigureproductexw", "msiinstallproducta",
        "msiinstallproductw"
    ));

    private static final class StringEvidence {
        final String value;
        final String dataAddress;
        final String sourceAddress;
        StringEvidence(String value, String dataAddress, String sourceAddress) {
            this.value = value;
            this.dataAddress = dataAddress;
            this.sourceAddress = sourceAddress;
        }
    }

    private static final class StringResults {
        final List<StringEvidence> entries = new ArrayList<>();
        boolean truncated = false;
        boolean scanTruncated = false;
        int instructionsScanned = 0;
    }

    // Never scrape arbitrary printable bytes: only Ghidra-defined string
    // data reached by an instruction reference from THIS function's body.
    private StringResults findReferencedStrings(Function fn) throws Exception {
        StringResults result = new StringResults();
        LinkedHashMap<String, StringEvidence> seen = new LinkedHashMap<>();
        InstructionIterator iterator =
            currentProgram.getListing().getInstructions(fn.getBody(), true);
        while (iterator.hasNext() &&
               result.instructionsScanned < MAX_STRING_SCAN_INSTRUCTIONS) {
            monitor.checkCancelled();
            Instruction instruction = iterator.next();
            result.instructionsScanned++;
            Reference[] references = instruction.getReferencesFrom();
            if (references.length > MAX_REFS_PER_INSTRUCTION)
                result.scanTruncated = true;
            for (int i = 0; i < Math.min(MAX_REFS_PER_INSTRUCTION, references.length); i++) {
                Reference ref = references[i];
                if (ref.getToAddress() == null ||
                    !ref.getToAddress().isMemoryAddress()) continue;
                Data defined = currentProgram.getListing().getDefinedDataContaining(
                    ref.getToAddress());
                if (defined == null || !defined.hasStringValue()) continue;
                Object raw = defined.getValue();
                if (!(raw instanceof String)) continue;
                String value = (String) raw;
                if (value.length() < 6 || value.length() > MAX_STRING_TEXT_CHARS)
                    continue;
                boolean printable = true;
                for (int ch = 0; ch < value.length(); ch++) {
                    if (value.charAt(ch) < 32 || value.charAt(ch) > 126) {
                        printable = false;
                        break;
                    }
                }
                if (!printable) continue;
                String dataAddress = defined.getAddress().toString();
                String sourceAddress = ref.getFromAddress().toString();
                if (!dataAddress.matches("[0-9a-fA-F]{1,16}") ||
                    !sourceAddress.matches("[0-9a-fA-F]{1,16}")) continue;
                if (!seen.containsKey(dataAddress))
                    seen.put(dataAddress, new StringEvidence(
                        value, dataAddress, sourceAddress));
                if (seen.size() > MAX_STRING_REFERENCES) {
                    result.truncated = true;
                    break;
                }
            }
            if (result.truncated) break;
        }
        if (iterator.hasNext()) result.scanTruncated = true;
        int exported = 0;
        for (StringEvidence entry : seen.values()) {
            if (exported++ >= MAX_STRING_REFERENCES) break;
            result.entries.add(entry);
        }
        return result;
    }

    private static final class Candidate {
        final Function function;
        final List<Function> callees;
        final int directCalleeCount;
        final boolean callsAvailable;
        final List<String> apiReferences;
        final int apiReferenceCount;
        int inboundSample;
        int rankScore;

        Candidate(Function function, List<Function> callees, int directCount,
                  boolean available, List<String> apiReferences, int apiRefCount) {
            this.function = function;
            this.callees = callees;
            this.directCalleeCount = directCount;
            this.callsAvailable = available;
            this.apiReferences = apiReferences;
            this.apiReferenceCount = apiRefCount;
        }
    }

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

    private static int symbolHint(String name) {
        if (name == null) return 0;
        String value = name.toLowerCase(Locale.ROOT);
        if (value.equals("main") || value.equals("winmain") || value.equals("wmain")
                || value.equals("maincrtstartup") || value.equals("winmaincrtstartup"))
            return 20;
        if (value.startsWith("fun_") || value.startsWith("sub_")
                || value.startsWith("thunk_")) return 0;
        return 5;  // A meaningful-looking name is only a HINT, not proof.
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (currentProgram == null || args == null || args.length != 1)
            throw new IllegalArgumentException("Expected one private JSON output path");
        if (analysisTimeoutOccurred())
            throw new IllegalStateException("Incomplete automatic analysis is not evidence");

        // One bounded scan. Keep at most 64 sorted callees per function for
        // prioritization, never ask the decompiler to process all of them.
        FunctionIterator iter = currentProgram.getFunctionManager().getFunctions(true);
        List<Candidate> candidates = new ArrayList<>();
        int scanned = 0;
        while (iter.hasNext() && scanned < MAX_SCANNED) {
            monitor.checkCancelled();
            Function fn = iter.next();
            scanned++;
            if (fn.isThunk()) continue;
            List<Function> called = new ArrayList<>();
            boolean available = true;
            int directCount = 0;
            TreeSet<String> referencedApis = new TreeSet<>();
            try {
                Set<Function> refs = fn.getCalledFunctions(monitor);
                if (refs != null) {
                    // Ghidra can return EXTERNAL/REGISTER references. These
                    // are not file-backed function entry points. This graph
                    // covers only directly referenced, normal memory addresses;
                    // imported calls are handled separately by PE-A1.
                    for (Function ref : refs) {
                        if (ref == null || ref.getEntryPoint() == null) continue;
                        // Keep external WinAPI evidence separate from the
                        // internal call graph. Resolve Ghidra import thunks
                        // only if their destination is confirmed external.
                        Function linked = ref;
                        if (ref.isThunk()) {
                            Function resolved = ref.getThunkedFunction(true);
                            if (resolved != null) linked = resolved;
                        }
                        if (linked.isExternal()) {
                            String name = linked.getName();
                            if (name.startsWith("__imp_"))
                                name = name.substring(6);
                            if (WIN_APIS.contains(name.toLowerCase(Locale.ROOT)))
                                referencedApis.add(name);
                        }
                        String entry = ref.getEntryPoint().toString();
                        if (entry.matches("[0-9a-fA-F]{1,16}")) called.add(ref);
                    }
                    directCount = called.size();
                    Collections.sort(called, Comparator.comparing(
                        x -> x.getEntryPoint().toString()));
                    if (called.size() > MAX_RANKING_EDGES)
                        called = new ArrayList<>(called.subList(0, MAX_RANKING_EDGES));
                }
            } catch (Exception error) {
                if (monitor.isCancelled()) throw error;
                available = false; // Missing xrefs never become invented calls.
                called.clear();
                directCount = 0;
                referencedApis.clear();
            }
            List<String> apiSample = new ArrayList<>(referencedApis);
            int apiCount = apiSample.size();
            if (apiSample.size() > MAX_API_REFERENCES)
                apiSample = new ArrayList<>(apiSample.subList(0, MAX_API_REFERENCES));
            candidates.add(new Candidate(
                fn, called, directCount, available, apiSample, apiCount));
        }
        boolean scanTruncated = iter.hasNext();

        // In-degree counts only edges observed inside the scanned sample.
        // No claim of a complete call graph for the whole program.
        Map<String, Candidate> byEntry = new HashMap<>();
        for (Candidate candidate : candidates) {
            byEntry.put(candidate.function.getEntryPoint().toString(), candidate);
        }
        for (Candidate from : candidates) {
            for (Function called : from.callees) {
                Candidate to = byEntry.get(called.getEntryPoint().toString());
                if (to != null) to.inboundSample++;
            }
        }

        for (Candidate candidate : candidates) {
            candidate.rankScore = Math.min(16, candidate.inboundSample) * 4
                + Math.min(16, candidate.directCalleeCount) * 2
                + symbolHint(candidate.function.getName())
                + (candidate.apiReferenceCount > 0 ? 128 : 0);
        }
        Collections.sort(candidates, Comparator
            .comparingInt((Candidate x) -> x.rankScore).reversed()
            .thenComparing(x -> x.function.getEntryPoint().toString()));
        List<Candidate> sample = candidates.subList(0,
            Math.min(MAX_DECOMPILED, candidates.size()));

        DecompInterface decompiler = new DecompInterface();
        decompiler.toggleCCode(true);
        try {
            boolean ready = decompiler.openProgram(currentProgram);
            try (BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(
                    new FileOutputStream(args[0]), StandardCharsets.UTF_8))) {
                writer.write("{\"schema\":\"ghidra_deep_preview_v3\",");
                writer.write("\"selection_method\":");
                writer.write(json(SELECTION_METHOD, 80));
                writer.write(",\"functions\":[");
                int emitted = 0;
                for (Candidate candidate : sample) {
                    monitor.checkCancelled();
                    Function fn = candidate.function;
                    if (emitted != 0) writer.write(",");
                    emitted++;
                    writer.write("{\"entry_point\":");
                    writer.write(json(fn.getEntryPoint().toString(), 32));
                    writer.write(",\"name\":");
                    writer.write(json(fn.getName(), MAX_NAME_CHARS));
                    writer.write(",\"selection_rank\":");
                    writer.write(Integer.toString(emitted));
                    writer.write(",\"selection_score\":");
                    writer.write(Integer.toString(candidate.rankScore));
                    writer.write(",\"sample_inbound_count\":");
                    writer.write(Integer.toString(candidate.inboundSample));
                    writer.write(",\"direct_callee_count\":");
                    writer.write(Integer.toString(candidate.directCalleeCount));
                    writer.write(",\"api_call_reference_count\":");
                    writer.write(Integer.toString(candidate.apiReferenceCount));
                    writer.write(",\"api_call_references\":[");
                    for (int i = 0; i < candidate.apiReferences.size(); i++) {
                        if (i > 0) writer.write(",");
                        writer.write(json(candidate.apiReferences.get(i), 80));
                    }
                    writer.write("],\"api_call_references_truncated\":");
                    writer.write(Boolean.toString(
                        candidate.apiReferenceCount > MAX_API_REFERENCES));
                    writer.write(",\"calls_status\":");
                    writer.write(json(candidate.callsAvailable ? "ok" : "unavailable", 16));
                    writer.write(",\"calls\":[");
                    for (int j = 0; j < Math.min(MAX_CALLEES, candidate.callees.size()); j++) {
                        if (j > 0) writer.write(",");
                        writer.write(json(candidate.callees.get(j).getEntryPoint().toString(), 32));
                    }
                    writer.write("],\"calls_truncated\":");
                    writer.write(Boolean.toString(candidate.directCalleeCount > MAX_CALLEES));
                    String status = "unavailable";
                    String c = "";
                    if (ready) {
                        try {
                            DecompileResults result = decompiler.decompileFunction(
                                fn, DECOMPILE_SECONDS, monitor);
                            if (result != null && result.decompileCompleted()) {
                                DecompiledFunction decoded = result.getDecompiledFunction();
                                if (decoded != null && decoded.getC() != null
                                        && !decoded.getC().isEmpty()) {
                                    c = decoded.getC();
                                    status = "ok";
                                }
                            } else if (result != null && result.isTimedOut()) {
                                status = "timed_out";
                            }
                        } catch (Exception failed) {
                            if (monitor.isCancelled()) throw failed;
                        }
                    }
                    writer.write(",\"decompile_status\":");
                    writer.write(json(status, 16));
                    writer.write(",\"pseudocode\":");
                    writer.write(json(c, MAX_PSEUDOCODE_CHARS));
                    writer.write(",\"pseudocode_truncated\":");
                    writer.write(Boolean.toString(c.length() > MAX_PSEUDOCODE_CHARS));
                    StringResults strings = findReferencedStrings(fn);
                    writer.write(",\"strings\":[");
                    for (int i = 0; i < strings.entries.size(); i++) {
                        if (i != 0) writer.write(",");
                        StringEvidence evidence = strings.entries.get(i);
                        writer.write("{\"text\":");
                        writer.write(json(evidence.value, MAX_STRING_TEXT_CHARS));
                        writer.write(",\"data_address\":");
                        writer.write(json(evidence.dataAddress, 32));
                        writer.write(",\"reference_from\":");
                        writer.write(json(evidence.sourceAddress, 32));
                        writer.write("}");
                    }
                    writer.write("],\"strings_truncated\":");
                    writer.write(Boolean.toString(strings.truncated));
                    writer.write(",\"string_scan_truncated\":");
                    writer.write(Boolean.toString(strings.scanTruncated));
                    writer.write(",\"instructions_scanned_for_strings\":");
                    writer.write(Integer.toString(strings.instructionsScanned));
                    writer.write("}");
                }
                writer.write("],\"candidates_scanned\":");
                writer.write(Integer.toString(scanned));
                writer.write(",\"eligible_non_thunks\":");
                writer.write(Integer.toString(candidates.size()));
                writer.write(",\"scan_truncated\":");
                writer.write(Boolean.toString(scanTruncated));
                writer.write(",\"sample_truncated\":");
                writer.write(Boolean.toString(candidates.size() > sample.size()));
                writer.write(",\"graph_scope\":\"scanned_functions_only\"");
                writer.write(",\"provenance\":\"ghidra_heuristic_not_original_source\"}");
            }
        } finally {
            decompiler.dispose();
        }
    }
}
