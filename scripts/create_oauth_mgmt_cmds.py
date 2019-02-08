"""
Create a bash file containing all management commands to run to add OAuth2 id/secret combos.
"""

import click
import csv

@click.command()
@click.option(
    '--csv_path',
    help='Path to the CSV file.',
    required=True
)
@click.option(
    '--environment',
    help='Environment targeted for mgmt commands.',
    type=click.Choice(['stage', 'prod']),
    required=True
)
def create_oauth_mgmt_cmds(csv_path,
                           environment):
    """
    Does things.
    """
    with open(csv_path, 'r') as csvfile:
        dot_reader = csv.reader(csvfile, delimiter=',')
        out_filename = '{}_cmds.sh'.format(environment)
        with open(out_filename, 'w') as outfile:
            outfile.write("#!/bin/bash\n")
            outfile.write('\n')
            for row in dot_reader:
                if row[0] == 'site_id':
                    # Skip the header row.
                    continue
                cmd = './manage.py update_site_oauth_settings ' \
                ' --site_id {} --sso-client-id {} --sso-client-secret {}' \
                ' --backend-service-client-id {} --backend-service-client-secret {}'.format(
                    row[0], row[1], row[2], row[3], row[4]
                )
                outfile.write(cmd)
                outfile.write('\n\n')


if __name__ == u"__main__":
    create_oauth_mgmt_cmds()  # pylint: disable=no-value-for-parameter
