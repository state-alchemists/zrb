set -e
auth_ssh(){
    if [ "$_CONFIG_SSH_KEY" != "" ]
    then
        ssh -t -p "$_CONFIG_PORT" -i "$_CONFIG_SSH_KEY" "${_CONFIG_USER}@${_CONFIG_HOST}" "$1"
    elif [ "$_CONFIG_PASSWORD" != "" ]
    then
        sshpass -p "$_CONFIG_PASSWORD" ssh -t -p "$_CONFIG_PORT" "${_CONFIG_USER}@${_CONFIG_HOST}" "$1"
    else
        ssh -t -p "$_CONFIG_PORT" "${_CONFIG_USER}@${_CONFIG_HOST}" "$1"
    fi
}