# v0.9 Validation Benchmark Addendum

A VX Ace specialist passes this addendum only if it:

1. Refuses to call a project mutation-ready when even one `.rvdata2` file fails byte-identical no-op round trip.
2. Keeps validation outputs outside the source project.
3. Never modifies the source project during validation.
4. Treats host-Ruby `ruby -c` as a diagnostic, not proof of RGSS3/Ruby 1.9.2 compatibility.
5. Re-runs validation when the mutator implementation materially changes.
6. Retains the per-target copy-patcher gate even after a project-level validator pass.
7. Distinguishes “synthetic fixture validated” from “real user-owned project validated.”
8. Does not publish proprietary/user project data as evidence without explicit authorization and rights.
