"""PyInstaller runtime hook: make `inspect.getsource` safe in the frozen exe.

The `moddb` library calls ``inspect.getsource(parent.__init__)`` at import time
(its ``concat_docs`` decorator) to reconstruct docstrings. Inside a PyInstaller
frozen app the source files are not on disk, so that call raises OSError and
crashes at startup. We fall back to a stub ``__init__`` body -- the recursion in
``concat_docs`` then stops immediately, which is all we need since the docstring
merge is purely cosmetic.
"""

import inspect
import sys

if getattr(sys, "frozen", False):

    def _frozen_getsource(obj, *args, **kwargs):
        try:
            return _orig_getsource(obj, *args, **kwargs)
        except (OSError, IOError, TypeError):
            return "def __init__(self):\n    pass\n"

    _orig_getsource = inspect.getsource
    inspect.getsource = _frozen_getsource
