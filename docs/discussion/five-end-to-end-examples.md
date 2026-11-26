# Audit FormSpec and scoring with five real forms

**Owner:** Jishu

Build five end-to-end examples using real corpus forms. Review the first worked example with Jordy before building the other four.

## For each example

1. Cite the form and the page or region that supports the expected behavior. Annotate the relevant fields, roles, rules, and constraints in a reviewed reference FormSpec.
2. Write two contrasting scenarios. Record what a human would enter or omit and whether each application is ready to submit.
3. Run Track A recovery and Track B completion. Save the source reference, spec, scenario, expected entries, candidate output, and actual and expected scores. Use current-version Gemini predictions if available, with hand-authored candidates for controlled comparisons or when predictions are unavailable.
4. Identify any workflow behavior the current spec misses. Propose the smallest supported change and show before-and-after behavior with a regression fixture. For each gap, explain whether an existing metric covers it, a diagnostic suffices, or a separate metric measures a distinct outcome.

## Coverage across the five examples

Include supporting documents, document-specific validations, role assignments, and requiredness versus applicability. Exercise missing required information, optional blanks, or surplus information where the source supports those cases.

Use one example where a real instruction paragraph governs multiple fields. Anchor the paragraph by page and location, and link each structured claim to the supporting passage. Test whether the spec can express mandatory completion order if the source requires it. For Track A, compare a correct rule with a supporting citation, a correct rule with a weak citation, and a wrong rule that cites the right paragraph. Report evidence support as a diagnostic alongside rule correctness.

## Deliverable

Open one PR with all five reproducible examples, the evidence-backed spec changes, and any justified metric changes. Include expected scores and open scoring decisions for review.

Jordy may ask Artemis where the samples are and can provide current-version Gemini predictions for a handful of forms if useful.

[Coauthor discussion briefs](https://github.com/globalforms/metric-pilot/tree/main/docs/discussion)
