🔖 [Table of Contents](../README.md)

<div align="center">
  <img src="../_images/emoji/brain.png"/>
  <p>
    <sub>
      Corgito Ergo Sum
    </sub>
  </p>
</div>


# Concepts and Terminologies

```
                            
          ┌────────────┐    ┌───────────────┐     ┌────────────┐     ┌────────────┐
       ┌──┴──────────┐ │    │ Task          │  ┌──┤ Group      │  ┌──┤ Group      │
       │ Inputs      ├─┼─┐  │               │  │  │            │  │  │            │
       │             │ │ │  │  ┌─────────┐  │  │  │  ┌──────┐  │  │  │  ┌──────┐  │
       │  ┌───────┐  │ │ │  │  │name     │  │  │  │  │name  │  │  │  │  │name  │  │
       │  │name   │  │ │ │  │  └─────────┘  │  │  │  └──────┘  │  │  │  └──────┘  │
       │  └───────┘  │ │ │  │  ┌─────────┐  │  │  │  ┌──────┐  │  │  │  ┌──────┐  │
       │  ┌───────┐  │ │ │  │  │group    ├──┼──┘  │  │parent├──┼──┘  │  │parent│  │
       │  │prompt │  │ │ │  │  └─────────┘  │     │  └──────┘  │     │  └──────┘  │
       │  └───────┘  │ │ │  │  ┌─────────┐  │     └────────────┘     └────────────┘
       │  ┌───────┐  │ │ └──┼──┤inputs   │  │  
       │  │default│  │ │    │  └─────────┘  │ 
       │  └───────┘  │ │    │  ┌─────────┐  │                           ┌──────────────────┐
       │  ┌───────┐  │ │    │  │envs     ├──┼                        ┌──┴────────────────┐ │
       │  │...    │  │ │    │  └─────────┘  │────────────────────────┤ Env               │ │
       │  └───────┘  ├─┘    │  ┌─────────┐  │                        │                   │ │
       └─────────────┘    ┌─┼──┤env_files│  │                        │  ┌─────────────┐  │ │
                          │ │  └─────────┘  │                        │  │name         │  │ │
                          │ │  ┌─────────┐  │     ┌───────────────┐  │  └─────────────┘  │ │
                          │ │  │checkers ├──┼─────┤ Task          │  │  ┌─────────────┐  │ │
                          │ │  └─────────┘  │     │               │  │  │os_name      │  │ │
                          │ │  ┌─────────┐  │     │  ┌─────────┐  │  │  └─────────────┘  │ │
    ┌──────────────────┐  | │  │...      │  │     │  │name     │  │  │  ┌─────────────┐  │ │
 ┌──┴────────────────┐ │  | │  └─────────┘  │     │  └─────────┘  │  │  │default      │  │ │
 │ EnvFile           ├─┼──┘ └───────────────┘     │  ┌─────────┐  │  │  └─────────────┘  │ │
 │                   │ │                          │  │group    │  │  │  ┌─────────────┐  │ │
 │  ┌─────────────┐  │ │                          │  └─────────┘  │  │  │should_render│  │ │
 │  │name         │  │ │                          │  ┌─────────┐  │  │  └─────────────┘  ├─┘
 │  └─────────────┘  │ │                          │  │inputs   │  │  └───────────────────┘
 │  ┌─────────────┐  │ │                          │  └─────────┘  │
 │  │prefix       │  │ │                          │  ┌─────────┐  │
 │  └─────────────┘  │ │                          │  │envs     │  │
 │  ┌─────────────┐  │ │                          │  └─────────┘  │
 │  │path         │  │ │                          │  ┌─────────┐  │
 │  └─────────────┘  │ │                          │  │env_files│  │
 │  ┌─────────────┐  │ │                          │  └─────────┘  │
 │  │should_render│  │ │                          │  ┌─────────┐  │
 │  └─────────────┘  ├─┘                          │  │checkers │  │
 └───────────────────┘                            │  └─────────┘  │
                                                  │  ┌─────────┐  │
                                                  │  │...      │  │
                                                  │  └─────────┘  │
                                                  └───────────────┘
```

- [Project](project.md)
- [Runner, Group, and Task](runner-group-and-task.md)
- [Task Lifecycle](task-lifecycle.md)
- [Task Upstream](task-upstream.md)
- [Inputs](inputs.md)
- [Environments](environments.md)
- [Xcom](xcom.md)
- [Template Rendering](template-rendering.md)
- [Specialized Tasks](specialized-tasks/README.md)
  - [DockerComposeTask](specialized-tasks/docker-compose-task.md)
  - [ResourceMaker](specialized-tasks/resource-maker.md)
  - [Notifier](specialized-tasks/notifider.md)
  - [RemoteCmdTask](specialized-tasks/remote-cmd-task.md)
  - [RsyncTask](specialized-tasks/rsync-task.md)
  - [Server](specialized-tasks/server.md)
  - [Checker](specialized-tasks/checker.md)
  - [FlowTask](specialized-tasks/flow-task.md)
- [Copying Task](copying-task.md)
- [Extending Task](extending-task.md)
- [Extending CmdTask](extending-cmd-task.md)

🔖 [Table of Contents](../README.md)
