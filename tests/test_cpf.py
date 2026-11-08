import pytest

from app.cpf import is_valid_cpf, mask_cpf


@pytest.mark.parametrize("cpf", ["529.982.247-25", "52998224725", "111.444.777-35"])
def test_cpfs_validos(cpf):
    assert is_valid_cpf(cpf)


@pytest.mark.parametrize(
    "cpf",
    ["529.982.247-24", "111.111.111-11", "123", "", "abcdefghijk", "529.982.247-250"],
)
def test_cpfs_invalidos(cpf):
    assert not is_valid_cpf(cpf)


def test_mask():
    assert mask_cpf("52998224725") == "***.***.247-25"
