set -e

command_exists() {
    command -v "$1" &> /dev/null
}

try_sudo() {
    if command_exists sudo
    then
        sudo -k $@
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
zrb project add task cmd \
    --project-dir . \
    --task-name "run-cmd"

log_info 'Add docker-compose-task'
zrb project add task docker-compose \
    --project-dir . \
    --task-name "run-container" \
    --compose-command "up" \
    --http-port 3001

log_info 'Add python-task'
zrb project add task python \
    --project-dir . \
    --task-name "run-python"

log_info 'Add python-app'
zrb project add app python \
    --project-dir . \
    --app-name "python-app" \
    --http-port 3002

log_info 'Add fastapp'
zrb project add fastapp app \
    --project-dir . \
    --app-name "fastapp" \
    --http-port 3003

log_info 'Add fastapp module'
zrb project add fastapp module \
    --project-dir . \
    --app-name "fastapp" \
    --module-name "library"

log_info 'Add fastapp crud'
zrb project add fastapp crud \
    --project-dir . \
    --app-name "fastapp" \
    --module-name "library" \
    --entity-name "book" \
    --plural-entity-name "books" \
    --column-name "code"

log_info 'Add fastapp field'
zrb project add fastapp field \
    --project-dir . \
    --app-name "fastapp" \
    --module-name "library" \
    --entity-name "book" \
    --column-name "title" \
    --column-type "string"

zrb project add fastapp field \
    --project-dir . \
    --app-name "fastapp" \
    --module-name "library" \
    --entity-name "book" \
    --column-name "page_number" \
    --column-type "integer"

zrb project add fastapp field \
    --project-dir . \
    --app-name "fastapp" \
    --module-name "library" \
    --entity-name "book" \
    --column-name "available" \
    --column-type "boolean"

zrb project add fastapp field \
    --project-dir . \
    --app-name "fastapp" \
    --module-name "library" \
    --entity-name "book" \
    --column-name "purchase_date" \
    --column-type "date"

zrb project add fastapp field \
    --project-dir . \
    --app-name "fastapp" \
    --module-name "library" \
    --entity-name "book" \
    --column-name "synopsis" \
    --column-type "text"

log_info 'Add plugin'
zrb project add plugin \
    --project-dir . \
    --package-name "my-plugin" \
    --package-description "A test package" \
    --package-homepage "https://github.com/state-alchemists/zrb" \
    --package-repository "https://github.com/state-alchemists/zrb" \
    --package-documentation "https://github.com/state-alchemists/zrb" \
    --package-author-name "Go Frendi" \
    --package-author-email "gofrendiasgard@gmail.com" \

log_info 'Add super-app generator'
zrb project add app generator \
    --project-dir "." \
    --package-name "my-plugin" \
    --generator-name "superapp" \
    --generator-app-port "8000"

log_info 'Add superapp'
zrb project add app superapp \
    --project-dir . \
    --app-name "super-app" \
    --http-port 3000
