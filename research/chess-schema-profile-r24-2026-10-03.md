# R24 schema profile

Research date: 2026-10-03.

SportsPlay v4 evidence schemas need a fixed validation profile in addition to byte hashing.

Use JSON Schema Draft 2020-12 with an explicit `$schema` and a non-network root ID of the form `urn:sportsplay:schema:chess:v4:<name>:1`. Permit only local `#/$defs/<name>` references, closed objects, explicit required fields, arrays, strings, booleans, null, safe integers, enum and const. Reject unknown keywords, external or dynamic references, format, pattern, open objects, binary floats and recursive refs in profile v1.

Cloud check: Python 3.13.5, jsonschema 4.26.0, referencing 0.37.0. The reference profile passed 23 focused tests and an 11-case differential corpus matched Draft202012Validator with zero mismatches using an empty Registry.

Primary references: JSON Schema Draft 2020-12 Core/Validation, referencing Registry documentation, python-jsonschema, and Bowtie. Accessed 2026-10-03.

Next native step after the existing C00/R20/R22/R23 gates: add source-controlled v4 schemas and run profile lint, meta-schema checking and the differential corpus before connecting them to the v4 evidence graph.
