set -e
echo '🤖 Remove my-project'
rm -Rf my-project


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
    --env-prefix "MY"

echo '🤖 Add python-task'
zrb project add python-task \
    --project-dir . \
    --task-name "run-python"


echo '🤖 Run cmd-task'
zrb project run-cmd

echo '🤖 Run python-task'
zrb project run-python

echo '🤖 Run docker-compose-task'
zrb project run-container

