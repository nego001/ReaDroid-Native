/*
 * PE-A4 fixture: only compiled for Ghidra static analysis in CI.
 * The Windows program is NEVER executed. It makes no destructive changes.
 */
#include <windows.h>

__declspec(dllexport) int add_numbers(int first, int second) {
    return first + second;
}
__declspec(dllexport) int compare_numbers(int first, int second) {
    if (first > second) return 1;
    if (first < second) return -1;
    return 0;
}

/* An observable harmless WinAPI call, useful for verifying that our
 * classifier grounds a filesystem-inspection hypothesis in actual
 * Ghidra pseudocode rather than in a function name or global import.
 */
__declspec(dllexport) int inspect_path(const char *path) {
    DWORD flags = GetFileAttributesA("negresco_evidence_2026.txt");
    return flags != INVALID_FILE_ATTRIBUTES && path != 0;
}
__declspec(dllexport) int path_check_one(void) {
    return inspect_path("example-one.txt");
}
__declspec(dllexport) int path_check_two(void) {
    return inspect_path("example-two.txt");
}
int main(void) {
    volatile int result = add_numbers(2, 3);
    volatile int found = path_check_one() + path_check_two();
    return compare_numbers(result, 5) + found;
}
