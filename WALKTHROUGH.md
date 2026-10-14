# How the MoonVeil v1.4.5 decompiler works

## 1. Parse before instrumentation

The first operation is an official Luau parse check. No wrapper code runs during this check. An unfinished source is reported as truncated or incomplete immediately, including the parser diagnostic. This prevents a partial loader from being mistaken for a new wrapper layout.

A complete input must include the final payload path and the VM construction logic needed to recover its program. Missing encrypted bytes or dispatcher code cannot be reconstructed from an early fragment.

## 2. Classify the v1.4.5 family

The pipeline distinguishes three structural representations:

1. A serialized VM wrapper with a direct final constructor call.
2. An indirect serialized wrapper whose constructor alias is assigned inside flattened control flow.
3. A source-level transformed program with encoded strings and arithmetic rewriting but no serialized prototype tree.

Classification uses syntax and data-flow relationships, not a fixed set of randomized local names or whole-file signatures.

## 3. Recover serialized prototypes

For a direct wrapper, the VM constructor is replaced at its unique boundary. The automation tests the protected constructor stage structurally because fresh v1.4.5 builds place it at call one, two, or three. MoonVeil's decode-only bootstrap stages may run, but the protected program is intercepted before normal execution. The deserializer returns a graph that is serialized through a binary-safe protocol.

For an indirect wrapper, the decompiler resolves the constructor, deserializer, payload decoder, payload selector, and flattened alias assignment separately. The constructor is intercepted before that alias can execute the target.

Each table, key, value, and reference is retained. Python then identifies prototype tables, instruction arrays, nested prototype arrays, numeric metadata, and source fields by their shapes.

## 4. Infer the randomized VM layout

MoonVeil changes identifiers and numeric keys between outputs. The generic layout pass therefore discovers:

- VM executor and its register, nested-prototype, instruction, and state arguments
- Program-counter and current-instruction variables
- Opcode and program-counter-step fields, including equivalent or decoy fetch aliases
- Prototype parameter, stack, upvalue, source, instruction, and nested fields

Ambiguous layouts stop recovery rather than falling back to hard-coded guesses.

## 5. Stabilize and probe instructions

Lazy instruction records can rewrite themselves the first time they are fetched. The harness registers every recovered prototype and forces each instruction slot through the dispatcher. Multiple isolated modes reveal different aspects of the same operation:

- `proxy`: register reads, writes, calls, indexing, and external paths
- `symbolic_true`: symbolic expressions and the alternate side of comparisons
- `numeric`: numeric-loop behavior, arithmetic writes, and loop exit edges
- `zero`: numeric-zero branch behavior that truthy proxy values cannot expose
- `table`: exact numeric table slots written by raw `SETLIST` handlers
- `false`: false-value branch behavior
- `nil`: nil-specific branch behavior

The output is parsed into per-prototype observations and matched back to the static graph. The protected program receives proxy values rather than Roblox, network, or filesystem capabilities.

## 6. Lift canonical semantics

Observed effects and randomized numeric operands are converted into version-independent operations such as:

```text
GETIMPORT      R1, game
LOAD           R2, "https://example.invalid/script"
NAMECALL       R3, R1, "HttpGet"
CALL           R3, arguments/results
CLOSURE        R4, child prototype
CAPTURE        by value/reference/upvalue
COMPARE        registers and both targets
FORGPREP       generic iterator setup
FORGLOOP       generic loop variables and target
FORNPREP       numeric loop range check
FORNLOOP       numeric index update and target
GETVARARGS     open vararg range and destination
RETURN
```

Operand transformations are inferred from complete opcode groups rather than private opcode numbers. RETURN source/count fields are separated even when fixed returns collide with open returns; quiet `SETUPVAL` and `CAPTURE` operands are checked against register/upvalue bounds; and `SETLIST` source, count bias, and AUX start are recovered from the slots actually written by the embedded handler. A fixed zero-length `SETLIST` is represented canonically without guessing a behaviorally irrelevant AUX field. Unknown or ambiguous semantic kinds fail closed.

## 7. Reconstruct readable Luau

A small high-confidence cleanup recognizes the common `loadstring(game:HttpGet(url))()` shape and emits a short explicit loader with descriptive names.

All other lifted programs go through the structured reconstruction backend. It uses control-flow dominance, strongly connected components, backedges, postdominators, and Luau stack conventions to recover nested generic loops, numeric loops, exitless conditional `while` loops, `break`, `continue`, latch-block operations, open calls, vararg forwarding, and variable table construction. A second dataflow-safe source pass converts iterator protocols to native `for` syntax, folds scratch-register expression trees and table literals, turns terminating branches into guards, names parameters and loop values, and moves one-use closures back to their lexical creation sites with scoped capture cells. Shared closures remain explicit factories rather than being duplicated. Service acquisition and other proven values receive conservative semantic names. The supplied serialized regression corpus reconstructs without program-counter dispatchers; an unseen irreducible graph still fails over locally rather than being guessed.

The output cannot restore original variable names or comments because the protected VM payload does not retain them.

## 8. Handle source-level transformed inputs

Some v1.4.5 outputs are transformed source rather than serialized VM bytecode. For these, the static pass:

1. Locates the cyclic-XOR and Base64 decoder relationships.
2. Decodes only literal calls whose values are provable.
3. Recursively unwraps supported literal layers.
4. Folds arithmetic expressions that contain no runtime names or calls.
5. Re-formats statements while preserving strings, long-bracket literals, and comments.

Recognized source-level layouts are reconstructed into explicit named Luau after their behavior is resolved in the restricted harness. For unknown layouts, runtime-dependent flattened branches stay in the result with an explanatory comment; the tool does not guess their behavior.

## 9. Compile and compare traces

Every generated serialized-program output is parsed and compiled with `luau-compile`. When the wrapper supports runtime tracing, verification runs:

```text
original protected VM -> proxy environment -> canonical observable trace
reconstructed Luau    -> proxy environment -> canonical observable trace
```

VM-internal events and allocation addresses are removed. The remaining events must match in order and count. A mismatch aborts the command and reports the first differing event.

Both direct and indirect serialized wrappers use this final proxy comparison. If the protected original itself does not terminate within the dedicated 10-second verification budget, the comparison is reported as inconclusive and the compiler-valid recovery is still written; decode and compiler stages retain the caller's full timeout, and an actual trace mismatch remains a hard failure. Recognized source-level layouts are compiler-validated after semantic lifting; unknown source-level layouts retain unresolved runtime flow in the marked static fallback.

## 10. Use it on another complete file

```powershell
python -m moonveil decompile "C:\path\obfuscated.lua" `
  -o "C:\path\recovered.luau" `
  --artifacts "C:\path\moonveil-artifacts"
```

If the command reports truncation, obtain the complete file. If it reports an unknown layout or semantic operation, retain the artifacts for calibration; do not execute a guessed partial reconstruction.