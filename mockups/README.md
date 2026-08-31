# Mockups

Static presentation mockups. **Not connected to the engine.**

| File | What |
|---|---|
| `reviewer_queue.html` | Single-file reviewer verification screen, 1440×900, no scroll |
| `reviewer_queue_1440x900.png` | Full-frame render for a slide |
| `cross_examination_crop.png` | Column 3 alone, 382×806, for a second slide |

## The numbers on this screen are illustrative

`Committed 812 · Flagged 47 · Unverifiable 19`, Mouza Bahilwara, khesra 217/1 and
the five witness values are **invented for the mockup**. They are not output from
`kavach.report`, and no real corpus has been processed.

The working UI over real engine output is `../dashboard.html`
(`python -m kavach.webui`). That one's figures are computed; this one's are not.

Caption any slide using these renders accordingly. On a pitch whose thesis is
"stop shipping systems that assert things they cannot back up", an uncaptioned
mockup screenshot is the one avoidable own-goal.

## Regenerating

```bash
open mockups/reviewer_queue.html          # or screenshot at exactly 1440×900
```
