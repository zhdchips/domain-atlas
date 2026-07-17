# Intake Evaluation Reports

`scripts/intake_eval.py --live` writes normalized live assessment reports here by default. Reports are intentionally JSON so runs can be compared across model, prompt, and threshold changes. They contain no prompts, raw model responses, provider URLs, credentials, or exception text.

Generated JSON reports are ignored by default. Commit a report only when it is useful as an explicit evaluation baseline; add that baseline deliberately so local runs do not create source churn.
