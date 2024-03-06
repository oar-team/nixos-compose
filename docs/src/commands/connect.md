`nxc connect` 

Opens one or more terminal sessions into the deployed nodes. By default, it will connect to all nodes, but we can specify which ones to connect to.

To connect to several machines at once. For this, we use a tmux (terminal multiplexer) session. Feel free to refer to the [tmux documentation](https://github.com/tmux/tmux/wiki) (or its [cheatsheet](https://tmuxcheatsheet.com/)), especially for the shortcuts to navigate between the different tabs.

## Examples

- `nxc connect`

    Open a Tmux session with on panel for each node.

- `nxc connect server`

    Connect to the `server` node. It runs on the current shell (Tmux is not used in this case)

## Options

- `-g, --geometry`

    Tmux geometry, 2 splitting indications are supported: +/\*.

    Examples: "1+3+2" (3 successive panes respectively horizontally spited by 1,3 and 2), "2\*3" (2 successive panes horizontally slitted by 3)

- `-d, --deployment-file`

    Deployment file. By default it takes the latest created in the `deploy` directory

- `-pc, --pane-console`

    Add a regular shell pane to the tmux session.

- `-i, --identity-file TEXT`

    The path to the ssh (private) key to use to connect to the deployments. It has to be the counterpart of the key that would have been given to `nxc start` (albeit with the same command line argument).