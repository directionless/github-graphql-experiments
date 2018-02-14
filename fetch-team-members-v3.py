#!/usr/bin/env python

import json
import os
import logging
from github import Github


def main():
    g = Github(os.environ['GITHUB_PRODUCTION_TOKEN'])
    org = os.environ['GITHUB_ORG']

    org_data = {}

    logger.info("Fetching org:{0}".format(org))
    for team in g.get_organization(org).get_teams():
        logger.info("Fetching team:{0}...".format(team.name))

        if team.name in org_data:
            raise ValueError("Duplicate Team")
        org_data[team.name] = {}
        org_data[team.name]['members'] = [member.login.lower()
                                          for member in team.get_members()]

        # fetching invitations in the v3 form is surprisingly hard, skip
        org_data[team.name]['invitations'] = []

    with open('output/members-v3.json', 'w') as fh:
        json.dump(org_data, fh,
                  indent=2,
                  sort_keys=True,
                  separators=(',', ': '))
        fh.write("\n")


if __name__ == "__main__":
    logger = logging.getLogger('fetch-team-members-v3')
    logging.basicConfig()
    logger.setLevel(logging.INFO)
    main()
