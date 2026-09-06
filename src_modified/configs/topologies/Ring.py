from m5.params import *
from m5.objects import *

from common import FileSystemConfig

from topologies.BaseTopology import SimpleTopology

# Ring (1D-torus) topology: N routers connected in a closed loop.
# Each router is bidirectionally connected to its two neighbours.
# Only one dimension exists, so routing is shortest-path around the loop
# (see outportComputeRing in RoutingUnit.cc).


class Ring(SimpleTopology):
    description = "Ring"

    def __init__(self, controllers):
        self.nodes = controllers

    def makeTopology(self, options, network, IntLink, ExtLink, Router):
        nodes = self.nodes

        num_routers = options.num_cpus

        # default values for link latency and router latency.
        # Can be over-ridden on a per link/router basis
        link_latency = options.link_latency  # used by simple and garnet
        router_latency = options.router_latency  # only used by garnet

        # Each router hosts a (nearly) equal number of controllers.
        cntrls_per_router, remainder = divmod(len(nodes), num_routers)
        assert remainder < num_routers

        # Create the routers in the ring
        routers = [
            Router(router_id=i, latency=router_latency)
            for i in range(num_routers)
        ]
        network.routers = routers

        # link counter to set unique link ids
        link_count = 0

        # Add all but the remainder nodes to the list of nodes to be uniformly
        # distributed across the network.
        network_nodes = []
        remainder_nodes = []
        for node_index in range(len(nodes)):
            if node_index < (len(nodes) - remainder):
                network_nodes.append(nodes[node_index])
            else:
                remainder_nodes.append(nodes[node_index])

        # Connect each node to the appropriate router
        ext_links = []
        for (i, n) in enumerate(network_nodes):
            cntrl_level, router_id = divmod(i, num_routers)
            assert cntrl_level < cntrls_per_router
            ext_links.append(
                ExtLink(
                    link_id=link_count,
                    ext_node=n,
                    int_node=routers[router_id],
                    latency=link_latency,
                )
            )
            link_count += 1

        # Connect the remainding nodes to router 0.  These should only be
        # DMA nodes.
        for (i, node) in enumerate(remainder_nodes):
            assert node.type == "DMA_Controller"
            assert i < remainder
            ext_links.append(
                ExtLink(
                    link_id=link_count,
                    ext_node=node,
                    int_node=routers[0],
                    latency=link_latency,
                )
            )
            link_count += 1

        network.ext_links = ext_links

        # Create the ring links: a closed loop of bidirectional links.
        int_links = []

        for i in range(num_routers):
            right = (i + 1) % num_routers
            left = (i - 1 + num_routers) % num_routers

            # Router i -> right neighbour. Leaves via "Right", arrives at
            # the neighbour's "Left" input port.
            int_links.append(
                IntLink(
                    link_id=link_count,
                    src_node=routers[i],
                    dst_node=routers[right],
                    src_outport="Right",
                    dst_inport="Left",
                    latency=link_latency,
                    weight=1,
                )
            )
            link_count += 1

            # Router i -> left neighbour. Leaves via "Left", arrives at
            # the neighbour's "Right" input port.
            int_links.append(
                IntLink(
                    link_id=link_count,
                    src_node=routers[i],
                    dst_node=routers[left],
                    src_outport="Left",
                    dst_inport="Right",
                    latency=link_latency,
                    weight=1,
                )
            )
            link_count += 1

        network.int_links = int_links

    # Register nodes with filesystem
    def registerTopology(self, options):
        for i in range(options.num_cpus):
            FileSystemConfig.register_node(
                [i], MemorySize(options.mem_size) // options.num_cpus, i
            )
