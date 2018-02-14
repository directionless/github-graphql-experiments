# GitHub GraphQL Experiments

_This repository accompanies an unwritten blog post_

## Introduction

Recently, I was writing some scripts to audit and sync a github
organization with an external list of users. GitHub recently changed
their API over to graphql, so I thought it would be a fun time to
experiment.

The simplest way to do this with the REST api, is a trivial for loop
-- for each team, fetch the team info. A trivial implementation is at
[fetch-team-members-v3.py].

But, this has a lot of overhead. It's a REST call per team, and each
call has a bunch of extraneous data. So, can we use graphql?

As it turns out, yes. But it took me awhile to work through the
pagination.

## Early Experiments

FIXME: Add content here <g>

## Final Realization

Ultimately, I realized that the correct way to handle the inner
pagination was something akin to recursion. Fetch as much data as we
can, and for anything incomplete, come back and fill in the
details. Whether this is done inline, or as a second step doesn't
matter much.

This results in something much more efficient. We're able to query for
_most_ of the teams, and _most_ of their members with a single API
call. And the few that require pagination can be followed up.

Proof of concept code can be see at [fetch-team-members-v4.py]
