#!/usr/bin/env python3
import heapq

def calk_paths_djk(graph):
    final = {}
    for start in graph:
        distances = {node: float('infinity') for node in graph}
        distances[start] = 0
        paths = {node: [start,] for node in graph}
        visited = set()
        queue = [(0, start)]
        while queue:
            current_distance, current_node = heapq.heappop(queue)
            if current_node not in visited:
                visited.add(current_node)
                for adjacent, weight in graph[current_node].items():
                    distance = current_distance + weight
                    if distance < distances[adjacent]:
                        distances[adjacent] = distance
                        paths[adjacent] = paths[current_node] + [adjacent]
                        heapq.heappush(queue, (distance, adjacent))
        # final[start] = (distances, paths) 
        # <Switch ID>,<Dest ID>:<Next Hop>,<Shortest distance>
        table = set()
        for k in graph:
            dest_id  = paths[k][-1]
            if len(paths[k]) > 1:
                next_hop = paths[k][1]
            else:
                next_hop = dest_id
            table.add((dest_id, next_hop, distances[k]))
        final[start] = table
    return final

# Given map of nodes
map = {0: {1: 100, 3: 200, 5: 80}, 1: {0: 100, 2: 50, 4: 180}, 3: {0: 200, 2: 50, 4: 100}, 5: {0: 80, 2: 150}, 2: {1: 50, 3: 50, 5: 150}, 4: {1: 180, 3: 100}}
# map = {0: {1: 20, 2: 10}, 1: {0: 20, 2: 30}, 2: {0: 10, 1: 30}}

# Perform Dijkstra's algorithm on each node

final= calk_paths_djk(map)
for node in map:
    print(f"First hops from node {node}: {final[node]}")

