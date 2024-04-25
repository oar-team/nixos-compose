class Flavour(object):
    name: str

    def __init__(self, ctx):
        self.ctx = ctx

    # def check(self, state="running"):
    #     self.ctx.wlog(f"Check not implement for flavour: {self.name}")
    #     return -1

    # def wait_on_check(self, state="running", mode="all", period=0.5, round=5):
    #     for _ in range(round):
    #         if mode == "all" and self.check(state) == len(self.machines):
    #             return True
    #         elif mode == "any" and self.check(state) > 0:
    #             return
    #         time.sleep(period)
    #     return False

    def generate_deployment_info(self, ssh_pub_key_file=None):
        pass

    def initialize_driver(self, ctx, start_scripts, tests, keep_vm_state):
        pass
