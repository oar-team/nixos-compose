{
  # funtion to multiple node based on the same configuration
  makeMany = base_conf: (makeManyByIf (id: base_conf))

  # funtion to multiple node based on the same configuration
  makeManyById = base_conf_by_id: name: count:
    let
      f = n: s:
        if n == 0 then
          s
        else
          f (n - 1) (s // { "${name}${toString n}" = (base_conf_by_id id); });
    in f count { };
}
