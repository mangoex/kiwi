# Python 3.12 installation inputs

Use `python scripts/install_python_runtime.py --dev` inside an empty Python 3.12 environment.
The installer selects Windows or Linux, checks the canonical dependency input digest, verifies
every external distribution hash, installs local API/gateway packages without resolving again,
and runs `pip check`. Runtime images use the Linux API lock. Windows runtime includes gateway.

Regenerate explicitly after a manifest change, using an isolated tooling environment:

```text
python -m pip install uv==0.12.24
uv --version
python scripts/compile_python_locks.py
```

The compiler rejects any other uv version. It reads canonical API/gateway manifests, excludes
the local API package from PyPI resolution and freezes setuptools as the editable build backend.
Commit all affected target locks and verify clean installations; regeneration is not an automatic
runtime fallback. Existing unlocked development requirements are legacy inputs, not the CI/image
installation authority.
