historic of command

# installation de nix
installation multi user, recomendé par le site nix
```
sh <(curl -L https://nixos.org/nix/install) --daemon
```

création de `.config/nix/nix.conf`

Flake support
```
echo "experimental-features = nix-command flakes" > ~/.config/nix/nix.conf
```

clonnage de nixos compose
```
git clone nixoscompose
```
Ensuite ici on a la choix ou pas ? 



## help on vagrant....
quand je supprime une vm...
il se peux qu'il y ai des reste... genre domaine

```
sudo virsh list --all
sudo virsh undefine fedora_default
```