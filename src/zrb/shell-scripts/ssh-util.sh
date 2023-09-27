auth_ssh(){
    if [ "$_CONFIG_SSH_KEY" != "" ]
    then
        ssh -p "$_CONFIG_PORT" -i "$_CONFIG_SSH_KEY" "${_CONFIG_USER}@${_CONFIG_HOST}"
    elif [ "$_CONFIG_PASSWORD" != "" ]
    then
        sshpass -p "$_CONFIG_PASSWORD" ssh -p "$_CONFIG_PORT" "${_CONFIG_USER}@${_CONFIG_HOST}"
    else
        ssh -p "$_CONFIG_PORT" "${_CONFIG_USER}@${_CONFIG_HOST}"
    fi
}