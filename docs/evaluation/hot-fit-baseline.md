# HOT-fit evaluation baseline

## Evaluation purpose

This baseline defines how the academic HEC dashboard prototype will be evaluated across Human, Organization, Technology, and net-benefit dimensions. It is a protocol, not a report of completed evaluation. No result is assumed in advance.

The evaluation asks whether the prototype is understandable, usable, organizationally plausible, technically reliable, privacy-preserving, and useful for the approved role-specific decisions without encouraging unsupported or punitive interpretation.

## Dimensions

### Human

Assess role relevance, cognitive load, task completion, interpretability, accessibility, confidence in provenance, and calibrated trust in simulated data. Professional walkthroughs must explicitly test whether participants avoid ranking and causal attribution.

### Organization

Assess fit with executive, service-management, and professional review workflows; governance ownership; training burden; target approval; simulated-data controls; and the boundary between an academic prototype and institutional operations.

### Technology

Assess contract integrity, calculation correctness, upload safety, data quality, reliability, performance, accessibility behavior, privacy invariants, maintainability, and reproducibility.

### Net benefits

Assess whether each role can identify a relevant signal, understand its limitation, and name a bounded review action more efficiently than from an unstructured extract, without increasing privacy, misuse, or false-authority risk.

## Evaluation stages

| Stage | Purpose | Minimum evidence |
|---|---|---|
| Design review | Verify traceability, scope, role relevance, privacy, and interaction contracts before application coding | Contract validator, architecture review, wireframe checklist, unresolved decision log |
| Internal functional test | Verify calculations, navigation, filters, upload behavior, null semantics, disclosure control, and performance | Automated tests, scripted scenarios, timings, defect log |
| Simulated user walkthrough | Observe comprehension, task success, accessibility, workflow fit, and misuse risks with representative role scenarios | Task sheet, observation notes, timing/click counts, brief structured feedback |
| Final academic demonstration | Demonstrate end-to-end value, limitations, evidence, and project fit | Stable public URL, scripted demo, validation evidence, limitations statement |

## Stakeholders and ownership

| Stakeholder/role | Evaluation interest | Ownership |
|---|---|---|
| Project team | Delivery quality, reproducibility, evidence collection | Evaluation coordinator maintains protocol and evidence index |
| Director/Director Médico proxy | Institutional and clinical-governance relevance | Product owner validates questions and interpretation boundaries |
| Service Chief proxy | Tactical workflow and service/specialty fit | Clinical-content owner validates selectors and review actions |
| Professional proxy | Non-punitive usefulness and misuse risk | Professional-safety reviewer validates language and separation of lenses |
| Data/technical reviewer | Calculation, validation, lineage, performance | Technical lead owns tests and defect resolution |
| Privacy/security reviewer | Law 21.719 constraint, minimization, disclosure, public-hosting limits | Privacy owner approves demonstration data and evidence |
| Course evaluator | Academic coherence, project logic, defensible limitations | Team prepares concise traceability and demonstration evidence |

Named team-member assignments are intentionally deferred until the team confirms responsibilities; role-level ownership is sufficient for this baseline.

## Evidence sources

- Approved service, indicator, role, map, and UI contracts.
- Architecture decisions and wireframes.
- Automated contract and calculation tests.
- Upload test cases covering valid and invalid workbooks.
- Aggregate performance timings and application error observations.
- Accessibility checklist and keyboard/screen-readable summaries.
- Simulated walkthrough task sheets, observations, and de-identified feedback.
- Demonstration screenshots or recordings containing simulated aggregate data only.
- Version, deployment, validation, and defect evidence.

## Traceability matrix

| HOT-fit dimension | Evaluation question | Evidence | Measure | Acceptance threshold | Responsible role | Stage |
|---|---|---|---|---|---|---|
| Human — role relevance | Does each view answer its approved management questions without irrelevant detail? | Role matrix, walkthrough | Relevant task completion and structured rating | At least 90% critical tasks completed; no role-contract mismatch | Product owner | Design review; walkthrough |
| Human — cognitive load | Can users find status, change, and review action without avoidable navigation? | Observation, timing, click count | Task completion, dead ends, qualitative burden | No critical task has a navigation dead end; median time/clicks recorded for improvement | UX/evaluation coordinator | Walkthrough |
| Human — interpretability | Can users distinguish current, prior, target/reference, quality, and unavailable states? | Comprehension questions | Correct interpretation rate | At least 80% correct across critical cases | Clinical-content owner | Walkthrough |
| Human — accessibility | Can the core journey be used without color-only meaning and with textual equivalents? | Accessibility checklist, keyboard test | Critical violations and journey completion | Zero critical color-only or missing-equivalent defects | UX/accessibility reviewer | Design review; functional test |
| Human — trust in simulation | Do users understand what is simulated and what comes from public DEIS? | Banner/provenance review, questions | Correct source classification | 100% test users identify simulation and public-reference boundaries | Evaluation coordinator | Walkthrough; demonstration |
| Organization — workflow fit | Do views align with executive, service, and professional review cadence and action? | Scenario walkthrough, stakeholder notes | Fit issues and actionable task success | No unresolved critical workflow mismatch | Product owner | Design review; walkthrough |
| Organization — governance | Are owners defined for contracts, targets, privacy, deployment, and defects? | Ownership table, decision log | Unowned critical control | Zero unowned critical controls before demonstration | Project lead | Design review; demonstration |
| Organization — training burden | Can evaluators complete core tasks with concise onboarding? | Walkthrough | Assistance rate and onboarding time | At least 90% critical tasks completed without facilitator assistance after brief orientation | Evaluation coordinator | Walkthrough |
| Organization — professional misuse | Could the interface support ranking, punishment, or individual causal attribution? | Professional scenarios, UI review | Misuse affordances/interpretations | Zero ranking or combined-score feature; all findings include boundaries | Professional-safety reviewer | Design review; walkthrough |
| Organization — target authority | Could a reference be mistaken for an official HEC target? | Target labels, comprehension questions | Misclassification count | Zero unlabeled references; applicability explained in every applicable view | Clinical-content owner | Design review; walkthrough |
| Technology — data quality | Does validation expose acceptance, completeness, rejections, codes, dates, duplicates, and unmatched origins? | Validator, invalid-upload scenarios | Expected outcomes matched | 100% planned scenarios produce expected status and summary | Technical lead | Functional test |
| Technology — reliability | Do role/filter/upload journeys behave consistently without corrupting active state? | Automated and scripted tests | Pass rate and critical defects | 100% critical tests pass; zero open critical defects | Technical lead | Functional test |
| Technology — performance | Are warm interactions and normal sample upload responsive enough for demonstration? | Timed runs | Warm interaction and upload duration | Warm interactions generally ≤2 s; normal sample upload ≤10 s | Technical lead | Functional test; demonstration |
| Technology — privacy | Are identifiers, addresses, patient detail, small cells, persistence, and ranking controlled? | Contract tests, repository scan, map scenarios | Privacy invariant failures | Zero failures; all geographic cells below 10 suppressed | Privacy owner | Design review; functional test |
| Technology — maintainability | Are contracts normalized, validated, documented, and separate from rendering logic? | Repository review, tests | Broken references, duplicated definitions | Contract validator passes; no KPI definition duplicated in UI contract | Technical lead | Design review |
| Technology — calculation accuracy | Do critical indicators match independent expected results and null semantics? | Calculation fixtures to be created during implementation | Expected-result match | 100% critical KPI cases match; denominator zero returns unavailable | Technical lead | Functional test |
| Net benefits — decision usefulness | Can each user identify a signal, limitation, and safe review action? | Scenario response | Complete decision-support response | At least 80% of critical scenarios answered correctly | Product owner | Walkthrough; demonstration |
| Net benefits — efficiency | Is the structured view more direct than an unstructured extract for approved tasks? | Comparative task notes where feasible | Time, steps, qualitative preference | Evidence recorded; no claim of superiority without observed comparison | Evaluation coordinator | Walkthrough |
| Net benefits — risk balance | Does value remain plausible without confidential data or unsupported claims? | Final risk review | Unmitigated critical risk | Zero unmitigated critical risk for simulated public demonstration | Project lead and privacy owner | Demonstration gate |

## Critical simulated walkthrough tasks

1. Select a role and reach the correct dashboard scope.
2. Identify current status, comparable change, and the first review priority.
3. Change a filter and explain whether the denominator meaning changed.
4. Inspect a geographic signal and confirm the accessible table and small-cell behavior.
5. Upload an invalid workbook and verify that the active dataset remains unchanged.
6. Upload a valid workbook, review the summary, and explicitly activate it.
7. For a mixed professional, explain the clinical and surgical lenses without creating a combined score.
8. Identify a reference target and explain why it is not automatically an official HEC target.

## Risks

| Risk | Evaluation control |
|---|---|
| Small convenience sample overstates usability | Report participant characteristics and treat findings as formative |
| Team members know the interface too well | Include at least one walkthrough participant not involved in implementation if feasible |
| Simulated data creates false confidence | Test provenance comprehension and repeat visible disclaimers |
| Academic demonstration rewards appearance over correctness | Require calculation, contract, upload, and privacy evidence |
| Professional metrics invite misuse | Test ranking, blame, and combined-score interpretations explicitly |
| Reference target appears institutionally approved | Test applicability explanation and target-label comprehension |
| Performance varies on free hosting | Measure warm and cold behavior separately and disclose host limitations |
| Accessibility is reduced to color contrast | Test keyboard flow, text equivalents, tables, focus, and status labels |

## Acceptance and gate rules

- A failed critical privacy, active-dataset preservation, mixed-profile separation, calculation, or contract-integrity test blocks the public demonstration.
- High-severity usability or interpretation defects require correction or a visible limitation and bounded workaround.
- Medium/low issues may remain only when recorded with owner, consequence, and deferral rationale.
- Thresholds are prototype acceptance targets, not observed results.
- Any institutional claim requires evidence beyond this academic protocol.

## Evidence recording

For each test, record date, build/commit identifier, contract versions, scenario, expected outcome, observed outcome, pass/fail, non-sensitive evidence link, defect ID, owner, and disposition. Do not capture uploaded row payloads, identifiers, patient-level content, or confidential information.

## Residual limitations

The baseline does not establish clinical validity, production safety, institutional adoption, population impact, cost-effectiveness, or compliance certification. Simulated walkthroughs and a short academic timeline cannot reproduce real HEC workflow pressure or stakeholder diversity. Free hosting does not demonstrate production availability or security. HOT-fit results, once collected, will support formative judgment only and must be reported with sample, method, and limitations.
