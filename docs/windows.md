# Windows / PowerShell guidelines

This project is developed and tested primarily on Windows using PowerShell. A
few notes to keep examples consistent and avoid confusion:

- Use PowerShell commands in documentation and examples. For example, use
  `python .\script.py` or `python -m dupdetector.cli` rather than Bash-like
  `./script.py` run syntax.
- Use backslashes for Windows paths in examples (e.g., `Z:\Photos\2025`).
- When showing multi-line Python snippets in PowerShell, prefer here-strings and
  piping to python, for example:

```powershell
@'
print("hello from stdin python")
'@ | python -
```

- If you paste a Bash heredoc (e.g. `python - <<'PY'`), indicate that you want a
  PowerShell-compatible variant; by default maintainers will provide PowerShell
  equivalents.

- If running scripts that import the local package, make sure to set `PYTHONPATH`
  to the project's `src` directory in the example, e.g.:

```powershell
$env:PYTHONPATH = 'Z:\tools\duplicate-detector\DupDetector\src'
python .\scripts\run_scan_persist.py --config '.\config.json'
```

If you want this policy enforced programmatically (for example linting docs for
shell hints), say so and I can add a simple doc checker script in `scripts/`.
