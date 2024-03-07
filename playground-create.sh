set -e

command_exists() {
    command -v "$1" &> /dev/null
}

try_sudo() {
    if command_exists sudo
    then
        sudo $@
    else
        $@
    fi
}

log_info() {
    echo -e "🤖 \e[0;33m${1}\e[0;0m"
}


log_info 'Remove playground'
try_sudo rm -Rf playground
export ZRB_SHOW_PROMPT=0
export ZRB_SHOW_TIME=0


log_info 'Create playground'
zrb project create --project-dir playground --project-name "Playground"
cd playground


log_info 'Add cmd-task'
zrb project add cmd-task \
    --project-dir . \
    --task-name "run-cmd"

log_info 'Add docker-compose-task'
zrb project add docker-compose-task \
    --project-dir . \
    --task-name "run-container" \
    --compose-command "up" \
    --http-port 3001

log_info 'Add python-task'
zrb project add python-task \
    --project-dir . \
    --task-name "run-python"

log_info 'Add simple-python-app'
zrb project add simple-python-app \
    --project-dir . \
    --app-name "simple" \
    --http-port 3002

log_info 'Add fastapp'
zrb project add fastapp \
    --project-dir . \
    --app-name "fastapp" \
    --http-port 3003

log_info 'Add fastapp module'
zrb project add fastapp-module \
    --project-dir . \
    --app-name "fastapp" \
    --module-name "library"

log_info 'Add fastapp crud'
zrb project add fastapp-crud \
    --project-dir . \
    --app-name "fastapp" \
    --module-name "library" \
    --entity-name "book" \
    --plural-entity-name "books" \
    --column-name "code"

log_info 'Add fastapp field'
zrb project add fastapp-field \
    --project-dir . \
    --app-name "fastapp" \
    --module-name "library" \
    --entity-name "book" \
    --column-name "title" \
    --column-type "str"

log_info 'Add python package'
zrb project add pip-package \
    --project-dir . \
    --package-name "zrb-pkg" \
    --package-description "A test package" \
    --package-homepage "https://github.com/state-alchemists/zrb" \
    --package-repository "https://github.com/state-alchemists/zrb" \
    --package-documentation "https://github.com/state-alchemists/zrb" \
    --package-author-name "Go Frendi" \
    --package-author-email "gofrendiasgard@gmail.com" \

log_info 'Add generator'
zrb project add app-generator \
    --template-name "app"

log_info 'Add generator (maximum feature)'
zrb project add app-generator \
    --template-name "app-max" \
    --build-custom-image true \
    --is-container-only true \
    --is-http-port true \
    --use-helm true \

log_info 'Add generator (No custom image)'
zrb project add app-generator \
    --template-name "app-no-custom-image" \
    --build-custom-image false \
    --is-container-only true

log_info 'Run generator'
zrb project add app \
    --project-dir . \
    --app-name "app" \
    --app-image-name "docker.io/gofrendi/coba" \
    --app-port "8080" \
    --env-prefix "APP"

log_info 'Run generator (maximum feature)'
zrb project add app-max \
    --project-dir . \
    --app-name "app-max" \
    --app-image-name "docker.io/gofrendi/coba" \
    --app-port "8081" \
    --env-prefix "APP"

log_info 'Run generator (no custom image)'
zrb project add app-no-custom-image \
    --project-dir . \
    --app-name "app-no-custom-image" \
    --app-image-name "docker.io/gofrendi/coba" \
    --app-port "8082" \
    --env-prefix "APP"
