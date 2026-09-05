#!/usr/bin/env python3
"""List complete colcon package Bash setups in dependency order (container only)."""
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
import sys


def package_setups(install: Path) -> list[Path]:
    packages = {}
    # Support the repository's isolated install and colcon's merged install layout.
    prefixes = [install] if (install / 'share/colcon-core/packages').is_dir() else sorted(
        path for path in install.iterdir() if path.is_dir()
    )
    for prefix in prefixes:
        index = prefix / 'share/colcon-core/packages'
        if not index.is_dir():
            continue
        for marker in sorted(index.iterdir()):
            setup = prefix / 'share' / marker.name / 'local_setup.bash'
            if marker.is_file() and setup.is_file():
                packages[marker.name] = (setup, marker.read_text().strip().split(';'))
    graph = {name: set(dependencies) & packages.keys()
             for name, (_, dependencies) in packages.items()}
    return [packages[name][0] for name in TopologicalSorter(graph).static_order()]


if __name__ == '__main__':
    try:
        for setup in package_setups(Path(sys.argv[1])):
            print(setup)
    except (OSError, CycleError) as error:
        print(f'Cannot resolve the ROS workspace environment: {error}', file=sys.stderr)
        raise SystemExit(1)
