if [ ! -d "${HOME}/.sdkman" ]
then
    echo "Download sdkman"
    curl -s "https://get.sdkman.io" | bash
else
    echo "Sdkman already exists"
fi