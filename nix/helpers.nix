{
  # funtion to multiple node based on the same configuration
  makeMany = base_conf: name: count:
    let
      f = n: s:
        if n == 0 then
          s
        else
          f (n - 1) (s // { "${name}${toString n}" = base_conf; });
    in f count { };
}
