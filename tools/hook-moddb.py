"""
PyInstaller runtime hook to fix moddb's use of inspect.getsource()
which fails in frozen executables.
"""

import sys

# Apply patch before any moddb imports
if getattr(sys, "frozen", False):
    import inspect

    # Save original functions
    _original_getsourcelines = inspect.getsourcelines
    _original_getsource = inspect.getsource

    def patched_getsourcelines(obj):
        """Return safe dummy source lines when running in frozen app."""
        try:
            return _original_getsourcelines(obj)
        except (OSError, TypeError):
            # Return a minimal valid Python function source
            return (["def dummy():\n", '    """Placeholder docstring."""\n', "    pass\n"], 0)

    def patched_getsource(obj):
        """Return safe dummy source when running in frozen app."""
        try:
            return _original_getsource(obj)
        except (OSError, TypeError):
            # Return a minimal valid Python function source
            return 'def dummy():\n    """Placeholder docstring."""\n    pass\n'

    # Patch inspect module
    inspect.getsourcelines = patched_getsourcelines
    inspect.getsource = patched_getsource
