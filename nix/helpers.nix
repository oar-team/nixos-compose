rec {
  # funtion to multiple node based on the same configuration
  makeManyById = base_conf_by_id: name: count:
    let
      f = n: s:
        if n == 0 then
          s
        else
          f (n - 1) (s // { "${name}${toString n}" = (base_conf_by_id n); });
    in f count { };

  # funtion to multiple node based on the same configuration, providing an id to base_conf
  makeMany = base_conf: (makeManyById (id: base_conf));
}
