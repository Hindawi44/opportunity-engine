# FINN Saved-Search Email Intake Adapter v1.0

**Domain:** `CLOTHING_INVENTORY` only
**Mode:** supplied-mail intake, no FINN page collection
**Automatic schedule:** not added by this task
**Commercial actions:** prohibited

## Purpose

Use FINN saved-search messages already delivered to an operator-owned mailbox as
a temporary Discovery input:

```text
FINN saved search
  -> delivered FINN alert message
  -> email intake adapter
  -> normalize and deduplicate stable FINN listing IDs
  -> Clothing Inventory Discovery Engine
  -> STRONG_LEAD_REQUIRES_VERIFICATION
  -> manual advert verification
  -> existing Opportunity Dossier boundary
```

This replaces live Playwright collection as the current experimental intake
path. It does not replace the authorized FINN API connector and does not grant
permission to collect or index FINN pages.

## Input contract

The adapter accepts operator-supplied:

- RFC822 `.eml` files; or
- JSON message objects with `sender`/`from_`, `subject`, `body`, optional
  `received_at`/`email_ts`, and optional `message_id`/`id`.

Accepted messages must:

- have the exact sender address `agent@finn.no`;
- have a subject beginning with `Nye annonser:`;
- contain at least one stable FINN advert reference.

The mailbox connector remains outside this module. The module does not store
mailbox credentials, recipients, raw MIME, or full message bodies.

## Link handling

The parser supports:

- FINN click-tracking URLs from `click.mailsvc.finn.no`;
- direct `https://www.finn.no/<listing-id>` links;
- current Torget item URLs;
- legacy Torget links containing a numeric `finnkode`.

Tracking URLs are decoded locally. They are never requested. Links for saved
searches, unsubscribe actions, search editing, help, and other non-item pages are
rejected. Stable listing IDs are deduplicated.

## Evidence boundary

Title, location, and price shown in an alert are retained only as email-channel
claims:

```text
advertised_price_nok
advertised_location
commercial_values_verified: false
page_opened: false
```

They must not populate the candidate's verified `price_nok`, `location`, active
status, or Analysis eligibility. Prices of `0` or `1 kr`, and phrases such as
`Send melding`, `Gi bud`, or `Pris på forespørsel`, are marked as symbolic or
unresolved.

Every accepted candidate must initially remain:

```text
opportunity_state: STRONG_LEAD_REQUIRES_VERIFICATION
listing_status: UNKNOWN
analysis_eligible: false
```

Only the existing manual verification boundary can confirm that a specific
listing is active, is genuinely for sale, and has bounded Clothing Inventory
evidence.

## Artifacts

The adapter writes the existing four Discovery artifacts plus:

```text
finn-email-intake.json
```

The extra artifact contains sanitized extracted fields and message fingerprints.
It excludes raw bodies, recipients, mailbox message IDs, and credentials.

## Manual execution

Export one or more FINN alert messages as RFC822 or connector JSON, then run:

```bash
PYTHONPATH=src:. python scripts/run_finn_email_intake.py \
  message-1.eml message-2.json \
  --output-dir artifacts/finn-email-intake
```

No FINN page is opened by this command.

## Scope lock

This task must not:

- modify the sixteen-query Clothing Inventory matrix;
- add a new opportunity domain;
- modify Brave, FINN API, or Playwright credentials or provider behavior;
- add a workflow, schedule, mailbox poller, or automatic execution;
- modify the Opportunity Dossier contract;
- modify market comparables, acquisition costs, financial formulas, scoring, or
  decision intelligence;
- contact a seller, bid, reserve, buy, or pay;
- log in to FINN, follow tracking URLs, import cookies, rotate proxies, bypass
  CAPTCHA, or bypass access controls.

## Success criteria

1. Real FINN click-tracking and direct advert links normalize to one stable ID.
2. Control links never become candidates.
3. Wrong senders and non-alert subjects fail closed.
4. Non-Clothing searches may be parsed but cannot enter Discovery Top 5.
5. Email prices and locations remain unverified source evidence only.
6. Symbolic `1 kr` cannot become a verified acquisition price.
7. Every email lead remains Analysis-blocked.
8. No network page is visited and no link is followed.
9. Existing Playwright and Discovery regression tests remain passing.
10. No raw mailbox content or message ID is written to artifacts.
