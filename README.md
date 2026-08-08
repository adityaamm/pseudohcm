# PseudoHCM — Test Harness

**Never ships. Deletable. Not a simulation of any organisation.**

A test fixture that stands in for a real HCM by speaking the published adapter
contract. Testing against it exercises the real integration path rather than
bypassing it.

See Document 10.

## What this is not

| Is | Is not |
|---|---|
| A test fixture for verifying software behaviour | A simulation of any real organisation |
| Deterministic output of a documented process | A dataset, benchmark, or source of evidence |
| Deletable without affecting the product | Shipped, bundled, or referenced in any release |

**No analysis run against this harness says anything about real workforces.** Every
result is a test of the software, never a finding about people.

## Hard rules

1. Nothing here may be imported by `aiecona-hr`.
2. Nothing here imports `aiecona-hr`. Both depend only on `aiecona-adapter-contract`.
3. Every emitted record carries the reserved marker and identifier namespace.
4. Harness data may **never** be used to validate forecast accuracy — it would measure
   only whether a model can recover its own generating rule set (D53).
