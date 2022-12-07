{ pkgs, ... }: {
  roles = {
    node = { pkgs, ... }: {
      environment.systemPackages = [ pkgs.nur.repos.kapack.npb pkgs.openmpi];
      # Allow root yo use open-mpi
      environment.variables.OMPI_ALLOW_RUN_AS_ROOT = "1";
      environment.variables.OMPI_ALLOW_RUN_AS_ROOT_CONFIRM = "1";
    };
  };
  # By default node1 et and node2 will deployed
  rolesDistribution = { node = 2; };
  testScript = ''
    node1.execute('echo -en "node1\nnode2" > nodes.txt')
    node1.succeed('mpirun --hostfile nodes.txt --mca btl tcp,self cg.A.mpi | grep SUCCESSFUL')
  '';
}
