from __future__ import annotations

import pytest
import torch

import pyqtorch as pyq
from pyqtorch.utils import is_normalized, overlap

pi = torch.tensor(torch.pi, dtype=torch.cdouble)


def Hamiltonian(batch_size: int = 1) -> torch.Tensor:
    sigmaz = torch.diag(torch.tensor([1.0, -1.0], dtype=torch.cdouble))
    Hbase = torch.kron(sigmaz, sigmaz)
    H = torch.kron(Hbase, Hbase)
    if batch_size == 1:
        return H
    elif batch_size == 2:
        return torch.stack((H, H.conj()), dim=2)
    else:
        raise NotImplementedError


def Hamiltonian_general(n_qubits: int = 2, batch_size: int = 1) -> torch.Tensor:
    H_batch = torch.zeros((2**n_qubits, 2**n_qubits, batch_size), dtype=torch.cdouble)
    for i in range(batch_size):
        H_0 = torch.randn((2**n_qubits, 2**n_qubits), dtype=torch.cdouble)
        H = (H_0 + torch.conj(H_0.transpose(0, 1))).cdouble()
        H_batch[..., i] = H
    return H_batch


def Hamiltonian_diag(n_qubits: int = 2, batch_size: int = 1) -> torch.Tensor:
    H_batch = torch.zeros((2**n_qubits, 2**n_qubits, batch_size), dtype=torch.cdouble)
    for i in range(batch_size):
        H_0 = torch.randn((2**n_qubits, 2**n_qubits), dtype=torch.cdouble)
        H = (H_0 + torch.conj(H_0.transpose(0, 1))).cdouble()
        get_diag = torch.diag(H)
        H_diag = torch.diag(get_diag)
        H_batch[..., i] = H_diag
    return H_batch


@pytest.mark.parametrize("n_qubits, batch_size", [(2, 1), (4, 2)])
def test_hamevo_general(n_qubits: int, batch_size: int) -> None:
    H = Hamiltonian_general(n_qubits, batch_size)
    t_evo = torch.rand(1, dtype=torch.float64)
    hamevo = pyq.HamiltonianEvolution(tuple([i for i in range(n_qubits)]), n_qubits)
    psi = pyq.random_state(n_qubits, batch_size)
    psi_star = hamevo(H, t_evo, psi)
    assert is_normalized(psi_star)


def test_hamevo_single() -> None:
    n_qubits = 4
    H = Hamiltonian(1)
    t_evo = torch.tensor([torch.pi / 4], dtype=torch.cdouble)
    hamevo = pyq.HamiltonianEvolution(tuple([i for i in range(n_qubits)]), n_qubits)
    psi = pyq.uniform_state(n_qubits)
    psi_star = hamevo(H, t_evo, psi)
    result = overlap(psi_star, psi)
    assert torch.isclose(result, torch.tensor([0.5]))


def test_hamevo_batch() -> None:
    n_qubits = 4
    batch_size = 2
    H = Hamiltonian(batch_size)
    t_evo = torch.tensor([torch.pi / 4], dtype=torch.cdouble)
    hamevo = pyq.HamiltonianEvolution(tuple([i for i in range(n_qubits)]), n_qubits)
    psi = pyq.uniform_state(n_qubits, batch_size)
    psi_star = hamevo(H, t_evo, psi)
    result = overlap(psi_star, psi)
    assert torch.allclose(result, torch.tensor([0.5, 0.5]))


@pytest.mark.parametrize(
    "H, t_evo, target, batch_size",
    [
        (  # batchsize 1 | 1
            Hamiltonian(1),
            torch.tensor([torch.pi / 4], dtype=torch.cdouble),
            torch.tensor([0.5]),
            1,
        ),
        (  # batchsize 1 | 4
            Hamiltonian(1),
            torch.tensor([torch.pi / 4, 0.0, torch.pi / 2, torch.pi]),
            torch.tensor([0.5, 1.0, 0.0, 1.0]),
            4,
        ),
        (  # batchsize 2 | 1
            Hamiltonian(2),
            torch.tensor([torch.pi / 4], dtype=torch.cdouble),
            torch.tensor([0.5, 0.5]),
            2,
        ),
        (  # batchsize 2 | 2
            Hamiltonian(2),
            torch.tensor([torch.pi / 4, torch.pi]),
            torch.tensor([0.5, 1.0]),
            2,
        ),
    ],
)
def test_hamiltonianevolution_with_types(
    H: torch.Tensor,
    t_evo: torch.Tensor,
    target: torch.Tensor,
    batch_size: int,
) -> None:
    n_qubits = 4
    hamevo = pyq.HamiltonianEvolution(tuple([i for i in range(n_qubits)]), n_qubits)
    psi = pyq.uniform_state(n_qubits)
    psi_star = hamevo(H, t_evo, psi)
    result = overlap(psi_star, psi)
    assert result.size() == (batch_size,)
    assert torch.allclose(result, target)


def test_hamevo_endianness() -> None:
    t = torch.ones(1)
    h = torch.tensor(
        [
            [0.9701, 0.0000, 0.7078, 0.0000],
            [0.0000, 0.9701, 0.0000, 0.7078],
            [0.4594, 0.0000, 0.9207, 0.0000],
            [0.0000, 0.4594, 0.0000, 0.9207],
        ]
    )
    iszero = torch.tensor([False, True, False, True])
    op = pyq.HamiltonianEvolution(qubit_support=(0, 1), n_qubits=2)
    st = op(h, t, pyq.zero_state(2)).flatten()
    assert torch.allclose(st[iszero], torch.zeros(1, dtype=torch.cdouble))

    h = torch.tensor(
        [
            [0.9701, 0.7078, 0.0000, 0.0000],
            [0.4594, 0.9207, 0.0000, 0.0000],
            [0.0000, 0.0000, 0.9701, 0.7078],
            [0.0000, 0.0000, 0.4594, 0.9207],
        ]
    )
    iszero = torch.tensor([False, False, True, True])
    op = pyq.HamiltonianEvolution(qubit_support=(0, 1), n_qubits=2)
    st = op(h, t, pyq.zero_state(2)).flatten()
    assert torch.allclose(st[iszero], torch.zeros(1, dtype=torch.cdouble))
