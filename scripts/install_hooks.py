import os
import shutil
import sys
from pathlib import Path

def install_hooks(target_dir=None):
    if not target_dir:
        target_dir = Path.cwd()
    else:
        target_dir = Path(target_dir)

    git_dir = target_dir / '.git'
    if not git_dir.exists():
        print(f'Error: {target_dir} is not a git repository.')
        return

    hooks_dir = git_dir / 'hooks'
    hooks_dir.mkdir(exist_ok=True)

    script_dir = Path(__file__).parent.parent
    template_dir = script_dir / 'templates' / 'hooks'

    # Determine OS
    is_windows = os.name == 'nt'

    # 1. Install Doxyfile.fast
    shutil.copy(template_dir / 'Doxyfile.fast.template', target_dir / 'Doxyfile.fast')
    print('Installed Doxyfile.fast')

    # 2. Install Hooks
    if is_windows:
        # On Windows, we still use .sh for git hooks but they call powershell
        # Actually, let's just provide the .sh ones as they work in git-bash
        # and are the standard for git hooks even on Windows.
        pass

    # Copy pre-commit
    shutil.copy(template_dir / 'pre-commit.sh.template', hooks_dir / 'pre-commit')
    os.chmod(hooks_dir / 'pre-commit', 0o755)

    # Copy pre-push
    shutil.copy(template_dir / 'pre-push.sh.template', hooks_dir / 'pre-push')
    os.chmod(hooks_dir / 'pre-push', 0o755)

    print('Installed git hooks to .git/hooks/')
    print('Doxygen will now update metadata in the background on commit and push.')

if __name__ == '__main__':
    install_hooks(sys.argv[1] if len(sys.argv) > 1 else None)
