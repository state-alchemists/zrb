🔖 [Table of Contents](../README.md) / [Tutorials](README.md)

# Integration with Other Tools

CLI Tools can interact to each other in various ways. The most common way is redirecting standard input, output, and error.

Every time you run a Zrb Task, Zrb will produce two types of output:
- stdout and
- stderr

The Stderr usually contains some logs or error information, while the stout usually contains the output.

# Stdout and Stderr

Let's say you want to redirect Zrb's stderr to `stderr.txt` and Zrb's stdout to `stdout.txt`

You can use any task's output for further processing. For example, redirect a task's output and error into files.

```bash
zrb base64 encode --text "non-credential-string" > stdout.txt 2> stderr.txt
cat stdout.txt
cat stderr.txt
```

You will see that `stdout.txt` contains just the output:

```
bm9uLWNyZWRlbnRpYWwtc3RyaW5n
```

While `stderr.txt` has everything else you expect to see on your screen:

```
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ○ ◷ 2023-11-26 06:59:12.672 ❁  22713 → 1/1 🍎    zrb base64 encode • Completed in 0.05152606964111328 seconds
To run again: zrb base64 encode --text "non-credential-string"
```

In most cases, you want to care more about the stdout.

```bash
zrb base64 encode --text "non-credential-string" > encoded-text.txt
```

# Using Zrb's Stdout as Other Tool's Input

There are two ways to use Zrb's Stdout as Other Tool's Input.

- Using Zrb's Stdout as Other Tool's Parameter
- Using Zrb's Stderr as Other Tool's Input

## Using Zrb's Stdout as Other Tool's Parameter

The first one is by using it as a parameter. For example, `cowsay` takes one parameter and shows a bubbled text.

```bash
cowsay hello
```

This command will show a bubbled "hello" on your screen.

You can use Zrb's output as `cowsay`'s parameter using `$(` and `)` like this:

```bash
cowsay $(zrb base64 encode --text "non-credential-string")
```

This command will show the bubbled output of `zrb base64 encode`.

```
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ○ ◷ 2023-11-26 07:26:12.391 ❁  23643 → 1/1 🍋    zrb base64 encode • Completed in 0.051149845123291016 seconds
To run again: zrb base64 encode --text "non-credential-string"
 ______________________________
< bm9uLWNyZWRlbnRpYWwtc3RyaW5n >
 ------------------------------
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\
                ||----w |
                ||     ||
```

## Using Zrb's Stdout as Other Tool's Input

Some other tools need to take information from user Stdin, for example, `lolcat`.

In that case, you can use pipe (`|`) operator to redirect Zrb's output as `lolcat`'s input:

```bash
zrb base64 encode --text "non-credential-string" | lolcat
```

```
Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ○ ◷ 2023-11-26 07:27:05.110 ❁  23687 → 1/1 🐭    zrb base64 encode • Completed in 0.05138230323791504 seconds
To run again: zrb base64 encode --text "non-credential-string"
bm9uLWNyZWRlbnRpYWwtc3RyaW5n
```

> __📝 NOTE:__ The output should be rainbow colored. You can install lolcat by following [it's documentation](https://github.com/busyloop/lolcat). If you are using Linux, and you don't like `snap`, you can try to use your OS's package manager (e.g., `sudo apt install lolcat`)

# Using Other Tool's Output as Zrb's Task Parameter

On the other hand, you can also use any CLI tool's output as Zrb's task parameter. This command will give you an interesting result:

```bash
zrb say --text "$(cowsay hi)" --width "80"
```

```
🤖 ○ ◷ 2023-11-26 07:28:58.860 ❁  23732 → 1/3 🐮              zrb say •

    ┌──────────────────────────────────────────────────────────────────────────────────┐
    |  ____                                                                            |
    | < hi >                                                                           |
    |  ----                                                                            |
    |         \   ^__^                                                                 |
    |          \  (oo)\_______                                                         |
    |             (__)\       )\/\                                                     |
    |                 ||----w |                                                        |
    |                 ||     ||                                                        |
    └──────────────────────────────────────────────────────────────────────────────────┘
          \
           \
      o    ___    o
      | ┌-------┐ |
      |(| o   o |)|
        | └---┘ |
        └-------┘

Support zrb growth and development!
☕ Donate at: https://stalchmst.com/donation
🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb
🐤 Follow us at: https://twitter.com/zarubastalchmst
🤖 ○ ◷ 2023-11-26 07:28:58.911 ❁  23732 → 1/3 🐮              zrb say • Completed in 0.05133986473083496 seconds
```

🔖 [Table of Contents](../README.md) / [Tutorials](README.md)
