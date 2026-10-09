"""Smoke test: build a Bell state in Qiskit, Cirq and pyQuil and check the results.

Run inside the container:   python /opt/quantum-lab/smoke_test.py
Run from the repo:          python tests/smoke_test.py

pyQuil uses the QVM and quilc servers when QCS_SETTINGS_APPLICATIONS_QVM_URL is
set (as docker-compose does), otherwise its built-in pure-Python simulator.
Pass --require-servers to fail instead of falling back (used in CI).
"""

import collections
import os
import sys
import threading
import warnings

SHOTS = 500


def check_bell(name, counts):
    total = sum(counts.values())
    bad = {k: v for k, v in counts.items() if k not in ("00", "11")}
    ok = total == SHOTS and not bad and counts.get("00", 0) > 0 and counts.get("11", 0) > 0
    print(f"{'PASS' if ok else 'FAIL'}  {name:<28} {dict(sorted(counts.items()))}")
    return ok


def run_with_time_limit(fn, seconds):
    """Run fn() but give up after `seconds`.

    pyQuil's quilc version check ignores compiler_timeout, so an unresponsive
    or stopped quilc container would otherwise hang forever.
    """
    out = {}

    def target():
        try:
            out["value"] = fn()
        except BaseException as exc:
            out["error"] = exc

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(seconds)
    if worker.is_alive():
        raise TimeoutError(f"no answer from QVM/quilc within {seconds}s")
    if "error" in out:
        raise out["error"]
    return out["value"]


def test_qiskit():
    from qiskit import QuantumCircuit, transpile
    from qiskit_aer import AerSimulator

    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure_all()
    sim = AerSimulator()
    counts = sim.run(transpile(qc, sim), shots=SHOTS).result().get_counts()
    return check_bell("Qiskit + Aer", counts)


def test_cirq():
    import cirq

    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(cirq.H(q[0]), cirq.CNOT(q[0], q[1]), cirq.measure(*q, key="m"))
    hist = cirq.Simulator(seed=1).run(circuit, repetitions=SHOTS).histogram(key="m")
    counts = {format(k, "02b"): v for k, v in hist.items()}
    return check_bell("Cirq", counts)


def test_pyquil(require_servers):
    warnings.filterwarnings("ignore", message=".*deprecated.*")
    from pyquil import Program, get_qc
    from pyquil.gates import CNOT, H, MEASURE

    def bell():
        p = Program(H(0), CNOT(0, 1))
        ro = p.declare("ro", "BIT", 2)
        p += MEASURE(0, ro[0])
        p += MEASURE(1, ro[1])
        p.wrap_in_numshots_loop(SHOTS)
        return p

    def run(qc, program):
        bits = qc.run(program).get_register_map()["ro"]
        return collections.Counter("".join(str(int(b)) for b in row) for row in bits)

    def on_servers():
        qc = get_qc("2q-qvm", compiler_timeout=20, execution_timeout=20)
        executable = qc.compile(bell())  # exercises quilc
        return run(qc, executable)

    use_servers = require_servers or "QCS_SETTINGS_APPLICATIONS_QVM_URL" in os.environ
    if use_servers:
        try:
            return check_bell("pyQuil + quilc + QVM", run_with_time_limit(on_servers, 30))
        except Exception as exc:
            if require_servers:
                print(f"FAIL  {'pyQuil + quilc + QVM':<28} {type(exc).__name__}: {exc}")
                return False
            print(f"note  QVM/quilc unreachable ({type(exc).__name__}); using PyQVM instead")

    return check_bell("pyQuil + PyQVM (no servers)", run(get_qc("2q-pyqvm"), bell()))


if __name__ == "__main__":
    results = [test_qiskit(), test_cirq(), test_pyquil("--require-servers" in sys.argv)]
    print("\nAll frameworks working." if all(results) else "\nSome checks failed.")
    sys.stdout.flush()
    # Hard exit: a timed-out pyQuil call may still be stuck in a background thread,
    # and a normal interpreter shutdown would abort on it.
    os._exit(0 if all(results) else 1)
