set -e
auth_rsync(){
    if [ "$_CONFIG_SSH_KEY" != "" ]
    then
        rsync --mkpath -avz -e "ssh -i $_CONFIG_SSH_KEY -p $_CONFIG_PORT" $@
    elif [ "$_CONFIG_PASSWORD" != "" ]
    then
        sshpass -p "$_CONFIG_PASSWORD" rsync --mkpath -avz -e "ssh -p $_CONFIG_PORT" $@
    else
        rsync --mkpath -avz -e "ssh -p $_CONFIG_PORT" $@
    fi
}