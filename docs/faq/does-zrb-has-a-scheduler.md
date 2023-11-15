🔖 [Table of Contents](../README.md) / [FAQ](README.md)

# Do Zrb has a Scheduler?

No. Zrb focus is to help you run complicated tasks in a single run. You will need third-party alternatives to make your tasks run by schedule.

# Why Is No Scheduler?

Implementing a Scheduler seems to be easy at the first glance.

However, there are a few reasons why we don't build our own internal scheduler:

- There are a lot of battle-proven tools and strategy you can already use.
- Maintaining internal scheduler might distract us from the main goal.

# What Can I Do to Make a Scheduled Task?

Don't worry, there are some [tricks](../tutorials/running-task-by-schedule.md) you can use. For example you can use infinite loop, Cronjob, or even orchestrator like Airflow.

🔖 [Table of Contents](../README.md) / [FAQ](README.md)
