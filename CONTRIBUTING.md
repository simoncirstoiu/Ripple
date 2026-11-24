# Contributing to Ripple

Thanks for your interest in contributing to Ripple.

Before you send a pull request, issue, patch or any other contribution, please read the Contributor License Agreement below.

By contributing, you agree to its terms.

## Contributor License Agreement (CLA)

By submitting a contribution to this project, you agree to the terms below.

A contribution includes pull requests, patches, code snippets in issues or discussions, suggestions applied to the codebase, and any material incorporated into the project.

1. **Original work.**

   Your contribution is your own original work, or you have the right to submit it under these terms.

   If your contribution includes work owned by your employer, you confirm that your employer allowed you to contribute it, or waived its rights to your contribution.

2. **License grant.**

   You grant Simon Cîrstoiu and the Ripple project a perpetual, worldwide, non-exclusive, royalty-free, irrevocable copyright license to reproduce, prepare derivative works of, publicly display, publicly perform, sublicense, and distribute your contribution and such derivative works **under any license, including commercial licenses and licenses incompatible with the project's current license**.

3. **Patent grant.**

   You grant Simon Cîrstoiu and the Ripple project a perpetual, worldwide, non-exclusive, royalty-free, irrevocable patent license to make, have made, use, offer to sell, sell, import, and otherwise transfer your contribution.

   This license applies only to those patent claims licensable by you that are necessarily infringed by your contribution alone or by combination of your contribution with the project.

4. **Retained rights.**

   You retain all other rights, title, and interest in and to your contribution.

   You may continue to use your contribution in any way you wish, including in other projects, under any license.

   This CLA is a license grant, not an assignment of copyright.

5. **No warranty.**

   Your contribution is provided "as is", without warranty of any kind.

   You are not obligated to provide support for your contribution.

6. **Acceptance.**

   Submitting a contribution, for example opening a pull request or committing to this repository, constitutes your acceptance of these terms.

   If you do not agree to these terms, do not submit contributions to this project.

If you are unsure whether you have the right to contribute, or if your employer needs to sign off, contact ripple@it-link.net before submitting.

## Running the tests

```bash
docker build -t ripple-test tests
docker run --rm -v $PWD:/work -w /work ripple-test python -m pytest -q -p no:cacheprovider
```
