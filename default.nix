with import (builtins.fetchGit { url = https://github.com/NixOS/nixpkgs-channels.git; ref = "nixos-18.09"; }) {};

with pkgs;

let

gremlin = stdenv.mkDerivation rec {
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

# To get latest graphml patches
nixUnstable = pkgs.nixUnstable.overrideAttrs (old: {
  src = fetchFromGitHub {
    owner = "NixOS";
    repo = "nix";
    rev = "d506342aa2b6945899988878b7c58de683cb573a";
    sha256 = "12z7v1vpr4sv9m7026gxdxazxvcrxhs0i8ifywf6axlngc5lyzzk";
  };
});

in writeShellScriptBin "gremnix" ''
   set -e
   GREMNIX_NIX_STORE=''${GREMNIX_NIX_STORE:-${nixUnstable}/bin/nix-store}
   FILE=$(mktemp --suffix .graphml)
   echo "Executing $GREMNIX_NIX_STORE -q --graphml $@ > $FILE"
   $GREMNIX_NIX_STORE -q --graphml $@ > $FILE
   ${gremlin}/bin/gremlin-console gremlin-console -i ${./gremnix.groovy} $FILE
''
