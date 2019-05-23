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
parser.add_argument('--hydra-eval-jobs', type=str, required=True, help="The hydra-eval-job scrip to use")
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
    p=subprocess.run([args.hydra_eval_jobs, args.repository_dir], stdout=subprocess.PIPE)
    if p.returncode != 0:
        print("Error while running %s %s" % (args.hydra_eval_jobs, args.repository_dir))
        exit(1)
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
        g = networkx.graphml.read_graphml(graphml_filepath)
    else:
        drvs = derivation_from_hydra_jobs(jobs_filepath)
        print("%s derviation loaded from Hydra jobs file %s" % (len(drvs), jobs_filepath))

        # FIXME
        # This is because we cannot provide more than 1000 drvs as Linux command arguments.
        g = networkx.DiGraph()
        for i in range(0,len(drvs), 1000):
            print("Generating partial graphml file (%d:%d)" % (i, len(drvs)))
            tmp = graphml(drvs[i:i+1000-1])
            g = networkx.compose(g, tmp)

        g = enhance_graph(g)

        print("Writing graphml file %s" % graphml_filepath)
        networkx.graphml.write_graphml(g, graphml_filepath)
    return g

# FIXME: This could/should be supported by nix --graphml output
# This does 2 things:
#
# 1. If a node is a derivation, get all of its outputs. For each
# outputs, a node is created and the drv is linked to these nodes with
# an edge of type 'output'.
#
# 2. For each node, add the hash, name, pname and version.
def enhance_graph(graph):
    print("Enriching nodes of the graph")
    ln = list([ k for k, v in graph.nodes(data=True) if v["type"] == "derivation"])
    step = 1000
    for i in range(0,len(ln), step):
        print("%d/%d\r" % (i, len(ln)), end="")
        p=subprocess.run(["nix", "show-derivation"] + ln[i:i+step], stdout=subprocess.PIPE)
        if p.returncode != 0:
            print("Unexepected error when nix show-derivation")
            exit(1)
        d = json.loads(p.stdout.decode('utf-8'))
        for n in d:
            for k, v in d[n]["outputs"].items():
                graph.add_node(v["path"], type="output-path")
                graph.add_edge(n, v["path"], type = "output", name = k)
            
    for n, v in graph.nodes(data=True):
        a = os.path.basename(n)
        b = a.split("-")
        if v["type"] == "derivation":
            if len(b) == 2:
                pname = "-".join(b[-1:])
                # FIXME find a better way
                version = "null"
            else:
                pname = "-".join(b[1:-1])
                version = "-".join(b[-1:])
            attrs = {
                "hash": b[0],
                "pname": pname,
                "version": version
            }
        else:
            name = "-".join(b[1:])
            attrs = {
                "hash": b[0],
                "name": name,
                # FIXME: We still add them to easily add node but this
                # should be removed.
                "pname": "null",
                "version": "null",
            }
            
        networkx.set_node_attributes(graph, { n: attrs })

    return graph
                
def init_janus():
    print("Initialization of Janus database")
    client = Client("ws://localhost:8182/gremlin", 'g')
    create_indexes = """
graph.tx().rollback()  //Never create new indexes while a transaction is active
mgmt = graph.openManagement();
// TODO: improve this
if (!mgmt.getGraphIndex("byHashUnique")) {
  hash = mgmt.makePropertyKey('hash').dataType(String.class).cardinality(SINGLE).make(); 
  mgmt.buildIndex('byHashUnique', Vertex.class).addKey(hash).unique().buildCompositeIndex()

  name = mgmt.makePropertyKey('name').dataType(String.class).cardinality(SINGLE).make(); 
  mgmt.buildIndex('byName', Vertex.class).addKey(name).buildCompositeIndex()

  pname = mgmt.makePropertyKey('pname').dataType(String.class).cardinality(SINGLE).make(); 
  mgmt.buildIndex('byPName', Vertex.class).addKey(pname).buildCompositeIndex()

  version = mgmt.makePropertyKey('version').dataType(String.class).cardinality(SINGLE).make(); 
  mgmt.buildIndex('byVersion', Vertex.class).addKey(version).buildCompositeIndex()

  commitId = mgmt.makePropertyKey('commitId').dataType(String.class).cardinality(SINGLE).make(); 
  mgmt.buildIndex('byCommitId', Vertex.class).addKey(commitId).buildCompositeIndex()

  attrName = mgmt.makePropertyKey('attrName').dataType(String.class).cardinality(SINGLE).make(); 
  mgmt.buildIndex('byAttrName', Vertex.class).addKey(attrName).buildCompositeIndex()

  mgmt.makeVertexLabel('derivation').make()
  mgmt.makeVertexLabel('job').make()
  mgmt.makeEdgeLabel('instantiation').multiplicity(SIMPLE).make()
  mgmt.makeEdgeLabel('reference').multiplicity(SIMPLE).make()
  mgmt.makeEdgeLabel('output').multiplicity(SIMPLE).make()

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
        return gremlin.V().has('hash', graph.nodes[n]["hash"]).hasNext()

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
        for n in nodes:
            if "pname" not in n:
                print(n)
        print("%d nodes loaded in %f\r" % (total_nodes_added, (time.time() - start)), end = '')
        t = gremlin.inject(nodes).unfold().as_('a').addV(select('a').select('type'))
        t = t.property('hash', select('a').select('hash'))
        t = t.property('name', select('a').select('name'))
        t = t.property('pname', select('a').select('pname'))
        t = t.property('version', select('a').select('version'))
        t.iterate()
        
    # 500 doens't work: Hit Max frame length of 65536 has been exceeded .
    step = 100
    print("Graph nodes and edges batch size: %d" % step)

    start = time.time()
    acc = []
    total_nodes_added = 0
    for (i, n) in enumerate(nodes):
        acc += [graph.nodes[n]]
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
                      "g.inject(1).V().has('hash', it.dst).as('d').V().has('hash',it.src).coalesce(__.out().has('hash', it.dst), __.addE(it.label).to('d')).iterate()" +
                      "}", {"data" : edges}).all().result()
        
    start = time.time()
    acc = []
    total_edges_added = 0
    for (i, n) in enumerate(nodes):
        for e in graph.edges(n):
            if e[0] != n:
                continue
            acc += [{
                'src':graph.nodes[e[0]]["hash"],
                'dst': graph.nodes[e[1]]["hash"],
                'label': graph[e[0]][e[1]].get("type", "reference")}]
            total_edges_added += 1
            if len(acc) == step:
                addE(client, acc, start, i, total_edges_added)
                acc = []
    if acc != []:
        addE(client, acc, start, i, total_edges_added)
    print("\n%d edges loaded in %fs" % (total_edges_added, time.time() - start))

def load_evaluation(revision):
    print("Connecting to Gremlin")
    gremlin = traversal().withRemote(DriverRemoteConnection('ws://localhost:8182/gremlin','g'))

    with open(data_dir + "/" + revision + ".json", "r") as read_file:
        data = json.load(read_file)
    
    l = [{"attrName": k, "hash": os.path.basename(v["drvPath"]).split("-")[0]} for k, v in data.items()]
    n = len(l)
    step = 100
    for i in range(0, n, step):
        print("Load batch of jobs %d-%d/%d\r" % (i, i + step, n), end="")
        gremlin.inject(l[i:i+step]).unfold().as_("m").\
            coalesce(__.V().has("commitId", revision).has("attrName", select("m").select("attrName")), __.addV("job").property("commitId", revision).property("attrName", select("m").select("attrName"))).as_('j').\
            V().has("hash", l[i]["hash"]).\
            coalesce(__.inE("instantiation"), __.addE("instantiation").from_("j")).\
            iterate()
    print()

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
    load_evaluation(revision)

run()
