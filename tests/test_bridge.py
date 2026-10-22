"""Tests for the lab bridge's jobs. In the lab image, from the repository root:

    docker compose run --rm -v ./bridge:/opt/bridge -v ./tests:/opt/tests notebook python /opt/tests/test_bridge.py
"""

import sys

sys.path.insert(0, "/opt/bridge")

import numpy as np  # noqa: E402
from qiskit import QuantumCircuit, qasm2  # noqa: E402
from qiskit.quantum_info import Statevector  # noqa: E402
from runner import JobError, import_code, run  # noqa: E402

QASM_HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'


def load(qasm):
    # Qiskit writes p and swap, which Qanvas reads but strict OpenQASM 2.0 parsing doesn't.
    return qasm2.loads(qasm, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)


def same_state(qasm, expected):
    a = Statevector(load(qasm).remove_final_measurements(inplace=False)).data
    b = Statevector(expected).data
    return a.shape == b.shape and np.allclose(a, b, atol=1e-9)


def test_aer_counts_list_q0_first_above_12_qubits():
    # Only q0 is flipped, so a reversed key would put the 1 last.
    counts = run(QASM_HEADER + "qreg q[14];\ncreg c[14];\nx q[0];\nmeasure q -> c;\n", 100)
    assert counts == {"counts": {"1" + "0" * 13: 100}, "measured": list(range(14))}


def test_aer_counts_only_the_measured_qubits():
    counts = run(QASM_HEADER + "qreg q[3];\ncreg c[3];\nx q[2];\nmeasure q[2] -> c[2];\nmeasure q[0] -> c[0];\n", 50)
    assert counts == {"counts": {"01": 50}, "measured": [0, 2]}


def assert_ones_share(answer, p):
    shots = sum(answer["counts"].values())
    share = answer["counts"].get("1", 0) / shots
    assert abs(share - p) < 3 * (p * (1 - p) / shots) ** 0.5, share


def test_swap_gets_one_two_qubit_error():
    qasm = QASM_HEADER + "gate swap a,b { cx a,b; cx b,a; cx a,b; }\nqreg q[2];\ncreg c[2];\nx q[0];\nswap q[0],q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];\n"
    assert_ones_share(run(qasm, 4000, {"oneQubit": 0, "twoQubit": 0.1, "readout": 0}, [1]), 0.95)


def test_readout_error_reaches_a_condition():
    qasm = QASM_HEADER + "qreg q[2];\ncreg c0[1];\ncreg c1[1];\nx q[0];\nmeasure q[0] -> c0[0];\nif(c0==1) x q[1];\nmeasure q[1] -> c1[0];\n"
    assert_ones_share(run(qasm, 4000, {"oneQubit": 0, "twoQubit": 0, "readout": 0.2}, [1]), 0.8 * 0.8 + 0.2 * 0.2)


def test_counted_qubit_is_read_after_its_last_gate():
    qasm = QASM_HEADER + "qreg q[1];\ncreg c[1];\nh q[0];\nmeasure q[0] -> c[0];\nreset q[0];\nx q[0];\n"
    assert run(qasm, 200, measured=[0]) == {"counts": {"1": 200}, "measured": [0]}


def test_noisy_cirq_export_imports_without_noise():
    noisy = (
        "import cirq\nimport numpy as np\nq = cirq.LineQubit.range(2)\n"
        "one_qubit_noise = cirq.depolarize(3 / 4 * 0.01)\ntwo_qubit_noise = cirq.depolarize(15 / 16 * 0.02, n_qubits=2)\n"
        "readout = 0.05\nconfusion = {(0,): np.array([[1 - readout, readout], [readout, 1 - readout]])}\n"
        "circuit = cirq.Circuit(\n"
        "    cirq.Moment(cirq.H(q[0])),\n    cirq.Moment(one_qubit_noise.on(q[0])),\n"
        "    cirq.Moment(cirq.CNOT(q[0], q[1])),\n    cirq.Moment(two_qubit_noise.on(q[0], q[1])),\n"
        '    cirq.Moment(cirq.measure(q[0], key="q0", confusion_map=confusion), cirq.measure(q[1], key="q1", confusion_map=confusion)),\n'
        ")\n"
    )
    plain = 'import cirq\nq = cirq.LineQubit.range(2)\ncircuit = cirq.Circuit(cirq.H(q[0]), cirq.CNOT(q[0], q[1]), cirq.measure(q[0], key="q0"), cirq.measure(q[1], key="q1"))\n'
    assert import_code("cirq", noisy) == import_code("cirq", plain)


def test_code_with_loops_imports_in_every_framework():
    expected = QuantumCircuit(3)
    for q in range(3):
        expected.h(q)
    expected.cx(0, 2)
    expected.p(0.3, 1)
    snippets = {
        "qiskit": "from qiskit import QuantumCircuit\nqc = QuantumCircuit(3)\nfor q in range(3):\n    qc.h(q)\nqc.cx(0, 2)\nqc.p(0.3, 1)\n",
        "cirq": "import cirq\nq = cirq.LineQubit.range(3)\ncircuit = cirq.Circuit(cirq.H(x) for x in q)\ncircuit.append(cirq.CNOT(q[0], q[2]))\ncircuit.append(cirq.ZPowGate(exponent=0.3 / 3.141592653589793)(q[1]))\n",
        "pyquil": "from pyquil import Program\nfrom pyquil.gates import CNOT, H, PHASE\nprogram = Program()\nfor q in range(3):\n    program += H(q)\nprogram += CNOT(0, 2)\nprogram += PHASE(0.3, 1)\n",
    }
    for language, code in snippets.items():
        qasm = import_code(language, code)["qasm"]
        # Cirq's ZPowGate and Qiskit's p differ by a global phase, which no measurement sees.
        a = Statevector(load(qasm)).data
        b = Statevector(expected).data
        assert abs(abs(np.vdot(a, b)) - 1) < 1e-9, language


def test_unused_low_qubits_keep_their_numbers():
    qasm = import_code("cirq", "import cirq\ncircuit = cirq.Circuit(cirq.X(cirq.LineQubit(2)))\n")["qasm"]
    expected = QuantumCircuit(3)
    expected.x(2)
    assert same_state(qasm, expected)
    qasm = import_code("pyquil", "from pyquil import Program\nfrom pyquil.gates import X\nprogram = Program(X(2))\n")["qasm"]
    assert same_state(qasm, expected)


def test_gates_qanvas_lacks_are_rewritten_and_dagger_is_kept():
    qasm = import_code("pyquil", "from pyquil import Program\nfrom pyquil.gates import H, S\nprogram = Program(H(0), S(0).dagger(), H(0))\n")["qasm"]
    assert "sdg" in qasm
    qasm = import_code("qiskit", "from qiskit import QuantumCircuit\nqc = QuantumCircuit(2)\nqc.sx(0)\nqc.cp(0.5, 0, 1)\nqc.barrier()\n")["qasm"]
    assert "sx" not in qasm and "cp" not in qasm and "barrier" not in qasm


def test_errors_say_what_and_where():
    for code, expected in [
        ("from qiskit import QuantumCircuit\nqc = QuantumCircuit(2)\nqc.h(5)\n", {"code": "python", "line": 3}),
        ("x = (\n", {"code": "python", "line": 1}),
        ("x = 1\n", {"code": "no-circuit"}),
        ("from qiskit import QuantumCircuit\nqc = QuantumCircuit(25)\n", {"code": "too-many-qubits", "detail": "25"}),
    ]:
        try:
            import_code("qiskit", code)
        except JobError as error:
            assert {k: error.answer[k] for k in expected} == expected, (code, error.answer)
        else:
            raise AssertionError(f"no error for {code!r}")


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS  {test.__name__}")
    print(f"\n{len(tests)} bridge tests passed.")
