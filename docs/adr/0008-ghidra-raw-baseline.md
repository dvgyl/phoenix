# Use a mechanical compatibility header for Ghidra-raw

Use the same Ghidra lift and reachable function set for the raw baseline
and Phoenix. Keep Ghidra's function bodies intact. Add standard C headers,
type aliases, recovered string data, and an entry wrapper in a generated
header. The wrapper uses the parameter types in the raw entry definition.

Declare the glibc formatted output entry points with generic format
pointers in the compatibility header. This accepts the raw address of
a string array on the two Linux targets. The raw baseline retains any
remaining type or behavior errors. The evaluator records its build,
behavior, and integrity results separately.
