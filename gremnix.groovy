if (args.size() != 1) {
    println("error: no GraphML file provided!")
    println("usage: ")
    println(" \$ gremnix file.graphml")
    System.exit(1)
}

graphFilename = args[0]
graphFilename = graphFilename.replaceFirst("^~", System.getProperty("user.home"))
if (! new File(graphFilename).isAbsolute()) {
    graphFilename = System.getProperty("user.working_dir") + "/" +  graphFilename
}


GraphTraversalSource.metaClass.root = { delegate.V().not(where(__.in())) };

GraphTraversal.metaClass.byName = {
    n -> return delegate.filter({ it.get().values("name").next().contains(n) })
}

GraphTraversal.metaClass.derivation = { delegate.has("type", "derivation") }

GraphTraversal.metaClass.outputPath = { delegate.has("type", "output-path") }

GraphTraversal.metaClass.pathsToParent = {
    n -> return delegate.repeat(__.in().simplePath()).until(hasId(n)).path()
}

GraphTraversal.metaClass.closure = { return delegate.repeat(out()).emit().dedup() }

GraphTraversal.metaClass.mb = { return delegate.map{ it.get() / 1000000 } }

printf("\nNix Helpers\n")
println("  byName(name)         filter store paths that contains 'name' string in their nameby name")
println("  root()               filter root store paths")
println("  derivation()         filter derivation store paths ")
println("  outputPath()         filter output path store paths ")
println("  pathsToParent(root)  return paths to 'root' store path")
println("  closure()            return all closure path")
println("  mb()                 convert bytes to MB")

printf("\nLoading the graphml file '%s'...\n", graphFilename)

g = TinkerGraph.open();
g.io(graphml()).readGraph(graphFilename);
g = g.traversal()

printf("gremlin> g\n")
printf("==>%s\n", g)