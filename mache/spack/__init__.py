import os
import subprocess
from jinja2 import Template
from importlib import resources
import yaml

from mache.machine_info import discover_machine
from mache.version import __version__


def make_spack_env(spack_path, env_name, spack_specs, compiler, mpi,
                   machine=None):
    """
    Clone the ``spack_for_mache_{{version}}`` branch from
    `E3SM's spack clone <https://github.com/E3SM-Project/spack>`_ and build
    a spack environment for the given machine, compiler and MPI library.

    Parameters
    ----------
    spack_path : str
        The base path where spack has been (or will be) cloned

    env_name : str
        The name of the spack environment to be created or recreated

    spack_specs : list of str
        A list of spack package specs to include in the environment

    compiler : str
        One of the E3SM supported compilers for the ``machine``

    mpi : str
        One of the E3SM supported MPI libraries for the given ``compiler`` and
        ``machine``

    machine : str, optional
        The name of an E3SM supported machine.  If none is given, the machine
        will be detected automatically via the host name.
    """

    if machine is None:
        machine = discover_machine()
        if machine is None:
            raise ValueError('Unable to discover machine form host name')

    if not os.path.exists(spack_path):
        # we need to clone the spack repo
        clone = f'git clone -b spack_for_mache_{__version__} ' \
                f'git@github.com:E3SM-Project/spack.git {spack_path}'
    else:
        clone = ''

    # add the package specs to the appropriate template
    specs = ''.join([f'  - {spec}\n' for spec in spack_specs])

    template_filename = f'{machine}_{compiler}_{mpi}.yaml'
    try:
        template = Template(
            resources.read_text('mache.spack', template_filename))
    except FileNotFoundError:
        raise ValueError(f'Spack template not available for {compiler} and '
                         f'{mpi} on {machine}.')
    yaml_file = template.render(specs=specs)
    yaml_filename = os.path.abspath(f'{env_name}.yaml')
    with open(yaml_filename, 'w') as handle:
        handle.write(yaml_file)

    template = Template(
        resources.read_text('mache.spack', 'build_spack_env.template'))
    build_file = template.render(clone=clone, spack_path=spack_path,
                                 env_name=env_name, yaml_filename=yaml_filename)
    build_filename = f'build_{env_name}.bash'
    with open(build_filename, 'w') as handle:
        handle.write(build_file)

    # clear environment variables and start fresh with those from login
    # so spack doesn't get confused by conda
    subprocess.check_call(f'env -i bash -l {build_filename}', shell=True)


def get_spack_script(spack_path, env_name, compiler, mpi, machine=None,
                     with_modules=True):
    """
    Build a snippet of a load script for the given spack environment

    Parameters
    ----------
    spack_path : str
        The base path where spack has been (or will be) cloned

    env_name : str
        The name of the spack environment to be created or recreated

    compiler : str
        One of the E3SM supported compilers for the ``machine``

    mpi : str
        One of the E3SM supported MPI libraries for the given ``compiler`` and
        ``machine``

    machine : str, optional
        The name of an E3SM supported machine.  If none is given, the machine
        will be detected automatically via the host name.

    with_modules : bool, optional
        Whether to include modules from the spack yaml file in the script

    Returns
    -------
    load_script : str
        A snippet of bash shell script that will load the given spack
        environment and add any additional steps required for using the
        environment such as setting environment variables or loading modules
        not handled by the spack environment directly
    """

    if machine is None:
        machine = discover_machine()
        if machine is None:
            raise ValueError('Unable to discover machine form host name')

    load_script = f'source {spack_path}/share/spack/setup-env.sh\n' \
                  f'spack env activate {env_name}'

    bash_filename = f'{machine}.sh'
    try:
        bask_script = resources.read_text('mache.spack', bash_filename)
        load_script = f'{load_script}\n{bask_script}'
    except FileNotFoundError:
        # there's nothing to add, which is fine
        pass

    bash_filename = f'{machine}_{compiler}_{mpi}.sh'
    try:
        bask_script = resources.read_text('mache.spack', bash_filename)
        load_script = f'{load_script}\n{bask_script}'
    except FileNotFoundError:
        # there's nothing to add, which is fine
        pass

    if with_modules:
        template_filename = f'{machine}_{compiler}_{mpi}.yaml'
        try:
            template = Template(
                resources.read_text('mache.spack', template_filename))
        except FileNotFoundError:
            raise ValueError(f'Spack template not available for {compiler} and '
                             f'{mpi} on {machine}.')
        yaml_data = yaml.safe_load(template.render(specs=''))

        mods = ['module purge']

        if 'spack' in yaml_data and 'packages' in yaml_data['spack']:
            package_data = yaml_data['spack']['packages']
            for package in package_data.values():
                if 'externals' in package:
                    for item in package['externals']:
                        if 'modules' in item:
                            for mod in item['modules']:
                                mods.append(f'module load {mod}')

        mods = '\n'.join(mods)
        load_script = f'{load_script}\n{mods}'

    return load_script