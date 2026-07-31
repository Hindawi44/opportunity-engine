# ny.auksjonen.no item redirect fix V1

Manual structured discovery after PR #370 recovered 10 current clothing-category item URLs, but the bounded Playwright verifier still rejected redirects from `auksjonen.no` item pages to the same item route on `ny.auksjonen.no`.

This fix accepts only stable `/auksjon/.../<numeric-id>` item routes on the two approved public frontend hosts, canonicalizes the new frontend host back to `auksjonen.no`, and then applies the existing HTML verification and source-channel hard gates.

Unrelated routes, category pages, query pages, and external hosts remain rejected. No login, contact, bid, purchase, or payment behavior is added.
