{
  name = "vm";
  description = "Plain vm ramdisk (all-in-memory), need lot of ram !";
  vm = true;
  image = {
    type = "ramdisk";
    distribution = "all-in-one";
  };
}
