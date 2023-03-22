(pulumi stack select {{input.snake_app_name_pulumi_stack}} || pulumi stack init {{input.snake_app_name_pulumi_stack}})
pulumi destroy --skip-preview