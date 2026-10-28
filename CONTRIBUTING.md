# Contributing

Thanks for helping improve Gbuds. Changes should keep model compatibility claims evidence-based and avoid sending undocumented packets to real devices.

## Before opening a pull request

1. Check the existing issues and avoid duplicate work.
2. Keep each change focused; explain any protocol assumptions.
3. Add or update offline regression coverage for behavior changes.
4. Run the checks in [Development](docs/DEVELOPMENT.md).
5. Update the support matrix and changelog when user-visible behavior or compatibility changes.

## Pull request description

Include:

- What changed and why.
- Models and firmware versions affected, if known.
- Tests/checks run and their results.
- Whether behavior was validated with fixtures, physical hardware, or both.
- Any known limitations or migration impact.

Redact Bluetooth addresses, earbud/case serial numbers, and private data from logs. Never include firmware dumps or packet captures containing personal identifiers without reviewing and sanitizing them first.

## Scope and evidence

An ID/name mapping is not proof of command support. Keep recognition, fixture coverage, and physical testing distinct in code comments and documentation. When relying on GalaxyBudsClient, identify the relevant upstream specification or test and preserve fixture attribution.

## License

By submitting a contribution, you agree that it may be distributed under the project's MIT License.
