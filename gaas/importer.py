# out edges of V are the requires of V

import networkx

from gremlin_python import statics
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import __, select, where
from gremlin_python.process.strategies import *
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.traversal import T
from gremlin_python.process.traversal import Order
from gremlin_python.process.traversal import Cardinality
from gremlin_python.process.traversal import Column
from gremlin_python.process.traversal import Direction
from gremlin_python.process.traversal import Operator
from gremlin_python.process.traversal import P
from gremlin_python.process.traversal import Pop
from gremlin_python.process.traversal import Scope
from gremlin_python.process.traversal import Barrier
from gremlin_python.process.traversal import Bindings
from gremlin_python.process.traversal import WithOptions, eq
from gremlin_python.driver.client import Client

import subprocess
import tempfile
import argparse

import json

import requests
import os.path
import time

parser = argparse.ArgumentParser(description='Importer')
parser.add_argument('revision', metavar='REVISION', type=str,
                    help='revision')
parser.add_argument('--no-prune', action='store_true')
parser.add_argument('--data-dir', type=str, default="/tmp/gremnix")
parser.add_argument('--repository-dir', type=str, required=True, help="The directory containing the repository to consider")
args = parser.parse_args()

data_dir = args.data_dir

def derivation_from_hydra_jobs(filename):
    with open(filename, "r") as read_file:
        data = json.load(read_file)
    return [ v['drvPath'] for k, v in data.items() if 'drvPath' in v ]

# Get last 10 evals from NixOS/nixpkgs hydra and store them in
# data_gremnix/nixpkgs-evals.json
def get_evals_from_hydra():
    headers = {'Accept': 'application/json'}
    resp = requests.get(url="https://hydra.nixos.org/jobset/nixpkgs/trunk/evals", headers=headers)
    data = resp.json()
    with open(data_dir + "/nixpkgs-evals.json", "w") as f:
        json.dump(resp.json(), f)

def eval_nixpkgs(revision):
    eval_filepath = data_dir + "/" + revision + ".json"
    if os.path.isfile(eval_filepath):
        print("Evaluation file %s already exists" % eval_filepath)
        return
    p=subprocess.run(["git", "-C", args.repository_dir, "checkout", revision])
    if p.returncode != 0:
        print("Running git fetch origin...")
        subprocess.run(["git", "-C", args.repository_dir, "fetch", "origin"])
        p=subprocess.run(["git", "-C", args.repository_dir, "checkout", revision])
    if p.returncode != 0:
        print("Unexepected error when checking out nixpkgs!")
        exit(1)
    print("Running hydra-eval-jobs...")
    p=subprocess.run(["/nix/store/4wkh88868x4lrv2gwb1602lqk62hdwqx-hydra-eval-nixpkgs-jobs/bin/hydra-eval-nixpkgs-jobs", args.repository_dir], stdout=subprocess.PIPE)
    with open(eval_filepath, "w") as f:
        f.write(p.stdout.decode('utf-8'))
        
def graphml(derivations):
    result = subprocess.run(['nix-store', '-q', '--graphml' ] + derivations, stdout=subprocess.PIPE)
    temp = tempfile.NamedTemporaryFile(mode='w+t')
    temp.write(result.stdout.decode('utf-8'))
    temp.seek(0)

    g = networkx.graphml.read_graphml(temp.name)
    temp.close()
    return g

# From a revision, read the json file containing Hydra jobs of this
# revision and generate a graphml file.
def graphml_from_hydra_jobs(revision):
    jobs_filepath =  data_dir + "/" + revision + ".json"
    graphml_filepath =  data_dir + "/" + revision + ".graphml"

    if os.path.isfile(graphml_filepath):
        print("Graphml file %s already exists" % graphml_filepath)
        return networkx.graphml.read_graphml(graphml_filepath)

    drvs = derivation_from_hydra_jobs(jobs_filepath)
    print("%s derviation loaded from Hydra jobs file %s" % (len(drvs), jobs_filepath))

    # FIXME
    # This is because we cannot provide more than 1000 drv as Linux command arguments.
    g = networkx.DiGraph()
    for i in range(0,len(drvs), 1000):
        print("Generating partial graphml file (%d:%d)" % (i, len(drvs)))
        tmp = graphml(drvs[i:i+1000-1])
        g = networkx.compose(g, tmp)
    print("Writing graphml file %s" % graphml_filepath)
    networkx.graphml.write_graphml(g, graphml_filepath)
    return g

def init_janus():
    print("Initialization of Janus database")
    client = Client("ws://localhost:8182/gremlin", 'g')
    create_indexes = """
graph.tx().rollback()  //Never create new indexes while a transaction is active
mgmt = graph.openManagement();
if (!mgmt.getGraphIndex("byPathUnique")) {
  path = mgmt.makePropertyKey('path').dataType(String.class).cardinality(SINGLE).make(); 
  mgmt.buildIndex('byPathUnique', Vertex.class).addKey(path).unique().buildCompositeIndex()

  mgmt.makeVertexLabel('derivation').make()
  mgmt.makeEdgeLabel('require').multiplicity(SIMPLE).make()

  mgmt.commit()
}
"""

    result_set = client.submit(create_indexes)
    future_results = result_set.all()
    results = future_results.result()
    client.close()

def get_new_nodes(graph, roots):
    visited_nodes = set()
    new_nodes = set()

    print("Connecting to Gremlin")
    gremlin = traversal().withRemote(DriverRemoteConnection('ws://localhost:8182/gremlin','g'))

    def already_loaded(n):
        return gremlin.V().has('path', n).hasNext()

    # The goal is to minimize the number of call to gremlin. This
    # checks which nodes are not in the graph. If a node is in the
    # graph, we consider the whole closure is also in the graph.
    def prune(graph, requires, assume_already_loaded=False):
        for r in requires:
            if r not in visited_nodes and r not in new_nodes:
                print("Visited nodes: %d - new nodes: %d\r" % (len(visited_nodes), len(new_nodes)), end='')
                if assume_already_loaded or already_loaded(r):
                    visited_nodes.update([r])
                    prune(graph, [e[1] for e in graph.edges(r) if e[0] == r], assume_already_loaded=True)
                else:
                    new_nodes.update([r])
                    prune(graph, [e[1] for e in graph.edges(r) if e[0] == r])

    print("Starting to prune the graph which have %d roots" % len(roots))
    prune(graph, roots)
    print("\n%d have been visited nodes to prune the graph" % len(visited_nodes))
    print("%d new nodes has to be added to the graph" % len(new_nodes))
    return new_nodes

def load_graph_into_janus(graph, nodes):
    print("Connecting to Gremlin")
    gremlin = traversal().withRemote(DriverRemoteConnection('ws://localhost:8182/gremlin','g'))
    client = Client("ws://localhost:8182/gremlin", 'g')
    
    def addV(gremlin, nodes, start, total_nodes_added):
        print("%d nodes already loaded in %f\r" % (total_nodes_added, (time.time() - start)), end = '')
        gremlin.inject(nodes).unfold().as_('a').addV('derivation').property('path', select('a')).iterate()
        
    # 500 doens't work: Hit Max frame length of 65536 has been exceeded .
    step = 100
    print("Graph nodes and edges batch size: %d" % step)

    start = time.time()
    acc = []
    total_nodes_added = 0
    for (i, n) in enumerate(nodes):
        acc += [n]
        total_nodes_added += 1
        if len(acc) == step:
            addV(gremlin, acc, start, total_nodes_added)
            acc = []
    if acc != []:
        addV(gremlin, acc, start, total_nodes_added)
    print("\n%d nodes loaded in %fs" % (total_nodes_added, time.time() - start))

    def addE(client, edges, start, index, total_edges_added):
        print("Loading edges for nodes %d - %d edges loaded in %f\r" % (index, total_edges_added, (time.time() - start)), end = '')
        # This one creates too much edges...
        # gremlin.inject(acc).unfold().as_('e').V().has('path', select('e').select('dst')).as_('d').V().has('path', select('e').select('src')).addE('require').to('d').iterate()
        # This one crash the janus graph server
        # gremlin.inject(acc).unfold().as_('e').select('src').as_('src').select('e').select('dst').as_('dst').V().has('path', __.where(eq('src'))).as_('src').V().has('path', __.where(eq('dst'))).addE('require').from_('src').iterate()
        client.submit("data.each { " +
                      "g.inject(1).V().has('path', it.dst).as('d').V().has('path',it.src).coalesce(__.out().has('path', it.dst), __.addE('require').to('d')).iterate()" +
                      "}", {"data" : edges}).all().result()
        
    start = time.time()
    acc = []
    total_edges_added = 0
    for (i, n) in enumerate(nodes):
        for e in graph.edges(n):
            if e[0] != n:
                continue
            acc += [{'src':e[0], 'dst': e[1]}]
            total_edges_added += 1
            if len(acc) == step:
                addE(client, acc, start, i, total_edges_added)
                acc = []
    if acc != []:
        addE(client, acc, start, i, total_edges_added)
    print("\n%d edges loaded in %fs" % (total_edges_added, time.time() - start))

    

def run():
    revision = args.revision
    eval_nixpkgs(revision)
    start = time.time()
    g = graphml_from_hydra_jobs(revision)
    print("%ds to load the graphml file" % int(time.time() - start))
    print("The graph contains %d nodes and %d edges" % (len(g.nodes), len(g.edges)))

    init_janus()

    nodes = g.nodes()
    if not args.no_prune:
        start = time.time()
        roots = [n for n,d in g.in_degree() if d==0]
        print("%ds to get roots" % int(time.time() - start))
        
        start = time.time()
        nodes = get_new_nodes(g, roots)
        print("%ds to get new nodes" % int(time.time() - start))
    
    load_graph_into_janus(g, nodes)

run()
