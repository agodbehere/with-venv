# -*- coding: utf-8 -*-
"""
Run scripts in a clean virtual environment.

Useful for testing, building, and deploying.

:author: Andrew B Godbehere
:date: 4/21/16
"""

import venv
import sys
import os
from urllib.parse import urlparse
from urllib.request import urlretrieve
from threading import Thread
from subprocess import Popen, PIPE
import os.path
import types
import shlex

import os

artifact_path = '.greenenv'
if not os.path.exists(artifact_path):
    os.makedirs(artifact_path)

import tempfile


class ExtendedEnvBuilder(venv.EnvBuilder):
    """
    This builder installs setuptools and pip so that you can pip or
    easy_install other packages into the created environment.

    Note: This class is from stdlib docs, with some minor modifications.

    :param nodist: If True, setuptools and pip are not installed into the
                   created environment.
    :param nopip: If True, pip is not installed into the created
                  environment.
    :param context: Information and environment variables for the virtual environment being created
    :param verbose: Flag, whether or not to show output from scripts run in environment
    """

    def __init__(self, *args, **kwargs):
        # self.nodist = kwargs.pop('nodist', False)
        # self.nopip = kwargs.pop('nopip', False)
        self.verbose = kwargs.pop('verbose', False)
        self.context = None
        self.python_name = None
        super().__init__(*args, **kwargs)

    def create(self, env_dir, python_name=None):
        """
        Create a virtual environment
        :param env_dir:
        :param python_name:
        :return:
        """
        if python_name is not None:
            self.python_name = python_name
        else:
            self.python_name = "python3"

        super().create(env_dir)
        return clean_env(self.context, self.verbose)

    def ensure_directories(self, env_dir):
        """
        Create the directories for the environment.

        Note: Minor modifications made to original method from venv.

        Returns a context object which holds paths in the environment,
        for use by subsequent logic.
        """

        def create_if_needed(d):
            if not os.path.exists(d):
                os.makedirs(d)
            elif os.path.islink(d) or os.path.isfile(d):
                raise ValueError('Unable to create directory %r' % d)

        if os.path.exists(env_dir) and self.clear:
            self.clear_directory(env_dir)
        context = types.SimpleNamespace()
        context.env_dir = env_dir
        context.env_name = os.path.split(env_dir)[1]
        context.prompt = '(%s) ' % context.env_name
        create_if_needed(env_dir)
        env = os.environ

        # Note: If running this from inside a virtual environment, do some extra work to untangle from current venv.
        if 'VIRTUAL_ENV' in os.environ:
            vpath = os.environ['VIRTUAL_ENV']
            base_binpath = os.pathsep.join(
                [x for x in os.environ['PATH'].split(os.pathsep) if not x.startswith(vpath)]
            )

            executable = None
            for p in base_binpath.split(os.pathsep):
                exepath = os.path.join(p, self.python_name)
                if os.path.exists(exepath):
                    executable = exepath
                    break

            if not executable:
                raise RuntimeError("No valid python executable discovered.")
        else:
            if sys.platform == 'darwin' and '__PYVENV_LAUNCHER__' in env:
                executable = os.environ['__PYVENV_LAUNCHER__']
            else:
                executable = sys.executable

        # TODO: Look for specified python distribution when outside of a virtual env when running
        dirname, exename = os.path.split(os.path.abspath(executable))
        context.executable = executable
        context.python_dir = dirname
        context.python_exe = exename
        if sys.platform == 'win32':
            binname = 'Scripts'
            incpath = 'Include'
            libpath = os.path.join(env_dir, 'Lib', 'site-packages')
        else:
            binname = 'bin'
            incpath = 'include'
            libpath = os.path.join(env_dir, 'lib',
                                   'python%d.%d' % sys.version_info[:2],
                                   'site-packages')
        context.inc_path = path = os.path.join(env_dir, incpath)
        create_if_needed(path)
        create_if_needed(libpath)
        # Issue 21197: create lib64 as a symlink to lib on 64-bit non-OS X POSIX
        if ((sys.maxsize > 2 ** 32) and (os.name == 'posix') and
                (sys.platform != 'darwin')):
            link_path = os.path.join(env_dir, 'lib64')
            if not os.path.exists(link_path):  # Issue #21643
                os.symlink('lib', link_path)
        context.bin_path = binpath = os.path.join(env_dir, binname)
        context.bin_name = binname
        context.env_exe = os.path.join(binpath, exename)
        create_if_needed(binpath)
        self.context = context
        return context


class clean_env:
    """
    Manage a clean environment.
    """

    def __init__(self, context, verbose):
        self.context = context
        self.verbose = verbose

    def reader(self, stream):
        """
        Read lines from a subprocess' output stream and either pass to a progress
        callable (if specified) or write progress information to sys.stderr.
        """
        while True:
            s = stream.readline()
            if not s:
                break

            if not self.verbose:
                sys.stderr.write('.')
            else:
                sys.stderr.write(s.decode('utf-8'))
                sys.stderr.flush()

        stream.close()

    def install_pip(self):
        name = 'pip'
        url = 'https://bootstrap.pypa.io/get-pip.py'
        _, _, path, _, _, _ = urlparse(url)
        fn = os.path.split(path)[-1]
        binpath = self.context.bin_path
        print("BINPATH: {}".format(binpath))
        distpath = os.path.join(binpath, fn)
        print("DISTPATH: {}".format(distpath))
        # Download script into the env's binaries folder
        urlretrieve(url, distpath)

        term = ''
        sys.stderr.write('Installing %s ...%s' % (name, term))
        sys.stderr.flush()

        # Install in the env
        self.run_in_env(os.path.join(binpath, fn))
        os.unlink(distpath)

    # TODO: 'save' function, to save artifacts to artifact_path
    # TODO: Option to run in a tmp directory, offer options to copy supporting files into directory?
    # TODO: Control env vars like PATH
    # TODO: Set include files/directories to copy into tmp directory
    # TODO: Build python wheel with -t to specify location of wheel file
    # TODO: pip options, like local path to search, --find-links...
    def install_dependency(self, dep, **kwargs):
        if isinstance(dep, str):
            dep = [dep]

        dep_str = ' '.join(dep)
        kwargstr = ' '.join(["--{key} {val}".format(key=k.replace('_', '-'), val=v)
                             for k, v in iter(kwargs.items())])
        cmd = os.path.join(self.context.bin_path, 'pip') + ' install ' + dep_str + ' ' + kwargstr
        parsed_cmd = shlex.split(cmd)

        print("FULL CMD: {}".format(cmd))
        print("PARSED CMD: {}".format(parsed_cmd))
        p = Popen(parsed_cmd, stdout=PIPE, stderr=PIPE, env=self.new_environ, cwd='.',
                  start_new_session=True)
        t1 = Thread(target=self.reader, args=(p.stdout,))
        t1.start()
        t2 = Thread(target=self.reader, args=(p.stderr,))
        t2.start()
        p.wait()
        t1.join()
        t2.join()

    def run_in_env(self, script):
        splitscript = shlex.split(script)
        p = Popen([self.context.python_exe] + splitscript, stdout=PIPE, stderr=PIPE, env=self.new_environ,
                  cwd='.', start_new_session=True)
        t1 = Thread(target=self.reader, args=(p.stdout,))
        t1.start()
        t2 = Thread(target=self.reader, args=(p.stderr,))
        t2.start()
        p.wait()
        t1.join()
        t2.join()
        if p.returncode != 0:  # mirror nonzero return call from child process
            sys.exit(p.returncode)

    def __enter__(self):
        # activate
        if 'VIRTUAL_ENV' in os.environ:
            vpath = os.environ['VIRTUAL_ENV']
            base_binpath = os.pathsep.join([x for x in os.environ['PATH'].split(os.pathsep)
                                            if not x.startswith(vpath)])
        else:
            base_binpath = os.environ['PATH']

        self.new_environ = dict(os.environ)
        self.new_environ['VIRTUAL_ENV'] = self.context.env_dir
        self.new_environ['PATH'] = self.context.bin_path + os.pathsep + base_binpath
        if "PYTHONHOME" in self.new_environ:
            print("HAS PYTHONHOME")
            self.new_environ.pop("PYTHONHOME")

        self.install_pip()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # TODO: Optionally remove the virtual environment.
        pass


if __name__ == "__main__":
    env = ExtendedEnvBuilder(verbose=True)
    # Note: Will always create a clean copy of current python environment.
    # Relies on other tools, build systems, to iterate over multiple python executables.
    with env.create('foo', 'python3.5') as fooenv:
        # for k, v in iter(fooenv.context.__dict__.items()):
        #     print("{}: {}".format(k, v))
        target_dir = os.path.expanduser("~/tmp")
        print("TARGET DIR: {}".format(target_dir))
        fooenv.install_dependency(
            [os.path.expanduser('~/Code/anser-indicus/'), 'numpy', 'pymystem3', 'tables', 'pyparsing',
             'scipy', 'sklearn'])  # , other_args="-t {}".format(target_dir))
        fooenv.run_in_env('../tests/helloworld.py')
