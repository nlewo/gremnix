# out edges of V are the requires of V

import networkx

from gremlin_python import statics
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import __
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
from gremlin_python.process.traversal import WithOptions
from gremlin_python.driver.client import Client

import subprocess
import tempfile
import argparse

parser = argparse.ArgumentParser(description='Importer')
parser.add_argument('derivations', metavar='DERIVATION', type=str, nargs='+',
                    help='derivations')
args = parser.parse_args()

print("Generating a graphml file for %s" % " ".join(args.derivations))
result = subprocess.run(['nix-store', '-q', '--graphml' ] + args.derivations, stdout=subprocess.PIPE)
temp = tempfile.NamedTemporaryFile(mode='w+t')
temp.write(result.stdout.decode('utf-8'))
temp.seek(0)

print("Loading graph from graphml")
g = networkx.graphml.read_graphml(temp.name)
temp.close()

print("Initialization of Janus database")
client = Client("ws://localhost:8182/gremlin", 'g')
create_indexes = """
graph.tx().rollback()  //Never create new indexes while a transaction is active
mgmt = graph.openManagement();
if (!mgmt.getGraphIndex("byPathUnique")) {
  path = mgmt.makePropertyKey('path').dataType(String.class).cardinality(SINGLE).make(); 
  mgmt.buildIndex('byPathUnique', Vertex.class).addKey(path).unique().buildCompositeIndex()
  mgmt.commit()
}
"""
result_set = client.submit(create_indexes)
future_results = result_set.all()
results = future_results.result()
client.close()

print("Connecting to Gremlin")
gremlin = traversal().withRemote(DriverRemoteConnection('ws://localhost:8182/gremlin','g'))

chunk_size = 1
print ("Adding %s nodes..." % len(g.nodes()))
for n in g.nodes():
    gremlin.inject(0).coalesce(__.V().has('path', n), __.addV("derivation").property("path", n)).iterate()

print ("Adding %s edges..." % len(g.edges()))
for e in g.edges():
    gremlin.V().has('path', e[1]).as_('d').V().has('path',e[0]).coalesce(__.out().has('path', e[1]), __.addE('require').to('d')).iterate()
