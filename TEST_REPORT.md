# Test report — 12 October 2026

| Check | Result |
| --- | --- |
| `python manage.py test --noinput` | PASS: 455 tests in 482.322 seconds. Test database destroyed afterward. |
| `python manage.py check` | PASS: no issues. |
| `python manage.py makemigrations --check --dry-run` | PASS: no changes detected. |
| Frontend `npm run build` | PASS: TypeScript and Vite. JavaScript chunk is 506.59 kB, exceeding the 500 kB advisory threshold. |
| `git diff --check` | PASS. |
| `python manage.py check --deploy --settings=config.settings.production` | One local configuration warning: weak SECRET_KEY (security.W009). Railway configuration was not audited. |
| Frontend `npm run lint` | BLOCKED: ESLint 9 has no eslint.config.js/mjs/cjs configuration. |

Backend commands used DEBUG=False for the process because the inherited value is not a valid boolean. No application configuration or secrets were changed.

The existing suite covers accounts, employees, offboarding stages, documents, security/access cases, skills, and policies. It verifies the cases implemented in those tests, not every possible workflow.

No frontend test script or installed Playwright runner was found. Browser visuals, mobile behavior, keyboard interaction, console checks, and authenticated UI journeys were not tested. Production workflow mutations and actual SMTP delivery were not tested.

Follow-up: configure ESLint and rerun lint; review local secret strength and separately check production settings; perform desktop/mobile browser tests. Consider bundle splitting if loading performance requires it.
