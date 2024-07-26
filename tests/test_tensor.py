from __future__ import annotations

import random

import pytest
import torch
from helpers import calc_mat_vec_wavefunction, get_op_support, random_pauli_hamiltonian

from pyqtorch.analog import Add, GeneratorType, HamiltonianEvolution, Scale
from pyqtorch.circuit import Sequence
from pyqtorch.parametric import OPS_PARAM, Parametric
from pyqtorch.primitive import (
    CNOT,
    OPS_DIGITAL,
    SWAP,
    N,
    Primitive,
    Projector,
)
from pyqtorch.utils import (
    ATOL,
    RTOL,
    random_state,
)

pi = torch.tensor(torch.pi)


@pytest.mark.parametrize("use_full_support", [True, False])
@pytest.mark.parametrize("n_qubits", [4, 5])
@pytest.mark.parametrize("batch_size", [1, 5])
def test_digital_tensor(n_qubits: int, batch_size: int, use_full_support: bool) -> None:
    """
    Goes through all non-parametric gates and tests their application to a random state
    in comparison with the `tensor` method, either using just the qubit support of the gate
    or expanding its matrix to the maximum qubit support of the full circuit.
    """
    op: type[Primitive]
    for op in OPS_DIGITAL:
        supp = get_op_support(op, n_qubits)
        op_concrete = op(*supp)
        psi_init = random_state(n_qubits, batch_size)
        psi_star = op_concrete(psi_init)
        full_support = tuple(range(n_qubits)) if use_full_support else None
        psi_expected = calc_mat_vec_wavefunction(
            op_concrete, psi_init, full_support=full_support
        )
        assert torch.allclose(psi_star, psi_expected, rtol=RTOL, atol=ATOL)


@pytest.mark.parametrize("use_full_support", [True, False])
@pytest.mark.parametrize("n_qubits", [4, 5])
@pytest.mark.parametrize("batch_size", [1, 5])
def test_param_tensor(n_qubits: int, batch_size: int, use_full_support: bool) -> None:
    """
    Goes through all parametric gates and tests their application to a random state
    in comparison with the `tensor` method, either using just the qubit support of the gate
    or expanding its matrix to the maximum qubit support of the full circuit.
    """
    op: type[Parametric]
    for op in OPS_PARAM:
        supp = get_op_support(op, n_qubits)
        params = [f"th{i}" for i in range(op.n_params)]
        op_concrete = op(*supp, *params)
        psi_init = random_state(n_qubits)
        values = {param: torch.rand(batch_size) for param in params}
        psi_star = op_concrete(psi_init, values)
        full_support = tuple(range(n_qubits)) if use_full_support else None
        psi_expected = calc_mat_vec_wavefunction(
            op_concrete, psi_init, values=values, full_support=full_support
        )
        assert torch.allclose(psi_star, psi_expected, rtol=RTOL, atol=ATOL)


@pytest.mark.parametrize("use_full_support", [True, False])
@pytest.mark.parametrize("n_qubits", [4, 5])
@pytest.mark.parametrize("batch_size", [1, 5])
@pytest.mark.parametrize("compose", [Sequence, Add])
def test_sequence_tensor(
    n_qubits: int,
    batch_size: int,
    use_full_support: bool,
    compose: type[Sequence] | type[Add],
) -> None:
    op_list = []
    values = {}
    op: type[Primitive] | type[Parametric]
    """
    Builds a Sequence or Add composition of all possible gates on random qubit
    supports. Also assigns a Scale of a random value to the non-parametric gates.
    Tests the forward method (which goes through each gate individually) to the
    `tensor` method, which builds the full operator matrix and applies it.
    """
    for op in OPS_DIGITAL:
        supp = get_op_support(op, n_qubits)
        op_concrete = Scale(op(*supp), torch.rand(1))
        op_list.append(op_concrete)
    for op in OPS_PARAM:
        supp = get_op_support(op, n_qubits)
        params = [f"{op.__name__}_th{i}" for i in range(op.n_params)]
        values.update({param: torch.rand(batch_size) for param in params})
        op_concrete = op(*supp, *params)
        op_list.append(op_concrete)
    random.shuffle(op_list)
    op_composite = compose(op_list)
    psi_init = random_state(n_qubits, batch_size)
    psi_star = op_composite(psi_init, values)
    full_support = tuple(range(n_qubits)) if use_full_support else None
    psi_expected = calc_mat_vec_wavefunction(
        op_composite, psi_init, values=values, full_support=full_support
    )
    assert torch.allclose(psi_star, psi_expected, rtol=RTOL, atol=ATOL)


@pytest.mark.parametrize("use_full_support", [True, False])
@pytest.mark.parametrize("n_qubits", [4, 5])
@pytest.mark.parametrize("n_proj", [1, 3])
@pytest.mark.parametrize("batch_size", [1, 5])
def test_projector_tensor(
    n_qubits: int, n_proj: int, batch_size: int, use_full_support: bool
) -> None:
    """
    Instantiates various random projectors on arbitrary qubit support
    and compares the forward method with directly applying the tensor.
    """
    iterations = 5
    for _ in range(iterations):
        rand_int_1 = random.randint(0, 2**n_proj - 1)
        rand_int_2 = random.randint(0, 2**n_proj - 1)
        bitstring1 = "{0:b}".format(rand_int_1).zfill(n_proj)
        bitstring2 = "{0:b}".format(rand_int_2).zfill(n_proj)
        supp = tuple(random.sample(range(n_qubits), n_proj))
        op = Projector(supp, bitstring1, bitstring2)
        psi_init = random_state(n_qubits, batch_size)
        psi_star = op(psi_init)
        full_support = tuple(range(n_qubits)) if use_full_support else None
        psi_expected = calc_mat_vec_wavefunction(
            op, psi_init, full_support=full_support
        )
        assert torch.allclose(psi_star, psi_expected, rtol=RTOL, atol=ATOL)


@pytest.mark.parametrize("n_qubits", [4, 5])
@pytest.mark.parametrize("operator", [N, CNOT, SWAP])
@pytest.mark.parametrize("use_full_support", [True, False])
def test_projector_vs_operator(
    n_qubits: int,
    operator: type[Primitive],
    use_full_support: bool,
) -> None:
    if operator == N:
        supp: tuple = (random.randint(0, n_qubits - 1),)
        op_concrete = N(*supp)
        projector = Projector(supp, "1", "1")
    if operator == CNOT:
        supp = tuple(random.sample(range(n_qubits), 2))
        op_concrete = CNOT(*supp)
        projector = Add(
            [
                Projector(supp, "00", "00"),
                Projector(supp, "01", "01"),
                Projector(supp, "10", "11"),
                Projector(supp, "11", "10"),
            ]
        )
    if operator == SWAP:
        supp = tuple(random.sample(range(n_qubits), 2))
        op_concrete = SWAP(*supp)
        projector = Add(
            [
                Projector(supp, "00", "00"),
                Projector(supp, "01", "10"),
                Projector(supp, "10", "01"),
                Projector(supp, "11", "11"),
            ]
        )
    full_support = tuple(range(n_qubits)) if use_full_support else None
    projector_mat = projector.tensor(full_support=full_support)
    operator_mat = op_concrete.tensor(full_support=full_support)
    assert torch.allclose(projector_mat, operator_mat, rtol=RTOL, atol=ATOL)


@pytest.mark.parametrize("n_qubits", [4, 5])
@pytest.mark.parametrize("make_param", [True, False])
@pytest.mark.parametrize("use_full_support", [True, False])
@pytest.mark.parametrize("batch_size", [1, 5])
def test_hevo_pauli_tensor(
    n_qubits: int, make_param: bool, use_full_support: bool, batch_size: int
) -> None:
    k_1q = 2 * n_qubits  # Number of 1-qubit terms
    k_2q = n_qubits**2  # Number of 2-qubit terms
    generator, param_list = random_pauli_hamiltonian(n_qubits, k_1q, k_2q, make_param)
    values = {param: torch.rand(batch_size) for param in param_list}
    psi_init = random_state(n_qubits, batch_size)
    full_support = tuple(range(n_qubits)) if use_full_support else None
    # Test the generator itself
    psi_star = generator(psi_init, values)
    psi_expected = calc_mat_vec_wavefunction(generator, psi_init, values, full_support)
    assert torch.allclose(psi_star, psi_expected, rtol=RTOL, atol=ATOL)
    # Test the hamiltonian evolution
    tparam = "t"
    operator = HamiltonianEvolution(generator, tparam, generator_parametric=make_param)
    if make_param:
        assert operator.generator_type == GeneratorType.PARAMETRIC_OPERATION
    else:
        assert operator.generator_type == GeneratorType.OPERATION
    values[tparam] = torch.rand(batch_size)
    psi_star = operator(psi_init, values)
    psi_expected = calc_mat_vec_wavefunction(operator, psi_init, values, full_support)
    assert torch.allclose(psi_star, psi_expected, rtol=RTOL, atol=ATOL)


@pytest.mark.parametrize("gen_qubits", [3, 4])
@pytest.mark.parametrize("n_qubits", [4, 5])
@pytest.mark.parametrize("use_full_support", [True, False])
@pytest.mark.parametrize("batch_size", [1, 5])
def test_hevo_tensor_tensor(
    gen_qubits: int, n_qubits: int, use_full_support: bool, batch_size: int
) -> None:
    k_1q = 2 * gen_qubits  # Number of 1-qubit terms
    k_2q = gen_qubits**2  # Number of 2-qubit terms
    generator, _ = random_pauli_hamiltonian(gen_qubits, k_1q, k_2q)
    psi_init = random_state(n_qubits, batch_size)
    full_support = tuple(range(n_qubits)) if use_full_support else None
    # Test the hamiltonian evolution
    generator_matrix = generator.tensor()
    supp = tuple(random.sample(range(n_qubits), gen_qubits))
    tparam = "t"
    operator = HamiltonianEvolution(generator_matrix, tparam, supp)
    assert operator.generator_type == GeneratorType.TENSOR
    values = {tparam: torch.rand(batch_size)}
    psi_star = operator(psi_init, values)
    psi_expected = calc_mat_vec_wavefunction(operator, psi_init, values, full_support)
    assert torch.allclose(psi_star, psi_expected, rtol=RTOL, atol=ATOL)
