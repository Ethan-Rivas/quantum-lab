# quantum-lab

[![Build](https://github.com/Ethan-Rivas/quantum-lab/actions/workflows/build.yml/badge.svg)](https://github.com/Ethan-Rivas/quantum-lab/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Platforms](https://img.shields.io/badge/platforms-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)

**A quantum computing lab that runs on your own computer.** Qiskit, Cirq and pyQuil in JupyterLab, set up with one command.

[Leer en español](README.es.md)

I built this while studying for my master's degree in quantum computing. The quantum part was the fun part. Getting a local setup to work was not: installing Qiskit with Anaconda kept failing on my Mac, and I couldn't find a ready-made environment that did what I needed, so I ended up on Google Colab. Colab works, but every session starts with reinstalling packages, and it disconnects when you step away. This repo is the setup I wanted instead: the same notebooks, everything already installed, and your files saved on your own machine. I'm sharing it so the next person can skip the setup and get straight to the qubits.

## What you need

[Docker Desktop](https://www.docker.com/products/docker-desktop/) for macOS, Windows or Linux. That's it. Python, Jupyter and the quantum libraries all live inside the containers, so nothing gets installed on your system.

## Quick start

```bash
git clone https://github.com/Ethan-Rivas/quantum-lab.git
cd quantum-lab
docker compose up
```

The first run downloads and builds everything, so give it a few minutes. After that it starts in seconds.

Then open **http://127.0.0.1:8888/lab?token=quantum**, open `00-hello-quantum.ipynb` and run the cells with **Shift + Enter**.

When you're done, press **Ctrl + C** in the terminal, or run `docker compose down`. Your notebooks are saved in the `notebooks/` folder, so nothing is lost when the lab shuts down.

## Your first experiment

The starter notebook builds a **Bell state**, the simplest example of entanglement:

1. A Hadamard gate puts the first qubit in a superposition of 0 and 1.
2. A CNOT gate links the second qubit to the first.
3. Both qubits are measured, 1,000 times.

You'll get `00` about half the time and `11` the other half, and never `01` or `10`. Each qubit on its own is a coin flip, but the two always agree. That's entanglement.

The notebook runs this same circuit in Qiskit, Cirq and pyQuil and plots the results side by side, so you can compare how each framework writes it. It ends with a small example of Grover's search algorithm.

## What's in the lab

| Tool | What it is |
|---|---|
| **Qiskit** + **Aer** | IBM's framework, and the most widely used. Aer is its fast simulator. IBM also lets you run Qiskit circuits on its real quantum computers. |
| **Cirq** | Google's framework. Lower level than Qiskit, and closer to how the hardware is laid out. |
| **pyQuil** + **QVM** + **quilc** | Rigetti's framework. quilc compiles your circuit into the gates a real chip supports, and the QVM simulates it. Each runs in its own container. |
| **JupyterLab** | The same notebook interface Colab is built on, with a file browser, tabs and a terminal. |

## Coming from Colab?

- Download any notebook from Colab (*File → Download → .ipynb*) and drop it into `notebooks/`.
- Remove Colab-only lines such as `from google.colab import drive`.
- Skip the `!pip install qiskit` cells. Everything is already installed.
- There's no GPU, but quantum simulators at learning scale run on the CPU anyway.

## Other ways to run it

**Without the Rigetti servers.** Faster to start. pyQuil uses its built-in Python simulator instead:

```bash
docker compose up --no-deps notebook
```

**VS Code or GitHub Codespaces.** Open the repo in VS Code and choose *Reopen in Container*, or on GitHub click *Code → Codespaces → Create codespace*. Codespaces runs the whole lab in the cloud, which makes it a good Colab replacement when you're not on your own computer.

**Prebuilt image.** Skip the build step and download a ready-made image:

```bash
docker compose -f docker-compose.yml -f docker-compose.prebuilt.yml up
```

That uses `latest`, which is rebuilt every week. To stay on a specific release, change the image in `docker-compose.prebuilt.yml` to a version tag such as `ghcr.io/ethan-rivas/quantum-lab:0.1.0`.

**Without Docker.** If you only need Qiskit and Cirq, [uv](https://docs.astral.sh/uv/) can run the lab directly (`brew install uv` on a Mac):

```bash
uvx -p 3.12 --from jupyter-core --with jupyterlab --with "qiskit[visualization]" \
    --with qiskit-aer --with cirq --with "pyquil<5" jupyter lab
```

pyQuil falls back to its built-in simulator here. Keep the `-p 3.12`, because pyQuil doesn't install on Python 3.13 yet.

## Check that everything works

With the lab running, open a second terminal and run:

```bash
docker compose exec notebook python /opt/quantum-lab/smoke_test.py
```

It runs a Bell state in each framework:

```
PASS  Qiskit + Aer                 {'00': 257, '11': 243}
PASS  Cirq                         {'00': 235, '11': 265}
PASS  pyQuil + quilc + QVM         {'00': 255, '11': 245}

All frameworks working.
```

## Troubleshooting

**The browser asks for a password or token.** Type `quantum`, or open the link above, which includes it.

**The pyQuil cell says "QVM/quilc not available".** The notebook waits up to 30 seconds for Rigetti's servers, then switches to pyQuil's built-in simulator, so you still get results. To find out why the servers didn't answer:

```bash
docker compose ps            # are qvm and quilc running?
docker compose logs quilc    # any errors?
```

On Apple Silicon Macs, the QVM is an x86 program that Docker Desktop has to emulate. If it's slow, turn on *Settings → General → Use Rosetta for x86_64/amd64 emulation on Apple Silicon* in Docker Desktop.

**Port 8888 is already in use.** In `docker-compose.yml`, change `"127.0.0.1:8888:8888"` to `"127.0.0.1:8889:8888"` and use port 8889 in the browser.

## Tips

- **Change the token.** On macOS and Linux run `JUPYTER_TOKEN=yourtoken docker compose up`. In Windows PowerShell run `$env:JUPYTER_TOKEN="yourtoken"; docker compose up`.
- **Add a package.** Add it to `requirements.txt` and run `docker compose build`. For a quick test, `%pip install <package>` in a notebook cell works until the container restarts.
- **pyQuil 5.** Version 5 drops the QVM and quilc in favor of new simulators, so this lab stays on pyQuil 4 for now. The deprecation notices it prints are expected.

## How it stays up to date

Every Monday, GitHub Actions rebuilds the lab with the latest library releases and runs the full test, real Rigetti servers included. If a new release breaks something, the weekly build catches it first. The prebuilt image is only published after the tests pass.

## Roadmap

- [ ] **Drag-and-drop circuit builder.** Add [Quirk](https://github.com/Strilanc/Quirk) to the lab, so you can build circuits visually and offline.
- [ ] **From Quirk to notebook.** A `from_quirk("<link>")` helper that turns a circuit built in Quirk into Qiskit, Cirq and pyQuil code, plus `to_quirk(circuit)` for the other direction.
- [ ] **Desktop app.** Open the lab in its own window with [JupyterLab Desktop](https://github.com/jupyterlab/jupyterlab-desktop) instead of a browser tab.
- [ ] **More notebooks:** Deutsch–Jozsa, quantum teleportation and noise.
- [ ] **Run on a real quantum computer.** A notebook that sends your circuit to one of IBM's quantum processors with a free account, then compares the results with the simulator so you can see what real hardware noise looks like.
- [ ] **PennyLane.** Add Xanadu's framework for quantum machine learning, with its own notebook on training a small quantum circuit.
- [ ] **pyQuil 5**, once its new simulators are stable.

## Contributing

Ideas, bug reports and pull requests are welcome. New notebooks are the most useful contribution, whether that's an algorithm, a framework comparison or a concept explained step by step. Notebooks in Spanish are welcome too. Before opening a pull request, check that the smoke test still passes.

If you try the lab on Windows, Linux or an Intel Mac, I'd like to hear how it went. Open an issue either way.

## License

[MIT](LICENSE)
