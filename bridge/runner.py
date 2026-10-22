"""One job for the lab bridge, run in its own process so the bridge can stop it at a time limit.

Reads a JSON job on stdin and writes a JSON answer on stdout:

    {"task": "run", "qasm": "...", "shots": 1000}
        -> {"counts": {"0110": 512, ...}, "measured": [0, 1, 2, 3]}
    {"task": "run", "qasm": "...", "shots": 1000, "noise": {"oneQubit": 0.01, "twoQubit": 0.02, "readout": 0.05},
     "measured": [0, 3]}
        -> {"counts": {"01": 512, ...}, "measured": [0, 3]}
    {"task": "import", "language": "qiskit" | "cirq" | "pyquil", "code": "..."}
        -> {"qasm": "OPENQASM 2.0; ..."}

Errors answer {"error": {"code": "...", "detail": "...", "line": n}}.
"""

import contextlib
import io
import json
import sys
import traceback
import warnings

warnings.filterwarnings("ignore")

MAX_QUBITS = 24
# The gates Qanvas has; anything else is rewritten into these by Qiskit's transpiler.
QANVAS_GATES = ["h", "x", "y", "z", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "p", "cx", "cz", "swap", "ccx", "measure"]
# The same noise model as Qanvas's Qiskit export (src/code/qiskit.ts). Qanvas's OpenQASM writes P as u1.
ONE_QUBIT_GATES = ["h", "x", "y", "z", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "p", "u1"]


class JobError(Exception):
    def __init__(self, code, detail=None, line=None):
        super().__init__(code)
        self.answer = {"code": code, **({"detail": str(detail)} if detail is not None else {}), **({"line": line} if line else {})}


def noise_model(noise):
    from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error

    model = NoiseModel()
    p1, p2, r = noise["oneQubit"], noise["twoQubit"], noise["readout"]
    if p1 > 0:
        model.add_all_qubit_quantum_error(depolarizing_error(p1, 1), ONE_QUBIT_GATES)
    if p2 > 0:
        model.add_all_qubit_quantum_error(depolarizing_error(p2, 2), ["cx", "cz", "swap"])
        model.add_all_qubit_quantum_error(depolarizing_error(p2, 3), ["ccx"])
    if r > 0:
        model.add_all_qubit_readout_error(ReadoutError([[1 - r, r], [r, 1 - r]]))
    return model


def final_measurements(qc, measured):
    """The classical bit holding each qubit's final measurement, measuring at the end the qubits that lack one."""
    from qiskit import ClassicalRegister

    if not measured or len(set(measured)) != len(measured) or not all(0 <= q < qc.num_qubits for q in measured):
        raise JobError("bad-request")
    last = {}
    for instruction in qc.data:
        for qubit in instruction.qubits:
            last[qc.find_bit(qubit).index] = instruction
    clbit_of = {}
    for q in measured:
        if q in last and last[q].operation.name == "measure":
            clbit_of[q] = qc.find_bit(last[q].clbits[0]).index
        else:
            register = ClassicalRegister(1, f"counted{q}")
            qc.add_register(register)
            qc.measure(q, register[0])
            clbit_of[q] = qc.find_bit(register[0]).index
    return clbit_of


def run(qasm, shots, noise=None, measured=None):
    from qiskit import qasm2, transpile
    from qiskit_aer import AerSimulator

    # Plain loads keeps Qanvas's swap one instruction, so it gets one 2-qubit error rather than three.
    qc = qasm2.loads(qasm)
    if qc.num_qubits > MAX_QUBITS:
        raise JobError("too-many-qubits", qc.num_qubits)
    if measured is not None:
        clbit_of = final_measurements(qc, measured)
    else:
        clbit_of = {}
        for instruction in qc.data:
            if instruction.operation.name == "measure":
                clbit_of[qc.find_bit(instruction.qubits[0]).index] = qc.find_bit(instruction.clbits[0]).index
        if not clbit_of:
            qc.measure_all()
            clbit_of = {q: q for q in range(qc.num_qubits)}
        measured = sorted(clbit_of)

    simulator = AerSimulator()
    if noise is None:
        counts = simulator.run(transpile(qc, simulator), shots=shots).result().get_counts()
    else:
        # Optimizing could merge or rewrite Qanvas's gates, and each must get its error exactly once.
        circuit = transpile(qc, simulator, optimization_level=0)
        counts = simulator.run(circuit, shots=shots, noise_model=noise_model(noise)).result().get_counts()
    # Bit order: Qiskit writes classical bit 0 last (rightmost), with a space between registers.
    # Qanvas lists the measured qubits with q0 first, so each key is rebuilt in that order.
    result = {}
    for key, n in counts.items():
        bits = key.replace(" ", "")
        ordered = "".join(bits[len(bits) - 1 - clbit_of[q]] for q in measured)
        result[ordered] = result.get(ordered, 0) + n
    return {"counts": result, "measured": measured}


def find(namespace, kind, preferred):
    if isinstance(namespace.get(preferred), kind):
        return namespace[preferred]
    found = [value for value in namespace.values() if isinstance(value, kind)]
    if not found:
        raise JobError("no-circuit")
    return found[-1]


def from_qiskit(namespace):
    from qiskit import QuantumCircuit

    return find(namespace, QuantumCircuit, "qc")


def without_noise(circuit):
    """The circuit without the depolarizing channels and readout errors of Qanvas's noisy Cirq export."""
    import cirq

    def plain(op):
        gate = op.without_classical_controls().gate if isinstance(op, cirq.ClassicallyControlledOperation) else op.gate
        if isinstance(gate, cirq.DepolarizingChannel):
            return None
        if isinstance(gate, cirq.MeasurementGate) and gate.confusion_map:
            return cirq.measure(*op.qubits, key=gate.mkey, invert_mask=gate.invert_mask)
        return op

    return cirq.Circuit(cirq.Moment(op for op in map(plain, moment) if op is not None) for moment in circuit)


def from_cirq(namespace):
    import cirq
    from qiskit import qasm2

    circuit = without_noise(find(namespace, cirq.Circuit, "circuit"))
    qubits = sorted(circuit.all_qubits())
    if all(isinstance(q, cirq.LineQubit) for q in qubits):
        # LineQubit(k) is qubit k even when lower qubits have no gates, so they're kept.
        qubits = cirq.LineQubit.range(max((q.x for q in qubits), default=-1) + 1)
    return qasm2.loads(circuit.to_qasm(qubit_order=qubits), custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)


def from_pyquil(namespace):
    from pyquil import Program
    from pyquil.quilbase import Declare, Gate, Measurement, Pragma
    from qiskit import QuantumCircuit
    from qiskit.circuit import library

    gates = {
        "I": library.IGate, "H": library.HGate, "X": library.XGate, "Y": library.YGate, "Z": library.ZGate,
        "S": library.SGate, "T": library.TGate, "RX": library.RXGate, "RY": library.RYGate, "RZ": library.RZGate,
        "PHASE": library.PhaseGate, "CNOT": library.CXGate, "CZ": library.CZGate, "SWAP": library.SwapGate,
        "CCNOT": library.CCXGate, "CPHASE": library.CPhaseGate, "ISWAP": library.iSwapGate, "CSWAP": library.CSwapGate,
    }
    program = find(namespace, Program, "program")
    instructions = [i for i in program.instructions if not isinstance(i, (Declare, Pragma))]
    indices = [q.index for i in instructions for q in (i.qubits if isinstance(i, Gate) else [i.qubit] if isinstance(i, Measurement) else [])]
    qubits = max(indices, default=-1) + 1
    if qubits > MAX_QUBITS:
        raise JobError("too-many-qubits", qubits)
    qc = QuantumCircuit(qubits, qubits)
    for instruction in instructions:
        if isinstance(instruction, Measurement):
            qc.measure(instruction.qubit.index, instruction.qubit.index)
            continue
        if not isinstance(instruction, Gate) or instruction.name not in gates:
            raise JobError("unsupported", getattr(instruction, "name", type(instruction).__name__))
        # pyQuil keeps angles as complex numbers (0.3+0j); a symbolic or memory parameter can't be drawn.
        if not all(isinstance(p, (int, float, complex)) and abs(complex(p).imag) < 1e-12 for p in instruction.params):
            raise JobError("unsupported", f"{instruction.name}({', '.join(map(str, instruction.params))})")
        gate = gates[instruction.name](*[complex(p).real for p in instruction.params])
        controls = 0
        for modifier in instruction.modifiers:
            if modifier == "DAGGER":
                gate = gate.inverse()
            elif modifier == "CONTROLLED":
                controls += 1
            else:
                raise JobError("unsupported", modifier)
        if controls:
            gate = gate.control(controls)
        qc.append(gate, [q.index for q in instruction.qubits])
    return qc


def to_qanvas(qc):
    from qiskit import qasm2, transpile

    if qc.num_qubits > MAX_QUBITS:
        raise JobError("too-many-qubits", qc.num_qubits)
    kept = qc.copy_empty_like()
    for instruction in qc.data:
        if instruction.operation.name not in ("barrier", "id", "delay"):
            kept.append(instruction)
    # Without a device to fit, level 0 keeps every qubit where it is and only rewrites gates Qanvas lacks.
    return qasm2.dumps(transpile(kept, basis_gates=QANVAS_GATES, optimization_level=0))


def import_code(language, code):
    readers = {"qiskit": from_qiskit, "cirq": from_cirq, "pyquil": from_pyquil}
    if language not in readers:
        raise JobError("unsupported", language)
    namespace = {"__name__": "__main__"}
    try:
        # What the code prints is dropped: stdout carries this job's answer.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            exec(compile(code, "<code>", "exec"), namespace)
    except SyntaxError as error:
        raise JobError("python", f"SyntaxError: {error.msg}", error.lineno if error.filename == "<code>" else None)
    except Exception as error:
        lines = [frame.lineno for frame in traceback.extract_tb(error.__traceback__) if frame.filename == "<code>"]
        raise JobError("python", f"{type(error).__name__}: {error}", lines[-1] if lines else None)
    return {"qasm": to_qanvas(readers[language](namespace))}


def main():
    job = json.loads(sys.stdin.read())
    try:
        answer = run(job["qasm"], job["shots"], job.get("noise"), job.get("measured")) if job["task"] == "run" else import_code(job["language"], job["code"])
    except JobError as error:
        answer = {"error": error.answer}
    except Exception as error:
        answer = {"error": {"code": "failed", "detail": f"{type(error).__name__}: {error}"}}
    sys.stdout.write(json.dumps(answer))


if __name__ == "__main__":
    main()
