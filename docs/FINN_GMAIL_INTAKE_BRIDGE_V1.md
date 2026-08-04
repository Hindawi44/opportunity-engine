# FINN Gmail Intake Bridge V1

## Purpose

Integrate operator-owned FINN saved-search email alerts into the existing
multi-market checkpoint without opening FINN advert pages or creating a second
discovery architecture.

## Runtime path

```text
FINN saved search
→ Gmail read-only API
→ existing run_finn_email_intake.py
→ existing Clothing Inventory discovery contracts
→ narrow FINN/Auksjonen channel aliasing
→ existing multi-market checkpoint and bulletin
```

## Credentials

The manual checkpoint reads these GitHub Actions secrets:

- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`

The OAuth grant is limited to `gmail.readonly`. The workflow never sends,
modifies, labels, archives, or deletes email.

## Bounds

- fixed Gmail API hosts only
- fixed FINN sender and subject filter
- seven-day Gmail query window
- maximum 20 messages per checkpoint run
- maximum hard limit 50 messages in the CLI
- raw RFC822 messages are processed in memory
- mailbox credentials, access tokens, refresh tokens, raw message bodies, and
  Gmail message IDs are never written to artifacts
- FINN links are decoded but never opened

## Cross-channel linkage

A FINN lead is aliased to an Auksjonen opportunity only when all conditions are
true:

1. the email context explicitly identifies `Auksjonen.No AS` as seller;
2. the normalized FINN title exactly matches one and only one clothing-lot title
   in the current Auksjonen report;
3. the Auksjonen record already has a stable checkpoint identity.

The result remains one opportunity with two evidence channels. Ambiguous title
matches and non-Auksjonen sellers remain separate unverified FINN leads.

## Safety lock

- no FINN page scraping
- no Facebook access
- no seller contact
- no automatic bid, reservation, purchase, or payment
- no commercial-value verification from email claims
- no change to transport, profit, ROI, or resale calculations
- no new country, database, service, or user interface
