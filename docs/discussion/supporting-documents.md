# Supporting documents in GlobalForms

Proposal for coauthor discussion · 19 November 2026

When a form asks for proof, Track A should recover what the applicant must supply. Track B should score how faithfully the response uses the documents available in the scenario. A response can earn full credit for reporting a missing document and still be incomplete for submission.

## What makes a document required

Consider a fictional application. “Enter your home address” asks for a value. “Attach your ID, front and back. Both sides are required” creates one proof request with two parts. A third instruction asks employed applicants for an offer letter or an employment certificate. Suppose the offer letter contains the employer’s VAT number. That fact becomes a required answer only if an application instruction asks for it.

**Proposed Track A spec excerpt.** The example anchor `E-id` locates the ID instruction on page one. The same anchor supports requiredness and both parts. A heading that merely says “ID” would not establish that the back is required.

```json
{"evidence": {"E-id": {"page": 1, "bbox": [40, 160, 500, 30]}},
 "attachmentRequests": {"identity": {
  "required": true, "evidenceIds": ["E-id"],
  "documents": {"op": "document", "documentType": "ID",
    "evidenceIds": ["E-id"], "parts": [
      {"name": "front", "evidenceIds": ["E-id"]},
      {"name": "back",  "evidenceIds": ["E-id"]}
    ]}
}}}
```

The offer letter establishes where a VAT value came from. The application never asks for it, so leaving it out earns full credit. Adding a VAT requirement to the recovered spec would be one Track A false positive.

## How Track B would score the same application

Assume the applicant is employed. Score three units for home address, ID and employment proof. The address and employment proof are correct in every row. Score the ID request once. Report the missing side as a diagnostic.

| Scenario and response | Proposed Track B outcome |
| --- | --- |
| Only the ID front was supplied. The system submits it and reports the back missing. | **3/3 faithful.** The application still needs the back before submission. |
| Both sides were supplied. The system submits only the front. | **2/3 faithful.** The ID loses one unit. The missing back identifies the reason. |
| Both sides were submitted. The system also returns the VAT number from the offer letter. | **3/4 faithful.** All three expected units are correct. The unsolicited field adds one extra to the denominator, even if its value is accurate. |

**Proposed output for the first row** (ID excerpt). The reviewed attachment inventory contains only the front of `id_scan`.

```json
{"documentSelections": {"identity": [
  {"attachmentId": "id_scan", "parts": ["front"]}]},
 "missingParts": {"identity": ["back"]}}
```

**Decision for the pilot.** Review the evidence for each obligation and freeze the attachment inventory before scoring. Report faithful completion and readiness separately. These counts illustrate the proposed extension to the current field scorer.
