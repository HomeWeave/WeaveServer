def toposort(graph):
    all_nodes = set(graph)
    order, nodes, state = [], set(graph), {}

    def dfs(node):
        state[node] = 1
        for k in graph.get(node, ()):
            if k not in all_nodes:
                continue
            sk = state.get(k, None)
            if sk == 1:
                raise ValueError("cycle")
            if sk == 2:
                continue
            nodes.discard(k)
            dfs(k)
        order.append(node)
        state[node] = 2

    while nodes:
        dfs(nodes.pop())
    return order
