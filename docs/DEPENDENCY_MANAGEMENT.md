# Dependency Management with pip-tools

## Overview

We use **pip-tools** to manage Python dependencies:

- `requirements.in` - Direct dependencies with loose version constraints
- `requirements.txt` - Locked, fully resolved dependencies (generated)

## Workflow

### Adding a new dependency

1. Add to `requirements.in` with a loose constraint:
   ```
   some-package>=1.0.0
   ```

2. Regenerate the lock file:
   ```bash
   pip-compile requirements.in -o requirements.txt
   ```

3. Commit both files.

### Upgrading dependencies

```bash
# Upgrade all packages
pip-compile --upgrade requirements.in -o requirements.txt

# Upgrade a specific package
pip-compile --upgrade-package django requirements.in -o requirements.txt
```

### Installing dependencies

```bash
# Install exact versions from lock file
pip install -r requirements.txt

# For development, also install pip-tools
pip install pip-tools
```

## CI Integration

The CI workflow:
1. Installs from `requirements.txt` (locked versions)
2. Runs `pip check` to verify dependency compatibility

## Why pip-tools?

- **Reproducible builds**: Lock file ensures same versions everywhere
- **Conflict detection**: Catches dependency conflicts at compile time
- **Minimal diffs**: Only direct deps in `.in`, full resolution in `.txt`
- **Fast installs**: No resolution needed at install time

## Troubleshooting

### Dependency conflict

If `pip-compile` fails with a conflict:

```bash
# See what's conflicting
pip-compile --verbose requirements.in

# Try with a resolver backtrack limit
pip-compile --resolver=backtracking requirements.in
```

### Version mismatch

If installed versions don't match lock file:

```bash
pip-sync requirements.txt  # Syncs exactly to lock file
```
