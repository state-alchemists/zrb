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
    --env-prefix "MY" \
    --http-port 3000

echo '🤖 Add python-task'
zrb project add python-task \
    --project-dir . \
    --task-name "run-python"

echo '🤖 Add simple-python-app'
zrb project add simple-python-app \
    --project-dir . \
    --app-name "simple" \
    --env-prefix "APP" \
    --http-port 3001


echo '🤖 Add test-project task'
echo '' >> zrb_init.py
echo 'from zrb import Task, runner' >> zrb_init.py
echo 'test_project = Task(' >> zrb_init.py
echo "    name='test-project'," >> zrb_init.py
echo '    upstreams=[' >> zrb_init.py
echo '        run_cmd.run_cmd,' >> zrb_init.py
echo '        run_container.run_container,' >> zrb_init.py
echo '        run_python.run_python,' >> zrb_init.py
echo '        simple_local.start_simple,' >> zrb_init.py
echo '    ]' >> zrb_init.py
echo ')' >> zrb_init.py
echo 'runner.register(test_project)' >> zrb_init.py
echo '' >> zrb_init.py


echo '🤖 Test project'
zrb test-project
