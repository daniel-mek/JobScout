# /status - move a posting through the tracker

`$ARGUMENTS` is `<key> <state>` plus optional words. Example: `/status google_software-engineering-intern Applied submitted through the careers site`.

States: Found, Saved, Prepped, Applied, OA, Interview, Offer, Rejected, Withdrawn, Passed. The candidate is the only one who submits anything, so `Applied` is always their statement, never Scout's guess.

## Steps

1. Parse the key and the state from `$ARGUMENTS`. Anything after the state is a note. If the key is not obvious, look it up: `grep -i "<company>" data/matches.json | head` or `python -m scout.tracker list`.
2. Run it:
   ```bash
   .venv/bin/python -m scout.tracker set <key> <State> --note "<note>" --next "<next action, if they said one>"
   ```
3. If the state is `Applied` and an `applications/<folder>/answers.md` exists for this posting, read it and ask one question: "Any of these answers worth keeping for next time?" If they name one, append it to `me/answer_bank.md` under a heading with the company and date. Never append without their yes.
4. Reply in one line: the company, the new state, and the next action if any.
