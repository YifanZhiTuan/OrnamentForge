"""Compatibility entry that delegates to the maintained current CLI."""

from .current.cli import main

raise SystemExit(main())
