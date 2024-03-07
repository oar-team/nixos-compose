
`nxc connect`

Opens one or more terminal sessions into the deployed nodes. By default, it will connect to all nodes, but we can specify which ones to connect to.

To connect to several machines at once. For this, we use a tmux (terminal multiplexer) session. Feel free to refer to the [tmux documentation](https://github.com/tmux/tmux/wiki) (or its [cheatsheet](https://tmuxcheatsheet.com/)), especially for the shortcuts to navigate between the different tabs.

## Examples

- `nxc connect`

    Open a Tmux session with on panel for each node.

- `nxc connect server`

    Connect to the `server` node. It runs on the current shell (Tmux is not used in this case)


## Usage

`nxc connect [OPTIONS] [HOST]...`

## Options

- `-l, --user`

    *Default:* `root`

- `-g, --geometry`
    Tmux geometry, 2 splitting indications are supported: +/*, examples: "1+3+2" (3 adjacent panes respectively horizontally splited by 1,3 and 2), "2*3" (2 adjacent panes horizontally splitted by 3)

- `-d, --deployment-file`
    Deployment file, take the latest created in deploy directory by default

- `-f, --flavour`
    flavour, by default it's extracted from deployment file name

- `-i, --identity-file`
    path to the ssh public private used to connect to the deployments

- `-pc, --pane-console`
    Add a pane console
    *Default:* `False`

- `host`


- `--help`
    Show this message and exit.
    *Default:* `False`

