import heapq

def dijkstra_with_path(graph, start):
    # Initialize distances, paths, and visited set
    distances = {node: float('infinity') for node in graph}
    distances[start] = 0
    paths = {node: [] for node in graph}
    visited = set()

    # Priority queue to store (distance, node) pairs
    priority_queue = [(0, start)]

    while priority_queue:
        current_distance, current_node = heapq.heappop(priority_queue)

        if current_node in visited:
            continue

        visited.add(current_node)

        for neighbor, weight in graph[current_node].items():
            distance = current_distance + weight

            if distance < distances[neighbor]:
                distances[neighbor] = distance
                paths[neighbor] = paths[current_node] + [current_node]
                heapq.heappush(priority_queue, (distance, neighbor))

    return distances, paths

# Given map of nodes
map = {0: {1: 100, 3: 200, 5: 80}, 1: {0: 100, 2: 50, 4: 180}, 3: {0: 200, 2: 50, 4: 100}, 5: {0: 80, 2: 150}, 2: {1: 50, 3: 50, 5: 150}, 4: {1: 180, 3: 100}}

# Perform Dijkstra's algorithm on each node
for node in map:
    distances, paths = dijkstra_with_path(map, node)
    print(f"Shortest paths from node {node}:")
    for destination, distance in distances.items():
        path = paths[destination] + [destination]
        print(f"To {destination}: Distance = {distance}, Path = {path}")
