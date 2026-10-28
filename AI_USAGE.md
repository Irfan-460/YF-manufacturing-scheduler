# AI Usage Disclosure

This project was developed with AI assistance (Amazon Q Developer).

## What AI was used for

- Generating the initial project scaffold and module structure
- Writing boilerplate for data generation, scheduling logic, and validation checks
- Drafting documentation (README, data dictionary, ER diagram, schema SQL)
- Suggesting test cases for edge conditions

## What was reviewed and verified manually

- All business rules (routing, changeover, material gates, shift calendars)
- Scheduling algorithm correctness (priority ordering, slot selection, overlap prevention)
- Anomaly injection logic (ensuring injected anomalies are detectable by validators)
- Ground truth separation (confirming labels are not leaked into input features)
- Reproducibility (fixed seed, counter reset, deterministic RNG)

## Prompts

Raw prompt history is stored in `prompts/`.

## Limitations

AI-generated code was treated as a first draft. All logic was reviewed for correctness against the problem statement before acceptance.
