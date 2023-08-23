set -e
echo '🤖 Remove my-project'
rm -Rf my-project
export ZRB_SHOW_PROMPT=0


echo '🤖 Create my-project'
zrb project create --project-dir my-project --project-name "My Project"
cd my-project


echo '🤖 Add cmd-task'
zrb project add cmd-task \
    --project-dir . \
    --task-name "run-cmd"

echo '🤖 Add docker-compose-task'
zrb project add docker-compose-task \
    --project-dir . \
    --task-name "run-container" \
    --compose-command "up" \
    --http-port 3001

echo '🤖 Add python-task'
zrb project add python-task \
    --project-dir . \
    --task-name "run-python"

echo '🤖 Add simple-python-app'
zrb project add simple-python-app \
    --project-dir . \
    --app-name "simple" \
    --http-port 3002

echo '🤖 Add fastapp'
zrb project add fastapp \
    --project-dir . \
    --app-name "fastapp" \
    --http-port 3003

echo '🤖 Add fastapp module'
zrb project add fastapp-module \
    --project-dir . \
    --app-name "fastapp" \
    --module-name "library"

echo '🤖 Add fastapp crud'
zrb project add fastapp-crud \
    --project-dir . \
    --app-name "fastapp" \
    --module-name "library" \
    --entity-name "book" \
    --plural-entity-name "books" \
    --column-name "code"

echo '🤖 Add fastapp field'
zrb project add fastapp-field \
    --project-dir . \
    --app-name "fastapp" \
    --module-name "library" \
    --entity-name "book" \
    --column-name "title" \
    --column-type "str"

echo '🤖 Add python package'
zrb project add pip-package \
    --project-dir . \
    --package-name "zrb-coba-test" \
    --package-description "A test package" \
    --package-homepage "https://github.com/state-alchemists/zrb" \
    --package-bug-tracker "https://github.com/state-alchemists/zrb/issues" \
    --package-author-name "Go Frendi" \
    --package-author-email "gofrendiasgard@gmail.com" \

echo '🤖 Add generator'
zrb project add app-generator \
    --template-name "coba-app"

echo '🤖 Test run generator'
zrb project add coba-app \
    --project-dir . \
    --app-name "coba" \
    --app-image-name "docker.io/gofrendi/coba" \
    --http-port "8080" \
    --env-prefix "COBA"

echo '🤖 Test fastapp'
zrb project test-fastapp

echo '🤖 Test Install pip package symlink'
zrb project install-zrb-coba-test-symlink

