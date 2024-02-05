This command is used to start a set of machines described in a deployment. It takes one positional argument in the yaml format to know how many instance of each role are expected. For instance the command `nxc start nodes.yaml`, with the file `nodes.yaml` written as this

```yaml
nfsServerNode: 1
nfsClientNode: 2
```

would instanciate two nodes with the role `nfsClientNode` and one only with the role `nfsServerNode`. Of course, these roles need to have been described beforhand in a `composition.nix` file.