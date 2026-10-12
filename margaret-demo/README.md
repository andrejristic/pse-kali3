# margaret-demo — teaching kit

Everything for the hands-on class where Margaret exercises all four tools
(recon · password · sniff · access) against authorized targets, ending with a
`margaret was here` file on your machine.

## Files
| File | What |
|---|---|
| `LESSON-PLAN.md` | the full class — 4 lessons, setup, cheat sheet (English) |
| `config.demo.yaml` | ready rules-of-engagement (the two authorized targets) |
| `words.txt` | small wordlist containing the lab password (for the cracker) |

## How to use
Run all commands from the repo root (`~/Desktop/pse-kali`). Before the class,
copy the two support files into place (and set your IP):
```sh
cp margaret-demo/config.demo.yaml config.yaml     # then edit YOUR-IP inside it
cp margaret-demo/words.txt .
```
Then open `LESSON-PLAN.md` and follow Part 0 (setup) → Lessons 1–4.

Every lesson is one `run_action.py` command; the kernel decides ALLOW/HELD. No
model needed. This is authorized only because the targets are the shipped lab and
your own machine, with your permission — see the top of the lesson plan.
