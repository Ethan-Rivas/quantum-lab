import os

# A website can point its own name at 127.0.0.1 (DNS rebinding) and reach JupyterLab through the
# browser; with the token, that runs code here. Accepting only local Host headers (localhost,
# 127.0.0.1, ::1) blocks it. Codespaces reaches JupyterLab under its own *.app.github.dev name,
# behind GitHub sign-in, so the dev container sets QUANTUM_LAB_ALLOW_REMOTE_ACCESS=1.
c.ServerApp.allow_remote_access = os.environ.get("QUANTUM_LAB_ALLOW_REMOTE_ACCESS") == "1"  # noqa: F821
