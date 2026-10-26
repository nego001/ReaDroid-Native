/*
 * PE-A2.1 fixture. Intentionally harmless, compiled only for static analysis.
 * CI must never execute this Windows binary or fetch a proprietary installer.
 */
__declspec(dllexport) int add_numbers(int first, int second) {
    return first + second;
}
__declspec(dllexport) int compare_numbers(int first, int second) {
    if (first > second) return 1;
    if (first < second) return -1;
    return 0;
}
int main(void) {
    volatile int result = add_numbers(2, 3);
    return compare_numbers(result, 5);
}
