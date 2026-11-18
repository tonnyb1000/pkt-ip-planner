"""Multi-router routing calculation and static route generator."""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Set, Tuple

from .models import StaticRoute, SubnetPlan


def compute_static_routes(plans: List[SubnetPlan]) -> Dict[str, List[StaticRoute]]:
    """
    Computes static routes for all routers in multi-router networks to ensure
    end-to-end inter-subnet communication.
    
    Returns:
        Dict mapping router_name -> List of StaticRoute
    """
    # 1. Identify which routers are directly attached to which subnets
    # router_subnets: router_name -> set of subnet_ids
    router_subnets: Dict[str, Set[str]] = {}
    # subnet_routers: subnet_id -> dict of router_name -> interface_ip
    subnet_routers: Dict[str, Dict[str, str]] = {}

    for plan in plans:
        subnet_routers[plan.subnet_id] = {}
        for a in plan.assignments:
            if a.device_kind == "Router" or a.role in ("gateway", "transit"):
                r_name = a.device_name
                router_subnets.setdefault(r_name, set()).add(plan.subnet_id)
                subnet_routers[plan.subnet_id][r_name] = a.ip

    all_routers = list(router_subnets.keys())
    if len(all_routers) <= 1:
        # Single router or zero routers: directly connected routes suffice!
        return {r: [] for r in all_routers}

    # 2. Build adjacency graph between routers
    # router_adj: router_a -> list of (router_b, shared_subnet_id, router_b_ip)
    router_adj: Dict[str, List[Tuple[str, str, str]]] = {r: [] for r in all_routers}
    for s_id, r_dict in subnet_routers.items():
        r_list = list(r_dict.keys())
        for i in range(len(r_list)):
            for j in range(i + 1, len(r_list)):
                r_a, r_b = r_list[i], r_list[j]
                router_adj[r_a].append((r_b, s_id, r_dict[r_b]))
                router_adj[r_b].append((r_a, s_id, r_dict[r_a]))

    routes_by_router: Dict[str, List[StaticRoute]] = {r: [] for r in all_routers}

    # 3. For each router, find routes to all remote subnets
    plan_by_id = {p.subnet_id: p for p in plans}

    for r_source in all_routers:
        directly_connected = router_subnets[r_source]

        for s_target_id, target_plan in plan_by_id.items():
            if s_target_id in directly_connected:
                continue  # Directly connected route already in IOS routing table

            # BFS from r_source to any router connected to s_target_id
            target_routers = set(subnet_routers[s_target_id].keys())
            if not target_routers:
                continue

            # Queue: (current_router, first_hop_ip)
            queue = deque([(r_source, None)])
            visited = {r_source}
            found_next_hop = None

            while queue:
                curr, first_hop = queue.popleft()
                if curr in target_routers:
                    found_next_hop = first_hop
                    break

                for neighbor, shared_sub, neighbor_ip in router_adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_hop_val = first_hop if first_hop is not None else neighbor_ip
                        queue.append((neighbor, next_hop_val))

            if found_next_hop:
                route = StaticRoute(
                    router_name=r_source,
                    destination_network=str(target_plan.network.network_address),
                    destination_mask=str(target_plan.netmask),
                    next_hop_ip=found_next_hop,
                    description=f"Route to {target_plan.name} via {found_next_hop}",
                )
                routes_by_router[r_source].append(route)

    return routes_by_router
