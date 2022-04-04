{ self }:
final: prev: {
  nixos-compose = self.packages.${prev.system}.nixos-compose;
  nixos-compose-full = self.packages.${prev.system}.nixos-compose-full;
}
