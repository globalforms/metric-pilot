# Validations as tools in GlobalForms

Proposal for coauthor discussion · 19 November 2026

We propose recording a document-specific validation as a deferred function call. Track A asks whether a system recovers the call from a blank form. Track B asks whether it handles a supplied value correctly.

## What would change in the spec

**Current pilot.** Each entry in `FormSpec.validations` has a fixed kind and kind-specific parameters. This is how the local pilot expresses an instruction that the reference number must leave remainder 1 when divided by 97.

```json
{"kind": "checksum", "algorithm": "decimal_mod_97", "remainder": 1,
 "fields": ["reference_number"], "evidenceIds": ["checksum_instruction"]}
```

**Proposed extension.** Add a `tool_call` kind alongside the existing kinds. A versioned tool catalog defines the function signature once. In this example it is `decimal_remainder(value: str, modulus: int, expected: int) → bool`. The form spec would store the following call.

```json
{"validations": [{
  "kind": "tool_call", "tool": "decimal_remainder", "version": 1,
  "inputs": {"value": {"fieldId": "reference_number"}},
  "arguments": {"modulus": 97, "expected": 1},
  "evidenceIds": ["checksum_instruction"]
}]}
```

Here `reference_number` identifies an existing field. The evidence ID points to the printed instruction. At completion time the runner passes the original digit string to the function and compares its decimal remainder with the expected value.

## What each track scores

**Track A · Rule recovery.** Compare the aligned field, function and arguments with the reviewed rule. Only score constraints supported by the form. “Pickup date” establishes the field type. A printed “YYYY-MM-DD” also establishes a format. Six character cells support a maximum of six. “Exactly six digits” also supplies a minimum and a digit alphabet.

**Track B · Completion behavior.** Award the paired check when the system handles both supplied values correctly. Include the missing-value case to verify omission separately.

| Scenario supplies | Expected completion |
| --- | --- |
| `00098` | Return `00098`, preserving its leading zeroes. |
| `00099` | Return `invalid`. Its remainder is 2. |
| No reference number | Accept omission. There is no supplied value to validate. |

Run the same scenarios with the reviewed spec and with the recovered spec. Compare their results to locate recovery errors. Keep the execution trace for diagnosis.

## Decision for the pilot

The model would receive the catalog of signatures and allowed arguments. For an unfamiliar rule, let it propose a signature, implementation and source evidence. Withhold the checksum tool as a first experiment. Freeze the proposed function before running it in isolation on independently authored, hidden cases. Compare it with the registered-tool baseline.
