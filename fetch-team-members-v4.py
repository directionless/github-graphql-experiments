#!/usr/bin/env python

# New strategy. Take the basic walk of "for each team, fetch", and
# optimize it using graphql. Feels slightly inelegant, but highly
# pragmatic
#
# Proposed algo:
#  1. Fetch ~everything with reasonable chunk_sizes
#  2. Populate initial data
#  3. For things that have hasNextPage, followup later
#
# Observe that chunk_size has interesting tuning properties. Do you
# have few teams with many members? Or many teams with few members?
# Note that the github v4 api caps the chunk size to 100, and has some
# complicated math about how they sum. It's complicated
# https://developer.github.com/v4/guides/resource-limitations/

import json
import requests
import os
import argparse
import logging


query = """{
    organization(login:"%(orgname)s") {
    teams(first: %(teams_chunk)s %(teams_pagination)s) {
      pageInfo {
        endCursor
        hasNextPage
      }
      edges {
        node {
          name
          description
          members(first: %(members_chunk)s ) {
            pageInfo {
              endCursor
              hasNextPage
            }
            edges {
              node {
                login
              }
            }
          }
          invitations(first: %(invitations_chunk)s ) {
            pageInfo {
              endCursor
              hasNextPage
            }
            edges {
              node {
                invitee {
                      name
                      login
                      email
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

team_query = """{
    organization(login:"%(orgname)s") {
      team(slug: "%(team_name)s") {
          members(first: %(members_chunk)s %(members_pagination)s) {
          pageInfo {
            endCursor
            hasNextPage
          }
          edges {
            node {
              login
            }
          }
        }
        invitations(first: %(invitations_chunk)s %(invitations_pagination)s) {
          pageInfo {
            endCursor
            hasNextPage
          }
          edges {
            node {
              invitee {
                login
              }
            }
          }
        }
      }
    }
  }
"""


def user_edge_to_s(u):
    # This is kinda ugly, since `member` and `invitee` are more
    # different than they should be. And though it seems like
    # graphql's aliases might help, they don't. This is because github
    # has this data at different depths.
    #
    # users are     edges { node { login } }
    # invitees are  edges { node { invitee { login } }
    #
    # I don't really understand why we can't alias across the layers
    # or what went into github's underlying data model. But they both
    # seem to be givens.
    if 'login' in u['node']:
        return u['node']['login'].lower()
    elif 'invitee' in u['node']:
        return u['node']['invitee']['login'].lower()
    else:
        logger.error(json.dumps(u))
        raise Exception('unknown user data format')


def run_query(query, **query_params):
    headers = {
        'Authorization': 'token {0}'.format(os.environ['GITHUB_PRODUCTION_TOKEN'])
    }
    merged_params = {
        'teams_chunk': '100',
        'members_chunk': '100',
        'invitations_chunk': '100',
    }
    merged_params.update(query_params)
    expanded_query = query % merged_params
    logger.debug(expanded_query)
    resp = requests.post('https://api.github.com/graphql',
                         json.dumps({"query": expanded_query}),
                         headers=headers)

    resp.raise_for_status()
    if 'errors' in resp.json():
        logger.critical('Got Errors')
        logger.critical(json.dumps(expanded_query))
        logger.critical(json.dumps(resp.json()))
        raise Exception('Got errors')

    return resp


def get_initial_org_data(org):
    org_data = {}

    pagination = ''
    still_going = True
    while(still_going):
        still_going = False
        logger.info("Querying for teams for org:{0}".format(org))
        resp = run_query(query, orgname=org.lower(), teams_pagination=pagination)

        for team in resp.json()['data']['organization']['teams']['edges']:
            team_name = team['node']['name']
            if team_name not in org_data:
                org_data[team_name] = {
                    'members': [],
                    'invitations': [],
                    'followup': False,
                }

            # Are we done?
            if resp.json()['data']['organization']['teams']['pageInfo']['hasNextPage'] is True:
                still_going = True
                pagination = 'after:"%s"' % resp.json()['data']['organization']['teams']['pageInfo']['endCursor']

            # If anything is didn't fit on a page, just skip it for now. We'll followup later
            if team['node']['members']['pageInfo']['hasNextPage'] is True or team['node']['invitations']['pageInfo']['hasNextPage'] is True:
                org_data[team_name]['followup'] = True
            else:
                # merge in data
                org_data[team_name]['members'].extend(map(user_edge_to_s, team['node']['members']['edges']))
                org_data[team_name]['invitations'].extend(map(user_edge_to_s, team['node']['invitations']['edges']))

    return org_data


def get_extended_team_data(orgname, team_name):
    team_data = {
        'members': [],
        'invitations': [],
    }

    pagination = {
        'members_pagination': '',
        'invitations_pagination': '',
    }

    still_going = True
    while still_going:
        logger.info("Query for team:{0}".format(json.dumps(team_name)))
        resp = run_query(team_query, orgname=orgname, team_name=team_name.lower(), **pagination)
        logger.debug(json.dumps(resp.json()))
        team_resp = resp.json()['data']['organization']['team']

        team_data['members'].extend(map(user_edge_to_s, team_resp['members']['edges']))
        team_data['invitations'].extend(map(user_edge_to_s, team_resp['invitations']['edges']))

        still_going = False
        if team_resp['members']['pageInfo']['hasNextPage'] is True:
            pagination['members_pagination'] = 'after:"%s"' % team_resp['members']['pageInfo']['endCursor']
            still_going = True

        if team_resp['invitations']['pageInfo']['hasNextPage'] is True:
            pagination['invitations_pagination'] = 'after:"%s"' % team_resp['invitations']['pageInfo']['endCursor']
            still_going = True

    return team_data


def get_org_data(orgname):
    # initial data load
    if orgname == "":
        raise Exception('Missing orgname')
    org_data = get_initial_org_data(orgname)

    # Now, lets revisit anything for followup
    for team_name in org_data.keys():
        followup = org_data[team_name].pop('followup', False)
        if followup:
            org_data[team_name] = get_extended_team_data(orgname, team_name)

    return org_data


def parse_args():
    parser = argparse.ArgumentParser(description='GitHub Membership Fetcher Experimental GraphQL Version')
    parser.add_argument('-o', dest='output', required=False,
                        default='output/members-v4.json',
                        help='Output File')

    parser.add_argument('-org', dest='org', required=False,
                        default=os.environ.get('GITHUB_ORG', ''),
                        help='GitHub Organization')

    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    org_data = get_org_data(args.org)

    with open(args.output, 'w') as fh:
        json.dump(org_data, fh,
                  indent=2,
                  sort_keys=True,
                  separators=(',', ': '))
        fh.write("\n")


if __name__ == "__main__":
    logger = logging.getLogger('fetch-team-members-v4')
    logging.basicConfig()
    logger.setLevel(logging.INFO)
    main()
