with rec {
  pkgs = import <nixpkgs>{};
};
{
  hydra-eval-jobs = pkgs.writeScriptBin "hydra-eval-nixpkgs-jobs" ''
    NIXPKGS=$(${pkgs.nix}/bin/nix add-to-store $1)
    ${pkgs.hydra}/bin/hydra-eval-jobs '<nixpkgs/pkgs/top-level/release.nix>' -I nixpkgs=$NIXPKGS --arg officialRelease false
  '';
}




