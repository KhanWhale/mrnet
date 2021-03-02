import copy
import heapq
import itertools
import operator
import time as time
from functools import reduce
from typing import Dict, List, Tuple, Union, Any, FrozenSet, Set
from ast import literal_eval

import networkx as nx
from monty.json import MSONable
from networkx.readwrite import json_graph

from mrnet.core.mol_entry import MoleculeEntry
from mrnet.core.reactions import (
    ConcertedReaction,
    CoordinationBondChangeReaction,
    IntermolecularReaction,
    IntramolSingleBondChangeReaction,
    Reaction,
    RedoxReaction,
    exponent,
    general_graph_rep,
    rexp,
    softplus,
    MetalHopReaction,
)
from mrnet.utils.classes import load_class

__author__ = "Sam Blau, Hetal Patel, Xiaowei Xie, Evan Spotte-Smith"
__version__ = "0.1"
__maintainer__ = "Sam Blau"
__status__ = "Alpha"

Mapping_Record_Dict = Dict[int, List[str]]


class ReactionPath(MSONable):
    """
    A class to define path object within the reaction network which
    constains all the associated characteristic attributes of a given path

    :param path - a list of nodes that defines a path from node A to B
        within a graph built using ReactionNetwork.build()
    """

    def __init__(self, path):
        """
        initializes the ReactionPath object attributes for a given path
        :param path: a list of nodes that defines a path from node A to B
            within a graph built using ReactionNetwork.build()
        """

        self.path = path
        self.byproducts = []
        self.unsolved_prereqs = []
        self.solved_prereqs = []
        self.all_prereqs = []
        self.cost = 0.0
        self.overall_free_energy_change = 0.0
        self.hardest_step = None
        self.description = ""
        self.pure_cost = 0.0
        self.full_path = None
        self.hardest_step_deltaG = None
        self.path_dict = {
            "byproducts": self.byproducts,
            "unsolved_prereqs": self.unsolved_prereqs,
            "solved_prereqs": self.solved_prereqs,
            "all_prereqs": self.all_prereqs,
            "cost": self.cost,
            "path": self.path,
            "overall_free_energy_change": self.overall_free_energy_change,
            "hardest_step": self.hardest_step,
            "description": self.description,
            "pure_cost": self.pure_cost,
            "hardest_step_deltaG": self.hardest_step_deltaG,
            "full_path": self.full_path,
        }

    @property
    def as_dict(self) -> dict:
        """
            A method to convert ReactionPath objection into a dictionary
        :return: d: dictionary containing all te ReactionPath attributes
        """
        d = {
            "@module": self.__class__.__module__,
            "@class": self.__class__.__name__,
            "byproducts": self.byproducts,
            "unsolved_prereqs": self.unsolved_prereqs,
            "solved_prereqs": self.solved_prereqs,
            "all_prereqs": self.all_prereqs,
            "cost": self.cost,
            "path": self.path,
            "overall_free_energy_change": self.overall_free_energy_change,
            "hardest_step": self.hardest_step,
            "description": self.description,
            "pure_cost": self.pure_cost,
            "hardest_step_deltaG": self.hardest_step_deltaG,
            "full_path": self.full_path,
            "path_dict": self.path_dict,
        }
        return d

    @classmethod
    def from_dict(cls, d):
        """
            A method to convert dict to ReactionPath object
        :param d:  dict retuend from ReactionPath.as_dict() method
        :return: ReactionPath object
        """
        x = cls(d.get("path"))
        x.byproducts = d.get("byproducts")
        x.unsolved_prereqs = d.get("unsolved_prereqs")
        x.solved_prereqs = d.get("solved_prereqs")
        x.all_prereqs = d.get("all_prereqs")
        x.cost = d.get("cost", 0)

        x.overall_free_energy_change = d.get("overall_free_energy_change", 0)
        x.hardest_step = d.get("hardest_step")
        x.description = d.get("description")
        x.pure_cost = d.get("pure_cost", 0)
        x.hardest_step_deltaG = d.get("hardest_step_deltaG")
        x.full_path = d.get("full_path")
        x.path_dict = d.get("path_dict")

        return x

    @classmethod
    def characterize_path(
        cls,
        path: List[Union[str, int]],
        weight: str,
        graph: nx.DiGraph,
        old_solved_PRs=[],
    ):  # -> ReactionPath
        """
         A method to define ReactionPath attributes based on the inputs

        :param path: a list of nodes that defines a path from node A to B
            within a graph built using ReactionNetwork.build()
        :param weight: string (either "softplus" or "exponent")
        :param graph: nx.Digraph
        :param old_solved_PRs: previously solved PRs from the iterations before
            the current iteration
        :return: ReactionPath object
        """

        if path is None:
            class_instance = cls(None)
        else:
            class_instance = cls(path)
            pool = []
            pool.append(path[0])
            for ii, step in enumerate(path):
                if ii != len(path) - 1:
                    class_instance.cost += graph[step][path[ii + 1]][weight]
                    if isinstance(step, str):
                        if "PR" in step:
                            prod = []  # type: List[Union[str, int]]
                            a = int(step.split(",")[0].split("+PR_")[0])
                            pr = int(step.split(",")[0].split("+PR_")[1])
                            if "+" in step.split(",")[1]:
                                c = int(step.split(",")[1].split("+")[0])
                                d = int(step.split(",")[1].split("+")[1])
                                prod = [c, d]
                            else:
                                c = int(step.split(",")[1])
                                prod = [c]
                            if pr in old_solved_PRs:
                                class_instance.solved_prereqs.append(pr)
                            else:
                                class_instance.unsolved_prereqs.append(pr)
                            class_instance.all_prereqs.append(pr)
                            pool.remove(a)
                            pool = pool + prod
                        elif "+" in step.split(",")[1]:
                            # node = A,B+C
                            a = int(step.split(",")[0])
                            b = int(step.split(",")[1].split("+")[0])
                            c = int(step.split(",")[1].split("+")[1])
                            pool.remove(a)
                            pool.append(b)
                            pool.append(c)
                        else:
                            # node = A,B
                            a = int(step.split(",")[0])
                            b = int(step.split(",")[1])
                            pool.remove(a)
                            pool.append(b)

        pool.remove(class_instance.path[-1])
        class_instance.byproducts = pool
        class_instance.path_dict = {
            "byproducts": class_instance.byproducts,
            "unsolved_prereqs": class_instance.unsolved_prereqs,
            "solved_prereqs": class_instance.solved_prereqs,
            "all_prereqs": class_instance.all_prereqs,
            "cost": class_instance.cost,
            "path": class_instance.path,
            "overall_free_energy_change": class_instance.overall_free_energy_change,
            "hardest_step": class_instance.hardest_step,
            "description": class_instance.description,
            "pure_cost": class_instance.pure_cost,
            "hardest_step_deltaG": class_instance.hardest_step_deltaG,
            "full_path": class_instance.full_path,
        }
        return class_instance

    @classmethod
    def characterize_path_final(
        cls,
        path: List[Union[str, int]],
        weight: str,
        graph: nx.DiGraph,
        old_solved_PRs=[],
        PR_paths={},
    ):
        """
            A method to define all the attributes of a given path once all the PRs are solved
        :param path: a list of nodes that defines a path from node A to B within a graph built using
        ReactionNetwork.build()
        :param weight: string (either "softplus" or "exponent")
        :param min_cost: dict with minimum cost from path start to a node, of from {node: float},
        if no path exist, value is "no_path", if path is unsolved yet, value is "unsolved_path"
        :param graph: nx.Digraph
        :param PR_paths: dict that defines a path from each node to a start,
               of the form {int(node1): {int(start1}: {ReactionPath object}, int(start2): {ReactionPath object}},
               int(node2):...}
        :return: ReactionPath object
        """

        if path is None:
            class_instance = cls(None)
        else:
            class_instance = cls.characterize_path(path, weight, graph, old_solved_PRs)
            assert len(class_instance.solved_prereqs) == len(class_instance.all_prereqs)
            assert len(class_instance.unsolved_prereqs) == 0

            PRs_to_join = copy.deepcopy(class_instance.all_prereqs)
            full_path = copy.deepcopy(class_instance.path)
            while len(PRs_to_join) > 0:
                new_PRs = []
                for PR in PRs_to_join:
                    PR_path = None
                    PR_min_cost = float("inf")  # 1000000000000000.0
                    for start in PR_paths[PR]:
                        if PR_paths[PR][start].path is not None:
                            if PR_paths[PR][start].cost < PR_min_cost:
                                PR_min_cost = PR_paths[PR][start].cost
                                PR_path = PR_paths[PR][start]
                    if PR_path is not None:
                        assert len(PR_path.solved_prereqs) == len(PR_path.all_prereqs)
                        for new_PR in PR_path.all_prereqs:
                            new_PRs.append(new_PR)
                        # class_instance.all_prereqs.append(new_PR)
                    # for new_BP in PR_path.byproducts:
                    # class_instance.byproducts.append(new_BP)
                    full_path = PR_path.path + full_path
                PRs_to_join = copy.deepcopy(new_PRs)

            for PR in class_instance.all_prereqs:
                if PR in class_instance.byproducts:
                    print("WARNING: Matching prereq and byproduct found!", PR)

            for ii, step in enumerate(full_path):
                if graph.nodes[step]["bipartite"] == 1:
                    if weight == "softplus":
                        class_instance.pure_cost += ReactionNetwork.softplus(
                            graph.nodes[step]["free_energy"]
                        )
                    elif weight == "exponent":
                        class_instance.pure_cost += ReactionNetwork.exponent(
                            graph.nodes[step]["free_energy"]
                        )
                    elif weight == "rexp":
                        class_instance.pure_cost += ReactionNetwork.rexp(
                            graph.nodes[step]["free_energy"]
                        )

                    class_instance.overall_free_energy_change += graph.nodes[step][
                        "free_energy"
                    ]

                    if class_instance.description == "":
                        class_instance.description += graph.nodes[step]["rxn_type"]
                    else:
                        class_instance.description += (
                            ", " + graph.nodes[step]["rxn_type"]
                        )

                    if class_instance.hardest_step is None:
                        class_instance.hardest_step = step
                    elif (
                        graph.nodes[step]["free_energy"]
                        > graph.nodes[class_instance.hardest_step]["free_energy"]
                    ):
                        class_instance.hardest_step = step

            class_instance.full_path = full_path

            if class_instance.hardest_step is None:
                class_instance.hardest_step_deltaG = None
            else:
                class_instance.hardest_step_deltaG = graph.nodes[
                    class_instance.hardest_step
                ]["free_energy"]

        class_instance.path_dict = {
            "byproducts": class_instance.byproducts,
            "unsolved_prereqs": class_instance.unsolved_prereqs,
            "solved_prereqs": class_instance.solved_prereqs,
            "all_prereqs": class_instance.all_prereqs,
            "cost": class_instance.cost,
            "path": class_instance.path,
            "overall_free_energy_change": class_instance.overall_free_energy_change,
            "hardest_step": class_instance.hardest_step,
            "description": class_instance.description,
            "pure_cost": class_instance.pure_cost,
            "hardest_step_deltaG": class_instance.hardest_step_deltaG,
            "full_path": class_instance.full_path,
        }

        return class_instance


Mapping_PR_Dict = Dict[int, Dict[int, ReactionPath]]


class ReactionNetwork(MSONable):
    """
    Class to build a reaction network from entries
    """

    def __init__(
        self,
        electron_free_energy,
        temperature,
        solvent_dielectric,
        solvent_refractive_index,
        entries_dict,
        entries_list,
        graph,
        reactions,
        PRs,
        PR_record,
        min_cost,
        num_starts,
    ):
        """
        :param electron_free_energy: Electron free energy (in eV)
        :param temperature: Temperature of the system, used for free energy
            and rate constants (temperature given in K)
        :param solvent_dielectric: dielectric constant of the solvent medium
        :param solvent_refractive_index: refractive index of the solvent medium
        :param entries_dict: dict of dicts of dicts of lists (d[formula][bonds][charge])
        :param entries_list: list of unique entries in entries_dict
        :param graph: nx.DiGraph representing connections in the network
        :param reactions: list of Reaction objects
        :param PRs: dict containing prerequisite information
        :param PR_record: dict containing reaction prerequisites
        :param min_cost: dict containing costs of entries in the network
        :param num_starts: Number of starting molecules
        """

        self.electron_free_energy = electron_free_energy
        self.temperature = temperature
        self.solvent_dielectric = solvent_dielectric
        self.solvent_refractive_index = solvent_refractive_index

        self.entries = entries_dict
        self.entries_list = entries_list

        self.graph = graph
        self.PR_record = PR_record
        self.reactions = reactions

        self.min_cost = min_cost
        self.num_starts = num_starts

        self.PRs = PRs
        self.reachable_nodes = []
        self.unsolvable_PRs = []
        self.entry_ids = {e.entry_id for e in self.entries_list}
        self.weight = None
        self.Reactant_record = None
        self.min_cost = {}
        self.not_reachable_nodes = []

    @classmethod
    def from_input_entries(
        cls,
        input_entries,
        electron_free_energy=-2.15,
        temperature=298.15,
        solvent_dielectric=18.5,
        solvent_refractive_index=1.415,
        replace_ind=True,
    ):
        """
        Generate a ReactionNetwork from a set of MoleculeEntries.

        :param input_entries: list of MoleculeEntries which will make up the
            network
        :param electron_free_energy: float representing the Gibbs free energy
            required to add an electron (in eV)
        :param temperature: Temperature of the system, used for free energy
            and rate constants (in K)
        :param solvent_dielectric: Dielectric constant of the solvent medium
        :param solvent_refractive_index: Refractive index of the solvent medium
        :param replace_ind: True if reindex the entries if it there is already
            indices in the input_entries
        :return:
        """

        entries = dict()
        entries_list = list()

        print(len(input_entries), "input entries")

        # Filter out unconnected entries, aka those that contain distinctly
        # separate molecules which are not connected via a bond
        connected_entries = list()
        for entry in input_entries:
            if len(entry.molecule) > 1:
                if nx.is_weakly_connected(entry.graph):
                    connected_entries.append(entry)
            else:
                connected_entries.append(entry)
        print(len(connected_entries), "connected entries")

        def get_formula(x):
            return x.formula

        def get_num_bonds(x):
            return x.num_bonds

        def get_charge(x):
            return x.charge

        def get_free_energy(x):
            return x.get_free_energy(temperature=temperature)

        # Sort by formula
        sorted_entries_0 = sorted(connected_entries, key=get_formula)
        for k1, g1 in itertools.groupby(sorted_entries_0, get_formula):
            sorted_entries_1 = sorted(list(g1), key=get_num_bonds)
            entries[k1] = dict()
            # Sort by number of bonds
            for k2, g2 in itertools.groupby(sorted_entries_1, get_num_bonds):
                sorted_entries_2 = sorted(list(g2), key=get_charge)
                entries[k1][k2] = dict()
                # Sort by charge
                for k3, g3 in itertools.groupby(sorted_entries_2, get_charge):
                    sorted_entries_3 = sorted(list(g3), key=get_free_energy)
                    if len(sorted_entries_3) > 1:
                        unique = list()
                        for entry in sorted_entries_3:
                            isomorphic_found = False
                            # Sort by graph isomorphism, taking the isomorphic
                            # entry with the lowest free energy
                            for ii, Uentry in enumerate(unique):
                                if entry.mol_graph.isomorphic_to(Uentry.mol_graph):
                                    isomorphic_found = True
                                    if (
                                        entry.get_free_energy() is not None
                                        and Uentry.get_free_energy() is not None
                                    ):
                                        if entry.get_free_energy(
                                            temperature
                                        ) < Uentry.get_free_energy(temperature):
                                            unique[ii] = entry
                                    elif entry.get_free_energy() is not None:
                                        unique[ii] = entry
                                    elif entry.energy < Uentry.energy:
                                        unique[ii] = entry
                                    break
                            if not isomorphic_found:
                                unique.append(entry)
                        entries[k1][k2][k3] = unique
                    else:
                        entries[k1][k2][k3] = sorted_entries_3
                    for entry in entries[k1][k2][k3]:
                        entries_list.append(entry)

        print(len(entries_list), "unique entries")
        # Add entry indices
        if replace_ind:
            for ii, entry in enumerate(entries_list):
                # if "ind" in entry.parameters.keys():
                #     pass
                # else:
                entry.parameters["ind"] = ii

        entries_list = sorted(entries_list, key=lambda x: x.parameters["ind"])

        graph = nx.DiGraph()

        network = cls(
            electron_free_energy,
            temperature,
            solvent_dielectric,
            solvent_refractive_index,
            entries,
            entries_list,
            graph,
            list(),
            dict(),
            dict(),
            dict(),
            0,
        )

        return network

    @staticmethod
    def softplus(free_energy: float) -> float:
        """
        Method to determine edge weight using softplus cost function
        NOTE: This cost function is unphysical and should only be used when
        neither rexp nor exponent allow prerequisite costs to be solved.
        """
        return softplus(free_energy)

    @staticmethod
    def exponent(free_energy: float) -> float:
        """
        Method to determine edge weight using exponent cost function
        """
        return exponent(free_energy)

    @staticmethod
    def rexp(free_energy: float) -> float:
        """
        Method to determine edge weight using exponent(dG/kt) cost function
        """
        return rexp(free_energy)

    def build(
        self,
        reaction_types: Union[Set, FrozenSet] = frozenset(
            {
                "RedoxReaction",
                "IntramolSingleBondChangeReaction",
                "IntermolecularReaction",
                "CoordinationBondChangeReaction",
            }
        ),
        determine_atom_mappings: bool = True,
    ) -> nx.DiGraph:
        """
            A method to build the reaction network graph

        :param reaction_types (set/frozenset): set/frozenset of all the reactions
            class to include while building the graph
        :param determine_atom_mappings (bool): If True (default), create an atom
            mapping between reactants and products in a given reaction
        :return: nx.DiGraph
        """

        print("build() start", time.time())

        # Add molecule nodes
        for entry in self.entries_list:
            self.graph.add_node(entry.parameters["ind"], bipartite=0)

        reaction_classes = [load_class(str(self.__module__), s) for s in reaction_types]

        all_reactions = list()

        # Generate reactions
        for r in reaction_classes:
            reactions = r.generate(
                self.entries, determine_atom_mappings=determine_atom_mappings
            )
            all_reactions.append(reactions)

        all_reactions = [i for i in all_reactions if i]
        self.reactions = list(itertools.chain.from_iterable(all_reactions))

        redox_c = 0
        inter_c = 0
        intra_c = 0
        coord_c = 0

        for ii, r in enumerate(self.reactions):
            r.parameters["ind"] = ii
            if r.__class__.__name__ == "RedoxReaction":
                redox_c += 1
                r.electron_free_energy = self.electron_free_energy
            elif r.__class__.__name__ == "IntramolSingleBondChangeReaction":
                intra_c += 1
            elif r.__class__.__name__ == "IntermolecularReaction":
                inter_c += 1
            elif r.__class__.__name__ == "CoordinationBondChangeReaction":
                coord_c += 1
            self.add_reaction(r.graph_representation())

        print(
            "redox: ",
            redox_c,
            "inter: ",
            inter_c,
            "intra: ",
            intra_c,
            "coord: ",
            coord_c,
        )
        self.PR_record = self.build_PR_record()
        self.Reactant_record = self.build_reactant_record()

        return self.graph

    def add_reaction(self, graph_representation: nx.DiGraph):
        """
            A method to add a single reaction to the ReactionNetwork.graph
            attribute
        :param graph_representation: Graph representation of a reaction,
            obtained from ReactionClass.graph_representation
        """
        self.graph.add_nodes_from(graph_representation.nodes(data=True))
        self.graph.add_edges_from(graph_representation.edges(data=True))

    def build_PR_record(self) -> Mapping_Record_Dict:
        """
        A method to determine all the reaction nodes that have a the same
        PR in the ReactionNetwork.graph

        :return: a dict of the form {int(node1): [all the reaction nodes with
        PR of node1, ex "2+PR_node1, 3"]}
        """
        PR_record = {}  # type: Mapping_Record_Dict
        for node in self.graph.nodes():
            if self.graph.nodes[node]["bipartite"] == 0:
                PR_record[node] = []
        for node in self.graph.nodes():
            if self.graph.nodes[node]["bipartite"] == 1:
                if "+PR_" in node.split(",")[0]:
                    PR = int(node.split(",")[0].split("+PR_")[1])
                    PR_record[PR].append(node)
        self.PR_record = PR_record
        return PR_record

    def build_reactant_record(self) -> Mapping_Record_Dict:
        """
        A method to determine all the reaction nodes that have the same non
        PR reactant node in the ReactionNetwork.graph

        :return: a dict of the form {int(node1): [all the reaction nodes with
        non PR reactant of node1, ex "node1+PR_2, 3"]}
        """
        Reactant_record = {}  # type: Mapping_Record_Dict
        for node in self.graph.nodes():
            if self.graph.nodes[node]["bipartite"] == 0:
                Reactant_record[node] = []
        for node in self.graph.nodes():
            if self.graph.nodes[node]["bipartite"] == 1:
                non_PR_reactant = node.split(",")[0].split("+PR_")[0]
                Reactant_record[int(non_PR_reactant)].append(node)
        self.Reactant_record = Reactant_record
        return Reactant_record

    def solve_prerequisites(
        self, starts: List[int], weight: str, max_iter=25
    ):  # -> Tuple[Union[Dict[Union[int, Any], dict], Any], Any]:
        """
            A method to solve all of the prerequisites found in
            ReactionNetwork.graph. By solving all PRs, it gives information on
            1. whether a path exists from any of the starts to each other
            molecule node, 2. if so, what is the min cost to reach that node
            from any of the starts, 3. if there is no path from any of the starts
            to a given molecule node, 4. for molecule nodes where the path
            exists, characterize it in the form of ReactionPath
        :param starts: List(molecular nodes), list of molecular nodes of type
            int found in the ReactionNetwork.graph
        :param weight: "softplus" or "exponent", type of cost function to use
            when calculating edge weights
        :param max_iter: maximum number of iterations to try to solve all the
            PRs
        :return: PRs: PR_paths: dict that defines a path from each node to a
            start, of the form {int(node1): {int(start1}: {ReactionPath object},
            int(start2): {ReactionPath object}}, int(node2):...}
        :return: old_solved_PRs: list of solved PRs
        """

        print("start solve_prerequisities", time.time())
        PRs = {}  # type: Dict[int, Dict[int, ReactionPath]]
        old_solved_PRs = []
        new_solved_PRs = ["placeholder"]
        old_attrs = {}  # type: Dict[Tuple[int, str], Dict[str, float]]
        new_attrs = {}  # type: Dict[Tuple[int, str], Dict[str, float]]
        self.weight = weight
        self.num_starts = len(starts)
        self.PR_byproducts = {}  # type: Dict[int, Dict[str, int]]

        if len(self.graph.nodes) == 0:
            self.build()
        if self.PR_record is None:
            self.PR_record = self.build_PR_record()
        if self.Reactant_record is None:
            self.Reactant_record = self.build_reactant_record()
        orig_graph = copy.deepcopy(self.graph)

        for start in starts:
            PRs[start] = {}

        for PR in PRs:
            for start in starts:
                if start == PR:
                    PRs[PR][start] = ReactionPath.characterize_path(
                        [start], weight, self.graph
                    )
                else:
                    PRs[PR][start] = ReactionPath(None)

            old_solved_PRs.append(PR)
            self.min_cost[PR] = PRs[PR][PR].cost
        for node in self.graph.nodes():
            if self.graph.nodes[node]["bipartite"] == 0:  # and node != target:
                if node not in PRs:
                    PRs[node] = {}

        ii = 0

        while (len(new_solved_PRs) > 0 or old_attrs != new_attrs) and ii < max_iter:
            print(ii, len(new_solved_PRs) > 0, old_attrs != new_attrs, ii < max_iter)

            min_cost = {}
            cost_from_start = {}  # type: Dict[int, Dict[int, Union[float, str]]]
            for PR in PRs:
                cost_from_start[PR] = {}
                min_cost[PR] = float("inf")
                self.PR_byproducts[PR] = {}
                for start in PRs[PR]:
                    if PRs[PR][start] == {}:
                        cost_from_start[PR][start] = "no_path"
                    elif PRs[PR][start].path is None:
                        cost_from_start[PR][start] = "no_path"
                    else:
                        cost_from_start[PR][start] = PRs[PR][start].cost
                        if PRs[PR][start].cost < min_cost[PR]:
                            min_cost[PR] = PRs[PR][start].cost
                            self.PR_byproducts[PR]["byproducts"] = PRs[PR][
                                start
                            ].byproducts
                            self.PR_byproducts[PR]["start"] = start
                for start in starts:
                    if start not in cost_from_start[PR]:
                        cost_from_start[PR][start] = "unsolved"
            PRs, cost_from_start, min_cost = self.find_path_cost(
                starts, weight, old_solved_PRs, cost_from_start, min_cost, PRs
            )
            solved_PRs = copy.deepcopy(old_solved_PRs)
            solved_PRs, new_solved_PRs, cost_from_start = self.identify_solved_PRs(
                PRs, solved_PRs, cost_from_start
            )

            print(ii, len(old_solved_PRs), len(new_solved_PRs), new_solved_PRs)
            attrs = self.update_edge_weights(min_cost, orig_graph)

            self.min_cost = copy.deepcopy(min_cost)
            old_solved_PRs = copy.deepcopy(solved_PRs)
            old_attrs = copy.deepcopy(new_attrs)
            new_attrs = copy.deepcopy(attrs)

            print("iteration", ii, "end at", time.time())
            ii += 1
        print("out of while loop at ", time.time())
        self.solved_PRs = copy.deepcopy(old_solved_PRs)
        self.PRs_before_final_check = PRs

        PRs = self.final_PR_check(PRs)
        self.PRs = PRs

        print(
            "total input molecules:",
            len(self.entries_list),
            "solvable PRs:",
            len(old_solved_PRs),
            "unsolvable PRs:",
            len(self.unsolvable_PRs),
            "not reachable mols:",
            len(self.not_reachable_nodes),
        )
        print("end solve_prerequisities", time.time())
        return PRs, old_solved_PRs

    def parse_path(self, path):
        nodes = []
        PR = []
        Reactants = []
        for step in path:
            if isinstance(step, int):
                nodes.append(step)
            elif "PR_" in step:
                if step.count("+") == 1:
                    nodes = nodes + [step.split("+")[0]]
                    Reactants.append(int(step.split("+")[0]))
                    PR.append(int(step.split("+")[1].split("PR_")[1].split(",")[0]))
                    nodes = nodes + step.split("+")[1].split("PR_")[1].split(",")
                elif step.count("+") == 2:
                    nodes = nodes + [step.split(",")[0].split("+PR_")[0]]
                    Reactants.append(step.split(",")[0].split("+PR_")[0])
                    PR.append(step.split(",")[0].split("+PR_")[1])
                    nodes = nodes + step.split(",")[1].split("+")
                else:
                    print("parse_path something is wrong", path, step)
            else:
                assert "," in step
                nodes = nodes + step.split(",")
        nodes.pop(0)
        if len(nodes) != 0:
            nodes.pop(-1)
        return nodes, PR, Reactants

    def find_path_cost(
        self, starts, weight, old_solved_PRs, cost_from_start, min_cost, PRs
    ):
        """
            A method to characterize the path to all the PRs. Characterize by
            determining if the path exist or not, and
            if so, is it a minimum cost path, and if so set PRs[node][start] = ReactionPath(path)
        :param starts: List(molecular nodes), list of molecular nodes of type
            int found in the ReactionNetwork.graph
        :param target: a single molecular node of type int found in the
            ReactionNetwork.graph
        :param weight: "softplus" or "exponent", type of cost function to use
            when calculating edge weights
        :param old_solved_PRs: list of PRs (molecular nodes of type int) that
            are already solved
        :param cost_from_start: dict of type {node1: {start1: float,
                                                      start2: float},
                                              node2: {...}}
        :param min_cost: dict with minimum cost from path start to a node, of
            from {node: float},
            if no path exist, value is "no_path", if path is unsolved yet,
            value is "unsolved_path"
        :param PRs: dict that defines a path from each node to a start,
            of the form {int(node1):
                            {int(start1}: {ReactionPath object},
                            int(start2): {ReactionPath object}},
                         int(node2):...}
        :return: PRs: updated PRs based on new PRs solved
        :return: cost_from_start: updated cost_from_start based on new PRs solved
        :return: min_cost: updated min_cost based on new PRs solved
        """

        not_reachable_nodes_for_start = {}

        wrong_paths = {}
        dist_and_path = {}
        self.num_starts = len(starts)
        for start in starts:
            not_reachable_nodes_for_start[start] = []
            dist, paths = nx.algorithms.shortest_paths.weighted.single_source_dijkstra(
                self.graph, start, weight=self.weight
            )
            dist_and_path[start] = {}
            wrong_paths[start] = []
            for node in range(len(self.entries_list)):
                if node not in paths.keys():
                    not_reachable_nodes_for_start[start].append(int(node))
            for node in paths:
                if self.graph.nodes[node]["bipartite"] == 0:
                    if node not in self.reachable_nodes:
                        self.reachable_nodes.append(int(node))

                    dist_and_path[start][int(node)] = {}
                    dist_and_path[start][node]["cost"] = dist[node]
                    dist_and_path[start][node]["path"] = paths[node]
                    nodes = []
                    PR = []
                    Reactants = []
                    for step in paths[node]:
                        if isinstance(step, int):
                            nodes.append(step)
                        elif "PR_" in step:
                            if step.count("+") == 1:
                                nodes = nodes + [step.split("+")[0]]
                                Reactants.append(int(step.split("+")[0]))
                                PR.append(
                                    int(
                                        step.split("+")[1].split("PR_")[1].split(",")[0]
                                    )
                                )
                                if node in PR:
                                    if node not in wrong_paths[start]:
                                        wrong_paths[start].append(int(node))
                                nodes = nodes + step.split("+")[1].split("PR_")[
                                    1
                                ].split(",")
                            elif step.count("+") == 2:
                                nodes = nodes + [step.split(",")[0].split("+PR_")[0]]
                                Reactants.append(step.split(",")[0].split("+PR_")[0])
                                PR.append(step.split(",")[0].split("+PR_")[1])
                                if node in PR:
                                    if node not in wrong_paths[start]:
                                        wrong_paths[start].append(int(node))
                                nodes = nodes + step.split(",")[1].split("+")
                            elif step.count("+") == 3:
                                PR.append(step.split(",")[0].split("+PR_")[1])
                                PR.append(step.split(",")[0].split("+PR_")[2])
                                if node in PR:
                                    if node not in wrong_paths[start]:
                                        wrong_paths[start].append(int(node))
                            else:
                                print("SOMETHING IS WRONG", step)
                        else:
                            assert "," in step
                            nodes = nodes + step.split(",")
                    nodes.pop(0)
                    if len(nodes) != 0:
                        nodes.pop(-1)
                    dist_and_path[start][node]["all_nodes"] = nodes
                    dist_and_path[start][node]["PRs"] = PR
                    dist_and_path[start][node]["reactant"] = Reactants

        for node in self.graph.nodes():
            if self.graph.nodes[node]["bipartite"] == 0:
                if node not in self.reachable_nodes:
                    if node not in self.not_reachable_nodes:
                        self.not_reachable_nodes.append(node)

        for start in not_reachable_nodes_for_start:
            for node in not_reachable_nodes_for_start[start]:
                if node not in self.graph.nodes:
                    pass
                else:
                    PRs[node][start] = ReactionPath(None)
                    cost_from_start[node][start] = "no_path"

        fixed_paths = {}
        for start in wrong_paths:
            fixed_paths[start] = {}
            for node in wrong_paths[start]:
                fixed_paths[start][node] = {}
                try:
                    (
                        length,
                        dij_path,
                    ) = nx.algorithms.simple_paths._bidirectional_dijkstra(
                        self.graph,
                        source=hash(start),
                        target=hash(node),
                        ignore_nodes=self.find_or_remove_bad_nodes(
                            [node] + self.not_reachable_nodes
                        ),
                        weight=self.weight,
                    )
                    fixed_paths[start][node]["cost"] = length
                    fixed_paths[start][node]["path"] = dij_path
                except nx.exception.NetworkXNoPath:
                    fixed_paths[start][node]["cost"] = "no_cost"
                    fixed_paths[start][node]["path"] = "no_path"

        self.unsolvable_PRs_per_start = {}
        for start in starts:
            self.unsolvable_PRs_per_start[start] = []
            for node in fixed_paths[start]:
                if fixed_paths[start][node]["path"] == "no_path":
                    dist_and_path[start][node] = {}
                    self.unsolvable_PRs_per_start[start].append(node)
                    pass
                else:
                    dist_and_path[start][node]["cost"] = fixed_paths[start][node][
                        "cost"
                    ]
                    dist_and_path[start][node]["path"] = fixed_paths[start][node][
                        "path"
                    ]
                    nodes, PR, reactant = self.parse_path(
                        dist_and_path[start][node]["path"]
                    )
                    dist_and_path[start][node]["all_nodes"] = nodes
                    dist_and_path[start][node]["PRs"] = PR
                    dist_and_path[start][node]["reactant"] = reactant
            dist_and_path[start] = {
                key: value
                for key, value in sorted(
                    dist_and_path[start].items(), key=lambda item: int(item[0])
                )
            }

        for start in starts:
            for node in dist_and_path[start]:
                if node not in old_solved_PRs:
                    if dist_and_path[start][node] == {}:
                        PRs[node][start] = ReactionPath(None)
                        cost_from_start[node][start] = "no_path"
                    elif dist_and_path[start][node]["cost"] == float("inf"):
                        PRs[node][start] = ReactionPath(None)
                    else:
                        path_class = ReactionPath.characterize_path(
                            dist_and_path[start][node]["path"],
                            weight,
                            self.graph,
                            old_solved_PRs,
                        )
                        cost_from_start[node][start] = path_class.cost
                        if len(path_class.unsolved_prereqs) == 0:
                            PRs[node][start] = path_class
                        if path_class.cost < min_cost[node]:
                            min_cost[node] = path_class.cost
                            self.PR_byproducts[node][
                                "byproducts"
                            ] = path_class.byproducts
                            self.PR_byproducts[node]["start"] = start

        return PRs, cost_from_start, min_cost

    def identify_solved_PRs(self, PRs, solved_PRs, cost_from_start):
        """
            A method to identify new solved PRs after each iteration
        :param PRs: dict that defines a path from each node to a start, of the
            form {int(node1): {int(start1}: {ReactionPath object},
                               int(start2): {ReactionPath object}},
                 int(node2):...}
        :param solved_PRs: list of PRs (molecular nodes of type int) that are
            already solved
        :param cost_from_start: dict of type {node1: {start1: float,
                                                      start2: float},
                                              node2: {...}}
        :return: solved_PRs: list of all the PRs(molecular nodes of type int)
            that are already solved plus new PRs solved in the current iteration
        :return: new_solved_PRs: list of just the new PRs(molecular nodes of
            type int) solved during current iteration
        :return: cost_from_start: updated dict of cost_from_start based on the
            new PRs solved during current iteration
        """
        new_solved_PRs = []

        for PR in PRs:
            if PR not in solved_PRs:
                if len(PRs[PR].keys()) == self.num_starts:
                    new_solved_PRs.append(PR)
                else:
                    best_start_so_far = [None, float("inf")]
                    for start in PRs[PR]:
                        if PRs[PR][start] is not None:  # ALWAYS TRUE should be != {}
                            if PRs[PR][start].cost < best_start_so_far[1]:
                                best_start_so_far[0] = start
                                best_start_so_far[1] = PRs[PR][start].cost

                    if best_start_so_far[0] is not None:
                        num_beaten = 0
                        for start in cost_from_start[PR]:
                            if start != best_start_so_far[0]:
                                if cost_from_start[PR][start] == "no_path":
                                    num_beaten += 1
                                elif cost_from_start[PR][start] >= best_start_so_far[1]:
                                    num_beaten += 1
                        if num_beaten == self.num_starts - 1:
                            new_solved_PRs.append(PR)

        solved_PRs = solved_PRs + new_solved_PRs

        return solved_PRs, new_solved_PRs, cost_from_start

    def update_edge_weights(
        self, min_cost: Dict[int, float], orig_graph: nx.DiGraph
    ) -> Dict[Tuple[int, str], Dict[str, float]]:
        """
            A method to update the ReactionNetwork.graph edge weights based on
            the new cost of solving PRs
        :param min_cost: dict with minimum cost from path start to a node, of
            from {node: float}, if no path exist, value is "no_path", if path
            is unsolved yet, value is "unsolved_path"
        :param orig_graph: ReactionNetwork.graph of type nx.Digraph before the
            start of current iteration of updates
        :return: attrs: dict of form {(node1, node2), {"softplus": float,
                                                       "exponent": float,
                                                       "weight: 1},
                                     (node2, node3): {...}}
                dict of all the edges to update the weights of
        """
        if len(self.graph.nodes) == 0:
            self.graph = self.build()
        if self.PR_record is None:
            self.PR_record = self.build_PR_record()

        attrs = {}
        for PR_ind in min_cost:
            for rxn_node in self.PR_record[PR_ind]:
                non_PR_reactant_node = int(rxn_node.split(",")[0].split("+PR_")[0])
                attrs[(non_PR_reactant_node, rxn_node)] = {
                    self.weight: orig_graph[non_PR_reactant_node][rxn_node][self.weight]
                    + min_cost[PR_ind]
                }

        nx.set_edge_attributes(self.graph, attrs)
        return attrs

    def final_PR_check(self, PRs: Mapping_PR_Dict):
        """
            A method to check errors in the path attributes of the PRs with a
            path, if no path then prints no path from any start to a given
        :param PRs: dict that defines a path from each node to a start, of the
            form {int(node1): {int(start1}: {ReactionPath object},
                               int(start2): {ReactionPath object}},
                  int(node2):...}
        """
        for PR in PRs:
            path_found = False
            if PRs[PR] != {}:
                for start in PRs[PR]:
                    if PRs[PR][start].cost == float("inf"):
                        PRs[PR][start] = ReactionPath(None)
                    if PRs[PR][start].path is not None:
                        path_found = True
                        path_dict_class = ReactionPath.characterize_path_final(
                            PRs[PR][start].path,
                            self.weight,
                            self.graph,
                            self.solved_PRs,
                            PRs,
                        )
                        PRs[PR][start] = path_dict_class
                        if (
                            abs(path_dict_class.cost - path_dict_class.pure_cost)
                            > 0.0001
                        ):
                            print(
                                "WARNING: cost mismatch for PR",
                                PR,
                                path_dict_class.cost,
                                path_dict_class.pure_cost,
                                path_dict_class.path_dict,
                                path_dict_class.full_path,
                            )

                if not path_found:
                    print("No path found from any start to PR", PR)
            else:
                self.unsolvable_PRs.append(PR)
                print("Unsolvable path from any start to PR", PR)
        self.PRs = PRs
        return PRs

    def remove_node(self, node_ind: List[int]):
        """
        Remove a species from self.graph. Also remove all the reaction nodes with that species.
        Used for e.g. removing Li0.
        :param: list of node numbers to remove
        """
        for n in node_ind:
            self.graph.remove_node(n)
            nodes = list(self.graph.nodes)
            for node in nodes:
                if self.graph.nodes[node]["bipartite"] == 1:
                    reactants = node.split(",")[0].split("+")
                    reactants = [reac.replace("PR_", "") for reac in reactants]
                    products = node.split(",")[1].split("+")
                    if str(n) in products:
                        if len(reactants) == 2:
                            self.PR_record[int(reactants[1])].remove(node)
                            self.graph.remove_node(node)
                            self.PR_record.pop(node, None)
                    elif str(n) in reactants:
                        if len(reactants) == 2:
                            self.PR_record[int(reactants[1])].remove(node)
                        self.Reactant_record.pop(node, None)

                        self.graph.remove_node(node)
            self.PR_record.pop(n, None)
            self.Product_record.pop(n, None)

    def find_or_remove_bad_nodes(
        self, nodes: List[int], remove_nodes=False
    ) -> Union[List[str], nx.DiGraph]:
        """
            A method to either create a list of the nodes a path solving method
            should ignore or generate a graph without all the nodes it a path
            solving method should not use in obtaining a path.
        :param nodes: List(molecular nodes), list of molecular nodes of type int
            found in the ReactionNetwork.graph
            that should be ignored when solving a path
        :param remove_nodes: if False (default), return list of bad nodes, if
            True, return a version of ReactionNetwork.graph (of type nx.Digraph)
            from with list of bad nodes are removed
        :return: if remove_nodes = False -> list[node],
                 if remove_nodes = True -> nx.DiGraph
        """
        if len(self.graph.nodes) == 0:
            self.graph = self.build()
        if self.PR_record is None:
            self.PR_record = self.build_PR_record()
        if self.Reactant_record is None:
            self.Reactant_record = self.build_reactant_record()
        bad_nodes = []
        for node in nodes:
            for bad_node in self.PR_record[node]:
                bad_nodes.append(bad_node)
            for bad_nodes2 in self.Reactant_record[node]:
                bad_nodes.append(bad_nodes2)
        if remove_nodes:
            pruned_graph = copy.deepcopy(self.graph)
            pruned_graph.remove_nodes_from(bad_nodes)
            return pruned_graph
        else:
            return bad_nodes

    def valid_shortest_simple_paths(
        self, start: int, target: int, PRs=[]
    ):  # -> Generator[List[str]]:????
        """
            A method to determine shortest path from start to target
        :param start: molecular node of type int from ReactionNetwork.graph
        :param target: molecular node of type int from ReactionNetwork.graph
        :param PRs: not used currently?
        :return: nx.path_generator of type generator
        """
        valid_graph = self.find_or_remove_bad_nodes([target], remove_nodes=True)
        valid_graph.remove_nodes_from(PRs)  # type: ignore

        return nx.shortest_simple_paths(
            valid_graph, hash(start), hash(target), weight=self.weight
        )

    def find_paths(self, starts, target, weight, num_paths=10, ignorenode=[]):  # -> ??
        """
            A method to find the shorted path from given starts to a target

        :param starts: starts: List(molecular nodes), list of molecular nodes
            of type int found in the ReactionNetwork.graph
        :param target: a single molecular node of type int found in the
            ReactionNetwork.graph
        :param weight: "softplus" or "exponent", type of cost function to use
            when calculating edge weights
        :param num_paths: Number (of type int) of paths to find. Defaults to 10.
        :return: PR_paths: solved dict of PRs
        :return: paths: list of paths (number of paths based on the value of
            num_paths)
        """

        print("find_paths start", time.time())
        self.weight = weight
        self.num_starts = len(starts)
        paths = []
        c = itertools.count()
        my_heapq = []
        if self.PRs == {}:
            print("Solving prerequisites...")
            if len(self.graph.nodes) == 0:
                self.build()
            self.solve_prerequisites(starts, weight)

        print("Finding paths...")

        remove_node = []
        for PR in self.unsolvable_PRs:
            remove_node = remove_node + self.PR_record[PR]
        ignorenode = ignorenode + remove_node
        try:
            for start in starts:
                ind = 0
                print(start, target)
                for path in self.valid_shortest_simple_paths(start, target, ignorenode):
                    # print(ind, path)
                    if ind == num_paths:
                        break
                    else:
                        ind += 1
                        path_dict_class2 = ReactionPath.characterize_path_final(
                            path, self.weight, self.graph, self.solved_PRs, self.PRs
                        )
                        heapq.heappush(
                            my_heapq, (path_dict_class2.cost, next(c), path_dict_class2)
                        )
        except Exception:
            print("no path from this start to the target", start)
        top_path_list = []
        while len(paths) < num_paths and my_heapq:
            (cost_HP, _x, path_dict_HP_class) = heapq.heappop(my_heapq)
            top_path_list.append(path_dict_HP_class.path)
            print(
                len(paths),
                cost_HP,
                path_dict_HP_class.overall_free_energy_change,
                path_dict_HP_class.hardest_step_deltaG,
                path_dict_HP_class.path_dict,
            )
            paths.append(
                path_dict_HP_class.path_dict
            )  # ideally just append the class, but for now dict for easy printing

        self.paths = paths
        self.top_path_list = top_path_list
        print("find_paths end", time.time())

        return self.PRs, paths, top_path_list

    @staticmethod
    def mols_w_cuttoff(RN_pr_solved, cutoff=0, build_pruned_network=True):
        """
        A method to identify molecules reached by dG <= cutoff

        :param RN_pr_solved: instance of reaction network
        :param: cutoff: dG value
        :param: build_pruned_network: if true a network with pruned entries will be build
        :return: mols_to_keep: list of molecule nodes that can be reached by dG <= cutoff
        :return: pruned_entries_list: list of MoleculeEntry of molecules that can be reached by dG <= cutoff
        """

        pruned_PRs = {}
        for PR_node in RN_pr_solved.PR_byproducts:
            if (
                RN_pr_solved.PRs[PR_node] != {}
                and RN_pr_solved.PR_byproducts[PR_node] != {}
            ):
                min_start = RN_pr_solved.PR_byproducts[PR_node]["start"]
                if (
                    RN_pr_solved.PRs[PR_node][min_start].overall_free_energy_change
                    <= cutoff
                ):
                    pruned_PRs[PR_node] = {}
                    pruned_PRs[PR_node][min_start] = RN_pr_solved.PRs[PR_node][
                        min_start
                    ]

        nodes_to_keep = []
        for PR_node in pruned_PRs:
            for start in pruned_PRs[PR_node]:
                nodes_to_keep = nodes_to_keep + pruned_PRs[PR_node][start].full_path

        nodes_to_keep = list(dict.fromkeys(nodes_to_keep))
        mols_to_keep = []
        for node in nodes_to_keep:
            if isinstance(node, int):
                mols_to_keep.append(node)
        mols_to_keep.sort()

        pruned_entries_list = []
        for entry in RN_pr_solved.entries_list:
            if entry.parameters["ind"] in mols_to_keep:
                pruned_entries_list.append(entry)

        if build_pruned_network:
            pruned_network_build = ReactionNetwork.from_input_entries(
                pruned_entries_list, replace_ind=False
            )
            pruned_network_build.build()
            return mols_to_keep, pruned_entries_list, pruned_network_build
        else:
            return mols_to_keep, pruned_entries_list

    @staticmethod
    def parse_reaction_node(node: str):
        """
        A method to identify reactants, PR, and prodcuts from a given reaction node string.
        :param node: string, ex. "1+PR_2,3+4"
        :return: react_list: reactant list, ex [1,2]
        :return: prod_list: product list, ex [3,4]
        """
        react_list = []
        prod_list = []
        if "PR" in node and "+" in node.split(",")[1]:
            reactant = int(node.split("+PR_")[0])
            pr = int(node.split("+PR_")[1].split(",")[0])
            product1 = int(node.split("+PR_")[1].split(",")[1].split("+")[0])
            product2 = int(node.split("+PR_")[1].split(",")[1].split("+")[1])
            react_list = [reactant, pr]
            prod_list = [product1, product2]
            prod_list.sort()
        elif "PR" in node and "+" not in node.split(",")[1]:
            reactant = int(node.split("+PR_")[0])
            pr = int(node.split("+PR_")[1].split(",")[0])
            product = int(node.split("+PR_")[1].split(",")[1])
            react_list = [reactant, pr]
            prod_list = [product]
        elif "PR" not in node and "+" in node:
            reactant = int(node.split(",")[0])
            product1 = int(node.split(",")[1].split("+")[0])
            product2 = int(node.split(",")[1].split("+")[1])
            prod_list = [product1, product2]
            prod_list.sort()
            react_list = [reactant]
            prod_list = [product1, product2]
            prod_list.sort()
        elif "PR" not in node and "+" not in node:
            reactant = int(node.split(",")[0])
            product = int(node.split(",")[1])
            react_list = [reactant]
            prod_list = [product]

        return react_list, prod_list

    @staticmethod
    def generate_node_string(combined_reactants, combined_products):
        """
        A method to genrate a reaction node string from given reactants and products.
        :param combined_reactants: list of reactant node indices, ex [1,2]
        :param combined_products: list of product node indices, ex [3,4]
        :return: node_str: string of reaction as it would be for a reaction node, ex  "1+PR_2,3+4"
        """
        node_str = None
        if len(combined_reactants) <= 2 and len(combined_products) <= 2:
            if len(combined_reactants) == 2 and len(combined_products) == 2:
                node_str = (
                    str(combined_reactants[0])
                    + "+"
                    + "PR_"
                    + str(combined_reactants[1])
                    + ","
                    + str(combined_products[0])
                    + "+"
                    + str(combined_products[1])
                )
            elif len(combined_reactants) == 2 and len(combined_products) == 1:
                node_str = (
                    str(combined_reactants[0])
                    + "+"
                    + "PR_"
                    + str(combined_reactants[1])
                    + ","
                    + str(combined_products[0])
                )
            elif len(combined_reactants) == 1 and len(combined_products) == 2:
                node_str = (
                    str(combined_reactants[0])
                    + ","
                    + str(combined_products[0])
                    + "+"
                    + str(combined_products[1])
                )
            elif len(combined_reactants) == 1 and len(combined_products) == 1:
                node_str = str(combined_reactants[0]) + "," + str(combined_products[0])
        return node_str

    @staticmethod
    def identify_concerted_rxns_via_intermediates(
        RN,
        mols_to_keep=None,
        single_elem_interm_ignore=["C1", "H1", "O1", "Li1", "P1", "F1"],
    ):
        """
            A method to identify concerted reactions via high enery intermediate molecules
        :param RN: Reaction network built
        :param mols_to_keep: List of pruned molecules, if not running then a list of all molecule nodes in the
        RN
        :param single_elem_interm_ignore: single_elem_interm_ignore: List of formula of high energy
        intermediates to ignore
        :return: list of unique reactions, list of reactions and its incoming and outgoing reaction nodes
        """

        print("identify_concerted_rxns_via_intermediates start", time.time())
        if mols_to_keep is None:
            mols_to_keep = list(range(0, len(RN.entries_list)))
        reactions = []
        unique_reactions = []
        for entry in RN.entries_list:
            (
                unique_rxns,
                rxns_with_nodes,
            ) = RN.identify_concerted_rxns_for_specific_intermediate(
                entry, RN, mols_to_keep, single_elem_interm_ignore
            )
            unique_reactions.append(unique_rxns)
            reactions.append(rxns_with_nodes)

        all_unique_reactions = reduce(operator.concat, unique_reactions)
        all_unique_reactions = list(
            map(
                lambda y: literal_eval(y),
                set(map(lambda x: repr(x), all_unique_reactions)),
            )
        )

        print("total number of unqiue concerted reactions:", len(all_unique_reactions))
        print("identify_concerted_rxns_via_intermediates end", time.time())
        return all_unique_reactions, reactions

    @staticmethod
    def identify_concerted_rxns_for_specific_intermediate(
        entry: MoleculeEntry,
        RN,
        mols_to_keep=None,
        single_elem_interm_ignore=["C1", "H1", "O1", "Li1", "P1", "F1"],
    ):

        """
            A method to identify concerted reactions via specific high enery intermediate molecule
        :param entry: MoleculeEntry to act as high energy intermediate
        :param RN: Reaction network built
        :param mols_to_keep: List of pruned molecules, if not running then a list of all molecule nodes
        in the RN_pr_solved
        :param single_elem_interm_ignore: single_elem_interm_ignore: List of formula of high energy
        intermediates to ignore
        :return: list of reactions
        """

        if mols_to_keep is None:
            mols_to_keep = list(range(0, len(RN.entries_list)))
        not_wanted_formula = single_elem_interm_ignore
        reactions_with_in_out_nodes = []
        unique_reactions = []
        node = entry.parameters["ind"]
        if (
            RN.entries_list[node].formula not in not_wanted_formula
            and RN.graph.nodes[node]["bipartite"] == 0
            and node not in RN.not_reachable_nodes
            and node not in RN.unsolvable_PRs
        ):
            out_nodes = []
            for rxn in list(RN.graph.neighbors(node)):
                if "electron" not in RN.graph.nodes[rxn]["rxn_type"]:
                    out_nodes.append(rxn)
            in_nodes = []
            for in_edge in list(RN.graph.in_edges(node)):
                in_rxn = in_edge[0]
                if "electron" not in RN.graph.nodes[in_rxn]["rxn_type"]:
                    in_nodes.append(in_rxn)
            for out_node in out_nodes:
                for in_node in in_nodes:
                    if (
                        "Concerted" in RN.graph.nodes[in_node]["rxn_type"]
                        and "Concerted" in RN.graph.nodes[out_node]["rxn_type"]
                    ):
                        pass
                    else:
                        rxn1_dG = RN.graph.nodes[in_node]["free_energy"]
                        total_dG = rxn1_dG + RN.graph.nodes[out_node]["free_energy"]
                        if rxn1_dG > 0 and total_dG < 0:
                            (
                                in_reactants,
                                in_products,
                            ) = ReactionNetwork.parse_reaction_node(in_node)
                            (
                                out_reactants,
                                out_products,
                            ) = ReactionNetwork.parse_reaction_node(out_node)
                            combined_reactants = in_reactants + out_reactants
                            combined_products = in_products + out_products
                            combined_reactants.sort()
                            combined_products.sort()
                            inter = set(combined_reactants).intersection(
                                set(combined_products)
                            )
                            for i in inter:
                                combined_reactants.remove(i)
                                combined_products.remove(i)
                            inter = set(combined_reactants).intersection(
                                set(combined_products)
                            )
                            for i in inter:
                                combined_reactants.remove(i)
                                combined_products.remove(i)
                            if (
                                0 < len(combined_reactants) <= 2
                                and 0 < len(combined_products) <= 2
                            ):
                                node_str = ReactionNetwork.generate_node_string(
                                    combined_reactants, combined_products
                                )
                                glist = combined_reactants + combined_products

                                if (
                                    node_str not in RN.graph.nodes
                                    and set().issubset(set(mols_to_keep))
                                    and set(combined_reactants)
                                    != set(combined_products)
                                ):
                                    unique_reactions.append(
                                        [combined_reactants, combined_products]
                                    )
                                    reactions_with_in_out_nodes.append(
                                        [
                                            combined_reactants,
                                            combined_products,
                                            [in_node, out_node],
                                        ]
                                    )

        # print(node, "unique reactions", len(unique_reactions))
        return unique_reactions, reactions_with_in_out_nodes

    @staticmethod
    def add_concerted_rxns(RN, reactions):
        """
            A method to add concerted reactions (obtained from identify_concerted_rxns_via_intermediates() method)to
            the ReactonNetwork
        :param RN: build Reaction Networl
        :param reactions: list of reactions obtained from identify_concerted_rxns_via_intermediates() method
        :return: reaction network with concerted reactions added
        """

        print("add_concerted_rxns start", time.time())
        c1 = 0
        c2 = 0
        c3 = 0
        c4 = 0
        mol_id_to_mol_entry_dict = {}
        for i in RN.entries_list:
            mol_id_to_mol_entry_dict[int(i.parameters["ind"])] = i
        for reaction in reactions:
            if len(reaction[0]) == 1 and len(reaction[1]) == 1:
                assert int(reaction[0][0]) in RN.graph.nodes
                assert int(reaction[1][0]) in RN.graph.nodes
                reactants = mol_id_to_mol_entry_dict[int(reaction[0][0])]
                products = mol_id_to_mol_entry_dict[int(reaction[1][0])]
                cr = ConcertedReaction([reactants], [products])
                cr.electron_free_energy = RN.temperature
                g = cr.graph_representation()
                for node in list(g.nodes):
                    if not isinstance(node, int) and g.nodes[node]["free_energy"] > 0:
                        g.remove_node(node)
                RN.add_reaction(g)
                c1 = c1 + 1
            elif len(reaction[0]) == 1 and len(reaction[1]) == 2:
                assert int(reaction[0][0]) in RN.graph.nodes
                assert int(reaction[1][0]) in RN.graph.nodes
                assert int(reaction[1][1]) in RN.graph.nodes
                reactant_0 = mol_id_to_mol_entry_dict[int(reaction[0][0])]
                product_0 = mol_id_to_mol_entry_dict[int(reaction[1][0])]
                product_1 = mol_id_to_mol_entry_dict[int(reaction[1][1])]
                cr = ConcertedReaction([reactant_0], [product_0, product_1])
                cr.electron_free_energy = RN.temperature
                g = cr.graph_representation()
                for node in list(g.nodes):
                    if not isinstance(node, int) and g.nodes[node]["free_energy"] > 0:
                        g.remove_node(node)
                RN.add_reaction(g)
                c2 = c2 + 1
            elif len(reaction[0]) == 2 and len(reaction[1]) == 1:
                assert int(reaction[0][0]) in RN.graph.nodes
                assert int(reaction[0][1]) in RN.graph.nodes
                assert int(reaction[1][0]) in RN.graph.nodes
                reactant_0 = mol_id_to_mol_entry_dict[int(reaction[0][0])]
                PR = mol_id_to_mol_entry_dict[int(reaction[0][1])]
                product_0 = mol_id_to_mol_entry_dict[int(reaction[1][0])]
                cr = ConcertedReaction([reactant_0, PR], [product_0])
                cr.electron_free_energy = RN.temperature
                g = cr.graph_representation()
                for node in list(g.nodes):
                    if not isinstance(node, int) and g.nodes[node]["free_energy"] > 0:
                        g.remove_node(node)
                RN.add_reaction(g)
                c3 = c3 + 1
            elif len(reaction[0]) == 2 and len(reaction[1]) == 2:
                assert int(reaction[0][0]) in RN.graph.nodes
                assert int(reaction[0][1]) in RN.graph.nodes
                assert int(reaction[1][0]) in RN.graph.nodes
                assert int(reaction[1][1]) in RN.graph.nodes
                reactant_0 = mol_id_to_mol_entry_dict[int(reaction[0][0])]
                PR = mol_id_to_mol_entry_dict[int(reaction[0][1])]
                product_0 = mol_id_to_mol_entry_dict[int(reaction[1][0])]
                product_1 = mol_id_to_mol_entry_dict[int(reaction[1][1])]
                cr = ConcertedReaction([reactant_0, PR], [product_0, product_1])
                cr.electron_free_energy = RN.temperature
                g = cr.graph_representation()
                for node in list(g.nodes):
                    if not isinstance(node, int) and g.nodes[node]["free_energy"] > 0:
                        g.remove_node(node)
                RN.add_reaction(g)
                c4 = c4 + 1
        total_num_concerted = c1 + c2 + c3 + c4
        RN.PR_record = RN.build_PR_record()
        RN.Reactant_record = RN.build_reactant_record()
        print("number of concerted reactions added", total_num_concerted)
        print("add_concerted_rxns end", time.time())
        return RN

    def as_dict(self) -> dict:
        entries = dict()  # type: Dict[str, Dict[int, Dict[int, List[Dict[str, Any]]]]]
        for formula in self.entries.keys():
            entries[formula] = dict()
            for bonds in self.entries[formula].keys():
                entries[formula][bonds] = dict()
                for charge in self.entries[formula][bonds].keys():
                    entries[formula][bonds][charge] = list()
                    for entry in self.entries[formula][bonds][charge]:
                        entries[formula][bonds][charge].append(entry.as_dict())

        entries_list = [e.as_dict() for e in self.entries_list]

        reactions = [r.as_dict() for r in self.reactions]

        d = {
            "@module": self.__class__.__module__,
            "@class": self.__class__.__name__,
            "entries_dict": entries,
            "entries_list": entries_list,
            "reactions": reactions,
            "electron_free_energy": self.electron_free_energy,
            "temperature": self.temperature,
            "solvent_dielectric": self.solvent_dielectric,
            "solvent_refractive_index": self.solvent_refractive_index,
            "graph": json_graph.adjacency_data(self.graph),
            "PR_record": self.PR_record,
            "min_cost": self.min_cost,
            "num_starts": self.num_starts,
            "PRs": self.PRs,
        }

        return d

    @classmethod
    def from_dict(cls, d):

        entries = dict()
        d_entries = d["entries_dict"]
        for formula in d_entries.keys():
            entries[formula] = dict()
            for bonds in d_entries[formula].keys():
                int_bonds = int(bonds)
                entries[formula][int_bonds] = dict()
                for charge in d_entries[formula][bonds].keys():
                    int_charge = int(charge)
                    entries[formula][int_bonds][int_charge] = list()
                    for entry in d_entries[formula][bonds][charge]:
                        entries[formula][int_bonds][int_charge].append(
                            MoleculeEntry.from_dict(entry)
                        )

        entries_list = [MoleculeEntry.from_dict(e) for e in d["entries_list"]]

        reactions = list()
        for reaction in d["reactions"]:
            rclass = load_class(str(cls.__module__), reaction["@class"])
            reactions.append(rclass.from_dict(reaction))

        graph = json_graph.adjacency_graph(d["graph"], directed=True)

        return cls(
            d["electron_free_energy"],
            d["temperature"],
            d["solvent_dielectric"],
            d["solvent_refractive_index"],
            entries,
            entries_list,
            graph,
            reactions,
            d.get("PR_record", dict()),
            d.get("PRs", dict()),
            d.get("min_cost", dict()),
            d["num_starts"],
        )
