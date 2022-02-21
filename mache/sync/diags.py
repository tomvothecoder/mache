import sys
import argparse
import subprocess

from mache.machine_info import MachineInfo
from mache.permissions import update_permissions


def sync_diags(other, direction='to', machine=None, username=None):
    """
    Synchronize diagnostics files between supported machines

    Parameters
    ----------
    other : str
        The other machine to sync to or from
    direction : {'to', 'from'}, optional
        The direction to sync (to or from the other machine).
    machine : str, optional
        The name of this machine.  If not provided, it will be detected
        automatically
    username : str, optional
        The username to use on the other machine, if not from ``.ssh/config``
    """
    if direction not in ['to', 'from']:
        raise ValueError('The direction must be one of "to" or "from"')

    machine_info = MachineInfo(machine=machine)
    machine = machine_info.machine

    lcrc_machines = ['anvil', 'chrysalis']
    if direction == 'to' and machine not in lcrc_machines:
        raise ValueError(f'You can only sync diagnostics to another machine '
                         f'from an LCRC machine: {", ".join(lcrc_machines)}')
    if direction == 'from' and other not in lcrc_machines:
        raise ValueError(f'You can only sync diagnostics from an LCRC '
                         f'machine: {", ".join(lcrc_machines)}')
    machine_config = machine_info.config
    other_info = MachineInfo(machine=other)
    other_config = other_info.config

    hostname = other_config.get('sync', 'hostname')
    if other_config.has_option('sync', 'tunnel_hostname'):
        tunnel = other_config.get('sync', 'tunnel_hostname')
    else:
        tunnel = None

    if direction == 'to' and (machine != other or tunnel is None):
        raise ValueError('You can only use "mache sync diags to ..." to '
                         'sync diags between directories on an LCRC machine\n'
                         'or to a machine with a tunnel.  Other machines '
                         'should only use "mache sync diags from ..." so\n'
                         'permissions can be updated.')

    if direction == 'from':
        source_config = other_config
        dest_config = machine_config
    else:
        source_config = machine_config
        dest_config = other_config

    public_diags = source_config.get('sync', 'public_diags')
    private_diags = source_config.get('sync', 'private_diags')
    dest_diags = dest_config.get('diagnostics', 'base_path')

    if machine == other:
        prefix = ''
    else:
        if username is not None:
            prefix = f'{username}@{hostname}:'
        else:
            prefix = f'{hostname}:'

    if direction == 'from':
        public_diags = f'{prefix}{public_diags}'
        private_diags = f'{prefix}{private_diags}'
    else:
        dest_diags = f'{prefix}{dest_diags}'

    args = ['rsync', '--verbose', '--recursive', '--times', '--links',
            '--compress', '--progress', '--update',
            '--exclude=observations/Atm', '--no-perms', '--omit-dir-times']

    if tunnel:
        args.append(f'--rsync-path="ssh {tunnel} rsync"')

    public_args = args + [public_diags, dest_diags]
    private_args = args + [private_diags, dest_diags]

    print(f'running: {" ".join(public_args)}')
    subprocess.check_call(public_args)
    print(f'running: {" ".join(private_args)}')
    subprocess.check_call(private_args)

    if direction == 'from':
        group = machine_config.get('diagnostics', 'group')
        print(f'Updating permissions on {dest_diags}:')
        update_permissions(base_paths=dest_diags, group=group,
                           show_progress=True, group_writable=True,
                           other_readable=True)
        print('Done.')


def main():
    """
    Defines the ``mache sync diags`` command
    """
    parser = argparse.ArgumentParser(
        description="Synchronize diagnostics files between supported machines",
        usage='''
    mache sync diags to <other> [<args>]
        or
    mache sync diags from <other> [<args>]

    To get help on an individual command, run:
        mache sync <command> --help
        ''')
    parser.add_argument('direction', help='whether to sync "to" or "from" the '
                                          'other machine')
    parser.add_argument("other", help="The other machine to sync to or from")
    parser.add_argument("-m", "--machine", dest="machine",
                        help="The name of this machine.  If not provided, it "
                             "will be detected automatically")
    parser.add_argument("-u", "--username", dest="username", required=True,
                        help="The username to use on the other machine")
    args = parser.parse_args(sys.argv[3:])
    sync_diags(args.other, args.direction, args.machine, args.username)
