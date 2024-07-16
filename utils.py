import networkx as nx

def traverse_functions_bottom_up(bv):
    """
    function pulled from: https://github.com/mrphrazer/reverser_ai/blob/main/reverser_ai/binary_ninja/utils.py
    Implements a worklist algorithm to traverse function call trees in a bottom-up manner as post-order traversal.

    This function creates an iterator that traverses nested function call trees from their leaves up to their roots,
    facilitating bottom-up analysis approaches where leaf-level information is propagated upwards in the call graph.
    This is particularly useful for scenarios where higher-level functions benefit from context provided by their leaf-level counterparts.

    Args:
        bv (binaryninja.BinaryView): The binary view representing the binary analysis context.

    Yields:
        binaryninja.Function: Functions from the binary view, traversed in a bottom-up order based on their call dependencies.
    """
    # Initialize a directed graph to represent the function call graph
    call_graph = nx.DiGraph()

    # Add all functions found in the binary view as nodes to the graph.
    call_graph.add_nodes_from(bv.functions)

    # Iterate over each function in the binary view to build edges in the graph based on call relationships.
    for f in bv.functions:
        # For each function, iterate over its callees (functions that it calls).
        for callee in f.callees:
            # Add an edge from the current function to each of its callees,
            # representing the call dependency in the graph.
            call_graph.add_edge(f, callee)

    # Perform a Depth-First Search (DFS) post-order traversal of the call graph.
    return nx.dfs_postorder_nodes(call_graph)
