In this part we will see how to install _NixOS Compose_ locally and on Grid5000.


The installation and usage differs a bit on Grid5000 due to policy usage restrictions and non Nix first class support.

The use of the `nxc` command line tool can be achieve in multiple ways and it will depends at which step in the process of the experiment you are. 
At the initialization of a project you will need Nix package manager and NixOSCompose project. Once an experiment is bundled (after `nxc init`) it comes with a mean to access to the nxc command through a shell provided by Nix. There is also the possibility to use an incomplete version of `nxc` when a Nix shell becomes a constraints to access testbeds platform tools, it is the case on Grid5000 (oar commands are not available in a nix shell).

Nix dependant commands : [ init build ]

Nix independent commands : [ start connect stop ]
