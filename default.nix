with import (builtins.fetchGit { url = https://github.com/NixOS/nixpkgs-channels.git; ref = "nixos-18.09"; }) {};

with pkgs;

let gremlin = stdenv.mkDerivation rec {
  name = "gremlin-console-${version}";
  version = "3.3.3";
  src = fetchzip {
    url = "http://www-eu.apache.org/dist/tinkerpop/${version}/apache-tinkerpop-gremlin-console-${version}-bin.zip";
    sha256 = "1yhcqxivs9jx0pc9wr4ywav37zf69wh5d99g1nali635cjkn0hg7";
  };
  buildInputs = [ makeWrapper ];
  installPhase = ''
    mkdir -p $out/opt
    cp -r ext lib $out/opt/
    install -D bin/gremlin.sh $out/opt/bin/gremlin-console
    makeWrapper $out/opt/bin/gremlin-console $out/bin/gremlin-console \
      --prefix PATH ":" "${openjdk}/bin/" \
      --set CLASSPATH "$out/opt/lib/"
  '';
  };

in writeShellScriptBin "gremnix" ''
   set -e
   GREMNIX_NIX_STORE=''${GREMNIX_NIX_STORE:-nix-store}
   FILE=$(mktemp --suffix .graphml)
   echo "Executing $GREMNIX_NIX_STORE -q --graphml $@ > $FILE"
   $$GREMNIX_NIX_STORE -q --graphml $@ > $FILE
   ${gremlin}/bin/gremlin-console gremlin-console -i ${./gremnix.groovy} $FILE
''
