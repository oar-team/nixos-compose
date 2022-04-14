{ pkgs }:
with pkgs.writers;
{
  test0-python3 = writePython3Bin "test0-python3" { libraries = [ pkgs.python3Packages.pyyaml ]; } ''
    import yaml

    y = yaml.safe_load("""
      - test: success
    """)
    print(y[0]['test'])
  '';
  test1-python3 = writePython3Bin "test1-python3" { libraries = [ pkgs.python3Packages.pyyaml ]; }
    (builtins.readFile ./test_python.py);
  test-bash = writeBashBin "test-bash" ''
    if [[ "test" == "test" ]]; then echo "success"; fi
  '';
}
