# Source Shadow Live Validation V1

This benchmark proves whether source candidates learned from confirmed external `SOURCE_GAP` misses can discover and independently verify a new stock opportunity that was not part of the teaching set.

Safety invariants:

- validated sources are scanned only in shadow mode;
- teaching URLs are excluded before candidate verification;
- exact candidate pages must prove a stock/lot opportunity;
- source count, candidate count, and exact-page requests are bounded;
- no source becomes production-active;
- no query/source production config is changed;
- no automatic promotion, contact, bid, purchase, or payment is allowed.

The temporary PR workflow used for the first live proof is intentionally removed before merge. The retained code is the manual bounded shadow runner plus its tests and the frozen proof result.
