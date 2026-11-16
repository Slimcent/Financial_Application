"""Checks every service's contract test uses: the class implements its interface (Services/Interfaces) completely,
and every operation is async and takes the caller's unit of work as its first argument."""
import inspect

from Data.Interfaces.i_unit_of_work import IUnitOfWork


def operations(interface):
    """The operations an interface declares, sorted by name."""
    return sorted(interface.__abstractmethods__)


def assert_implements(service_class, interface):
    assert issubclass(service_class, interface)
    assert not service_class.__abstractmethods__


def assert_takes_the_unit_of_work_first(service_class, interface, name):
    declared = inspect.signature(getattr(interface, name))
    implemented = inspect.signature(getattr(service_class, name))
    first = list(implemented.parameters.values())[1]

    assert inspect.iscoroutinefunction(getattr(service_class, name))
    assert first.name == "unit_of_work"
    assert first.annotation in (IUnitOfWork, "IUnitOfWork")
    assert list(implemented.parameters) == list(declared.parameters)
