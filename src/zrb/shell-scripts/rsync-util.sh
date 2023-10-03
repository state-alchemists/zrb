set -e
auth_rsync(){
    if [ "$_CONFIG_SSH_KEY" != "" ]
    then
        rsync -avz -e "ssh -i $_CONFIG_SSH_KEY -p $_CONFIG_PORT" $@
    elif [ "$_CONFIG_PASSWORD" != "" ]
    then
        sshpass -p "$_CONFIG_PASSWORD" rsync -avz -e "ssh -p $_CONFIG_PORT" $@
    else
        rsync -avz -e "ssh -p $_CONFIG_PORT" $@
    fi
}