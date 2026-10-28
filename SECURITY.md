# Security policy

## Supported versions

Security fixes are made against the latest supported release. This project is currently in beta; users should update to the newest release before reporting a suspected vulnerability.

## Reporting a vulnerability

Do not report security issues in a public issue. Use GitHub's private **Report a vulnerability** feature for this repository when available. If private reporting is unavailable, contact the repository maintainer through the contact method listed on the GitHub profile and include only the minimum information needed to reproduce the issue.

Please include the affected version, Linux distribution, Python version, impact, and a minimal reproduction. Do not attach Bluetooth addresses, earbud/case serial numbers, pairing data, or unredacted captures unless they are essential to the report.

## Sensitive data

`gbuds info` can display a Bluetooth address and device serial numbers. Review and redact output before sharing it. Gbuds does not require an account, cloud service, or project-managed secret.
