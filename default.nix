with import (builtins.fetchGit { url = https://github.com/NixOS/nixpkgs-channels.git; ref = "nixos-unstable"; }) {};

writeShellScriptBin "gremnix" ''
   set -e
   GREMNIX_NIX_STORE=''${GREMNIX_NIX_STORE:-${nixUnstable}/bin/nix-store}
   FILE=$(mktemp --suffix .graphml)
   echo "Executing $GREMNIX_NIX_STORE -q --graphml $@ > $FILE"
   $GREMNIX_NIX_STORE -q --graphml $@ > $FILE
   ${gremlin-console}/bin/gremlin-console gremlin-console -i ${./gremnix.groovy} $FILE
''
