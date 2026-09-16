# Pending backend release: mobile-results-v5

The frontend can be published independently to Netlify. Backend v4 is currently live.

Before deploying v5 to Render, confirm durable storage and back up the running SQLite database, audio and outbox. A known production QA session disappeared after the v4 deployment. The repository declares Render Free; the effective production storage configuration has not been confirmed. SQLite and media currently remain local, and Supabase signup does not synchronize readings or restore the local database.

Do not describe v5 as deployed until `/api/config` returns `2026-09-15-mobile-results-v5` and live regression checks pass. Pushing the main branch triggers Render deployment; the prepared changes are saved separately for review while storage is investigated.

## Included fixes

- Enroll requires a password and verifies existing accounts; registering a legacy passwordless account requires recovery.
- An email match alone cannot claim historical sessions or orders. Switching accounts creates a separate session.
- Detailed plan validation provides private day/field diagnostics and at most one repair request per batch. Connection errors and provider rate limits are not retried automatically.
- Short welcome no longer says a completed plan is still being prepared.

## Checks performed

- 111 Python tests passed; 16 JavaScript UI tests passed.
- Six account security regressions fail against the earlier code and pass against the correction.
- Real DeepSeek plan test: 14 valid days, five minutes each, one repaired batch.

## Release checks still needed

1. Confirm storage service and take a consistent backup before restarting the backend.
2. Verify backup restoration; deploy v5 and check that an existing account, reading, plan, audio and progress survive.
3. Confirm account ownership regression protection in production using only synthetic accounts.
4. Repeat detailed-plan generation and optional welcome once in production.

Full progress report is in the audit task's outputs directory, outside this repository. Checkout is outside this release's scope.
