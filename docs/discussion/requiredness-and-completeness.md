# Score requiredness and submission completeness

The current pilot represents applicability and requiredness as distinct rule effects. Both require a choice-field trigger. Add a way to express unconditional requiredness and represent scenario- or role-dependent requirements when supported by the form or supplied workflow instructions.

- **Track A.** Score recovery of requiredness separately from applicability. Applicability determines whether a field is relevant. Requiredness determines whether an applicable field needs a value before submission. Resolve each requirement before checking whether its field is populated.
- **Track B.** Add a submission-completeness pass against the reviewed requirements for the scenario. Every applicable required field must have a valid value or an accepted prefill. Report missing or invalid required fields. Optional blanks leave completeness intact. Keep the existing score for faithfully handling the supplied information, including any penalty for unsolicited entries.

## Reimbursement example

If the scenario lacks the required IBAN, flagging it as missing can earn full credit for faithful handling while submission completeness fails. If a valid IBAN is supplied and entered, the IBAN requirement is satisfied. A client ID requirement can already be satisfied by a reliable customer association when the documented workflow accepts it.

## Acceptance criteria

- Agree how to represent unconditional requiredness and how it interacts with conditional rules.
- Add paired cases with a supplied and an absent required value, plus cases with an optional blank and accepted prefill.
- Report both Track B outcomes for each case.

[Tracking discussion](https://github.com/Jordy-VL/form2agent/issues/300#issuecomment-7191928942)
