# Repository guidance

## Runtime and commands

- Support Python 3.13. The application has no runtime dependencies and runs directly from a checkout:
  `python -m pagerduty_auto_ack --pagerduty-api-key <api_key>`.
- Before handing off a change, run:
  `python -m unittest discover -v` and `python -m pagerduty_auto_ack --help`.
- Do not add a dependency, virtual-environment requirement, pipx, or Poetry to the normal run path without an explicit reason.

## PagerDuty safety

- A normal invocation acknowledges live incidents. Use mocked clients in tests and do not run the acknowledgement loop against a real PagerDuty token unless explicitly requested.
- Keep the API token out of source control, test output, and logs.

## Implementation

- Keep the HTTP client dependency-free, using the Python standard library.
- Preserve pagination when changing incident retrieval and preserve batching when changing acknowledgement requests.
