
# Profiling Zrb

When diagnosing performance issues, especially slow startup times, profiling is an essential tool. This guide outlines how to use `cProfile` with `snakeviz` or `flameprof` to identify performance bottlenecks.

## Generating a Profile

First, generate a profile file using Python's built-in `cProfile` module. It's best to profile a simple, fast-running command like `zrb --help` to isolate startup costs.

```bash
python3 -m cProfile -o .cprofile.prof -m zrb --help
```

This command runs `zrb --help` and saves the profiling data to a file named `.cprofile.prof`.

## Visualizing the Profile

You can visualize the profiling data in a few ways.

### Using `snakeviz`

`snakeviz` creates an interactive HTML visualization that is easy to navigate.

1.  **Install `snakeviz`**:
    ```bash
    pip install snakeviz
    ```

2.  **Run `snakeviz`**:
    ```bash
    snakeviz .cprofile.prof
    ```
    This will start a web server and open the visualization in your browser.

### Using `flameprof`

If you're working in an environment without a web browser, you can generate a flame graph in your terminal using `flameprof`.

1.  **Install `flameprof`**:
    ```bash
    pip install flameprof
    ```

2.  **Generate the flame graph**:
    ```bash
    flameprof .cprofile.prof > flamegraph.svg
    ```
    You can then open `flamegraph.svg` in a browser or a compatible image viewer.

By analyzing the output of these tools, you can identify which function calls are taking the most time and focus your optimization efforts accordingly.
