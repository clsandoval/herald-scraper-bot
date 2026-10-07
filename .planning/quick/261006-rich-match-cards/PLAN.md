# Rich match cards and renderer safety

## Goal

Make replay selection readable from item inventories, early skill paths and factual
micro-events, preserving scheduled-report eligibility and the private menu's
separate corpus policy. No live sends, emoji creation, deployment or secrets.

## History reviewed

The full 104-commit checkout was available. Followed the moved render/board files
and reviewed relevant historical changes: 5f48ff3, bc688e9, 4cf5deb (V2 prototypes
and glance rows), b955251/241b5c2 (item receipts), 4eb8614/5037ac0/d57abe5
(skill scoring and rejected whole-build/rule approaches), 6c6c36a/9a781c1
(micro-event receipts and discarded ward/fountain proxies), 44b5610 (locked
threshold and async regressions), and dcd6579 (two-mode handoff). The original
b5e0ec1/82e3c39 item/ability rendering history was also reviewed.

## Implementation

- Keep the reporter's parent plus two classic-embed team messages, compatible
  with immutable historical delivery receipts. Lead team fields with final
  inventory and numbered non-talent skill picks, followed by factual review
  moments. Parent provides build/skill previews and explicit review cues.
- Keep the menu on actual Discord Components V2. Shared pure render helpers
  provide compact build-oriented list cards and separate inventory/skill tabs.
  Preserve existing corpus thresholds and winner-neutral evidence.
- Missing and explicitly empty data have distinct labels. Unknown KDA/APM and
  scores do not become zero. Malformed optional notes fail closed.
- Use only application emojis explicitly present in the active inventory, with
  readable names as fallback. Do not invent inline image support in an embed.
- Validate classic embed field and message budgets separately from V2's
  conservative 3,600-text-character / 40-component project guard.
- Serialize Matplotlib Agg access with a shared lock and clean leaked figures
  in a finally block. Empty charts say data is unavailable.

## Verification

Offline test coverage in tests/test_match_cards.py includes rich/missing/empty
builds, longest bundled inventory names, skill truncation, malformed archive
notes, nullable KDA/APM/scoreboards, spoiler-neutral micro-events, classic limits,
concurrent chart generation, empty charts and exception cleanup. Existing
scheduled delivery, menu and mode-boundary tests remain part of the full suite.
Simulator screenshot QA consumes the production payloads, not a parallel mock.

## Current reference constraints

- Discord V2 requires IS_COMPONENTS_V2=32768 and excludes classic content/embeds;
  nested components count toward the 40-component limit. Attachments must be
  referenced by components.
  https://docs.discord.com/developers/components/reference
- Classic embeds: title256, description4096, <=25 fields, field name256/value1024,
  footer2048, author256, total text <=6000 across the message's embeds.
  https://docs.discord.com/developers/resources/message#embed-object-embed-limits
- Matplotlib is not thread-safe; callers must serialize artist access and use a
  non-interactive backend for worker-thread rendering.
  https://matplotlib.org/stable/users/faq.html#work-with-threads
