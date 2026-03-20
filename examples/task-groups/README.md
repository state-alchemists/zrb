# Task Groups Example

Shows how to organize tasks in groups (subcommands).

## Creating Groups

```python
from zrb import Group, cli

# Create a group (subcommand)
math = cli.add_group(Group("math", description="Math tools"))

# Add task to group
math.add_task(Task(name="add", ...))
```

## Nested Groups

```python
# Create subgroup within group
geometry = math.add_group(Group("geometry", description="Geometry tools"))

# Add task to subgroup
geometry.add_task(Task(name="perimeter", ...))
```

## Running

```bash
# Top level
zrb --help

# Math group
cd examples/task-groups
zrb math add --a 5 --b 3
zrb math subtract --a 10 --b 4

# Geometry subgroup
zrb math geometry perimeter --height 10 --width 5
zrb math geometry area --height 10 --width 5
zrb math geometry square-area --side 7

# Using alias
zrb math geometry calc-area --side 5
```

## Structure

```
zrb
├── math
│   ├── add
│   ├── subtract
│   └── geometry
│       ├── perimeter
│       ├── area
│       └── square-area
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| `Group` | Container for related tasks |
| `cli.add_group()` | Add group to root CLI |
| `group.add_group()` | Create nested group |
| `group.add_task()` | Add task to group |
| `alias` | Alternative name for a task |
