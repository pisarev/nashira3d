# Contributing

Thank you for taking the time.

Bug reports and patches are welcome. A report that names the formula, the
domain and what you expected is worth more than a long description of the
symptom: the first can be run, the second has to be guessed at.

## Terms

By opening a pull request you agree that your contribution is licensed to the
project owner under the MIT licence, and that the owner may relicense the
project, including your contribution, under different terms in the future.

You keep the copyright to what you wrote. This is a licence grant, not a
transfer: it exists so that the licence of the project can be changed later
without tracking down everyone who ever sent a patch. Without it, one accepted
contribution closes that door permanently - in either direction, including back
to MIT.

## What a patch should carry

Every change that fixes something should come with a check that fails without
it. The repository has no test framework and does not want one: the probes in
`tests/` are plain programs that print `ok` or `FAIL` and return a non-zero
code. Add to them.

A check with only the green case is not a check. If it cannot go red, it is
green when the code works and green when the code has been replaced by a stub.
