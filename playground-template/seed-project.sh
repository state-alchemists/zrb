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
    --package-name "zrb-pkg" \
    --package-description "A test package" \
    --package-homepage "https://github.com/state-alchemists/zrb" \
    --package-bug-tracker "https://github.com/state-alchemists/zrb/issues" \
    --package-author-name "Go Frendi" \
    --package-author-email "gofrendiasgard@gmail.com" \

echo '🤖 Add generator'
zrb project add app-generator \
    --template-name "gen"

echo '🤖 Add generator (maximum feature)'
zrb project add app-generator \
    --template-name "gen-max" \
    --build-custom-image true \
    --is-container-only true \
    --is-http-port true \
    --use-helm true \
    --download-helm-chart true

echo '🤖 Add generator (No custom image)'
zrb project add app-generator \
    --template-name "gen-no-custom-image" \
    --build-custom-image false \
    --is-container-only true

echo '🤖 Test run generator'
zrb project add gen \
    --project-dir . \
    --app-name "app" \
    --app-image-name "docker.io/gofrendi/coba" \
    --app-port "8080" \
    --env-prefix "APP"

echo '🤖 Test run generator (maximum feature)'
zrb project add gen-max \
    --project-dir . \
    --app-name "app-max" \
    --app-image-name "docker.io/gofrendi/coba" \
    --app-port "8081" \
    --env-prefix "APP"

echo '🤖 Test run generator (no custom image)'
zrb project add gen-no-custom-image \
    --project-dir . \
    --app-name "app-no-custom-image" \
    --app-image-name "docker.io/gofrendi/coba" \
    --app-port "8082" \
    --env-prefix "APP"

echo '🤖 Test fastapp'
zrb project test-fastapp

echo '🤖 Test Install pip package symlink'
zrb project install-zrb-pkg-symlink
