# Bug: `kubelingo` crashes with `argparse.ArgumentError` when using `--review-flagged`

### Description

When trying to review flagged questions using the `--review-flagged` option, the `kubelingo` CLI crashes.
The crash is caused by an `argparse.ArgumentError: argument --module: conflicting option string: --module`, which indicates that the `--module` argument is defined more than once in the argument parser.

### Steps to Reproduce

1. Run the CLI with the `--review-flagged` argument.
   ```bash
   ./kubelingo/cli.py --review-flagged
   ```

### Expected Behavior

The CLI should start a quiz session with only the questions that have been flagged for review.

### Actual Behavior

The script crashes with the following traceback:

```text
+-------------------------------------------------------+
| K   K U   U  BBBB  EEEEE L     III N   N  GGGG   OOO  |
| K  K  U   U  B   B E     L      I  NN  N G   G O   O  |
| KK    U   U  BBBB  EEEE  L      I  N N N G  GG O   O  |
| K  K  U   U  B   B E     L      I  N  NN G   G O   O  |
| K   K  UUU   BBBB  EEEEE LLLLL III N   N  GGGG   OOO  |
+-------------------------------------------------------+

Traceback (most recent call last):
  File "/Users/user/Documents/GitHub/kubelingo/./kubelingo/cli.py", line 641, in <module>
    main()
  File "/Users/user/Documents/GitHub/kubelingo/./kubelingo/cli.py", line 536, in main
    parser.add_argument('--module', type=str,
  File "/Users/user/.pyenv/versions/3.11.0/lib/python3.11/argparse.py", line 1461, in add_argument
    return self._add_action(action)
  File "/Users/user/.pyenv/versions/3.11.0/lib/python3.11/argparse.py", line 1843, in _add_action
    self._optionals._add_action(action)
  File "/Users/user/.pyenv/versions/3.11.0/lib/python3.11/argparse.py", line 1663, in _add_action
    action = super(_ArgumentGroup, self)._add_action(action)
  File "/Users/user/.pyenv/versions/3.11.0/lib/python3.11/argparse.py", line 1475, in _add_action
    self._check_conflict(action)
  File "/Users/user/.pyenv/versions/3.11.0/lib/python3.11/argparse.py", line 1612, in _check_conflict
    conflict_handler(action, confl_optionals)
  File "/Users/user/.pyenv/versions/3.11.0/lib/python3.11/argparse.py", line 1621, in _handle_conflict_error
    raise ArgumentError(action, message % conflict_string)
argparse.ArgumentError: argument --module: conflicting option string: --module
```
