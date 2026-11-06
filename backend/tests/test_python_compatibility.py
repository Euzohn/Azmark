"""Import-time annotations must also work on the Python 3.11 Docker image."""

import ast
from pathlib import Path


def test_attachment_annotations_are_postponed():
    # AttachmentService.list shadows the builtin for later class annotations.
    # Python 3.11 eagerly evaluates annotations unless this import is present;
    # Python 3.14's deferred evaluation would otherwise hide the startup error.
    source = Path(__file__).parents[1] / "app/services/attachment.py"
    module = ast.parse(source.read_text())
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and any(alias.name == "annotations" for alias in node.names)
        for node in module.body
    )
