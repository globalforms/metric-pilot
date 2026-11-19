# Scoring completion roles in GlobalForms

Proposal for coauthor discussion · 19 November 2026

We propose ranking field-to-actor assignments in Track A and reporting explicitly printed role names separately. A form with one unnamed actor can then earn full assignment credit when every field omits its role.

## Three choices for the benchmark

| Scoring policy | Consequence for review |
| --- | --- |
| Match names on every field | A missing name can lose credit repeatedly. On the locker receipt, omitting both roles earns 100% with the Custodian default. Calling the same actor “Clerk” earns 0%. The form prints neither name. |
| Score field groupings alone | Arbitrary IDs work and splits or mergers lose credit. The scorer gives no credit for recovering a printed name such as “Applicant.” |
| Score assignments and names separately | Each field contributes to assignment quality. Each named actor contributes once to name precision and recall. We recommend this option for the pilot. |

## What would change in the spec

**Current pilot.** Fields and sections carry an optional `role` string. The locker review manifest supplies `"default_role": "Custodian"` and its reference repeats that name on the receipt section.

**Proposed extension.** Add a top-level `roles` map and an optional `defaultRoleId` to FormSpec. Replace the field and section `role` strings with optional `roleId` references. Resolve a field’s actor from its own assignment, the nearest assigned section, then the form default.

**Locker excerpt.** These two properties describe the single actor. The receipt section and both fields can omit `roleId`. Local IDs may vary. An empty actor record carries no name claim.

```json
{"roles": {"actor_1": {}}, "defaultRoleId": "actor_1"}
```

**Incident excerpt.** These are the role-related properties only. Applicant fields inherit the default. Office fields inherit their section’s override. A declared name requires evidence that identifies the actor. Here each ID points to its printed heading.

```json
{
  "roles": {
    "a": {"name": "Applicant", "nameEvidenceIds": ["applicant_heading"]},
    "b": {"name": "Business Office", "nameEvidenceIds": ["office_heading"]}
  },
  "defaultRoleId": "a",
  "sections": {"office": {"roleId": "b"}}
}
```

## Decision for the pilot

Align actor groups one-to-one by shared fields. Locker then earns **2/2 assignments** with zero reference names. An invented “Clerk” adds one false-positive name. On a form naming one actor, omitting that name costs one name claim. On the incident form, merging the actors loses assignment credit, while swapping just their names loses name credit.

Use the anonymous default for a reviewed single-actor form. Leave unresolved ownership unscored pending review. Examine assignment and name errors separately before deciding whether names belong in the headline score.
