Place soundboard `.wav` files in this directory.

The websocket protocol exposes each file by its lowercase filename stem:

- `bark.wav` -> `a s play bark`
- `startup_chime.wav` -> `a s play startup_chime`

Only lowercase ASCII letters, digits, and underscores are supported in sound IDs.
