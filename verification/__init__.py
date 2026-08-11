"""CodeStrata Engine verification suites (repo/export only; not shipped in the wheel).

Namespace-extended so Platform SV suites under ``platform/verification/`` can
share the ``verification`` package name when both parents are on ``sys.path``.
"""

from __future__ import annotations

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

__all__ = ["__version__"]

__version__ = "1.0.0"
