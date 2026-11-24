# MC2 (third-party)

`MC2v2.0beta2.jar` is MC2, the Monte Carlo model checker for PLTLc properties of
simulation traces (Bioinformatics Research Centre, University of Glasgow; later
distributed by the Data Structures and Software Dependability group of BTU
Cottbus). It is not part of TENNCell and not covered by its licence; it is kept
here unchanged because its former download is no longer online.

TENNCell does not use it at runtime. Only the opt-in MC2 tests run it
(`NNC_MC2_JAR`, with `java` on `PATH`); `scripts/ci_full_tools.sh` points the
full CI suite at this file.

SHA-256: `c177aa32ef7bb908bd44fa24000d40ecae620ec3ddd14d3bf5b0aa8f6a440d81`
