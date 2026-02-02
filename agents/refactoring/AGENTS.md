# Refactoring Agent - AGENTS.md

> Agent configuration for code refactoring tasks in ZRB project.

---

## 🎯 Purpose

This agent specializes in code refactoring tasks including:
- Code modernization
- Design pattern implementation
- Code deduplication
- Performance optimization
- Type hint improvements
- Documentation updates during refactoring

---

## 🔧 Tools & Capabilities

### Primary Tools

```python
from zrb.llm.tool.code import analyze_code, analyze_code_complexity
from zrb.llm.tool.file import write_file, read_file
from zrb.llm.tool.bash import bash
```

### Available Actions

1. **analyze_code**: Analyze code structure and identify refactoring opportunities
2. **write_file**: Update refactored code
3. **bash**: Run linters, formatters, tests
4. **sub_agent**: Delegate specific refactoring sub-tasks

---

## 📋 Refactoring Tasks

### 1. Code Modernization

Modernize Python code to use newer features.

**Prompt Template:**
```
Refactor {file_path} to use modern Python 3.11+ features:

Changes to make:
1. Convert old-style classes to dataclasses where appropriate
2. Use type hint generics (list[str] instead of List[str])
3. Replace Union[X, Y] with X | Y syntax
4. Use match/case for complex conditionals
5. Convert to f-strings where missing
6. Use walrus operator := where it improves readability
7. Add __slots__ for memory efficiency where appropriate

Maintain backward compatibility where required.
Run tests after refactoring to ensure nothing breaks.
```

**Example Task:**
```python
from zrb import LLMTask, StrInput
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.file import write_file

modernize_code = LLMTask(
    name="modernize-code",
    description="Modernize Python code to 3.11+",
    input=[
        StrInput(name="target_file", description="File to modernize"),
    ],
    message="""
    Refactor {ctx.input.target_file} using modern Python 3.11+ features:
    
    Improvements to make:
    1. Use | union types instead of Union[] or Optional[]
    2. Use builtin generics (list[T], dict[K,V] instead of typing.List/Dict)
    3. Convert appropriate classes to @dataclass or @dataclass(slots=True)
    4. Use match/case for pattern matching where beneficial
    5. Use f-strings consistently
    6. Apply walrus operator where it improves readability
    7. Use Self type where appropriate
    
    Rules:
    - Maintain all existing functionality
    - Preserve type safety
    - Keep the same public API
    - Add/update docstrings
    """,
    tools=[analyze_code, write_file],
)
```

### 2. Extract Design Pattern

Refactor code to use appropriate design patterns.

**Prompt Template:**
```
Analyze {file_path} and refactor to use {pattern_name} pattern:

Current issues:
- {issue_description}

Pattern to implement: {pattern_name}

Requirements:
1. Identify where pattern applies
2. Implement pattern structure
3. Update all usages
4. Maintain backward compatibility
5. Add documentation for the pattern usage

Patterns to consider:
- Factory: For object creation
- Strategy: For interchangeable algorithms
- Observer: For event handling
- Command: For action encapsulation
- Repository: For data access
```

### 3. Deduplicate Code

Find and eliminate code duplication.

**Prompt Template:**
```
Analyze codebase and find duplication:

1. Find similar code blocks (> 3 lines, > 80% similar)
2. Identify common patterns
3. Extract to shared functions/classes
4. Update all call sites
5. Ensure tests still pass

Output:
- Refactoring summary
- Before/after comparison
- Test verification results
```

### 4. Performance Optimization

Optimize code for better performance.

**Prompt Template:**
```
Optimize {file_path} for performance:

Optimization targets:
1. Reduce algorithmic complexity
2. Minimize unnecessary allocations
3. Use generators for large datasets
4. Add caching/memoization where appropriate
5. Optimize imports (lazy loading)

Benchmark before and after.
Ensure thread safety if applicable.
```

---

## 🏗️ Refactoring Patterns

### Extract Method

```python
# Before
def process_data(data):
    # Validate
    if not data:
        raise ValueError("Empty data")
    if not isinstance(data, list):
        raise TypeError("Must be list")
    
    # Transform
    result = []
    for item in data:
        result.append(item.upper())
    
    return result

# After
def _validate_data(data):
    """Validate input data."""
    if not data:
        raise ValueError("Empty data")
    if not isinstance(data, list):
        raise TypeError("Must be list")

def _transform_data(data):
    """Transform data items."""
    return [item.upper() for item in data]

def process_data(data):
    """Process data with validation and transformation."""
    _validate_data(data)
    return _transform_data(data)
```

### Replace Conditional with Polymorphism

```python
# Before
def calculate_area(shape):
    if shape.type == "circle":
        return 3.14 * shape.radius ** 2
    elif shape.type == "rectangle":
        return shape.width * shape.height
    elif shape.type == "triangle":
        return 0.5 * shape.base * shape.height

# After
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self) -> float: ...

class Circle(Shape):
    def __init__(self, radius: float):
        self.radius = radius
    
    def area(self) -> float:
        return 3.14159 * self.radius ** 2

class Rectangle(Shape):
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height
    
    def area(self) -> float:
        return self.width * self.height
```

### Dependency Injection

```python
# Before
class UserService:
    def __init__(self):
        self.db = Database()  # Hardcoded dependency
        self.cache = RedisCache()  # Hardcoded dependency

# After
class UserService:
    def __init__(
        self,
        db: DatabaseInterface,
        cache: CacheInterface
    ):
        self.db = db
        self.cache = cache

# Usage
service = UserService(
    db=Database(),
    cache=RedisCache()
)
```

---

## 🔍 Code Smells to Fix

| Smell | Solution |
|-------|----------|
| Long Method | Extract Method |
| Large Class | Extract Class/Interface |
| Duplicated Code | Extract Method/Class |
| Feature Envy | Move Method |
| Data Clumps | Extract Class |
| Switch Statements | Replace with Polymorphism |
| Temporary Field | Extract Class |
| Refused Bequest | Replace Inheritance with Delegation |
| Comments | Extract Method (make code self-documenting) |
| Long Parameter List | Introduce Parameter Object |

---

## ⚡ Modernization Checklist

### Python 3.11+ Features to Use

- [ ] Use `|` for union types (X | Y instead of Union[X, Y])
- [ ] Use builtin generics (list[T], dict[K,V])
- [ ] Use `Self` type for fluent interfaces
- [ ] Use `TypedDict` with required/not_required
- [ ] Use `dataclass(slots=True)` for memory efficiency
- [ ] Use `match`/`case` for pattern matching
- [ ] Use `asyncio.TaskGroup` for structured concurrency
- [ ] Use `tomllib` for TOML parsing

### Type Safety Improvements

- [ ] Add return type annotations
- [ ] Use `Protocol` for structural subtyping
- [ ] Use `Final` for constants
- [ ] Use `Literal` for specific string values
- [ ] Use `Required`/`NotRequired` for TypedDict

---

## 🔄 Refactoring Workflow

### Safe Refactoring Steps

```python
from zrb import cli, Group, LLMTask, CmdTask
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.file import write_file

refactor_group = cli.add_group(Group(name="refactor", description="🔧 Refactoring tasks"))

# Step 1: Analyze code
analyze = refactor_group.add_task(LLMTask(
    name="analyze",
    description="Analyze code for refactoring opportunities",
    input=[StrInput(name="file", description="File to analyze")],
    message="""
    Analyze {ctx.input.file} for:
    1. Code smells
    2. Duplication
    3. Complexity issues
    4. Modernization opportunities
    
    Provide specific recommendations.
    """,
    tools=[analyze_code],
))

# Step 2: Run tests before
test_before = refactor_group.add_task(CmdTask(
    name="test-before",
    description="Run tests before refactoring",
    cmd="pytest {ctx.input.file} -v --tb=short",
))

# Step 3: Apply refactoring
refactor = refactor_group.add_task(LLMTask(
    name="apply",
    description="Apply refactoring",
    message="Apply the recommended refactoring to {ctx.input.file}",
    tools=[write_file],
))

# Step 4: Run tests after
test_after = refactor_group.add_task(CmdTask(
    name="test-after",
    description="Run tests after refactoring",
    cmd="pytest {ctx.input.file} -v --tb=short",
))

# Step 5: Format code
format_code = refactor_group.add_task(CmdTask(
    name="format",
    description="Format refactored code",
    cmd="black {ctx.input.file} && isort {ctx.input.file}",
))

# Chain workflow
analyze >> test_before >> refactor >> format_code >> test_after
```

### Pre-refactoring Checklist

- [ ] Understand the code completely
- [ ] Have comprehensive tests
- [ ] Tests pass before refactoring
- [ ] Version control checkpoint
- [ ] Identify refactoring boundaries

### Post-refactoring Checklist

- [ ] All tests pass
- [ ] Code is formatted (black, isort)
- [ ] Type checking passes (mypy)
- [ ] No new linting errors (flake8)
- [ ] Documentation updated
- [ ] Performance benchmarks maintained

---

## 📊 Refactoring Metrics

Track improvement with:

```python
# cyclomatic_complexity.py
import ast
from pathlib import Path

def calculate_complexity(file_path: str) -> dict:
    """Calculate code complexity metrics."""
    code = Path(file_path).read_text()
    tree = ast.parse(code)
    
    # Count branches, returns, etc.
    # Return complexity score
    pass

# Usage before/after refactoring
before = calculate_complexity("src/before.py")
after = calculate_complexity("src/after.py")
print(f"Complexity reduced: {before['score']} -> {after['score']}")
```

---

## 🔗 Related Agents

- `../documentation/AGENTS.md` - For documenting refactored code
- `../planning/AGENTS.md` - For refactoring planning
- `../testing/AGENTS.md` - For test-driven refactoring

---

*Last updated: 2026-02-02*
