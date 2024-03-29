if [ -d "${HOME}/.gvm" ]
then
    [[ -s "${HOME}/.gvm/scripts/gvm" ]] && source "${HOME}/.gvm/scripts/gvm"
    # Workaround for https://github.com/moovweb/gvm/issues/445#issuecomment-1879884673
    export PATH=$(echo $PATH | sed 's/:\([^/]\)/ \1/g')
fi
