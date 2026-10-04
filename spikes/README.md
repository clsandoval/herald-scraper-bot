# Signal experiments

Retained research, not throwaway clutter. Their findings explain the menu's current signals.

| Directory | Evidence and role |
| --- | --- |
| `daimon/` | Independent unfinished Postgres/agent scaffold; [status](daimon/README.md). Excluded from product dependencies and tests. |
| `skill-weirdness/` | Ability-order surprisal experiments, Markov/PMI variants, calibration data. See `.planning/spikes/skill-weirdness/README.md`. |
| `signal-mining/` | Feeding, death time, chat and mega-creep comeback exploration. See `.planning/spikes/signal-mining/README.md`. |
| `stratz-signals/` | Raw signal availability and extraction research. See `.planning/spikes/stratz-signals/README.md`. |
| `menu-v2/approaches/` | Six presentation prototypes and their component contract. Findings in `.planning/spikes/menu-v2/README.md`. |
| `menu-v2/` | Compatibility shims plus historical posting/emoji tools. Assets and fixtures link to the maintained `herald/` copy. |

Historical `post.py`, `post_all.py`, and `emoji_sync.py` can write to Discord; they are not onboarding or test commands. Generated output and delivery receipts are ignored and must never be committed. Use the root README for current operations. Old research documents preserve historical claims; the current two-mode intent in README.md takes precedence.
