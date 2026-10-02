import re

from tree_sitter import Language, Parser
import tree_sitter_python


def terms(text: str) -> list[str]:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return re.findall(r"[a-zA-Z][a-zA-Z0-9]*", text.lower())


def parse(source: str, path: str) -> list[dict]:
    """Syntax-derived symbols and unresolved call/import references, not a call graph."""
    raw = source.encode()
    root = Parser(Language(tree_sitter_python.language())).parse(raw).root_node
    if root.has_error:
        raise ValueError(f"Python syntax could not be parsed: {path}")
    chunks = []

    def text(node):
        return raw[node.start_byte:node.end_byte].decode()

    def references(node):
        found = set()
        for child in node.named_children:
            if child.type in {"function_definition", "class_definition"}:
                continue
            if child.type == "call":
                function = child.child_by_field_name("function")
                if function:
                    found.add(text(function))
            found.update(references(child))
        return found

    def visit(node, parents=()):
        if node.type in {"function_definition", "class_definition"}:
            name = text(node.child_by_field_name("name"))
            qualified = ".".join((*parents, name))
            extent = node.parent if node.parent.type == "decorated_definition" else node
            chunks.append({"symbol": qualified, "kind": "class" if node.type == "class_definition" else "function",
                           "start": extent.start_point.row + 1, "end": extent.end_point.row + 1,
                           "content": text(extent), "calls": sorted(references(node))})
            parents = (*parents, name)
        for child in node.named_children:
            visit(child, parents)

    visit(root)
    # Preserve imports, constants, module docstrings and top-level statements as
    # separate structural chunks, rather than repeating the full module.
    for node in root.named_children:
        if node.type in {"function_definition", "class_definition", "decorated_definition"}:
            continue
        chunks.append({"symbol": "<module>", "kind": "module", "start": node.start_point.row + 1,
                       "end": node.end_point.row + 1, "content": text(node), "calls": sorted(references(node))})
    return chunks
