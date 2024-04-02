export PYTHONUNBUFFERED=1
echo "Start load test"
locust {%if input.snake_zrb_app_name_load_test_headless %}--headless{% endif %} \
    --web-port {{ input.snake_zrb_app_name_load_test_port }} \
    --users {{ input.snake_zrb_app_name_load_test_users }} \
    --spawn-rate {{ input.snake_zrb_app_name_load_test_spawn_rate }} \
    -H {{ input.snake_zrb_app_name_load_test_url }}