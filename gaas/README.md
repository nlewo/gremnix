
1. Run the janusgraph container:
   docker run -p 8182:8182 --name janusgraph-default janusgraph/janusgraph:latest

2. Genreate a list of jobs with hydra-eval-nixpkgs-jobs from default.nix

3. Run python importer.py derivation
   source the venv in gaas/venv
