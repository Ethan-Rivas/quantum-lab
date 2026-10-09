# quantum-lab

**Qiskit, Cirq and pyQuil in a local JupyterLab, with one command.** No Anaconda and no dependency wrangling. Runs natively on Apple Silicon.

```bash
git clone https://github.com/<your-username>/quantum-lab.git
cd quantum-lab
docker compose up
```

Then open **http://127.0.0.1:8888/lab?token=quantum** and start with `00-hello-quantum.ipynb`.

![Build](https://github.com/<your-username>/quantum-lab/actions/workflows/build.yml/badge.svg)

---

## What's inside

| | |
|---|---|
| **Qiskit 2.x** + **Aer** simulator | IBM, with circuit drawing and histograms |
| **Cirq 1.x** | Google |
| **pyQuil 4.x** + **QVM** + **quilc** | Rigetti's simulator and compiler, each in its own container |
| **JupyterLab 4** | Python 3.12 |
| **Starter notebook** | A Bell state in all three frameworks side by side, plus Grover's search |

Notebooks live in `./notebooks` on your machine, so your work survives container restarts and rebuilds.

## Four ways to run it

### 1. Docker Compose (everything, recommended)

```bash
docker compose up        # first run builds the image, takes a few minutes
docker compose down      # stop everything
```

To skip the Rigetti servers (pyQuil then uses its built-in Python simulator):

```bash
docker compose up --no-deps notebook
```

### 2. Prebuilt image (no build step)

Every push to `main`, plus a weekly rebuild, publishes a multi-arch image to GitHub Container Registry:

```bash
docker compose -f docker-compose.yml -f docker-compose.prebuilt.yml up
```

(Set your username in `docker-compose.prebuilt.yml` first.)

Tags: `latest`, a date tag such as `2026-10-08`, and the commit SHA. Pin a date tag if you need a notebook to keep working exactly as it does today.

### 3. VS Code or GitHub Codespaces

Open the repo in VS Code and choose **Reopen in Container**, or click **Code → Codespaces → Create codespace** on GitHub. You get the same environment, QVM and quilc included, and the smoke test runs when it attaches. Codespaces works as a cloud alternative to Colab.

### 4. No Docker at all

With [uv](https://docs.astral.sh/uv/) installed (`brew install uv`):

```bash
uvx -p 3.12 --from jupyter-core --with jupyterlab --with "qiskit[visualization]" \
    --with qiskit-aer --with cirq --with "pyquil<5" jupyter lab
```

Qiskit and Cirq work fully. pyQuil falls back to its built-in simulator, since QVM and quilc aren't running. The `-p 3.12` matters: pyQuil's dependencies don't install on Python 3.13 yet.

## Check that it works

```bash
docker compose run --rm notebook python /opt/quantum-lab/smoke_test.py
```

```
PASS  Qiskit + Aer                 {'00': 252, '11': 248}
PASS  Cirq                         {'00': 235, '11': 265}
PASS  pyQuil + quilc + QVM         {'00': 251, '11': 249}

All frameworks working.
```

## Notes

**Apple Silicon.** The notebook image is native arm64. Rigetti only publishes `qvm` and `quilc` for x86, so Docker Desktop emulates those two. That's fine for learning-size circuits. If they're slow or crash, enable *Settings → General → Use Rosetta for x86/amd64 emulation* in Docker Desktop.

**Jupyter token.** The default token is `quantum` and the port is bound to `127.0.0.1` only. To change the token: `JUPYTER_TOKEN=something docker compose up`.

**pyQuil 5.** pyQuil 4.22 deprecated the QVM, PyQVM and quilc, and pyQuil 5 removes them in favor of new simulators. `requirements.txt` pins `pyquil<5` so this lab keeps working; you'll see deprecation notices, which the notebook silences.

**"pull access denied for quantum-lab"?** You have an older copy of `docker-compose.yml` that lets Docker look for the image on Docker Hub. Update to the latest version, or run `docker compose up --build`.

**Port 8888 already in use?** Change the left side of the port mapping in `docker-compose.yml`, for example `"127.0.0.1:8889:8888"`.

**Adding packages.** Add them to `requirements.txt` and run `docker compose build`. For a quick experiment, `%pip install <package>` in a notebook cell works until the container is recreated.

## How it stays current

The [workflow](.github/workflows/build.yml) builds the image, starts QVM and quilc, runs the smoke test against the real servers, and executes the starter notebook. It runs on every push and PR, and **every Monday** it picks up new library releases. If an upstream release breaks something, the weekly run fails before anyone else hits it. Only after the tests pass does it publish the amd64 and arm64 images.

## Roadmap

- [ ] **Visual circuit builder.** Add [Quirk](https://github.com/Strilanc/Quirk), an open-source drag-and-drop simulator, as a fourth compose service so it runs offline alongside JupyterLab.
- [ ] **Quirk ⇄ notebook bridge.** A `from_quirk("<link>")` helper that turns a Quirk circuit into Qiskit, Cirq and pyQuil circuits, plus `to_quirk(circuit)` for the reverse. The plumbing already works through Cirq and OpenQASM (`cirq.quirk_url_to_circuit` → `cirq.qasm` → `qiskit.qasm2.loads`).
- [ ] **Desktop app experience.** Document using [JupyterLab Desktop](https://github.com/jupyterlab/jupyterlab-desktop) with the container, or a small launcher that starts everything and opens both tools in one window.
- [ ] **More tutorial notebooks:** Deutsch–Jozsa, quantum teleportation, noise models, and running on real IBM hardware.
- [ ] **pyQuil 5 migration** to its new built-in simulators, once they're stable.

## Contributing

Ideas and PRs welcome. New tutorial notebooks are especially useful (algorithms, noise models, framework comparisons). Please make sure `smoke_test.py` still passes.

## License

[MIT](LICENSE)
