import re


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def is_valid_cpf(value: str) -> bool:
    cpf = only_digits(value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    # dois dígitos verificadores, pesos decrescentes a partir de 10 e 11
    for i in (9, 10):
        total = sum(int(cpf[n]) * (i + 1 - n) for n in range(i))
        digit = (total * 10 % 11) % 10
        if digit != int(cpf[i]):
            return False
    return True


def mask_cpf(cpf: str) -> str:
    """12345678909 -> ***.***.789-09"""
    return f"***.***.{cpf[6:9]}-{cpf[9:]}"
