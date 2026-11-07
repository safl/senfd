# Changelog

Each release of senfd has a section here, named by its version, such as
`## 0.3.0`. That section is the text of the release on GitHub.

A release is made by merging a pull request whose last commit is
`ver: bump to vX.Y.Z`. That commit sets `__version__` in
`src/senfd/__init__.py` and adds the `## X.Y.Z` section to this file. When it
lands on `main`, `.github/workflows/release.yml` checks both, takes the build
that the pull request's checks tested, publishes it to PyPI, tags it, and
creates the GitHub release. Release tags are not pushed by hand.

## Unreleased

A release is made by merging a version bump, as described above, rather than
by pushing a tag. The package version is read from `senfd.__version__`.
