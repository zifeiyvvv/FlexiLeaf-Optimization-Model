# FlexiLeaf Design-Basis Digital Twin Case Study

This folder is a prospective simulation of the planned FlexiLeaf campus and
community microgrid. It is **not measured operational data**.

## Fixed evidence layers

- HKO King's Park 2025 daily global solar radiation.
- HKO King's Park 2025 daily relative humidity.
- HKO King's Park 2025 daily bright sunshine.
- Blueprint-defined buildings, PV surfaces, storage and V2G resources.
- Explicit engineering assumptions recorded in `assumption_register.csv`.

## Main files

- `design_case_8760h.csv`: detailed design/full-microgrid hourly case.
- `design_configurations_8760h.csv`: five design configurations.
- `scenario_comparison.csv`: 3 performance scenarios × 5 configurations.
- `monthly_summary.csv`: monthly metrics for every scenario/configuration.
- `assumption_register.csv`: provenance and uncertainty classification.
- `validation_summary.json`: numerical checks and headline result.

## Required wording

Use:

> In the design-basis prospective digital-twin case, the model estimates...

Do not use:

> The installed system actually achieved...

Generated case ID: `flexileaf_design_basis_2025`
