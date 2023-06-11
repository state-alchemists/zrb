🔖 [Table of Contents](../README.md) / [Troubleshooting](README.md)

# Enable shell completion

To enable shell completion, you need to set `_ZRB_COMPLETE` variable.

For `bash`:

```bash
eval $(_ZRB_COMPLETE=bash_source zrb)
```

For `zsh`:

```bash
eval $(_ZRB_COMPLETE=zsh_source zrb)
```

Once set, you will have a shell completion in your session:

```bash
zrb <TAB>
zrb md5 hash -<TAB>
```

Visit [click shell completion](https://click.palletsprojects.com/en/8.1.x/shell-completion/) for more information.



🔖 [Table of Contents](../README.md) / [Troubleshooting](README.md)
