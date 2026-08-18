"""
Typing syntax changes across Python versions — old spelling paired with its
replacement, in the order a migration checklist would hit them. `List`,
`Dict`, and `Tuple` give way to the builtin generics; `typing.Callable` and
`typing.Iterable` move to `collections.abc`; `typing.Text` was always just
`str`. A few names are gone outright in 3.13+ (`typing.io`, `typing.re`,
`ByteString`), while `TypeAlias` and `Optional`/`Union`/`TypeVar` have modern
replacements (`type`, `|`, PEP 695 generics) rather than removals.

Run: python3 10_deprecations.py
"""

# Deprecated
from typing import List, Dict, Tuple
x: List[int] = []
y: Dict[str, int] = {}
z: Tuple[int, ...] = ()

# Use instead
x: list[int] = []
y: dict[str, int] = {}
z: tuple[int, ...] = ()


# Deprecated
from typing import Callable, Iterable
def f(x: Callable[[int], str], items: Iterable[int]) -> None: ...

# Use instead
from collections.abc import Callable, Iterable
def f(x: Callable[[int], str], items: Iterable[int]) -> None: ...


# Deprecated
from typing import Text
name: Text = "hi"

# Use instead
name: str = "hi"



# No longer works (3.13+)
from typing import io, re

# Use instead
from typing import IO, TextIO, BinaryIO, Pattern, Match



from typing import ByteString
def f(data: ByteString) -> None: ...

# Use instead
def f(data: bytes | bytearray | memoryview) -> None: ...



# Deprecated
from typing import TypeAlias
IntList: TypeAlias = list[int]

# Use instead (3.12+)
type IntList = list[int]



# Old style
from typing import Optional, Union, TypeVar
def f(x: Optional[int], y: Union[str, bytes]) -> None: ...
T = TypeVar("T")
def g(x: T) -> T: ...

# Preferred (3.10+ for |, 3.12+ for generic syntax)
def f(x: int | None, y: str | bytes) -> None: ...
def g[T](x: T) -> T: ...


from typing import Any
def process(data: Any) -> Any:
    return data.whatever_method_exists()  # no error, even if it doesn't exist