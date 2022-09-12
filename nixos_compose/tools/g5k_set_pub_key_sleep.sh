#!/usr/bin/env bash
: ${DURATION:=1h}
export SSH_PUB_KEY=$HOME/.ssh/id_rsa.pub
taktuk -f <( uniq $OAR_FILE_NODES ) broadcast exec [ "sudo-g5k sh -c \"cat $SSH_PUB_KEY >> /root/.ssh/authorized_keys\"" ] 1>&2
cat $OAR_NODEFILE | uniq
sleep $DURATION
