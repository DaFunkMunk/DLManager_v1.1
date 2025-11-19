# Distribution List Copilot – Training Sample Validator

This repository contains the Distribution List Copilot demo plus supporting tools.  
The newest addition is `scripts/validate_training_samples.py`, a regression harness that replays every utterance in `training_samples.jsonl` against the current intent parser (or the running API) and reports pass/fail results.

---

## Prerequisites

- Python 3.10+ (matches the versions used for the Flask app and parser).
- Dependencies from `requirements.txt` installed in your virtual environment:

  ```bash
  python -m venv .venv
  .\.venv\Scripts\activate
  pip install -r requirements.txt
  ```

- Model artifacts present at `models/intent_slot` (already committed) so the script can instantiate `IntentSlotParser`.

> **Note:** API validation requires the Flask app to be running (`python app.py`) and, if authentication is enabled, a valid session cookie (log in via the UI once before running the script).

---

## Running the Validator

### Validate Everything (Default)

```bash
python scripts/validate_training_samples.py
```

- Loads every line in `training_samples.jsonl`.
- Instantiates the local parser (no HTTP calls required).
- Compares the returned intent/slots with the expected values inside each training sample.
- Writes a JSONL log to `validation_logs/validation_<timestamp>.jsonl`.
- Exits with code `0` if all samples pass; non‑zero if any fail.

### Use the Live API Instead of the Local Parser

```bash
python scripts/validate_training_samples.py --mode api --base-url http://127.0.0.1:5000 --cookie "session=eyJfcGVybWFuZW50Ijp0cnVlLCJ1c2VyIjoiYWRtaW4ifQ.aRPG4Q.UI6JJ50Q9NAO54SzB-qng8WFNoA"
```

- Requires the Flask app to be running and accessible at the provided base URL.
- If authentication is enabled, supply your Flask session cookie via `--cookie` (copy it from browser dev tools after logging in).
- Sends each prompt to `/api/nlp/parse` with `X-Mode: demo`.
- Slot comparisons treat certain optional fields (rule/group metadata) as warnings so you can see coverage without failing the entire run.
- User/group name comparisons are case-insensitive to match the parser’s normalized output.
- Useful for verifying the deployed API (or remote environments) without modifying the script.

### Focus on a Subset

The validator accepts optional filters so you can concentrate on specific scenarios during debugging:

```bash
#API validator with the skip flag manager-rule 
python scripts/validate_training_samples.py --mode api --base-url http://127.0.0.1:5000 --cookie "session=eyJfcGVybWFuZW50Ijp0cnVlLCJ1c2VyIjoiYWRtaW4ifQ.aRPG4Q.UI6JJ50Q9NAO54SzB-qng8WFNoA" --skip-intent edit_rule

# Only employee_record_set utterances
python scripts/validate_training_samples.py --intent employee_record_set

# Only samples whose field updates include "active"
python scripts/validate_training_samples.py --field active

# Combine filters (logical AND)
python scripts/validate_training_samples.py --intent employee_record_set --field active
```

You can repeat `--intent` or `--field` to include more than one value.

### Verbose Output

```bash
python scripts/validate_training_samples.py --verbose
```

Prints `[PASS]` lines for every prompt (not just failures), useful when you want to follow along in real time.

---

## Understanding the Results

Example console output:

```
[FAIL] "Turn Sam Contractor inactive for now": slot 'record_updates' mismatch (expected=[{'field': 'active', 'value': False}], actual=[])

Validation complete: 49/50 passed. Log written to validation_logs/validation_20251110T143012Z.jsonl
```

- The log file is newline-delimited JSON. Each entry includes the text, pass/fail, expected vs. actual intent, and any slot errors.
- Keep the log for auditing or attach it to bug reports.
- Rerun the script after parser changes, model retraining, or training-sample edits to confirm nothing regressed.

---

## Adding New Training Samples

1. Append the new utterance to `training_samples.jsonl` (one JSON object per line).
2. Run the validator:

   ```bash
   python scripts/validate_training_samples.py --verbose
   ```

3. Fix any mismatches the script reports.

Because the validator reads directly from `training_samples.jsonl`, no extra wiring is needed—the new utterance automatically participates in the next run.

---

## Troubleshooting

| Problem | Likely Cause / Fix |
| --- | --- |
| `Training samples file not found` | Double-check the path you passed to `--samples`. |
| `Invalid JSON on line ...` | The JSONL entry is malformed (missing quotes, trailing commas, etc.). |
| `models/intent_slot` missing | Re-download or regenerate the model artifacts before running the script. |
| API mode fails with 401 | Pass the active Flask session cookie via `--cookie "session=..."` or run the script in local mode. |
| Warnings shown for rule/group slots | The parser isn’t emitting those yet; warnings are informational and don’t fail the run. Adjust `OPTIONAL_SLOTS` in the script if you want stricter checks. |

---

## Extending the Validator

Ideas you can layer on later:

- Add `--output junit` to emit JUnit-style XML for CI dashboards.
- Track top-level metrics (overall accuracy, per-intent pass rates).
- Pair the script with an auto-train pipeline so every model build reruns these checks automatically.

If you need help implementing any of those enhancements, just ask!***
