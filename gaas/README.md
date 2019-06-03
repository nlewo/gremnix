
1. Run the janusgraph container:
   docker run -p 8182:8182   --name janusgraph-default  -v /tmp/janusgraph-data/:/opt/janus  graph/db/ -e janusgraph.storage.backend=embeddedcassandra -e janusgraph.storage.conf-file='conf/cassandra/cassandra.yaml' janusgraph/janusgraph:latest

2. Run the nix shell

3. source the venv in gaas/venv
   python  importer.py b3221e3 --repository-name nixpkgs-cloudwatt --repository-dir /tmp/gremnix/nixpkgs-cloudwatt --hydra-eval-jobs /nix/store/wyfmhgmvpwivpsw4825655qvrx8xbhsm-hydra-eval-nixpkgs-cloudwatt-jobs/bin/hydra-eval-nixpkgs-cloudwatt-jobs
        


It takes about 18min to load a nixpgs evaluation from scratch
(no-prune) and less than 2 min for nixpkgs-cloudwatt.

