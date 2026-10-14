"""Iterative strongly connected components for bounded direct common-event calls."""


def cycles(nodes, edges, spend):
    forward = {node: set() for node in nodes}
    reverse = {node: set() for node in nodes}
    for source, target in edges:
        spend()
        forward[source].add(target); reverse[target].add(source)
    visited, order = set(), []
    for root in sorted(nodes):
        if root in visited:
            continue
        stack = [(root, False)]
        while stack:
            spend(); node, exiting = stack.pop()
            if exiting:
                order.append(node)
            elif node not in visited:
                visited.add(node); stack.append((node, True))
                stack.extend((child, False) for child in sorted(forward[node], reverse=True) if child not in visited)
    visited, result = set(), []
    for root in reversed(order):
        if root in visited:
            continue
        component, stack = [], [root]; visited.add(root)
        while stack:
            spend(); node = stack.pop(); component.append(node)
            for parent in reverse[node]:
                if parent not in visited:
                    visited.add(parent); stack.append(parent)
        if len(component) > 1 or root in forward[root]:
            result.append(sorted(component))
    return sorted(result)
